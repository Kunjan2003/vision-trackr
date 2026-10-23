"""Range-consistent analytics for the personal desktop workspace."""
import re
from collections import defaultdict
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import User, ActivitySlice, WorkSession, UserSettings
from .security import current_user, get_db
from .stats import bounds, day_stats, period_stats, clipped, slices_for

router = APIRouter(prefix="/v3", tags=["Workspace analytics"])

@router.get("/summary")
def summary(start: date, end: date, tz: int = Query(0, ge=-840, le=840),
            user: User = Depends(current_user), db: Session = Depends(get_db)):
    count = (end-start).days+1
    if not 1 <= count <= 93:
        raise HTTPException(422, "Choose a range between 1 and 93 days")
    period = period_stats(db, user.id, start, count, tz)
    previous = period_stats(db, user.id, start-timedelta(days=count), count, tz)
    left, _ = bounds(start, tz)
    _, right = bounds(end, tz)
    apps = defaultdict(lambda: {"seconds": 0, "productive": 0, "neutral": 0, "non_productive": 0})
    domains = defaultdict(float)
    switches = 0
    last_app = None
    for row, a, b, secs in clipped(slices_for(db, user.id, left, right), left, right):
        if row.state in ("productive", "neutral", "non_productive") and row.app_name:
            apps[row.app_name]["seconds"] += secs
            apps[row.app_name][row.state] += secs
            if last_app and last_app != row.app_name:
                switches += 1
            last_app = row.app_name
            # The opt-in bridge appends a hostname, never a full URL.
            match = re.search(r"\[([a-z0-9.-]+\.[a-z]{2,63})\]$", row.window_title, re.I)
            if match:
                domains[match[1].lower()] += secs
    sessions = db.scalars(select(WorkSession).where(WorkSession.user_id == user.id,
        WorkSession.started_at < right,
        (WorkSession.finished_at.is_(None) | (WorkSession.finished_at > left)))).all()
    settings = db.get(UserSettings, user.id)
    goal = (settings.daily_goal_minutes if settings else 480)*60
    daily = []
    for d in period["days"]:
        day_left, day_right = bounds(date.fromisoformat(d["date"]), tz)
        overlapping = [s for s in sessions if s.started_at < day_right and (s.finished_at is None or s.finished_at > day_left)]
        starts = [max(day_left, s.started_at) for s in overlapping]
        ends = [min(day_right, s.finished_at) for s in overlapping if s.finished_at]
        daily.append({**d, "active": round(d["productive"]+d["neutral"]+d["non_productive"],1),
            "first_seen": min(starts).isoformat()+"Z" if starts else None,
            "last_seen": max(ends).isoformat()+"Z" if ends else None,
            "open_session": any(s.finished_at is None for s in overlapping),
            "overtime": max(0, d["work"]-goal), "goal": goal})
    return {**period, "days": daily, "previous": previous["totals"],
        "apps": sorted([{"name": name, **v} for name,v in apps.items()], key=lambda x:-x["seconds"]),
        "websites": sorted([{"name": name, "seconds": seconds} for name,seconds in domains.items()], key=lambda x:-x["seconds"]),
        "context_switches": switches, "active_days": sum(d["work"]>0 for d in daily),
        "goal_seconds": goal, "selected_day": day_stats(db,user.id,end,tz)}
