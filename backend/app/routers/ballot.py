"""Public voting endpoints on the fixed link /{nr_apc}. No per-owner links exist: the owner
enters their own data, ticks the properties (imobile) they own and votes once per property."""
import base64
import json
import os
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..ballot_text import GDPR_TEXT, build_ballot_texts, PLACEHOLDER
from ..config import settings
from ..database import get_db
from ..email_html import build_email_html, build_email_text
from ..email_utils import mask_email, render_template, send_confirmation_email
from ..notifications import send_results_after_vote
from ..pdf import generate_receipt_pdf
from ..results import election_status
from ..smtp_config import get_smtp

router = APIRouter(prefix="/api/ballot", tags=["ballot"])

_NAME_RE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿĀ-ž' .\-]+$")
_PHONE_RE = re.compile(r"^\+?[0-9][0-9 ()\-.]{5,19}$")
_PROP_RE = re.compile(r"^[0-9A-Za-zÀ-ÖØ-öø-ÿĀ-ž/ .\-]+$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
PROPERTY_TYPES = ("apartament", "debara", "parcare")

VOTER_FIELDS = ("nume_prenume", "phone", "str_locatar", "email")


def _now():
    return datetime.now(timezone.utc)


def _active_election(db: Session, nr_apc: str) -> models.Election:
    election = (
        db.query(models.Election)
        .filter(models.Election.nr_apc == nr_apc.strip(), models.Election.is_active.is_(True))
        .order_by(models.Election.id.desc())
        .first()
    )
    if not election:
        raise HTTPException(status_code=404, detail="Nu există un vot activ pentru acest APC.")
    return election


def _election_property_types(election: models.Election) -> list[str]:
    """Property types the APC allows (apartament, debara, parcare, or custom ones).
    The owner types the number of each property on the ballot."""
    try:
        items = json.loads(election.properties_json or "[]")
    except (ValueError, TypeError):
        items = []
    types: list[str] = []
    for item in items if isinstance(items, list) else []:
        tip = str(item.get("tip_proprietate", "") if isinstance(item, dict) else item).strip().lower()
        if tip and tip not in types:
            types.append(tip)
    return types


# ------------------------------------------------------------- voting logic --
def _is_positive(question: dict, value) -> bool:
    options = question.get("options") or []
    return bool(options) and isinstance(value, str) and value == str(options[0])


def _exclusive_forced(questions: list, answers: dict) -> dict:
    """Questions forced by an exclusive chestiune: if one question of the group is "Pentru",
    the others of the same chestiune get their last option ("Împotriva") automatically."""
    groups: list[tuple[bool, list]] = []
    current: list = []
    exclusive = False
    for q in questions:
        if q.get("type") == "section":
            if current:
                groups.append((exclusive, current))
            current, exclusive = [], bool(q.get("exclusive"))
            continue
        current.append(q)
    if current:
        groups.append((exclusive, current))

    forced: dict = {}
    for is_exclusive, group in groups:
        if not is_exclusive or len(group) < 2:
            continue
        winners = [q for q in group if _is_positive(q, answers.get(q.get("id")))]
        if not winners:
            continue
        winner_id = winners[0].get("id")
        for q in group:
            options = q.get("options") or []
            if q.get("id") != winner_id and options:
                forced[q.get("id")] = str(options[-1])
    return forced


def _resolve_answers(questions: list, answers: dict) -> tuple[dict, dict]:
    """Apply question dependencies (see README): a dependent question gets `auto_answer`
    when its parent's effective answer equals `depends_value`. Exclusive chestiuni force the rest."""
    effective: dict = {}
    auto: dict = {}
    forced_exclusive = _exclusive_forced(questions, answers)
    for q in questions:
        qid = q.get("id")
        if q.get("type") == "section":
            continue
        if qid in forced_exclusive:
            effective[qid] = forced_exclusive[qid]
            auto[qid] = forced_exclusive[qid]
            continue
        triggered = False
        parent = q.get("depends_on")
        if parent:
            parent_answer = effective.get(parent)
            if parent_answer not in (None, "", []):
                triggered = str(parent_answer) == str(q.get("depends_value"))
        if triggered:
            options = q.get("options") or []
            forced = str(q.get("auto_answer") or (options[-1] if options else ""))
            effective[qid] = forced
            auto[qid] = forced
        else:
            effective[qid] = answers.get(qid)
    return effective, auto


def _validate_answers(questions: list, effective: dict, auto: dict) -> None:
    for q in questions:
        if q.get("type") == "section":
            continue  # chestiune title, nothing to answer
        qid = q.get("id")
        if qid in auto:
            continue
        value = effective.get(qid)
        options = q.get("options") or []
        label = f"{q.get('number') or ''}. {q.get('text', '')}".strip(". ").strip()

        if value in (None, "", []):
            if q.get("required", True):
                raise HTTPException(
                    status_code=400,
                    detail=f'Răspunsul la întrebarea „{label}” este obligatoriu.',
                )
            continue

        if q.get("type") == "multiple":
            if not isinstance(value, list) or any(str(v) not in options for v in value):
                raise HTTPException(status_code=400, detail=f'Răspuns invalid la întrebarea „{label}”.')
        elif str(value) not in options:
            raise HTTPException(status_code=400, detail=f'Răspuns invalid la întrebarea „{label}”.')


def _clean_voter(voter: schemas.VoterData) -> dict:
    """Trim, normalize and validate the owner data entered by the voter. Email is optional:
    without it the confirmation goes to the APC address."""
    data = {field: (getattr(voter, field, "") or "").strip() for field in VOTER_FIELDS}
    for field in ("nume_prenume", "str_locatar"):
        data[field] = re.sub(r"\s+", " ", data[field])

    errors = []
    if len(data["nume_prenume"]) < 3 or len(data["nume_prenume"]) > 120:
        errors.append("Numele și prenumele trebuie să aibă între 3 și 120 de caractere.")
    elif len(data["nume_prenume"].split()) < 2:
        errors.append("Introduceți atât numele, cât și prenumele.")
    elif not _NAME_RE.match(data["nume_prenume"]):
        errors.append("Numele conține caractere nepermise.")

    phone_digits = re.sub(r"\D", "", data["phone"])
    if not _PHONE_RE.match(data["phone"]) or not (6 <= len(phone_digits) <= 15):
        errors.append("Numărul de telefon nu este valid (6–15 cifre, poate începe cu +).")

    if not (5 <= len(data["str_locatar"]) <= 250):
        errors.append("Adresa de corespondență trebuie să aibă între 5 și 250 de caractere.")

    if data["email"] and (len(data["email"]) > 160 or not _EMAIL_RE.match(data["email"])):
        errors.append("Adresa electronică (email) nu este validă.")

    if errors:
        raise HTTPException(status_code=400, detail=" ".join(errors))
    return data


def _clean_properties(election: models.Election, items: list) -> list[dict]:
    """Owner's properties: the type must be one the APC allows; the number is typed by the owner.
    The same type+number is listed once per vote."""
    allowed_types = set(_election_property_types(election))
    chosen: list[dict] = []
    for item in items:
        tip = (item.tip_proprietate or "").strip().lower()
        nr = re.sub(r"\s+", " ", (item.nr_proprietate or "").strip())
        if tip not in allowed_types:
            raise HTTPException(status_code=400, detail=f"Tipul de imobil „{tip}” nu este permis în acest APC.")
        if not (1 <= len(nr) <= 30) or not _PROP_RE.match(nr):
            raise HTTPException(status_code=400, detail=f"Numărul imobilului ({tip}) nu este valid.")
        if not any(c["tip_proprietate"] == tip and c["nr_proprietate"] == nr for c in chosen):
            chosen.append({"tip_proprietate": tip, "nr_proprietate": nr})
    if not chosen:
        raise HTTPException(status_code=400, detail="Selectați cel puțin un imobil pe care îl dețineți.")
    if len(chosen) > 1 and not election.allow_multiple_properties:
        raise HTTPException(status_code=400, detail="Acest vot permite selectarea unui singur imobil.")
    return chosen


def _check_not_voted(db: Session, election: models.Election, properties: list[dict]) -> None:
    """Refuse properties already voted in this election and show the masked email used for it."""
    for p in properties:
        existing = (
            db.query(models.VoterProperty)
            .filter(
                models.VoterProperty.election_id == election.id,
                models.VoterProperty.tip_proprietate == p["tip_proprietate"],
                models.VoterProperty.nr_proprietate == p["nr_proprietate"],
            )
            .first()
        )
        if existing:
            previous = db.query(models.VoterToken).get(existing.token_id)
            masked = mask_email(previous.email) if previous and previous.email else "(fără email)"
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Imobilul {p['tip_proprietate']} cu nr {p['nr_proprietate']} a fost deja votat. "
                    f"Verificați emailul {masked}."
                ),
            )


