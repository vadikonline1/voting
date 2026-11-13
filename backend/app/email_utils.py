"""Sends the vote confirmation email with the PDF receipt attached, using the SMTP settings
configured from the admin panel (stored in the database, not just env vars)."""
import smtplib
import ssl
from email.message import EmailMessage

from . import models


def send_confirmation_email(
    smtp: models.SmtpSettings,
    *,
    to_email: str,
    voter_name: str,
    election_title: str,
    submitted_at_str: str,
    pdf_path: str,
) -> tuple[bool, str]:
    if not smtp.enabled:
        return False, "SMTP dezactivat"
    if not smtp.host or not to_email:
        return False, "Lipsesc host SMTP sau adresa destinatarului"

    subject = smtp.subject_template.format(election_title=election_title)
    body = smtp.body_template.format(
        voter_name=voter_name or "votant",
        election_title=election_title,
        submitted_at=submitted_at_str,
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{smtp.from_name} <{smtp.from_email}>" if smtp.from_name else smtp.from_email
    msg["To"] = to_email
    msg.set_content(body)

    try:
        with open(pdf_path, "rb") as f:
            msg.add_attachment(
                f.read(), maintype="application", subtype="pdf",
                filename="buletin-de-vot-confirmare.pdf",
            )
    except OSError as exc:
        return False, f"Nu am putut citi PDF-ul: {exc}"

    try:
        if smtp.use_tls:
            with smtplib.SMTP(smtp.host, smtp.port, timeout=20) as server:
                server.starttls(context=ssl.create_default_context())
                if smtp.username:
                    server.login(smtp.username, smtp.password)
                server.send_message(msg)
        else:
            with smtplib.SMTP_SSL(smtp.host, smtp.port, timeout=20) as server:
                if smtp.username:
                    server.login(smtp.username, smtp.password)
                server.send_message(msg)
        return True, "OK"
    except Exception as exc:  # noqa: BLE001 - we want to report the reason back to the admin
        return False, str(exc)
