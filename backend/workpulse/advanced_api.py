"""Authenticated local-only WorkPulse v2 REST extensions.

All write endpoints are scoped to the logged-in user; there is intentionally no
remote team administration endpoint.
"""
import hashlib
import json
import secrets
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from . import agent
from .security import current_user, get_db
from .models import (User, Project, WorkTask, ProjectRule, ActiveAssignment,
    PrivacySettings, PrivacyRule, ActivitySlice, ManualEntry, IdleReview,
    FocusBlock, CalendarMeeting, WorkSession, DashboardPreference)
from .stats import bounds, day_stats, period_stats
from .enhancements import retention_cleanup

router=APIRouter(prefix="/v2",tags=["WorkPulse v2"])

DASHBOARD_SECTIONS={"metrics","goal","charts","apps","timeline"}

class DashboardIn(BaseModel):
    sections:list[Literal["metrics","goal","charts","apps","timeline"]]=Field(max_length=5)

@router.get("/dashboard")
def get_dashboard(user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=db.get(DashboardPreference,user.id)
    if not row:
        return {"sections":["metrics","goal","charts","apps","timeline"]}
    try:
        sections=json.loads(row.sections)
    except (TypeError,ValueError):
        sections=[]
    return {"sections":[x for x in sections if x in DASHBOARD_SECTIONS]}

@router.put("/dashboard")
def save_dashboard(body:DashboardIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    # Stable order plus unique IDs prevents duplicate panels and preserves the
    # order selected in the desktop customizer.
    sections=list(dict.fromkeys(body.sections))
    row=db.get(DashboardPreference,user.id)
    if row is None:
        row=DashboardPreference(user_id=user.id,sections=json.dumps(sections));db.add(row)
    else:
        row.sections=json.dumps(sections)
    db.commit()
    return {"sections":sections}

def as_dict(obj, fields):
    return {field: ((getattr(obj,field).astimezone(timezone.utc).replace(tzinfo=None) if getattr(obj,field).tzinfo else getattr(obj,field)).isoformat()+"Z" if isinstance(getattr(obj,field),datetime) else getattr(obj,field)) for field in fields}

def owned(db, model, object_id, user_id):
    row=db.get(model,object_id)
    if row is None or row.user_id!=user_id:raise HTTPException(404,"Item not found")
    return row

class ProjectIn(BaseModel):
    name:str=Field(min_length=1,max_length=120)
    client:str=Field(default="",max_length=120)
    hourly_rate:float=Field(default=0,ge=0,le=1000000)
    budget_hours:float=Field(default=0,ge=0,le=100000)
    archived:bool=False

class TaskIn(BaseModel):
    project_id:int
    name:str=Field(min_length=1,max_length=160)
    status:Literal["todo","doing","done"]="todo"
    estimate_minutes:int=Field(default=0,ge=0,le=100000)

class ProjectRuleIn(BaseModel):
    project_id:int
    pattern:str=Field(min_length=2,max_length=160)

class AssignmentIn(BaseModel):
    project_id:int|None=None
    task_id:int|None=None

@router.get("/projects")
def projects(user:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(Project).where(Project.user_id==user.id).order_by(Project.name)).all()
    return [as_dict(p,("id","name","client","hourly_rate","budget_hours","archived")) for p in rows]

@router.post("/projects",status_code=201)
def create_project(body:ProjectIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=Project(user_id=user.id,**body.model_dump())
    db.add(row)
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,"Project name already exists")
    return as_dict(row,("id","name","client","hourly_rate","budget_hours","archived"))

@router.patch("/projects/{item_id}")
def edit_project(item_id:int,body:ProjectIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=owned(db,Project,item_id,user.id)
    for k,v in body.model_dump().items():setattr(row,k,v)
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,"Project name already exists")
    return as_dict(row,("id","name","client","hourly_rate","budget_hours","archived"))

@router.get("/tasks")
def tasks(project_id:int|None=None,user:User=Depends(current_user),db:Session=Depends(get_db)):
    stmt=select(WorkTask).where(WorkTask.user_id==user.id).order_by(WorkTask.id.desc())
    if project_id is not None:
        owned(db,Project,project_id,user.id)
        stmt=stmt.where(WorkTask.project_id==project_id)
    return [as_dict(t,("id","project_id","name","status","estimate_minutes")) for t in db.scalars(stmt)]

@router.post("/tasks",status_code=201)
def create_task(body:TaskIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    owned(db,Project,body.project_id,user.id)
    row=WorkTask(user_id=user.id,**body.model_dump());db.add(row);db.commit()
    return as_dict(row,("id","project_id","name","status","estimate_minutes"))

@router.patch("/tasks/{item_id}")
def edit_task(item_id:int,body:TaskIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=owned(db,WorkTask,item_id,user.id)
    owned(db,Project,body.project_id,user.id)
    for k,v in body.model_dump().items():setattr(row,k,v)
    db.commit()
    return as_dict(row,("id","project_id","name","status","estimate_minutes"))

@router.get("/project-rules")
def project_rules(user:User=Depends(current_user),db:Session=Depends(get_db)):
    return [as_dict(r,("id","project_id","pattern")) for r in db.scalars(select(ProjectRule).where(ProjectRule.user_id==user.id))]

@router.post("/project-rules",status_code=201)
def add_project_rule(body:ProjectRuleIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    owned(db,Project,body.project_id,user.id)
    row=ProjectRule(user_id=user.id,pattern=body.pattern.strip().lower(),project_id=body.project_id)
    db.add(row)
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,"Pattern already exists")
    return as_dict(row,("id","project_id","pattern"))

@router.delete("/project-rules/{item_id}",status_code=204)
def remove_project_rule(item_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    db.delete(owned(db,ProjectRule,item_id,user.id));db.commit()

@router.get("/assignment")
def active_assignment(user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=db.get(ActiveAssignment,user.id)
    return {"project_id":row.project_id if row else None,"task_id":row.task_id if row else None}

@router.put("/assignment")
def set_assignment(body:AssignmentIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if body.project_id is not None:owned(db,Project,body.project_id,user.id)
    if body.task_id is not None:
        task=owned(db,WorkTask,body.task_id,user.id)
        if task.project_id!=body.project_id:raise HTTPException(422,"Task does not belong to the selected project")
    with agent.tracker.lock:
        row=db.get(ActiveAssignment,user.id)
        if row is None:row=ActiveAssignment(user_id=user.id);db.add(row)
        row.project_id=body.project_id
        row.task_id=body.task_id
        # Avoid assigning part of an earlier interval to a newly chosen task.
        opened=db.scalar(select(WorkSession).where(WorkSession.user_id==user.id,WorkSession.finished_at.is_(None)))
        if opened:opened.last_tick_at=datetime.utcnow()
        db.commit()
    return body.model_dump()

class PrivacyIn(BaseModel):
    paused:bool|None=None
    hide_window_titles:bool|None=None
    retention_days:int|None=Field(default=None,ge=1,le=3650)
    browser_opt_in:bool|None=None
    ai_opt_in:bool|None=None
    meeting_opt_in:bool|None=None

class PrivacyRuleIn(BaseModel):
    pattern:str=Field(min_length=2,max_length=120)
    action:Literal["exclude","mask"]="exclude"

def get_privacy(db,user_id):
    row=db.get(PrivacySettings,user_id)
    if row is None:
        row=PrivacySettings(user_id=user_id)
        db.add(row);db.flush()
    return row

PRIVACY_FIELDS=("paused","hide_window_titles","retention_days","browser_opt_in","ai_opt_in","meeting_opt_in")

@router.get("/privacy")
def privacy(user:User=Depends(current_user),db:Session=Depends(get_db)):
    return as_dict(get_privacy(db,user.id),PRIVACY_FIELDS)

@router.patch("/privacy")
def edit_privacy(body:PrivacyIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    with agent.tracker.lock:
        row=get_privacy(db,user.id)
        for k,v in body.model_dump(exclude_none=True).items():setattr(row,k,v)
        active=db.scalar(select(WorkSession).where(WorkSession.user_id==user.id,WorkSession.finished_at.is_(None)))
        if active:active.last_tick_at=datetime.utcnow()
        db.commit()
    return as_dict(row,PRIVACY_FIELDS)

@router.get("/privacy/rules")
def privacy_rules(user:User=Depends(current_user),db:Session=Depends(get_db)):
    return [as_dict(r,("id","pattern","action")) for r in db.scalars(select(PrivacyRule).where(PrivacyRule.user_id==user.id))]

@router.post("/privacy/rules",status_code=201)
def add_privacy_rule(body:PrivacyRuleIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=PrivacyRule(user_id=user.id,pattern=body.pattern.strip().lower(),action=body.action)
    db.add(row)
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,"Pattern already exists")
    return as_dict(row,("id","pattern","action"))

@router.delete("/privacy/rules/{item_id}",status_code=204)
def delete_privacy_rule(item_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    db.delete(owned(db,PrivacyRule,item_id,user.id));db.commit()

@router.post("/privacy/pause")
def pause_tracking(user:User=Depends(current_user),db:Session=Depends(get_db)):
    return edit_privacy(PrivacyIn(paused=True),user,db)

@router.post("/privacy/resume")
def resume_tracking(user:User=Depends(current_user),db:Session=Depends(get_db)):
    return edit_privacy(PrivacyIn(paused=False),user,db)

@router.post("/privacy/purge")
def purge_old(user:User=Depends(current_user),db:Session=Depends(get_db)):
    count=retention_cleanup(db,user.id);db.commit()
    return {"deleted":count}

@router.get("/idle/pending")
def pending_idle(user:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(IdleReview).where(IdleReview.user_id==user.id,IdleReview.resolved==False).order_by(IdleReview.id.desc()).limit(10)).all()
    result=[]
    for r in rows:
        sl=db.get(ActivitySlice,r.slice_id)
        if sl:result.append({"id":r.id,"start":sl.started_at.isoformat()+"Z","end":sl.ended_at.isoformat()+"Z","seconds":sl.duration})
    return result

class IdleDecision(BaseModel):
    decision:Literal["productive","neutral","break","keep_idle"]
    project_id:int|None=None
    task_id:int|None=None

@router.post("/idle/{item_id}/resolve")
def resolve_idle(item_id:int,body:IdleDecision,user:User=Depends(current_user),db:Session=Depends(get_db)):
    with agent.tracker.lock:
        row=owned(db,IdleReview,item_id,user.id)
        if row.resolved:raise HTTPException(409,"Already resolved")
        sl=owned(db,ActivitySlice,row.slice_id,user.id)
        if body.project_id is not None:owned(db,Project,body.project_id,user.id)
        if body.task_id is not None:
            task=owned(db,WorkTask,body.task_id,user.id)
            if task.project_id!=body.project_id:raise HTTPException(422,"Task/project mismatch")
        if body.decision!="keep_idle":
            sl.state=body.decision
            sl.category=body.decision if body.decision!="break" else "neutral"
            sl.project_id=body.project_id
            sl.task_id=body.task_id
        row.resolved=True
        db.commit()
    return {"resolved":True,"state":sl.state}

class ManualIn(BaseModel):
    started_at:datetime
    ended_at:datetime
    state:Literal["productive","neutral","break"]="productive"
    note:str=Field(default="",max_length=300)
    project_id:int|None=None
    task_id:int|None=None

def utc_naive(dt:datetime):
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt

@router.get("/manual")
def manual_entries(day:date=Query(default_factory=date.today),tz:int=Query(default=0,ge=-840,le=840),user:User=Depends(current_user),db:Session=Depends(get_db)):
    # Interpret the requested date in the user's local timezone, matching the
    # dashboard and the rest of the reporting API (tz = UTC - local minutes).
    start,end=bounds(day,tz)
    return [as_dict(x,("id","started_at","ended_at","state","note","project_id","task_id")) for x in db.scalars(select(ManualEntry).where(ManualEntry.user_id==user.id,ManualEntry.ended_at>start,ManualEntry.started_at<end))]

@router.post("/manual",status_code=201)
def create_manual(body:ManualIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    start,end=utc_naive(body.started_at),utc_naive(body.ended_at)
    if end<=start or end-start>timedelta(hours=24) or end>datetime.utcnow()+timedelta(minutes=5):
        raise HTTPException(422,"Use a valid past interval under 24 hours")
    if body.project_id is not None:owned(db,Project,body.project_id,user.id)
    if body.task_id is not None:
        task=owned(db,WorkTask,body.task_id,user.id)
        if task.project_id!=body.project_id:raise HTTPException(422,"Task/project mismatch")
    # No double-counting: reject overlaps with any tracked segment or manual segment.
    existing=db.scalar(select(ActivitySlice.id).where(ActivitySlice.user_id==user.id,ActivitySlice.started_at<end,ActivitySlice.ended_at>start).limit(1))
    existing_manual=db.scalar(select(ManualEntry.id).where(ManualEntry.user_id==user.id,ManualEntry.started_at<end,ManualEntry.ended_at>start).limit(1))
    if existing or existing_manual:raise HTTPException(409,"Time overlaps recorded activity; use idle recovery for tracked idle time")
    row=ManualEntry(user_id=user.id,started_at=start,ended_at=end,**body.model_dump(exclude={"started_at","ended_at"}))
    db.add(row);db.commit()
    return as_dict(row,("id","started_at","ended_at","state","note","project_id","task_id"))

@router.delete("/manual/{item_id}",status_code=204)
def delete_manual(item_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    db.delete(owned(db,ManualEntry,item_id,user.id));db.commit()

class FocusStart(BaseModel):
    minutes:int=Field(default=25,ge=5,le=180)
    task_id:int|None=None

def close_expired_focus(db,row):
    if row and row.status=="running" and (datetime.utcnow()-row.started_at)>=timedelta(minutes=row.duration_minutes):
        row.status="completed";row.finished_at=row.started_at+timedelta(minutes=row.duration_minutes)
        db.commit()

@router.get("/focus")
def focus(user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=db.scalar(select(FocusBlock).where(FocusBlock.user_id==user.id).order_by(FocusBlock.id.desc()))
    close_expired_focus(db,row)
    return as_dict(row,("id","started_at","finished_at","duration_minutes","status","task_id")) if row else None

@router.post("/focus/start")
def start_focus(body:FocusStart,user:User=Depends(current_user),db:Session=Depends(get_db)):
    previous=db.scalar(select(FocusBlock).where(FocusBlock.user_id==user.id,FocusBlock.status=="running"))
    if previous:
        close_expired_focus(db,previous)
        if previous.status=="running":raise HTTPException(409,"Finish the current focus session first")
    if body.task_id is not None:owned(db,WorkTask,body.task_id,user.id)
    row=FocusBlock(user_id=user.id,task_id=body.task_id,duration_minutes=body.minutes)
    db.add(row);db.commit()
    return as_dict(row,("id","started_at","finished_at","duration_minutes","status","task_id"))

@router.post("/focus/finish")
def finish_focus(user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=db.scalar(select(FocusBlock).where(FocusBlock.user_id==user.id,FocusBlock.status=="running").order_by(FocusBlock.id.desc()))
    if not row:raise HTTPException(409,"No running focus session")
    close_expired_focus(db,row)
    if row.status=="running":row.finished_at=datetime.utcnow();row.status="finished";db.commit()
    return {"status":row.status}

@router.get("/attendance")
def attendance(year:int=Query(ge=2000,le=2100),month:int=Query(ge=1,le=12),
               tz:int=Query(default=0,ge=-840,le=840),user:User=Depends(current_user),db:Session=Depends(get_db)):
    first=date(year,month,1);next_month=date(year+1,1,1) if month==12 else date(year,month+1,1)
    period=period_stats(db,user.id,first,(next_month-first).days,tz)
    from .models import UserSettings
    settings=db.get(UserSettings,user.id);target=(settings.daily_goal_minutes if settings else 480)*60
    return {"days":[{"date":d["date"],"work":d["work"],"productivity":d["productivity"],
                     "goal_met":d["work"]>=target,"status":"worked" if d["work"]>0 else "no_activity"} for d in period["days"]],
            "total_work":period["totals"]["work"],"goal_days":sum(d["work"]>=target for d in period["days"])}

@router.get("/projects/analytics")
def project_analytics(start:date=Query(default_factory=lambda:date.today()-timedelta(days=6)),
                      end:date=Query(default_factory=date.today),
                      tz:int=Query(default=0,ge=-840,le=840),
                      user:User=Depends(current_user),db:Session=Depends(get_db)):
    if end<start or (end-start).days>365:raise HTTPException(422,"Range must be 0–365 days")
    left,_=bounds(start,tz)
    _,right=bounds(end,tz)
    tracked=db.scalars(select(ActivitySlice).where(ActivitySlice.user_id==user.id,ActivitySlice.started_at<right,ActivitySlice.ended_at>left,ActivitySlice.project_id.is_not(None))).all()
    manual=db.scalars(select(ManualEntry).where(ManualEntry.user_id==user.id,ManualEntry.started_at<right,ManualEntry.ended_at>left,ManualEntry.project_id.is_not(None))).all()
    seconds=defaultdict(float)
    for row in tracked:
        if row.state in ("productive","neutral"):seconds[row.project_id]+=max(0,(min(right,row.ended_at)-max(left,row.started_at)).total_seconds())
    for row in manual:
        if row.state in ("productive","neutral"):seconds[row.project_id]+=max(0,(min(right,row.ended_at)-max(left,row.started_at)).total_seconds())
    projects=db.scalars(select(Project).where(Project.user_id==user.id)).all()
    return [{"id":p.id,"name":p.name,"client":p.client,"seconds":round(seconds[p.id],6),"hours":round(seconds[p.id]/3600,2),
             "hourly_rate":p.hourly_rate,"billable":round(seconds[p.id]/3600*p.hourly_rate,2),
             "budget_hours":p.budget_hours} for p in projects]

@router.get("/insights")
def local_insights(user:User=Depends(current_user),db:Session=Depends(get_db)):
    from .insights import generate
    return generate(db,user.id)

@router.post("/insights/ai")
def ai_insights(user:User=Depends(current_user),db:Session=Depends(get_db)):
    prefs=get_privacy(db,user.id)
    if not prefs.ai_opt_in:raise HTTPException(403,"Enable local AI insights in Privacy settings")
    from .insights import ask_local_ollama
    return {"text":ask_local_ollama(local_insights(user,db))}


@router.get("/tasks/analytics")
def task_analytics(start:date=Query(default_factory=lambda:date.today()-timedelta(days=6)),
                   end:date=Query(default_factory=date.today),
                   tz:int=Query(default=0,ge=-840,le=840),
                   user:User=Depends(current_user),db:Session=Depends(get_db)):
    if end<start or (end-start).days>365:raise HTTPException(422,"Range must be 0–365 days")
    left,_=bounds(start,tz)
    _,right=bounds(end,tz)
    tracked=db.scalars(select(ActivitySlice).where(ActivitySlice.user_id==user.id,
        ActivitySlice.started_at<right,ActivitySlice.ended_at>left,ActivitySlice.task_id.is_not(None))).all()
    manual=db.scalars(select(ManualEntry).where(ManualEntry.user_id==user.id,
        ManualEntry.started_at<right,ManualEntry.ended_at>left,ManualEntry.task_id.is_not(None))).all()
    seconds=defaultdict(float)
    for item in [*tracked,*manual]:
        if item.state in ("productive","neutral"):
            seconds[item.task_id]+=max(0,(min(right,item.ended_at)-max(left,item.started_at)).total_seconds())
    return [{"task_id":task.id,"project_id":task.project_id,"name":task.name,
             "hours":round(seconds[task.id]/3600,2),"estimate_minutes":task.estimate_minutes}
            for task in db.scalars(select(WorkTask).where(WorkTask.user_id==user.id))]
