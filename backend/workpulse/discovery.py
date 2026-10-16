"""Local-only discovery for the optional browser extension.

The main FastAPI API still binds a random port and requires an ephemeral
application capability. The discovery endpoint returns only the port, never
the capability, JWT or local account metadata.
"""
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

DISCOVERY_PORT=47631
logger=logging.getLogger("workpulse.discovery")

def start_discovery(api_port:int):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path!="/workpulse-port":
                self.send_error(404);return
            payload=json.dumps({"port":api_port}).encode()
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            self.send_header("Cache-Control","no-store")
            origin=self.headers.get("Origin","")
            if origin.startswith("chrome-extension://") or origin.startswith("extension://"):
                self.send_header("Access-Control-Allow-Origin",origin)
                self.send_header("Vary","Origin")
            self.send_header("Content-Length",str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        def log_message(self,format,*args):
            pass
    try:
        server=ThreadingHTTPServer(("127.0.0.1",DISCOVERY_PORT),Handler)
        t=threading.Thread(target=server.serve_forever,name="workpulse-browser-discovery",daemon=True)
        t.start()
        return server
    except OSError:
        logger.warning("Browser discovery port is already occupied")
        return None
