import os
import json
from pathlib import Path

def secret(name):
    value=os.getenv(name)
    if value:
        return value
    path=Path(os.getenv("GATEARR_SECRETS_FILE","/data/bootstrap.json"))
    return json.loads(path.read_text()).get(name,"") if path.exists() else ""
from dataclasses import dataclass

@dataclass
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:////data/gatearr.db")
    secret_key: str = secret("SECRET_KEY")
    media_server: str = os.getenv("MEDIA_SERVER", "emby")
    public_url: str = os.getenv("PUBLIC_URL", "http://localhost:8000").rstrip("/")
    app_name: str = os.getenv("APP_NAME", "Gatearr")
    secure_cookie: bool = os.getenv("COOKIE_SECURE", "true").lower() == "true"
    sync_minutes: int = int(os.getenv("SYNC_INTERVAL_MINUTES", "30"))

settings = Settings()
