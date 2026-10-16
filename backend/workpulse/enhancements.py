"""Privacy-first enrichment of captured Windows activity.

Only foreground metadata is processed. Browser integration is strictly opt-in and
uses a short-lived domain hint, never full URLs or page content.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import ActiveAssignment, CalendarMeeting, PrivacyRule, PrivacySettings, ProjectRule, WorkTask
from .windows import Foreground

BROWSERS={"chrome.exe","msedge.exe","firefox.exe","brave.exe","opera.exe","vivaldi.exe"}
_browser_hints:dict[int,tuple[str,datetime]]={}

def set_browser_hint(user_id:int, hostname:str):
    _browser_hints[user_id]=(hostname.lower(),datetime.utcnow())

def foreground_with_domain(db:Session,user_id:int,fg:Foreground,now:datetime)->Foreground:
    p=db.get(PrivacySettings,user_id)
    if not p or not p.browser_opt_in or fg.app_name.lower() not in BROWSERS:
        return fg
    hint=_browser_hints.get(user_id)
    if not hint or (now-hint[1]).total_seconds()>10:
        return fg
    return Foreground(fg.app_name,(fg.title+" ["+hint[0]+"]")[:500],fg.idle_seconds,fg.locked)

@dataclass
class CapturePolicy:
    skip:bool
    foreground:Foreground
    project_id:int|None=None
    task_id:int|None=None
    meeting:bool=False

def capture_policy(db:Session,user_id:int,fg:Foreground,now:datetime)->CapturePolicy:
    settings=db.get(PrivacySettings,user_id)
    if settings and (settings.paused or (settings.paused_until and settings.paused_until>now)):
        return CapturePolicy(True,Foreground(idle_seconds=fg.idle_seconds,locked=fg.locked))
    fg=foreground_with_domain(db,user_id,fg,now)
    title=fg.title
    full=(fg.app_name+" "+title).lower()
    mask=bool(settings and settings.hide_window_titles)
    for rule in db.scalars(select(PrivacyRule).where(PrivacyRule.user_id==user_id)):
        if rule.pattern.lower() in full:
            if rule.action=="exclude":
                return CapturePolicy(True,Foreground(idle_seconds=fg.idle_seconds,locked=fg.locked))
            if rule.action=="mask":mask=True
    assignment=db.get(ActiveAssignment,user_id)
    project_id=assignment.project_id if assignment else None
    task_id=assignment.task_id if assignment else None
    if not project_id:
        rules=db.scalars(select(ProjectRule).where(ProjectRule.user_id==user_id)).all()
        for rule in sorted(rules,key=lambda r:len(r.pattern),reverse=True):
            if rule.pattern.lower() in full:
                project_id=rule.project_id
                break
    # A project can be selected automatically; tasks are only pinned explicitly.
    if not project_id:
        task_id=None
    meeting=False
    if settings and settings.meeting_opt_in:
        meeting=bool(db.scalar(select(CalendarMeeting.id).where(
            CalendarMeeting.user_id==user_id,
            CalendarMeeting.starts_at<=now,CalendarMeeting.ends_at>now
        ).limit(1)))
    return CapturePolicy(False,Foreground(fg.app_name,"" if mask else title,fg.idle_seconds,fg.locked),project_id,task_id,meeting)

def retention_cleanup(db:Session,user_id:int,now:datetime|None=None)->int:
    from .models import ActivitySlice,IdleReview,ManualEntry
    now=now or datetime.utcnow()
    prefs=db.get(PrivacySettings,user_id)
    if not prefs or prefs.retention_days<=0:return 0
    cutoff=now-timedelta(days=prefs.retention_days)
    oldids=db.scalars(select(ActivitySlice.id).where(ActivitySlice.user_id==user_id,ActivitySlice.ended_at<cutoff)).all()
    if oldids:
        db.query(IdleReview).filter(IdleReview.user_id==user_id,IdleReview.slice_id.in_(oldids)).delete(synchronize_session=False)
    count=db.query(ActivitySlice).filter(ActivitySlice.user_id==user_id,ActivitySlice.ended_at<cutoff).delete(synchronize_session=False)
    count+=db.query(ManualEntry).filter(ManualEntry.user_id==user_id,ManualEntry.ended_at<cutoff).delete(synchronize_session=False)
    return count
