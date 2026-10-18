from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from .settings import settings

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False, "timeout": 20} if settings.database_url.startswith("sqlite") else {})
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def sqlite_options(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
SessionLocal = sessionmaker(engine, expire_on_commit=False)
