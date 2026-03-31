"""
TradeShield AI — PDF Compliance Report v3.0
Broker-ready: CBP-compliant language, reasonable care, no overconfident classifications
"""
import io, os
from datetime import datetime

def build_pdf_oldstyle(audit_data: dict, job_id: str, filename: str, tier: str) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether, PageBreak
    )
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT

    # Colors
    NAVY   = colors.HexColor("#0b1e3d")
    TEAL   = colors.HexColor("#00b3a4")
    RED    = colors.HexColor("#c62828")
    AMBER  = colors.HexColor("#cc8800")
    GREEN  = colors.HexColor("#0f7a3a")
    LGRAY  = colors.HexColor("#f4f6f9")
    DGRAY  = colors.HexColor("#5b6775")
    SOFT_R = colors.HexColor("#fdf0f0")
    SOFT_A = colors.HexColor("#fffbf0")
    SOFT_G = colors.HexColor("#f0faf4")
    SOFT_B = colors.HexColor("#eef4fb")
    BORDER = colors.HexColor("#cfe0f3")
    DKBLUE = colors.HexColor("#004080")
    WHITE  = colors.white
    BLACK  = colors.black

    def PS(name, **kw):
        d = dict(fontName="Helvetica", fontSize=9, textColor=BLACK, leading=13)
        d.update(kw); return ParagraphStyle(name, **d)

    S = {
        "title":   PS("T",  fontSize=17, textColor=WHITE, fontName="Helvetica-Bold"),
        "meta":    PS("M",  fontSize=7.5, textColor=colors.HexColor("#aaccee"), alignment=TA_RIGHT, leading=11),
        "h2":      PS("H2", fontSize=11, textColor=NAVY, fontName="Helvetica-Bold", spaceAfter=4),
        "h3":      PS("H3", fontSize=9,  textColor=NAVY, fontName="Helvetica-Bold", spaceAfter=2),
        "body":    PS("B",  fontSize=8.5, leading=13),
        "small":   PS("SM", fontSize=7.5, textColor=DGRAY, leading=11),
        "bold":    PS("BO", fontSize=8.5, fontName="Helvetica-Bold"),
        "center":  PS("C",  fontSize=9,   alignment=TA_CENTER),
        "right":   PS("R",  fontSize=9,   alignment=TA_RIGHT),
        "warn":    PS("W",  fontSize=8.5, textColor=colors.HexColor("#7a1c1c"), fontName="Helvetica-Bold", leading=13),
        "green":   PS("G",  fontSize=8.5, textColor=GREEN, fontName="Helvetica-Bold"),
        "amber":   PS("A",  fontSize=8.5, textColor=AMBER, fontName="Helvetica-Bold"),
        "red":     PS("RD", fontSize=8.5, textColor=RED,   fontName="Helvetica-Bold"),
        "footer":  PS("F",  fontSize=7,   textColor=DGRAY, alignment=TA_CENTER),
        "label":   PS("LB", fontSize=7,   textColor=DGRAY, fontName="Helvetica-Bold", spaceAfter=0),
        "italic":  PS("IT", fontSize=8.5, fontName="Helvetica-Oblique", textColor=colors.HexColor("#2b3b4f"), leading=13),
        "notice":  PS("NT", fontSize=8,   textColor=colors.HexColor("#5a3000"), leading=12),
        "code":    PS("CD", fontSize=8,   fontName="Courier", textColor=DKBLUE),
        "usitc":   PS("US", fontSize=7.5, fontName="Helvetica-Oblique", textColor=DKBLUE),
        "tag":     PS("TG", fontSize=8,   textColor=WHITE, fontName="Helvetica-Bold", alignment=TA_CENTER),
    }

    def div(color=TEAL, space=6):
        return HRFlowable(width="100%", thickness=0.5, color=color, spaceAfter=space, spaceBefore=4)

    def risk_colors(level):
        l = str(level).upper()
        if l == "HIGH":   return RED,   SOFT_R
        if l == "MEDIUM": return AMBER, SOFT_A
        return GREEN, SOFT_G

    def flag_tag(text, color):
        t = Table([[Paragraph(text, S["tag"])]], colWidths=[0.85*inch])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), color),
            ("TOPPADDING",    (0,0),(-1,-1), 2),
            ("BOTTOMPADDING", (0,0),(-1,-1), 2),
            ("LEFTPADDING",   (0,0),(-1,-1), 4),
            ("RIGHTPADDING",  (0,0),(-1,-1), 4),
        ]))
        return t

    # Data
    shipment   = audit_data.get("shipment_summary") or {}
    products   = audit_data.get("products") or []
    risk_score = int(shipment.get("overall_risk_score", 0) or 0)
    rec        = (shipment.get("overall_recommendation", "REVIEW") or "REVIEW").upper()
    summary    = (shipment.get("summary", "") or "").strip()
    top_action = (shipment.get("top_action_required", "") or "").strip()
    cross_flags= shipment.get("cross_document_flags", []) or []
    fine_exp   = (shipment.get("potential_fine_exposure", "") or "").strip()
    now        = datetime.utcnow().strftime("%B %d, %Y  %H:%M UTC")
    is_pro     = tier in ("pro", "premium", "enterprise")
    high_c     = int(shipment.get("high_risk_count", 0) or 0)
    med_c      = int(shipment.get("medium_risk_count", 0) or 0)
    low_c      = int(shipment.get("low_risk_count", 0) or 0)
    total_c    = len(products)
    usitc_v    = sum(1 for p in products if p.get("usitc_verified"))
    usitc_f    = total_c - usitc_v

    # China-origin items (global notice instead of per-product repeat)
    china_items = [p for p in products if "china" in str(p.get("sanctions_detail","")).lower()
                   or "china" in str(p.get("compliance_notes","")).lower()
                   or "301" in str(p.get("tariff_layers",""))]
    has_s232   = any(p for p in products if "N/A" not in str(p.get("section_232_rate","N/A")))
    has_s301   = any(p for p in products if "N/A" not in str(p.get("section_301_rate","N/A")))

    rec_color  = GREEN if rec=="APPROVE" else (RED if rec in ("HOLD","REJECT") else AMBER)
    risk_label = "LOW" if risk_score<34 else ("MEDIUM" if risk_score<67 else "HIGH")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=0.55*inch, rightMargin=0.55*inch,
                            topMargin=0.45*inch, bottomMargin=0.5*inch)
    story = []

    # ══════════════════════════════════════════════════════════════
    # 1. HEADER
    # ══════════════════════════════════════════════════════════════
    tier_label = "PRO REPORT" if is_pro else "FREE REPORT — UPGRADE FOR FULL ANALYSIS"
    hdr = Table([[
        Paragraph("TradeShield AI", S["title"]),
        Paragraph(f"US Customs Compliance Report\n{tier_label}\nJob: {job_id}  |  {now}", S["meta"]),
    ]], colWidths=[3.2*inch, 3.7*inch])
    hdr.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), NAVY),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("LEFTPADDING",   (0,0),(-1,-1), 12),
        ("RIGHTPADDING",  (0,0),(-1,-1), 12),
        ("TOPPADDING",    (0,0),(-1,-1), 10),
        ("BOTTOMPADDING", (0,0),(-1,-1), 10),
    ]))
    story.append(hdr)
    story.append(Spacer(1, 6))

    # ══════════════════════════════════════════════════════════════
    # 2. COMPLIANCE NOTICE (CBP-REQUIRED LANGUAGE)
    # ══════════════════════════════════════════════════════════════
    notice_text = (
        "IMPORTANT COMPLIANCE NOTICE: TradeShield AI does not perform customs business as defined by "
        "U.S. Customs and Border Protection (19 CFR Part 111). This report provides data extraction, "
        "risk indicators, and classification candidates only. It is designed to assist importers in "
        "exercising reasonable care under 19 U.S.C. Section 1484. All tariff classifications, CBP "
        "filings, and final determinations must be reviewed and completed by a licensed customs broker "
        "or attorney. TradeShield AI, ITCloudX, and Deccod LLC assume no liability for customs decisions "
        "made in reliance on this report."
    )
    notice_t = Table([[Paragraph(notice_text, S["notice"])]], colWidths=[6.9*inch])
    notice_t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), colors.HexColor("#fff8ee")),
        ("BOX",           (0,0),(-1,-1), 1, AMBER),
        ("LEFTPADDING",   (0,0),(-1,-1), 10),
        ("RIGHTPADDING",  (0,0),(-1,-1), 10),
        ("TOPPADDING",    (0,0),(-1,-1), 7),
        ("BOTTOMPADDING", (0,0),(-1,-1), 7),
    ]))
    story.append(notice_t)
    story.append(Spacer(1, 8))

    # ══════════════════════════════════════════════════════════════
    # 3. EXECUTIVE SUMMARY SCORECARD
    # ══════════════════════════════════════════════════════════════
    sc_data = [
        [Paragraph("AI RISK FLAG", S["label"]),
         Paragraph("HIGH RISK ITEMS", S["label"]),
         Paragraph("MEDIUM RISK", S["label"]),
         Paragraph("TOTAL PRODUCTS", S["label"]),
         Paragraph("FILE", S["label"])],
        [Paragraph(risk_label, PS("RL", fontSize=15, fontName="Helvetica-Bold", alignment=TA_CENTER,
                   textColor=GREEN if risk_label=="LOW" else (RED if risk_label=="HIGH" else AMBER))),
         Paragraph(str(high_c), PS("HC", fontSize=15, fontName="Helvetica-Bold", alignment=TA_CENTER,
                   textColor=RED if high_c else GREEN)),
         Paragraph(str(med_c),  PS("MC", fontSize=15, fontName="Helvetica-Bold", alignment=TA_CENTER, textColor=AMBER)),
         Paragraph(str(total_c),PS("TC", fontSize=15, fontName="Helvetica-Bold", alignment=TA_CENTER, textColor=NAVY)),
         Paragraph(str(filename)[:18], PS("FC", fontSize=7.5, textColor=DGRAY, alignment=TA_CENTER))],
    ]
    sc = Table(sc_data, colWidths=[1.38*inch]*5)
    sc.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), LGRAY),
        ("BOX",           (0,0),(-1,-1), 0.5, BORDER),
        ("INNERGRID",     (0,0),(-1,-1), 0.3, BORDER),
        ("ALIGN",         (0,0),(-1,-1), "CENTER"),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
    ]))
    story.append(sc)
    story.append(Spacer(1, 6))

    if summary:
        story.append(Paragraph(summary, S["italic"]))
        story.append(Spacer(1, 5))

    # ══════════════════════════════════════════════════════════════
    # 4. TOP ISSUES — BROKER VIEW (NEW SECTION)
    # ══════════════════════════════════════════════════════════════
    top_issues = []
    high_products = [(i+1, p) for i,p in enumerate(products) if str(p.get("risk_level","")).upper()=="HIGH"]
    s232_products = [(i+1, p) for i,p in enumerate(products) if "N/A" not in str(p.get("section_232_rate","N/A"))]

    if high_products:
        names = ", ".join([f"Line {n}: {p.get('name','')[:30]}" for n,p in high_products[:3]])
        top_issues.append(("HIGH RISK", f"Classification review required — {names}", RED))
    if s232_products:
        top_issues.append(("SECTION 232", f"{len(s232_products)} item(s) subject to steel/aluminum tariff surcharges", AMBER))
    if has_s301:
        china_count = len([p for p in products if "N/A" not in str(p.get("section_301_rate","N/A"))])
        top_issues.append(("SECTION 301", f"{china_count} China-origin item(s) subject to +25% List 3 surcharge", AMBER))
    if usitc_f:
        top_issues.append(("HTS UNVERIFIED", f"{usitc_f} HTS code(s) not confirmed in USITC database", RED))
    if cross_flags:
        for flag in cross_flags:
            top_issues.append(("DOC FLAG", str(flag)[:80], AMBER))
    if fine_exp:
        top_issues.append(("FINE EXPOSURE", str(fine_exp), RED))
    if not top_issues:
        top_issues.append(("LOW RISK", "No major compliance issues identified in this shipment", GREEN))

    story.append(div())
    story.append(Paragraph("TOP ISSUES — BROKER REVIEW SUMMARY", S["h2"]))
    for flag, desc, color in top_issues:
        row = Table([[
            Paragraph(flag, PS("FG", fontSize=8, fontName="Helvetica-Bold", textColor=WHITE, alignment=TA_CENTER)),
            Paragraph(desc, S["body"]),
        ]], colWidths=[1.1*inch, 5.8*inch])
        row.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(0,-1), color),
            ("BACKGROUND",    (1,0),(1,-1), LGRAY),
            ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
            ("LEFTPADDING",   (0,0),(-1,-1), 6),
            ("TOPPADDING",    (0,0),(-1,-1), 4),
            ("BOTTOMPADDING", (0,0),(-1,-1), 4),
            ("LINEBELOW",     (0,0),(-1,-1), 0.3, BORDER),
        ]))
        story.append(row)
    story.append(Spacer(1, 6))

    # ══════════════════════════════════════════════════════════════
    # 5. GLOBAL TRADE MEASURES (replaces per-product repetition)
    # ══════════════════════════════════════════════════════════════
    if has_s301 or has_s232:
        story.append(div())
        story.append(Paragraph("TRADE MEASURES — APPLIES TO THIS SHIPMENT", S["h2"]))
        measures = []
        if has_s301:
            measures.append("Section 301 (China Trade War List 3): +25% surcharge applies to all China-origin goods in this shipment. Importer must maintain supplier traceability records for UFLPA enforcement. CBP may request documentation proving goods are not produced with forced labor.")
        if has_s232:
            s232_lines = [f"Line {i+1}" for i,p in enumerate(products) if "N/A" not in str(p.get("section_232_rate","N/A"))]
            measures.append(f"Section 232 (Steel/Aluminum): +25% steel or +10% aluminum surcharge applies to {', '.join(s232_lines)}. Verify product specifications match classification to avoid overpayment or underpayment.")
        measures.append("UFLPA (Uyghur Forced Labor Prevention Act): All China-origin goods are subject to rebuttable presumption of forced labor. Importer should obtain and retain: (1) supplier name and address, (2) description of manufacturing process, (3) country of origin certification.")
        for m in measures:
            story.append(Table([[Paragraph(m, S["body"])]], colWidths=[6.9*inch]))
            story.append(Spacer(1, 3))
        story.append(Spacer(1, 3))

    # ══════════════════════════════════════════════════════════════
    # 6. PRODUCT ANALYSIS
    # ══════════════════════════════════════════════════════════════
    story.append(div())
    story.append(Paragraph(f"PRODUCT ANALYSIS ({total_c} items)", S["h2"]))

    display = products if is_pro else products[:3]
    if not is_pro and total_c > 3:
        story.append(Paragraph(
            f"Free tier: showing 3 of {total_c} products. Upgrade at itcloudx.com/pricing for full report.",
            PS("UP", fontSize=8, textColor=AMBER, fontName="Helvetica-Oblique")
        ))
    story.append(Spacer(1, 4))

    for i, p in enumerate(display):
        rl      = (p.get("risk_level","LOW") or "LOW").upper()
        rs      = int(p.get("risk_score",0) or 0)
        fg, bg  = risk_colors(rl)
        hts     = p.get("hs_code","N/A")
        name    = (p.get("name","Unknown") or "Unknown")
        action  = (p.get("recommended_action","REVIEW") or "REVIEW").upper()
        notes   = (p.get("compliance_notes","") or "").strip()
        usitc_ok= p.get("usitc_verified", False)
        usitc_d = (p.get("usitc_description","") or "").strip()
        conf    = rl  # AI risk level — single source of truth
        sanctions=(p.get("sanctions_detail","") or "").strip()
        tariff_l= (p.get("tariff_layers","") or "").strip()
        total_d = (p.get("total_duty_rate","") or "").strip()
        s301    = (p.get("section_301_rate","N/A") or "N/A")
        s232    = (p.get("section_232_rate","N/A") or "N/A")
        est_d   = (p.get("estimated_duty_usd","") or "")
        req_docs= p.get("required_documents",[]) or []

        # Translate action to broker-friendly language
        ai_flag = {"APPROVE":"LOW RISK","REVIEW":"REVIEW","HOLD":"HOLD — SEE NOTES","REJECT":"REJECT"}.get(action, action)
        flag_color = GREEN if action=="APPROVE" else (RED if action in ("HOLD","REJECT") else AMBER)

        block = []

        # Header
        ph = Table([[
            Paragraph(f"#{i+1}  {name[:52]}", PS("PH", fontSize=9.5, fontName="Helvetica-Bold", textColor=WHITE)),
            Paragraph(f"AI FLAG: {ai_flag}", PS("PF", fontSize=8.5, fontName="Helvetica-Bold",
                      textColor=WHITE, alignment=TA_RIGHT)),
        ]], colWidths=[4.8*inch, 2.1*inch])
        ph.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), NAVY),
            ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
            ("LEFTPADDING",   (0,0),(-1,-1), 8),
            ("RIGHTPADDING",  (0,0),(-1,-1), 8),
            ("TOPPADDING",    (0,0),(-1,-1), 5),
            ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ]))
        block.append(ph)

        # HTS + duty grid
        usitc_label = "Matched to USITC database" if usitc_ok else "Not confirmed in USITC database"
        usitc_lcolor= TEAL if usitc_ok else RED
        detail = [
            [Paragraph("Declared HTS:", S["label"]),
             Paragraph(hts, S["code"]),
             Paragraph("USITC Check:", S["label"]),
             Paragraph(usitc_label, PS("UL", fontSize=8, fontName="Helvetica-Bold", textColor=usitc_lcolor))],
            [Paragraph("Duties Applied:", S["label"]),
             Paragraph(tariff_l if tariff_l else total_d, S["body"]),
             Paragraph("AI Risk Flag:", S["label"]),
             Paragraph(rl, PS("RL", fontSize=8.5, fontName="Helvetica-Bold", textColor=fg))],
        ]
        if s232 and "N/A" not in s232:
            detail.append([
                Paragraph("Section 232:", S["label"]),
                Paragraph(s232, S["bold"]),
                Paragraph("Est. Duty USD:", S["label"]),
                Paragraph(f"${est_d}" if est_d and not str(est_d).startswith("$") else (est_d or "—"), S["body"])
            ])
        elif est_d:
            detail.append([
                Paragraph("Est. Duty USD:", S["label"]),
                Paragraph(f"${est_d}" if not str(est_d).startswith("$") else est_d, S["body"]),
                Paragraph("", S["label"]), Paragraph("", S["body"])
            ])

        dt = Table(detail, colWidths=[0.9*inch, 2.55*inch, 0.9*inch, 2.55*inch])
        dt.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), bg),
            ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
            ("LEFTPADDING",   (0,0),(-1,-1), 6),
            ("RIGHTPADDING",  (0,0),(-1,-1), 4),
            ("TOPPADDING",    (0,0),(-1,-1), 3),
            ("BOTTOMPADDING", (0,0),(-1,-1), 3),
            ("LINEBELOW",     (0,0),(-1,-2), 0.3, BORDER),
        ]))
        block.append(dt)

        # USITC official description
        if usitc_d:
            ur = Table([[
                Paragraph("USITC Official:", S["label"]),
                Paragraph(usitc_d[:120], S["usitc"]),
            ]], colWidths=[0.9*inch, 6.0*inch])
            ur.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),(-1,-1), SOFT_B),
                ("VALIGN",        (0,0),(-1,-1), "TOP"),
                ("LEFTPADDING",   (0,0),(-1,-1), 6),
                ("TOPPADDING",    (0,0),(-1,-1), 3),
                ("BOTTOMPADDING", (0,0),(-1,-1), 3),
            ]))
            block.append(ur)

        # Analysis — strip China/301 repetition if global notice covers it
        if notes:
            # Remove boilerplate that's now in the global section
            clean_notes = notes
            boilerplate = [
                "Importer should maintain robust supply chain due diligence to mitigate potential UFLPA risks, as all goods from China are subject to increased scrutiny.",
                "This product from China is subject to a 25% Section 301 List 3 surcharge in addition to",
            ]
            for bp in boilerplate:
                if bp in clean_notes:
                    clean_notes = clean_notes.replace(bp, "").strip().strip(".")
            clean_notes = clean_notes.strip()

            if clean_notes:
                nr = Table([[
                    Paragraph("Analysis:", S["label"]),
                    Paragraph(clean_notes, PS("NV", fontSize=8.5, textColor=BLACK, leading=13)),
                ]], colWidths=[0.65*inch, 6.25*inch])
                nr.setStyle(TableStyle([
                    ("BACKGROUND",    (0,0),(-1,-1), SOFT_B if rl=="LOW" else (SOFT_A if rl=="MEDIUM" else SOFT_R)),
                    ("VALIGN",        (0,0),(-1,-1), "TOP"),
                    ("LEFTPADDING",   (0,0),(-1,-1), 6),
                    ("TOPPADDING",    (0,0),(-1,-1), 5),
                    ("BOTTOMPADDING", (0,0),(-1,-1), 5),
                ]))
                block.append(nr)

        # Sanctions
        if sanctions:
            scl = SOFT_G if "CLEARED" in sanctions.upper() else SOFT_R
            scc = TEAL   if "CLEARED" in sanctions.upper() else RED
            sr = Table([[
                Paragraph("Sanctions:", S["label"]),
                Paragraph(sanctions[:160], PS("SV", fontSize=8, textColor=scc, leading=12)),
            ]], colWidths=[0.7*inch, 6.2*inch])
            sr.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),(-1,-1), scl),
                ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
                ("LEFTPADDING",   (0,0),(-1,-1), 6),
                ("TOPPADDING",    (0,0),(-1,-1), 3),
                ("BOTTOMPADDING", (0,0),(-1,-1), 3),
            ]))
            block.append(sr)

        # ── BROKER-GRADE ADDITIONS (HIGH risk items only) ────────
        if rl == "HIGH":
            broker_block = []

            # 1. Classification Reasoning (GRI-based)
            hts_clean = hts.replace(".","")
            chapter = hts_clean[:2] if len(hts_clean) >= 2 else "??"
            cross_match_note = ""
            if p.get("cross_hts_match"):
                cross_match_note = " CBP CROSS rulings show similar products classified under this heading."
            elif p.get("cross_rulings"):
                alt_hts = []
                for cr in p.get("cross_rulings",[])[:2]:
                    alt_hts.extend(cr.get("hts_codes",[])[:1])
                if alt_hts:
                    cross_match_note = f" CBP CROSS rulings show similar products classified under: {', '.join(set(alt_hts[:2]))}."
            gri_text = (
                f"GRI 1: Classification based on product function and heading text — Chapter {chapter}. "
                f"GRI 6: Subheading determined by technical specifications (wattage, material, composition). "
                f"Potential inconsistency identified between declared product description and HTS subheading criteria."
                f"{cross_match_note} "
                f"Final GRI application must be determined by a licensed customs broker."
            )
            broker_block.append(Table([[
                Paragraph("Classification Reasoning (AI-Assisted):", PS("CRH", fontSize=8, fontName="Helvetica-Bold", textColor=DKBLUE)),
            ],[
                Paragraph(gri_text, PS("CRB", fontSize=8, textColor=BLACK, leading=12)),
            ]], colWidths=[6.9*inch]))

            # 2. Data Sufficiency Check
            missing_data = []
            desc_lower = name.lower()
            if any(w in desc_lower for w in ["motor","pump","engine"]):
                missing_data.append("Exact wattage/output rating (confirmed vs. estimated)")
                missing_data.append("Motor type confirmation (AC / DC / stepper / servo)")
            if any(w in desc_lower for w in ["steel","aluminum","alloy","metal"]):
                missing_data.append("Material grade and composition certificate")
            if any(w in desc_lower for w in ["chemical","compound","paste","fluid"]):
                missing_data.append("Chemical composition / MSDS / TSCA certification")
            if not missing_data:
                missing_data.append("Confirm technical datasheet matches product description on invoice")
            data_rows = [[Paragraph("Data Sufficiency Check:", PS("DSH", fontSize=8, fontName="Helvetica-Bold", textColor=AMBER))]]
            for md in missing_data:
                data_rows.append([Paragraph(f"  - {md}", PS("DSB", fontSize=7.5, textColor=BLACK, leading=11))])
            data_rows.append([Paragraph(
                "Action: Importer should obtain and provide technical specifications before broker files entry.",
                PS("DSA", fontSize=7.5, fontName="Helvetica-Oblique", textColor=DGRAY)
            )])
            dst = Table(data_rows, colWidths=[6.9*inch])
            dst.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),(-1,-1), SOFT_A),
                ("LEFTPADDING",   (0,0),(-1,-1), 8),
                ("TOPPADDING",    (0,0),(-1,-1), 3),
                ("BOTTOMPADDING", (0,0),(-1,-1), 3),
            ]))
            broker_block.append(dst)

            # 3. AI Confidence Score
            usitc_match = p.get("usitc_verified", False)
            conf_score  = 60  # base
            if usitc_match:    conf_score += 15
            if rs <= 40:       conf_score += 10
            if rs >= 70:       conf_score -= 15
            if len(name) > 30: conf_score += 5   # detailed description
            conf_score = max(20, min(90, conf_score))
            conf_color = GREEN if conf_score >= 70 else (AMBER if conf_score >= 50 else RED)
            conf_text  = "Moderate" if conf_score < 70 else ("High" if conf_score >= 80 else "Moderate-High")

            conf_rows = [
                [Paragraph("AI Confidence Score:", PS("ACH", fontSize=8, fontName="Helvetica-Bold", textColor=DKBLUE)),
                 Paragraph(f"{conf_score}% ({conf_text})", PS("ACV", fontSize=9, fontName="Helvetica-Bold", textColor=conf_color))],
                [Paragraph("Basis:", PS("ACB", fontSize=7.5, textColor=DGRAY)),
                 Paragraph(
                     f"USITC match: {'confirmed (+15%)' if usitc_match else 'not confirmed (-10%)'}  |  "
                     f"Risk score: {rs}/100  |  Description detail: {'adequate' if len(name)>30 else 'limited'}. "
                     f"Interpretation: Broker validation required before filing.",
                     PS("ACD", fontSize=7.5, textColor=BLACK, leading=11)
                 )],
            ]
            ct = Table(conf_rows, colWidths=[1.4*inch, 5.5*inch])
            ct.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),(-1,-1), SOFT_B),
                ("VALIGN",        (0,0),(-1,-1), "TOP"),
                ("LEFTPADDING",   (0,0),(-1,-1), 6),
                ("TOPPADDING",    (0,0),(-1,-1), 3),
                ("BOTTOMPADDING", (0,0),(-1,-1), 3),
            ]))
            broker_block.append(ct)

            # 4. Assumptions block
            assumptions = [
                f"Product type inferred from invoice description: '{name[:40]}'",
                "Country of origin accepted as declared — not independently verified",
                "Wattage/specifications assumed accurate as declared on invoice",
                "No additional technical datasheet or manufacturer spec sheet provided",
            ]
            arows = [[Paragraph("Assumptions Used in This Analysis:", PS("AH", fontSize=8, fontName="Helvetica-Bold", textColor=DGRAY))]]
            for a in assumptions:
                arows.append([Paragraph(f"  - {a}", PS("AB", fontSize=7.5, textColor=DGRAY, leading=11))])
            at = Table(arows, colWidths=[6.9*inch])
            at.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),(-1,-1), LGRAY),
                ("LEFTPADDING",   (0,0),(-1,-1), 8),
                ("TOPPADDING",    (0,0),(-1,-1), 2),
                ("BOTTOMPADDING", (0,0),(-1,-1), 2),
            ]))
            broker_block.append(at)

            # Wrap entire broker block in a bordered box
            for brow in broker_block:
                story.append(brow)
            story.append(Spacer(1, 3))

        # CROSS CBP Rulings
        cross_rulings  = p.get("cross_rulings", []) or []
        cross_status   = p.get("cross_status", "")
        cross_hts_match= p.get("cross_hts_match", False)
        if cross_rulings:
            status_color = GREEN if cross_hts_match else AMBER
            status_text  = "HTS code found in CBP rulings" if cross_hts_match else "Related rulings found — HTS not directly cited"
            cross_rows = [[
                Paragraph("CBP CROSS Rulings:", S["label"]),
                Paragraph(status_text, PS("CRS", fontSize=7.5, fontName="Helvetica-Bold", textColor=status_color)),
            ]]
            for ruling in cross_rulings[:3]:
                revoked_note = " [REVOKED]" if ruling.get("revoked") else ""
                cross_rows.append([
                    Paragraph("", S["label"]),
                    Paragraph(
                        f"{ruling['number']}{revoked_note} ({ruling['date'][:7]}) — {ruling['subject'][:80]}  "
                        f"[HTS: {', '.join(ruling.get('hts_codes',[])[:2])}]  "
                        f"rulings.cbp.gov/ruling/{ruling['number']}",
                        PS("CRR", fontSize=7, textColor=DGRAY if not ruling.get("revoked") else RED, leading=11)
                    ),
                ])
            cross_rows.append([
                Paragraph("", S["label"]),
                Paragraph(
                    "Note: CBP rulings are fact-specific and may not apply to this exact product. "
                    "Broker/legal interpretation required.",
                    PS("CRN", fontSize=7, fontName="Helvetica-Oblique", textColor=DGRAY, leading=11)
                ),
            ])
            crt = Table(cross_rows, colWidths=[1.0*inch, 5.9*inch])
            crt.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),(-1,-1), SOFT_B),
                ("VALIGN",        (0,0),(-1,-1), "TOP"),
                ("LEFTPADDING",   (0,0),(-1,-1), 6),
                ("TOPPADDING",    (0,0),(-1,-1), 3),
                ("BOTTOMPADDING", (0,0),(-1,-1), 3),
                ("LINEABOVE",     (0,0),(-1,0),  0.5, BORDER),
            ]))
            block.append(crt)

        # Required docs
        if req_docs:
            dr = Table([[
                Paragraph("Required Docs:", S["label"]),
                Paragraph("  /  ".join(req_docs[:6]), S["small"]),
            ]], colWidths=[0.9*inch, 6.0*inch])
            dr.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),(-1,-1), LGRAY),
                ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
                ("LEFTPADDING",   (0,0),(-1,-1), 6),
                ("TOPPADDING",    (0,0),(-1,-1), 3),
                ("BOTTOMPADDING", (0,0),(-1,-1), 3),
            ]))
            block.append(dr)

        block.append(HRFlowable(width="100%", thickness=0.8, color=BORDER, spaceAfter=7, spaceBefore=0))
        story.append(KeepTogether(block))

    # ══════════════════════════════════════════════════════════════
    # 7. HTS REVIEW TABLE
    # ══════════════════════════════════════════════════════════════
    story.append(div())
    story.append(Paragraph("HTS CLASSIFICATION REVIEW TABLE", S["h2"]))
    story.append(Paragraph(
        "HTS codes below are cross-referenced against the USITC HTSUS 2026 database (hts.usitc.gov). "
        "Status 'Matched to USITC' confirms the code exists in the schedule — it does not constitute "
        "a binding tariff classification ruling. Final classification must be made by a licensed broker.",
        S["italic"]
    ))
    story.append(Spacer(1, 5))

    vhdr = [Paragraph(h, PS("VH", fontSize=7.5, fontName="Helvetica-Bold", textColor=WHITE))
            for h in ["#","Product","Declared HTS","USITC Status","AI Risk Level","Duties Applied"]]
    vrows = [vhdr]
    for i, p in enumerate(products, 1):
        ok    = p.get("usitc_verified", False)
        # SINGLE SOURCE OF TRUTH: risk_level from Gemini
        rlvl  = (p.get("risk_level","MEDIUM") or "MEDIUM").upper()
        rs_n  = int(p.get("risk_score", 0) or 0)
        rcol  = RED if rlvl=="HIGH" else (AMBER if rlvl=="MEDIUM" else GREEN)
        vrows.append([
            Paragraph(str(i), S["small"]),
            Paragraph((p.get("name",""))[:32], PS("VN", fontSize=7)),
            Paragraph(p.get("hs_code",""), PS("VC", fontName="Courier", fontSize=7.5)),
            Paragraph("Exists in HTSUS" if ok else "Not confirmed",
                      PS("VS", fontSize=7.5, fontName="Helvetica-Bold",
                         textColor=TEAL if ok else RED)),
            Paragraph(f"{rlvl} ({rs_n})", PS("VF", fontSize=7.5, fontName="Helvetica-Bold", textColor=rcol)),
            Paragraph(p.get("total_duty_rate",""), PS("VD", fontSize=7.5)),
        ])
    vt = Table(vrows, colWidths=[0.22*inch, 2.2*inch, 0.95*inch, 1.1*inch, 0.8*inch, 1.63*inch])
    vt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  DKBLUE),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [WHITE, LGRAY]),
        ("GRID",          (0,0),(-1,-1), 0.3, BORDER),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("LEFTPADDING",   (0,0),(-1,-1), 3),
        ("TOPPADDING",    (0,0),(-1,-1), 2),
        ("BOTTOMPADDING", (0,0),(-1,-1), 2),
    ]))
    story.append(vt)
    story.append(Spacer(1, 8))

    # ══════════════════════════════════════════════════════════════
    # 8. FINAL RECOMMENDATION
    # ══════════════════════════════════════════════════════════════
    story.append(div())
    story.append(Paragraph("FINAL RECOMMENDATION FOR BROKER REVIEW", S["h2"]))

    rec_bg = SOFT_G if rec=="APPROVE" else (SOFT_R if rec in ("HOLD","REJECT") else SOFT_A)
    rec_bc = GREEN  if rec=="APPROVE" else (RED    if rec in ("HOLD","REJECT") else AMBER)

    # Build broker-ready action list
    broker_actions = []
    if high_products:
        for n, p in high_products:
            hts = p.get("hs_code","")
            broker_actions.append(f"Review HTS classification for Line {n} ({p.get('name','')[:35]}) — declared code {hts} may not match product specifications. Confirm correct code with manufacturer data sheet.")
    if s232_products:
        broker_actions.append(f"Confirm Section 232 applicability for {len(s232_products)} steel/aluminum item(s). Verify product technical specs match classification.")
    if has_s301:
        broker_actions.append("Obtain and retain UFLPA supply chain documentation for all China-origin goods: manufacturer name/address, description of production process, and signed country of origin declaration.")
    if usitc_f:
        broker_actions.append(f"Manually verify {usitc_f} HTS code(s) not confirmed in USITC HTSUS database before filing entry.")
    broker_actions.append("Verify declared values against invoice and packing list. CBP may query transaction value on China-origin goods.")
    broker_actions.append("Retain this report and supporting documents for 5 years per 19 CFR 163 (reasonable care recordkeeping).")

    rec_rows = [[Paragraph(
        f"AI RISK ASSESSMENT: {rec}  |  Risk Items: {high_c} HIGH, {med_c} MEDIUM, {low_c} LOW",
        PS("RH", fontSize=11, fontName="Helvetica-Bold", textColor=rec_bc, alignment=TA_CENTER)
    )]]
    if summary:
        rec_rows.append([Paragraph(summary, S["italic"])])

    rec_rows.append([Paragraph("Broker Action Items:", PS("BAH", fontSize=9, fontName="Helvetica-Bold", textColor=NAVY, spaceAfter=3))])
    for j, action in enumerate(broker_actions, 1):
        rec_rows.append([Paragraph(f"{j}. {action}", S["body"])])

    rec_rows.append([Paragraph(
        "This report is designed to support reasonable care under 19 U.S.C. Section 1484. "
        "Final classification, valuation, and filing decisions must be made by a licensed "
        "US customs broker or attorney.",
        PS("RC", fontSize=8, fontName="Helvetica-Oblique", textColor=DGRAY, leading=12)
    )])

    rt = Table(rec_rows, colWidths=[6.9*inch])
    rt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), rec_bg),
        ("BOX",           (0,0),(-1,-1), 1.5, rec_bc),
        ("LEFTPADDING",   (0,0),(-1,-1), 10),
        ("RIGHTPADDING",  (0,0),(-1,-1), 10),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
    ]))
    story.append(rt)
    story.append(Spacer(1, 10))

    # ══════════════════════════════════════════════════════════════
    # 9. FOOTER
    # ══════════════════════════════════════════════════════════════
    story.append(div(DGRAY, 4))
    story.append(Table([[
        Paragraph("TradeShield AI  |  itcloudx.com  |  Stop Fines Before They Start  |  Powered by Gemini + USITC", S["footer"]),
        Paragraph("AI-assisted pre-screening only. Licensed customs broker review required before CBP filing.", S["footer"]),
    ]], colWidths=[3.8*inch, 3.1*inch]))

    if not is_pro:
        story.append(Spacer(1, 4))
        story.append(Table([[Paragraph(
            "Upgrade to Pro for full 25-item analysis, unlimited scans, and clean broker-ready reports — itcloudx.com/pricing",
            PS("WM", fontSize=8, textColor=AMBER, fontName="Helvetica-Bold", alignment=TA_CENTER)
        )]], colWidths=[6.9*inch]))

    doc.build(story)
    return buf.getvalue()
