"""Polling worker; writes in small committed transactions and does not send data off-device."""
import logging
import threading
from datetime import datetime, timezone
from sqlalchemy import select
from .db import SessionLocal
from .models import User, WorkSession
from .tracker import Tracker
from .windows import observe

logger = logging.getLogger("workpulse")
tracker = Tracker()
wake = threading.Event()
stopping = threading.Event()
last_state = "finished"
foreground = {"app_name": "", "title": ""}
_latest_user: int | None = None

def set_user(user_id: int | None):
    global _latest_user
    _latest_user = user_id
    wake.set()

def run():
    global last_state, foreground
    while not stopping.is_set():
        poll = 4
        user_id = _latest_user
        if user_id:
            try:
                with SessionLocal() as db:
                    from .models import UserSettings
                    config = db.get(UserSettings, user_id)
                    if config:
                        poll = config.poll_interval
                    opened = db.scalar(select(WorkSession).where(WorkSession.user_id == user_id,
                                                WorkSession.finished_at.is_(None)).order_by(WorkSession.id.desc()))
                    if opened:
                        fg = observe()
                        foreground = {"app_name": fg.app_name, "title": fg.title}
                        last_state = tracker.tick(db, user_id, fg)
                        db.commit()
                    else:
                        last_state, foreground = "finished", {"app_name": "", "title": ""}
            except Exception:
                logger.exception("Tracker poll failed; retrying")
        wake.wait(timeout=poll)
        wake.clear()

def launch():
    worker = threading.Thread(target=run, name="workpulse-tracker", daemon=True)
    worker.start()
    return worker

def stop():
    stopping.set()
    wake.set()

def restore_user_session():
    """Resume unfinished session on restart, never silently start a finished day."""
    with SessionLocal() as db:
        opened = db.scalar(select(WorkSession).where(WorkSession.finished_at.is_(None)).order_by(WorkSession.id.desc()))
        if opened:
            set_user(opened.user_id)
