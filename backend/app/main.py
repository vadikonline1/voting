import json
import os
import threading
import time
import uuid
from contextlib import asynccontextmanager
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
from .notifications import send_expiry_reminders, send_pending_final_results
from .routers import ballot, admin, public

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
            "public_uuid": "VARCHAR",
            "results_email": "VARCHAR DEFAULT ''",
            "notify_results_on_vote": "BOOLEAN DEFAULT 1",
            "results_final_email_sent_at": "DATETIME",
            "expiry_reminders_json": "TEXT DEFAULT '{}'",
            "properties_json": "TEXT DEFAULT '[]'",
            "allow_multiple_properties": "BOOLEAN DEFAULT 1",
        },
        "voter_tokens": {
            "tip_proprietate": "VARCHAR DEFAULT 'apartament'",
            "properties_json": "TEXT DEFAULT '[]'",
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

        # Existing elections predate the public dashboard: give each one a random identifier.
        rows = conn.execute(
            text("SELECT id FROM elections WHERE public_uuid IS NULL OR public_uuid = ''")
        ).fetchall()
        for (election_id,) in rows:
            conn.execute(
                text("UPDATE elections SET public_uuid = :value WHERE id = :id"),
                {"value": uuid.uuid4().hex, "id": election_id},
            )
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_elections_public_uuid "
            "ON elections (public_uuid)"
        ))


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
                title="Alegerea președintelui și secretarului Adunării Generale Mixte",
                description="Exemplu de formulare. Completați nr. APC, adresa, localitatea și datele din panoul de administrare.",
                nr_apc="12",
                str_apc="str. Exemplu 1",
                oras="Chișinău",
                tip_proprietate="apartament",
                questions_json=json.dumps([
                    {"id": "q1", "number": "1", "text": "Președintele adunării, dna Anastasia Malec", "type": "single", "options": ["Pentru", "Împotriva"], "required": True},
                    {"id": "q2", "number": "2", "text": "Președintele adunării, dna Anaia Mac", "type": "single", "options": ["Pentru", "Împotriva"], "required": True},
                ], ensure_ascii=False),
                is_active=False,  # exemplul nu este activ, ca să nu blocheze linkul APC real
                require_signature=True,
            ))
        db.commit()
    finally:
        db.close()


_bootstrap()


def _run_results_scheduler(stop_event: threading.Event, interval_seconds: int = 300) -> None:
    """Light-weight background loop: sends the final results report once per election,
    shortly after its end date has passed."""
    while not stop_event.wait(interval_seconds):
        db = SessionLocal()
        try:
            sent = send_pending_final_results(db)
            if sent:
                print(f"[results] Raport final trimis pentru {sent} vot(uri).")
            reminders = send_expiry_reminders(db)
            if reminders:
                print(f"[reminders] Înștiințări de expirare trimise: {reminders}.")
        except Exception as exc:  # noqa: BLE001 - the scheduler must never kill the app
            print(f"[results] Verificarea rapoartelor finale a eșuat: {exc}")
        finally:
            db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    stop_event = threading.Event()
    thread = threading.Thread(
        target=_run_results_scheduler, args=(stop_event,), daemon=True,
        name="results-final-email",
    )
    thread.start()
    try:
        yield
    finally:
        stop_event.set()


app = FastAPI(title="Sistem de Vot", lifespan=lifespan)


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
app.include_router(public.router)

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
