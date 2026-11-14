import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, Text, DateTime, ForeignKey, Boolean, UniqueConstraint
)
from sqlalchemy.orm import relationship

from .database import Base


def utcnow():
    return datetime.now(timezone.utc)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    # True while the account still uses the initial/default password; the admin API refuses
    # all operations except /me and /change-password until the password is replaced.
    must_change_password = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)


class SmtpSettings(Base):
    """Singleton row (id=1) holding the SMTP configuration, editable from the admin panel."""
    __tablename__ = "smtp_settings"

    id = Column(Integer, primary_key=True, default=1)
    enabled = Column(Boolean, default=False)
    host = Column(String, default="")
    port = Column(Integer, default=587)
    username = Column(String, default="")
    password = Column(String, default="")  # stored as given; see README for securing this further
    from_email = Column(String, default="")
    from_name = Column(String, default="")  # unused: the sender name is always the APC number
    use_tls = Column(Boolean, default=True)
    subject_template = Column(String, default="Confirmare vot - {election_title}")
    body_template = Column(
        Text,
        default=(
            "Bună {voter_name},\n\n"
            "Votul dumneavoastră pentru \"{election_title}\" a fost înregistrat cu succes "
            "la data {submitted_at}.\n\n"
            "{buletin}\n\n"
            "Cu respect,\n{nr_apc}"
        ),
    )


class Election(Base):
    __tablename__ = "elections"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False, default="Vot")  # internal label, shown only in admin
    description = Column(Text, default="")  # internal admin note, not shown to voters

    # --- Fixed-legal-template variables (buletin de vot APC) -----------------
    nr_apc = Column(String, default="")               # nr. Asociației de Proprietari din Condominiu
    str_apc = Column(String, default="")              # adresa condominiului
    oras = Column(String, default="")                 # localitatea
    start_date_vot = Column(DateTime, nullable=True)  # data Adunării Generale cu prezență
    end_date_vot = Column(DateTime, nullable=True)    # termenul-limită de remitere a buletinului
    tip_proprietate = Column(String, default="apartament")

    # Chestiunea propusă spre vot: the text shown on the ballot above the questions
    chestiune = Column(Text, default="")

    # Properties (imobile) of this APC that owners can tick on the ballot:
    # [{"tip_proprietate": "apartament", "nr_proprietate": "12"}, ...]
    properties_json = Column(Text, default="[]")
    # True: an owner may vote several properties in one ballot. False: only one property per ballot.
    allow_multiple_properties = Column(Boolean, default=True)

    # Blocks / addresses of this APC (one APC can have several buildings). The owner picks one on the
    # ballot when there are two or more. ["str. A. Doga 13/7", "str. Cornești 7", ...]
    adrese_json = Column(Text, default="[]")
    # Blocks of the building (bl_apc), one per line in the admin. Empty = the owner types the block himself.
    blocuri_json = Column(Text, default="[]")

    # JSON-encoded list of decisions (Hotărâri) to vote on:
    # [{"id": "q1", "text": "...", "type": "single", "options": ["Da/Pro","Nu/Contra"], "required": true}]
    questions_json = Column(Text, default="[]")

    is_active = Column(Boolean, default=True)
    require_signature = Column(Boolean, default=True)

    # --- Public results dashboard ------------------------------------------
    # Random, unguessable identifier used by the public dashboard:
    # https://domeniu/{public_uuid}/dashboard
    public_uuid = Column(String, unique=True, index=True, default=lambda: uuid.uuid4().hex)
    # Secret link for the APC to prolong the vote (sent in the expiry reminders and the final email):
    # https://domeniu/extend/{extend_uuid}. Separate from public_uuid, so the dashboard link cannot prolong.
    extend_uuid = Column(String, unique=True, index=True, default=lambda: uuid.uuid4().hex)

    # --- Confirmation email options (per election) -------------------------
    email_with_attachment = Column(Boolean, default=True)  # False = send the email without the PDF
    email_cc = Column(String, default="")                  # optional copy addresses, comma separated
    email_bcc = Column(String, default="")                 # optional hidden copy addresses, comma separated

    # --- Results reports (per election) ------------------------------------
    results_email = Column(String, default="")             # APC address(es) receiving the results reports
    notify_results_on_vote = Column(Boolean, default=True)  # email updated results after every new vote
    results_final_email_sent_at = Column(DateTime, nullable=True)  # final report sent once, after end_date_vot
    # Expiry reminders to the APC (3, 2, 1 days before end_date_vot). Stores the end date they belong to,
    # so a prolonged vote (new end_date_vot) gets its reminders again: {"end": "...", "sent": [3, 2]}
    expiry_reminders_json = Column(Text, default="{}")

    # When the APC received the vote link and the dashboard link (sent from the admin, once all questions are in)
    links_email_sent_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    tokens = relationship("VoterToken", back_populates="election", cascade="all, delete-orphan")
    votes = relationship("Vote", back_populates="election", cascade="all, delete-orphan")

    @property
    def addresses(self) -> list[str]:
        """The blocks / addresses of the APC, in the order the admin typed them."""
        return _json_list(self.adrese_json)

    @property
    def blocks(self) -> list[str]:
        """The blocks (bl_apc) the owner can pick from. Empty = the owner writes the block himself."""
        return _json_list(self.blocuri_json)


