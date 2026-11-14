import re
import csv
import io
import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import (
    create_session_token, hash_password, verify_password, require_admin,
    get_current_admin, SESSION_COOKIE, SESSION_MAX_AGE,
)
from .. import retention
from ..ballot_template import DEFAULT_TEMPLATE, VARIABLES, load_template, save_template, template_values
from ..ballot_text import build_ballot_texts, labelled_questions, public_questions
from ..config import settings
from ..database import get_db
from ..extension import extend_url
from ..notifications import send_links_email, send_results_email
from ..results import compute_results, dashboard_url
from ..smtp_config import get_smtp
from ..tz import end_of_day, start_of_day

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
    return {
        "ok": True,
        "username": user.username,
        "must_change_password": bool(user.must_change_password),
    }


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me")
def me(admin: models.AdminUser = Depends(get_current_admin)):
    return {
        "username": admin.username,
        "must_change_password": bool(admin.must_change_password),
    }


@router.post("/change-password")
def change_password(
    payload: schemas.ChangePasswordIn,
    admin: models.AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Lets the logged-in admin replace the initial/default password."""
    if not verify_password(payload.current_password, admin.password_hash):
        raise HTTPException(status_code=400, detail="Parola actuală este incorectă.")
    new_password = (payload.new_password or "").strip()
    if len(new_password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Parola nouă trebuie să aibă cel puțin 8 caractere.",
        )
    if len(new_password) > 128:
        raise HTTPException(
            status_code=400,
            detail="Parola nouă este prea lungă (maximum 128 de caractere).",
        )
    if new_password == payload.current_password:
        raise HTTPException(
            status_code=400,
            detail="Parola nouă trebuie să fie diferită de cea actuală.",
        )
    admin.password_hash = hash_password(new_password)
    admin.must_change_password = False
    db.commit()
    return {"ok": True}


# -------------------------------------------------------------- helpers ----
def _property_types_from_payload(items) -> list[dict]:
    """Keep the distinct property types (apartament, debara, parcare, or custom), without numbers."""
    types: list[str] = []
    for item in items:
        tip = (item.tip_proprietate or "").strip().lower()
        if not tip:
            continue
        if len(tip) > 30 or not re.match(r"^[a-zăâîșțA-Z ]+$", tip):
            raise HTTPException(status_code=400, detail=f"Tip de imobil invalid: „{item.tip_proprietate}”.")
        if tip not in types:
            types.append(tip)
    return [{"tip_proprietate": t} for t in types]


def _vote_url(nr_apc: str | None) -> str:
    base = settings.public_base_url.rstrip("/")
    return f"{base}/{nr_apc}" if nr_apc else ""


def _election_properties(e: models.Election) -> list[dict]:
    """Allowed property types of the APC (the numbers are typed by the owners)."""
    try:
        items = json.loads(e.properties_json or "[]")
    except (ValueError, TypeError):
        return []
    return [{"tip_proprietate": i["tip_proprietate"]} for i in items if isinstance(i, dict) and i.get("tip_proprietate")]


def _ensure_single_active(db: Session, payload: schemas.ElectionIn, election_id: int | None):
    """Each APC has one active vote: the fixed link /{nr_apc} opens it."""
    if not payload.is_active:
        return
    if not (payload.nr_apc or "").strip():
        raise HTTPException(status_code=400, detail="Completați numărul APC înainte de a activa votul.")
    query = db.query(models.Election).filter(
        func.lower(models.Election.nr_apc) == payload.nr_apc.strip().lower(),
        models.Election.is_active.is_(True),
    )
    if election_id is not None:
        query = query.filter(models.Election.id != election_id)
    if query.first():
        raise HTTPException(
            status_code=400,
            detail=f"Există deja un vot activ pentru APC nr. {payload.nr_apc}. Dezactivați-l mai întâi.",
        )


def _clean_addresses(items: list[str]) -> list[str]:
    """Blocks / addresses of the APC: trimmed, without empty lines or duplicates, order kept."""
    cleaned: list[str] = []
    for item in items or []:
        value = re.sub(r"\s+", " ", (item or "").strip())
        if not value:
            continue
        if len(value) > 250:
            raise HTTPException(status_code=400, detail=f"Adresa „{value[:40]}…” este prea lungă (maximum 250 de caractere).")
        if value.lower() not in [c.lower() for c in cleaned]:
            cleaned.append(value)
    return cleaned


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
        properties=[schemas.PropertyItem(tip_proprietate=p["tip_proprietate"]) for p in _election_properties(e)],
        allow_multiple_properties=bool(e.allow_multiple_properties),
        chestiune=e.chestiune or "",
        adrese=e.addresses,
        blocuri=e.blocks,
        vote_url=_vote_url(e.nr_apc),
        extend_url=extend_url(e),
        questions=json.loads(e.questions_json or "[]"),
        is_active=e.is_active,
        require_signature=e.require_signature,
        email_with_attachment=bool(e.email_with_attachment),
        email_cc=e.email_cc or "",
        email_bcc=e.email_bcc or "",
        results_email=e.results_email or "",
        notify_results_on_vote=bool(e.notify_results_on_vote),
        public_uuid=e.public_uuid or "",
        created_at=e.created_at,
        updated_at=e.updated_at,
    )


def _apply_election_fields(election: models.Election, payload: schemas.ElectionIn):
    election.title = payload.title
    election.description = payload.description
    election.nr_apc = payload.nr_apc.strip()
    # The addresses of the condominium are kept as a list; str_apc is their joined text (title, PDF, emails)
    addresses = _clean_addresses(payload.adrese)
    election.adrese_json = json.dumps(addresses, ensure_ascii=False)
    election.blocuri_json = json.dumps(_clean_addresses(payload.blocuri), ensure_ascii=False)
    election.str_apc = "; ".join(addresses) if addresses else (payload.str_apc or "").strip()
    election.oras = payload.oras
    # the vote runs by days in Chisinau time: from the start of the first day to the end of the deadline day
    election.start_date_vot = start_of_day(payload.start_date_vot)
    election.end_date_vot = end_of_day(payload.end_date_vot)
    election.tip_proprietate = payload.tip_proprietate
    election.allow_multiple_properties = bool(payload.allow_multiple_properties)
    election.chestiune = payload.chestiune or ""
    election.properties_json = json.dumps(
        _property_types_from_payload(payload.properties),
        ensure_ascii=False,
    )
    election.questions_json = json.dumps([q.model_dump() for q in payload.questions], ensure_ascii=False)
    election.is_active = payload.is_active
    election.require_signature = payload.require_signature
    election.email_with_attachment = payload.email_with_attachment
    election.email_cc = payload.email_cc
    election.email_bcc = payload.email_bcc
    election.results_email = (payload.results_email or "").strip()
    election.notify_results_on_vote = payload.notify_results_on_vote


# -------------------------------------------------------------- elections --
@router.get("/elections", response_model=list[schemas.ElectionOut])
def list_elections(username: str = Depends(require_admin), db: Session = Depends(get_db)):
    elections = db.query(models.Election).order_by(models.Election.id.desc()).all()
    return [_election_to_out(e) for e in elections]


@router.post("/elections", response_model=schemas.ElectionOut)
def create_election(payload: schemas.ElectionIn, username: str = Depends(require_admin), db: Session = Depends(get_db)):
    _ensure_single_active(db, payload, None)
    election = models.Election(public_uuid=uuid.uuid4().hex)
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
    _ensure_single_active(db, payload, election.id)
    _apply_election_fields(election, payload)
    election.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(election)
    return _election_to_out(election)


@router.post("/elections/{election_id}/extend")
def extend_election(
    election_id: int,
    end_date: str,
    username: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Prolong the vote to the end of the chosen day (Chisinau time). The expiry reminders start again."""
    election = db.query(models.Election).get(election_id)
    if not election:
        raise HTTPException(status_code=404, detail="Votul nu a fost găsit")
    try:
        new_end = end_of_day(end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Data de încheiere nu este validă.")
    if new_end <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="Noua dată de încheiere trebuie să fie în viitor.")
    end_date = new_end
    election.end_date_vot = end_date
    election.is_active = True
    election.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "end_date_vot": end_date.isoformat()}


