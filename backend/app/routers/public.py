"""Public, unauthenticated endpoints: the live results dashboard.

Access is granted only through the election's random `public_uuid`, which is deliberately
different from the voter tokens, so the ballot links stay secret while the results can be
shared with the APC members.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..results import compute_results, dashboard_url

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/results/{public_uuid}")
def public_results(public_uuid: str, db: Session = Depends(get_db)):
    election = (
        db.query(models.Election)
        .filter(models.Election.public_uuid == public_uuid)
        .first()
    )
    if not election:
        raise HTTPException(status_code=404, detail="Rezultatele nu au fost găsite.")

    data = compute_results(db, election)
    data["dashboard_url"] = dashboard_url(election)
    data["public_uuid"] = election.public_uuid
    return data
