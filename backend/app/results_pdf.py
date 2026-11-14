"""Results report as PDF (aggregated only, no personal data), attached to the final email sent to the
APC when the vote ends. Uses the same Unicode font as the ballot PDF."""
import os
from datetime import datetime, timezone
from html import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .pdf import body_style, h2_style, small_style, title_style

STATUS_TEXT = {"open": "Votare în curs", "closed": "Votare încheiată"}


def generate_results_pdf(election, results: dict, output_path: str) -> str:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    generated = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M:%S UTC")
    status = STATUS_TEXT.get(results.get("status"), results.get("status", ""))

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm, leftMargin=20 * mm, rightMargin=20 * mm,
    )
    elements = [
        Paragraph(escape(f"Rezultatele votului – {election.title}"), title_style),
        Spacer(1, 3 * mm),
        Paragraph(
            escape(
                f"APC nr. {election.nr_apc or '—'} · {election.str_apc or '—'} · {election.oras or '—'}"
            ),
            body_style,
        ),
        Paragraph(escape(f"Status: {status} · Raport generat: {generated}"), body_style),
        Paragraph(
            escape(
                f"Total voturi: {results['total_votes']} din {results['total_tokens']} "
                f"({results['participation_percent']}% participare)"
            ),
            body_style,
        ),
        Spacer(1, 4 * mm),
    ]

    if not results.get("questions"):
        elements.append(Paragraph("Nu există întrebări configurate.", body_style))

    for question in results.get("questions", []):
        elements.append(Paragraph(escape(f"{question['number']}. {question['text']}"), h2_style))
        rows = [["Opțiune", "Voturi", "Procent"]]
        for option in question.get("options", []):
            rows.append([
                Paragraph(escape(str(option.get("option", ""))), body_style),
                str(option.get("count", 0)),
                f"{option.get('percent', 0)}%",
            ])
        table = Table(rows, colWidths=[110 * mm, 30 * mm, 30 * mm])
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "DejaVuSans"),
            ("FONTNAME", (0, 0), (-1, 0), "DejaVuSans-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9ced8")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f8")),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements += [table, Spacer(1, 5 * mm)]

    elements.append(Paragraph(
        "Raport generat automat de sistemul de vot. Conține rezultate agregate, fără date personale ale votanților.",
        small_style,
    ))
    doc.build(elements)
    return output_path
