import asyncio
import csv
import io
import os
from datetime import date, datetime, timedelta
from typing import Literal
from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from . import agent
from .db import SessionLocal
from .models import ActivitySlice, CategoryRule, User, UserSettings, WorkSession
from .schemas import Login, Register, RuleInput, SettingsPatch
from .security import CAPABILITY, current_user, get_db, hash_password, issue_token, throttle, verify_capability, verify_password
from .stats import bounds, clipped, day_stats, period_stats, slices_for
from .tracker import seed_user

app = FastAPI(title="WorkPulse Local API", version="1.0.0", docs_url="/docs", redoc_url=None)
# Docs are gated by the ephemeral capability through the Electron server; /openapi.json is
# local-only, but contains no secrets or user data.
@app.get("/health")
def health(_=Depends(verify_capability)):
    return {"ok": True}

@app.get("/auth/status")
def auth_status(_=Depends(verify_capability), db: Session = Depends(get_db)):
    return {"registered": bool(db.scalar(select(User.id).limit(1)))}

def profile(user: User):
    return {"id": user.id, "full_name": user.full_name, "email": user.email, "department": user.department}

@app.post("/auth/register", status_code=201)
def register(form: Register, _=Depends(verify_capability), db: Session = Depends(get_db)):
    if db.scalar(select(User.id).limit(1)):
        raise HTTPException(409, "This device already has an account")
    user = User(full_name=form.full_name, email=str(form.email).lower(),
                password_hash=hash_password(form.password), department=form.department.strip())
    db.add(user)
    try:
        db.flush()
        seed_user(db, user.id)
        agent.tracker.transition(db, user.id, "start")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Account already exists")
    agent.set_user(user.id)
    return {"token": issue_token(user), "user": profile(user)}

@app.post("/auth/login")
def login(form: Login, _=Depends(verify_capability), db: Session = Depends(get_db)):
    email = str(form.email).lower()
    throttle(email)
    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    # Restoring an open session does not restart a finished day.
    agent.set_user(user.id)
    return {"token": issue_token(user), "user": profile(user)}

@app.get("/auth/me")
def me(user: User = Depends(current_user)):
    return profile(user)

def session_state(db: Session, user_id: int):
    s = db.scalar(select(WorkSession).where(WorkSession.user_id == user_id).order_by(WorkSession.id.desc()))
    return {"break_seconds": max(0, (datetime.utcnow() - (s.state_since or s.started_at)).total_seconds()) if s and s.finished_at is None and s.status == "break" else 0,
            "status": s.status if s and s.finished_at is None else "finished",
            "started_at": s.started_at.isoformat()+"Z" if s and s.finished_at is None else None,
            "session_id": s.id if s and s.finished_at is None else None}