def _safe_part(value: str) -> str:
    """Keep a filename part readable and free of characters Windows/macOS reject."""
    cleaned = re.sub(r'[\/:*?"<>|\s]+', "-", (value or "").strip())
    return cleaned.strip("-") or "fara"


def ballot_filename(election, token, submitted_at) -> str:
    """{data}-buletin_de_vot-{nr_apc}-{tip_imobil}-{nr_imobil}-{email}.pdf"""
    date = submitted_at.strftime("%Y-%m-%d")
    props = "_".join(
        f"{_safe_part(p['tip_proprietate'])}-{_safe_part(p['nr_proprietate'])}" for p in token.properties
    ) or "fara-imobil"
    email = _safe_part(token.email) if token.email else "fara-email"
    return f"{date}-buletin_de_vot-{_safe_part(election.nr_apc)}-{props}-{email}.pdf"


def _send_confirmation(db, election, token, effective, submitted_at, receipt_path):
    """Send the ballot to the owner. Without an owner email it goes to the APC address.
    The sender name is always the APC number. Returns (sent, recipient_masked_or_label)."""
    smtp, _source = get_smtp(db)
    if not smtp or not smtp.enabled:
        return False, ""

    if token.email:
        to_email = token.email
        recipient = mask_email(token.email)
    else:
        to_email = (election.results_email or "").strip()
        recipient = "adresa APC"
    if not to_email:
        return False, ""

    attach_pdf = bool(election.email_with_attachment)
    receipt_url = f"{settings.public_base_url.rstrip('/')}/api/ballot/receipt/{token.id}.pdf"
    submitted_str = submitted_at.strftime("%d.%m.%Y %H:%M:%S UTC")
    values = dict(
        voter_name=token.nume_prenume or "votant",
        election_title=election.title,
        submitted_at=submitted_str,
        nr_apc=election.nr_apc or "",
    )
    ok, _info = send_confirmation_email(
        smtp,
        to_email=to_email,
        cc=election.email_cc or "",
        bcc=election.email_bcc or "",
        voter_name=token.nume_prenume,
        election_title=election.title,
        submitted_at_str=submitted_str,
        pdf_path=receipt_path,
        text_body=build_email_text(
            election=election, voter=token, answers=effective, submitted_at=submitted_at,
            body_template=smtp.body_template, values=values,
            receipt_url=receipt_url, attach_pdf=attach_pdf,
        ),
        html_body=build_email_html(
            election=election, voter=token, answers=effective, submitted_at=submitted_at,
            body_template=smtp.body_template, values=values,
            receipt_url=receipt_url, attach_pdf=attach_pdf,
        ),
        attach_pdf=attach_pdf,
        nr_apc=election.nr_apc or "",
        attachment_name=ballot_filename(election, token, submitted_at),
        db=db,
        election_id=election.id,
        kind="confirmare vot",
    )
    return ok, recipient


