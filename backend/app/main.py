import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .database import Base, engine, SessionLocal
from . import models
from .auth import hash_password
from .config import settings
from .routers import ballot, admin

Base.metadata.create_all(bind=engine)


def _migrate_sqlite():
    """Add columns introduced after the initial release to an existing SQLite database.

    `Base.metadata.create_all` only creates missing tables; it never alters existing ones.
    These lightweight, idempotent ALTERs keep an existing /data/voting.db usable after an image
    update, without requiring a full migration tool.
    """
    if not settings.database_url.startswith("sqlite"):
        return
    additions = {
        "elections": {
            "email_with_attachment": "BOOLEAN DEFAULT 1",
            "email_cc": "VARCHAR DEFAULT ''",
            "email_bcc": "VARCHAR DEFAULT ''",
        },
        "votes": {
            "gdpr_consent_at": "DATETIME",
        },
    }
    with engine.begin() as conn:
        for table, columns in additions.items():
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


_migrate_sqlite()


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
                    '[{"id":"q1","number":"1","text":"Aprobarea dării de seamă a administratorului pe anul curent.",'
                    '"type":"single","options":["Pentru","Împotriva"],"required":true}]'
                ),
                is_active=True,
                require_signature=True,
            ))
        db.commit()
    finally:
        db.close()


_bootstrap()

app = FastAPI(title="Sistem de Vot")


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return a readable message instead of the default list of Pydantic errors."""
    messages = []
    for err in exc.errors():
        location = " → ".join(str(part) for part in err.get("loc", ()) if part != "body")
        message = err.get("msg", "valoare invalidă")
        messages.append(f"{location}: {message}" if location else message)
    detail = "; ".join(messages) or "Datele trimise nu sunt valide."
    return JSONResponse(status_code=422, content={"detail": detail})


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