@app.post("/session/{action}")
def change_session(action: Literal["start", "break", "resume", "finish"], user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        result = agent.tracker.transition(db, user.id, action)
    except ValueError as error:
        raise HTTPException(409, str(error))
    db.commit()
    agent.set_user(user.id)
    return session_state(db, user.id)

@app.get("/activity/live")
def live(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {**session_state(db, user.id), "state": agent.last_state,
            "foreground": agent.foreground}

@app.websocket("/ws/live")
async def live_socket(ws: WebSocket):
    await ws.accept()
    try:
        payload = await asyncio.wait_for(ws.receive_json(), timeout=5)
        import hmac
        import jwt
        from .security import jwt_secret
        if not hmac.compare_digest(str(payload.get("agent", "")), CAPABILITY):
            await ws.close(code=1008)
            return
        identity = jwt.decode(str(payload.get("token", "")), jwt_secret(), algorithms=["HS256"])
        user_id = int(identity["sub"])
        with SessionLocal() as db:
            if not db.get(User, user_id):
                await ws.close(code=1008)
                return
        while True:
            with SessionLocal() as db:
                state = {**session_state(db, user_id), "state": agent.last_state, "foreground": agent.foreground}
                # Lightweight today totals for live timer.
                state["today"] = day_stats(db, user_id, date.today(), -int(datetime.now().astimezone().utcoffset().total_seconds() / 60))["totals"]
                s = db.scalar(select(WorkSession).where(WorkSession.user_id == user_id, WorkSession.finished_at.is_(None)).order_by(WorkSession.id.desc()))
                if s:
                    age = max(0.0, min(8.0, (datetime.utcnow() - s.last_tick_at).total_seconds()))
                    which = "break" if s.status == "break" else agent.last_state
                    if which not in ("productive", "neutral", "non_productive", "idle", "break"):
                        which = "neutral"
                    state["today"][which] += age
                    if which != "break":
                        state["today"]["work"] += age
                    t = state["today"]
                    t["productivity"] = round(100*t["productive"]/t["work"], 1) if t["work"] else 0.0
                state["reminder"] = agent.reminder
            await ws.send_json(state)
            await asyncio.sleep(1)
    except (WebSocketDisconnect, asyncio.TimeoutError, ValueError, KeyError):
        return
    except Exception:
        try:
            await ws.close(code=1011)
        except Exception:
            pass

@app.get("/stats/day")
def stats_day(day: date = Query(default_factory=date.today), tz: int = Query(0, ge=-840, le=840),
              user: User = Depends(current_user), db: Session = Depends(get_db)):
    return day_stats(db, user.id, day, tz)

@app.get("/stats/week")
def stats_week(day: date = Query(default_factory=date.today), tz: int = Query(0, ge=-840, le=840),
               user: User = Depends(current_user), db: Session = Depends(get_db)):
    monday = day - timedelta(days=day.weekday())
    return period_stats(db, user.id, monday, 7, tz)

@app.get("/stats/month")
def stats_month(day: date = Query(default_factory=date.today), tz: int = Query(0, ge=-840, le=840),
                user: User = Depends(current_user), db: Session = Depends(get_db)):
    first = day.replace(day=1)
    next_month = first.replace(year=first.year + 1, month=1) if first.month == 12 else first.replace(month=first.month + 1)
    return period_stats(db, user.id, first, (next_month-first).days, tz)

@app.get("/categories")
def list_categories(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": x.id, "pattern": x.pattern, "category": x.category, "enabled": x.enabled}
            for x in db.scalars(select(CategoryRule).where(CategoryRule.user_id == user.id).order_by(CategoryRule.id))]

@app.post("/categories", status_code=201)
def add_category(body: RuleInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = CategoryRule(user_id=user.id, **body.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Pattern already exists")
    return {"id": item.id, **body.model_dump()}

@app.put("/categories/{rule_id}")
def update_category(rule_id: int, body: RuleInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.get(CategoryRule, rule_id)
    if not item or item.user_id != user.id:
        raise HTTPException(404, "Rule not found")
    for k, v in body.model_dump().items():
        setattr(item, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Pattern already exists")
    return {"id": item.id, **body.model_dump()}

@app.delete("/categories/{rule_id}", status_code=204)
def delete_category(rule_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.get(CategoryRule, rule_id)
    if not item or item.user_id != user.id:
        raise HTTPException(404, "Rule not found")
    db.delete(item)
    db.commit()

@app.get("/settings")
def settings(user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = db.get(UserSettings, user.id)
    return {k: getattr(s, k) for k in ("idle_threshold", "poll_interval", "auto_start", "break_reminder_minutes", "daily_goal_minutes", "theme")}

@app.patch("/settings")
def update_settings(body: SettingsPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = db.get(UserSettings, user.id)
    for k,v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(s,k,v)
    db.commit()
    return settings(user,db)

@app.get("/export")
def export(format: Literal["csv", "pdf"] = "csv", day: date = Query(default_factory=date.today),
           tz: int = Query(0, ge=-840, le=840), user: User = Depends(current_user), db: Session = Depends(get_db)):
    start,end = bounds(day,tz)
    rows = list(clipped(slices_for(db,user.id,start,end),start,end))
    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Start (UTC)","End (UTC)","Seconds","Status","Application","Window title"])
        for item,a,b,secs in rows:
            writer.writerow([a.isoformat()+"Z",b.isoformat()+"Z",round(secs,1),item.state,item.app_name,item.window_title])
        return StreamingResponse(iter([buf.getvalue()]),media_type="text/csv",
                                 headers={"Content-Disposition":f'attachment; filename="workpulse-{day}.csv"'})
    buf = io.BytesIO()
    page = canvas.Canvas(buf,pagesize=A4)
    page.setTitle("WorkPulse Report")
    page.setFont("Helvetica-Bold",20)
    page.drawString(42,790,f"WorkPulse - {day.isoformat()}")
    totals = day_stats(db,user.id,day,tz)["totals"]
    page.setFont("Helvetica",11)
    y=750
    for key in ("work","productive","neutral","non_productive","idle","break"):
        page.drawString(46,y,f'{key.replace("_"," ").title()}: {totals[key]/3600:.2f} h')
        y-=24
    page.drawString(46,y,f'Productivity: {totals["productivity"]}%')
    y-=42
    page.setFont("Helvetica-Bold",12)
    page.drawString(46,y,"Top activity")
    page.setFont("Helvetica",9)
    for item,a,b,secs in rows[:35]:
        y-=17
        if y < 55:
            page.showPage(); y=790; page.setFont("Helvetica",9)
        # replace unsupported font glyphs; truncate titles, never render passwords/content.
        detail = f'{a.strftime("%H:%M")} {item.state} {item.app_name} {item.window_title}'[:102]
        page.drawString(46,y,detail.encode("latin-1","replace").decode("latin-1"))
    page.save(); buf.seek(0)
    return StreamingResponse(buf,media_type="application/pdf",
                             headers={"Content-Disposition":f'attachment; filename="workpulse-{day}.pdf"'})

# All v2 routes use the same local capability and user authentication.
from .advanced_api import router as advanced_router
app.include_router(advanced_router)

from .browser_bridge import router as browser_router
app.include_router(browser_router)

from .backup import router as backup_router
app.include_router(backup_router)
from .calendar_api import router as calendar_router
app.include_router(calendar_router)