def _json_list(raw: str | None) -> list[str]:
    try:
        items = json.loads(raw or "[]")
    except (ValueError, TypeError):
        return []
    return [str(i).strip() for i in items if str(i).strip()] if isinstance(items, list) else []


class VoterToken(Base):
    __tablename__ = "voter_tokens"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=False)

    # --- Per-owner data, entered by the voter on the fixed public link -------------
    nume_prenume = Column(String, default="")
    phone = Column(String, default="")
    str_locatar = Column(String, default="")   # adresa de corespondență poștală
    email = Column(String, default="")          # also used to send the confirmation + PDF

    # Primary property (kept for backward compatibility) and the full list of properties
    # covered by this vote: [{"tip_proprietate": "apartament", "nr_proprietate": "12"}, ...]
    tip_proprietate = Column(String, default="apartament")
    nr_proprietate = Column(String, default="")
    properties_json = Column(Text, default="[]")
    # The block / address the owner chose (empty when the APC has a single address)
    adresa = Column(String, default="")
    # The block (bl_apc) the owner chose or typed ("" when not given)
    bloc = Column(String, default="")

    created_at = Column(DateTime, default=utcnow)
    voted_at = Column(DateTime, nullable=True)

    election = relationship("Election", back_populates="tokens")
    vote = relationship("Vote", back_populates="token", uselist=False, cascade="all, delete-orphan")

    @property
    def has_voted(self) -> bool:
        return self.voted_at is not None

    @property
    def label(self) -> str:
        """Backward-compatible display label."""
        return self.nume_prenume or ""

    @property
    def properties(self) -> list[dict]:
        """All properties covered by this vote (backfilled from the legacy single field)."""
        try:
            items = json.loads(self.properties_json or "[]")
        except (ValueError, TypeError):
            items = []
        if not isinstance(items, list):
            items = []
        cleaned = []
        for item in items:
            if not isinstance(item, dict):
                continue
            tip = (item.get("tip_proprietate") or "").strip()
            nr = (item.get("nr_proprietate") or "").strip()
            bloc = (item.get("bloc") or "").strip()
            if tip or nr:
                cleaned.append({"tip_proprietate": tip or "apartament", "nr_proprietate": nr, "bloc": bloc})
        if not cleaned and self.nr_proprietate:
            cleaned = [{
                "tip_proprietate": self.tip_proprietate or "apartament",
                "nr_proprietate": self.nr_proprietate,
                "bloc": self.bloc or "",
            }]
        return cleaned


class VoterProperty(Base):
    """One property covered by a vote. The unique constraint guarantees that the same property
    (block/address + type + number) cannot be voted twice within the same election."""
    __tablename__ = "voter_properties"
    __table_args__ = (
        UniqueConstraint("election_id", "adresa", "bloc", "tip_proprietate", "nr_proprietate",
                         name="uq_voter_property_election"),
    )

    id = Column(Integer, primary_key=True)
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=False)
    token_id = Column(String, ForeignKey("voter_tokens.id"), nullable=False)
    adresa = Column(String, nullable=False, default="")  # address of the condominium ("" = single address)
    bloc = Column(String, nullable=False, default="")    # block ("" = none given)
    tip_proprietate = Column(String, nullable=False)  # apartament | debara | parcare
    nr_proprietate = Column(String, nullable=False)


class BallotTemplate(Base):
    """Singleton row (id=1): the editable text of the buletin de vot. Empty fields are not used;
    a missing row means the default text (see ballot_template.py)."""
    __tablename__ = "ballot_template"

    id = Column(Integer, primary_key=True, default=1)
    title = Column(Text, nullable=True)
    paragraph1 = Column(Text, nullable=True)
    paragraph2 = Column(Text, nullable=True)
    note = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class EmailLog(Base):
    """Every email the system sends for an election: who sent it, to whom, and the headers."""
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True)
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow)
    kind = Column(String, default="")          # confirmare vot | raport rezultate | reamintire expirare | ...
    status = Column(String, default="")        # trimis | eșuat
    info = Column(Text, default="")            # SMTP answer or error reason
    from_addr = Column(String, default="")
    to_addr = Column(String, default="")
    cc = Column(String, default="")
    bcc = Column(String, default="")
    subject = Column(String, default="")
    headers = Column(Text, default="")
    attachment = Column(String, default="")
    preview = Column(Text, default="")


class Vote(Base):
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True)
    token_id = Column(String, ForeignKey("voter_tokens.id"), unique=True, nullable=False)
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=False)
    answers_json = Column(Text, default="{}")
    signature_path = Column(String, nullable=True)
    receipt_pdf_path = Column(String, nullable=True)
    email_sent = Column(Boolean, default=False)
    gdpr_consent_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, default=utcnow)
    ip_address = Column(String, default="")

    token = relationship("VoterToken", back_populates="vote")
    election = relationship("Election", back_populates="votes")
