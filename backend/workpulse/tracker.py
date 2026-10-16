"""Durable session state machine. No keylogging, screenshots or outbound requests."""
import threading
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import ActivitySlice, CategoryRule, UserSettings, WorkSession, IdleReview
from .windows import Foreground

DEFAULT_RULES = [
    ("code.exe", "productive"), ("devenv.exe", "productive"),
    ("pycharm", "productive"), ("excel.exe", "productive"),
    ("winword.exe", "productive"), ("powerpnt.exe", "productive"),
    ("notepad", "productive"), ("terminal", "productive"),
    ("youtube", "non_productive"), ("netflix", "non_productive"),
    ("steam.exe", "non_productive"), ("epicgames", "non_productive"),
    ("discord", "neutral"), ("chrome.exe", "neutral"),
    ("firefox.exe", "neutral"), ("msedge.exe", "neutral"),
]
VALID_STATES = {"productive", "neutral", "non_productive", "idle", "break"}

def naive_utc(dt: datetime) -> datetime:
    """SQLite stores UTC timestamps without an offset; use UTC for every comparison."""
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt

def seed_user(db: Session, user_id: int) -> None:
    if not db.get(UserSettings, user_id):
        db.add(UserSettings(user_id=user_id))
    if not db.scalar(select(CategoryRule.id).where(CategoryRule.user_id == user_id).limit(1)):
        db.add_all(CategoryRule(user_id=user_id, pattern=p, category=c) for p,c in DEFAULT_RULES)
    db.flush()

def classify(db: Session, user_id: int, fg: Foreground) -> str:
    text = (fg.app_name + " " + fg.title).lower()
    rules = db.scalars(select(CategoryRule).where(CategoryRule.user_id == user_id, CategoryRule.enabled == True).order_by(CategoryRule.id)).all()
    # Most specific pattern wins, so "youtube" beats "chrome.exe".
    for rule in sorted(rules, key=lambda r: len(r.pattern), reverse=True):
        if rule.pattern.lower() in text:
            return rule.category
    return "neutral"

def split_midnight(start: datetime, end: datetime):
    """Yield intervals that do not cross a UTC day boundary."""
    while start < end:
        boundary = datetime.combine((start + timedelta(days=1)).date(), datetime.min.time())
        right = min(end, boundary)
        yield start, right
        start = right

class Tracker:
    def __init__(self):
        self.lock = threading.RLock()

    def open_session(self, db: Session, user_id: int) -> WorkSession:
        current = db.scalar(select(WorkSession).where(WorkSession.user_id == user_id, WorkSession.finished_at.is_(None)).order_by(WorkSession.id.desc()))
        if current:
            return current
        now = datetime.utcnow()
        current = WorkSession(user_id=user_id, started_at=now, last_tick_at=now)
        db.add(current)
        db.flush()
        return current

    def transition(self, db: Session, user_id: int, action: str) -> WorkSession:
        with self.lock:
            now = datetime.utcnow()
            current = db.scalar(select(WorkSession).where(WorkSession.user_id == user_id, WorkSession.finished_at.is_(None)).order_by(WorkSession.id.desc()))
            if action == "start":
                result = current or self.open_session(db, user_id)
                result.status = "working"
            elif action == "break" and current:
                if current.status != "working":
                    raise ValueError("Break requires a working session")
                result = current
                result.status = "break"
            elif action == "resume" and current:
                if current.status != "break":
                    raise ValueError("Resume requires a break")
                result = current
                result.status = "working"
            elif action == "finish" and current:
                result = current
                result.finished_at = now
                result.status = "finished"
            else:
                raise ValueError("No active session for this action")
            # Never credit unobserved intervals during a state transition.
            result.last_tick_at = now
            result.state_since = now
            db.flush()
            return result

    def tick(self, db: Session, user_id: int, fg: Foreground, now: datetime | None = None) -> str:
        with self.lock:
            now = naive_utc(now or datetime.now(timezone.utc))
            s = self.open_session(db, user_id)
            settings = db.get(UserSettings, user_id)
            if not settings:
                seed_user(db, user_id)
                settings = db.get(UserSettings, user_id)
            from .enhancements import capture_policy
            policy = capture_policy(db, user_id, fg, now)
            previous = naive_utc(s.last_tick_at)
            gap = (now - previous).total_seconds()
            if policy.skip:
                s.last_tick_at = now
                db.flush()
                return "private"
            foreground = policy.foreground
            classified = classify(db, user_id, policy.original or fg)
            # A calendar event is an opt-in suggestion; user category rules win.
            if policy.meeting and classified == "neutral":
                classified = "productive"
            state = ("break" if s.status == "break" else "idle" if fg.locked or fg.idle_seconds >= settings.idle_threshold else classified)
            # Discard long, unknown intervals caused by sleep / shutdown / crash.
            if gap <= 0 or gap > max(30, settings.poll_interval * 3):
                s.last_tick_at = now
                return state
            last = db.scalar(select(ActivitySlice).where(ActivitySlice.session_id == s.id).order_by(ActivitySlice.id.desc()).limit(1))
            idle_to_review = last if last and last.state == "idle" and last.duration >= 60 and state not in ("idle", "break") else None
            for left, right in split_midnight(previous, now):
                self._record(db, s, left, right, state, foreground, policy.project_id, policy.task_id)
            if idle_to_review and not db.scalar(select(IdleReview.id).where(IdleReview.slice_id == idle_to_review.id)):
                db.add(IdleReview(user_id=user_id, slice_id=idle_to_review.id))
            s.last_tick_at = now
            db.flush()
            return state

    @staticmethod
    def _record(db: Session, session: WorkSession, start: datetime, end: datetime, state: str, fg: Foreground, project_id: int | None = None, task_id: int | None = None):
        app = fg.app_name if state not in ("break", "idle") else ""
        title = fg.title if state not in ("break", "idle") else ""
        last = db.scalar(select(ActivitySlice).where(ActivitySlice.session_id == session.id).order_by(ActivitySlice.id.desc()).limit(1))
        secs = (end - start).total_seconds()
        # Coalesce adjacent identical intervals, limiting DB growth.
        if last and last.state == state and last.app_name == app and last.window_title == title and last.project_id == project_id and last.task_id == task_id and (start - naive_utc(last.ended_at)).total_seconds() <= 1 and last.started_at.date() == start.date():
            last.ended_at = end
            last.duration += secs
        else:
            db.add(ActivitySlice(session_id=session.id, user_id=session.user_id, started_at=start, ended_at=end, duration=secs, state=state, category=state if state not in ("idle", "break") else "neutral", app_name=app, window_title=title, project_id=project_id, task_id=task_id))
