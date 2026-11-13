"""Builds the vote-confirmation email content (plain text + HTML) from the same fixed legal
text used by the web ballot and the PDF, so the wording can never diverge."""
import json
from datetime import datetime
from html import escape

from .ballot_text import build_ballot_texts, question_label


def _answer_text(question: dict, answer) -> str:
    if question.get("type") == "multiple" and isinstance(answer, list):
        return ", ".join(str(a) for a in answer) if answer else "(fără răspuns)"
    if answer in (None, "", []):
        return "(fără răspuns)"
    return str(answer)


def _questions(election) -> list:
    return json.loads(election.questions_json or "[]")


def _votes_text(election, answers: dict) -> str:
    lines = []
    for i, q in enumerate(_questions(election), start=1):
        lines.append(question_label(q, i))
        lines.append(f"Vot: {_answer_text(q, answers.get(q['id']))}")
        lines.append("")
    return "\n".join(lines).rstrip()


def build_email_text(
    *,
    election,
    voter,
    answers: dict,
    submitted_at: datetime,
    intro_text: str = "",
    receipt_url: str | None = None,
    attach_pdf: bool = True,
) -> str:
    texts = build_ballot_texts(election, voter)
    parts = []
    if intro_text:
        parts += [intro_text.strip(), ""]

    parts += [
        texts["title"],
        f"{texts['date_line']}                                    {texts['city_line']}",
        "",
        texts["paragraph1"],
        "",
        texts["paragraph2"],
        "",
        _votes_text(election, answers),
        "",
        f"Data și ora votării: {submitted_at.strftime('%d.%m.%Y %H:%M:%S UTC')}",
        "Consimțământ GDPR: acordat",
    ]
    if attach_pdf:
        parts.append("Buletinul de vot completat și semnat este atașat acestui email (PDF).")
    elif receipt_url:
        parts.append(f"Buletinul de vot completat poate fi descărcat aici: {receipt_url}")
    return "\n".join(parts)


def build_email_html(
    *,
    election,
    voter,
    answers: dict,
    submitted_at: datetime,
    intro_text: str = "",
    receipt_url: str | None = None,
    attach_pdf: bool = True,
) -> str:
    texts = build_ballot_texts(election, voter)
    intro_html = ""
    if intro_text:
        intro_html = (
            '<p style="margin:0 0 18px;font-size:15px;line-height:1.55;">'
            + escape(intro_text.strip()).replace("\n", "<br>")
            + "</p>"
        )

    rows = []
    for i, q in enumerate(_questions(election), start=1):
        rows.append(
            '<div style="margin:0 0 14px;padding:12px 14px;border:1px solid #e2e5ea;'
            'border-radius:8px;background:#fafbfc;">'
            f'<div style="font-weight:600;margin:0 0 6px;line-height:1.45;">{escape(question_label(q, i))}</div>'
            f'<div style="margin:0;color:#2452b5;"><strong>Vot:</strong> '
            f'{escape(_answer_text(q, answers.get(q["id"])))}</div>'
            "</div>"
        )

    if attach_pdf:
        delivery_note = (
            "Buletinul de vot completat și semnat este atașat acestui email, în format PDF."
        )
    elif receipt_url:
        delivery_note = (
            'Buletinul de vot completat poate fi descărcat accesând '
            f'<a href="{escape(receipt_url)}" style="color:#2452b5;">acest link</a>.'
        )
    else:
        delivery_note = ""

    return f"""<!doctype html>
<html lang="ro">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1f2430;">
  <div style="max-width:680px;margin:0 auto;padding:28px 18px;">
    <div style="background:#ffffff;border:1px solid #e2e5ea;border-radius:12px;padding:28px 30px;">
      {intro_html}
      <h2 style="text-align:center;font-size:19px;line-height:1.4;margin:0 0 12px;">{escape(texts['title'])}</h2>
      <table role="presentation" width="100%" style="border-collapse:collapse;margin:0 0 18px;font-size:14px;">
        <tr>
          <td align="left" style="padding:0;">{escape(texts['date_line'])}</td>
          <td align="right" style="padding:0;">{escape(texts['city_line'])}</td>
        </tr>
      </table>
      <p style="margin:0 0 12px;font-size:14px;line-height:1.55;text-align:left;">{escape(texts['paragraph1'])}</p>
      <p style="margin:0 0 20px;font-size:14px;line-height:1.55;text-align:left;">{escape(texts['paragraph2'])}</p>
      {''.join(rows)}
      <p style="margin:16px 0 6px;font-size:13px;color:#6b7280;">
        Data și ora votării: {escape(submitted_at.strftime('%d.%m.%Y %H:%M:%S UTC'))} · Consimțământ GDPR: acordat
      </p>
      {f'<p style="margin:0;font-size:13px;color:#6b7280;">{delivery_note}</p>' if delivery_note else ''}
    </div>
    <p style="text-align:center;font-size:12px;color:#9ca3af;margin:14px 0 0;">
      Acest mesaj a fost generat automat de sistemul de vot.
    </p>
  </div>
</body>
</html>"""
