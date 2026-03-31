"""
TradeShield AI — CBP CROSS Rulings Lookup
Free government API: https://rulings.cbp.gov/api/search
220,303+ CBP rulings — real precedent for HTS classification
"""
import requests, re

CROSS_BASE = "https://rulings.cbp.gov/api"

def search_cross(keyword: str, hts_code: str = "", limit: int = 3) -> list:
    """
    Search CBP CROSS for rulings related to a product keyword + HTS code.
    Returns list of relevant rulings with number, subject, HTS, date, URL.
    """
    results = []

    # Strategy 1: Search by keyword
    try:
        params = {"term": keyword[:60], "pageSize": limit, "sortOrder": "RULING_DATE_DESC"}
        r = requests.get(f"{CROSS_BASE}/search", params=params, timeout=8)
        if r.status_code == 200:
            data = r.json()
            rulings = data.get("rulings", [])
            for ruling in rulings[:limit]:
                results.append(_format_ruling(ruling))
    except Exception as e:
        print(f"CROSS keyword search error: {e}")

    # Strategy 2: If HTS provided, also search by HTS code
    if hts_code and len(results) < limit:
        try:
            hts_clean = hts_code.replace(".", "")[:8]  # use 8-digit for broader match
            params2 = {"term": hts_clean, "pageSize": 2, "sortOrder": "RULING_DATE_DESC"}
            r2 = requests.get(f"{CROSS_BASE}/search", params=params2, timeout=8)
            if r2.status_code == 200:
                data2 = r2.json()
                for ruling in data2.get("rulings", [])[:2]:
                    formatted = _format_ruling(ruling)
                    # Avoid duplicates
                    if formatted["number"] not in [x["number"] for x in results]:
                        results.append(formatted)
        except Exception as e:
            print(f"CROSS HTS search error: {e}")

    return results[:limit]


def _format_ruling(ruling: dict) -> dict:
    """Format a CROSS ruling into clean dict."""
    ruling_num = ruling.get("rulingNumber", "")
    collection  = ruling.get("collection", "ny").upper()
    tariffs     = ruling.get("tariffs", [])
    date_str    = ruling.get("rulingDate", "")[:10]

    return {
        "number":    ruling_num,
        "subject":   ruling.get("subject", "")[:120],
        "hts_codes": tariffs[:3],
        "date":      date_str,
        "collection": collection,  # NY or HQ
        "url":       f"https://rulings.cbp.gov/ruling/{ruling_num}",
        "revoked":   ruling.get("operationallyRevoked", False),
    }


def get_cross_summary(product_name: str, hts_code: str) -> dict:
    """
    Get CROSS ruling summary for a product.
    Returns: match status, ruling refs, and whether HTS aligns with rulings.
    """
    # Simple keyword: take first 3 words of product name (most descriptive)
    words = product_name.split()[:3]
    keyword = ' '.join(words)[:50]

    rulings = search_cross(keyword, hts_code, limit=3)

    # Fallback: search by HTS code directly if keyword search failed
    if not rulings and hts_code:
        try:
            hts_clean = hts_code.replace(".", "")[:8]
            r3 = requests.get(f"{CROSS_BASE}/search",
                              params={"term": hts_clean, "pageSize": 3, "sortOrder": "RULING_DATE_DESC"},
                              timeout=8)
            if r3.status_code == 200:
                for ruling in r3.json().get("rulings", [])[:3]:
                    rulings.append(_format_ruling(ruling))
        except Exception as e:
            print(f"CROSS HTS fallback error: {e}")

    # Fallback 2: try first 2 words only
    if not rulings:
        try:
            short_kw = " ".join(product_name.split()[:2])
            r4 = requests.get(f"{CROSS_BASE}/search",
                              params={"term": short_kw, "pageSize": 3, "sortOrder": "RULING_DATE_DESC"},
                              timeout=8)
            if r4.status_code == 200:
                for ruling in r4.json().get("rulings", [])[:3]:
                    rulings.append(_format_ruling(ruling))
        except Exception as e:
            print(f"CROSS fallback2 error: {e}")

    if not rulings:
        return {
            "status": "NO_RESULTS",
            "rulings": [],
            "hts_match": False,
            "summary": f"No CROSS rulings found for this product. Manual broker research recommended."
        }

    # Check if any ruling HTS matches declared HTS
    declared_clean = hts_code.replace(".", "")[:8]
    hts_match = any(
        declared_clean in r_hts.replace(".", "")
        for ruling in rulings
        for r_hts in ruling.get("hts_codes", [])
    )

    # Filter out revoked rulings
    active = [r for r in rulings if not r.get("revoked")]
    revoked = [r for r in rulings if r.get("revoked")]

    status = "MATCH" if hts_match else ("PARTIAL" if active else "NO_MATCH")

    return {
        "status":    status,
        "rulings":   active[:3],
        "revoked":   revoked,
        "hts_match": hts_match,
        "summary":   f"{len(active)} active CBP ruling(s) found. "
                     f"{'HTS code appears in ruling precedents.' if hts_match else 'HTS code not directly cited in found rulings — broker verification recommended.'}"
    }
