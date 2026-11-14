"""Public endpoints behind the prolongation link /extend/{extend_uuid}: the APC sees the current end
date and chooses how many days to add."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..extension import EXTEND_OPTIONS, prolong
from ..results import _aware, election_status

router = APIRouter(prefix="/api/extend", tags=["extend"])


class ExtendIn(BaseModel):
    days: int


def _by_token(db: Session, token: str) -> models.Election:
    election = db.query(models.Election).filter(models.Election.extend_uuid == token).first()
    if not election:
        raise HTTPException(status_code=404, detail="Linkul de prelungire nu este valid.")
    return election


@router.get("/{token}")
def get_extension(token: str, db: Session = Depends(get_db)):
    election = _by_token(db, token)
    end = _aware(election.end_date_vot)
    return {
        "nr_apc": election.nr_apc or "",
        "title": election.title,
        "end_date_vot": end.isoformat() if end else None,
        "status": election_status(election),
        "is_active": bool(election.is_active),
        "options": list(EXTEND_OPTIONS),
    }


@router.post("/{token}")
def post_extension(token: str, payload: ExtendIn, db: Session = Depends(get_db)):
    election = _by_token(db, token)
    if payload.days not in EXTEND_OPTIONS:
        raise HTTPException(status_code=400, detail="Alegeți una dintre perioadele propuse.")
    if not election.is_active:
        raise HTTPException(status_code=400, detail="Votul nu este activ, prelungirea nu este posibilă.")
    new_end = prolong(db, election, payload.days)
    return {"ok": True, "end_date_vot": new_end.isoformat() + "+00:00"}
