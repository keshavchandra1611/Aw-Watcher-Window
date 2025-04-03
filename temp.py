import logging
import os
import json
import psutil
from datetime import datetime
from time import sleep
import ctypes

from .config import parse_args
from .lib import get_current_window

logger = logging.getLogger(__name__)

# JSON file to store blocked apps
BLOCKED_APPS_FILE = "blocked_apps.json"
USAGE_LIMIT = 10  # Maximum allowed usage time (seconds)


def initialize_blocked_apps_file():
    """Creates blocked_apps.json if it doesn't exist."""
    if not os.path.exists(BLOCKED_APPS_FILE):
        with open(BLOCKED_APPS_FILE, "w") as file:
            json.dump({"blocked_apps": {}}, file, indent=4)

def load_blocked_apps():
    """Loads blocked apps and their usage details from JSON."""
    try:
        with open(BLOCKED_APPS_FILE, "r") as file:
            return json.load(file).get("blocked_apps", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_blocked_apps(blocked_apps):
    """Saves blocked apps and their usage details to JSON."""
    with open(BLOCKED_APPS_FILE, "w") as file:
        json.dump({"blocked_apps": blocked_apps}, file, indent=4)

def add_blocked_app(app_name, duration=USAGE_LIMIT):
    """Adds an app to the blocked list and initializes tracking."""
    blocked_apps = load_blocked_apps()
    
    if app_name.lower() not in blocked_apps:
        blocked_apps[app_name.lower()] = {
            "total_usage": 0,  # Track total usage time
            "last_start_time": None,  # Store when the app was last started
            "blocked": False  # Flag to permanently block the app after exceeding usage
        }
        save_blocked_apps(blocked_apps)
        print(f"Blocked {app_name} with a usage limit of {duration} seconds.")

def update_app_usage():
    """Tracks running time and updates total usage correctly, ignoring inactive time."""
    blocked_apps = load_blocked_apps()
    current_time = datetime.now().timestamp()

    running_apps = set()  # Track currently running apps

    for proc in psutil.process_iter(attrs=['pid', 'name', 'create_time']):
        try:
            proc_name = proc.info['name'].lower()
            running_apps.add(proc_name)  # Mark as currently running

            if proc_name in blocked_apps:
                app_data = blocked_apps[proc_name]

                if app_data["blocked"]:
                    continue  # Skip already blocked apps

                if app_data["last_start_time"] is None:
                    # App just started, mark the start time
                    app_data["last_start_time"] = current_time

                # Calculate active session time **only if app was running last time**
                running_time = current_time - app_data["last_start_time"]
                if running_time > 0:
                    app_data["total_usage"] += running_time

                # Update last_start_time to current time
                app_data["last_start_time"] = current_time

                print(f"{proc_name} has used {app_data['total_usage']:.2f}s.")

                if app_data["total_usage"] >= USAGE_LIMIT:
                    app_data["blocked"] = True  # Mark app as permanently blocked
                    print(f"{proc_name} exceeded limit! Blocking now.")

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    # Reset last_start_time for apps that are **no longer running**
    for app_name in blocked_apps.keys():
        if app_name not in running_apps:
            blocked_apps[app_name]["last_start_time"] = None

    save_blocked_apps(blocked_apps)

def block_unwanted_apps():
    """Kills apps that have exceeded allowed usage time."""
    blocked_apps = load_blocked_apps()

    for proc in psutil.process_iter(attrs=['pid', 'name']):
        try:
            proc_name = proc.info['name'].lower()
            if proc_name in blocked_apps and blocked_apps[proc_name]["blocked"]:
                print(f"Killing {proc_name} (PID: {proc.info['pid']}) - Usage exceeded.")
                proc.terminate()
                sleep(1)
                if proc.is_running():
                    proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
        
        
        
def lock_system():
    """Locks the Windows system."""
    try:
        ctypes.windll.user32.LockWorkStation()
        logger.info("System locked successfully")
        print("System locked successfully")
    except Exception as e:
        logger.error(f"Failed to lock system: {e}")
        print(f"Failed to lock system: {e}")


def main():
    args = parse_args()

    # Ensure the blocked apps file exists
    initialize_blocked_apps_file()

    logger.info("App blocker started")

    # Ask user if they want to block a new app
    # user_input = input("Enter app name to block (or press Enter to skip): ").strip()
    # print("Blocking for 10 seconds")
    # # Ask user if they want to block a new app
    user_input = input("Enter app name to block (or 'lockSystem' to lock the system, or press Enter to skip): ").strip()
    
    if user_input.lower() == "locksystem":
        print("Locking the system")
        lock_system()
        return
    
    print("Blocking for 10 seconds")
    if user_input:
        add_blocked_app(user_input)

    while True:
        try:
            update_app_usage()
            block_unwanted_apps()
        except Exception:
            logger.exception("Error processing app usage")

        sleep(args.poll_time)





























import logging
import os
import re
import signal
import sys
from datetime import datetime, timezone
from time import sleep

from .config import parse_args
from .lib import get_current_window

logger = logging.getLogger(__name__)

# Run with LOG_LEVEL=DEBUG
log_level = os.environ.get("LOG_LEVEL")
if log_level:
    logger.setLevel(logging.__getattribute__(log_level.upper()))


def try_compile_title_regex(title):
    try:
        return re.compile(title, re.IGNORECASE)
    except re.error:
        logger.error(f"Invalid regex pattern: {title}")
        exit(1)


def main():
    args = parse_args()

    if sys.platform.startswith("linux") and (
        "DISPLAY" not in os.environ or not os.environ["DISPLAY"]
    ):
        raise Exception("DISPLAY environment variable not set")

    logger.info("aw-watcher-window started (without server)")

    heartbeat_loop(
        poll_time=args.poll_time,
        strategy=args.strategy,
        exclude_title=args.exclude_title,
        exclude_titles=[
            try_compile_title_regex(title)
            for title in args.exclude_titles
            if title is not None
        ],
    )


def heartbeat_loop(
    poll_time, strategy, exclude_title=False, exclude_titles=[]
):
    while True:
        if os.getppid() == 1:
            logger.info("window-watcher stopped because parent process died")
            break

        current_window = None
        try:
            current_window = get_current_window(strategy)
            logger.debug(current_window)
        except Exception:
            logger.exception("Error while fetching active window")
            continue

        if current_window:
            for pattern in exclude_titles:
                if pattern.search(current_window["title"]):
                    current_window["title"] = "excluded"

            if exclude_title:
                current_window["title"] = "excluded"

            now = datetime.now(timezone.utc)

            # **Print the active window info**
            print(f"{now}: {current_window}")

            # **Save to a local file**
            with open("window_log.txt", "a") as log_file:
                log_file.write(f"{now}: {current_window}\n")

        sleep(poll_time)
