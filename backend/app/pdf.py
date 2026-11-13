"""Generates the completed-ballot PDF (buletin de vot completat), matching the fixed legal
layout: centered title, a date/city line, two left-aligned legal paragraphs, the decisions
(Hotărâri) with the owner's vote, and the holographic signature at the end."""
import os
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from .ballot_text import build_ballot_texts, question_label

# Register a Unicode TTF font so Romanian diacritics (ă, â, î, ș, ț) render correctly -
# the base14 PDF fonts (Helvetica) do not support them.
_FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")
pdfmetrics.registerFont(TTFont("DejaVuSans", os.path.join(_FONTS_DIR, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", os.path.join(_FONTS_DIR, "DejaVuSans-Bold.ttf")))

styles = getSampleStyleSheet()
title_style = ParagraphStyle("TitleCustom", parent=styles["Title"], alignment=TA_CENTER, fontSize=14, leading=18, fontName="DejaVuSans-Bold")
body_style = ParagraphStyle("BodyCustom", parent=styles["Normal"], alignment=TA_LEFT, fontSize=10.5, leading=15, spaceAfter=8, fontName="DejaVuSans")
left_style = ParagraphStyle("LeftCustom", parent=styles["Normal"], alignment=TA_LEFT, fontSize=10.5, fontName="DejaVuSans")
right_style = ParagraphStyle("RightCustom", parent=styles["Normal"], alignment=TA_RIGHT, fontSize=10.5, fontName="DejaVuSans")
h2_style = ParagraphStyle("H2Custom", parent=styles["Heading2"], fontSize=11, spaceAfter=4, fontName="DejaVuSans-Bold")
normal_style = ParagraphStyle("NormalCustom", parent=styles["Normal"], fontName="DejaVuSans")
small_style = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, textColor=colors.grey, fontName="DejaVuSans")


def _answer_text(question: dict, answer) -> str:
    if question.get("type") == "multiple" and isinstance(answer, list):
        return ", ".join(str(a) for a in answer) if answer else "(fără răspuns)"
    if answer in (None, "", []):
        return "(fără răspuns)"
    return str(answer)


def generate_receipt_pdf(
    *,
    election,
    voter,
    answers: dict,
    submitted_at: datetime,
    signature_path: str | None,
    output_path: str,
    gdpr_consent_at: datetime | None = None,
) -> str:
    texts = build_ballot_texts(election, voter)
    questions = __import__("json").loads(election.questions_json or "[]")

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm, leftMargin=20 * mm, rightMargin=20 * mm,
    )
    elements = []

    elements.append(Paragraph(texts["title"], title_style))
    elements.append(Spacer(1, 4 * mm))

    date_city_table = Table(
        [[Paragraph(texts["date_line"], left_style), Paragraph(texts["city_line"], right_style)]],
        colWidths=[85 * mm, 85 * mm],
    )
    date_city_table.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    elements.append(date_city_table)
    elements.append(Spacer(1, 5 * mm))

    elements.append(Paragraph(texts["paragraph1"], body_style))
    elements.append(Paragraph(texts["paragraph2"], body_style))
    elements.append(Spacer(1, 4 * mm))

    for i, q in enumerate(questions, start=1):
        qid = q["id"]
        elements.append(Paragraph(question_label(q, i), h2_style))
        elements.append(Paragraph(f"Vot: <b>{_answer_text(q, answers.get(qid))}</b>", normal_style))
        elements.append(Spacer(1, 3 * mm))

    meta_rows = [
        ["ID vot (token):", voter.id if voter else ""],
        ["Data și ora votării:", submitted_at.strftime("%d.%m.%Y %H:%M:%S UTC")],
    ]
    if gdpr_consent_at:
        meta_rows.append(["Consimțământ GDPR:", gdpr_consent_at.strftime("%d.%m.%Y %H:%M:%S UTC")])
    meta_table = Table(meta_rows, colWidths=[45 * mm, 120 * mm])
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "DejaVuSans"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
    ]))
    elements.append(Spacer(1, 4 * mm))
    elements.append(meta_table)

    if signature_path and os.path.exists(signature_path):
        elements.append(Spacer(1, 6 * mm))
        elements.append(Paragraph("Semnătură olografă:", h2_style))
        elements.append(RLImage(signature_path, width=60 * mm, height=30 * mm))

    elements.append(Spacer(1, 8 * mm))
    elements.append(Paragraph(
        "Acest document a fost generat automat și confirmă înregistrarea votului dumneavoastră. "
        f"Generat de sistemul de vot la {datetime.utcnow().strftime('%d.%m.%Y %H:%M:%S UTC')}.",
        small_style,
    ))

    doc.build(elements)
    return output_path
