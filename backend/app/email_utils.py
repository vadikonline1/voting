"""Sends the vote confirmation email using the SMTP settings configured from the admin panel.
Supports an optional PDF attachment, an HTML alternative, and CC/BCC copies configured per vote."""
import re
import smtplib
import ssl
from email.message import EmailMessage

from . import models

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def _parse_addresses(raw: str | None) -> list[str]:
    """Split a comma/semicolon separated list and keep only syntactically valid addresses."""
    if not raw:
        return []
    parts = re.split(r"[,;]", raw)
    return [p.strip() for p in parts if p.strip() and _EMAIL_RE.match(p.strip())]


def send_confirmation_email(
    smtp: models.SmtpSettings,
    *,
    to_email: str,
    cc: str = "",
    bcc: str = "",
    voter_name: str,
    election_title: str,
    submitted_at_str: str,
    pdf_path: str | None = None,
    text_body: str | None = None,
    html_body: str | None = None,
    attach_pdf: bool = True,
) -> tuple[bool, str]:
    if not smtp.enabled:
        return False, "SMTP dezactivat"
    if not smtp.host or not to_email:
        return False, "Lipsesc host SMTP sau adresa destinatarului"

    subject = smtp.subject_template.format(election_title=election_title)
    if text_body is None:
        text_body = smtp.body_template.format(
            voter_name=voter_name or "votant",
            election_title=election_title,
            submitted_at=submitted_at_str,
        )

    cc_list = _parse_addresses(cc)
    bcc_list = _parse_addresses(bcc)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{smtp.from_name} <{smtp.from_email}>" if smtp.from_name else smtp.from_email
    msg["To"] = to_email
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    if attach_pdf:
        if not pdf_path:
            return False, "Lipsește PDF-ul care trebuie atașat"
        try:
            with open(pdf_path, "rb") as f:
                msg.add_attachment(
                    f.read(), maintype="application", subtype="pdf",
                    filename="buletin-de-vot-confirmare.pdf",
                )
        except OSError as exc:
            return False, f"Nu am putut citi PDF-ul: {exc}"

    # BCC addresses are passed to the SMTP envelope only, never written into the headers.
    recipients = list(dict.fromkeys([to_email, *cc_list, *bcc_list]))

    try:
        if smtp.use_tls:
            with smtplib.SMTP(smtp.host, smtp.port, timeout=20) as server:
                server.starttls(context=ssl.create_default_context())
                if smtp.username:
                    server.login(smtp.username, smtp.password)
                server.send_message(msg, to_addrs=recipients)
        else:
            with smtplib.SMTP_SSL(smtp.host, smtp.port, timeout=20) as server:
                if smtp.username:
                    server.login(smtp.username, smtp.password)
                server.send_message(msg, to_addrs=recipients)
        return True, "OK"
    except Exception as exc:  # noqa: BLE001 - we want to report the reason back to the admin
        return False, str(exc)
