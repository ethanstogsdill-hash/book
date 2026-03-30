"""PDF settlement report generation using reportlab."""
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def generate_settlement_pdf(week_ending: str, settlements: list) -> bytes:
    """Generate a PDF settlement report and return bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.75*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=18, spaceAfter=12)
    elements.append(Paragraph(f"Settlement Report", title_style))
    elements.append(Paragraph(f"Week Ending: {week_ending}", styles['Normal']))
    elements.append(Spacer(1, 20))

    # Separate by type
    sub_settlements = [s for s in settlements if s["counterparty_type"] == "sub_agent"]
    player_settlements = [s for s in settlements if s["counterparty_type"] == "player"]
    backer_settlements = [s for s in settlements if s["counterparty_type"] == "backer"]

    def fmt(n):
        if n < 0:
            return f"-${abs(n):,.2f}"
        return f"${n:,.2f}"

    # Sub-agent table
    if sub_settlements:
        elements.append(Paragraph("Sub-Agent Settlements", styles['Heading2']))
        elements.append(Spacer(1, 8))

        data = [["Name", "Amount", "Direction", "Vig", "Status", "Notes"]]
        for s in sub_settlements:
            data.append([
                s["counterparty_name"],
                fmt(s["amount"]),
                s["direction"].upper(),
                fmt(s["vig_amount"]),
                s["status"].upper(),
                (s["notes"] or "")[:40],
            ])

        t = Table(data, colWidths=[1.5*inch, 1*inch, 0.9*inch, 0.8*inch, 0.8*inch, 1.5*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (1, 0), (4, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#334155')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 16))

    # Direct player table
    if player_settlements:
        elements.append(Paragraph("Direct Player Settlements", styles['Heading2']))
        elements.append(Spacer(1, 8))

        data = [["Name", "Amount", "Direction", "Status"]]
        for s in player_settlements:
            data.append([
                s["counterparty_name"],
                fmt(s["amount"]),
                s["direction"].upper(),
                s["status"].upper(),
            ])

        t = Table(data, colWidths=[2*inch, 1.2*inch, 1*inch, 1*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (1, 0), (3, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#334155')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 16))

    # Backer summary
    if backer_settlements:
        elements.append(Paragraph("Backer Settlement", styles['Heading2']))
        elements.append(Spacer(1, 8))
        for s in backer_settlements:
            direction_text = "PAY to backer" if s["direction"] == "pay" else "COLLECT from backer"
            elements.append(Paragraph(
                f"<b>{direction_text}:</b> {fmt(s['amount'])}",
                styles['Normal']
            ))
            if s.get("notes"):
                elements.append(Paragraph(f"<i>{s['notes']}</i>", styles['Normal']))
        elements.append(Spacer(1, 16))

    # Summary totals
    total_collect = sum(s["amount"] for s in settlements if s["direction"] == "collect")
    total_pay = sum(s["amount"] for s in settlements if s["direction"] == "pay")
    net = total_collect - total_pay

    elements.append(Paragraph("Summary", styles['Heading2']))
    elements.append(Spacer(1, 8))

    summary_data = [
        ["Total to Collect", fmt(total_collect)],
        ["Total to Pay", fmt(total_pay)],
        ["Net Position", fmt(net)],
    ]
    t = Table(summary_data, colWidths=[2*inch, 1.5*inch])
    t.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LINEBELOW', (0, -1), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t)

    doc.build(elements)
    return buf.getvalue()
