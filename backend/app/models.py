import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, Text, DateTime, ForeignKey, Boolean
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
    from_name = Column(String, default="Comisia Electorală")
    use_tls = Column(Boolean, default=True)
    subject_template = Column(String, default="Confirmare vot - {election_title}")
    body_template = Column(
        Text,
        default=(
            "Bună {voter_name},\n\n"
            "Votul dumneavoastră pentru \"{election_title}\" a fost înregistrat cu succes "
            "la data {submitted_at}.\n\n"
            "Buletinul de vot completat și semnat este atașat acestui email, în format PDF.\n\n"
            "Cu respect,\nComisia Electorală"
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

    # JSON-encoded list of decisions (Hotărâri) to vote on:
    # [{"id": "q1", "text": "...", "type": "single", "options": ["Da/Pro","Nu/Contra"], "required": true}]
    questions_json = Column(Text, default="[]")

    is_active = Column(Boolean, default=True)
    require_signature = Column(Boolean, default=True)

    # --- Public results dashboard ------------------------------------------
    # Random, unguessable identifier used by the public dashboard:
    # https://domeniu/{public_uuid}/dashboard
    public_uuid = Column(String, unique=True, index=True, default=lambda: uuid.uuid4().hex)

    # --- Confirmation email options (per election) -------------------------
    email_with_attachment = Column(Boolean, default=True)  # False = send the email without the PDF
    email_cc = Column(String, default="")                  # optional copy addresses, comma separated
    email_bcc = Column(String, default="")                 # optional hidden copy addresses, comma separated

    # --- Results reports (per election) ------------------------------------
    results_email = Column(String, default="")             # APC address(es) receiving the results reports
    notify_results_on_vote = Column(Boolean, default=True)  # email updated results after every new vote
    results_final_email_sent_at = Column(DateTime, nullable=True)  # final report sent once, after end_date_vot

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    tokens = relationship("VoterToken", back_populates="election", cascade="all, delete-orphan")
    votes = relationship("Vote", back_populates="election", cascade="all, delete-orphan")


class VoterToken(Base):
    __tablename__ = "voter_tokens"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=False)

    # --- Per-owner data, filled in by the admin when the link is generated ---
    nume_prenume = Column(String, default="")
    phone = Column(String, default="")
    str_locatar = Column(String, default="")   # adresa de corespondență poștală
    email = Column(String, default="")          # also used to send the confirmation + PDF
    nr_proprietate = Column(String, default="")  # nr. unității (bunului imobil)

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
