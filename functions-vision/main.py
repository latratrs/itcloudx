"""TradeShield AI — Google Cloud Vision API scan handler.

Provides OCR, label detection, object localization, and barcode extraction
for uploaded images and PDFs.  Runs as a Google Cloud Function (HTTP trigger).

Supported input types (multipart/form-data POST):
  - Images : JPEG, PNG, TIFF, WebP, BMP, GIF
  - Documents: PDF  (first page rendered via PyMuPDF; falls back to inline
                     document-text-detection for single-page PDFs)

Fields accepted:
  file     (required) — the uploaded file
  email    (optional) — submitter e-mail, echoed in the response
  company  (optional) — company / consignee name, echoed in the response

Response JSON:
  {
    "status":     "success" | "error",
    "job_id":     "<unique scan ID>",
    "filename":   "<original filename>",
    "email":      "<submitted email>",
    "company":    "<submitted company>",
    "ocr_text":   "<full extracted text>",
    "labels":     [{"description": "...", "score": 0.0–1.0}, ...],
    "objects":    [{"name": "...", "score": 0.0–1.0}, ...],
    "barcodes":   [{"type": "UPC/EAN" | "QR/URL", "value": "..."}, ...],
    "page_count": <int>,
    "note":       "<optional processing note>"
  }

Deployment (Cloud Functions gen2, Python 3.11+):
  gcloud functions deploy scan_handler \\
    --gen2 \\
    --runtime=python311 \\
    --trigger-http \\
    --allow-unauthenticated \\
    --source=functions/ \\
    --entry-point=scan_handler \\
    --region=us-central1

Prerequisites:
  1. Enable the Cloud Vision API in your Google Cloud project:
       gcloud services enable vision.googleapis.com
  2. Grant the function's service account the
     "Cloud Vision API User" role (or roles/ml.admin).
  3. (Optional) Set GOOGLE_CLOUD_PROJECT env var if your project ID differs
     from what Application Default Credentials detect automatically.
"""

import json
import re
import uuid

import functions_framework
from google.cloud import vision


# ---------------------------------------------------------------------------
# Cloud Function entry point
# ---------------------------------------------------------------------------

@functions_framework.http
def scan_handler(request):
    """HTTP entry point — accepts a multipart/form-data POST with a 'file' field."""

    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
    }

    # Pre-flight
    if request.method == "OPTIONS":
        return ("", 204, cors_headers)

    if request.method != "POST":
        return (
            json.dumps({"status": "error", "error": "Method not allowed. Use POST."}),
            405,
            {**cors_headers, "Content-Type": "application/json"},
        )

    try:
        uploaded_file = request.files.get("file")
        if not uploaded_file:
            return (
                json.dumps({
                    "status": "error",
                    "error": "No file provided. Send a multipart/form-data POST with a 'file' field.",
                }),
                400,
                {**cors_headers, "Content-Type": "application/json"},
            )

        file_bytes: bytes = uploaded_file.read()
        filename: str = uploaded_file.filename or "upload"
        content_type: str = uploaded_file.content_type or ""
        email: str = request.form.get("email", "")
        company: str = request.form.get("company", "")

        job_id = f"VISION-{uuid.uuid4().hex[:6].upper()}"
        is_pdf = filename.lower().endswith(".pdf") or "pdf" in content_type.lower()

        client = vision.ImageAnnotatorClient()

        if is_pdf:
            result = _scan_pdf(client, file_bytes, filename)
        else:
            result = _scan_image(client, file_bytes, filename)

        company_name = company or _extract_company_name(result.get("ocr_text", ""))
        result.update({
            "job_id": job_id,
            "email": email,
            "company": company,
            "company_name": company_name,
            "scanner_type": "SHERLOCK VISION API",
        })

        return (
            json.dumps(result),
            200,
            {**cors_headers, "Content-Type": "application/json"},
        )

    except Exception as exc:  # noqa: BLE001
        return (
            json.dumps({"status": "error", "error": f"Vision API error: {str(exc)}"}),
            500,
            {**cors_headers, "Content-Type": "application/json"},
        )


# ---------------------------------------------------------------------------
# Vision API helpers
# ---------------------------------------------------------------------------

