"""Pure SQLite tracker tests: privacy controls, auto-tagging and idle return prompts."""
from datetime import datetime,timedelta
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from workpulse.db import Base
from workpulse.models import (
    User,Project,ProjectRule,PrivacyRule,PrivacySettings,ActivitySlice,IdleReview,
    CalendarMeeting
)
from workpulse.tracker import Tracker,seed_user
from workpulse.windows import Foreground
from workpulse.enhancements import capture_policy

def fresh():
    engine=create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db=Session(engine)
    user=User(full_name="Test User",email="sample@example.test",
              password_hash="mock-hash",department="Tests")
    db.add(user);db.flush();seed_user(db,user.id)
    privacy=PrivacySettings(user_id=user.id)
    db.add(privacy);db.flush()
    return db,user

def test_project_detection_priority_and_title_privacy():
    db,user=fresh()
    project=Project(user_id=user.id,name="Important workspace",client="",hourly_rate=0,budget_hours=0)
    db.add(project);db.flush()
    db.add(ProjectRule(user_id=user.id,project_id=project.id,pattern="special-workspace"))
    db.get(PrivacySettings,user.id).hide_window_titles=True
    db.flush()
    visible=Foreground("Code.exe","special-workspace confidential notes",0)
    captured=capture_policy(db,user.id,visible,datetime.utcnow())
    assert captured.project_id==project.id
    assert captured.foreground.title==""
    assert captured.original.title==visible.title
    tracker=Tracker()
    now=datetime.utcnow().replace(microsecond=0)
    tracker.open_session(db,user.id).last_tick_at=now
    assert tracker.tick(db,user.id,visible,now+timedelta(seconds=4))=="productive"
    entry=db.scalar(select(ActivitySlice))
    assert entry.window_title==""
    assert entry.project_id==project.id

def test_excluded_apps_and_manual_pause_prevent_storage():
    db,user=fresh()
    db.add(PrivacyRule(user_id=user.id,pattern="secretviewer",action="exclude"))
    tracker=Tracker()
    now=datetime.utcnow().replace(microsecond=0)
    tracker.open_session(db,user.id).last_tick_at=now
    assert tracker.tick(db,user.id,Foreground("secretviewer.exe","Private"),now+timedelta(seconds=4))=="private"
    assert db.scalar(select(ActivitySlice)) is None
    privacy=db.get(PrivacySettings,user.id)
    privacy.paused=True
    db.flush()
    assert tracker.tick(db,user.id,Foreground("Code.exe","Repository"),now+timedelta(seconds=8))=="private"
    assert db.scalar(select(ActivitySlice)) is None

def test_idle_prompt_when_returning_from_keyboard_inactivity():
    db,user=fresh()
    tracker=Tracker()
    now=datetime.utcnow().replace(microsecond=0)
    tracker.open_session(db,user.id).last_tick_at=now
    for seconds in range(4,84,4):
        tracker.tick(db,user.id,Foreground("Code.exe","Workspace",idle_seconds=800),now+timedelta(seconds=seconds))
    assert tracker.tick(db,user.id,Foreground("Code.exe","Workspace",idle_seconds=0),now+timedelta(seconds=84))=="productive"
    db.flush()
    review=db.scalar(select(IdleReview))
    assert review is not None
    sl=db.get(ActivitySlice,review.slice_id)
    assert sl.state=="idle" and sl.duration>=60

def test_opt_in_calendar_meeting_without_category_rule():
    db,user=fresh()
    now=datetime.utcnow().replace(microsecond=0)
    db.get(PrivacySettings,user.id).meeting_opt_in=True
    db.add(CalendarMeeting(user_id=user.id,external_uid="local-calendar-test",
        title="Planning",starts_at=now-timedelta(minutes=2),
        ends_at=now+timedelta(minutes=20)))
    db.flush()
    tracker=Tracker()
    tracker.open_session(db,user.id).last_tick_at=now
    state=tracker.tick(db,user.id,Foreground("teams.exe","Planning",idle_seconds=0),
        now+timedelta(seconds=4))
    assert state=="productive"
