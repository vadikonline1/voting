"""The editable text of the buletin de vot (title and paragraphs) and the variables it can use.

The admin edits the four parts on the page "Șablon buletin". Variables written in braces, for example
{nr_apc} or {voter_name}, are filled automatically from the vote and the owner's ballot. Unknown
variables stay visible as they are, so a typo is easy to spot in the preview."""
from datetime import datetime

from . import models
from .config import settings

PLACEHOLDER = "…………………"
FIELDS = ("title", "paragraph1", "paragraph2", "note")

# The text used until the admin changes it (the legal wording of the APC ballot).
DEFAULT_TEMPLATE = {
    "title": (
        "Buletin de VOT, al Adunării Generale Mixte a membrilor APC nr. {nr_apc}, {str_apc}, "
        "din data de {start_date_long} {oras}"
    ),
    "paragraph1": (
        "În conformitate cu prevederile art. 41, al Legii nr. 187 din 14.07.2022, cu privire la condominiu, "
        "se emite buletinul de vot, necesar pentru primirea deciziilor asupra chestiunilor propuse spre vot, "
        "care urmează a fi completat de fiecare membru al Asociației de Proprietari din Condominiu nr. {nr_apc} "
        "și transmis către APC nr. {nr_apc} până la data de {end_date_long}, fizic, online pe adresa "
        "https://exfactormcb41.md/buletin-de-vot-2026/, și/sau la adresa electronică: {email_apc}, "
        "inclusiv, după cum urmează:"
    ),
    "paragraph2": (
        "Dl/Dna. {voter_name}, tel.{voter_phone}, {adresa_bloc}, adresa de email {voter_email}, "
        "{imobile}, îmi exprim acordul și votul pentru adoptarea următoarelor decizii:"
    ),
    "note": (
        "Notă: (în cazul deținerii mai multor unități, se completează pentru fiecare câte un buletin de vot). "
        "Proprietarii care dețin doar alte încăperi decât apartamente, își vor expune opțiunea de vot doar la "
        "rubricile din buletin, în măsura în care sunt vizați)."
    ),
}

# (variable, what it is, example shown in the admin before a vote exists)
VARIABLES = [
    ("nr_apc", "Numărul APC", "12"),
    ("election_title", "Titlul votului (intern)", "Adunare generală 2026"),
    ("str_apc", "Adresele condominiului (toate, separate prin „; ”)", "str. A. Doga 13/7; str. Cornești 7"),
    ("oras", "Localitatea", "Chișinău"),
    ("start_date", "Data Adunării cu prezență (zz.ll.aaaa)", "31.10.2026"),
    ("start_date_long", "Data Adunării cu prezență, scrisă", "31 octombrie 2026"),
    ("end_date", "Termenul de remitere a buletinului (zz.ll.aaaa)", "25.11.2026"),
    ("end_date_long", "Termenul de remitere, scris", "25 noiembrie 2026"),
    ("email_apc", "Adresa electronică a APC (rezultate)", "apc@exemplu.md"),
    ("vote_url", "Linkul fix de vot al APC", "https://vot.exemplu.md/12"),
    ("dashboard_url", "Linkul dashboard-ului cu rezultate", "https://vot.exemplu.md/<uuid>/dashboard"),
    ("adresa", "Adresa condominiului aleasă de votant", "str. Cornești 7"),
    ("bloc", "Blocul votantului", "E"),
    ("adresa_bloc", "Adresa și blocul votantului, ex. „str. X, blocul E”", "str. Cornești 7, blocul E"),
    ("imobile", "Imobilele votantului, ex. „apartament 803/E, debara 4”", "apartament 803/E"),
    ("voter_name", "Numele și prenumele votantului", "Ion Popescu"),
    ("voter_phone", "Telefonul votantului", "+373 60 000 000"),
    ("voter_email", "Emailul votantului", "votant@exemplu.md"),
    ("voter_address", "Adresa de corespondență a votantului", "str. Exemplu 1, ap. 2"),
    ("submitted_at", "Data și ora votului (UTC)", "14.11.2026 10:30:00 UTC"),
    ("submitted_date", "Data votului (zz.ll.aaaa)", "14.11.2026"),
]

