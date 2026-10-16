"""Extra API contract tests for WorkPulse 2."""
from datetime import datetime
from backend.tests.test_api import client, HEADERS

def login_headers():
    response=client.post("/auth/login",headers=HEADERS,
        json={"email":"alice@example.com","password":"StrongPassword123!"})
    assert response.status_code==200
    return {**HEADERS,"Authorization":"Bearer "+response.json()["token"]}

def test_project_task_rules_and_focus():
    headers=login_headers()
    p=client.post("/v2/projects",headers=headers,
        json={"name":"Quality assurance","client":"Local","hourly_rate":75,"budget_hours":12})
    assert p.status_code==201,p.text
    project_id=p.json()["id"]
    task=client.post("/v2/tasks",headers=headers,
        json={"name":"Write unit tests","project_id":project_id,"status":"doing","estimate_minutes":30})
    assert task.status_code==201,task.text
    tagged=client.put("/v2/assignment",headers=headers,
        json={"project_id":project_id,"task_id":task.json()["id"]})
    assert tagged.status_code==200,tagged.text
    assert client.get("/v2/projects",headers=headers).status_code==200
    assert client.get("/v2/projects/analytics",headers=headers).status_code==200
    assert client.post("/v2/focus/start",headers=headers,json={"minutes":25}).status_code==200
    assert client.get("/v2/focus",headers=headers).json()["status"]=="running"
    assert client.post("/v2/focus/finish",headers=headers).status_code==200
    assert client.put("/v2/assignment",headers=headers,json={"project_id":None,"task_id":None}).status_code==200

def test_privacy_attendance_and_range_reports():
    headers=login_headers()
    changed=client.patch("/v2/privacy",headers=headers,
        json={"hide_window_titles":True,"retention_days":30})
    assert changed.status_code==200,changed.text
    assert client.post("/v2/privacy/pause",headers=headers).json()["paused"]
    assert not client.post("/v2/privacy/resume",headers=headers).json()["paused"]
    assert client.get("/v2/privacy/rules",headers=headers).status_code==200
    assert client.get("/v2/attendance?year=2024&month=1",headers=headers).status_code==200
    assert "tips" in client.get("/v2/insights",headers=headers).json()
    for kind in ("csv","pdf"):
        result=client.get("/v2/reports/export?start=2024-01-01&end=2024-01-07&format="+kind,headers=headers)
        assert result.status_code==200,result.text[:200] if kind=="csv" else result.status_code
        if kind=="pdf":assert result.content.startswith(b"%PDF")

def test_manual_project_time_uses_local_day_and_appears_in_billing():
    headers=login_headers()
    project=client.post("/v2/projects",headers=headers,json={
        "name":"Manual billing project","client":"Example client","hourly_rate":80,"budget_hours":10
    })
    assert project.status_code==201,project.text
    project_id=project.json()["id"]
    task=client.post("/v2/tasks",headers=headers,json={
        "project_id":project_id,"name":"Client workshop","status":"done","estimate_minutes":60
    })
    assert task.status_code==201,task.text
    entry=client.post("/v2/manual",headers=headers,json={
        "started_at":"2024-01-01T00:15:00+05:30","ended_at":"2024-01-01T01:15:00+05:30",
        "state":"productive","note":"Client workshop","project_id":project_id,"task_id":task.json()["id"]
    })
    assert entry.status_code==201,entry.text
    assert entry.json()["project_id"]==project_id
    local_day=client.get("/v2/manual?day=2024-01-01&tz=-330",headers=headers)
    assert local_day.status_code==200
    assert any(row["id"]==entry.json()["id"] for row in local_day.json())
    billing=client.get("/v2/projects/analytics?start=2024-01-01&end=2024-01-01&tz=-330",headers=headers)
    project_row=next(row for row in billing.json() if row["id"]==project_id)
    assert project_row["hours"]==1.0
    assert project_row["billable"]==80.0
    task_hours=client.get("/v2/tasks/analytics?start=2024-01-01&end=2024-01-01&tz=-330",headers=headers).json()
    assert next(row for row in task_hours if row["task_id"]==task.json()["id"])["hours"]==1.0
