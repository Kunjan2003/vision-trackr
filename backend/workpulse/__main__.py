"""Launch via python -m workpulse or the PyInstaller onefile executable."""
import ctypes
import logging
import os
import socket
import sys

def single_instance():
    if sys.platform == "win32":
        kernel = ctypes.windll.kernel32
        handle = kernel.CreateMutexW(None, False, "Local\\WorkPulsePythonAgent")
        if kernel.GetLastError() == 183:
            print("WorkPulse agent is already running", file=sys.stderr)
            sys.exit(2)
        return handle
    return None

def main():
    _mutex = single_instance()
    from .db import migrate
    migrate()
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
        uvicorn.Server(config).run(sockets=[sock])
    finally:
        agent.stop()
        if discovery:
            discovery.shutdown()
            discovery.server_close()
        sock.close()

if __name__ == "__main__":
    main()
