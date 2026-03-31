"""
TradeShield AI — Report Validator v1.0
Prevents inconsistencies before PDF generation
"""

def validate_and_fix(audit_data: dict) -> tuple:
    """
    Validate and auto-fix report data before PDF generation.
    Returns: (fixed_audit_data, list_of_warnings)
    """
    warnings = []
    products = audit_data.get("products", []) or []
    shipment = audit_data.get("shipment_summary", {}) or {}

    # 1. Count actual risk levels from products
    actual_high = sum(1 for p in products if str(p.get("risk_level","")).upper() == "HIGH")
    actual_med  = sum(1 for p in products if str(p.get("risk_level","")).upper() == "MEDIUM")
    actual_low  = sum(1 for p in products if str(p.get("risk_level","")).upper() == "LOW")

    # 2. Fix shipment summary counts to match actual products
    reported_high = int(shipment.get("high_risk_count", 0) or 0)
    if reported_high != actual_high:
        warnings.append(f"high_risk_count mismatch: reported {reported_high}, actual {actual_high} — auto-fixed")
        shipment["high_risk_count"] = actual_high

    reported_med = int(shipment.get("medium_risk_count", 0) or 0)
    if reported_med != actual_med:
        warnings.append(f"medium_risk_count mismatch: reported {reported_med}, actual {actual_med} — auto-fixed")
        shipment["medium_risk_count"] = actual_med

    shipment["low_risk_count"] = actual_low
    shipment["total_products"] = len(products)

    # 3. Validate HTS format — must be 10 digits
    for i, p in enumerate(products):
        hts = str(p.get("hs_code", "") or "")
        clean = hts.replace(".","").replace(" ","")
        if not (clean.isdigit() and len(clean) == 10):
            warnings.append(f"Line {i+1}: Invalid HTS format '{hts}' — flagged for broker review")
            p["hts_confidence"] = "LOW"
            p["usitc_verified"] = False
            if not p.get("compliance_notes"):
                p["compliance_notes"] = f"HTS code '{hts}' does not match 10-digit HTSUS format. Manual classification required."

    # 4. HIGH risk items must have analysis notes
    for i, p in enumerate(products):
        if str(p.get("risk_level","")).upper() == "HIGH" and not p.get("compliance_notes"):
            warnings.append(f"Line {i+1}: HIGH risk item missing analysis — added placeholder")
            p["compliance_notes"] = "HIGH risk flag set. Classification or sanctions issue requires broker review before import."

    # 5. Ensure overall_risk_score is consistent with risk distribution
    score = int(shipment.get("overall_risk_score", 0) or 0)
    if actual_high > 0 and score < 50:
        warnings.append(f"Risk score {score} too low for {actual_high} HIGH risk items — adjusted to minimum 55")
        shipment["overall_risk_score"] = max(score, 55)
    if actual_high == 0 and actual_med == 0 and score > 33:
        warnings.append(f"Risk score {score} too high for all-LOW shipment — adjusted")
        shipment["overall_risk_score"] = min(score, 33)

    # 6. Validate overall_recommendation aligns with risk
    rec = (shipment.get("overall_recommendation","REVIEW") or "REVIEW").upper()
    if actual_high > 0 and rec == "APPROVE":
        warnings.append(f"APPROVE recommendation with {actual_high} HIGH risk items — changed to REVIEW")
        shipment["overall_recommendation"] = "REVIEW"

    # 7. Format USD values with commas
    for p in products:
        est = p.get("estimated_duty_usd")
        if est:
            try:
                clean_val = str(est).replace("$","").replace(",","").split("(")[0].strip()
                numeric = float(clean_val)
                context = str(est)[str(est).find("("):] if "(" in str(est) else ""
                p["estimated_duty_usd"] = f"{numeric:,.2f}{context}"
            except:
                pass

    audit_data["shipment_summary"] = shipment
    audit_data["products"] = products

    if warnings:
        print(f"[Validator] {len(warnings)} issues auto-fixed:")
        for w in warnings:
            print(f"  - {w}")
    else:
        print("[Validator] Report passed all checks")

    return audit_data, warnings
