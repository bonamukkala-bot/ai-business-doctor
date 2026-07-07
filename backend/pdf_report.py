import io
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle", parent=styles["Title"], fontSize=20, spaceAfter=4
    ))
    styles.add(ParagraphStyle(
        name="SectionHeading", parent=styles["Heading2"], spaceBefore=16, spaceAfter=6,
        textColor=colors.HexColor("#1a3c34")
    ))
    styles.add(ParagraphStyle(
        name="ReasoningText", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#444444")
    ))
    return styles


def build_pdf_report(insights: dict) -> io.BytesIO:
    """
    Builds a formatted PDF version of the business diagnosis report, so the
    owner can download, print, or share it with a partner/supplier — real
    business value beyond just an on-screen dashboard.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
    )
    styles = _styles()
    story = []

    # --- Title ---
    story.append(Paragraph("AI Business Doctor — Diagnostic Report", styles["ReportTitle"]))
    story.append(Paragraph(
        f"Generated {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", styles["Normal"]
    ))
    story.append(Spacer(1, 12))

    # --- Vitals summary ---
    profit = insights["profit_analysis"]
    vitals_data = [
        ["Profit Trend (15 days)", "Stop-Selling Candidates", "Urgent Reorders"],
        [
            f"Rs {profit['total_profit_change']:,.0f}",
            str(len(insights["stop_selling"])),
            str(len(insights["reorder"])),
        ],
    ]
    vitals_table = Table(vitals_data, colWidths=[2.2 * inch] * 3)
    vitals_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c34")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, 1), 13),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(vitals_table)
    story.append(Spacer(1, 10))

    health = insights.get("health_score")
    if health:
        story.append(Paragraph(
            f"<b>Business Health Score: {health['score']}/100 — {health['label']}</b>",
            styles["Normal"]
        ))
    story.append(Spacer(1, 16))

    # --- Top Priority Actions ---
    story.append(Paragraph("Top Priority Actions", styles["SectionHeading"]))
    actions = insights.get("priority_actions", [])
    if not actions:
        story.append(Paragraph("No urgent actions flagged.", styles["Normal"]))
    else:
        for a in actions:
            story.append(Paragraph(
                f"<b>#{a['rank']} [{a['urgency_label']}] {a['product']}</b> — "
                f"Rs {a['impact_rupees']:,.0f} impact", styles["Normal"]
            ))
            story.append(Paragraph(a["recommended_action"], styles["ReasoningText"]))
            story.append(Spacer(1, 6))

    # --- Anomaly Alerts ---
    anomalies = insights.get("anomaly_alerts", [])
    if anomalies:
        story.append(Paragraph("Alerts", styles["SectionHeading"]))
        for a in anomalies:
            story.append(Paragraph(f"<b>[{a['severity'].upper()}]</b> {a['message']}", styles["ReasoningText"]))
            story.append(Spacer(1, 4))

    story.append(PageBreak())

    # --- Profit Movement ---
    story.append(Paragraph("Diagnosis: Profit Movement", styles["SectionHeading"]))
    story.append(Paragraph(profit["summary"], styles["Normal"]))
    story.append(Spacer(1, 6))
    for d in profit["top_drivers"]:
        story.append(Paragraph(f"<b>{d['product']}</b> ({d['pct_change']}%)", styles["Normal"]))
        story.append(Paragraph(d["reasoning"], styles["ReasoningText"]))
        story.append(Spacer(1, 6))

    # --- Stop Selling ---
    story.append(Paragraph("Prescription: Consider Discontinuing", styles["SectionHeading"]))
    if not insights["stop_selling"]:
        story.append(Paragraph("No products currently qualify.", styles["Normal"]))
    for s in insights["stop_selling"]:
        story.append(Paragraph(f"<b>{s['product']}</b> — {s['avg_daily_units']}/day", styles["Normal"]))
        story.append(Paragraph(s["reasoning"], styles["ReasoningText"]))
        story.append(Spacer(1, 6))

    # --- Reorder ---
    story.append(Paragraph("Prescription: Reorder Urgently", styles["SectionHeading"]))
    if not insights["reorder"]:
        story.append(Paragraph("Nothing urgent right now.", styles["Normal"]))
    for r in insights["reorder"]:
        story.append(Paragraph(
            f"<b>{r['product']}</b> — {r['days_of_stock_left']} days left, "
            f"reorder {r['recommended_reorder_qty']} units", styles["Normal"]
        ))
        story.append(Paragraph(r["reasoning"], styles["ReasoningText"]))
        story.append(Spacer(1, 6))

    # --- Raw Summary Table ---
    story.append(PageBreak())
    story.append(Paragraph("Raw Data Summary (90 days)", styles["SectionHeading"]))
    raw = insights.get("raw_summary", [])
    if raw:
        table_data = [["Product", "Units", "Revenue (Rs)", "Profit (Rs)", "Stock"]]
        for row in raw:
            table_data.append([
                row["product"], str(row["total_units"]),
                f"{row['total_revenue']:,.0f}", f"{row['total_profit']:,.0f}",
                str(row["current_stock"]),
            ])
        raw_table = Table(table_data, colWidths=[1.8 * inch, 0.9 * inch, 1.2 * inch, 1.2 * inch, 0.8 * inch])
        raw_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c34")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(raw_table)

    doc.build(story)
    buffer.seek(0)
    return buffer