_MONTHS = [
    "ianuarie", "februarie", "martie", "aprilie", "mai", "iunie",
    "iulie", "august", "septembrie", "octombrie", "noiembrie", "decembrie",
]


class _Safe(dict):
    """Unknown {variables} stay visible instead of raising an error."""

    def __missing__(self, key):
        return "{" + key + "}"


def render(text: str, values: dict) -> str:
    return (text or "").format_map(_Safe(values))


def _date(dt: datetime | None, long: bool = False) -> str:
    if not dt:
        return PLACEHOLDER
    if long:
        return f"{dt.day} {_MONTHS[dt.month - 1]} {dt.year}"
    return dt.strftime("%d.%m.%Y")


def _imobile(election, voter) -> str:
    if voter is None:
        return f"{election.tip_proprietate or 'apartament'} {PLACEHOLDER}"
    props = voter.properties
    if not props:
        return f"{election.tip_proprietate or 'apartament'} {PLACEHOLDER}"
    return ", ".join(f"{p['tip_proprietate']} {p['nr_proprietate']}" for p in props)


def template_values(election, voter=None, submitted_at: datetime | None = None) -> dict:
    """Every variable with its value for this election and (optionally) this owner's ballot.
    Without an owner (the blank ballot) the owner's fields are placeholders."""
    addresses = election.addresses
    str_apc = "; ".join(addresses) if addresses else (election.str_apc or PLACEHOLDER)
    if voter is None:
        # blank ballot: the owner's own fields stay as placeholders to be filled by hand
        adresa, bloc, adresa_bloc = PLACEHOLDER, "", PLACEHOLDER
    else:
        # the address the owner chose (or the only address of the APC), and the block he wrote or picked
        adresa = (getattr(voter, "adresa", "") or "") or (addresses[0] if addresses else str_apc)
        bloc = getattr(voter, "bloc", "") or ""
        adresa_bloc = f"{adresa}, blocul {bloc}" if bloc else adresa

    public_base = _public_base()
    values = {
        "nr_apc": election.nr_apc or PLACEHOLDER,
        "election_title": election.title or PLACEHOLDER,
        "str_apc": str_apc,
        "oras": election.oras or PLACEHOLDER,
        "start_date": _date(election.start_date_vot),
        "start_date_long": _date(election.start_date_vot, long=True),
        "end_date": _date(election.end_date_vot),
        "end_date_long": _date(election.end_date_vot, long=True),
        "email_apc": (election.results_email or "").strip() or PLACEHOLDER,
        "vote_url": f"{public_base}/{election.nr_apc}" if election.nr_apc else PLACEHOLDER,
        "dashboard_url": (
            f"{public_base}/{election.public_uuid}/dashboard" if election.public_uuid else PLACEHOLDER
        ),
        "adresa": adresa,
        "bloc": bloc or PLACEHOLDER,
        "adresa_bloc": adresa_bloc,
        "imobile": _imobile(election, voter),
        "voter_name": (getattr(voter, "nume_prenume", "") or "") or PLACEHOLDER,
        "voter_phone": (getattr(voter, "phone", "") or "") or PLACEHOLDER,
        "voter_email": (getattr(voter, "email", "") or "") or PLACEHOLDER,
        "voter_address": (getattr(voter, "str_locatar", "") or "") or PLACEHOLDER,
        "submitted_at": submitted_at.strftime("%d.%m.%Y %H:%M:%S UTC") if submitted_at else PLACEHOLDER,
        "submitted_date": _date(submitted_at),
    }
    return values


def _public_base() -> str:
    return settings.public_base_url.rstrip("/")


def load_template(db) -> dict:
    """The saved text, or the default text when the admin has not saved one yet."""
    row = db.query(models.BallotTemplate).get(1) if db is not None else None
    if row is None:
        return dict(DEFAULT_TEMPLATE)
    return {f: DEFAULT_TEMPLATE[f] if getattr(row, f) is None else getattr(row, f) for f in FIELDS}


def save_template(db, data: dict) -> dict:
    row = db.query(models.BallotTemplate).get(1)
    if row is None:
        row = models.BallotTemplate(id=1)
        db.add(row)
    for field in FIELDS:
        setattr(row, field, data.get(field) or "")
    row.updated_at = datetime.utcnow()
    db.commit()
    return load_template(db)
