"""Aggregated vote results, shared by the admin panel, the public dashboard and the
results emails, so percentages and totals are always calculated the same way."""
import json
from datetime import datetime, timezone

from . import models
from .ballot_text import labelled_questions, public_questions
from .config import settings


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite stores naive datetimes; treat them as UTC."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def election_status(election: models.Election) -> str:
    if not election.is_active:
        return "closed"
    end = _aware(election.end_date_vot)
    if end and datetime.now(timezone.utc) > end:
        return "closed"
    return "open"


def dashboard_url(election: models.Election) -> str:
    base = (settings.public_base_url or "").rstrip("/")
    if not base or not election.public_uuid:
        return ""
    return f"{base}/{election.public_uuid}/dashboard"


def compute_results(db, election: models.Election) -> dict:
    """Return totals, participation and per-question counts/percentages."""
    questions = public_questions(json.loads(election.questions_json or "[]"))
    votes = db.query(models.Vote).filter(models.Vote.election_id == election.id).all()
    total_tokens = (
        db.query(models.VoterToken)
        .filter(models.VoterToken.election_id == election.id)
        .count()
    )
    total_votes = len(votes)

    tally = {q["id"]: {opt: 0 for opt in q.get("options", [])} for q in questions}
    for vote in votes:
        answers = json.loads(vote.answers_json or "{}")
        for question in questions:
            answer = answers.get(question["id"])
            if answer is None:
                continue
            if isinstance(answer, list):
                for value in answer:
                    tally[question["id"]][value] = tally[question["id"]].get(value, 0) + 1
            else:
                tally[question["id"]][answer] = tally[question["id"]].get(answer, 0) + 1

    question_rows = []
    for question, label in labelled_questions(questions):
        if label is None:
            continue
        options = []
        for option in question.get("options", []):
            count = tally[question["id"]].get(option, 0)
            percent = round(count / total_votes * 100, 1) if total_votes else 0.0
            options.append({"option": option, "count": count, "percent": percent})
        question_rows.append({
            "id": question["id"],
            "number": label,
            "text": question.get("text", ""),
            "options": options,
        })

    participation = round(total_votes / total_tokens * 100, 1) if total_tokens else 0.0
    now = datetime.now(timezone.utc)
    return {
        "election_id": election.id,
        "title": election.title,
        "chestiune": election.chestiune or "",
        "nr_apc": election.nr_apc or "",
        "str_apc": election.str_apc or "",
        "oras": election.oras or "",
        "status": election_status(election),
        "start_date_vot": _aware(election.start_date_vot).isoformat() if election.start_date_vot else None,
        "end_date_vot": _aware(election.end_date_vot).isoformat() if election.end_date_vot else None,
        "total_votes": total_votes,
        "total_tokens": total_tokens,
        "participation_percent": participation,
        "questions": question_rows,
        "generated_at": now.isoformat(),
    }
