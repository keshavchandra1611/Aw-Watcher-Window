from datetime import datetime, timezone, timedelta
IST = timezone(timedelta(hours=5, minutes=30)) # Indian Time
from threading import Thread
from time import sleep

from .app_Uage import check_and_update_usage
from .server import sio, connect_socket, sendData, block_apps
from .config import parse_args
import sys
import os
from .lib import get_current_window
import logging
logger = logging.getLogger(__name__)

# Log File
LOG_FILE = "window_log.txt"

def heartbeat_loop(poll_time, strategy, exclude_title=False, exclude_titles=[]):
    """Continuously logs the active window and writes to a file."""
    while True:
        current_window = None
        try:
            current_window = get_current_window(strategy)
        except Exception:
            logger.exception("Error while fetching active window")
            continue

        if current_window:
            try:
                for pattern in exclude_titles:
                    if pattern.search(current_window["title"]):
                        current_window["title"] = "excluded"

                if exclude_title:
                    current_window["title"] = "excluded"

                now = datetime.now(IST)
                # log_entry = f"{now}: {current_window}"
                # log_entry = f"{current_window}"
                log_entry = f"{now}: [App: {current_window['app']}]"

                # Print to Terminal
                print(log_entry)
                sendData(log_entry)

                # Save to File
                with open(LOG_FILE, "a") as log_file:
                    log_file.write(log_entry + "\n")
            except Exception as e:
                print(f"❌ Error sending log: {e}")
                connect_socket() # Server.py
        # sleep(poll_time)
        sleep(5)

# Main function
def main():
    """Main function to start the system."""
    connect_socket()  # Connect to Socket.IO Server # Server.py
    
    args = parse_args()
    # Start the background logging thread
    thread1 = Thread(
        target=heartbeat_loop,
        args=(args.poll_time, args.strategy, args.exclude_title, args.exclude_titles),
        daemon=True,
    )
    thread1.start()
    
    thread2 = Thread (target= block_apps,daemon=True)
    thread2.start()
    
    thread3 = Thread(target=check_and_update_usage, daemon=True)
    thread3.start()
    
    if sys.platform.startswith("linux") and (
        "DISPLAY" not in os.environ or not os.environ["DISPLAY"]
    ):
        raise Exception("DISPLAY environment variable not set")
    print("Window tracker started. Running background process.")

    # Keep the script running
    while True:
        sleep(1)
