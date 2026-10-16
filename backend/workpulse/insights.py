"""Evidence-based local coaching. Optional Ollama never receives window titles."""
import json
from collections import Counter,defaultdict
from datetime import datetime,timedelta
from urllib.request import Request,urlopen
from urllib.error import URLError
from fastapi import HTTPException
from sqlalchemy import select
from .models import ActivitySlice,ManualEntry

def generate(db,user_id:int)->dict:
    start=datetime.utcnow()-timedelta(days=7)
    rows=db.scalars(select(ActivitySlice).where(ActivitySlice.user_id==user_id,ActivitySlice.ended_at>=start).order_by(ActivitySlice.started_at)).all()
    productive=sum(r.duration for r in rows if r.state=="productive")
    work=sum(r.duration for r in rows if r.state!="break")
    app_changes=0
    last_app=None
    longest=0.0
    streak=0.0
    end_streak=None
    hourly=defaultdict(float)
    daily=defaultdict(float)
    for row in rows:
        if row.state=="productive":
            if end_streak and (row.started_at-end_streak).total_seconds()<=15:
                streak+=row.duration
            else:
                streak=row.duration
            end_streak=row.ended_at
            longest=max(longest,streak)
            hourly[row.started_at.hour]+=row.duration
        else:
            end_streak=None;streak=0
        if row.state not in ("idle","break"):
            if last_app and row.app_name and row.app_name!=last_app:
                app_changes+=1
            if row.app_name:last_app=row.app_name
        if row.state!="break":daily[row.started_at.date().isoformat()]+=row.duration
    peak=sorted(hourly,key=lambda k:hourly[k],reverse=True)[:3]
    pct=round(100*productive/work,1) if work else 0
    tips=[]
    if not rows:tips=["Start a work session to receive personalized insights from your own data."]
    else:
        if peak:tips.append("Your strongest recorded focus hours are "+", ".join(f"{h:02d}:00" for h in peak)+". Consider scheduling difficult tasks then.")
        if app_changes>35:tips.append("You switched foreground apps "+str(app_changes)+" times this week. Try 25-minute single-task focus blocks.")
        if longest<25*60:tips.append("Your longest continuous productive block is under 25 minutes. Try a protected focus session.")
        if pct<45:tips.append("Less than 45% of tracked work was classified productive. Review categories before changing your schedule.")
        if len(daily)>=5:tips.append("You have recorded activity on "+str(len(daily))+" different days. Compare goal completion in Attendance.")
    return {"productive_hours":round(productive/3600,2),"work_hours":round(work/3600,2),
            "productivity":pct,"context_switches":app_changes,"longest_focus_minutes":round(longest/60,1),
            "peak_hours":peak,"active_days":len(daily),"tips":tips}

def ask_local_ollama(summary:dict)->str:
    """Only aggregates are sent to a user-managed localhost Ollama instance."""
    prompt=("You are a concise, supportive productivity coach. Give 3 actionable tips "
            "based only on these aggregate statistics, without inventing evidence:\n"
            +json.dumps(summary,ensure_ascii=True))
    body=json.dumps({"model":"llama3.2:3b","prompt":prompt,"stream":False,"options":{"num_predict":230}}).encode()
    request=Request("http://127.0.0.1:11434/api/generate",data=body,method="POST",
                    headers={"Content-Type":"application/json"})
    try:
        with urlopen(request,timeout=15) as response:
            result=json.loads(response.read(256000).decode())
        return str(result.get("response",""))[:3000]
    except (URLError,TimeoutError,OSError,ValueError) as exc:
        raise HTTPException(503,"Local Ollama is unavailable. Install Ollama and run: ollama pull llama3.2:3b") from exc
