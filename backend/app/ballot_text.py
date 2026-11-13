"""Single source of truth for the fixed legal ballot text (buletin de vot APC), so the
web page and the generated PDF always show exactly the same wording. Only the bracketed
variables change; everything else is fixed legal text."""
from datetime import datetime

PLACEHOLDER = "…………………"


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
    nr_proprietate = (voter.nr_proprietate if voter else "") or PLACEHOLDER

    paragraph2 = (
        f"Dl/Dna {nume_prenume}, tel. {phone}, adresa de corespondență poștală "
        f"{str_locatar}, adresa electronică {email}, în calitate de membru al "
        f"Asociației de Proprietari din Condominiu nr. {nr_apc}, proprietar al unității (bunului "
        f"imobil) din: {str_apc}, {tip_proprietate} cu nr {nr_proprietate}, îmi exprim votul "
        "(Da/Pro, Nu/Contra) pentru adoptarea următoarelor Hotărâri:"
    )

    return {
        "title": title,
        "date_line": start_date_vot,
        "city_line": oras,
        "paragraph1": paragraph1,
        "paragraph2": paragraph2,
    }
