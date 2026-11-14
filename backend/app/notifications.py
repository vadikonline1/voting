"""Sends aggregated vote-result reports to the APC email: after each new vote (optional),
manually from the admin panel, and once when the voting period ends."""
import json
import math
import os
import re
from datetime import datetime, timedelta, timezone

from html import escape

from . import models
from .config import settings
from .email_utils import send_email
from .extension import extend_url
from .smtp_config import get_smtp
from .results import _aware, compute_results, dashboard_url
from .results_email import build_results_email_html, build_results_email_text
from .results_pdf import generate_results_pdf


def _results_pdf_name(election: models.Election) -> str:
    """{data}-rezultate-votare-APC-{nr_apc}.pdf"""
    nr = re.sub(r'[\/:*?"<>|\s]+', "-", (election.nr_apc or "").strip()).strip("-") or "fara-nr"
    return f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-rezultate-votare-APC-{nr}.pdf"


def send_results_email(db, election: models.Election, *, final: bool = False) -> tuple[bool, str]:
    """Send the current results report. The final report (vote ended) also carries the secret link to
    prolong the vote and the results as a PDF. Returns (ok, info)."""
    recipients = (election.results_email or "").strip()
    if not recipients:
        return False, "Nu este configurat un email APC pentru rezultate."

    smtp, _source = get_smtp(db)
    if not smtp or not smtp.enabled:
        return False, "SMTP este dezactivat sau neconfigurat."

    results = compute_results(db, election)
    url = dashboard_url(election)
    pdf_path, link = None, ""
    if final:
        pdf_path = generate_results_pdf(
            election, results,
            os.path.join(settings.data_dir, "results", f"{election.id}-rezultate-finale.pdf"),
        )
        link = extend_url(election)
    subject = f"{'Rezultate finale' if final else 'Rezultate actualizate'} – {election.title}"
    ok, info = send_email(
        smtp,
        to=recipients,
        subject=subject,
        text_body=build_results_email_text(election, results, dashboard_url=url, final=final, extend_url=link),
        html_body=build_results_email_html(election, results, dashboard_url=url, final=final, extend_url=link),
        pdf_path=pdf_path,
        attach_pdf=bool(final),
        attachment_name=_results_pdf_name(election),
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


def send_links_email(db, election: models.Election) -> tuple[bool, str]:
    """Send the APC the fixed vote link (for the owners) and the dashboard link, with a reminder that
    the information is confidential: the dashboard is shared only with the people the APC chooses."""
    recipients = (election.results_email or "").strip()
    if not recipients:
        return False, "Nu este configurat un email APC pentru rezultate."
    smtp, _source = get_smtp(db)
    if not smtp or not smtp.enabled:
        return False, "SMTP este dezactivat sau neconfigurat."
    if not election.nr_apc:
        return False, "Completați numărul APC înainte de trimiterea linkurilor."

    base = settings.public_base_url.rstrip("/")
    vote_url = f"{base}/{election.nr_apc}"
    dash_url = dashboard_url(election)
    nr = election.nr_apc
    text = (
        "Bună ziua,\n\n"
        f"Votul pentru APC nr. {nr} ({election.title}) este pregătit. Vă transmitem două linkuri:\n\n"
        "1. Link de vot, pentru proprietarii din APC:\n"
        f"{vote_url}\n"
        "Proprietarii îl deschid, își completează datele, bifează imobilele pe care le dețin și votează.\n\n"
        "2. Dashboard cu rezultatele votării în timp real:\n"
        f"{dash_url}\n\n"
        "IMPORTANT: informațiile din dashboard sunt confidențiale și destinate exclusiv asociației. "
        "Dashboard-ul trebuie partajat doar persoanelor cărora asociația le acordă dreptul să vadă aceste "
        "informații (de exemplu membrilor comitetului). Nu publicați linkul pe site-uri sau în rețele sociale.\n\n"
        "Linkul de vot se trimite doar proprietarilor din APC.\n\n"
        f"Cu respect,\n{nr}"
    )
    html = (
        '<div style="font-family:Segoe UI,Roboto,Arial,sans-serif;font-size:15px;line-height:1.55;color:#1f2430;">'
        "<p>Bună ziua,</p>"
        f"<p>Votul pentru <strong>APC nr. {escape(str(nr))}</strong> ({escape(election.title)}) este pregătit. "
        "Vă transmitem două linkuri:</p>"
        '<p style="margin:14px 0 4px;"><strong>1. Link de vot</strong> (pentru proprietarii din APC):</p>'
        f'<p style="margin:0 0 6px;"><a href="{escape(vote_url)}" style="color:#2452b5;word-break:break-all;">'
        f"{escape(vote_url)}</a></p>"
        '<p style="margin:0 0 14px;font-size:13px;color:#4b5b76;">Proprietarii își completează datele, bifează '
        "imobilele pe care le dețin și votează.</p>"
        '<p style="margin:14px 0 4px;"><strong>2. Dashboard cu rezultatele în timp real</strong>:</p>'
        f'<p style="margin:0 0 14px;"><a href="{escape(dash_url)}" style="color:#2452b5;word-break:break-all;">'
        f"{escape(dash_url)}</a></p>"
        '<div style="margin:18px 0 0;padding:14px 16px;border:1px solid #e3d3a8;border-radius:10px;background:#fdf8ea;">'
        "<strong>Important:</strong> informațiile din dashboard sunt confidențiale și destinate exclusiv asociației. "
        "Dashboard-ul trebuie partajat doar persoanelor cărora asociația le acordă dreptul să vadă aceste informații "
        "(de exemplu membrilor comitetului). Nu publicați linkul pe site-uri sau în rețele sociale.</div>"
        '<p style="margin:14px 0 0;font-size:13px;color:#6b7280;">Linkul de vot se trimite doar proprietarilor din APC.</p>'
        "</div>"
    )
    ok, info = send_email(
        smtp,
        to=recipients,
        subject=f"Linkuri de vot și dashboard – APC nr. {nr}",
        text_body=text,
        html_body=html,
        from_name=nr,
        db=db,
        election_id=election.id,
        kind="linkuri vot",
    )
    if ok:
        election.links_email_sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
    return ok, info


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
    link = extend_url(election)
    unit = "zi" if days_left == 1 else "zile"
    subject = f"Votarea expiră în {days_left} {unit} – APC nr. {election.nr_apc}"
    end_text = end.strftime("%d.%m.%Y %H:%M UTC")
    text = (
        f"Votarea pentru APC nr. {election.nr_apc} ({election.title}) expiră în {days_left} {unit}, "
        f"la data {end_text}.\n\n"
        f"Până în prezent au votat {results['total_votes']} din {results['total_tokens']} proprietari "
        f"({results['participation_percent']}%).\n\n"
        "Dacă doriți să prelungiți termenul de votare, alegeți perioada de prelungire la adresa:\n"
        f"{link}\n\n"
        "Dacă votarea se încheie fără prelungire, rezultatele vor fi trimise automat la încheiere, "
        "împreună cu un raport PDF."
    )
    html = (
        '<div style="font-family:Segoe UI,Roboto,Arial,sans-serif;font-size:15px;line-height:1.55;color:#1f2430;">'
        f"<p>Votarea pentru <strong>APC nr. {escape(str(election.nr_apc))}</strong> ({escape(election.title)}) "
        f"expiră în <strong>{days_left} {unit}</strong>, la data {escape(end_text)}.</p>"
        f"<p>Până în prezent au votat <strong>{results['total_votes']}</strong> din "
        f"{results['total_tokens']} proprietari ({results['participation_percent']}%).</p>"
        "<p>Dacă doriți să prelungiți termenul de votare, alegeți perioada de prelungire:</p>"
        f'<p><a href="{escape(link)}" style="display:inline-block;padding:10px 18px;border-radius:999px;'
        'background:#2452b5;color:#fff;text-decoration:none;font-weight:600;">Prelungește votarea</a></p>'
        "<p style=\"font-size:13px;color:#6b7280;\">Dacă votarea se încheie fără prelungire, rezultatele vor fi "
        "trimise automat la încheiere, împreună cu un raport PDF.</p>"
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
