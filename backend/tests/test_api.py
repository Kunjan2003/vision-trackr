import os
import tempfile
from pathlib import Path
# isolated database before importing workpulse.db
_tmp = tempfile.TemporaryDirectory()
os.environ["WORKPULSE_DATA_DIR"] = _tmp.name
os.environ["WORKPULSE_AGENT_TOKEN"] = "test-only-agent-token"
from fastapi.testclient import TestClient
from workpulse.db import migrate, SessionLocal
from workpulse.api import app

migrate()
client = TestClient(app)
HEADERS = {"X-Agent-Token": "test-only-agent-token"}

def test_agent_capability_enforced():
    assert client.get("/auth/status").status_code == 403
    assert client.get("/auth/status", headers=HEADERS).json()["registered"] is False

def test_registration_and_authenticated_routes():
    resp = client.post("/auth/register", headers=HEADERS, json={
        "full_name": "Alice Example", "email": "alice@example.com", "password": "StrongPassword123!", "department":"Engineering"
    })
    assert resp.status_code == 201, resp.text
    token = resp.json()["token"]
    auth = {**HEADERS, "Authorization": f"Bearer {token}"}
    assert client.get("/auth/me", headers=auth).json()["full_name"] == "Alice Example"
    assert client.get("/activity/live", headers=auth).status_code == 200
    assert client.post("/session/break", headers=auth).json()["status"] == "break"
    assert client.post("/session/resume", headers=auth).json()["status"] == "working"
    assert client.get("/stats/day", headers=auth).status_code == 200
    assert client.get("/stats/week", headers=auth).status_code == 200
    assert client.get("/stats/month", headers=auth).status_code == 200
    assert client.get("/export?format=csv", headers=auth).status_code == 200
    assert client.get("/export?format=pdf", headers=auth).content.startswith(b"%PDF")
    rules = client.get("/categories", headers=auth).json()
    assert len(rules) > 3
    assert client.patch("/settings", headers=auth, json={"idle_threshold":600}).json()["idle_threshold"] == 600
    assert client.post("/session/finish", headers=auth).json()["status"] == "finished"
    assert client.post("/auth/register",headers=HEADERS,json={"full_name":"Bob","email":"bob@example.com","password":"anotherpassword"}).status_code == 409

def test_login_rejects_wrong_password():
    assert client.post("/auth/login",headers=HEADERS,json={"email":"alice@example.com","password":"bad"}).status_code == 401
