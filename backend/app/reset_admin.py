"""Reset the admin password directly in the database.

Works even when the container was started without the variables from `.env`
(and therefore the login credentials are unknown):

    docker compose exec app python -m app.reset_admin --password "parola-noua"

The account is flagged so that the new password must be changed again at the next login
(use --no-force-change to skip that).
"""
import argparse
import getpass

from . import models
from .auth import hash_password
from .config import settings
from .database import SessionLocal


def reset_admin_password(password: str, username: str | None = None, force_change: bool = True) -> str:
    db = SessionLocal()
    try:
        admin = db.query(models.AdminUser).first()
        if not admin:
            admin = models.AdminUser(username=username or settings.admin_username, password_hash="")
            db.add(admin)
            db.flush()
        if username:
            admin.username = username
        admin.password_hash = hash_password(password)
        admin.must_change_password = force_change
        db.commit()
        return admin.username
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Reset the admin password of the voting system.",
    )
    parser.add_argument("--password", help="new password (asked interactively when omitted)")
    parser.add_argument("--username", help="new username (optional)")
    parser.add_argument(
        "--no-force-change",
        action="store_true",
        help="do not require another password change at the next login",
    )
    args = parser.parse_args(argv)

    password = args.password
    if not password:
        password = getpass.getpass("Parola nouă: ")
        if password != getpass.getpass("Repetați parola nouă: "):
            parser.error("parolele nu coincid")
    if len(password) < 8:
        parser.error("parola trebuie să aibă cel puțin 8 caractere")

    username = reset_admin_password(
        password, args.username, force_change=not args.no_force_change
    )
    print(f"Parola contului „{username}” a fost resetată.")
    if not args.no_force_change:
        print("La următoarea autentificare vi se va cere să o schimbați.")


if __name__ == "__main__":
    main()
