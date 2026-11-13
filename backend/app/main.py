import os
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .database import Base, engine, SessionLocal
from . import models
from .auth import hash_password, verify_password
from .config import settings
from .routers import ballot, admin

Base.metadata.create_all(bind=engine)

# Initial/example passwords shipped in the docs or earlier releases. If an existing database
# still uses one of them, the owner is asked to change it at the next login.
LEGACY_DEFAULT_PASSWORDS = ("admin", "change-this-password", "schimba-aceasta-parola")
ADMIN_RESET_MARKER = ".admin-reset-used"


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
        "admin_users": {
            "must_change_password": "BOOLEAN DEFAULT 0",
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
        admin_user = db.query(models.AdminUser).first()
        reset_marker = os.path.join(settings.data_dir, ADMIN_RESET_MARKER)

        if not admin_user:
            db.add(models.AdminUser(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                must_change_password=True,
            ))
            print(
                "[bootstrap] Cont de administrare creat. "
                "Autentificați-vă și schimbați parola la prima conectare."
            )
        elif settings.admin_reset_password and not os.path.exists(reset_marker):
            # One-shot recovery for a database with an unknown/forgotten password.
            admin_user.username = settings.admin_username or admin_user.username
            admin_user.password_hash = hash_password(settings.admin_password)
            admin_user.must_change_password = True
            try:
                with open(reset_marker, "w", encoding="utf-8") as fh:
                    fh.write(datetime.now(timezone.utc).isoformat())
            except OSError:
                pass
            print(
                "[bootstrap] Parola de administrare a fost resetată din ADMIN_PASSWORD. "
                "Schimbați-o după autentificare."
            )
        elif not admin_user.must_change_password:
            # Existing installation created before the "must change password" flag existed:
            # detect the old default/example passwords and force a change on next login.
            for candidate in LEGACY_DEFAULT_PASSWORDS:
                try:
                    if verify_password(candidate, admin_user.password_hash):
                        admin_user.must_change_password = True
                        break
                except Exception:  # noqa: BLE001 - never block startup because of a hash issue
                    break

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
