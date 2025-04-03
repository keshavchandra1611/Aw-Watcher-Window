import psutil
import json
import time
import threading
import os
import win32gui
import win32process
from collections import OrderedDict  # ✅ Preserve JSON order

JSON_FILE = "usage.json"

def load_usage_data():
    """Load usage data from the JSON file without modifying its order."""
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f, object_pairs_hook=OrderedDict)  # ✅ Preserve order
            except json.JSONDecodeError:
                return OrderedDict()
    return OrderedDict()

def update_app_usage_time(app_name, usage_time=None, fg_usage_time=None):
    """Update only the usage time of a single app without rewriting the entire JSON object."""
    if not os.path.exists(JSON_FILE):
        return

    with open(JSON_FILE, "r+", encoding="utf-8") as f:
        try:
            existing_data = json.load(f, object_pairs_hook=OrderedDict)  # ✅ Keep order
        except json.JSONDecodeError:
            existing_data = OrderedDict()

        if app_name in existing_data:
            if usage_time is not None:
                existing_data[app_name]["usage_time"] = usage_time
            if fg_usage_time is not None:
                existing_data[app_name]["fg_usage_time"] = fg_usage_time

            # ✅ Write only the updated data, preserving order
            f.seek(0)
            json.dump(existing_data, f, indent=4)
            f.truncate()

def add_app(app_name, limit_seconds=None):
    """Add a new app without modifying existing data or rearranging JSON.
       If the app already exists, update the limit only if it's not None.
    """
    if not os.path.exists(JSON_FILE):
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(OrderedDict(), f, indent=4)

    with open(JSON_FILE, "r+", encoding="utf-8") as f:
        try:
            existing_data = json.load(f, object_pairs_hook=OrderedDict)  # ✅ Preserve order
        except json.JSONDecodeError:
            existing_data = OrderedDict()

        if app_name in existing_data:
            # ✅ Update limit only if it's not None
            if limit_seconds is not None:
                existing_data[app_name]["limit"] = limit_seconds
        else:
            # ✅ Add new app if not present
            existing_data[app_name] = {"usage_time": 0, "fg_usage_time": 0, "limit": limit_seconds}

        # ✅ Write back changes while keeping order
        f.seek(0)
        json.dump(existing_data, f, indent=4)
        f.truncate()


def update_running_apps():
    """Continuously checks running apps and adds new apps without modifying existing data."""
    while True:
        running_apps = {p.info['name'].lower() for p in psutil.process_iter(attrs=['name'])}
        existing_data = load_usage_data()

        for app_name in running_apps:
            if app_name not in existing_data:
                add_app(app_name)  # Append new app without modifying existing ones

        time.sleep(5)  # Check every 5 seconds for new apps

def get_active_window_process():
    """Get the process name of the currently active (foreground) window."""
    try:
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        for proc in psutil.process_iter(attrs=['pid', 'name']):
            if proc.info['pid'] == pid:
                return proc.info['name'].lower()
    except Exception:
        return None
    return None

def check_and_update_usage():
    """Continuously check running apps, update total & foreground usage time, and enforce limits."""
    start_times = {}

    while True:
        usage_data = load_usage_data()
        running_apps = {p.info['name'].lower(): p for p in psutil.process_iter(attrs=['pid', 'name'])}
        active_app = get_active_window_process()

        for app_name in usage_data.keys():
            app_lower = app_name.lower()

            if app_lower in running_apps:
                if app_name not in start_times:
                    start_times[app_name] = time.time()

                elapsed_time = time.time() - start_times[app_name]
                total_usage = usage_data[app_name]["usage_time"] + elapsed_time
                fg_usage = usage_data[app_name]["fg_usage_time"]

                # If the app is in the foreground, update foreground usage
                if app_lower == active_app:
                    fg_usage += elapsed_time

                start_times[app_name] = time.time()  # Reset start time for next check

                # Check if foreground usage exceeded limit
                if usage_data[app_name]["limit"] is not None and fg_usage >= usage_data[app_name]["limit"]:
                    print(f"Foreground usage limit exceeded for {app_name}. Terminating...")
                    try:
                        psutil.Process(running_apps[app_lower].info['pid']).terminate()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                # ✅ Update only changed values
                update_app_usage_time(app_name, total_usage, fg_usage)
            else:
                start_times.pop(app_name, None)  # Remove start time if app is closed

        time.sleep(1)  # Check every second

add_app("notepad.exe", 10)
add_app("chrome.exe", None) 

threading.Thread(target=update_running_apps, daemon=True).start()
