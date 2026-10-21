"""Printable extra statements, grouped by consumption day in the hotel's zone.

Generating a statement is a read-only operation. Voided charges remain visible
for traceability but never contribute to daily or final amounts.
"""

from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

import reportlab
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import Charge, HotelSettings

ZERO = Decimal("0.00")
BRAND = colors.HexColor("#7367f0")
INK = colors.HexColor("#283046")
MUTED = colors.HexColor("#64748b")
PALE = colors.HexColor("#f4f2ff")
BORDER = colors.HexColor("#e2e8f0")

# Embed fonts shipped by ReportLab: identical output on Windows and in Docker,
# with accented Italian text and the euro glyph independent of system fonts.
FONT_DIRECTORY = Path(reportlab.__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("HotelSans", str(FONT_DIRECTORY / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("HotelSansBold", str(FONT_DIRECTORY / "VeraBd.ttf")))
pdfmetrics.registerFontFamily(
    "HotelSans", normal="HotelSans", bold="HotelSansBold", italic="HotelSans", boldItalic="HotelSansBold"
)


@dataclass(frozen=True)
class ExtraDay:
    date: date
    charges: tuple[Charge, ...]
    total: Decimal


def consumption_time(charge: Charge, zone: ZoneInfo) -> datetime:
    return (charge.consumed_at or charge.created_at).astimezone(zone)


def group_extra_days(charges, zone: ZoneInfo) -> list[ExtraDay]:
    grouped = OrderedDict()
    rows = sorted(
        (charge for charge in charges if charge.kind == "extra"),
        key=lambda charge: ((charge.consumed_at or charge.created_at).astimezone(UTC), charge.pk),
    )
    for charge in rows:
        grouped.setdefault(consumption_time(charge, zone).date(), []).append(charge)
    return [
        ExtraDay(day, tuple(items), sum((row.amount for row in items if not row.voided_at), ZERO))
        for day, items in grouped.items()
    ]


def euro(amount: Decimal) -> str:
    return f"{amount:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".") + " €"


def quantity(value: Decimal) -> str:
    return (
        format(value, "f").rstrip("0").rstrip(".").replace(".", ",")
        if "." in format(value, "f")
        else str(value)
    )


def render_extra_statement(*, hotel: HotelSettings, heading: str, subtitle: str, charges) -> bytes:
    zone = ZoneInfo(hotel.timezone)
    days = group_extra_days(charges, zone)
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
        title="Estratto extra - " + heading,
        author=hotel.name,
        pageCompression=1,
        allowSplitting=True,
    )
    styles = {
        "brand": ParagraphStyle("brand", fontName="HotelSansBold", fontSize=12, leading=17, textColor=BRAND),
        "title": ParagraphStyle(
            "title", fontName="HotelSansBold", fontSize=19, leading=25, textColor=INK, spaceAfter=5 * mm
        ),
        "body": ParagraphStyle("body", fontName="HotelSans", fontSize=9, leading=14, textColor=INK),
        "small": ParagraphStyle("small", fontName="HotelSans", fontSize=8, leading=12, textColor=MUTED),
        "cell": ParagraphStyle(
            "cell", fontName="HotelSans", fontSize=8, leading=12, textColor=INK, splitLongWords=True
        ),
        "void": ParagraphStyle("void", fontName="HotelSans", fontSize=8, leading=12, textColor=MUTED),
        "head": ParagraphStyle("head", fontName="HotelSansBold", fontSize=7.5, leading=11, textColor=MUTED),
        "day": ParagraphStyle("day", fontName="HotelSansBold", fontSize=10, leading=15, textColor=BRAND),
        "sum": ParagraphStyle(
            "sum", fontName="HotelSansBold", fontSize=9, leading=14, textColor=INK, alignment=TA_RIGHT
        ),
        "number": ParagraphStyle(
            "number", fontName="HotelSans", fontSize=8, leading=12, textColor=INK, alignment=TA_RIGHT
        ),
    }

    def paragraph(text, style="cell"):
        # Descriptions and guest names are untrusted text, never ReportLab XML.
        safe = escape(str(text)).replace("\n", "<br/>")
        return Paragraph(safe, styles[style])

    story = [
        paragraph(hotel.name, "brand"),
        Spacer(1, 3 * mm),
        paragraph("Estratto extra per giorno", "title"),
        paragraph(heading, "body"),
        paragraph(subtitle, "small"),
        Spacer(1, 4 * mm),
        paragraph(f"Data e ora consumazioni nel fuso {hotel.timezone}.", "small"),
        Spacer(1, 6 * mm),
    ]
    total = ZERO
    for day in days:
        data = [[paragraph(day.date.strftime("%d/%m/%Y"), "day"), "", "", "", "", "", ""]]
        data.append(
            [
                paragraph(text, "head")
                for text in ("Ora", "Camera", "Descrizione", "Qtà", "Prezzo", "Importo", "Stato")
            ]
        )
        void_rows = []
        for charge in day.charges:
            local = consumption_time(charge, zone)
            room_number = charge.stay.room.number
            # Use the recorded room segment at consumption time after a move.
            for segment in charge.stay.segments.all():
                if segment.arrival <= (charge.consumed_at or charge.created_at) < segment.departure:
                    room_number = segment.room.number
                    break
            void = bool(charge.voided_at)
            row_style = "void" if void else "cell"
            data.append(
                [
                    paragraph(local.strftime("%H:%M"), row_style),
                    paragraph(room_number, row_style),
                    paragraph(
                        charge.description + (f"\nStorno: {charge.void_reason}" if void else ""), row_style
                    ),
                    paragraph(quantity(charge.quantity), "number"),
                    paragraph(euro(charge.unit_price), "number"),
                    paragraph(euro(charge.amount), "number"),
                    paragraph("Stornato" if void else "Addebitato", row_style),
                ]
            )
            if void:
                void_rows.append(len(data) - 1)
        data.append(
            [
                paragraph("Totale giorno (esclusi storni)", "sum"),
                "",
                "",
                "",
                "",
                paragraph(euro(day.total), "sum"),
                "",
            ]
        )
        table = LongTable(
            data,
            colWidths=[15 * mm, 16 * mm, 61 * mm, 12 * mm, 23 * mm, 25 * mm, 26 * mm],
            repeatRows=2,
            hAlign="LEFT",
        )
        commands = [
            ("SPAN", (0, 0), (-1, 0)),
            ("BACKGROUND", (0, 0), (-1, 0), PALE),
            ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f8fafc")),
            ("LINEBELOW", (0, 1), (-1, 1), 0.6, BORDER),
            ("LINEBELOW", (0, 2), (-1, -2), 0.3, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("SPAN", (0, -1), (4, -1)),
            ("SPAN", (5, -1), (6, -1)),
            ("BACKGROUND", (0, -1), (-1, -1), PALE),
        ]
        for row in void_rows:
            commands.append(("BACKGROUND", (0, row), (-1, row), colors.HexColor("#f8fafc")))
        table.setStyle(TableStyle(commands))
        story.extend([table, Spacer(1, 5 * mm)])
        total += day.total
    if not days:
        story.extend(
            [paragraph("Nessuna consumazione registrata per questo conto.", "body"), Spacer(1, 6 * mm)]
        )
    summary = Table(
        [[paragraph("TOTALE EXTRA", "sum"), paragraph(euro(total), "sum")]],
        colWidths=[125 * mm, 53 * mm],
        hAlign="LEFT",
    )
    summary.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.extend(
        [
            summary,
            Spacer(1, 4 * mm),
            paragraph(
                "Importi gestionali in euro. Gli extra stornati non concorrono ai totali. Documento non fiscale.",
                "small",
            ),
        ]
    )
    generated = timezone.now().astimezone(zone).strftime("%d/%m/%Y %H:%M")

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(BORDER)
        canvas.line(16 * mm, 16 * mm, 194 * mm, 16 * mm)
        canvas.setFont("HotelSans", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(16 * mm, 11 * mm, f"Generato il {generated} - {hotel.timezone}")
        canvas.drawRightString(194 * mm, 11 * mm, f"Pagina {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
