# Vision API Integration — Setup & Deployment Guide

## Overview

This integration replaces the previous scan widget with a unified **Google Cloud Vision API** component. Both the homepage (`/`) and audit tool (`/audit`) now use the same reusable `ScanWidget.astro` component, backed by a single Python Cloud Function (`functions/scan_handler.py`).

| Feature | Implementation |
|---------|---------------|
| OCR (text extraction) | `DOCUMENT_TEXT_DETECTION` |
| Label detection | `LABEL_DETECTION` (top 10) |
| Object localization | `OBJECT_LOCALIZATION` (top 10) |
| Barcode / QR extraction | Regex patterns over OCR text |
| PDF support | PyMuPDF → image → Vision API |

---

## 1. Enable Google Cloud Vision API

In your Google Cloud project (`itcloudx-com`):

```bash
gcloud services enable vision.googleapis.com --project=itcloudx-com
```

No additional configuration is required — the Cloud Function uses Application Default Credentials automatically.

**Cost:** The Vision API free tier covers **1,000 units/month** for OCR, label, and object detection. For a typical development workload this is zero cost.

---

## 2. Deploy the Cloud Function

```bash
cd /path/to/itcloudx

gcloud functions deploy scan_handler \
  --gen2 \
  --runtime=python311 \
  --trigger-http \
  --allow-unauthenticated \
  --source=functions/ \
  --entry-point=scan_handler \
  --region=us-central1 \
  --project=itcloudx-com
```

After deployment, note the function URL (e.g. `https://us-central1-itcloudx-com.cloudfunctions.net/scan_handler`).

### Optional: install PyMuPDF for multi-page PDF support

`PyMuPDF` is already listed in `functions/requirements.txt` and will be installed automatically during deployment. It enables rendering any PDF page to an image before sending to Vision API.

---

## 3. Configure the Frontend

Set the function URL as a build-time environment variable:

```bash
# astrowind/.env  (local development)
VISION_FUNCTION_URL=https://us-central1-itcloudx-com.cloudfunctions.net/scan_handler
```

For Firebase Hosting / CI:

```bash
# Set in your build pipeline or Firebase App Hosting env config
VISION_FUNCTION_URL=https://us-central1-itcloudx-com.cloudfunctions.net/scan_handler
```

> **Without `VISION_FUNCTION_URL`**: the widget runs in **demo mode** — it returns sample Vision API data so you can develop and test the UI without a live backend.

---

## 4. Build and Deploy the Frontend

```bash
cd astrowind
npm install
npm run build          # static output → dist/

cd ..
firebase deploy --only hosting   # deploys dist/client/ to Firebase Hosting
```

Or use the existing one-command script:

```bash
~/itcloudx/publish.sh
```

---

## 5. Test the Integration

### Local smoke test (Vision API backend)

```bash
# Activate the Python venv
source ~/tradeshield-env/bin/activate
pip install functions-framework google-cloud-vision PyMuPDF

# Start the function locally
cd functions
functions-framework --target=scan_handler --port=8080 &

# Send a test image
curl -X POST http://localhost:8080 \
  -F "file=@/path/to/invoice.jpg" \
  -F "email=test@example.com"
```

Expected response:

```json
{
  "status": "success",
  "job_id": "VISION-XXXXXXXXXX",
  "filename": "invoice.jpg",
  "ocr_text": "...",
  "labels": [{"description": "Document", "score": 0.99}, ...],
  "objects": [{"name": "Paper", "score": 0.88}, ...],
  "barcodes": [],
  "page_count": 1
}
```

### UI smoke test

1. Open `https://itcloudx.com` or `https://itcloudx.com/audit`
2. Upload a JPG/PNG invoice or product image
3. Enter an email address and click **Run Vision Scan**
4. Verify the four result tabs appear: **OCR Text**, **Labels**, **Objects**, **Barcodes**

---

## 6. Architecture

```
Browser (ScanWidget.astro)
        │  multipart/form-data POST
        ▼
Google Cloud Functions (scan_handler.py)
        │  google-cloud-vision SDK
        ▼
Google Cloud Vision API
  ├── DOCUMENT_TEXT_DETECTION  →  ocr_text
  ├── LABEL_DETECTION          →  labels[]
  ├── OBJECT_LOCALIZATION      →  objects[]
  └── regex on ocr_text        →  barcodes[]
        │
        ▼ JSON response
Browser renders tabbed results
```

---

## 7. File Changes Summary

| File | Change |
|------|--------|
| `functions/scan_handler.py` | **New** — Vision API Cloud Function |
| `functions/requirements.txt` | **New** — Python dependencies |
| `astrowind/src/components/widgets/ScanWidget.astro` | **New** — reusable scan widget |
| `astrowind/src/pages/index.astro` | Updated — uses ScanWidget, removed ~200 lines of inline JS |
| `astrowind/src/pages/audit.astro` | Updated — uses ScanWidget, replaced stub implementation |
| `astrowind/src/pages/api/scan.ts` | Updated — Vision API demo data, `VISION_FUNCTION_URL` env var |

---

## 8. Adding Gemini Compliance Analysis (Future)

To add Gemini-powered HS code classification and sanctions screening on top of the Vision API OCR text, extend `scan_handler.py`:

```python
from google import genai

def _analyze_compliance(ocr_text: str) -> dict:
    client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=f"Analyze this shipment document for HS codes and compliance issues:\n\n{ocr_text}"
    )
    return {"compliance_notes": response.text}
```

Then call `_analyze_compliance(result['ocr_text'])` in `scan_handler` and merge the result. Add the Gemini tab to `ScanWidget.astro` when ready.
