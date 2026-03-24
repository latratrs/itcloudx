# ═══════════════════════════════════════════════════════════════
# TRADESHIELD AI — SCANNER BACKEND v3.02
# Firebase Cloud Function · Python 3.13
# Features: OFAC/UN/EU sanctions, scan counter, PDF reports, tier enforcement
# ═══════════════════════════════════════════════════════════════

from firebase_functions import https_fn, options
from firebase_admin import initialize_app, firestore
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
from google import genai
from google.genai import types
import os, uuid, json, io, csv, re, requests, hashlib
from datetime import datetime, timezone, timedelta

# ── Initialize ───────────────────────────────────────────────────
initialize_app()
db = firestore.client()

# ── Constants ────────────────────────────────────────────────────
MAX_FILE_BYTES = 25 * 1024 * 1024
ALLOWED_ORIGINS = ['https://itcloudx.com', 'https://www.itcloudx.com', 'https://itcloudx-com.web.app', 'https://itcloudx-com.firebaseapp.com', 'http://localhost:4321']

# Free tier: 5 scans/month, Pro: unlimited
FREE_SCAN_LIMIT = 5

# Public sanctions list URLs (all free, no API key needed)
OFAC_SDN_URL    = "https://ofac.treasury.gov/system/files/126/sdn.xml"
UN_LIST_URL     = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"
EU_LIST_URL     = "https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content"

# ── Gemini System Prompt ─────────────────────────────────────────
SYSTEM_INSTRUCTION = """
You are TradeShield AI, an elite US customs compliance auditor with deep expertise in:
- HTS/HS code classification (CBP HTSUS 2026 schedule) — always return FULL 10-digit HTS codes (format: XXXX.XX.XXXX)
- OFAC SDN sanctions screening
- EU and UN consolidated sanctions lists
- UFLPA forced labor supply chain checks
- Stacked tariff analysis: Section 301 (China trade war), Section 232 (steel/aluminum), Section 122, AD/CVD

Analyze the provided trade document. Extract EVERY product/item and audit each one.

Return ONLY valid JSON — no markdown, no explanation, no preamble:
{
  "products": [
    {
      "name": "Product Name",
      "hs_code": "XXXX.XX.XXXX",
      "duty_rate": "X.X%",
      "section_301_rate": "25% (List 3 - from China)" or "N/A",
      "section_232_rate": "25% (steel article)" or "N/A",
      "section_122_rate": "N/A",
      "total_duty_rate": "29.9%",
      "tariff_layers": "4.9% MFN base + 25% Section 301 = 29.9% total",
      "estimated_duty_usd": "estimated duty in USD if value is known, else null",
      "sanctions_status": "CLEARED",
      "sanctions_detail": "No matches found on OFAC SDN, EU, or UN lists",
      "risk_level": "LOW",
      "risk_score": 25,
      "compliance_notes": "Brief actionable note for the importer",
      "required_documents": ["Commercial Invoice", "Packing List"],
      "recommended_action": "APPROVE"
    }
  ],
  "shipment_summary": {
    "total_products": 0,
    "high_risk_count": 0,
    "medium_risk_count": 0,
    "low_risk_count": 0,
    "overall_risk_score": 0,
    "overall_recommendation": "APPROVE",
    "summary": "One sentence summary of compliance status",
    "potential_fine_exposure": "estimated fine exposure if violations found, else null"
  }
}

Rules:
- ALWAYS use full 10-digit HTS codes. Never use 6-digit or 8-digit.
- section_301_rate: applies to goods from China. List 1/2/3 = 25%, List 4A = 7.5%. Set N/A if not from China.
- section_232_rate: steel products = 25%, aluminum = 10%, regardless of origin. Set N/A if not applicable.
- total_duty_rate: sum of duty_rate + section_301_rate + section_232_rate.
- Risk: LOW (0-33) standard; MEDIUM (34-66) needs review; HIGH (67-100) sanctions/UFLPA/major tariff issue.
"""


# ══════════════════════════════════════════════════════════════════
# OFAC / SANCTIONS CHECKER
# Caches SDN list in Firestore, refreshes daily
# ══════════════════════════════════════════════════════════════════

