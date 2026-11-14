from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


class Question(BaseModel):
    id: str
    number: str = ""  # display number, e.g. "1", "2", "3.a" (empty -> fallback to position)
    text: str
    type: str = "single"  # "single" | "multiple"
    options: List[str] = Field(default_factory=lambda: ["Pentru", "Împotriva"])
    required: bool = True

    # Conditional logic: if the answer to `depends_on` equals `depends_value`,
    # this question is disabled and automatically receives `auto_answer`.
    depends_on: Optional[str] = None
    depends_value: Optional[str] = None
    auto_answer: Optional[str] = None

    # Only on a chestiune (type "section"): one "Pentru" (options[0]) in the group makes every other
    # question of the same chestiune automatically "Împotriva" (options[-1]).
    exclusive: bool = False

    # Only on a chestiune (type "section"): show it (and its questions) only to owners who selected
    # a property of this type, e.g. "parcare". Empty = shown to everyone.
    property_type: str = ""

    # Hidden from the voters (not on the ballot, the PDF, the email or the results). Kept in the admin.
    hidden: bool = False


class PropertyItem(BaseModel):
    tip_proprietate: str = "apartament"  # apartament | debara | parcare
    nr_proprietate: str = ""
    bloc: str = ""  # blocul imobilului (fiecare imobil poate fi în alt bloc)
    adresa: str = ""  # adresa condominiului în care se află imobilul (dacă APC are mai multe)


class ElectionIn(BaseModel):
    title: str
    description: str = ""
    nr_apc: str = ""
    str_apc: str = ""
    oras: str = ""
    start_date_vot: Optional[datetime] = None
    end_date_vot: Optional[datetime] = None
    tip_proprietate: str = "apartament"
    properties: List[PropertyItem] = Field(default_factory=list)
    allow_multiple_properties: bool = True
    chestiune: str = ""  # Chestiunea propusă spre vot
    adrese: List[str] = Field(default_factory=list)  # adresele condominiului (str_apc), una pe rând în admin
    blocuri: List[str] = Field(default_factory=list)  # blocurile (bl_apc), una pe rând; gol = votantul scrie blocul
    questions: List[Question] = Field(default_factory=list)
    is_active: bool = True
    require_signature: bool = True
    email_with_attachment: bool = True
    email_cc: str = ""
    email_bcc: str = ""
    results_email: str = ""
    notify_results_on_vote: bool = True


class ElectionOut(ElectionIn):
    id: int
    public_uuid: str = ""
    vote_url: str = ""  # PUBLIC_BASE_URL/{nr_apc}
    extend_url: str = ""  # secret link for the APC to prolong the vote (sent by email)
    created_at: datetime
    updated_at: datetime


class VoterData(BaseModel):
    nume_prenume: str = ""
    phone: str = ""
    str_locatar: str = ""
    email: str = ""
    nr_proprietate: str = ""


class BallotPublicOut(BaseModel):
    """What an anonymous voter sees when opening /{uuid}."""
    title: str
    date_line: str
    city_line: str
    paragraph1: str
    paragraph2: str
    gdpr_text: str
    voter: VoterData
    questions: List[Question]
    require_signature: bool
    already_voted: bool
    is_open: bool
    status: str  # "open" | "closed" | "voted"


class ApcBallotOut(BaseModel):
    """What an owner sees on the fixed public link /{nr_apc}."""
    nr_apc: str
    title: str
    date_line: str
    city_line: str
    gdpr_text: str
    properties: List[PropertyItem]
    allow_multiple_properties: bool
    adrese: List[str] = Field(default_factory=list)  # adresele condominiului; votantul alege una dacă sunt mai multe
    blocuri: List[str] = Field(default_factory=list)  # blocurile; votantul alege din listă sau scrie blocul
    chestiune: str = ""
    questions: List[Question]
    require_signature: bool
    is_open: bool
    status: str  # "open" | "closed"


class VoteSubmission(BaseModel):
    answers: Dict[str, Any] = Field(default_factory=dict)
    voter: VoterData = Field(default_factory=VoterData)
    adresa: str = ""  # adresa condominiului aleasă de votant (obligatorie dacă APC are mai multe)
    bloc: str = ""  # blocul ales din listă sau scris de votant
    properties: List[PropertyItem] = Field(default_factory=list)  # imobilele votate de proprietar
    gdpr_consent: bool = False
    signature_png_base64: Optional[str] = None


class BallotTemplateIn(BaseModel):
    """The editable parts of the buletin de vot (variables in braces, e.g. {nr_apc})."""
    title: str = ""
    paragraph1: str = ""
    paragraph2: str = ""
    note: str = ""


class ClearAllIn(BaseModel):
    confirm: str = ""  # must be the exact words shown in the admin, e.g. "STERGE TOT"


class BallotPreviewIn(BallotTemplateIn):
    election_id: Optional[int] = None  # the vote whose data fills the variables in the preview


class AdminLogin(BaseModel):
    username: str
    password: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


class VoterRow(BaseModel):
    nume_prenume: str = ""
    phone: str = ""
    str_locatar: str = ""
    email: str = ""
    nr_proprietate: str = ""


class TokenGenerateRequest(BaseModel):
    election_id: int
    rows: Optional[List[VoterRow]] = None  # one token per row, with that owner's data pre-filled
    count: int = 0  # fallback: generate this many *blank* tokens, to be filled in later


class VoterTokenOut(BaseModel):
    id: str
    nume_prenume: str
    phone: str
    str_locatar: str
    email: str
    nr_proprietate: str
    url: str


class VoterTokenUpdate(BaseModel):
    nume_prenume: Optional[str] = None
    phone: Optional[str] = None
    str_locatar: Optional[str] = None
    email: Optional[str] = None
    nr_proprietate: Optional[str] = None


class SmtpSettingsIn(BaseModel):
    enabled: bool = False
    host: str = ""
    port: int = 587
    username: str = ""
    password: Optional[str] = None  # None = keep existing password unchanged
    from_email: str = ""
    from_name: str = "Comisia Electorală"
    use_tls: bool = True
    subject_template: Optional[str] = None
    body_template: Optional[str] = None


class SmtpSettingsOut(BaseModel):
    enabled: bool
    host: str
    port: int
    username: str
    has_password: bool
    from_email: str
    from_name: str
    use_tls: bool
    subject_template: str
    body_template: str
    env_managed: bool = False  # True when SMTP_HOST is set: connection fields come from .env
