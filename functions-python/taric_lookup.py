"""
TradeShield AI — EU TARIC Tariff Lookup
Source: EU TARIC official rates (static table based on official TARIC data)
Live API: Apitalks api.store (requires registration - add when available)
Fallback: Gemini-enriched EU rate knowledge
"""
import requests, re

# ── Static EU TARIC MFN rates (most common HS chapters) ──────────
# Based on official EU TARIC schedule - updated periodically
# Format: {hs_prefix: (mfn_rate, description_hint)}
EU_MFN_RATES = {
    # Chapter 39 - Plastics
    "3926": ("6.5%", "Articles of plastics"),
    "3920": ("6.5%", "Plastic plates, sheets, film"),
    "3921": ("6.5%", "Cellular plastic articles"),
    "3824": ("6.5%", "Chemical preparations"),
    "3902": ("3.0%", "Polymers of propylene"),
    "3917": ("6.5%", "Tubes, pipes, hoses of plastics"),
    # Chapter 40 - Rubber
    "4016": ("3.7%", "Articles of vulcanised rubber"),
    # Chapter 68/69 - Stone, ceramics
    "6812": ("0.0%", "Fabricated asbestos fibres"),
    "6815": ("0.0%", "Articles of stone"),
    # Chapter 73 - Steel
    "7216": ("0.0%", "Iron or steel angles, shapes"),  # + AD duties possible
    "7210": ("0.0%", "Flat-rolled steel products"),
    "7304": ("0.0%", "Steel tubes and pipes"),
    "7312": ("0.0%", "Stranded wire, ropes, cables of steel"),
    "7318": ("3.7%", "Screws, bolts, nuts of iron/steel"),
    # Chapter 74 - Copper
    "7407": ("0.0%", "Copper bars, rods and profiles"),
    # Chapter 76 - Aluminium
    "7604": ("3.0%", "Aluminium bars and profiles"),
    "7616": ("3.0%", "Other articles of aluminium"),
    # Chapter 82/83 - Tools
    "8302": ("3.0%", "Mountings, fittings of base metal"),
    # Chapter 84 - Machinery
    "8412": ("1.7%", "Hydraulic/pneumatic power engines"),
    "8413": ("2.2%", "Pumps for liquids"),
    "8414": ("1.7%", "Air pumps and fans"),
    "8481": ("1.7%", "Taps, cocks, valves"),
    "8483": ("1.7%", "Transmission shafts, gearboxes"),
    "8501": ("2.7%", "Electric motors and generators"),
    "8504": ("0.0%", "Electrical transformers, static converters"),
    "8507": ("0.0%", "Electric accumulators/batteries"),
    "8511": ("3.7%", "Electrical ignition/starting equipment"),
    "8517": ("0.0%", "Telephone/telecom apparatus"),
    "8528": ("0.0%", "Monitors, projectors, TV receivers"),
    "8534": ("0.0%", "Printed circuits"),
    "8536": ("2.7%", "Electrical apparatus for switching"),
    "8537": ("1.5%", "Boards, panels for electric control"),
    "8541": ("0.0%", "Semiconductor devices"),
    "8542": ("0.0%", "Electronic integrated circuits"),
    "8543": ("2.7%", "Electrical machines not elsewhere specified"),
    "8544": ("2.7%", "Insulated wire, cable, optical fibre"),
    # Chapter 90 - Instruments
    "9014": ("3.7%", "Direction finding compasses; instruments"),
    "9025": ("2.0%", "Thermometers, hydrometers"),
    "9026": ("2.0%", "Instruments for measuring flow/pressure"),
    "9030": ("0.0%", "Oscilloscopes, measuring instruments"),
}

