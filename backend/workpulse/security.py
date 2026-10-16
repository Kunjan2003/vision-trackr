"""Local-only credentials: application capability plus per-user JWT."""
import hmac
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import SessionLocal, data_directory
from .models import User

SECRET_FILE = data_directory() / "jwt.secret"
def jwt_secret() -> str:
    if not SECRET_FILE.exists():
        try:
            fd = os.open(str(SECRET_FILE), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(secrets.token_hex(48))
        except FileExistsError:
            pass
    return SECRET_FILE.read_text().strip()

CAPABILITY = os.getenv("WORKPULSE_AGENT_TOKEN") or secrets.token_urlsafe(48)
LOGIN_ATTEMPTS: dict[str, list[float]] = {}

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def issue_token(user: User) -> str:
    return jwt.encode({"sub": str(user.id), "exp": datetime.now(timezone.utc) + timedelta(days=30)}, jwt_secret(), algorithm="HS256")

def verify_capability(x_agent_token: str | None = Header(default=None)) -> None:
    if not x_agent_token or not hmac.compare_digest(x_agent_token, CAPABILITY):
        raise HTTPException(403, "Invalid local application capability")

def get_db():
    with SessionLocal() as db:
        yield db

def current_user(authorization: str | None = Header(default=None), _=Depends(verify_capability), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Sign in required")
    try:
        payload = jwt.decode(authorization[7:], jwt_secret(), algorithms=["HS256"])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, "Session expired or invalid")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(401, "Account not found")
    return user

def throttle(email: str) -> None:
    now = time.monotonic()
    history = LOGIN_ATTEMPTS.setdefault(email, [])
    history[:] = [t for t in history if now-t < 60]
    if len(history) >= 8:
        raise HTTPException(429, "Too many attempts. Try again in a minute.")
    history.append(now)
