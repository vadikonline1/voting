"""Resolves the SMTP configuration: values from the environment (.env) when SMTP_HOST is set,
otherwise the settings saved in the admin panel. Subject/body templates always come from the
panel row."""
from . import models
from .config import settings

DEFAULT_SUBJECT = "Confirmare vot - {election_title}"


def get_smtp(db):
    """Return (smtp_config, source). smtp_config is a transient object (not added to the session)."""
    row = db.query(models.SmtpSettings).first()
    if settings.smtp_host:
        return models.SmtpSettings(
            id=1,
            enabled=settings.smtp_enabled,
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            from_email=settings.smtp_from_email,
            from_name=row.from_name if row else "",
            use_tls=settings.smtp_use_tls,
            subject_template=row.subject_template if row else DEFAULT_SUBJECT,
            body_template=row.body_template if row else "",
        ), "env"
    return row, "panel"
