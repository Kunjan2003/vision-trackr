"""Custom date-range reporting with project-based billable totals."""
import csv
import io
from datetime import date,datetime,timedelta
from fastapi import APIRouter,Depends,HTTPException,Query
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session
from .models import User
from .security import current_user,get_db
from .stats import period_stats
from .advanced_api import project_analytics

router=APIRouter(prefix="/v2/reports",tags=["Work reports"])

def csv_safe(text:str)->str:
    # Prevent Excel/Sheets formula injection when importing untrusted project labels.
    return "'"+text if text and text[0] in "=+-@\t\r" else text

@router.get("/export")
def export_range(start:date,end:date,format:str=Query("csv",pattern="^(csv|pdf)$"),
                 tz:int=Query(0,ge=-840,le=840),user:User=Depends(current_user),
                 db:Session=Depends(get_db)):
    if end<start or (end-start).days>365:
        raise HTTPException(422,"Range must be between 1 and 366 days")
    period=period_stats(db,user.id,start,(end-start).days+1,tz)
    projects=project_analytics(start,end,tz,user,db)
    name="WorkPulse-"+start.isoformat()+"-"+end.isoformat()
    if format=="csv":
        out=io.StringIO(newline="")
        writer=csv.writer(out)
        writer.writerow(["Date","Work (hours)","Productive (hours)","Idle (hours)","Break (hours)","Productivity (%)"])
        for day in period["days"]:
            writer.writerow([day["date"],round(day["work"]/3600,2),round(day["productive"]/3600,2),
                             round(day["idle"]/3600,2),round(day["break"]/3600,2),day["productivity"]])
        writer.writerow([])
        writer.writerow(["Project","Client","Hours","Rate","Billable total"])
        for project in projects:
            writer.writerow([csv_safe(project["name"]),csv_safe(project["client"]),project["hours"],
                             project["hourly_rate"],project["billable"]])
        return StreamingResponse(iter([out.getvalue()]),media_type="text/csv",
            headers={"Content-Disposition":'attachment; filename="'+name+'.csv"'})
    out=io.BytesIO()
    pdf=canvas.Canvas(out,pagesize=A4)
    pdf.setTitle("WorkPulse custom time report")
    def header():
        pdf.setFont("Helvetica-Bold",17)
        pdf.drawString(42,790,"WorkPulse | Work Summary")
        pdf.setFont("Helvetica",10)
        pdf.drawString(42,770,start.isoformat()+" to "+end.isoformat())
        return 740
    y=header()
    pdf.setFont("Helvetica",11)
    total=period["totals"]
    pdf.drawString(42,y,"Total work: %.2f h   Productive: %.2f h   Productivity: %.1f%%"%
                   (total["work"]/3600,total["productive"]/3600,total["productivity"]))
    y-=32
    pdf.setFont("Helvetica-Bold",10)
    pdf.drawString(42,y,"DATE                       WORK           PRODUCTIVE          IDLE             BREAK")
    y-=18
    pdf.setFont("Helvetica",9)
    for d in period["days"]:
        if y<85:
            pdf.showPage();y=header();pdf.setFont("Helvetica",9)
        line=f'{d["date"]}               {d["work"]/3600:>6.2f}                 {d["productive"]/3600:>6.2f}                {d["idle"]/3600:>6.2f}              {d["break"]/3600:>6.2f}'
        pdf.drawString(42,y,line)
        y-=14
    if y<130:pdf.showPage();y=header()
    y-=16
    pdf.setFont("Helvetica-Bold",11);pdf.drawString(42,y,"Client & project billing");y-=20
    pdf.setFont("Helvetica",9)
    for p in projects:
        if y<80:pdf.showPage();y=header()
        line=(p["name"]+" / "+p["client"])[:48]
        line="".join(ch if ord(ch)<256 else "?" for ch in line)
        pdf.drawString(42,y,f'{line}: {p["hours"]:.2f} h x {p["hourly_rate"]:.2f} = {p["billable"]:.2f}')
        y-=16
    pdf.save();out.seek(0)
    return StreamingResponse(out,media_type="application/pdf",
        headers={"Content-Disposition":'attachment; filename="'+name+'.pdf"'})