@router.delete("/elections/{election_id}")
def delete_election(election_id: int, username: str = Depends(require_admin), db: Session = Depends(get_db)):
    election = db.query(models.Election).get(election_id)
    if not election:
        raise HTTPException(status_code=404, detail="Votul nu a fost găsit")
    db.delete(election)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------- voter tokens --
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
            "adresa": t.adresa or "",
            "bloc": t.bloc or "",
            "properties": t.properties,
            "has_voted": t.has_voted,
            "voted_at": t.voted_at,
            "email_sent": bool(t.vote.email_sent) if t.vote else False,
        }
        for t in tokens
    ]
    total = len(rows)
    voted = sum(1 for r in rows if r["has_voted"])
    return {
        "election_title": election.title,
        "vote_url": _vote_url(election.nr_apc),
        "extend_url": extend_url(election),
        "links_email_sent_at": election.links_email_sent_at.isoformat() if election.links_email_sent_at else None,
        "total": total,
        "voted": voted,
        "rows": rows,
    }


@router.get("/elections/{election_id}/votes/{token_id}")
def vote_detail(election_id: int, token_id: str, username: str = Depends(require_admin), db: Session = Depends(get_db)):
    """What one owner voted, for the APC administrator (opened from the checklist). Hidden questions are
    not part of the ballot, so they are not listed."""
    token = (
        db.query(models.VoterToken)
        .filter(models.VoterToken.id == token_id, models.VoterToken.election_id == election_id)
        .first()
    )
    if not token or not token.vote:
        raise HTTPException(status_code=404, detail="Acest link nu a votat.")
    election = token.election
    answers = json.loads(token.vote.answers_json or "{}")
    items = []
    for question, label in labelled_questions(public_questions(json.loads(election.questions_json or "[]"))):
        if label is None:
            items.append({"type": "section", "text": question.get("text", "")})
            continue
        answer = answers.get(question["id"])
        if isinstance(answer, list):
            answer_text = ", ".join(str(a) for a in answer) if answer else "(fără răspuns)"
        else:
            answer_text = str(answer) if answer not in (None, "") else "(fără răspuns)"
        items.append({"type": "question", "label": label, "text": question.get("text", ""), "answer": answer_text})
    return {
        "token_id": token.id,
        "nume_prenume": token.nume_prenume,
        "adresa": token.adresa or "",
        "bloc": token.bloc or "",
        "properties": token.properties,
        "voted_at": token.voted_at.isoformat() if token.voted_at else None,
        "receipt_url": f"/api/ballot/receipt/{token.id}.pdf?inline=1",
        "items": items,
    }


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
    writer.writerow(["nume_prenume", "phone", "str_locatar", "email", "adresa", "bloc", "imobile", "has_voted", "voted_at"])
    for t in tokens:
        writer.writerow([
            t.nume_prenume, t.phone, t.str_locatar, t.email, t.adresa or "", t.bloc or "",
            "; ".join(f"{p['tip_proprietate']} {p['nr_proprietate']}" for p in t.properties),
            "DA" if t.has_voted else "NU", t.voted_at.isoformat() if t.voted_at else "",
        ])
    return Response(
        content=buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=linkuri-vot.csv"},
    )