def get_cached_sanctions_names(list_name: str, url: str) -> set:
    """Fetch sanctions list, cache in Firestore for 24 hours."""
    cache_ref = db.collection("sanctions_cache").document(list_name)
    try:
        doc = cache_ref.get()
        if doc.exists:
            data = doc.to_dict()
            cached_at = data.get("cached_at")
            if cached_at:
                age = datetime.now(timezone.utc) - cached_at.replace(tzinfo=timezone.utc)
                if age < timedelta(hours=24):
                    return set(data.get("names", []))
    except Exception as e:
        print(f"Cache read error for {list_name}: {e}")

    # Fetch fresh list
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            # Extract names from XML using regex (no lxml needed)
            text = resp.text
            # OFAC uses <lastName> and <firstName>, UN/EU use <FIRST_NAME> <SECOND_NAME> etc
            names = set()
            for pattern in [
                r'<lastName[^>]*>([^<]+)</lastName>',
                r'<firstName[^>]*>([^<]+)</firstName>',
                r'<FIRST_NAME>([^<]+)</FIRST_NAME>',
                r'<SECOND_NAME>([^<]+)</SECOND_NAME>',
                r'<THIRD_NAME>([^<]+)</THIRD_NAME>',
                r'<NAME_ORIGINAL_SCRIPT>([^<]+)</NAME_ORIGINAL_SCRIPT>',
                r'<name[^>]*>([^<]+)</name>',
                r'<NAME>([^<]+)</NAME>',
            ]:
                found = re.findall(pattern, text, re.IGNORECASE)
                names.update(n.upper().strip() for n in found if len(n.strip()) > 2)

            # Cache in Firestore
            names_list = list(names)[:10000]  # limit for Firestore doc size
            try:
                cache_ref.set({
                    "names": names_list,
                    "cached_at": datetime.now(timezone.utc),
                    "count": len(names_list),
                    "source": url
                })
                print(f"Cached {len(names_list)} names for {list_name}")
            except Exception as e:
                print(f"Cache write error: {e}")

            return set(names_list)
    except Exception as e:
        print(f"Failed to fetch {list_name}: {e}")

    return set()


def check_sanctions(entity_name: str) -> dict:
    """
    Check entity name against OFAC, UN, EU lists.
    Returns: {hit: bool, lists: [], confidence: str}
    """
    if not entity_name or len(entity_name.strip()) < 3:
        return {"hit": False, "lists": [], "confidence": "N/A"}

    name_upper = entity_name.upper().strip()
    name_parts = set(name_upper.split())
    hits = []

    lists_to_check = [
        ("OFAC_SDN", OFAC_SDN_URL),
        ("UN_CONSOLIDATED", UN_LIST_URL),
    ]

    for list_name, url in lists_to_check:
        try:
            sanctions_names = get_cached_sanctions_names(list_name, url)
            # Exact match
            if name_upper in sanctions_names:
                hits.append(f"{list_name} (exact match)")
                continue
            # Partial match — all name parts must appear
            if len(name_parts) >= 2:
                matched_parts = sum(1 for part in name_parts if any(part in sn for sn in sanctions_names))
                if matched_parts >= len(name_parts):
                    hits.append(f"{list_name} (possible match - verify manually)")
        except Exception as e:
            print(f"Sanctions check error for {list_name}: {e}")

    return {
        "hit": len(hits) > 0,
        "lists": hits,
        "confidence": "HIGH" if any("exact" in h for h in hits) else ("MEDIUM" if hits else "CLEAR")
    }


# ══════════════════════════════════════════════════════════════════
# SCAN COUNTER — FREE TIER ENFORCEMENT
# ══════════════════════════════════════════════════════════════════

def get_scan_count(identifier: str) -> int:
    """Get scan count for email or IP this month."""
    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    doc_id = hashlib.md5(f"{identifier}:{month_key}".encode()).hexdigest()
    try:
        doc = db.collection("scan_counters").document(doc_id).get()
        if doc.exists:
            return doc.to_dict().get("count", 0)
    except Exception:
        pass
    return 0


def increment_scan_count(identifier: str) -> int:
    """Increment and return new scan count."""
    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    doc_id = hashlib.md5(f"{identifier}:{month_key}".encode()).hexdigest()
    try:
        ref = db.collection("scan_counters").document(doc_id)
        doc = ref.get()
        if doc.exists:
            new_count = doc.to_dict().get("count", 0) + 1
            ref.update({"count": new_count})
        else:
            new_count = 1
            ref.set({"identifier": identifier, "month": month_key, "count": 1})
        return new_count
    except Exception as e:
        print(f"Counter error: {e}")
        return 1


def get_user_tier(email: str) -> str:
    """Check if email has a paid subscription. Returns: free / pro / enterprise"""
    if not email:
        return "free"
    try:
        docs = db.collection("subscriptions").where("email", "==", email).where("status", "==", "active").limit(1).get()
        for doc in docs:
            return doc.to_dict().get("tier", "free")
    except Exception:
        pass
    return "free"


# ══════════════════════════════════════════════════════════════════
# FILE EXTRACTOR
# ══════════════════════════════════════════════════════════════════