# EU Anti-Dumping duties on Chinese goods (common ones)
EU_ANTIDUMPING_CN = {
    "7216": ("25.0%", "Steel structural profiles - ADD Reg. 2019/1676"),
    "7210": ("25.0%", "Flat steel products - ADD measures active"),
    "7304": ("51.5%", "Steel seamless pipes - ADD Reg. 2018/1508"),
    "7312": ("17.2%", "Steel wire ropes from China - ADD Reg. 2019/1382"),
    "8501": ("0.0%", "Check specific motor subheadings for ADD"),
    "3917": ("0.0%", "Check TARIC for plastic tubes from CN"),
}

# CBAM sectors (Carbon Border Adjustment Mechanism - mandatory from 2026)
CBAM_SECTORS = {
    "7216", "7210", "7304", "7312", "7318",  # Steel
    "7604", "7616", "7407",                    # Aluminium, Copper
    "2507", "2523",                            # Cement
    "3102", "3105",                            # Fertilisers
}


def lookup_eu_taric(cn_code: str, origin_country: str = "CN") -> dict:
    """
    Look up EU TARIC data for a CN code.
    Returns MFN rate, ADD duties, CBAM status, and source.
    """
    if not cn_code:
        return {"error": "No CN code provided"}

    # Normalize CN code
    clean = cn_code.replace(".", "").replace(" ", "")
    prefix4 = clean[:4]
    prefix6 = clean[:6]
    prefix8 = clean[:8]

    # MFN duty rate
    mfn_rate = None
    mfn_desc = ""
    for prefix in [prefix8, prefix6, prefix4]:
        if prefix in EU_MFN_RATES:
            mfn_rate, mfn_desc = EU_MFN_RATES[prefix]
            break

    # Anti-dumping (China-specific)
    add_rate = None
    add_desc = ""
    if origin_country.upper() in ("CN", "CHN", "CHINA"):
        for prefix in [prefix8, prefix6, prefix4]:
            if prefix in EU_ANTIDUMPING_CN:
                add_rate, add_desc = EU_ANTIDUMPING_CN[prefix]
                break

    # CBAM check
    cbam = prefix4 in CBAM_SECTORS or prefix6[:4] in CBAM_SECTORS

    # VAT note (standard EU import VAT)
    vat_note = "Import VAT applies in destination member state (typically 19-25%)"

    # Calculate total if possible
    total_note = ""
    if mfn_rate and add_rate and add_rate != "0.0%":
        try:
            mfn_num = float(mfn_rate.replace("%",""))
            add_num = float(add_rate.replace("%",""))
            total_note = f"{mfn_num + add_num:.1f}% (MFN + ADD)"
        except:
            pass

    result = {
        "cn_code":      cn_code,
        "cn_clean":     prefix8 if len(clean) >= 8 else clean,
        "mfn_rate":     mfn_rate or "Check TARIC",
        "mfn_desc":     mfn_desc,
        "add_duty":     add_rate,
        "add_desc":     add_desc if add_rate and add_rate != "0.0%" else None,
        "cbam_required": cbam,
        "total_rate":   total_note or mfn_rate or "Check TARIC",
        "vat_note":     vat_note,
        "source":       "EU TARIC schedule (static reference) — verify at taric.europa.eu",
        "taric_url":    f"https://ec.europa.eu/taxation_customs/dds2/taric/measures.jsp?Lang=en&Area={origin_country}&search_text={prefix8}&Action=search",
    }

    return result


def get_taric_summary(cn_code: str, product_name: str = "", origin: str = "CN") -> dict:
    """
    Get full EU TARIC summary for a product.
    Used in EU scan reports.
    """
    data = lookup_eu_taric(cn_code, origin)

    issues = []
    if data.get("add_duty") and data["add_duty"] != "0.0%":
        issues.append(f"Anti-Dumping duty {data['add_duty']} applies — {data.get('add_desc','')}")
    if data.get("cbam_required"):
        issues.append("CBAM declaration required — embedded carbon reporting mandatory from 2026")
    if data.get("mfn_rate") == "Check TARIC":
        issues.append("MFN rate not in static table — verify at taric.europa.eu for exact rate")

    data["issues"] = issues
    data["product_name"] = product_name
    data["origin"] = origin

    return data
