"""Local SQLite configuration. All timestamps are timezone-aware UTC in application code."""
import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

def data_directory() -> Path:
    root = os.getenv("WORKPULSE_DATA_DIR")
    p = Path(root) if root else Path(os.getenv("LOCALAPPDATA", Path.home() / ".local" / "share")) / "WorkPulse"
    p.mkdir(parents=True, exist_ok=True)
    return p

def database_url() -> str:
    return "sqlite:///" + str(data_directory() / "workpulse.db").replace("\\", "/")

engine = create_engine(database_url(), connect_args={"check_same_thread": False, "timeout": 30})

@event.listens_for(engine, "connect")
def configure_sqlite(conn, _):
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA busy_timeout=30000")
    cur.close()

class Base(DeclarativeBase):
    pass

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def migrate() -> None:
    """Upgrade schema on startup, also inside PyInstaller's _MEIPASS bundle."""
    from alembic import command
    from alembic.config import Config
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url())
    command.upgrade(cfg, "head")
