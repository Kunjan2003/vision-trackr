"""Release the local agent if the desktop that launched it exits unexpectedly."""
import os
import logging
import threading
import psutil


def watch_parent(on_exit, interval=1.0):
    value = os.getenv("WORKPULSE_PARENT_PID")
    if not value:
        return None
    try:
        parent = psutil.Process(int(value))
        # Holding the Process identity also detects PID reuse.
        if not parent.is_running():
            logging.getLogger("workpulse").warning("Launching desktop is no longer running")
            on_exit()
            return None
    except (ValueError, psutil.Error) as error:
        logging.getLogger("workpulse").warning("Cannot find launching desktop: %s", error)
        on_exit()
        return None
    stopped = threading.Event()

    def watch():
        while not stopped.wait(interval):
            try:
                alive = parent.is_running() and parent.status() != psutil.STATUS_ZOMBIE
            except psutil.Error:
                alive = False
            if not alive:
                logging.getLogger("workpulse").warning("Launching desktop exited; stopping local agent")
                on_exit()
                return

    threading.Thread(target=watch, name="workpulse-parent-watch", daemon=True).start()
    return stopped
