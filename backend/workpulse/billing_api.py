"""Local invoice records. Marking sent/paid is a user action, never an email or payment."""
import json
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .models import Invoice, User
from .security import current_user, get_db
from .advanced_api import project_analytics, owned

router = APIRouter(prefix="/v3/invoices", tags=["Local billing"])

class InvoiceIn(BaseModel):
    number: str = Field(min_length=1,max_length=80)
    client: str = Field(min_length=1,max_length=120)
    currency: Literal["INR","USD","EUR","GBP"] = "INR"
    start: date
    end: date
    issued_on: date
    due_on: date
    project_ids: list[int] = Field(min_length=1,max_length=100)
    @field_validator("number","client")
    @classmethod
    def nonblank(cls, value):
        if not value.strip(): raise ValueError("Value cannot be blank")
        return value.strip()

class StatusIn(BaseModel):
    status: Literal["draft","sent","paid","void"]

def record(row):
    return {k:getattr(row,k) for k in ("id","number","client","currency","status","issued_on","due_on","total")} | {"details":json.loads(row.snapshot)}

@router.get("")
def invoices(user:User=Depends(current_user),db:Session=Depends(get_db)):
    return [record(row) for row in db.scalars(select(Invoice).where(Invoice.user_id==user.id).order_by(Invoice.id.desc()))]

@router.post("",status_code=201)
def create_invoice(body:InvoiceIn,tz:int=Query(0,ge=-840,le=840),user:User=Depends(current_user),db:Session=Depends(get_db)):
    if body.due_on<body.issued_on: raise HTTPException(422,"Due date must follow issue date")
    analytics=project_analytics(body.start,body.end,tz,user,db)
    selected=set(body.project_ids)
    lines=[p for p in analytics if p["id"] in selected]
    if len(lines)!=len(selected): raise HTTPException(404,"Project not found")
    if any(p["client"] != body.client for p in lines): raise HTTPException(422,"Select projects belonging to the same client")
    lines=[p for p in lines if p["billable"]>0]
    if not lines: raise HTTPException(422,"Selected projects have no billable work in this range")
    for line in lines:
        quantity=Decimal(str(line["seconds"]))/Decimal(3600)
        line["hours"]=round(float(quantity),6)
        line["billable"]=float((quantity*Decimal(str(line["hourly_rate"]))).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP))
    total=float(sum(Decimal(str(p["billable"])) for p in lines))
    row=Invoice(user_id=user.id,number=body.number,client=body.client,currency=body.currency,
        status="draft",issued_on=body.issued_on.isoformat(),due_on=body.due_on.isoformat(),total=total,
        snapshot=json.dumps({"start":body.start.isoformat(),"end":body.end.isoformat(),"lines":lines}))
    db.add(row)
    try: db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,"Invoice number already exists")
    return record(row)

@router.patch("/{item_id}")
def change_status(item_id:int,body:StatusIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=owned(db,Invoice,item_id,user.id)
    transitions={"draft":{"sent","void"},"sent":{"paid","void"},"paid":set(),"void":set()}
    if body.status!=row.status and body.status not in transitions[row.status]:
        raise HTTPException(409,"This invoice status change is not allowed")
    row.status=body.status;db.commit()
    return record(row)

@router.get("/{item_id}/export")
def export_invoice(item_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    import io
    from html import escape
    from fastapi.responses import StreamingResponse
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    row=owned(db,Invoice,item_id,user.id)
    details=json.loads(row.snapshot)
    out=io.BytesIO()
    styles=getSampleStyleSheet()
    safe=lambda text:escape(str(text))
    content=[Paragraph("Vision Tracker | Invoice",styles["Title"]),Spacer(1,20),
        Paragraph(safe(row.number),styles["Heading2"]),
        Paragraph("From: "+safe(user.full_name)+"<br/>Client: "+safe(row.client),styles["BodyText"]),
        Spacer(1,12),Paragraph(f"Issued: {row.issued_on} | Due: {row.due_on} | Status: {safe(row.status)}",styles["BodyText"]),
        Paragraph(f"Work period: {details['start']} to {details['end']} | Currency: {row.currency}",styles["BodyText"]),Spacer(1,20)]
    cells=[["Project","Hours","Rate","Amount"]]
    for line in details['lines']:
        cells.append([Paragraph(safe(line['name']),styles['BodyText']),str(line['hours']),f"{line['hourly_rate']:.2f}",f"{line['billable']:.2f}"])
    cells.append(["TOTAL","","",f"{row.currency} {row.total:.2f}"])
    table=Table(cells,colWidths=[235,55,85,100],repeatRows=1)
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e3f3ef')),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('ALIGN',(1,0),(-1,-1),'RIGHT'),
        ('BOTTOMPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),12),
        ('LINEBELOW',(0,0),(-1,-1),.5,colors.HexColor('#dddddd'))]))
    content.extend([table,Spacer(1,20),Paragraph('Local invoice record. Payment processing and tax calculation are not connected.',styles['BodyText'])])
    SimpleDocTemplate(out,title='Vision Tracker invoice',rightMargin=45,leftMargin=45).build(content)
    out.seek(0)
    return StreamingResponse(out,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="VisionTracker-invoice-{row.id}.pdf"'})
