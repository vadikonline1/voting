"""Sends aggregated vote-result reports to the APC email: after each new vote (optional),
manually from the admin panel, and once when the voting period ends."""
from datetime import datetime, timezone

from . import models
from .config import settings
from .email_utils import send_email
from .results import _aware, compute_results, dashboard_url
from .results_email import build_results_email_html, build_results_email_text


def send_results_email(db, election: models.Election, *, final: bool = False) -> tuple[bool, str]:
    """Send the current results report. Returns (ok, info)."""
    recipients = (election.results_email or "").strip()
    if not recipients:
        return False, "Nu este configurat un email APC pentru rezultate."

    smtp = db.query(models.SmtpSettings).first()
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