# ------------------------------------------------------------------ results
@router.get("/elections/{election_id}/emails")
def email_log(election_id: int, username: str = Depends(require_admin), db: Session = Depends(get_db)):
    """Log of the emails sent for this vote: sender, recipients, subject and headers."""
    rows = (
        db.query(models.EmailLog)
        .filter(models.EmailLog.election_id == election_id)
        .order_by(models.EmailLog.created_at.desc())
        .limit(300)
        .all()
    )
    return [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "kind": r.kind,
            "status": r.status,
            "info": r.info,
            "from": r.from_addr,
            "to": r.to_addr,
            "cc": r.cc,
            "bcc": r.bcc,
            "subject": r.subject,
            "headers": r.headers,
            "attachment": r.attachment,
            "preview": r.preview,
        }
        for r in rows
    ]


@router.get("/elections/{election_id}/results")
def results(election_id: int, username: str = Depends(require_admin), db: Session = Depends(get_db)):
    election = db.query(models.Election).get(election_id)
    if not election:
        raise HTTPException(status_code=404, detail="Votul nu a fost găsit")
    data = compute_results(db, election)
    data["dashboard_url"] = dashboard_url(election)
    data["results_email"] = election.results_email or ""
    data["notify_results_on_vote"] = bool(election.notify_results_on_vote)
    data["results_final_email_sent_at"] = (
        election.results_final_email_sent_at.isoformat()
        if election.results_final_email_sent_at else None
    )
    return data


@router.post("/elections/{election_id}/send-links")
def send_links(election_id: int, username: str = Depends(require_admin), db: Session = Depends(get_db)):
    """Email the APC the vote link and the dashboard link (send after all questions are added)."""
    election = db.query(models.Election).get(election_id)
    if not election:
        raise HTTPException(status_code=404, detail="Votul nu a fost găsit")
    ok, info = send_links_email(db, election)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Trimiterea a eșuat: {info}")
    return {"ok": True, "sent_to": election.results_email, "sent_at": election.links_email_sent_at.isoformat()}


