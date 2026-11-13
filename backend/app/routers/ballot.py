import base64
import json
import os
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from ..database import get_db
from ..ballot_text import GDPR_TEXT, build_ballot_texts
from ..email_html import build_email_html, build_email_text
from ..pdf import generate_receipt_pdf
from ..email_utils import send_confirmation_email
from ..notifications import send_results_after_vote

router = APIRouter(prefix="/api/ballot", tags=["ballot"])

_NAME_RE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿĀ-ž' .\-]+$")
_PHONE_RE = re.compile(r"^\+?[0-9][0-9 ()\-.]{5,19}$")
_PROP_RE = re.compile(r"^[0-9A-Za-zÀ-ÖØ-öø-ÿĀ-ž/ .\-]+$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")

VOTER_FIELDS = ("nume_prenume", "phone", "str_locatar", "email", "nr_proprietate")


def _now():
    return datetime.now(timezone.utc)


def _aware(dt):
    """SQLite stores naive datetimes; treat them as UTC for comparisons."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _resolve_status(token: models.VoterToken, election: models.Election) -> str:
    if token.has_voted:
        return "voted"
    end = _aware(election.end_date_vot)
    now = _now()
    if end and now > end:
        grace_end = end + timedelta(days=settings.link_grace_days)
        if now > grace_end:
            return "gone"
        return "closed"
    if not election.is_active:
        return "closed"
    return "open"


def _get_token_or_404(db: Session, token_id: str) -> models.VoterToken:
    token = db.query(models.VoterToken).filter(models.VoterToken.id == token_id).first()
    if not token:
        raise HTTPException(status_code=404, detail="Link de vot invalid")
    status_ = _resolve_status(token, token.election)
    if status_ == "gone":
        raise HTTPException(status_code=410, detail="Acest link de vot nu mai este valabil")
    return token


# ------------------------------------------------------------- voting logic --
def _resolve_answers(questions: list, answers: dict) -> tuple[dict, dict]:
    """Apply question dependencies.

    If a question declares `depends_on`, `depends_value` and `auto_answer`, then when the
    parent's effective answer equals `depends_value`, this question is disabled and gets
    `auto_answer` automatically (e.g. Q1 = "Pentru" -> Q2 forced to "Împotriva").
    """
    effective: dict = {}
    auto: dict = {}
    for q in questions:
        qid = q.get("id")
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
        qid = q.get("id")
        if qid in auto:
            continue  # forced by a dependency; nothing for the voter to answer
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
                raise HTTPException(
                    status_code=400,
                    detail=f'Răspuns invalid la întrebarea „{label}”.',
                )
        elif str(value) not in options:
            raise HTTPException(
                status_code=400,
                detail=f'Răspuns invalid la întrebarea „{label}”.',
            )


def _clean_voter(voter: schemas.VoterData) -> dict:
    """Trim, normalize and validate the owner data entered by the voter."""
    data = {field: (getattr(voter, field, "") or "").strip() for field in VOTER_FIELDS}
    for field in ("nume_prenume", "str_locatar", "nr_proprietate"):
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

    if len(data["email"]) > 160 or not _EMAIL_RE.match(data["email"]):
        errors.append("Adresa electronică (email) nu este validă.")

    if not (1 <= len(data["nr_proprietate"]) <= 30) or not _PROP_RE.match(data["nr_proprietate"]):
        errors.append("Numărul unității (bunului imobil) nu este valid.")

    if errors:
        raise HTTPException(status_code=400, detail=" ".join(errors))
    return data


# ------------------------------------------------------------------ routes ---
@router.get("/{token_id}", response_model=schemas.BallotPublicOut)
def get_ballot(token_id: str, db: Session = Depends(get_db)):
    token = _get_token_or_404(db, token_id)
    election = token.election
    status_ = _resolve_status(token, election)
    questions = json.loads(election.questions_json or "[]")
    texts = build_ballot_texts(election, token)
    return schemas.BallotPublicOut(
        title=texts["title"],
        date_line=texts["date_line"],
        city_line=texts["city_line"],
        paragraph1=texts["paragraph1"],
        paragraph2=texts["paragraph2"],
        gdpr_text=GDPR_TEXT,
        voter=schemas.VoterData(**{field: getattr(token, field) or "" for field in VOTER_FIELDS}),
        questions=questions,
        require_signature=election.require_signature,
        already_voted=token.has_voted,
        is_open=status_ == "open",
        status=status_,
    )


@router.post("/{token_id}/vote")
def submit_vote(token_id: str, payload: schemas.VoteSubmission, request: Request, db: Session = Depends(get_db)):
    token = _get_token_or_404(db, token_id)
    election = token.election
    status_ = _resolve_status(token, election)
    if status_ != "open":
        messages = {
            "voted": "Ați votat deja cu acest link.",
            "closed": "Perioada de votare s-a încheiat.",
        }
        raise HTTPException(status_code=400, detail=messages.get(status_, "Votarea nu este disponibilă."))

    if not payload.gdpr_consent:
        raise HTTPException(
            status_code=400,
            detail="Trebuie să acceptați prelucrarea datelor personale (GDPR) pentru a vota.",
        )

    voter_data = _clean_voter(payload.voter)

    questions = json.loads(election.questions_json or "[]")
    effective, auto = _resolve_answers(questions, payload.answers or {})
    _validate_answers(questions, effective, auto)

    if election.require_signature and not payload.signature_png_base64:
        raise HTTPException(status_code=400, detail="Semnătura olografă este obligatorie")

    signature_path = None
    if payload.signature_png_base64:
        try:
            header, b64data = (
                payload.signature_png_base64.split(",", 1)
                if "," in payload.signature_png_base64
                else (None, payload.signature_png_base64)
            )
            raw = base64.b64decode(b64data)
        except Exception:
            raise HTTPException(status_code=400, detail="Semnătura trimisă este invalidă")
        signature_path = os.path.join(settings.data_dir, "signatures", f"{token_id}.png")
        with open(signature_path, "wb") as f:
            f.write(raw)

    submitted_at = _now()

    # Persist the owner data exactly as entered/confirmed by the voter, so the PDF and the
    # email show the same values and an incomplete admin pre-fill can be corrected on the spot.
    for field, value in voter_data.items():
        setattr(token, field, value)

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
    token.voted_at = submitted_at
    db.commit()
    db.refresh(vote)

    receipt_path = os.path.join(settings.data_dir, "receipts", f"{token_id}.pdf")
    generate_receipt_pdf(
        election=election,
        voter=token,
        answers=effective,
        submitted_at=submitted_at,
        signature_path=signature_path,
        output_path=receipt_path,
        gdpr_consent_at=submitted_at,
    )
    vote.receipt_pdf_path = receipt_path
    db.commit()

    email_sent = False
    if token.email:
        smtp = db.query(models.SmtpSettings).first()
        if smtp and smtp.enabled:
            attach_pdf = bool(election.email_with_attachment)
            receipt_url = f"{settings.public_base_url.rstrip('/')}/api/ballot/{token.id}/receipt.pdf"
            intro_text = smtp.body_template.format(
                voter_name=token.nume_prenume or "votant",
                election_title=election.title,
                submitted_at=submitted_at.strftime("%d.%m.%Y %H:%M:%S UTC"),
            )
            ok, _info = send_confirmation_email(
                smtp,
                to_email=token.email,
                cc=election.email_cc or "",
                bcc=election.email_bcc or "",
                voter_name=token.nume_prenume,
                election_title=election.title,
                submitted_at_str=submitted_at.strftime("%d.%m.%Y %H:%M:%S UTC"),
                pdf_path=receipt_path,
                text_body=build_email_text(
                    election=election,
                    voter=token,
                    answers=effective,
                    submitted_at=submitted_at,
                    intro_text=intro_text,
                    receipt_url=receipt_url,
                    attach_pdf=attach_pdf,
                ),
                html_body=build_email_html(
                    election=election,
                    voter=token,
                    answers=effective,
                    submitted_at=submitted_at,
                    intro_text=intro_text,
                    receipt_url=receipt_url,
                    attach_pdf=attach_pdf,
                ),
                attach_pdf=attach_pdf,
            )
            email_sent = ok
            vote.email_sent = ok
            db.commit()

    # Results report to the APC address (if configured). Never let a mail problem fail the vote.
    try:
        notification_ok, notification_info = send_results_after_vote(db, election)
        if not notification_ok and (election.results_email or "").strip() and election.notify_results_on_vote:
            print(f"[results] Notificarea după vot a eșuat: {notification_info}")
    except Exception as exc:  # noqa: BLE001 - results email must never break the ballot
        print(f"[results] Notificarea după vot a eșuat: {exc}")

    return {"ok": True, "email_sent": email_sent, "receipt_available": True}


@router.get("/{token_id}/receipt.pdf")
def download_receipt(token_id: str, db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse

    token = db.query(models.VoterToken).filter(models.VoterToken.id == token_id).first()
    if not token or not token.vote or not token.vote.receipt_pdf_path:
        raise HTTPException(status_code=404, detail="Chitanța nu este disponibilă")
    if not os.path.exists(token.vote.receipt_pdf_path):
        raise HTTPException(status_code=404, detail="Chitanța nu este disponibilă")
    return FileResponse(token.vote.receipt_pdf_path, filename="buletin-de-vot-confirmare.pdf", media_type="application/pdf")
