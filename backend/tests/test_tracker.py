from datetime import datetime, timedelta
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from workpulse.db import Base
from workpulse.models import User, WorkSession, ActivitySlice
from workpulse.tracker import Tracker, seed_user
from workpulse.windows import Foreground

def setup():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = Session(engine)
    user = User(full_name="Test", email="test@example.com", password_hash="hash", department="QA")
    db.add(user)
    db.flush()
    seed_user(db, user.id)
    return db, user

def test_productive_classification_and_coalescing():
    db, u = setup()
    t = Tracker()
    start = datetime.utcnow().replace(microsecond=0)
    s = t.open_session(db, u.id)
    s.last_tick_at = start
    assert t.tick(db, u.id, Foreground("Code.exe", "work.py"), start + timedelta(seconds=4)) == "productive"
    assert t.tick(db, u.id, Foreground("Code.exe", "work.py"), start + timedelta(seconds=8)) == "productive"
    slices = db.scalars(select(ActivitySlice)).all()
    assert len(slices) == 1
    assert slices[0].duration == 8

def test_idle_not_counted_as_productive():
    db,u = setup()
    t = Tracker()
    start = datetime.utcnow().replace(microsecond=0)
    t.open_session(db, u.id).last_tick_at = start
    assert t.tick(db, u.id, Foreground("Code.exe", "work.py", idle_seconds=301), start + timedelta(seconds=4)) == "idle"
    assert db.scalar(select(ActivitySlice)).state == "idle"

def test_break_and_resume_transition():
    db,u = setup()
    t = Tracker()
    assert t.transition(db,u.id,"start").status == "working"
    assert t.transition(db,u.id,"break").status == "break"
    s = db.scalar(select(WorkSession))
    s.last_tick_at = datetime.utcnow() - timedelta(seconds=4)
    assert t.tick(db,u.id,Foreground("Code.exe","file")) == "break"
    assert db.scalar(select(ActivitySlice)).state == "break"
    assert t.transition(db,u.id,"resume").status == "working"
    assert t.transition(db,u.id,"finish").status == "finished"

def test_crash_gap_not_billed_and_open_session_reused():
    db,u = setup()
    t = Tracker()
    s = t.open_session(db,u.id)
    s.last_tick_at = datetime.utcnow() - timedelta(hours=4)
    assert t.tick(db,u.id,Foreground("Code.exe", "file")) == "productive"
    assert db.scalar(select(ActivitySlice)) is None
    assert t.open_session(db,u.id).id == s.id

def test_midnight_split():
    from workpulse.tracker import split_midnight
    left = datetime(2026, 10, 15, 23, 59, 58)
    blocks = list(split_midnight(left, left + timedelta(seconds=4)))
    assert len(blocks) == 2
    assert all(a.date() == (b - timedelta(microseconds=1)).date() for a,b in blocks)