# ------------------------------------------------------------------ routes ---
@router.get("/apc/{nr_apc}", response_model=schemas.ApcBallotOut)
def get_apc_ballot(nr_apc: str, db: Session = Depends(get_db)):
    election = _active_election(db, nr_apc)
    texts = build_ballot_texts(election, None)
    status_ = election_status(election)
    return schemas.ApcBallotOut(
        nr_apc=election.nr_apc,
        title=texts["title"],
        date_line=texts["date_line"],
        city_line=texts["city_line"],
        gdpr_text=GDPR_TEXT,
        properties=[schemas.PropertyItem(tip_proprietate=t, nr_proprietate="") for t in _election_property_types(election)],
        allow_multiple_properties=bool(election.allow_multiple_properties),
        chestiune=election.chestiune or "",
        questions=json.loads(election.questions_json or "[]"),
        require_signature=election.require_signature,
        is_open=status_ == "open",
        status=status_,
    )


@router.post("/apc/{nr_apc}/vote")
def submit_apc_vote(nr_apc: str, payload: schemas.VoteSubmission, request: Request, db: Session = Depends(get_db)):
    election = _active_election(db, nr_apc)
    if election_status(election) != "open":
        raise HTTPException(status_code=400, detail="Perioada de votare s-a încheiat.")

    if not payload.gdpr_consent:
        raise HTTPException(
            status_code=400,
            detail="Trebuie să acceptați prelucrarea datelor personale (GDPR) pentru a vota.",
        )

    voter_data = _clean_voter(payload.voter)
    properties = _clean_properties(election, payload.properties)
    _check_not_voted(db, election, properties)

    questions = json.loads(election.questions_json or "[]")
    effective, auto = _resolve_answers(questions, payload.answers or {})
    _validate_answers(questions, effective, auto)

    if election.require_signature and not payload.signature_png_base64:
        raise HTTPException(status_code=400, detail="Semnătura olografă este obligatorie")

    raw_signature = None
    if payload.signature_png_base64:
        try:
            _header, b64data = (
                payload.signature_png_base64.split(",", 1)
                if "," in payload.signature_png_base64
                else (None, payload.signature_png_base64)
            )
            raw_signature = base64.b64decode(b64data)
        except Exception:
            raise HTTPException(status_code=400, detail="Semnătura trimisă este invalidă")

    submitted_at = _now()
    token = models.VoterToken(
        election_id=election.id,
        **voter_data,
        tip_proprietate=properties[0]["tip_proprietate"],
        nr_proprietate=properties[0]["nr_proprietate"],
        properties_json=json.dumps(properties, ensure_ascii=False),
        voted_at=submitted_at,
    )
    db.add(token)
    try:
        db.flush()  # assigns token.id, needed for file names
        for p in properties:
            db.add(models.VoterProperty(
                election_id=election.id, token_id=token.id,
                tip_proprietate=p["tip_proprietate"], nr_proprietate=p["nr_proprietate"],
            ))

        signature_path = None
        if raw_signature is not None:
            signature_path = os.path.join(settings.data_dir, "signatures", f"{token.id}.png")
            with open(signature_path, "wb") as f:
                f.write(raw_signature)

        vote = models.Vote(
            token_id=token.id,
            election_id=election.id,
            answers_json=json.dumps(effective, ensure_ascii=False),
            signature_path=signature_path,
            gdpr_consent_at=submitted_at,
            submitted_at=submitted_at,
            ip_address=request.client.host if request.client else "",
        )
        db.add(vote)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Unul dintre imobile a fost votat între timp. Reîncărcați pagina.")
    db.refresh(vote)

    receipt_path = os.path.join(settings.data_dir, "receipts", f"{token.id}.pdf")
    generate_receipt_pdf(
        election=election,
        voter=token,
        answers=effective,
        submitted_at=submitted_at,
        signature_path=vote.signature_path,
        output_path=receipt_path,
        gdpr_consent_at=submitted_at,
    )
    vote.receipt_pdf_path = receipt_path
    db.commit()

    email_sent, sent_to = False, ""
    try:
        email_sent, sent_to = _send_confirmation(db, election, token, effective, submitted_at, receipt_path)
        vote.email_sent = email_sent
        db.commit()
    except Exception as exc:  # noqa: BLE001 - a mail problem must never fail the vote
        print(f"[email] Confirmarea votului nu a fost trimisă: {exc}")

    # Results report to the APC address (if configured). Never let a mail problem fail the vote.
    try:
        notification_ok, notification_info = send_results_after_vote(db, election)
        if not notification_ok and (election.results_email or "").strip() and election.notify_results_on_vote:
            print(f"[results] Notificarea după vot a eșuat: {notification_info}")
    except Exception as exc:  # noqa: BLE001
        print(f"[results] Notificarea după vot a eșuat: {exc}")

    return {
        "ok": True,
        "email_sent": email_sent,
        "email_recipient": sent_to,
        "receipt_url": f"/api/ballot/receipt/{token.id}.pdf",
        "properties": properties,
    }


@router.get("/receipt/{token_id}.pdf")
def download_receipt(token_id: str, inline: bool = False, db: Session = Depends(get_db)):
    """The token id is random and only given to the owner who voted (it is not guessable).
    `inline=1` opens the ballot in the browser; otherwise it is downloaded."""
    token = db.query(models.VoterToken).filter(models.VoterToken.id == token_id).first()
    if not token or not token.vote or not token.vote.receipt_pdf_path:
        raise HTTPException(status_code=404, detail="Chitanța nu este disponibilă")
    if not os.path.exists(token.vote.receipt_pdf_path):
        raise HTTPException(status_code=404, detail="Chitanța nu este disponibilă")
    submitted_at = token.vote.submitted_at or token.voted_at
    return FileResponse(
        token.vote.receipt_pdf_path,
        filename=ballot_filename(token.election, token, submitted_at),
        media_type="application/pdf",
        content_disposition_type="inline" if inline else "attachment",
    )
