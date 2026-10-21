"""Printable Italian cash reports generated from the same filters as the UI."""

from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .services import ZERO

BRAND = colors.HexColor("#7367F0")
INK = colors.HexColor("#283046")
MUTED = colors.HexColor("#64748B")


def money(value):
    value = Decimal(value or ZERO)
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " EUR"


def method_label(value):
    return {"cash": "Contanti", "card": "Carta", "transfer": "Bonifico"}.get(value, value)


def room_label(movement):
    payment = movement.payment
    if not payment:
        return "-"
    if payment.stay_id:
        return f"Camera {payment.stay.room.number}"
    rooms = sorted({stay.room.number for stay in payment.group.stays.all()})
    return f"Gruppo {payment.group.name} - camere {', '.join(rooms) or '-'}"


def _paragraph(value, style):
    return Paragraph(escape(str(value or "-")), style)


def build_cash_report_pdf(*, hotel, report, sections, start, end, generated_at, filters):
    """Render the report in readable, paginated business sections."""
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=25 * mm,
        bottomMargin=16 * mm,
        title="Rapporto di cassa",
        author=hotel.name,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=21, textColor=INK)
    subtitle = ParagraphStyle("ReportSubtitle", parent=styles["Normal"], fontSize=9, leading=13, textColor=MUTED)
    normal = ParagraphStyle("ReportNormal", parent=styles["Normal"], fontSize=7.2, leading=9, textColor=INK)
    small = ParagraphStyle("ReportSmall", parent=normal, fontSize=6.6, leading=8)
    amount = ParagraphStyle("ReportAmount", parent=normal, alignment=TA_RIGHT)
    story = [
        Paragraph("Rapporto di cassa", title),
        Paragraph(escape(hotel.name), subtitle),
        Spacer(1, 4 * mm),
    ]
    # `end` is exclusive; show users the same inclusive final date selected in the UI.
    filters_label = [f"Periodo: {start:%d/%m/%Y} - {(end - timedelta(days=1)):%d/%m/%Y}"]
    if filters.get("operator"):
        filters_label.append(f"Operatore ID: {filters['operator']}")
    if filters.get("method"):
        filters_label.append(f"Metodo: {method_label(filters['method'])}")
    if filters.get("shift"):
        filters_label.append(f"Turno: #{filters['shift']}")
    if filters.get("direction"):
        filters_label.append("Direzione: Entrate" if filters["direction"] == "in" else "Direzione: Uscite")
    filters_label.append(f"Generato il: {generated_at:%d/%m/%Y %H:%M}")
    story.append(Paragraph(" | ".join(filters_label), subtitle))
    story.append(Spacer(1, 5 * mm))

    summary = [
        ["Entrate", "Uscite", "Saldo movimenti", "Credito da riscuotere", "Occupazione"],
        [
            money(report["income"]),
            money(report["expenses"]),
            money(report["balance"]),
            money(report["outstanding"]),
            f"{report['occupancy']}%",
        ],
    ]
    summary_table = Table(summary, colWidths=[53 * mm] * 5)
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F5F3FF")),
                ("TEXTCOLOR", (0, 1), (-1, 1), BRAND),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DDD6FE")),
            ]
        )
    )
    story.extend([summary_table, Spacer(1, 6 * mm), Paragraph("Dettaglio per sezione", styles["Heading2"])])
    for section in sections:
        story.extend(
            [
                Spacer(1, 4 * mm),
                Paragraph(f"{escape(section['label'])} - {money(section['total'])}", styles["Heading3"]),
                Spacer(1, 1.5 * mm),
            ]
        )
        rows = [["Data e ora", "Camera / conto", "Direzione", "Importo", "Metodo", "Causale", "Operatore", "Turno"]]
        for row in section["rows"]:
            rows.append(
                [
                    _paragraph(row["display_date"], small),
                    _paragraph(row["account"], small),
                    _paragraph("Entrata" if row["direction"] == "in" else "Uscita", small),
                    _paragraph(money(row["amount"]), amount),
                    _paragraph(method_label(row["method"]), small),
                    _paragraph(row["reason"], small),
                    _paragraph(row["operator_name"], small),
                    _paragraph(f"#{row['shift']}" if row["shift"] else "-", small),
                ]
            )
        if len(rows) == 1:
            rows.append([_paragraph("Nessun movimento nella sezione.", normal)] + [""] * 7)
        movements_table = Table(
            rows,
            colWidths=[28 * mm, 55 * mm, 22 * mm, 26 * mm, 24 * mm, 44 * mm, 47 * mm, 18 * mm],
            repeatRows=1,
        )
        movements_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), BRAND),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 7),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(movements_table)

    def decorate(canvas, document):
        canvas.saveState()
        canvas.setFillColor(INK)
        canvas.rect(0, landscape(A4)[1] - 12 * mm, landscape(A4)[0], 12 * mm, fill=1, stroke=0)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(colors.white)
        canvas.drawString(12 * mm, landscape(A4)[1] - 8 * mm, hotel.name)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(landscape(A4)[0] - 12 * mm, 8 * mm, f"Pagina {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return output.getvalue()
