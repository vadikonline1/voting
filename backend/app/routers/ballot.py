import base64
import json
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from ..database import get_db
from ..ballot_text import build_ballot_texts
from ..pdf import generate_receipt_pdf
from ..email_utils import send_confirmation_email

router = APIRouter(prefix="/api/ballot", tags=["ballot"])


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

    questions = json.loads(election.questions_json or "[]")
    answers = payload.answers or {}

    for q in questions:
        if q.get("required", True):
            val = answers.get(q["id"])
            if val in (None, "", []):
                raise HTTPException(status_code=400, detail=f"Răspunsul la \"{q['text']}\" este obligatoriu")

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

    vote = models.Vote(
        token_id=token.id,
        election_id=election.id,
        answers_json=json.dumps(answers, ensure_ascii=False),
        signature_path=signature_path,
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
        answers=answers,
        submitted_at=submitted_at,
        signature_path=signature_path,
        output_path=receipt_path,
    )
    vote.receipt_pdf_path = receipt_path
    db.commit()

    email_sent = False
    if token.email:
        smtp = db.query(models.SmtpSettings).first()
        if smtp and smtp.enabled:
            ok, _info = send_confirmation_email(
                smtp,
                to_email=token.email,
                voter_name=token.nume_prenume,
                election_title=election.title,
                submitted_at_str=submitted_at.strftime("%d.%m.%Y %H:%M:%S UTC"),
                pdf_path=receipt_path,
            )
            email_sent = ok
            vote.email_sent = ok
            db.commit()

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
