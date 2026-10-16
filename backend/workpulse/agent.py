"""Automatic polling and break-reminder scheduler; no network egress."""
import logging
import threading
from datetime import datetime
from sqlalchemy import select
from apscheduler.schedulers.background import BackgroundScheduler
from .db import SessionLocal
from .models import UserSettings, WorkSession
from .tracker import Tracker
from .windows import observe

logger=logging.getLogger("workpulse")
tracker=Tracker()
wake=threading.Event()
stopping=threading.Event()
last_state="finished"
foreground={"app_name":"","title":""}
reminder=None
_latest_user=None
_scheduler=None

def set_user(user_id):
    global _latest_user,reminder
    _latest_user=user_id
    reminder=None
    wake.set()

def run():
    global last_state,foreground
    while not stopping.is_set():
        poll=4
        user_id=_latest_user
        if user_id:
            try:
                with SessionLocal() as db:
                    cfg=db.get(UserSettings,user_id)
                    if cfg:poll=cfg.poll_interval
                    opened=db.scalar(select(WorkSession).where(WorkSession.user_id==user_id,WorkSession.finished_at.is_(None)).order_by(WorkSession.id.desc()))
                    if opened:
                        fg=observe()
                        foreground={"app_name":fg.app_name,"title":fg.title}
                        last_state=tracker.tick(db,user_id,fg)
                        db.commit()
                    else:last_state,foreground="finished",{"app_name":"","title":""}
            except Exception:logger.exception("Tracking poll failed")
        wake.wait(timeout=poll)
        wake.clear()

def check_break_reminder():
    global reminder
    if not _latest_user:return
    try:
        with SessionLocal() as db:
            s=db.scalar(select(WorkSession).where(WorkSession.user_id==_latest_user,WorkSession.finished_at.is_(None)).order_by(WorkSession.id.desc()))
            cfg=db.get(UserSettings,_latest_user)
            if not s or not cfg or s.status!="working" or not cfg.break_reminder_minutes:return
            last=s.state_since or s.started_at
            elapsed=max(0,(datetime.utcnow()-last).total_seconds())
            threshold=cfg.break_reminder_minutes*60
            blocks=int(elapsed//threshold)
            if blocks>0:
                identity=str(s.id)+"-"+str(blocks)
                if not reminder or reminder["id"]!=identity:
                    reminder={"id":identity,"message":"You've been working for "+str(blocks*cfg.break_reminder_minutes)+" minutes. Consider a short break."}
    except Exception:logger.exception("Reminder check failed")

def launch():
    global _scheduler
    t=threading.Thread(target=run,name="workpulse-tracker",daemon=True)
    t.start()
    _scheduler=BackgroundScheduler(daemon=True,timezone="UTC")
    _scheduler.add_job(check_break_reminder,"interval",seconds=60,max_instances=1,coalesce=True,id="reminder")
    _scheduler.start()
    return t

def stop():
    stopping.set()
    wake.set()
    if _scheduler and _scheduler.running:_scheduler.shutdown(wait=False)

def restore_user_session():
    with SessionLocal() as db:
        s=db.scalar(select(WorkSession).where(WorkSession.finished_at.is_(None)).order_by(WorkSession.id.desc()))
        if s:set_user(s.user_id)
