"""Import local iCalendar files on explicit user request; no calendar login or sync."""
from datetime import date,datetime,timedelta,timezone
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from icalendar import Calendar
from .models import CalendarMeeting,PrivacySettings,User
from .security import current_user,get_db

router=APIRouter(prefix="/v2/meetings",tags=["Calendar meetings"])
class ICSBody(BaseModel):
    text:str=Field(min_length=10,max_length=1500000)

def normalize(value):
    if not isinstance(value,datetime):return None
    return (value.astimezone(timezone.utc).replace(tzinfo=None)
            if value.tzinfo else value)

@router.post("/import")
def import_ics(body:ICSBody,user:User=Depends(current_user),db:Session=Depends(get_db)):
    prefs=db.get(PrivacySettings,user.id)
    if not prefs or not prefs.meeting_opt_in:
        raise HTTPException(403,"Enable calendar integration in Privacy settings first")
    try:calendar=Calendar.from_ical(body.text.encode("utf-8"))
    except (ValueError,TypeError,KeyError) as exc:
        raise HTTPException(422,"Invalid calendar file") from exc
    imported=0
    # Keep only recently-relevant, non-all-day events; do not store descriptions,
    # attendees or full calendar data.
    low=datetime.utcnow()-timedelta(days=365)
    high=datetime.utcnow()+timedelta(days=365)
    for event in calendar.walk("VEVENT"):
        try:
            start=normalize(event.decoded("DTSTART"))
            end=normalize(event.decoded("DTEND"))
            uid=str(event.get("UID","")).strip()[:200]
            title=str(event.get("SUMMARY","Meeting")).strip()[:180]
            if not start or not end or start>=end or end<low or start>high or not uid:continue
            item=db.scalar(select(CalendarMeeting).where(CalendarMeeting.user_id==user.id,CalendarMeeting.external_uid==uid))
            if item is None:item=CalendarMeeting(user_id=user.id,external_uid=uid,title=title,starts_at=start,ends_at=end)
            else:
                item.title=title;item.starts_at=start;item.ends_at=end
            db.add(item);imported+=1
            if imported>=3000:break
        except (KeyError,ValueError,TypeError,OverflowError):continue
    db.commit()
    return {"imported":imported}

@router.get("")
def meetings(day:date=Query(default_factory=date.today),user:User=Depends(current_user),db:Session=Depends(get_db)):
    left=datetime.combine(day,datetime.min.time())
    right=left+timedelta(days=1)
    rows=db.scalars(select(CalendarMeeting).where(CalendarMeeting.user_id==user.id,CalendarMeeting.starts_at<right,CalendarMeeting.ends_at>left).order_by(CalendarMeeting.starts_at)).all()
    return [{"id":x.id,"title":x.title,"starts_at":x.starts_at.isoformat()+"Z","ends_at":x.ends_at.isoformat()+"Z"} for x in rows]

@router.delete("/{meeting_id}",status_code=204)
def delete_meeting(meeting_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    item=db.get(CalendarMeeting,meeting_id)
    if not item or item.user_id!=user.id:raise HTTPException(404,"Meeting not found")
    db.delete(item);db.commit()
