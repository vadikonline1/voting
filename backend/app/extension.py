"""Prolonging a vote from the secret link the APC receives by email (/extend/{extend_uuid}).

The APC chooses how many days to add. The new end is counted from the current end date, or from
now when the vote has already ended. The expiry reminders restart for the new end date, and the
final results email is sent again when the prolonged vote ends."""
from datetime import datetime, timedelta, timezone

from . import models
from .config import settings
from .results import _aware

EXTEND_OPTIONS = (1, 3, 7, 14, 30)  # days the APC can add


def extend_url(election: models.Election) -> str:
    """The public link the APC uses to prolong the vote. Empty when there is no secret link."""
    if not election.extend_uuid:
        return ""
    return f"{settings.public_base_url.rstrip('/')}/extend/{election.extend_uuid}"


def prolong(db, election: models.Election, days: int) -> datetime:
    """Add `days` to the end of the vote. Returns the new end date (naive UTC, as stored)."""
    now = datetime.now(timezone.utc)
    end = _aware(election.end_date_vot) or now
    base = end if end > now else now
    new_end = (base + timedelta(days=days)).replace(tzinfo=None)

    election.end_date_vot = new_end
    election.is_active = True
    election.results_final_email_sent_at = None  # the final report goes out again at the new end
    election.updated_at = now
    db.commit()
    return new_end
