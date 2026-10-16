"""Encrypted portable backup, staged restart-safe restoration, migration snapshots.

All exports use AES-256-GCM with scrypt-derived passphrase keys. Automatic
on-device snapshots use a persistent local device key. No cloud dependencies.
"""
import base64
import hashlib
import json
import os
import secrets
import sqlite3
import tempfile
from datetime import datetime,timezone
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from .db import data_directory, database_url
from .models import User
from .security import current_user

MAGIC=b"WORKPULSE2\x00"
router=APIRouter(prefix="/v2/backups",tags=["Encrypted backups"])

def _key_from_passphrase(password:str,salt:bytes)->bytes:
    return Scrypt(salt=salt,length=32,n=2**14,r=8,p=1).derive(password.encode("utf-8"))

def encrypt(raw:bytes,password:str)->bytes:
    salt=secrets.token_bytes(16)
    nonce=secrets.token_bytes(12)
    key=_key_from_passphrase(password,salt)
    return MAGIC+salt+nonce+AESGCM(key).encrypt(nonce,raw,MAGIC)

def decrypt(bundle:bytes,password:str)->bytes:
    if not bundle.startswith(MAGIC) or len(bundle)<len(MAGIC)+16+12+16:
        raise ValueError("Invalid WorkPulse backup")
    prefix=len(MAGIC)
    salt=bundle[prefix:prefix+16];nonce=bundle[prefix+16:prefix+28]
    return AESGCM(_key_from_passphrase(password,salt)).decrypt(nonce,bundle[prefix+28:],MAGIC)

def _device_key()->bytes:
    keyfile=data_directory()/".backup-key"
    if not keyfile.exists():
        try:
            fd=os.open(str(keyfile),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,"wb") as f:f.write(secrets.token_bytes(32))
        except FileExistsError:pass
    key=keyfile.read_bytes()
    if len(key)!=32:raise RuntimeError("Invalid local backup key")
    return key

def _encrypt_device(raw:bytes)->bytes:
    nonce=secrets.token_bytes(12)
    return nonce+AESGCM(_device_key()).encrypt(nonce,raw,MAGIC)

def _decrypt_device(ciphertext:bytes)->bytes:
    if len(ciphertext)<28:raise ValueError("Invalid backup snapshot")
    return AESGCM(_device_key()).decrypt(ciphertext[:12],ciphertext[12:],MAGIC)

def _sqlite_copy()->bytes:
    """Use SQLite's backup API, not a raw copy of a WAL-mode database."""
    path=data_directory()/"workpulse.db"
    with tempfile.TemporaryDirectory() as tmp:
        staging=Path(tmp)/"snapshot.db"
        source=sqlite3.connect(str(path))
        try:
            dest=sqlite3.connect(str(staging))
            try:
                source.backup(dest)
            finally:dest.close()
        finally:source.close()
        return staging.read_bytes()

def _integrity_check(raw:bytes)->None:
    if len(raw)>200*1024*1024 or len(raw)<100 or not raw.startswith(b"SQLite format 3\x00"):
        raise ValueError("Invalid or oversized SQLite database")
    with tempfile.TemporaryDirectory() as tmp:
        name=Path(tmp)/"validate.db";name.write_bytes(raw)
        with sqlite3.connect("file:"+str(name)+"?mode=ro",uri=True) as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise ValueError("SQLite integrity check failed")
            tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"users","work_sessions","activity_slices","alembic_version"}<=tables:
                raise ValueError("Not a WorkPulse database")

def ensure_migration_snapshot()->None:
    """Secure daily local migration snapshots, keeping the last 5 copies."""
    source=data_directory()/"workpulse.db"
    if not source.exists() or source.stat().st_size<100:return
    folder=data_directory()/"backups";folder.mkdir(exist_ok=True)
    today=datetime.now(timezone.utc).strftime("%Y%m%d")
    output=folder/("before-start-"+today+".wpdevice")
    if output.exists():return
    raw=_sqlite_copy()
    fd,tmp=tempfile.mkstemp(dir=folder,prefix=".snapshot-")
    try:
        with os.fdopen(fd,"wb") as f:f.write(_encrypt_device(raw))
        os.replace(tmp,output)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    for old in sorted(folder.glob("before-start-*.wpdevice"),reverse=True)[5:]:
        old.unlink(missing_ok=True)

def prepare_restore(bundle:bytes,password:str)->None:
    try:
        raw=decrypt(bundle,password)
        _integrity_check(raw)
    except Exception as exc:
        raise ValueError("Cannot decrypt or validate the backup") from exc
    path=data_directory()/"pending-restore.wpdevice"
    path.write_bytes(_encrypt_device(raw))

def apply_pending_restore()->bool:
    """Called only during backend startup, before opening any DB connection."""
    path=data_directory()/"pending-restore.wpdevice"
    if not path.exists():return False
    raw=_decrypt_device(path.read_bytes())
    _integrity_check(raw)
    source=data_directory()/"workpulse.db"
    stage=data_directory()/".restore-new.db"
    stage.write_bytes(raw)
    # Preserve pre-restore database in a recoverable encrypted snapshot.
    ensure_migration_snapshot()
    os.replace(stage,source)
    for suffix in ("-wal","-shm"):
        (data_directory()/("workpulse.db"+suffix)).unlink(missing_ok=True)
    path.unlink()
    return True

class PasswordInput(BaseModel):
    password:str=Field(min_length=12,max_length=256)

class RestoreInput(PasswordInput):
    payload:str=Field(max_length=300000000)

@router.post("/create")
def create_backup(body:PasswordInput,user:User=Depends(current_user)):
    # The user password never goes into the backup filename or application logs.
    raw=_sqlite_copy()
    return {"filename":"WorkPulse-"+datetime.now().strftime("%Y-%m-%d")+".wpbackup",
            "payload":base64.b64encode(encrypt(raw,body.password)).decode("ascii")}

@router.post("/prepare-restore")
def restore_backup(body:RestoreInput,user:User=Depends(current_user)):
    try:
        bundle=base64.b64decode(body.payload,validate=True)
        if len(bundle)>220*1024*1024:raise ValueError("Too large")
        prepare_restore(bundle,body.password)
    except Exception as exc:
        raise HTTPException(422,"Backup password is wrong or the file is invalid") from exc
    return {"restart_required":True,"message":"Encrypted backup staged. Restart WorkPulse to restore safely."}
