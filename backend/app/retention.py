"""Data retention for votes: remove the votes that ended more than RETENTION_DAYS ago, and the
"clear everything" action that is allowed only when no vote is active.

Deleting is permanent: the vote, its owners' data, the ballots (PDF), the signatures, the results PDFs
and the email log of the vote are removed. Nothing here runs by itself; the admin starts it."""
import os
from datetime import datetime, timedelta, timezone

from . import models
from .config import settings
from .results import _aware

RETENTION_DAYS = 180


def _old_elections(db) -> list[models.Election]:
    """Votes whose end date is more than RETENTION_DAYS in the past."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    out = []
    for election in db.query(models.Election).all():
        end = _aware(election.end_date_vot)
        if end and end < cutoff:
            out.append(election)
    return out


def _files_of(db, election_ids: list[int]) -> list[str]:
    """Every file that belongs to these votes: ballots, signatures and results reports."""
    paths: list[str] = []
    for election_id in election_ids:
        paths.append(os.path.join(settings.data_dir, "results", f"{election_id}-rezultate-finale.pdf"))
    tokens = db.query(models.VoterToken).filter(models.VoterToken.election_id.in_(election_ids)).all()
    for token in tokens:
        paths.append(os.path.join(settings.data_dir, "receipts", f"{token.id}.pdf"))
        paths.append(os.path.join(settings.data_dir, "signatures", f"{token.id}.png"))
    return paths


def _delete_elections(db, elections: list[models.Election]) -> dict:
    ids = [e.id for e in elections]
    if not ids:
        return {"votes": 0, "owners": 0}
    tokens = db.query(models.VoterToken).filter(models.VoterToken.election_id.in_(ids)).count()
    paths = _files_of(db, ids)

    db.query(models.VoterProperty).filter(models.VoterProperty.election_id.in_(ids)).delete(synchronize_session=False)
    db.query(models.EmailLog).filter(models.EmailLog.election_id.in_(ids)).delete(synchronize_session=False)
    for election in elections:
        db.delete(election)  # cascades to the owners (tokens) and their votes
    db.commit()

    for path in paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError as exc:
            print(f"[retention] Nu am putut șterge fișierul {path}: {exc}")
    return {"votes": len(ids), "owners": tokens}


def has_active_vote(db) -> bool:
    return db.query(models.Election).filter(models.Election.is_active.is_(True)).first() is not None


def preview(db) -> dict:
    old = _old_elections(db)
    old_ids = [e.id for e in old]
    owners = db.query(models.VoterToken).filter(models.VoterToken.election_id.in_(old_ids)).count() if old_ids else 0
    total_elections = db.query(models.Election).count()
    return {
        "retention_days": RETENTION_DAYS,
        "old_votes": len(old),
        "old_owners": owners,
        "old_titles": [f"APC nr. {e.nr_apc or '—'} · {e.title}" for e in old],
        "total_votes": total_elections,
        "has_active_vote": has_active_vote(db),
    }


def purge_old(db) -> dict:
    return _delete_elections(db, _old_elections(db))


def clear_all(db) -> dict:
    """Removes every vote. Refused by the caller while a vote is active."""
    return _delete_elections(db, db.query(models.Election).all())
