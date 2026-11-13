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


class ElectionIn(BaseModel):
    title: str
    description: str = ""
    nr_apc: str = ""
    str_apc: str = ""
    oras: str = ""
    start_date_vot: Optional[datetime] = None
    end_date_vot: Optional[datetime] = None
    tip_proprietate: str = "apartament"
    questions: List[Question] = Field(default_factory=list)
    is_active: bool = True
    require_signature: bool = True
    email_with_attachment: bool = True
    email_cc: str = ""
    email_bcc: str = ""


class ElectionOut(ElectionIn):
    id: int
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


class VoteSubmission(BaseModel):
    answers: Dict[str, Any] = Field(default_factory=dict)
    voter: VoterData = Field(default_factory=VoterData)
    gdpr_consent: bool = False
    signature_png_base64: Optional[str] = None


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
