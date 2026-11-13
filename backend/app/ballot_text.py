"""Single source of truth for the fixed legal ballot text (buletin de vot APC), used by the
generated PDF and the confirmation email. Only the bracketed variables change; everything
else is fixed legal text. The web voting page intentionally does not display these paragraphs."""
from datetime import datetime

PLACEHOLDER = "…………………"

GDPR_TEXT = (
    "Accept prelucrarea datelor mele cu caracter personal (nume și prenume, telefon, "
    "adresă de corespondență, adresă electronică și numărul unității) în scopul exclusiv "
    "al organizării și desfășurării acestei votări, în conformitate cu Regulamentul (UE) "
    "2016/679 (GDPR). Datele nu sunt folosite în alte scopuri și nu sunt transmise unor terți."
)


def question_letter(index: int) -> str:
    """1 -> a, 2 -> b, ... (numbers beyond z stay numeric)."""
    return chr(96 + index) if 1 <= index <= 26 else str(index)


def question_label(question: dict, index: int) -> str:
    """Display label for a question: 'a. text' by default, or the number the admin typed."""
    number = str(question.get("number") or "").strip() or question_letter(index)
    return f"{number}. {question.get('text', '').strip()}"



def format_date_ro(dt: datetime | None) -> str:
    if not dt:
        return PLACEHOLDER
    return dt.strftime("%d.%m.%Y")


def build_ballot_texts(election, voter) -> dict:
    nr_apc = election.nr_apc or PLACEHOLDER
    str_apc = election.str_apc or PLACEHOLDER
    oras = election.oras or PLACEHOLDER
    tip_proprietate = election.tip_proprietate or "apartament"
    start_date_vot = format_date_ro(election.start_date_vot)
    end_date_vot = format_date_ro(election.end_date_vot)

    title = f"Buletin de VOT, al Adunării Generale Mixte a membrilor APC nr. {nr_apc}, din {str_apc}"

    paragraph1 = (
        "În conformitate cu prevederile art. 41 alin. (1), (2), al Legii nr. 187 din 14.07.2022 cu "
        "privire la condominiu, se emite buletinul de vot, necesar pentru primirea deciziilor asupra "
        "chestiunilor propuse spre vot, care urmează a fi completat (de către membrii asociației ce nu au "
        f"fost prezenți la Adunarea Generală cu prezență din data de {start_date_vot}) și remis către APC "
        f"nr. {nr_apc} până la data de {end_date_vot} inclusiv, după cum urmează:"
    )

    nume_prenume = (voter.nume_prenume if voter else "") or PLACEHOLDER
    phone = (voter.phone if voter else "") or PLACEHOLDER
    str_locatar = (voter.str_locatar if voter else "") or PLACEHOLDER
    email = (voter.email if voter else "") or PLACEHOLDER
    props = voter.properties if voter else []
    if props:
        props_text = ", ".join(f"{p['tip_proprietate']} cu nr {p['nr_proprietate']}" for p in props)
    else:
        props_text = f"{tip_proprietate} cu nr {PLACEHOLDER}"

    paragraph2 = (
        f"Dl/Dna {nume_prenume}, tel. {phone}, adresa de corespondență poștală "
        f"{str_locatar}, adresa electronică {email}, în calitate de membru al "
        f"Asociației de Proprietari din Condominiu nr. {nr_apc}, proprietar al unității (bunului "
        f"imobil) din: {str_apc}, {props_text}, îmi exprim votul "
        "(Da/Pro, Nu/Contra) pentru adoptarea următoarelor Hotărâri:"
    )

    return {
        "title": title,
        "date_line": start_date_vot,
        "city_line": oras,
        "paragraph1": paragraph1,
        "paragraph2": paragraph2,
    }