@router.post("/elections/{election_id}/send-results")
def send_results(
    election_id: int,
    final: bool = False,
    username: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Email the current results report to the configured APC address."""
    election = db.query(models.Election).get(election_id)
    if not election:
        raise HTTPException(status_code=404, detail="Votul nu a fost găsit")
    if not (election.results_email or "").strip():
        raise HTTPException(
            status_code=400,
            detail="Configurați mai întâi adresa de email APC pentru rezultate.",
        )
    ok, info = send_results_email(db, election, final=final)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Trimiterea a eșuat: {info}")
    return {"ok": True, "sent_to": election.results_email, "final": final}


# ------------------------------------------------------------ retention ----
@router.get("/retention")
def retention_preview(username: str = Depends(require_admin), db: Session = Depends(get_db)):
    return retention.preview(db)


@router.post("/retention/purge-old")
def retention_purge_old(username: str = Depends(require_admin), db: Session = Depends(get_db)):
    """Deletes every vote that ended more than 180 days ago (permanent)."""
    result = retention.purge_old(db)
    return {"ok": True, **result}


@router.post("/retention/clear-all")
def retention_clear_all(payload: schemas.ClearAllIn, username: str = Depends(require_admin), db: Session = Depends(get_db)):
    """Deletes every vote. Allowed only when no vote is active, and only with the typed confirmation."""
    if retention.has_active_vote(db):
        raise HTTPException(status_code=409, detail="Există un vot activ. Dezactivați-l înainte de golire.")
    if (payload.confirm or "").strip() != "STERGE TOT":
        raise HTTPException(status_code=400, detail="Scrieți „STERGE TOT” pentru confirmare.")
    result = retention.clear_all(db)
    return {"ok": True, **result}


# ------------------------------------------------------- ballot template ----
def _sample_voter():
    """An example owner for the preview (never saved)."""
    return SimpleNamespace(
        id="exemplu", nume_prenume="Ion Popescu", phone="+373 60 000 000",
        str_locatar="str. Exemplu 1, ap. 2", email="votant@exemplu.md", adresa="", bloc="E",
        properties=[{"tip_proprietate": "apartament", "nr_proprietate": "803/E"}],
    )


@router.get("/ballot-template")
def get_ballot_template(username: str = Depends(require_admin), db: Session = Depends(get_db)):
    return {
        "template": load_template(db),
        "defaults": DEFAULT_TEMPLATE,
        "variables": [{"key": k, "label": label, "example": example} for k, label, example in VARIABLES],
    }


@router.put("/ballot-template")
def put_ballot_template(payload: schemas.BallotTemplateIn, username: str = Depends(require_admin), db: Session = Depends(get_db)):
    return save_template(db, payload.model_dump())


@router.post("/ballot-template/preview")
def preview_ballot_template(payload: schemas.BallotPreviewIn, username: str = Depends(require_admin), db: Session = Depends(get_db)):
    """Renders the text with the given (unsaved) template. Variables come from the chosen vote, or from
    the first vote, and the owner is an example."""
    election = None
    if payload.election_id:
        election = db.query(models.Election).get(payload.election_id)
    if election is None:
        election = db.query(models.Election).order_by(models.Election.id.desc()).first()
    if election is None:
        election = models.Election(title="Exemplu", nr_apc="12", str_apc="str. Exemplu 1", oras="Chișinău",
                                   start_date_vot=datetime(2026, 10, 31), end_date_vot=datetime(2026, 11, 25))
    template = payload.model_dump(exclude={"election_id"})
    voter = _sample_voter()
    submitted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    return {
        "rendered": build_ballot_texts(election, voter, template, submitted_at),
        "values": template_values(election, voter, submitted_at),
        "election_title": election.title,
    }


# --------------------------------------------------------------- smtp -----
def _smtp_out(smtp) -> schemas.SmtpSettingsOut:
    return schemas.SmtpSettingsOut(
        enabled=smtp.enabled, host=smtp.host, port=smtp.port, username=smtp.username,
        has_password=bool(smtp.password), from_email=smtp.from_email, from_name=smtp.from_name,
        use_tls=smtp.use_tls, subject_template=smtp.subject_template, body_template=smtp.body_template,
        env_managed=bool(settings.smtp_host),
    )


@router.get("/smtp", response_model=schemas.SmtpSettingsOut)
def get_smtp_settings(username: str = Depends(require_admin), db: Session = Depends(get_db)):
    smtp, _source = get_smtp(db)
    return _smtp_out(smtp)


@router.put("/smtp", response_model=schemas.SmtpSettingsOut)
def update_smtp(payload: schemas.SmtpSettingsIn, username: str = Depends(require_admin), db: Session = Depends(get_db)):
    smtp = db.query(models.SmtpSettings).first()
    if settings.smtp_host:
        # Connection settings come from .env: the panel can only change the email texts.
        if payload.subject_template:
            smtp.subject_template = payload.subject_template
        if payload.body_template:
            smtp.body_template = payload.body_template
    else:
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
    effective, _source = get_smtp(db)
    return _smtp_out(effective)


@router.post("/smtp/test")
def test_smtp(to_email: str, username: str = Depends(require_admin), db: Session = Depends(get_db)):
    from ..email_utils import send_confirmation_email
    import tempfile, os
    from reportlab.pdfgen import canvas as rl_canvas

    smtp, _source = get_smtp(db)
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
