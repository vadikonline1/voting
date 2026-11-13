"""Sends aggregated vote-result reports to the APC email: after each new vote (optional),
manually from the admin panel, and once when the voting period ends."""
import json
import math
from datetime import datetime, timedelta, timezone

from html import escape

from . import models
from .config import settings
from .email_utils import send_email
from .smtp_config import get_smtp
from .results import _aware, compute_results, dashboard_url
from .results_email import build_results_email_html, build_results_email_text


def send_results_email(db, election: models.Election, *, final: bool = False) -> tuple[bool, str]:
    """Send the current results report. Returns (ok, info)."""
    recipients = (election.results_email or "").strip()
    if not recipients:
        return False, "Nu este configurat un email APC pentru rezultate."

    smtp, _source = get_smtp(db)
    if not smtp or not smtp.enabled:
        return False, "SMTP este dezactivat sau neconfigurat."

    results = compute_results(db, election)
    url = dashboard_url(election)
    subject = f"{'Rezultate finale' if final else 'Rezultate actualizate'} – {election.title}"
    ok, info = send_email(
        smtp,
        to=recipients,
        subject=subject,
        text_body=build_results_email_text(election, results, dashboard_url=url, final=final),
        html_body=build_results_email_html(election, results, dashboard_url=url, final=final),
        from_name=election.nr_apc or None,
        db=db,
        election_id=election.id,
        kind="raport final" if final else "raport rezultate",
    )
    if ok and final:
        election.results_final_email_sent_at = datetime.now(timezone.utc)
        db.commit()
    return ok, info


def send_results_after_vote(db, election: models.Election) -> tuple[bool, str]:
    """Best-effort notification after a new vote; never blocks or fails the vote itself."""
    if not (election.results_email or "").strip() or not election.notify_results_on_vote:
        return False, "Notificarea rezultatelor nu este configurată."
    return send_results_email(db, election, final=False)


def send_pending_final_results(db) -> int:
    """Send the final report once for every election whose end date has passed."""
    now = datetime.now(timezone.utc)
    elections = (
        db.query(models.Election)
        .filter(
            models.Election.results_email.isnot(None),
            models.Election.results_email != "",
            models.Election.results_final_email_sent_at.is_(None),
            models.Election.end_date_vot.isnot(None),
        )
        .all()
    )
    sent = 0
    for election in elections:
        end = _aware(election.end_date_vot)
        if not end or now <= end:
            continue
        ok, info = send_results_email(db, election, final=True)
        if ok:
            sent += 1
        else:
            print(f"[results] Raport final pentru votul {election.id} nu a fost trimis: {info}")
    return sent


def results_dashboard_path(election: models.Election) -> str:
    """Relative dashboard path, useful for admin links."""
    return f"/{election.public_uuid}/dashboard" if election.public_uuid else ""


# ------------------------------------------------------------ expiry reminders --
EXPIRY_STEPS = (3, 2, 1)  # days before end_date_vot


def _reminder_state(election: models.Election, end_iso: str) -> dict:
    """Reminders already sent for this end date. A new end date (prolonged vote) starts afresh."""
    try:
        state = json.loads(election.expiry_reminders_json or "{}")
    except (ValueError, TypeError):
        state = {}
    if not isinstance(state, dict) or state.get("end") != end_iso:
        return {"end": end_iso, "sent": []}
    return {"end": end_iso, "sent": [int(d) for d in state.get("sent", []) if d in EXPIRY_STEPS]}


def _expiry_email(db, election: models.Election, days_left: int, end: datetime) -> tuple[bool, str]:
    recipients = (election.results_email or "").strip()
    if not recipients:
        return False, "Nu este configurat un email APC."
    smtp, _source = get_smtp(db)
    if not smtp or not smtp.enabled:
        return False, "SMTP este dezactivat sau neconfigurat."

    results = compute_results(db, election)
    base = settings.public_base_url.rstrip("/")
    admin_url = f"{base}/admin/elections/{election.id}"
    unit = "zi" if days_left == 1 else "zile"
    subject = f"Votarea expiră în {days_left} {unit} – APC nr. {election.nr_apc}"
    end_text = end.strftime("%d.%m.%Y %H:%M UTC")
    text = (
        f"Votarea pentru APC nr. {election.nr_apc} ({election.title}) expiră în {days_left} {unit}, "
        f"la data {end_text}.\n\n"
        f"Până în prezent au votat {results['total_votes']} din {results['total_tokens']} proprietari "
        f"({results['participation_percent']}%).\n\n"
        "Dacă doriți să prelungiți termenul de votare, puteți modifica data din panoul de administrare:\n"
        f"{admin_url}\n\n"
        "Dacă votarea se încheie fără prelungire, rezultatele vor fi trimise automat la încheiere."
    )
    html = (
        '<div style="font-family:Segoe UI,Roboto,Arial,sans-serif;font-size:15px;line-height:1.55;color:#1f2430;">'
        f"<p>Votarea pentru <strong>APC nr. {escape(str(election.nr_apc))}</strong> ({escape(election.title)}) "
        f"expiră în <strong>{days_left} {unit}</strong>, la data {escape(end_text)}.</p>"
        f"<p>Până în prezent au votat <strong>{results['total_votes']}</strong> din "
        f"{results['total_tokens']} proprietari ({results['participation_percent']}%).</p>"
        "<p>Dacă doriți să prelungiți termenul de votare, modificați data din panoul de administrare:</p>"
        f'<p><a href="{escape(admin_url)}" style="display:inline-block;padding:10px 18px;border-radius:999px;'
        'background:#2452b5;color:#fff;text-decoration:none;font-weight:600;">Deschide votul în panou</a></p>'
        "</div>"
    )
    return send_email(
        smtp,
        to=recipients,
        subject=subject,
        text_body=text,
        html_body=html,
        from_name=election.nr_apc or None,
        db=db,
        election_id=election.id,
        kind="reamintire expirare",
    )


def send_expiry_reminders(db) -> int:
    """Email the APC 3, 2 and 1 day(s) before the vote ends. One email per run covers every step
    that is due; the steps are remembered per end date, so a prolonged vote is reminded again."""
    now = datetime.now(timezone.utc)
    elections = (
        db.query(models.Election)
        .filter(
            models.Election.is_active.is_(True),
            models.Election.end_date_vot.isnot(None),
            models.Election.results_email.isnot(None),
            models.Election.results_email != "",
        )
        .all()
    )
    sent_count = 0
    for election in elections:
        end = _aware(election.end_date_vot)
        if not end or now >= end:
            continue
        end_iso = end.isoformat()
        state = _reminder_state(election, end_iso)
        due = [d for d in EXPIRY_STEPS if now >= end - timedelta(days=d) and d not in state["sent"]]
        if not due:
            continue
        days_left = max(1, math.ceil((end - now).total_seconds() / 86400))
        ok, info = _expiry_email(db, election, days_left, end)
        if ok:
            state["sent"] = sorted(set(state["sent"]) | set(due), reverse=True)
            election.expiry_reminders_json = json.dumps(state)
            db.commit()
            sent_count += 1
        else:
            print(f"[reminders] Înștiințarea pentru votul {election.id} nu a fost trimisă: {info}")
    return sent_count