def _scan_image(
    client: vision.ImageAnnotatorClient,
    image_bytes: bytes,
    filename: str,
) -> dict:
    """Run Vision API on an image: document OCR, label, object, and barcode detection."""

    image = vision.Image(content=image_bytes)

    # Batch all feature requests in a single API call for efficiency and cost savings.
    features = [
        vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION),
        vision.Feature(type_=vision.Feature.Type.LABEL_DETECTION, max_results=10),
        vision.Feature(type_=vision.Feature.Type.OBJECT_LOCALIZATION, max_results=10),
    ]

    annotate_request = vision.AnnotateImageRequest(image=image, features=features)
    response = client.annotate_image(annotate_request)

    # Full-document OCR (preserves layout better than TEXT_DETECTION alone)
    ocr_text = ""
    if response.full_text_annotation and response.full_text_annotation.text:
        ocr_text = response.full_text_annotation.text.strip()

    labels = [
        {"description": lbl.description, "score": round(lbl.score, 3)}
        for lbl in response.label_annotations
    ]

    objects = [
        {"name": obj.name, "score": round(obj.score, 3)}
        for obj in response.localized_object_annotations
    ]

    barcodes = _extract_barcodes(ocr_text)

    return {
        "status": "success",
        "filename": filename,
        "ocr_text": ocr_text,
        "labels": labels,
        "objects": objects,
        "barcodes": barcodes,
        "page_count": 1,
    }


def _scan_pdf(
    client: vision.ImageAnnotatorClient,
    pdf_bytes: bytes,
    filename: str,
) -> dict:
    """Scan a PDF using Vision API.

    Primary path: convert first page to PNG via PyMuPDF (fitz) at 150 DPI,
    then run full Vision API analysis (_scan_image).

    Fallback (PyMuPDF not installed): send raw bytes to
    document_text_detection — works reliably for single-page PDFs.
    """
    try:
        import fitz  # PyMuPDF — pip install PyMuPDF

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_count = len(doc)

        # Render first page at 150 DPI (good balance of OCR quality vs. speed)
        page = doc.load_page(0)
        mat = fitz.Matrix(150 / 72, 150 / 72)
        pix = page.get_pixmap(matrix=mat)
        image_bytes = pix.tobytes("png")
        doc.close()

        result = _scan_image(client, image_bytes, filename)
        result["page_count"] = page_count
        if page_count > 1:
            result["note"] = f"OCR performed on page 1 of {page_count}. Multi-page async scanning coming soon."
        return result

    except ImportError:
        # Fallback for environments without PyMuPDF.
        # Vision API's document_text_detection accepts raw PDF bytes inline
        # for single-page documents.
        image = vision.Image(content=pdf_bytes)
        response = client.document_text_detection(image=image)

        ocr_text = ""
        if response.full_text_annotation and response.full_text_annotation.text:
            ocr_text = response.full_text_annotation.text.strip()

        barcodes = _extract_barcodes(ocr_text)

        return {
            "status": "success",
            "filename": filename,
            "ocr_text": ocr_text,
            "labels": [],
            "objects": [],
            "barcodes": barcodes,
            "page_count": 1,
            "note": "PyMuPDF not installed — label and object detection unavailable for PDFs.",
        }


def _extract_barcodes(text: str) -> list:
    """Extract barcode values embedded in OCR-decoded text.

    Handles:
    - UPC-A (12 digits)
    - EAN-13 (13 digits)
    - URLs typically encoded in QR codes
    """
    barcodes: list = []
    seen: set = set()

    # UPC-A / EAN-13 — standalone digit runs of exactly 12 or 13 characters
    for match in re.finditer(r"(?<!\d)(\d{12,13})(?!\d)", text):
        val = match.group(1)
        if val not in seen:
            seen.add(val)
            barcodes.append({"type": "UPC/EAN", "value": val})

    # URLs — typically QR-code payloads
    for match in re.finditer(r"https?://[^\s]+", text):
        val = match.group(0).rstrip(".,;)")
        if val not in seen:
            seen.add(val)
            barcodes.append({"type": "QR/URL", "value": val})

    return barcodes
