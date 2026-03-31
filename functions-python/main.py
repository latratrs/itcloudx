# ═══════════════════════════════════════════════════════════════
# TRADESHIELD AI — SCANNER BACKEND v3.02
# Firebase Cloud Function · Python 3.13
# Features: OFAC/UN/EU sanctions, scan counter, PDF reports, tier enforcement
# ═══════════════════════════════════════════════════════════════

from firebase_functions import https_fn, options
from firebase_admin import initialize_app, firestore, auth
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
import os, uuid, json, io, csv, re, requests, hashlib
from datetime import datetime, timezone, timedelta

from hts_lookup import enrich_products, validate_hts
from cross_lookup import get_cross_summary
from report_validator import validate_and_fix
# ── Initialize ───────────────────────────────────────────────────
initialize_app()
db = firestore.client()

# ── Constants ────────────────────────────────────────────────────
MAX_FILE_BYTES = 25 * 1024 * 1024
ALLOWED_ORIGINS = [
    "https://itcloudx.com",
    "https://www.itcloudx.com",
    "https://itcloudx-com.web.app",
    "https://itcloudx-com.firebaseapp.com",
    "http://localhost:4321",
]

# Free tier: 5 scans/month
FREE_SCAN_LIMIT = 5

# Tier scan quotas (per calendar month)
TIER_LIMITS = {
    "free": 5,
    "pro": 500,
    "premium": 2500,
    "enterprise": 10**9,  # effectively unlimited
}

# PayPal Plan IDs (live)
PAYPAL_PLAN_TO_TIER = {
    "P-1NU513273T353600TNGWN7CQ": "pro",      # Pro monthly
    "P-7GJ23119F6048484ANGWOEWY": "pro",      # Pro yearly
    "P-6B6986702B7923417NGWOKBQ": "premium",  # Premium monthly
    "P-4XK302596Y708620JNGWOMYA": "premium",  # Premium yearly
}

# Public sanctions list URLs (all free, no API key needed)
OFAC_SDN_URL = "https://ofac.treasury.gov/system/files/126/sdn.xml"
UN_LIST_URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"
EU_LIST_URL = "https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content"

