"""Generates the completed-ballot PDF (buletin de vot completat), matching the fixed legal
layout: centered title, a date/city line, two left-aligned legal paragraphs, the decisions
(Hotărâri) with the owner's vote, and the holographic signature at the end."""
import os
from datetime import datetime
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from .ballot_text import build_ballot_texts, labelled_questions, public_questions, question_label

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
# legal paragraphs: justified, first line indented ("aliniat")
indent_style = ParagraphStyle(
    "IndentCustom", parent=body_style, alignment=TA_JUSTIFY, firstLineIndent=12 * mm, spaceAfter=8,
)
note_style = ParagraphStyle("NoteCustom", parent=body_style, fontSize=8.5, leading=12, textColor=colors.HexColor("#4b5563"))


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
    template: dict | None = None,
) -> str:
    texts = build_ballot_texts(election, voter, template, submitted_at)
    questions = public_questions(__import__("json").loads(election.questions_json or "[]"))

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm, leftMargin=20 * mm, rightMargin=20 * mm,
    )
    elements = []

    elements.append(Paragraph(xml_escape(texts["title"]), title_style))
    elements.append(Spacer(1, 6 * mm))

    elements.append(Paragraph(xml_escape(texts["paragraph1"]), indent_style))
    elements.append(Paragraph(xml_escape(texts["paragraph2"]), indent_style))
    elements.append(Spacer(1, 4 * mm))

    chestiune_no = 0
    for q, label in labelled_questions(questions):
        if label is None:
            chestiune_no += 1
            chestiune = q.get("text", "").strip().replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            elements.append(Paragraph(f"<b>Chestiunea {chestiune_no}.</b> {chestiune}", h2_style))
            elements.append(Spacer(1, 2 * mm))
            continue
        qid = q["id"]
        text = q.get("text", "").strip().replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        elements.append(Paragraph(f"{label}. {text}", h2_style))
        elements.append(Paragraph(f"Vot: <b>{_answer_text(q, answers.get(qid))}</b>", normal_style))
        elements.append(Spacer(1, 3 * mm))

    # every property the owner voted, enumerated with its block
    props = voter.properties if voter is not None else []
    if props:
        elements.append(Paragraph("Imobilele pentru care votați:", h2_style))
        rows = [["Nr.", "Tip de imobil", "Număr", "Bloc"]]
        for index, p in enumerate(props, start=1):
            rows.append([str(index), p.get("tip_proprietate", ""), p.get("nr_proprietate", ""), p.get("bloc") or "—"])
        table = Table(rows, colWidths=[15 * mm, 60 * mm, 50 * mm, 40 * mm], hAlign="LEFT")
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "DejaVuSans"),
            ("FONTNAME", (0, 0), (-1, 0), "DejaVuSans-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9ca3af")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f8")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements += [table, Spacer(1, 5 * mm)]

    if texts.get("note"):
        elements.append(Paragraph(xml_escape(texts["note"]), note_style))
        elements.append(Spacer(1, 4 * mm))

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
