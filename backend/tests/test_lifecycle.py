import threading
from unittest.mock import Mock
from workpulse.lifecycle import watch_parent

def test_standalone_agent_does_not_require_a_parent(monkeypatch):
    monkeypatch.delenv("WORKPULSE_PARENT_PID",raising=False)
    on_exit=Mock()
    assert watch_parent(on_exit) is None
    on_exit.assert_not_called()

def test_watchdog_stops_when_parent_disappears(monkeypatch):
    monkeypatch.setenv("WORKPULSE_PARENT_PID","1234")
    parent=Mock();parent.is_running.side_effect=[True,False]
    monkeypatch.setattr("workpulse.lifecycle.psutil.Process",lambda pid:parent)
    exited=threading.Event()
    stopped=watch_parent(exited.set,interval=.01)
    try:
        assert exited.wait(1)
    finally:
        stopped.set()

def test_parent_watch_can_be_cancelled(monkeypatch):
    monkeypatch.setenv("WORKPULSE_PARENT_PID","1234")
    parent=Mock();parent.is_running.return_value=True;parent.status.return_value="running"
    monkeypatch.setattr("workpulse.lifecycle.psutil.Process",lambda pid:parent)
    exited=threading.Event()
    stopped=watch_parent(exited.set,interval=.01)
    stopped.set()
    assert not exited.wait(.03)

def test_invalid_parent_identity_shuts_down_agent(monkeypatch):
    monkeypatch.setenv("WORKPULSE_PARENT_PID","not-a-pid")
    on_exit=Mock()
    assert watch_parent(on_exit) is None
    on_exit.assert_called_once()
