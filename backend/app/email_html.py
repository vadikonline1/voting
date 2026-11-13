"""Builds the vote-confirmation email (plain text + HTML) from the admin's email template.

The template may contain the placeholder {buletin}. In the HTML email it is replaced with the
completed ballot (the same content as the PDF); in the plain-text version with the ballot as
text. Without the placeholder the ballot is placed after the template text."""
import json
from datetime import datetime
from html import escape

from .ballot_text import build_ballot_texts, question_label
from .email_utils import render_template

BALLOT_TOKEN = "{buletin}"


def _answer_text(question: dict, answer) -> str:
    if question.get("type") == "multiple" and isinstance(answer, list):
        return ", ".join(str(a) for a in answer) if answer else "(fără răspuns)"
    if answer in (None, "", []):
        return "(fără răspuns)"
    return str(answer)


def _questions(election) -> list:
    return json.loads(election.questions_json or "[]")


def _split_template(template: str, values: dict) -> tuple[str, str]:
    """Rendered text before and after the {buletin} placeholder."""
    if BALLOT_TOKEN in template:
        before, after = template.split(BALLOT_TOKEN, 1)
    else:
        before, after = template, ""
    return render_template(before, values).strip(), render_template(after, values).strip()


def _ballot_text(election, voter, answers: dict, submitted_at: datetime) -> str:
    texts = build_ballot_texts(election, voter)
    lines = [
        texts["title"],
        f"{texts['date_line']}                                    {texts['city_line']}",
        "",
        texts["paragraph1"],
        "",
        texts["paragraph2"],
        "",
    ]
    for i, q in enumerate(_questions(election), start=1):
        lines.append(question_label(q, i))
        lines.append(f"Vot: {_answer_text(q, answers.get(q['id']))}")
        lines.append("")
    lines += [
        f"Data și ora votării: {submitted_at.strftime('%d.%m.%Y %H:%M:%S UTC')}",
        "Consimțământ GDPR: acordat",
    ]
    return "\n".join(lines).rstrip()


def _ballot_html(election, voter, answers: dict, submitted_at: datetime) -> str:
    texts = build_ballot_texts(election, voter)
    rows = []
    for i, q in enumerate(_questions(election), start=1):
        rows.append(
            '<div style="margin:0 0 14px;padding:12px 14px;border:1px solid #e2e5ea;'
            'border-radius:8px;background:#fafbfc;">'
            f'<div style="font-weight:600;margin:0 0 6px;line-height:1.45;">{escape(question_label(q, i))}</div>'
            '<div style="margin:0;color:#2452b5;"><strong>Vot:</strong> '
            f'{escape(_answer_text(q, answers.get(q["id"])))}</div>'
            "</div>"
        )
    return (
        '<div style="margin:18px 0;padding:22px 24px;border:1px solid #e2e5ea;border-radius:10px;background:#ffffff;">'
        f'<h2 style="text-align:center;font-size:18px;line-height:1.4;margin:0 0 12px;">{escape(texts["title"])}</h2>'
        '<table role="presentation" width="100%" style="border-collapse:collapse;margin:0 0 16px;font-size:14px;">'
        '<tr>'
        f'<td align="left" style="padding:0;">{escape(texts["date_line"])}</td>'
        f'<td align="right" style="padding:0;">{escape(texts["city_line"])}</td>'
        "</tr></table>"
        f'<p style="margin:0 0 12px;font-size:14px;line-height:1.55;text-align:justify;">{escape(texts["paragraph1"])}</p>'
        f'<p style="margin:0 0 18px;font-size:14px;line-height:1.55;text-align:justify;">{escape(texts["paragraph2"])}</p>'
        + "".join(rows)
        + '<p style="margin:14px 0 0;font-size:13px;color:#6b7280;">'
        f"Data și ora votării: {escape(submitted_at.strftime('%d.%m.%Y %H:%M:%S UTC'))} · Consimțământ GDPR: acordat"
        "</p></div>"
    )


def _paragraphs(text: str) -> str:
    """Escaped text as HTML paragraphs: blank line = new paragraph, single line break = <br>."""
    out = []
    for block in text.split("\n\n"):
        block = block.strip()
        if block:
            out.append(
                '<p style="margin:0 0 12px;font-size:14px;line-height:1.55;">'
                + escape(block).replace("\n", "<br>")
                + "</p>"
            )
    return "".join(out)


def _delivery_note(attach_pdf: bool, receipt_url: str | None) -> tuple[str, str]:
    """(plain text, html) note about how the ballot PDF is delivered."""
    if attach_pdf:
        text = "Buletinul de vot completat și semnat este atașat acestui email (PDF)."
        return text, escape(text)
    if receipt_url:
        text = f"Buletinul de vot completat poate fi descărcat aici: {receipt_url}"
        html = (
            "Buletinul de vot completat poate fi descărcat accesând "
            f'<a href="{escape(receipt_url)}" style="color:#2452b5;">acest link</a>.'
        )
        return text, html
    return "", ""


def build_email_text(
    *,
    election,
    voter,
    answers: dict,
    submitted_at: datetime,
    body_template: str,
    values: dict,
    receipt_url: str | None = None,
    attach_pdf: bool = True,
) -> str:
    before, after = _split_template(body_template, values)
    ballot = _ballot_text(election, voter, answers, submitted_at)
    note, _ = _delivery_note(attach_pdf, receipt_url)
    parts = [p for p in [before, ballot, after, note] if p]
    return "\n\n".join(parts)


def build_email_html(
    *,
    election,
    voter,
    answers: dict,
    submitted_at: datetime,
    body_template: str,
    values: dict,
    receipt_url: str | None = None,
    attach_pdf: bool = True,
) -> str:
    before, after = _split_template(body_template, values)
    ballot = _ballot_html(election, voter, answers, submitted_at)
    _, note_html = _delivery_note(attach_pdf, receipt_url)
    note = f'<p style="margin:0;font-size:13px;color:#6b7280;">{note_html}</p>' if note_html else ""
    title = escape(values.get("election_title", ""))

    return f"""<!doctype html>
<html lang="ro">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1f2430;">
  <div style="max-width:680px;margin:0 auto;padding:28px 18px;">
    <div style="background:#ffffff;border:1px solid #e2e5ea;border-radius:12px;padding:28px 30px;">
      {_paragraphs(before)}
      {ballot}
      {_paragraphs(after)}
      {note}
    </div>
    <p style="text-align:center;font-size:12px;color:#9ca3af;margin:14px 0 0;">
      Acest mesaj a fost generat automat de sistemul de vot.
    </p>
  </div>
</body>
</html>"""
