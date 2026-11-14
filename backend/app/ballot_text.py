"""Single source of truth for the fixed legal ballot text (buletin de vot APC), used by the
generated PDF and the confirmation email. Only the bracketed variables change; everything
else is fixed legal text. The web voting page intentionally does not display these paragraphs."""
import re
from datetime import datetime

from .ballot_template import DEFAULT_TEMPLATE, FIELDS, PLACEHOLDER, render, template_values
from .tz import format_day

GDPR_TEXT = (
    "Accept prelucrarea datelor mele cu caracter personal (nume și prenume, telefon, "
    "adresă de corespondență, adresă electronică și numărul unității) în scopul exclusiv "
    "al organizării și desfășurării acestei votări, în conformitate cu Regulamentul (UE) "
    "2016/679 (GDPR). Datele nu sunt folosite în alte scopuri și nu sunt transmise unor terți."
)


def question_letter(index: int) -> str:
    """1 -> a, 2 -> b, ... (numbers beyond z stay numeric)."""
    return chr(96 + index) if 1 <= index <= 26 else str(index)


def public_questions(questions: list) -> list:
    """What voters see and vote on: everything except the items hidden in the admin."""
    return [q for q in questions if not q.get("hidden")]


def labelled_questions(questions: list) -> list:
    """[(question, label)] in order. A "section" item is a chestiune (label None); the questions
    after it are lettered a, b, c… again, so each chestiune starts from a."""
    out = []
    counter = 0
    for q in questions:
        if q.get("type") == "section":
            counter = 0
            out.append((q, None))
            continue
        counter += 1
        label = str(q.get("number") or "").strip() or question_letter(counter)
        out.append((q, label))
    return out


def question_label(question: dict, index: int) -> str:
    """Display label for a question: 'a. text' by default, or the number the admin typed."""
    number = str(question.get("number") or "").strip() or question_letter(index)
    return f"{number}. {question.get('text', '').strip()}"



def format_date_ro(dt: datetime | None) -> str:
    text = format_day(dt)
    return text if text else PLACEHOLDER


def build_ballot_texts(election, voter, template: dict | None = None, submitted_at=None) -> dict:
    """The four parts of the ballot, rendered from the admin's text (ballot_template.py).
    The date/city keys are kept for the voting page."""
    tpl = template or DEFAULT_TEMPLATE
    values = template_values(election, voter, submitted_at)
    texts = {field: render(tpl.get(field) or "", values) for field in FIELDS}
    if voter is None:
        # blank ballot: an unknown address leaves no empty part in the title ("nr. X, , din" -> "nr. X, din")
        texts["title"] = re.sub(r",\s*,", ",", texts["title"])
    texts["date_line"] = format_date_ro(election.start_date_vot)
    texts["city_line"] = election.oras or PLACEHOLDER
    return texts
