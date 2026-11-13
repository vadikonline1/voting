import csv
import io
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import (
    create_session_token, verify_password, require_admin,
    SESSION_COOKIE, SESSION_MAX_AGE,
)
from ..config import settings
from ..database import get_db

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ---------------------------------------------------------------- auth -----
@router.post("/login")
def login(payload: schemas.AdminLogin, response: Response, db: Session = Depends(get_db)):
    user = db.query(models.AdminUser).filter(models.AdminUser.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Utilizator sau parolă incorectă")
    token = create_session_token(user.username)
    response.set_cookie(
        SESSION_COOKIE, token, max_age=SESSION_MAX_AGE, httponly=True, samesite="lax",
    )
    return {"ok": True, "username": user.username}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me")
def me(username: str = Depends(require_admin)):
    return {"username": username}


# -------------------------------------------------------------- helpers ----
def _election_to_out(e: models.Election) -> schemas.ElectionOut:
    return schemas.ElectionOut(
        id=e.id,
        title=e.title,
        description=e.description or "",
        nr_apc=e.nr_apc or "",
        str_apc=e.str_apc or "",
        oras=e.oras or "",
        start_date_vot=e.start_date_vot,
        end_date_vot=e.end_date_vot,
        tip_proprietate=e.tip_proprietate or "apartament",
        questions=json.loads(e.questions_json or "[]"),
        is_active=e.is_active,
        require_signature=e.require_signature,
        email_with_attachment=bool(e.email_with_attachment),
        email_cc=e.email_cc or "",
        email_bcc=e.email_bcc or "",
        created_at=e.created_at,
        updated_at=e.updated_at,
    )


def _apply_election_fields(election: models.Election, payload: schemas.ElectionIn):
    election.title = payload.title
    election.description = payload.description
    election.nr_apc = payload.nr_apc
    election.str_apc = payload.str_apc
    election.oras = payload.oras
    election.start_date_vot = payload.start_date_vot
    election.end_date_vot = payload.end_date_vot
    election.tip_proprietate = payload.tip_proprietate
    election.questions_json = json.dumps([q.model_dump() for q in payload.questions], ensure_ascii=False)
    election.is_active = payload.is_active
    election.require_signature = payload.require_signature
    election.email_with_attachment = payload.email_with_attachment
    election.email_cc = payload.email_cc
    election.email_bcc = payload.email_bcc


# -------------------------------------------------------------- elections --
@router.get("/elections", response_model=list[schemas.ElectionOut])
def list_elections(username: str = Depends(require_admin), db: Session = Depends(get_db)):
    elections = db.query(models.Election).order_by(models.Election.id.desc()).all()
    return [_election_to_out(e) for e in elections]


@router.post("/elections", response_model=schemas.ElectionOut)
def create_election(payload: schemas.ElectionIn, username: str = Depends(require_admin), db: Session = Depends(get_db)):
    election = models.Election()
    _apply_election_fields(election, payload)
    db.add(election)
    db.commit()
    db.refresh(election)
    return _election_to_out(election)


@router.put("/elections/{election_id}", response_model=schemas.ElectionOut)
def update_election(election_id: int, payload: schemas.ElectionIn, username: str = Depends(require_admin), db: Session = Depends(get_db)):
    election = db.query(models.Election).get(election_id)
    if not election:
        raise HTTPException(status_code=404, detail="Votul nu a fost găsit")
    _apply_election_fields(election, payload)
    election.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(election)
    return _election_to_out(election)


@router.delete("/elections/{election_id}")
def delete_election(election_id: int, username: str = Depends(require_admin), db: Session = Depends(get_db)):
    election = db.query(models.Election).get(election_id)
    if not election:
        raise HTTPException(status_code=404, detail="Votul nu a fost găsit")
    db.delete(election)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------- voter tokens --
def _token_url(token_id: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}/{token_id}"


@router.post("/tokens/generate")
def generate_tokens(payload: schemas.TokenGenerateRequest, username: str = Depends(require_admin), db: Session = Depends(get_db)):
    election = db.query(models.Election).get(payload.election_id)
    if not election:
        raise HTTPException(status_code=404, detail="Votul nu a fost găsit")

    created = []
    if payload.rows:
        for row in payload.rows[:5000]:
            token = models.VoterToken(
                election_id=election.id,
                nume_prenume=row.nume_prenume.strip(),
                phone=row.phone.strip(),
                str_locatar=row.str_locatar.strip(),
                email=row.email.strip(),
                nr_proprietate=row.nr_proprietate.strip(),
            )
            db.add(token)
            created.append(token)
    else:
        count = max(1, min(payload.count or 1, 5000))
        for _ in range(count):
            token = models.VoterToken(election_id=election.id)
            db.add(token)
            created.append(token)

    db.commit()
    return {
        "ok": True,
        "tokens": [
            {
                "id": t.id,
                "nume_prenume": t.nume_prenume,
                "phone": t.phone,
                "str_locatar": t.str_locatar,
                "email": t.email,
                "nr_proprietate": t.nr_proprietate,
                "url": _token_url(t.id),
            }
            for t in created
        ],
    }


@router.put("/tokens/{token_id}")
def update_token(token_id: str, payload: schemas.VoterTokenUpdate, username: str = Depends(require_admin), db: Session = Depends(get_db)):
    token = db.query(models.VoterToken).filter(models.VoterToken.id == token_id).first()
    if not token:
        raise HTTPException(status_code=404, detail="Link-ul nu a fost găsit")
    if token.has_voted:
        raise HTTPException(status_code=400, detail="Nu poți edita datele unui link care a votat deja")
    for field in ("nume_prenume", "phone", "str_locatar", "email", "nr_proprietate"):
        value = getattr(payload, field)
        if value is not None:
            setattr(token, field, value.strip())
    db.commit()
    return {"ok": True}


@router.delete("/tokens/{token_id}")
def delete_token(token_id: str, username: str = Depends(require_admin), db: Session = Depends(get_db)):
    token = db.query(models.VoterToken).filter(models.VoterToken.id == token_id).first()
    if not token:
        raise HTTPException(status_code=404, detail="Link-ul nu a fost găsit")
    db.delete(token)
    db.commit()
    return {"ok": True}


@router.get("/elections/{election_id}/checklist")
def checklist(election_id: int, username: str = Depends(require_admin), db: Session = Depends(get_db)):
    """HTML-friendly list of who has voted (secret-ballot safe: shows voted status, not the vote content)."""
    election = db.query(models.Election).get(election_id)
    if not election:
        raise HTTPException(status_code=404, detail="Votul nu a fost găsit")
    tokens = (
        db.query(models.VoterToken)
        .filter(models.VoterToken.election_id == election_id)
        .order_by(models.VoterToken.created_at.asc())
        .all()
    )
    rows = [
        {
            "token_id": t.id,
            "nume_prenume": t.nume_prenume,
            "phone": t.phone,
            "str_locatar": t.str_locatar,
            "email": t.email,
            "nr_proprietate": t.nr_proprietate,
            "url": _token_url(t.id),
            "has_voted": t.has_voted,
            "voted_at": t.voted_at,
            "email_sent": bool(t.vote.email_sent) if t.vote else False,
        }
        for t in tokens
    ]
    total = len(rows)
    voted = sum(1 for r in rows if r["has_voted"])
    return {"election_title": election.title, "total": total, "voted": voted, "rows": rows}


@router.get("/elections/{election_id}/tokens.csv")
def export_tokens_csv(election_id: int, username: str = Depends(require_admin), db: Session = Depends(get_db)):
    tokens = (
        db.query(models.VoterToken)
        .filter(models.VoterToken.election_id == election_id)
        .order_by(models.VoterToken.created_at.asc())
        .all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["nume_prenume", "phone", "str_locatar", "email", "nr_proprietate", "url", "has_voted", "voted_at"])
    for t in tokens:
        writer.writerow([
            t.nume_prenume, t.phone, t.str_locatar, t.email, t.nr_proprietate, _token_url(t.id),
            "DA" if t.has_voted else "NU", t.voted_at.isoformat() if t.voted_at else "",
        ])
    return Response(
        content=buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=linkuri-vot.csv"},
    )


# ------------------------------------------------------------------ results
@router.get("/elections/{election_id}/results")
def results(election_id: int, username: str = Depends(require_admin), db: Session = Depends(get_db)):
    election = db.query(models.Election).get(election_id)
    if not election:
        raise HTTPException(status_code=404, detail="Votul nu a fost găsit")
    questions = json.loads(election.questions_json or "[]")
    votes = db.query(models.Vote).filter(models.Vote.election_id == election_id).all()

    tally = {q["id"]: {opt: 0 for opt in q.get("options", [])} for q in questions}
    for v in votes:
        answers = json.loads(v.answers_json or "{}")
        for q in questions:
            qid = q["id"]
            ans = answers.get(qid)
            if ans is None:
                continue
            if isinstance(ans, list):
                for a in ans:
                    tally[qid][a] = tally[qid].get(a, 0) + 1
            else:
                tally[qid][ans] = tally[qid].get(ans, 0) + 1

    return {
        "election_title": election.title,
        "total_votes": len(votes),
        "questions": questions,
        "tally": tally,
    }


# --------------------------------------------------------------- smtp -----
@router.get("/smtp", response_model=schemas.SmtpSettingsOut)
def get_smtp(username: str = Depends(require_admin), db: Session = Depends(get_db)):
    smtp = db.query(models.SmtpSettings).first()
    return schemas.SmtpSettingsOut(
        enabled=smtp.enabled, host=smtp.host, port=smtp.port, username=smtp.username,
        has_password=bool(smtp.password), from_email=smtp.from_email, from_name=smtp.from_name,
        use_tls=smtp.use_tls, subject_template=smtp.subject_template, body_template=smtp.body_template,
    )


@router.put("/smtp", response_model=schemas.SmtpSettingsOut)
def update_smtp(payload: schemas.SmtpSettingsIn, username: str = Depends(require_admin), db: Session = Depends(get_db)):
    smtp = db.query(models.SmtpSettings).first()
    smtp.enabled = payload.enabled
    smtp.host = payload.host
    smtp.port = payload.port
    smtp.username = payload.username
    if payload.password is not None and payload.password != "":
        smtp.password = payload.password
    smtp.from_email = payload.from_email
    smtp.from_name = payload.from_name
    smtp.use_tls = payload.use_tls
    if payload.subject_template:
        smtp.subject_template = payload.subject_template
    if payload.body_template:
        smtp.body_template = payload.body_template
    db.commit()
    db.refresh(smtp)
    return schemas.SmtpSettingsOut(
        enabled=smtp.enabled, host=smtp.host, port=smtp.port, username=smtp.username,
        has_password=bool(smtp.password), from_email=smtp.from_email, from_name=smtp.from_name,
        use_tls=smtp.use_tls, subject_template=smtp.subject_template, body_template=smtp.body_template,
    )


@router.post("/smtp/test")
def test_smtp(to_email: str, username: str = Depends(require_admin), db: Session = Depends(get_db)):
    from ..email_utils import send_confirmation_email
    import tempfile, os
    from reportlab.pdfgen import canvas as rl_canvas

    smtp = db.query(models.SmtpSettings).first()
    tmp_path = os.path.join(tempfile.gettempdir(), "smtp-test.pdf")
    c = rl_canvas.Canvas(tmp_path)
    c.drawString(100, 700, "Test email - sistem de vot")
    c.save()
    ok, info = send_confirmation_email(
        smtp, to_email=to_email, voter_name="Test", election_title="Test SMTP",
        submitted_at_str=datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M:%S UTC"), pdf_path=tmp_path,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=f"Trimiterea a eșuat: {info}")
    return {"ok": True}
