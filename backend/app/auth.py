from fastapi import Depends, HTTPException, Request, status
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_serializer = URLSafeTimedSerializer(settings.secret_key, salt="admin-session")

SESSION_COOKIE = "voting_admin_session"
SESSION_MAX_AGE = 60 * 60 * 12  # 12h


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_session_token(username: str) -> str:
    return _serializer.dumps({"username": username})


def read_session_token(token: str) -> str | None:
    try:
        data = _serializer.loads(token, max_age=SESSION_MAX_AGE)
        return data.get("username")
    except (BadSignature, SignatureExpired):
        return None


def get_admin_username(request: Request) -> str:
    """Return the username from a valid admin session cookie, or 401."""
    token = request.cookies.get(SESSION_COOKIE)
    username = read_session_token(token) if token else None
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autentificare necesară")
    return username


def get_current_admin(request: Request, db: Session = Depends(get_db)) -> models.AdminUser:
    """Admin user from the session cookie, without enforcing the password change.

    Used by `/me` and `/change-password`, so the panel can detect and resolve a pending
    password change even though all other admin endpoints are blocked until then.
    """
    username = get_admin_username(request)
    admin = db.query(models.AdminUser).filter(models.AdminUser.username == username).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesiunea de administrare nu mai este validă",
        )
    return admin


def require_admin(admin: models.AdminUser = Depends(get_current_admin)) -> str:
    """Full admin access: the session must be valid and the password must have been changed."""
    if admin.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Trebuie să schimbați parola implicită înainte de a continua.",
        )
    return admin.username
