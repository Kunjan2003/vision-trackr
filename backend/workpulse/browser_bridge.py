"""Explicitly paired, domain-only Chrome/Edge browser extension bridge."""
import hashlib
import re
import secrets
from datetime import datetime
from fastapi import APIRouter,Depends,HTTPException,Header,Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel,Field
from sqlalchemy.orm import Session
from .models import BrowserPair,PrivacySettings,User
from .security import current_user,get_db
from .enhancements import set_browser_hint

router=APIRouter(tags=["Browser integration"])
valid_host=re.compile(r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
headers={"Access-Control-Allow-Origin":"*",
         "Access-Control-Allow-Methods":"POST, OPTIONS",
         "Access-Control-Allow-Headers":"Content-Type, X-Browser-Token",
         "Cache-Control":"no-store"}

@router.post("/v2/browser/pair")
def pair(request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
    preferences=db.get(PrivacySettings,user.id)
    if not preferences or not preferences.browser_opt_in:
        raise HTTPException(403,"Enable browser integration in Privacy settings first")
    key=secrets.token_urlsafe(32)
    row=db.get(BrowserPair,user.id)
    if row is None:row=BrowserPair(user_id=user.id,token_hash="")
    row.token_hash=hashlib.sha256(key.encode()).hexdigest()
    db.add(row);db.commit()
    return {"port":request.app.state.port,"token":key,
            "note":"Enter the port and token in the WorkPulse Chrome/Edge extension. The token is shown only once."}

@router.delete("/v2/browser/pair",status_code=204)
def unpair(user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=db.get(BrowserPair,user.id)
    if row:db.delete(row);db.commit()

class BrowserEvent(BaseModel):
    hostname:str=Field(min_length=1,max_length=253)

@router.options("/browser/activity")
def browser_preflight():
    return JSONResponse({},headers=headers)

@router.post("/browser/activity")
def browser_activity(body:BrowserEvent,x_browser_token:str|None=Header(None),db:Session=Depends(get_db)):
    if not x_browser_token or len(x_browser_token)>200:
        raise HTTPException(403,"Pair browser integration to continue",headers=headers)
    fingerprint=hashlib.sha256(x_browser_token.encode()).hexdigest()
    from sqlalchemy import select
    row=db.scalar(select(BrowserPair).where(BrowserPair.token_hash==fingerprint))
    if not row:raise HTTPException(403,"Browser pairing revoked or invalid",headers=headers)
    prefs=db.get(PrivacySettings,row.user_id)
    if not prefs or not prefs.browser_opt_in:
        raise HTTPException(403,"Browser tracking is disabled",headers=headers)
    host=body.hostname.strip().lower().strip(".")
    if not valid_host.fullmatch(host) or host.startswith(".") or ".." in host:
        raise HTTPException(422,"Invalid domain",headers=headers)
    # In-memory hint expires quickly and only enriches the current foreground browser.
    set_browser_hint(row.user_id,host)
    return JSONResponse({"ok":True},headers=headers)
