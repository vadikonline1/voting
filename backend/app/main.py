import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .database import Base, engine, SessionLocal
from . import models
from .auth import hash_password
from .config import settings
from .routers import ballot, admin

Base.metadata.create_all(bind=engine)


def _bootstrap():
    db = SessionLocal()
    try:
        if not db.query(models.AdminUser).first():
            db.add(models.AdminUser(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
            ))
        if not db.query(models.SmtpSettings).first():
            db.add(models.SmtpSettings(id=1))
        if not db.query(models.Election).first():
            db.add(models.Election(
                title="Exemplu: Adunare Generală APC",
                description="Completează nr. APC, adresa, localitatea și datele din panoul de administrare.",
                nr_apc="12",
                str_apc="str. Exemplu 1",
                oras="Chișinău",
                tip_proprietate="apartament",
                questions_json=(
                    '[{"id":"q1","text":"Aprobarea dării de seamă a administratorului pe anul curent.",'
                    '"type":"single","options":["Da/Pro","Nu/Contra"],"required":true}]'
                ),
                is_active=True,
                require_signature=True,
            ))
        db.commit()
    finally:
        db.close()


_bootstrap()

app = FastAPI(title="Sistem de Vot")

app.include_router(ballot.router)
app.include_router(admin.router)

FRONTEND_DIST = os.environ.get("FRONTEND_DIST", "/app/frontend_dist")

if os.path.isdir(FRONTEND_DIST):
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        """Serves the React SPA for every non-API route, including /{uuid} ballot links
        and /admin — the client-side router decides what to render."""
        candidate = os.path.join(FRONTEND_DIST, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
