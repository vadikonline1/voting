"""Email sending using the SMTP settings (panel or .env).
Supports an optional PDF attachment, an HTML alternative, CC/BCC copies, and keeps a log of every
email (sender, recipients, subject and headers) so the admin can see what was sent and to whom."""
import re
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

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


def _headers_text(sender: str, to: list[str], cc: list[str], bcc: list[str], subject: str,
                  date: str, message_id: str, attachment: str) -> str:
    lines = [f"From: {sender}", f"To: {', '.join(to)}"]
    if cc:
        lines.append(f"Cc: {', '.join(cc)}")
    if bcc:
        lines.append(f"Bcc (doar în transport, nu apare în email): {', '.join(bcc)}")
    lines += [f"Subject: {subject}", f"Date: {date}", f"Message-ID: {message_id}"]
    if attachment:
        lines.append(f"Attachment: {attachment}")
    return "\n".join(lines)


def _record(db, *, election_id, kind: str, ok: bool, info: str, sender: str, to: list[str],
            cc: list[str], bcc: list[str], subject: str, text_body: str, headers: str,
            attachment: str) -> None:
    """Store one log row. Logging must never break sending, so errors are only printed."""
    if db is None:
        return
    try:
        db.add(models.EmailLog(
            election_id=election_id,
            kind=kind,
            status="trimis" if ok else "eșuat",
            info=(info or "")[:500],
            from_addr=sender,
            to_addr=", ".join(to),
            cc=", ".join(cc),
            bcc=", ".join(bcc),
            subject=subject[:300],
            headers=headers,
            attachment=attachment,
            preview=(text_body or "").strip()[:400],
            created_at=datetime.now(timezone.utc),
        ))
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"[email-log] Nu am putut salva jurnalul emailului: {exc}")


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
    attachments: list[tuple[str, str]] | None = None,
    db=None,
    election_id: int | None = None,
    kind: str = "",
) -> tuple[bool, str]:
    """Send one email. Returns (ok, info). BCC addresses are only used in the SMTP envelope.
    `from_name` is the sender display name: always the APC number, never the panel value.
    When `db` is given, the email (headers included) is written to the email log."""
    name = (from_name or "").strip()
    sender = f"{name} <{smtp.from_email}>" if name else (smtp.from_email or "")
    to_list = parse_addresses(to)
    cc_list = parse_addresses(cc)
    bcc_list = parse_addresses(bcc)
    # one or more (path, file name) pairs; a single pdf_path is the classic case
    files = list(attachments or [])
    if attach_pdf and not files and pdf_path:
        files = [(pdf_path, attachment_name)]
    attachment = ", ".join(name for _, name in files) if (attach_pdf and files) else ""
    date = formatdate(localtime=False)
    domain = smtp.from_email.split("@")[-1] if smtp.from_email and "@" in smtp.from_email else "localhost"
    message_id = make_msgid(domain=domain)

    def done(ok: bool, info: str) -> tuple[bool, str]:
        _record(
            db, election_id=election_id, kind=kind, ok=ok, info=info, sender=sender,
            to=to_list, cc=cc_list, bcc=bcc_list, subject=subject, text_body=text_body,
            headers=_headers_text(sender, to_list, cc_list, bcc_list, subject, date, message_id, attachment),
            attachment=attachment,
        )
        return ok, info

    if not smtp.enabled:
        return done(False, "SMTP dezactivat")
    if not smtp.host:
        return done(False, "Lipsește hostul SMTP")
    if not to_list:
        return done(False, "Adresa destinatarului nu este validă")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(to_list)
    msg["Date"] = date
    msg["Message-ID"] = message_id
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    if attach_pdf:
        if not files:
            return done(False, "Lipsește PDF-ul care trebuie atașat")
        for path, name in files:
            try:
                with open(path, "rb") as fh:
                    msg.add_attachment(fh.read(), maintype="application", subtype="pdf", filename=name)
            except OSError as exc:
                return done(False, f"Nu am putut citi PDF-ul: {exc}")

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
        return done(True, "OK")
    except Exception as exc:  # noqa: BLE001 - we want to report the reason back to the admin
        return done(False, str(exc))


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
    attachments: list[tuple[str, str]] | None = None,
    text_body: str | None = None,
    html_body: str | None = None,
    attach_pdf: bool = True,
    nr_apc: str = "",
    attachment_name: str = "buletin-de-vot.pdf",
    db=None,
    election_id: int | None = None,
    kind: str = "confirmare vot",
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
        attachments=attachments,
        attach_pdf=attach_pdf,
        from_name=nr_apc or None,
        attachment_name=attachment_name,
        db=db,
        election_id=election_id,
        kind=kind,
    )
