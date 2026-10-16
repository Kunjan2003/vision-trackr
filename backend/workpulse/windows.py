"""Windows-only foreground metadata and inactivity detection. Never captures keys or pixels."""
import sys
from dataclasses import dataclass

@dataclass(frozen=True)
class Foreground:
    app_name: str = ""
    title: str = ""
    idle_seconds: float = 0
    locked: bool = False

def observe() -> Foreground:
    if sys.platform != "win32":
        return Foreground()
    import ctypes
    import psutil
    from ctypes import wintypes
    import win32gui
    import win32process

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    li = LASTINPUTINFO()
    li.cbSize = ctypes.sizeof(li)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li))
    ticks = ctypes.windll.kernel32.GetTickCount64()
    # LASTINPUTINFO.dwTime is 32 bits and wraps at ~49 days.
    idle = ((ticks & 0xFFFFFFFF) - li.dwTime) & 0xFFFFFFFF
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return Foreground(idle_seconds=idle / 1000, locked=True)
    try:
        title = win32gui.GetWindowText(hwnd)[:500]
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        app = psutil.Process(pid).name().lower()
        return Foreground(app_name=app, title=title, idle_seconds=idle / 1000)
    except (OSError, psutil.Error):
        return Foreground(idle_seconds=idle / 1000)
