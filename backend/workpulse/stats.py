"""Time-zone-aware aggregation with interval overlap, including local midnight splits."""
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import ActivitySlice

STATES = ("productive", "neutral", "non_productive", "idle", "break")

def bounds(day: date, offset_minutes: int):
    # JS getTimezoneOffset = UTC - local
    start = datetime.combine(day, time.min) + timedelta(minutes=offset_minutes)
    return start, start + timedelta(days=1)

def slices_for(db: Session, user_id: int, start: datetime, end: datetime):
    return db.scalars(select(ActivitySlice).where(
        ActivitySlice.user_id == user_id,
        ActivitySlice.ended_at > start,
        ActivitySlice.started_at < end
    ).order_by(ActivitySlice.started_at)).all()

def totals_from(seconds: dict[str, float]):
    result = {k: round(seconds.get(k, 0.0), 1) for k in STATES}
    result["work"] = round(sum(result[k] for k in STATES if k != "break"), 1)
    result["productivity"] = round(100 * result["productive"] / result["work"], 1) if result["work"] else 0.0
    return result

def clipped(rows, start: datetime, end: datetime):
    for row in rows:
        left, right = max(row.started_at, start), min(row.ended_at, end)
        if right > left:
            yield row, left, right, (right-left).total_seconds()

def day_stats(db: Session, user_id: int, day: date, offset: int):
    start, end = bounds(day, offset)
    data = list(clipped(slices_for(db, user_id, start, end), start, end))
    seconds = defaultdict(float)
    apps = defaultdict(lambda: {"seconds": 0.0, "category": "neutral"})
    hourly = [{k: 0 for k in STATES} | {"hour": f"{h:02d}:00"} for h in range(24)]
    timeline = []
    for row, left, right, duration in data:
        seconds[row.state] += duration
        if row.app_name and row.state not in ("idle", "break"):
            apps[row.app_name]["seconds"] += duration
            apps[row.app_name]["category"] = row.category
        timeline.append({"start": left.isoformat()+"Z", "end": right.isoformat()+"Z", "state": row.state,
                         "app_name": row.app_name, "title": row.window_title, "seconds": round(duration, 1)})
        cursor = left
        while cursor < right:
            local_hour = (cursor - timedelta(minutes=offset)).hour
            next_hour = (cursor - timedelta(minutes=offset)).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1, minutes=offset)
            part_end = min(next_hour, right)
            hourly[local_hour][row.state] += round((part_end-cursor).total_seconds(), 1)
            cursor = part_end
    return {"date": day.isoformat(), "totals": totals_from(seconds),
            "apps": sorted(({"app_name": k, **v} for k,v in apps.items()), key=lambda x: -x["seconds"])[:30],
            "timeline": timeline, "hourly": hourly}

def period_stats(db: Session, user_id: int, start_day: date, days: int, offset: int):
    daily = [day_stats(db, user_id, start_day + timedelta(days=i), offset) for i in range(days)]
    totals = defaultdict(float)
    for item in daily:
        for state in STATES:
            totals[state] += item["totals"][state]
    return {"start": start_day.isoformat(), "days": [{"date": d["date"], **d["totals"]} for d in daily],
            "totals": totals_from(totals)}