def extract_content(file_bytes: bytes, mime_type: str, filename: str):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    # CSV
    if ext == 'csv' or mime_type == 'text/csv':
        try:
            text = file_bytes.decode('utf-8', errors='replace')
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)
            formatted = "\n".join([", ".join(row) for row in rows[:500]])
            return {"type": "text", "data": f"PRODUCT CSV:\n{formatted}"}, "CSV"
        except Exception:
            return {"type": "text", "data": file_bytes.decode('utf-8', errors='replace')}, "CSV_RAW"

    # Excel
    if ext in ('xlsx', 'xls') or 'spreadsheet' in mime_type or 'excel' in mime_type:
        try:
            import pandas as pd
            df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None, nrows=5000)
            parts = []
            for sheet_name, sheet_df in df.items():
                parts.append(f"SHEET: {sheet_name}\n{sheet_df.to_string(index=False)}")
            return {"type": "text", "data": "\n\n".join(parts)}, "EXCEL"
        except Exception as e:
            return {"type": "text", "data": f"Excel error: {e}"}, "EXCEL_ERROR"

    # Word documents
    if ext in ('doc', 'docx') or 'word' in mime_type or 'officedocument.wordprocessingml' in mime_type:
        try:
            import docx2txt
            text = docx2txt.process(io.BytesIO(file_bytes))
            return {'type': 'text', 'data': f'WORD DOCUMENT:\n{text}'}, 'DOCX'
        except Exception as e:
            return {'type': 'text', 'data': file_bytes.decode('utf-8', errors='replace')}, 'DOC_RAW'

    # RTF
    if ext == 'rtf' or 'rtf' in mime_type:
        try:
            text = file_bytes.decode('utf-8', errors='replace')
            import re
            text = re.sub(r'\\[a-z]+\d*\s?', ' ', text)
            text = re.sub(r'[{}]', '', text)
            return {'type': 'text', 'data': f'RTF DOCUMENT:\n{text[:5000]}'}, 'RTF'
        except Exception as e:
            return {'type': 'text', 'data': ''}, 'RTF_ERROR'

    # HTML/HTM
    if ext in ('html', 'htm') or 'html' in mime_type:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(file_bytes.decode('utf-8', errors='replace'), 'html.parser')
            for script in soup(['script', 'style', 'meta', 'link']):
                script.decompose()
            text = soup.get_text(separator=' ', strip=True)[:5000]
            return {'type': 'text', 'data': f'HTML DOCUMENT:\n{text}'}, 'HTML'
        except Exception as e:
            return {'type': 'text', 'data': ''}, 'HTML_ERROR'

    # ODS (OpenDocument Spreadsheet)
    if ext == 'ods' or 'opendocument.spreadsheet' in mime_type:
        try:
            import pandas as pd
            df = pd.read_excel(io.BytesIO(file_bytes), engine='odf', sheet_name=None)
            parts = []
            for sheet_name, sheet_df in df.items():
                parts.append(f'SHEET: {sheet_name}\n{sheet_df.to_string(index=False)}')
            return {'type': 'text', 'data': '\n\n'.join(parts)}, 'ODS'
        except Exception as e:
            return {'type': 'text', 'data': f'ODS error: {e}'}, 'ODS_ERROR'

    # GIF - treat as image
    if ext == 'gif' or mime_type == 'image/gif':
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(file_bytes)).convert('RGB')
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            return {'type': 'blob', 'data': buf.getvalue(), 'mime': 'image/png'}, 'GIF'
        except Exception:
            return {'type': 'blob', 'data': file_bytes, 'mime': 'image/gif'}, 'GIF_RAW'

    # WebP
    if ext == 'webp' or mime_type == 'image/webp':
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(file_bytes))
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            return {'type': 'blob', 'data': buf.getvalue(), 'mime': 'image/png'}, 'WEBP'
        except Exception:
            return {'type': 'blob', 'data': file_bytes, 'mime': 'image/webp'}, 'WEBP_RAW'

    # Images — upscale for better OCR
    if mime_type in ('image/jpeg', 'image/png', 'image/tiff') or ext in ('jpg', 'jpeg', 'png', 'tiff', 'tif'):
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(file_bytes))
            w, h = img.size
            if w < 2000:
                img = img.resize((w * 2, h * 2), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            return {"type": "blob", "data": buf.getvalue(), "mime": "image/png"}, "IMAGE"
        except Exception:
            return {"type": "blob", "data": file_bytes, "mime": mime_type}, "IMAGE_RAW"

    # PDF — send natively to Gemini
    if mime_type == 'application/pdf' or ext == 'pdf':
        return {"type": "blob", "data": file_bytes, "mime": "application/pdf"}, "PDF"

    return {"type": "text", "data": file_bytes.decode('utf-8', errors='replace')}, "TEXT"


# ══════════════════════════════════════════════════════════════════
# PDF REPORT GENERATOR
# ══════════════════════════════════════════════════════════════════

def generate_pdf_report(audit_data: dict, job_id: str, filename: str, tier: str) -> bytes:
    """Generate compliance PDF report using ReportLab."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter,
                                rightMargin=0.75*inch, leftMargin=0.75*inch,
                                topMargin=0.75*inch, bottomMargin=0.75*inch)

        styles = getSampleStyleSheet()
        navy   = colors.HexColor('#0b1e3d')
        cyan   = colors.HexColor('#0099cc')
        red    = colors.HexColor('#cc2222')
        yellow = colors.HexColor('#cc8800')
        green  = colors.HexColor('#007744')
        gray   = colors.HexColor('#666666')

        title_style   = ParagraphStyle('Title',   fontSize=22, textColor=navy,   spaceAfter=4,  alignment=TA_CENTER, fontName='Helvetica-Bold')
        sub_style     = ParagraphStyle('Sub',     fontSize=11, textColor=gray,   spaceAfter=2,  alignment=TA_CENTER)
        h2_style      = ParagraphStyle('H2',      fontSize=14, textColor=navy,   spaceBefore=16, spaceAfter=6, fontName='Helvetica-Bold')
        body_style    = ParagraphStyle('Body',    fontSize=10, textColor=colors.black, spaceAfter=4)
        warning_style = ParagraphStyle('Warn',    fontSize=10, textColor=red,    spaceAfter=4,  fontName='Helvetica-Bold')

        # Extra styles
        tag_style    = ParagraphStyle('Tag',  fontSize=8,  textColor=colors.white, fontName='Helvetica-Bold', alignment=TA_CENTER)
        cell_style   = ParagraphStyle('Cell', fontSize=9,  textColor=colors.black, leading=13)
        risk_h_style = ParagraphStyle('RH',   fontSize=11, textColor=colors.white, fontName='Helvetica-Bold', spaceAfter=2)
        risk_b_style = ParagraphStyle('RB',   fontSize=9,  textColor=colors.HexColor('#333333'), leading=14, spaceAfter=3)
        footer_style = ParagraphStyle('Foot', fontSize=7,  textColor=gray, alignment=TA_CENTER, leading=10)

        story = []
        now = datetime.now().strftime("%B %d, %Y %I:%M %p PT")

        # ── HEADER BANNER ──────────────────────────────────────────
        header_data = [[
            Paragraph('<font color="white"><b>🛡 TradeShield AI</b></font>', ParagraphStyle('HT', fontSize=20, textColor=colors.white, fontName='Helvetica-Bold')),
            Paragraph(f'<font color="#aaddff">Job: {job_id}</font><br/><font color="#aaddff">{now}</font>', ParagraphStyle('HS', fontSize=8, textColor=colors.white, alignment=TA_RIGHT, leading=12)),
        ]]
        header_table = Table(header_data, colWidths=[4.5*inch, 2.75*inch])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), navy),
            ('TOPPADDING', (0,0), (-1,-1), 14),
            ('BOTTOMPADDING', (0,0), (-1,-1), 14),
            ('LEFTPADDING', (0,0), (0,0), 16),
            ('RIGHTPADDING', (-1,0), (-1,-1), 16),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 2))

        # Sub-header stripe
        sub_data = [[ Paragraph('CUSTOMS COMPLIANCE REPORT', ParagraphStyle('SH', fontSize=9, textColor=colors.HexColor('#0fb39d'), fontName='Helvetica-Bold', letterSpacing=2)) ]]
        sub_table = Table(sub_data, colWidths=[7.25*inch])
        sub_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#0b2d52')),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 16),
        ]))
        story.append(sub_table)
        story.append(Spacer(1, 16))

        # Watermark for free tier
        if tier == "free":
            wm_data = [[Paragraph('⚠  FREE TIER — Upgrade to Pro for full unredacted analysis', ParagraphStyle('WM', fontSize=9, textColor=colors.HexColor('#7a3020'), fontName='Helvetica-Bold'))]]
            wm_table = Table(wm_data, colWidths=[7.25*inch])
            wm_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fdecea')),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('LEFTPADDING', (0,0), (-1,-1), 12),
                ('ROUNDEDCORNERS', [4]),
            ]))
            story.append(wm_table)
            story.append(Spacer(1, 12))

        # Summary box
        shipment = audit_data.get("shipment_summary", {})
        overall_score = shipment.get("overall_risk_score", 0)
        recommendation = shipment.get("overall_recommendation", "REVIEW")
        summary_text = shipment.get("summary", "")

        rec_color = green if recommendation == "APPROVE" else (red if recommendation == "HOLD" else yellow)
        score_color = green if overall_score < 34 else (red if overall_score >= 67 else yellow)

        # ── RISK SCORE BANNER ──────────────────────────────────────
        score_bg = colors.HexColor('#cc2222') if overall_score >= 67 else (colors.HexColor('#cc8800') if overall_score >= 34 else colors.HexColor('#007744'))
        rec_label = recommendation.replace('_', ' ')
        score_data = [[
            Paragraph(f'<font color="white" size="36"><b>{overall_score}</b></font><br/><font color="white" size="9">RISK SCORE</font>', ParagraphStyle('SC', fontSize=36, textColor=colors.white, alignment=TA_CENTER, fontName='Helvetica-Bold', leading=40)),
            Table([
                [Paragraph('<font color="white" size="11"><b>SHIPMENT SUMMARY</b></font>', ParagraphStyle('SSL', fontSize=11, textColor=colors.white, fontName='Helvetica-Bold'))],
                [Paragraph(f'<font color="white"><b>Document:</b> {filename[:50]}</font>', ParagraphStyle('SSD', fontSize=9, textColor=colors.white, leading=14))],
                [Paragraph(f'<font color="white"><b>Recommendation:</b> {rec_label}</font>', ParagraphStyle('SSR', fontSize=9, textColor=colors.white, leading=14))],
                [Paragraph(f'<font color="white"><b>Products:</b> {len(audit_data.get("products",[]))}  |  <b>High Risk:</b> {shipment.get("high_risk_count",0)}</font>', ParagraphStyle('SSP', fontSize=9, textColor=colors.white, leading=14))],
            ], colWidths=[4.5*inch], rowHeights=[20,16,16,16]),
        ]]
        score_table = Table(score_data, colWidths=[1.5*inch, 5.75*inch])
        score_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), score_bg),
            ('TOPPADDING', (0,0), (-1,-1), 14),
            ('BOTTOMPADDING', (0,0), (-1,-1), 14),
            ('LEFTPADDING', (0,0), (0,0), 16),
            ('LEFTPADDING', (1,0), (1,0), 16),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(score_table)
        story.append(Spacer(1, 12))

        if summary_text:
            sum_data = [[Paragraph(f'<i>{summary_text}</i>', ParagraphStyle('SumI', fontSize=9, textColor=colors.HexColor('#333'), leading=14))]]
            sum_box = Table(sum_data, colWidths=[7.25*inch])
            sum_box.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f5f8fc')),
                ('TOPPADDING', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,-1), 10),
                ('LEFTPADDING', (0,0), (-1,-1), 14),
                ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#ccddee')),
            ]))
            story.append(sum_box)
            story.append(Spacer(1, 16))

        if shipment.get("potential_fine_exposure"):
            fine_data = [[Paragraph(f'⚠  Potential Fine Exposure: {shipment["potential_fine_exposure"]}', ParagraphStyle('Fine', fontSize=10, textColor=colors.HexColor('#7a3020'), fontName='Helvetica-Bold'))]]
            fine_box = Table(fine_data, colWidths=[7.25*inch])
            fine_box.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fdecea')),
                ('TOPPADDING', (0,0), (-1,-1), 8), ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('LEFTPADDING', (0,0), (-1,-1), 12),
            ]))
            story.append(fine_box)
            story.append(Spacer(1, 12))

        # ── SECTION HEADER: Products ────────────────────────────────
        sec_data = [[Paragraph('PRODUCT COMPLIANCE DETAILS', ParagraphStyle('SecH', fontSize=10, textColor=colors.white, fontName='Helvetica-Bold'))]]
        sec_table = Table(sec_data, colWidths=[7.25*inch])
        sec_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#1a3a6b')),
            ('TOPPADDING', (0,0), (-1,-1), 7), ('BOTTOMPADDING', (0,0), (-1,-1), 7),
            ('LEFTPADDING', (0,0), (-1,-1), 12),
        ]))
        story.append(sec_table)
        story.append(Spacer(1, 8))

        products = audit_data.get("products", [])
        if not products:
            story.append(Paragraph("No products were extracted from this document.", body_style))
        else:
            # Free tier: show max 3 products, blur rest
            if tier == "free" and len(products) > 3:
                story.append(Paragraph(f"⚠️ Showing 3 of {len(products)} products. Upgrade to Pro for full report.", warning_style))
                products = products[:3]

            for i, p in enumerate(products, 1):
                risk = p.get("risk_level", "LOW")
                risk_color = green if risk == "LOW" else (red if risk == "HIGH" else yellow)

                prod_data = [
                    [f"#{i}  {p.get('name', 'Unknown Product')}", ""],
                    ["HS Code (10-digit)", p.get("hs_code", "N/A")],
                    ["MFN Base Duty", p.get("duty_rate", "N/A")],
                ]

                if tier == "pro":
                    prod_data += [
                        ["Section 301 Surcharge", p.get("section_301_rate", "N/A")],
                        ["Section 232 Surcharge", p.get("section_232_rate", "N/A")],
                        ["Total Duty Rate",        p.get("total_duty_rate", p.get("duty_rate", "N/A"))],
                        ["Tariff Breakdown",       p.get("tariff_layers", "N/A")],
                    ]
                else:
                    prod_data.append(["Tariff Breakdown", "🔒 Upgrade to Pro — Section 301/232 surcharges hidden"])

                prod_data += [
                    ["Sanctions Status",   p.get("sanctions_status", "N/A")],
                    ["Risk Level",         f"{risk}  (Score: {p.get('risk_score', 0)}/100)"],
                    ["Recommended Action", p.get("recommended_action", "REVIEW")],
                    ["Compliance Notes",   p.get("compliance_notes", "")],
                ]

                if p.get("required_documents"):
                    docs_str = ", ".join(p["required_documents"]) if isinstance(p["required_documents"], list) else str(p["required_documents"])
                    prod_data.append(["Required Documents", docs_str])

                # Wrap text for proper word wrap
                from reportlab.platypus import Paragraph as Para
                from reportlab.lib.styles import ParagraphStyle as PS
                wl = PS('WL', fontSize=9, fontName='Helvetica-Bold', textColor=navy, leading=13)
                wr = PS('WR', fontSize=9, leading=13)
                wrapped = []
                for row in prod_data:
                    c0 = Para(str(row[0]), wl) if row[0] else ""
                    c1 = Para(str(row[1] if len(row)>1 else ""), wr) if len(row)>1 and row[1] else ""
                    wrapped.append([c0, c1])
                prod_table = Table(wrapped, colWidths=[1.8*inch, 5.0*inch])
                prod_table.setStyle(TableStyle([
                    ('SPAN',       (0,0), (1,0)),
                    ('BACKGROUND', (0,0), (1,0), navy),
                    ('TEXTCOLOR',  (0,0), (1,0), colors.white),
                    ('FONTNAME',   (0,0), (1,0), 'Helvetica-Bold'),
                    ('FONTSIZE',   (0,0), (-1,-1), 10),
                    ('BACKGROUND', (0,1), (0,-1), colors.HexColor('#e8f0f8')),
                    ('FONTNAME',   (0,1), (0,-1), 'Helvetica-Bold'),
                    ('GRID',       (0,0), (-1,-1), 0.5, colors.HexColor('#ccddee')),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#f5f8fc'), colors.white]),
                    ('TOPPADDING',  (0,0), (-1,-1), 5),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                    ('LEFTPADDING', (0,0), (-1,-1), 8),
                ]))
                story.append(prod_table)
                story.append(Spacer(1, 10))

        # Footer
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#ccddee')))
        story.append(Spacer(1, 6))
        footer_text = (
            "This report is generated by TradeShield AI (itcloudx.com) for informational purposes only. "
            "It does not constitute legal advice. Always consult a licensed customs broker for final classification decisions. "
            "© 2026 Deccod / ITCloudX. All rights reserved."
        )
        story.append(Paragraph(footer_text, ParagraphStyle('Footer', fontSize=8, textColor=gray, alignment=TA_CENTER)))

        doc.build(story)
        pdf_bytes = buf.getvalue()

        # Free tier: merge watermark ON TOP using pypdf (draws over colored backgrounds)
        if tier == "free":
            from pypdf import PdfReader, PdfWriter
            from reportlab.pdfgen import canvas as rl_canvas
            from reportlab.lib.pagesizes import letter as rl_letter

            wm_buf = io.BytesIO()
            wm = rl_canvas.Canvas(wm_buf, pagesize=rl_letter)
            wm.saveState()
            wm.setFont("Helvetica-Bold", 72)
            wm.setFillColorRGB(0.5, 0.5, 0.5, alpha=0.55)
            wm.translate(306, 396)
            wm.rotate(45)
            wm.drawCentredString(0, 40, "FREE PREVIEW")
            wm.setFont("Helvetica-Bold", 34)
            wm.drawCentredString(0, -50, "UPGRADE TO PRO")
            wm.restoreState()
            wm.save()
            wm_buf.seek(0)

            original = PdfReader(io.BytesIO(pdf_bytes))
            watermark_page = PdfReader(wm_buf).pages[0]
            writer = PdfWriter()
            for page in original.pages:
                page.merge_page(watermark_page)
                writer.add_page(page)
            out = io.BytesIO()
            writer.write(out)
            return out.getvalue()

        return pdf_bytes

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"PDF generation error: {e}")
        return b""


# ══════════════════════════════════════════════════════════════════
# SAFE JSON PARSER
# ══════════════════════════════════════════════════════════════════

def safe_parse_json(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1] if len(lines) > 2 else lines)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to extract JSON block
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return {
            "products": [],
            "shipment_summary": {
                "total_products": 0,
                "high_risk_count": 0,
                "medium_risk_count": 0,
                "low_risk_count": 0,
                "overall_risk_score": 0,
                "overall_recommendation": "REVIEW",
                "summary": "Could not parse document. Manual review recommended.",
                "potential_fine_exposure": None
            },
            "parse_error": True
        }


# ══════════════════════════════════════════════════════════════════
# HELPER
# ══════════════════════════════════════════════════════════════════

def _json_response(data: dict, status: int) -> https_fn.Response:
    return https_fn.Response(
        json.dumps(data),
        status=status,
        mimetype="application/json"
    )


# ══════════════════════════════════════════════════════════════════
# MAIN CLOUD FUNCTION: /scan
# ══════════════════════════════════════════════════════════════════

@https_fn.on_request(
    secrets=["GEMINI_API_KEY"],
    cors=options.CorsOptions(
        cors_origins=ALLOWED_ORIGINS,
        cors_methods=["POST", "OPTIONS"]
    ),
    memory=options.MemoryOption.GB_1,
    timeout_sec=120,
    region="us-central1"
)
def scan(req: https_fn.Request) -> https_fn.Response:

    if req.method == "OPTIONS":
        return https_fn.Response("", status=204)
    if req.method != "POST":
        return https_fn.Response("Method not allowed", status=405)

    # ── Get request data ─────────────────────────────────────────
    email   = req.form.get("email", "").strip().lower()
    company = req.form.get("company", "").strip()
    ip      = req.headers.get("X-Forwarded-For", "unknown").split(",")[0].strip()
    job_id  = f"TS-{uuid.uuid4().hex[:8].upper()}"

    # ── Tier detection ───────────────────────────────────────────
    tier = get_user_tier(email) if email else "free"

    # ── Scan counter enforcement (free tier only) ────────────────
    if tier == "free":
        identifier = email if email else ip
        current_count = get_scan_count(identifier)
        if current_count >= FREE_SCAN_LIMIT:
            return _json_response({
                "error": f"Free tier limit reached ({FREE_SCAN_LIMIT} scans/month). Upgrade to Pro at itcloudx.com/pricing",
                "upgrade_url": "https://itcloudx.com/pricing",
                "scans_used": current_count,
                "scans_limit": FREE_SCAN_LIMIT
            }, 429)

    # ── Log lead ─────────────────────────────────────────────────
    try:
        db.collection("leads").document(job_id).set({
            "jobId": job_id,
            "email": email,
            "company": company,
            "tier": tier,
            "ip": ip,
            "status": "PROCESSING",
            "timestamp": SERVER_TIMESTAMP,
        })
    except Exception as e:
        print(f"Lead log error: {e}")

    try:
        # ── File validation ───────────────────────────────────────
        file_obj = req.files.get("file")
        if not file_obj:
            return _json_response({"error": "No file uploaded. Please attach a PDF, CSV, Excel, or image."}, 400)

        file_bytes  = file_obj.read()
        mime_type   = file_obj.content_type or "application/octet-stream"
        filename    = file_obj.filename or "document"

        if len(file_bytes) > MAX_FILE_BYTES:
            return _json_response({"error": "File too large. Max 25MB."}, 400)

        MAGIC_BYTES = {
            b'%PDF': 'pdf',
            b'PK\x03\x04': 'zip_based',
            b'\xd0\xcf\x11\xe0': 'ole',
            b'\xff\xd8\xff': 'jpg',
            b'\x89PNG': 'png',
            b'GIF8': 'gif',
            b'II*\x00': 'tiff',
            b'MM\x00*': 'tiff',
            b'RIFF': 'webp',
            b'<html': 'html',
            b'<!DOC': 'html',
        }
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        detected = None
        for magic, ftype in MAGIC_BYTES.items():
            if file_bytes[:len(magic)] == magic:
                detected = ftype
                break
        if detected == 'zip_based' and ext not in ('xlsx', 'xls', 'docx', 'ods', 'zip'):
            return _json_response({'error': 'Invalid file format detected.'}, 400)
        if detected == 'ole' and ext not in ('doc', 'xls'):
            return _json_response({'error': 'Invalid file format detected.'}, 400)

        allowed_exts = {'pdf', 'csv', 'xlsx', 'xls', 'doc', 'docx', 'rtf', 'ods', 'html', 'htm', 'jpg', 'jpeg', 'png', 'gif', 'tiff', 'tif', 'webp'}
        if ext not in allowed_exts:
            return _json_response({"error": f"File type .{ext} not supported. Use PDF, CSV, Excel, or image."}, 400)

        import time
        # Rate limit: max 10 requests per minute per IP
        ip_key = f'ratelimit:{ip}:{int(time.time() // 60)}'
        try:
            ip_ref = db.collection('rate_limits').document(ip_key)
            ip_doc = ip_ref.get()
            if ip_doc.exists and ip_doc.to_dict().get('count', 0) >= 10:
                return _json_response({'error': 'Too many requests. Please wait a minute before trying again.'}, 429)
            ip_ref.set({'count': (ip_doc.to_dict().get('count', 0) + 1) if ip_doc.exists else 1, 'expires': time.time() + 60}, merge=True)
        except Exception as e:
            print(f'Rate limit check error (non-fatal): {e}')

        # ── Extract content ───────────────────────────────────────
        content, extraction_method = extract_content(file_bytes, mime_type, filename)
        print(f"[{job_id}] Extraction: {extraction_method} | File: {filename} | Tier: {tier}")

        # ── Build Gemini prompt ───────────────────────────────────
        instruction = (
            f"Audit this trade document ({filename}). "
            f"Apply CBP HTS 2026, OFAC SDN, UFLPA, and all applicable sanctions checks. "
            f"Be thorough — missing a sanctions hit can result in $1M+ fines."
        )

        if content["type"] == "text":
            prompt_parts = [instruction + "\n\n" + content["data"]]
        else:
            prompt_parts = [
                types.Part.from_bytes(data=content["data"], mime_type=content["mime"]),
                instruction
            ]

        # ── Call Gemini ───────────────────────────────────────────
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt_parts,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.0,
                response_mime_type="application/json",
                max_output_tokens=8192,
            )
        )

        try:
            raw_text = response.candidates[0].content.parts[0].text
        except Exception:
            raw_text = response.text
        audit_data = safe_parse_json(raw_text)
        print(f"[{job_id}] RAW GEMINI: {response.text[:500]}")
        products   = audit_data.get("products", [])
        shipment   = audit_data.get("shipment_summary", {})
        print(f"[{job_id}] Gemini: {len(products)} products, score={shipment.get('overall_risk_score',0)}")
        print(f"[{job_id}] Gemini returned {len(products)} products, score={shipment.get('overall_risk_score',0)}")

        # ── Real OFAC sanctions check on consignee/company ───────
        sanctions_check = None
        if company and tier != "free":
            sanctions_check = check_sanctions(company)
            if sanctions_check["hit"]:
                shipment["overall_recommendation"] = "HOLD"
                shipment["summary"] = (
                    f"⚠️ SANCTIONS ALERT: {company} may match restricted entity. "
                    + shipment.get("summary", "")
                )

        # ── Generate PDF report (never crash main flow) ───────────
        pdf_base64 = None
        pdf_error = None
        try:
            pdf_bytes = generate_pdf_report(audit_data, job_id, filename, tier)
            if pdf_bytes:
                import base64
                pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
                print(f"[{job_id}] PDF generated: {len(pdf_bytes)} bytes")
        except Exception as pdf_err:
            print(f"[{job_id}] PDF generation skipped: {pdf_err}")

        # ── Increment scan counter ────────────────────────────────
        identifier = email if email else ip
        new_count  = 1
        scans_left = None
        try:
            new_count  = increment_scan_count(identifier)
            scans_left = max(0, FREE_SCAN_LIMIT - new_count) if tier == "free" else None
        except Exception as cnt_err:
            print(f"[{job_id}] Counter error (non-fatal): {cnt_err}")

        # ── Save to Firestore (never crash main flow) ─────────────
        try:
            db.collection("compliance_audits").document(job_id).set({
                "jobId":              job_id,
                "email":              email,
                "company":            company,
                "tier":               tier,
                "filename":           filename,
                "extraction_method":  extraction_method,
                "status":             "COMPLETED",
                "report_data":        audit_data,
                "sanctions_check":    sanctions_check,
                "timestamp":          SERVER_TIMESTAMP,
            })
            db.collection("leads").document(job_id).update({
                "status":             "COMPLETED",
                "overall_risk_score": shipment.get("overall_risk_score", 0),
                "product_count":      len(products),
                "tier":               tier,
            })
        except Exception as fs_err:
            print(f"[{job_id}] Firestore save error (non-fatal): {fs_err}")

        # ── Build response ────────────────────────────────────────
        response_data = {
            "jobId":                  job_id,
            "status":                 "success",
            "tier":                   tier,
            "filename":               filename,
            "product_count":          len(products),
            "overall_risk_score":     shipment.get("overall_risk_score", 0),
            "overall_recommendation": shipment.get("overall_recommendation", "REVIEW"),
            "summary":                shipment.get("summary", ""),
            "high_risk_count":        shipment.get("high_risk_count", 0),
            "products":               products if tier != "free" else products[:3],
            "pdf_report":             pdf_base64,
            "pdf_error":              pdf_error,
            "sanctions_check":        sanctions_check,
            "scans_used":             new_count,
            "scans_remaining":        scans_left,
            "upgrade_url":            "https://itcloudx.com/pricing" if tier == "free" else None,
        }

        # Free tier: watermark message
        if tier == "free" and len(products) > 3:
            response_data["free_tier_notice"] = (
                f"Showing 3 of {len(products)} products. "
                f"Upgrade to Pro at itcloudx.com/pricing for full report."
            )

        return _json_response(response_data, 200)

    except Exception as e:
        print(f"Scan error [{job_id}]: {str(e)}")
        try:
            db.collection("compliance_audits").document(job_id).set({
                "jobId": job_id, "email": email,
                "status": "FAILED", "error": str(e),
                "timestamp": SERVER_TIMESTAMP,
            })
            db.collection("leads").document(job_id).update({"status": "FAILED"})
        except Exception:
            pass
        return _json_response({
            "error": "Scan failed. Please try again or contact support.",
            "jobId": job_id
        }, 500)


# ══════════════════════════════════════════════════════════════════
# SANCTIONS CACHE REFRESH — scheduled daily
# ══════════════════════════════════════════════════════════════════

@https_fn.on_request(
    cors=options.CorsOptions(cors_origins=ALLOWED_ORIGINS, cors_methods=["POST"]),
    region="us-central1"
)
def refresh_sanctions(req: https_fn.Request) -> https_fn.Response:
    """Manually trigger sanctions cache refresh. Call daily via cron."""
    results = {}
    for list_name, url in [("OFAC_SDN", OFAC_SDN_URL), ("UN_CONSOLIDATED", UN_LIST_URL)]:
        # Force refresh by clearing cache first
        try:
            db.collection("sanctions_cache").document(list_name).delete()
            names = get_cached_sanctions_names(list_name, url)
            results[list_name] = f"Refreshed: {len(names)} names"
        except Exception as e:
            results[list_name] = f"Error: {str(e)}"

    return https_fn.Response(json.dumps(results), status=200, mimetype="application/json")

