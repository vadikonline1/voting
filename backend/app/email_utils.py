"""Email sending using the SMTP settings configured from the admin panel.
Supports an optional PDF attachment, an HTML alternative, and CC/BCC copies."""
import re
import smtplib
import ssl
from email.message import EmailMessage

from . import models

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def parse_addresses(raw: str | None) -> list[str]:
    """Split a comma/semicolon separated list and keep only syntactically valid addresses."""
    if not raw:
        return []
    parts = re.split(r"[,;]", raw)
    return [p.strip() for p in parts if p.strip() and _EMAIL_RE.match(p.strip())]


# Backwards-compatible private alias.
_parse_addresses = parse_addresses


class _SafeValues(dict):
    """Unknown {placeholders} stay visible instead of raising KeyError."""

    def __missing__(self, key):
        return "{" + key + "}"


def render_template(template: str, values: dict) -> str:
    return (template or "").format_map(_SafeValues(values))


def mask_email(address: str) -> str:
    """pu****im@gmail.com style masking for on-screen warnings."""
    if not address or "@" not in address:
        return ""
    local, domain = address.split("@", 1)
    if len(local) <= 4:
        return local[:1] + "****@" + domain
    return local[:2] + "****" + local[-2:] + "@" + domain


def send_email(
    smtp: models.SmtpSettings,
    *,
    to: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    cc: str = "",
    bcc: str = "",
    pdf_path: str | None = None,
    attach_pdf: bool = False,
    from_name: str | None = None,
    attachment_name: str = "buletin-de-vot.pdf",
) -> tuple[bool, str]:
    """Send one email. Returns (ok, info). BCC addresses are only used in the SMTP envelope.
    `from_name` is the sender display name: always the APC number, never the panel value."""
    if not smtp.enabled:
        return False, "SMTP dezactivat"
    if not smtp.host:
        return False, "Lipsește hostul SMTP"

    to_list = parse_addresses(to)
    if not to_list:
        return False, "Adresa destinatarului nu este validă"
    cc_list = parse_addresses(cc)
    bcc_list = parse_addresses(bcc)

    msg = EmailMessage()
    msg["Subject"] = subject
    name = (from_name or "").strip()
    msg["From"] = f"{name} <{smtp.from_email}>" if name else smtp.from_email
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    if attach_pdf:
        if not pdf_path:
            return False, "Lipsește PDF-ul care trebuie atașat"
        try:
            with open(pdf_path, "rb") as fh:
                msg.add_attachment(
                    fh.read(), maintype="application", subtype="pdf",
                    filename=attachment_name,
                )
        except OSError as exc:
            return False, f"Nu am putut citi PDF-ul: {exc}"

    recipients = list(dict.fromkeys([*to_list, *cc_list, *bcc_list]))

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
    nr_apc: str = "",
    attachment_name: str = "buletin-de-vot.pdf",
) -> tuple[bool, str]:
    values = dict(
        voter_name=voter_name or "votant",
        election_title=election_title,
        submitted_at=submitted_at_str,
        nr_apc=nr_apc,
    )
    if text_body is None:
        text_body = render_template(smtp.body_template, values)
    subject = render_template(smtp.subject_template, values)
    return send_email(
        smtp,
        to=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        cc=cc,
        bcc=bcc,
        pdf_path=pdf_path,
        attach_pdf=attach_pdf,
        from_name=nr_apc or None,
        attachment_name=attachment_name,
    )
