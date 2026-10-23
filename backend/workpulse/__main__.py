"""Launch via python -m workpulse or the PyInstaller onefile executable."""
import ctypes
import logging
import os
import socket
import sys

def single_instance():
    if sys.platform == "win32":
        kernel = ctypes.windll.kernel32
        from ctypes import wintypes
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        kernel.CreateMutexW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.CreateMutexW(None, False, "Local\\WorkPulsePythonAgent")
        if not handle:
            raise ctypes.WinError()
        if kernel.GetLastError() == 183:
            print("WorkPulse agent is already running", file=sys.stderr)
            sys.exit(2)
        return handle
    return None

def main():
    print("Starting local tracking agent", file=sys.stderr, flush=True)
    _mutex = single_instance()
    from .db import migrate
    print("Preparing local database", file=sys.stderr, flush=True)
    migrate()
    print("Local database ready", file=sys.stderr, flush=True)
    from . import agent
    agent.restore_user_session()
    worker = agent.launch()
    from .api import app
    import uvicorn
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(128)
    port = sock.getsockname()[1]
    from .discovery import start_discovery
    discovery = start_discovery(port)
    app.state.port = port
    # The secret is transmitted to Electron via inherited environment, not a URL or log.
    print(f'WORKPULSE_PORT={port}', flush=True)
    try:
        config = uvicorn.Config(app, log_level="warning", access_log=False, host="127.0.0.1")
        server = uvicorn.Server(config)
        from .lifecycle import watch_parent
        parent_watch = watch_parent(lambda: setattr(server, "should_exit", True))
        try:
            server.run(sockets=[sock])
        finally:
            if parent_watch:
                parent_watch.set()
    finally:
        agent.stop()
        if discovery:
            discovery.shutdown()
            discovery.server_close()
        sock.close()
        if _mutex is not None:
            ctypes.windll.kernel32.CloseHandle(_mutex)

if __name__ == "__main__":
    main()