# ── Gemini System Prompt ─────────────────────────────────────────
SYSTEM_INSTRUCTION = """
You are TradeShield AI, a US Customs compliance analyst. Your job is to analyze trade documents and produce structured, accurate, human-readable compliance assessments.

SCOPE: US imports and exports only. Apply CBP HTSUS 2026, OFAC SDN, UFLPA, and all current US trade regulations.

ACCURACY RULES (CRITICAL):
- Use FULL 10-digit HTS codes (format: XXXX.XX.XXXX). Never guess — if uncertain, use the closest verified code and flag for review.
- section_301_rate: China origin goods only. List 1/2/3 = 25%, List 4A = 7.5%. Set "N/A" if not from China.
- section_232_rate: Steel = 25%, Aluminum = 10%, regardless of origin. Set "N/A" if not applicable.
- section_122_rate: Emergency tariff authority — currently N/A for most goods.
- total_duty_rate: Must equal duty_rate + section_301 + section_232 (numeric sum).
- risk_score: Integer 0-100. LOW=0-33, MEDIUM=34-66, HIGH=67-100.

WRITING RULES (CRITICAL):
- compliance_notes: Write in plain English. Be specific. Example: "This product from China is subject to 25% Section 301 List 3 surcharge in addition to the 2.5% MFN base rate, for a total of 27.5%. Ensure HTS 8471.30.0100 matches the exact product specification — misclassification penalties start at $10,000."
- recommended_action: Use one of: APPROVE / REVIEW / HOLD / REJECT. Always explain WHY in compliance_notes.
- sanctions_detail: Be specific. If cleared: "Screened against OFAC SDN, EU Consolidated, and UN Security Council lists — no matches found." If flagged: explain the exact match.
- summary (shipment_summary): Write 2-3 sentences. State total products, highest risks found, and single most important action the importer should take.

CROSS-DOCUMENT CHECKS:
- Flag if product descriptions are vague (e.g., "parts", "components", "goods") — these trigger CBP scrutiny.
- Flag if no country of origin is specified — required on all commercial invoices.
- Flag if values seem unusually low (potential undervaluation fraud).

Return ONLY valid JSON — no markdown, no explanation, no preamble:
{
  "products": [
    {
      "name": "Exact product name from document",
      "hs_code": "XXXX.XX.XXXX",
      "duty_rate": "X.X%",
      "section_301_rate": "25% (List 3 - China)" or "N/A",
      "section_232_rate": "25% (steel)" or "N/A",
      "section_122_rate": "N/A",
      "total_duty_rate": "27.5%",
      "tariff_layers": "2.5% MFN base + 25% Section 301 List 3 = 27.5% total",
      "estimated_duty_usd": "1250.00 (based on declared value $5,000 x 27.5%)" or null,
      "sanctions_status": "CLEARED",
      "sanctions_detail": "Screened against OFAC SDN, EU Consolidated, and UN Security Council lists — no matches found.",
      "risk_level": "MEDIUM",
      "risk_score": 55,
      "compliance_notes": "Specific, plain-English explanation of risks and required actions.",
      "required_documents": ["Commercial Invoice", "Packing List", "Certificate of Origin"],
      "recommended_action": "REVIEW"
    }
  ],
  "shipment_summary": {
    "total_products": 0,
    "high_risk_count": 0,
    "medium_risk_count": 0,
    "low_risk_count": 0,
    "overall_risk_score": 0,
    "overall_recommendation": "APPROVE",
    "summary": "2-3 sentence plain-English summary of the shipment compliance status and top action required.",
    "potential_fine_exposure": "$X,XXX estimated based on Y violations found" or null,
    "cross_document_flags": ["List any inconsistencies found across documents"],
    "top_action_required": "Single most important thing the importer must do right now."
  }
}
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
                r"<lastName[^>]*>([^<]+)</lastName>",
                r"<firstName[^>]*>([^<]+)</firstName>",
                r"<FIRST_NAME>([^<]+)</FIRST_NAME>",
                r"<SECOND_NAME>([^<]+)</SECOND_NAME>",
                r"<THIRD_NAME>([^<]+)</THIRD_NAME>",
                r"<NAME_ORIGINAL_SCRIPT>([^<]+)</NAME_ORIGINAL_SCRIPT>",
                r"<name[^>]*>([^<]+)</name>",
                r"<NAME>([^<]+)</NAME>",
            ]:
                found = re.findall(pattern, text, re.IGNORECASE)
                names.update(n.upper().strip() for n in found if len(n.strip()) > 2)

            # Cache in Firestore
            names_list = list(names)[:10000]  # limit for Firestore doc size
            try:
                cache_ref.set(
                    {
                        "names": names_list,
                        "cached_at": datetime.now(timezone.utc),
                        "count": len(names_list),
                        "source": url,
                    }
                )
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
        "confidence": "HIGH" if any("exact" in h for h in hits) else ("MEDIUM" if hits else "CLEAR"),
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
    """Check if email has a paid subscription. Returns: free / pro / premium / enterprise"""
    if not email:
        return "free"
    try:
        docs = (
            db.collection("subscriptions")
            .where("email", "==", email)
            .where("status", "==", "active")
            .limit(1)
            .get()
        )
        for doc in docs:
            tier = doc.to_dict().get("tier", "free")
            if tier not in ("free", "pro", "premium", "enterprise"):
                return "free"
            return tier
    except Exception:
        pass
    return "free"


def _month_key_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _verify_firebase_user(req: https_fn.Request):
    """Return decoded token dict, or None if missing/invalid."""
    auth_header = req.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    id_token = auth_header.split(" ", 1)[1].strip()
    if not id_token:
        return None
    try:
        return auth.verify_id_token(id_token)
    except Exception as e:
        print(f"Auth verify failed: {e}")
        return None


def _usage_doc_id(uid: str, month_key: str) -> str:
    return f"{uid}_{month_key}"


def get_scan_usage_for_uid(uid: str, month_key: str) -> int:
    doc_id = _usage_doc_id(uid, month_key)
    try:
        doc = db.collection("scan_usage").document(doc_id).get()
        if doc.exists:
            return int(doc.to_dict().get("count", 0) or 0)
    except Exception as e:
        print(f"Usage read error: {e}")
    return 0


def enforce_and_increment_quota(uid: str, tier: str) -> tuple[int, int, int]:
    """
    Atomically check + increment monthly scan usage for uid.
    Returns: (new_count, limit, remaining)
    Raises: ValueError("quota_exceeded")
    """
    month_key = _month_key_now()
    limit = int(TIER_LIMITS.get(tier or "free", TIER_LIMITS["free"]))
    doc_id = _usage_doc_id(uid, month_key)
    ref = db.collection("scan_usage").document(doc_id)

    def txn_fn(txn):
        snap = ref.get(transaction=txn)
        current = int((snap.to_dict() or {}).get("count", 0) or 0) if snap.exists else 0
        if current >= limit:
            raise ValueError("quota_exceeded")
        new_count = current + 1
        txn.set(ref, {"uid": uid, "month": month_key, "count": new_count, "updatedAt": SERVER_TIMESTAMP}, merge=True)
        return new_count

    try:
        new_count = db.transaction()(txn_fn)
    except ValueError:
        raise
    except Exception as e:
        print(f"Quota txn error: {e}")
        # fail-open (do not block scans due to transient firestore issues)
        new_count = 1

    remaining = max(0, limit - int(new_count))
    return int(new_count), limit, remaining


# ══════════════════════════════════════════════════════════════════
# FILE EXTRACTOR
# ══════════════════════════════════════════════════════════════════

def extract_content(file_bytes: bytes, mime_type: str, filename: str):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    # CSV
    if ext == "csv" or mime_type == "text/csv":
        try:
            text = file_bytes.decode("utf-8", errors="replace")
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)
            formatted = "\n".join([", ".join(row) for row in rows[:500]])
            return {"type": "text", "data": f"PRODUCT CSV:\n{formatted}"}, "CSV"
        except Exception:
            return {"type": "text", "data": file_bytes.decode("utf-8", errors="replace")}, "CSV_RAW"

    # Excel
    if ext in ("xlsx", "xls") or "spreadsheet" in mime_type or "excel" in mime_type:
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
    if ext in ("doc", "docx") or "word" in mime_type or "officedocument.wordprocessingml" in mime_type:
        try:
            import docx2txt
            text = docx2txt.process(io.BytesIO(file_bytes))
            return {"type": "text", "data": f"WORD DOCUMENT:\n{text}"}, "DOCX"
        except Exception:
            return {"type": "text", "data": file_bytes.decode("utf-8", errors="replace")}, "DOC_RAW"

    # RTF
    if ext == "rtf" or "rtf" in mime_type:
        try:
            text = file_bytes.decode("utf-8", errors="replace")
            text = re.sub(r"\\[a-z]+\d*\s?", " ", text)
            text = re.sub(r"[{}]", "", text)
            return {"type": "text", "data": f"RTF DOCUMENT:\n{text[:5000]}"}, "RTF"
        except Exception:
            return {"type": "text", "data": ""}, "RTF_ERROR"

    # HTML/HTM
    if ext in ("html", "htm") or "html" in mime_type:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(file_bytes.decode("utf-8", errors="replace"), "html.parser")
            for script in soup(["script", "style", "meta", "link"]):
                script.decompose()
            text = soup.get_text(separator=" ", strip=True)[:5000]
            return {"type": "text", "data": f"HTML DOCUMENT:\n{text}"}, "HTML"
        except Exception:
            return {"type": "text", "data": ""}, "HTML_ERROR"

    # ODS (OpenDocument Spreadsheet)
    if ext == "ods" or "opendocument.spreadsheet" in mime_type:
        try:
            import pandas as pd
            df = pd.read_excel(io.BytesIO(file_bytes), engine="odf", sheet_name=None)
            parts = []
            for sheet_name, sheet_df in df.items():
                parts.append(f"SHEET: {sheet_name}\n{sheet_df.to_string(index=False)}")
            return {"type": "text", "data": "\n\n".join(parts)}, "ODS"
        except Exception as e:
            return {"type": "text", "data": f"ODS error: {e}"}, "ODS_ERROR"

    # GIF - treat as image
    if ext == "gif" or mime_type == "image/gif":
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return {"type": "blob", "data": buf.getvalue(), "mime": "image/png"}, "GIF"
        except Exception:
            return {"type": "blob", "data": file_bytes, "mime": "image/gif"}, "GIF_RAW"

    # WebP
    if ext == "webp" or mime_type == "image/webp":
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(file_bytes))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return {"type": "blob", "data": buf.getvalue(), "mime": "image/png"}, "WEBP"
        except Exception:
            return {"type": "blob", "data": file_bytes, "mime": "image/webp"}, "WEBP_RAW"

    # Images — upscale for better OCR
    if mime_type in ("image/jpeg", "image/png", "image/tiff") or ext in ("jpg", "jpeg", "png", "tiff", "tif"):
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(file_bytes))
            w, h = img.size
            if w < 2000:
                img = img.resize((w * 2, h * 2), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return {"type": "blob", "data": buf.getvalue(), "mime": "image/png"}, "IMAGE"
        except Exception:
            return {"type": "blob", "data": file_bytes, "mime": mime_type}, "IMAGE_RAW"

    # PDF — send natively to Gemini
    if mime_type == "application/pdf" or ext == "pdf":
        return {"type": "blob", "data": file_bytes, "mime": "application/pdf"}, "PDF"

    return {"type": "text", "data": file_bytes.decode("utf-8", errors="replace")}, "TEXT"


# ══════════════════════════════════════════════════════════════════
# PDF REPORT GENERATOR
# ══════════════════════════════════════════════════════════════════

from pdf_report_oldstyle import build_pdf_oldstyle

def safe_parse_json(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1] if len(lines) > 2 else lines)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to extract JSON block
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
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
                "potential_fine_exposure": None,
            },
            "parse_error": True,
        }


# ══════════════════════════════════════════════════════════════════
# HELPER
# ══════════════════════════════════════════════════════════════════

def _json_response(data: dict, status: int) -> https_fn.Response:
    return https_fn.Response(json.dumps(data), status=status, mimetype="application/json")


# ══════════════════════════════════════════════════════════════════
# PAYPAL WEBHOOK (MVP)
# - Secured via X-Webhook-Secret header checked against Secret Manager
# - Upserts Firestore subscription records by PayPal subscription id
# ══════════════════════════════════════════════════════════════════

@https_fn.on_request(
    secrets=["PAYPAL_WEBHOOK_SECRET"],
    cors=options.CorsOptions(cors_origins=["https://www.paypal.com", "https://api.paypal.com"], cors_methods=["POST", "OPTIONS"]),
    region="us-central1",
)
def paypal_webhook(req: https_fn.Request) -> https_fn.Response:
    # PayPal webhooks are server-to-server; CORS is irrelevant, but OPTIONS can still show up.
    if req.method == "OPTIONS":
        return https_fn.Response("", status=204)
    if req.method != "POST":
        return https_fn.Response("Method not allowed", status=405)

    # Simple shared-secret auth (fast MVP).
    expected = os.environ.get("PAYPAL_WEBHOOK_SECRET", "")
    provided = req.headers.get("X-Webhook-Secret", "")
    if not expected or provided != expected:
        return _json_response({"error": "unauthorized"}, 401)

    try:
        payload = req.get_json(silent=True) or {}
    except Exception:
        payload = {}

    event_type = (payload.get("event_type") or "").strip()
    resource = payload.get("resource") or {}

    # Subscription fields vary slightly by event. These are the common ones:
    sub_id = (resource.get("id") or resource.get("subscription_id") or "").strip()
    plan_id = (resource.get("plan_id") or "").strip()
    status = (resource.get("status") or "").strip().lower()

    subscriber = resource.get("subscriber") or {}
    email = (subscriber.get("email_address") or "").strip().lower()

    tier = PAYPAL_PLAN_TO_TIER.get(plan_id, "free")

    # Normalize status
    # PayPal typical statuses: ACTIVE, CANCELLED, SUSPENDED, EXPIRED, APPROVAL_PENDING
    if status in ("active",):
        norm_status = "active"
    elif status in ("cancelled", "canceled", "expired", "suspended"):
        norm_status = "inactive"
    else:
        norm_status = status or "unknown"

    if not sub_id:
        # Still store event for debugging, but cannot key subscription correctly.
        doc_id = f"paypal_event:{uuid.uuid4().hex}"
    else:
        doc_id = f"paypal:{sub_id}"

    try:
        db.collection("subscriptions").document(doc_id).set(
            {
                "provider": "paypal",
                "paypal_subscription_id": sub_id or None,
                "plan_id": plan_id or None,
                "tier": tier,
                "status": norm_status,
                "email": email or None,
                "event_type": event_type or None,
                "raw": payload,
                "updatedAt": SERVER_TIMESTAMP,
            },
            merge=True,
        )
    except Exception as e:
        print(f"PayPal webhook Firestore write error: {e}")
        return _json_response({"error": "firestore_write_failed"}, 500)

    return _json_response({"ok": True}, 200)



# ══════════════════════════════════════════════════════════════════
# MAIN CLOUD FUNCTION: /scan
# ══════════════════════════════════════════════════════════════════

@https_fn.on_request(
    secrets=["GEMINI_API_KEY"],
    cors=options.CorsOptions(cors_origins=ALLOWED_ORIGINS, cors_methods=["POST", "OPTIONS"]),
    memory=options.MemoryOption.GB_2,
    timeout_sec=540,
    region="us-central1",
)
def scan(req: https_fn.Request) -> https_fn.Response:

    if req.method == "OPTIONS":
        return https_fn.Response("", status=204)
    if req.method != "POST":
        return https_fn.Response("Method not allowed", status=405)

    # ── Get request data ─────────────────────────────────────────
    email = req.form.get("email", "").strip().lower()
    company = req.form.get("company", "").strip()
    ip = req.headers.get("X-Forwarded-For", "unknown").split(",")[0].strip()
    job_id = f"TS-{uuid.uuid4().hex[:8].upper()}"


    # ── Firebase Auth (preferred) ──────────────────────────────────
    decoded = _verify_firebase_user(req)
    uid = decoded.get("uid") if decoded else None
    auth_email = (decoded.get("email") or "").strip().lower() if decoded else ""

    # ── Tier detection ───────────────────────────────────────────
    tier = get_user_tier(auth_email or email) if (auth_email or email) else "free"

    # ── Quota enforcement ───────────────────────────────────────
    # If authenticated: enforce by uid for ALL tiers.
    # If not authenticated: fallback to legacy free-tier enforcement by email/ip.
    scans_used = None
    scans_limit = None
    scans_remaining = None

    if uid:
        try:
            scans_used, scans_limit, scans_remaining = enforce_and_increment_quota(uid, tier)
        except ValueError:
            limit = int(TIER_LIMITS.get(tier or "free", TIER_LIMITS["free"]))
            month_key = _month_key_now()
            return _json_response(
                {
                    "error": f"Monthly scan limit reached for {month_key}.",
                    "code": "quota_exceeded",
                    "tier": tier,
                    "scans_used": limit,
                    "scans_limit": limit,
                    "scans_remaining": 0,
                    "upgrade_url": "https://itcloudx.com/pricing",
                },
                429,
            )
    else:
        # Legacy fallback (free only)
        if tier == "free":
            identifier = email if email else ip
            current_count = get_scan_count(identifier)
            if current_count >= FREE_SCAN_LIMIT:
                return _json_response(
                    {
                        "error": f"Free tier limit reached ({FREE_SCAN_LIMIT} scans/month). Upgrade to Pro at itcloudx.com/pricing",
                        "code": "quota_exceeded",
                        "tier": "free",
                        "scans_used": current_count,
                        "scans_limit": FREE_SCAN_LIMIT,
                        "scans_remaining": 0,
                        "upgrade_url": "https://itcloudx.com/pricing",
                    },
                    429,
                )

    # ── Log lead ─────────────────────────────────────────────────
    pdf_url = None  # declared here so always in scope
    pdf_base64 = None
    pdf_error = None
    try:
        db.collection("leads").document(job_id).set(
            {
                "jobId": job_id,
                "email": email,
                "company": company,
                "tier": tier,
                "ip": ip,
                "status": "PROCESSING",
                "timestamp": SERVER_TIMESTAMP,
            }
        )
    except Exception as e:
        print(f"Lead log error: {e}")

    try:
        # ── File validation ───────────────────────────────────────
        file_obj = req.files.get("file")
        if not file_obj:
            return _json_response(
                {"error": "No file uploaded. Please attach a PDF, CSV, Excel, or image."},
                400,
            )

        file_bytes = file_obj.read()
        mime_type = file_obj.content_type or "application/octet-stream"
        filename = file_obj.filename or "document"

        if len(file_bytes) > MAX_FILE_BYTES:
            return _json_response({"error": "File too large. Max 25MB."}, 400)

        MAGIC_BYTES = {
            b"%PDF": "pdf",
            b"PK\x03\x04": "zip_based",
            b"\xd0\xcf\x11\xe0": "ole",
            b"\xff\xd8\xff": "jpg",
            b"\x89PNG": "png",
            b"GIF8": "gif",
            b"II*\x00": "tiff",
            b"MM\x00*": "tiff",
            b"RIFF": "webp",
            b"<html": "html",
            b"<!DOC": "html",
        }
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        detected = None
        for magic, ftype in MAGIC_BYTES.items():
            if file_bytes[: len(magic)] == magic:
                detected = ftype
                break
        if detected == "zip_based" and ext not in ("xlsx", "xls", "docx", "ods", "zip"):
            return _json_response({"error": "Invalid file format detected."}, 400)
        if detected == "ole" and ext not in ("doc", "xls"):
            return _json_response({"error": "Invalid file format detected."}, 400)

        allowed_exts = {
            "pdf",
            "csv",
            "xlsx",
            "xls",
            "doc",
            "docx",
            "rtf",
            "ods",
            "html",
            "htm",
            "jpg",
            "jpeg",
            "png",
            "gif",
            "tiff",
            "tif",
            "webp",
        }
        if ext not in allowed_exts:
            return _json_response(
                {"error": f"File type .{ext} not supported. Use PDF, CSV, Excel, or image."},
                400,
            )

        import time

        # Rate limit: max 10 requests per minute per IP
        ip_key = f"ratelimit:{ip}:{int(time.time() // 60)}"
        try:
            ip_ref = db.collection("rate_limits").document(ip_key)
            ip_doc = ip_ref.get()
            if ip_doc.exists and ip_doc.to_dict().get("count", 0) >= 10:
                return _json_response(
                    {"error": "Too many requests. Please wait a minute before trying again."},
                    429,
                )
            ip_ref.set(
                {
                    "count": (ip_doc.to_dict().get("count", 0) + 1) if ip_doc.exists else 1,
                    "expires": time.time() + 60,
                },
                merge=True,
            )
        except Exception as e:
            print(f"Rate limit check error (non-fatal): {e}")

        # ── Extract content ───────────────────────────────────────
        content, extraction_method = extract_content(file_bytes, mime_type, filename)
        print(f"[{job_id}] Extraction: {extraction_method} | File: {filename} | Tier: {tier}")

        # ── Build Gemini prompt ───────────────────────────────────
        instruction = (
            f"Audit this trade document ({filename}). "
            f"Apply CBP HTS 2026, OFAC SDN, UFLPA, and all applicable sanctions checks. "
            f"Be thorough — missing a sanctions hit can result in $1M+ fines."
        )

        # ── Call Gemini ───────────────────────────────────────────
        from google import genai
        from google.genai import types

        if content["type"] == "text":
            prompt_parts = [instruction + "\n\n" + content["data"]]
        else:
            prompt_parts = [
                types.Part.from_bytes(data=content["data"], mime_type=content["mime"]),
                instruction,
            ]

        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt_parts,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.0,
                response_mime_type="application/json",
                max_output_tokens=65536,
            ),
        )

        try:
            raw_text = response.candidates[0].content.parts[0].text
        except Exception:
            raw_text = response.text

        audit_data = safe_parse_json(raw_text)
        print(f"[{job_id}] RAW GEMINI: {response.text[:500]}")
        products = audit_data.get("products", [])
        shipment = audit_data.get("shipment_summary", {})
        print(f"[{job_id}] Gemini returned {len(products)} products, score={shipment.get('overall_risk_score',0)}")

        # ── USITC HTS Validation (free government API) ────────────────
        try:
            products = enrich_products(products)
            usitc_verified = sum(1 for p in products if p.get("usitc_verified"))
            usitc_flagged  = sum(1 for p in products if not p.get("usitc_verified"))
            print(f"[{job_id}] USITC: {usitc_verified} verified, {usitc_flagged} flagged")
            if usitc_flagged > 0:
                shipment["cross_document_flags"] = shipment.get("cross_document_flags", [])
                shipment["cross_document_flags"].append(
                    f"{usitc_flagged} HTS code(s) could not be verified against USITC HTSUS — manual review required"
                )
        except Exception as ue:
            print(f"[{job_id}] USITC enrichment skipped: {ue}")

        # ── CROSS CBP Rulings lookup (HIGH + MEDIUM risk items) ──
        try:
            for p in products:
                rl = (p.get("risk_level","LOW") or "LOW").upper()
                if rl in ("HIGH", "MEDIUM"):
                    cross = get_cross_summary(
                        p.get("name",""),
                        p.get("hs_code","")
                    )
                    p["cross_status"]  = cross.get("status","")
                    p["cross_rulings"] = cross.get("rulings",[])
                    p["cross_summary"] = cross.get("summary","")
                    p["cross_hts_match"] = cross.get("hts_match", False)
            cross_count = sum(1 for p in products if p.get("cross_rulings"))
            print(f"[{job_id}] CROSS: {cross_count} products with ruling precedents")
        except Exception as ce:
            print(f"[{job_id}] CROSS lookup skipped: {ce}")

        # ── Validate + auto-fix report data ─────────────────────
        try:
            audit_data, val_warnings = validate_and_fix(audit_data)
            products = audit_data.get("products", [])
            shipment = audit_data.get("shipment_summary", {})
            if val_warnings:
                shipment["cross_document_flags"] = shipment.get("cross_document_flags", []) + val_warnings[:3]
        except Exception as ve:
            print(f"[{job_id}] Validator skipped: {ve}")

        # ── Real OFAC sanctions check on consignee/company ───────
        sanctions_check = None
        if company and tier != "free":
            sanctions_check = check_sanctions(company)
            if sanctions_check["hit"]:
                shipment["overall_recommendation"] = "HOLD"
                shipment["summary"] = f"⚠️ SANCTIONS ALERT: {company} may match restricted entity. " + shipment.get("summary", "")

        # ── Generate PDF report (never crash main flow) ───────────
        pdf_base64 = None
        pdf_error = None
        try:
            # Lazy import to keep cold-start fast
            from pdf_report_oldstyle import build_pdf_oldstyle
            pdf_bytes = build_pdf_oldstyle(audit_data, job_id, filename, tier)
            if pdf_bytes:
                import base64
                pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
                print(f"[{job_id}] PDF generated: {len(pdf_bytes)} bytes")
        
                pdf_url = f"data:application/pdf;base64,{pdf_base64}"
                print(f"[{job_id}] PDF generated: {len(pdf_bytes)} bytes — base64 ready")
        except Exception as pdf_err:
            pdf_error = str(pdf_err)
            print(f"[{job_id}] PDF generation/upload skipped: {pdf_error}")
        # ── Legacy counter increment (only when unauthenticated + free tier) ─
        if not uid and tier == "free":
            identifier = email if email else ip
            try:
                new_count = increment_scan_count(identifier)
                scans_used = new_count
                scans_limit = FREE_SCAN_LIMIT
                scans_remaining = max(0, FREE_SCAN_LIMIT - new_count)
            except Exception as cnt_err:
                print(f"[{job_id}] Counter error (non-fatal): {cnt_err}")

        # Ensure scans_* are always present
        if scans_used is None:
            # For paid tiers we can omit remaining if desired, but we want WOW meter:
            # if uid is missing (shouldn't happen for paid users), fall back to unknown.
            scans_used = scans_used or 0
        if scans_limit is None:
            scans_limit = int(TIER_LIMITS.get(tier or "free", TIER_LIMITS["free"])) if uid else (FREE_SCAN_LIMIT if tier == "free" else None)
        if scans_remaining is None:
            scans_remaining = max(0, int(scans_limit) - int(scans_used)) if scans_limit is not None else None

        # ── Save to Firestore (never crash main flow) ───────────── (never crash main flow) ─────────────
        try:
            db.collection("compliance_audits").document(job_id).set(
                {
                    "jobId": job_id,
                    "email": email,
                    "company": company,
                    "tier": tier,
                    "filename": filename,
                    "extraction_method": extraction_method,
                    "status": "COMPLETED",
                    "report_data": audit_data,
                    "sanctions_check": sanctions_check,
                    "timestamp": SERVER_TIMESTAMP,
                }
            )
            leads_update = {
                "status": "COMPLETED",
                "overall_risk_score": shipment.get("overall_risk_score", 0),
                "product_count": len(products),
                "tier": tier,
            }
            if pdf_url:
                leads_update["pdf_url"] = pdf_url
                leads_update["pdf_path"] = f"reports/{job_id}.pdf"
            db.collection("leads").document(job_id).set(leads_update, merge=True)
        except Exception as fs_err:
            print(f"[{job_id}] Firestore save error (non-fatal): {fs_err}")

        # ── Build response ────────────────────────────────────────
        response_data = {
            "jobId": job_id,
            "status": "success",
            "tier": tier,
            "filename": filename,
            "product_count": len(products),
            "overall_risk_score": shipment.get("overall_risk_score", 0),
            "overall_recommendation": shipment.get("overall_recommendation", "REVIEW"),
            "summary": shipment.get("summary", ""),
            "high_risk_count": shipment.get("high_risk_count", 0),
            "products": products if tier != "free" else products[:3],
            "pdf_report": pdf_base64,
            "pdf_url": pdf_url,
            "pdf_error": pdf_error,
            "sanctions_check": sanctions_check,
            "scans_used": scans_used,
            "scans_remaining": scans_remaining,
            "upgrade_url": "https://itcloudx.com/pricing" if tier == "free" else None,
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
            db.collection("compliance_audits").document(job_id).set(
                {"jobId": job_id, "email": email, "status": "FAILED", "error": str(e), "timestamp": SERVER_TIMESTAMP}
            )
            db.collection("leads").document(job_id).set({"status": "FAILED"}, merge=True)
        except Exception:
            pass
        return _json_response({"error": "Scan failed. Please try again or contact support.", "jobId": job_id}, 500)


# ══════════════════════════════════════════════════════════════════
# SANCTIONS CACHE REFRESH — scheduled daily
# ══════════════════════════════════════════════════════════════════

@https_fn.on_request(
    cors=options.CorsOptions(cors_origins=ALLOWED_ORIGINS, cors_methods=["POST"]),
    region="us-central1",
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


# ── Weekly Blog Publisher ─────────────────────────────────────────
# NOTE: Firebase CLI imports this module to analyze functions. Keep heavy deps out of import-time.
# Enable this publisher explicitly when you want it deployed/active.
import os as _os
if _os.environ.get('ENABLE_WEEKLY_PUBLISHER') == '1':
    from weekly_publisher import weekly_publish
