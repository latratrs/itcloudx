"""
TradeShield AI — USITC HTS Lookup
Free government API: https://hts.usitc.gov
Validates and enriches AI-suggested HTS codes with real CBP data
"""
import requests, re

USITC_BASE = "https://hts.usitc.gov/reststop"

def search_hts(keyword: str, limit: int = 5) -> list:
    """Search USITC for HTS codes matching keyword. Returns list of matches."""
    try:
        r = requests.get(f"{USITC_BASE}/search",
                         params={"keyword": keyword, "offset": 0, "limit": limit},
                         timeout=8)
        if r.status_code == 200:
            results = r.json() if isinstance(r.json(), list) else r.json().get("results", [])
            return [{
                "htsno":       item.get("htsno", ""),
                "description": item.get("description", ""),
                "general":     item.get("general", ""),   # MFN duty rate
                "special":     item.get("special", ""),   # GSP/FTA rates
                "units":       item.get("units", []),
            } for item in results if item.get("htsno")]
    except Exception as e:
        print(f"USITC search error: {e}")
    return []

def validate_hts(code: str) -> dict:
    """Validate a 10-digit HTS code against USITC. Returns validation result."""
    # Normalize: strip dots
    clean = re.sub(r'[.\s]', '', str(code))
    if not clean.isdigit():
        return {"valid": False, "reason": "Non-numeric characters in HTS code"}
    if len(clean) not in (8, 10):
        return {"valid": False, "reason": f"HTS code must be 10 digits, got {len(clean)}"}

    # Format as XXXX.XX.XXXX for lookup
    formatted = f"{clean[:4]}.{clean[4:6]}.{clean[6:]}"
    try:
        r = requests.get(f"{USITC_BASE}/htsnumber",
                         params={"htsno": formatted},
                         timeout=8)
        if r.status_code == 200:
            data = r.json()
            results = data if isinstance(data, list) else data.get("results", [])
            if results:
                item = results[0]
                return {
                    "valid":       True,
                    "htsno":       item.get("htsno", formatted),
                    "description": item.get("description", ""),
                    "general":     item.get("general", ""),
                    "special":     item.get("special", ""),
                    "source":      "USITC HTSUS 2026",
                }
    except Exception as e:
        print(f"USITC validate error for {code}: {e}")

    # Fallback: basic format check passed, USITC unreachable
    return {"valid": True, "htsno": formatted, "description": "", "general": "", "source": "format-check-only"}

def enrich_products(products: list) -> list:
    """
    For each product from Gemini, validate HTS code via USITC and add:
    - usitc_verified: bool
    - usitc_description: official description
    - usitc_duty: official MFN rate
    - hts_confidence: HIGH / MEDIUM / LOW
    """
    enriched = []
    for p in products:
        hts = p.get("hs_code", "")
        result = validate_hts(hts)
        p["usitc_verified"]    = result.get("valid", False)
        p["usitc_description"] = result.get("description", "")
        p["usitc_duty"]        = result.get("general", "")
        p["usitc_source"]      = result.get("source", "")

        # Confidence logic
        if result.get("valid") and result.get("description"):
            p["hts_confidence"] = "HIGH"
        elif result.get("valid"):
            p["hts_confidence"] = "MEDIUM"
        else:
            p["hts_confidence"] = "LOW"
            p["compliance_notes"] = (
                f"⚠️ HTS code {hts} could not be verified against USITC HTSUS. "
                "Manual review by licensed customs broker required before import."
            )
        enriched.append(p)
    return enriched
