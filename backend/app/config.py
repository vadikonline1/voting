"""Application configuration, loaded from environment variables (.env in dev, real env vars in Docker)."""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Core
    secret_key: str = os.environ.get("SECRET_KEY", "change-me-please-super-secret")
    database_url: str = os.environ.get("DATABASE_URL", "sqlite:////data/voting.db")
    data_dir: str = os.environ.get("DATA_DIR", "/data")

    # Admin bootstrap (only used the first time, to create the admin account if none exists)
    admin_username: str = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password: str = os.environ.get("ADMIN_PASSWORD", "schimba-aceasta-parola")

    # Public base URL, used to build voter links (e.g. https://vot.aalto.md)
    public_base_url: str = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000")

    # How many days after the election's end date a voting link keeps resolving
    # (shows a "voting closed" page instead of a 404) before it is considered gone.
    link_grace_days: int = int(os.environ.get("LINK_GRACE_DAYS", "30"))

    class Config:
        env_file = ".env"


settings = Settings()
os.makedirs(settings.data_dir, exist_ok=True)
os.makedirs(os.path.join(settings.data_dir, "signatures"), exist_ok=True)
os.makedirs(os.path.join(settings.data_dir, "receipts"), exist_ok=True)
