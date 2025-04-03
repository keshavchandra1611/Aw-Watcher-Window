import socketio
import os
import psutil
import subprocess
from time import sleep
from datetime import datetime, timezone
import pygetwindow as gw
import win32gui
import win32process
import json
import time
import atexit
import ctypes
import sys


import platform
import threading
from .machineConnection import hardwareBasedId, macAdd, socketBasedId


# Always Unique to differentiate the system
print(f"Hardware Based ID: {hardwareBasedId}\n"        # MOST UNIQUE: Hardware Based ID: xxxxx........
      f"Mac Address: {macAdd}\n"                       # MORE UNIQUE: Mac Address: yyy........
      f"Socket ID {socketBasedId}")                    # SIMPLE: Socket ID Keshav-Dell-P

# Initialize Socket.IO client
sio = socketio.Client()
SERVER_URL = 'http://localhost:4000'
# Connect to Socket.IO Server
def connect_socket():
    """Connects to the Socket.IO server with auto-reconnect."""
    while True:
        if not sio.connected:  # Check if not connected
            try:
                sio.connect(SERVER_URL)  # Connect to the server
                sio.emit('register', 'windows')  # Register Windows device
                print("✅ Connected to Socket.IO Server.")
                break  # Exit the loop when connected
            except Exception as e:
                print(f"❌ Connection failed: {e}. Retrying in 5 seconds...")
                sleep(5)  # Wait for 5 seconds before retrying
        else:
            # Register Windows device
            sio.emit('register', 'windows')
            print("✅ Already connected to the server.")
            break  # If already connected, break the loop

# Getting Data from main.py
def sendData(data):
    sio.emit("log", data)  # Send logs

# APIs from Server: ----------------------------------------------------------------------------------------------------------------
last_battery_status = {"percent": None, "charging": None}
def monitor_battery():
    global last_battery_status
    while True:
        if not sio.connected:
            time.sleep(5)  # Wait if not connected
            continue

        battery = psutil.sensors_battery()
        if battery is None:
            print("❌ Battery status not available")
            return

        percent = battery.percent
        charging = battery.power_plugged  # True if charging, False otherwise

        # Send update only if battery state has changed
        if (percent != last_battery_status["percent"]) or (charging != last_battery_status["charging"]):
            last_battery_status["percent"] = percent
            last_battery_status["charging"] = charging

            status = {
                "percent": percent,
                "charging": charging
            }

            # sio.emit("batteryUpdate", status)  # Send battery status to server
            print(
                f"🔋 Battery: {percent}% {'⚡ Charging' if charging else '🔋 On Battery'}")

        time.sleep(5)  # Check every 5 seconds


threading.Thread(target=monitor_battery, daemon=True).start()


# Handle request for data from server
@sio.on("helloReq")
def handle_request():
    """Handles data request from the server and sends back a response."""
    now = datetime.now(timezone.utc)
    response_data = {
        "device": "windows",
        "timestamp": "Keshav this side " + now.isoformat(),
        "message": "🔥 Response from Windows App!"
    }
    print("📤 Sending response:", response_data)
    sio.emit("HelloRes", response_data)  # Send response back


# Handle incoming commands from server
@sio.on("execute_command")
def handle_command(data):
    """Handles commands received from the server."""
    print(f"📥 Received command: {data['command']}")

    command = data.get("command", "")
    print(data)
    if command == "lock_system":
        print("🔒 Locking system...")
        os.system("rundll32.exe user32.dll,LockWorkStation")  # Lock Windows


# Get Last 50 Logs starts -----------------------------------
LOG_FILE = "window_log.txt"
def get_last_50_lines(file_path, num_lines=50):
    """Returns the last 'num_lines' lines from the given text file."""
    try:
        with open(file_path, 'r') as file:
            lines = file.readlines()
            # Return the last 'num_lines' lines from the file
            return lines[-num_lines:]  # Slicing the list to get last 50 lines
    except FileNotFoundError:
        return ["Log file not found."]
    except Exception as e:
        return [f"Error reading file: {str(e)}"]

@sio.on("request-last-50-logs")
def get_logs():
    """API endpoint that returns the last 50 lines of the log file."""
    last_50_logs = get_last_50_lines(LOG_FILE, num_lines=20)
    # Return the logs as a JSON response
    sio.emit('last-50', last_50_logs)
# Get Last 50 Logs ends -----------------------------------

# Killing an app starts -------------------------------------
@sio.on('kill-app')
def kill_app(data):
    """
    Kill the app based on its executable name (e.g., 'Code.exe')
    """
    app_name = data.get('app_name') or "notepad.exe"
    killed = False
    # Iterate over all running processes
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # Check if the process name matches the app name
            if proc.info['name'].lower() == app_name.lower():
                print(
                    f"Killing process {app_name} with PID {proc.info['pid']}")
                proc.terminate()  # Terminate kardo Process 
                proc.wait()  # Wait for the process to terminate
                killed = True
                # return f"{app_name} terminated successfully"
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    if (killed):
        message = f'{app_name} killed-successfully'
        sio.emit('killed-app', message)
    else:
        sio.emit('killed-app', 'Notepad is not running')
# Killing an app ends -------------------------------------


@sio.on('lock_System')
def lock_system():
    print("🔒 Locking the system...")

    # Execute the lock command
    # Lock the Windows system
    os.system("rundll32.exe user32.dll,LockWorkStation")

    # Send response back to the server
    response = {
        "status": "success",
        "message": "System locked successfully",
    }
    sio.emit("lockSystem_response", response)  # Send response to server


sio.on("ShutDown")
def shut_down():
    print("Shutting down the system...")
    os.system("shutdown /s /t 1")  # Shut down the system in
    # 1 second
    sio.emit('shut_down_response', {
             'status': 'success', 'message': "System shutting down..."})  # Send response to server



# Get system Name starts -------------------------------------
@sio.on("system_name")
def system_name():
    print("System Name legaya Server")
    system_name = platform.node()
    sio.emit('got_System', system_name)
# Get system Name starts -------------------------------------


def get_process_name_from_hwnd(hwnd):
    """Retrieve the process name from a window handle (hWnd)."""
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)  # Get process ID from hWnd
        process = psutil.Process(pid)
        return process.name()  # Return the process name
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None  # If process isn't found, return None


@sio.on("W-windows_Running_Apps")
def get_running_apps():
    """Returns a list of currently running app names (not window titles)."""
    running_apps = set()  # Use a set to avoid duplicates

    for win in gw.getAllWindows():
        if win.visible and win.title.strip():  # Ensure window is visible and has a title
            process_name = get_process_name_from_hwnd(win._hWnd)
            if process_name:
                running_apps.add(process_name)  # Store only the process name

    running_apps_list = list(running_apps)
    print(running_apps_list)
    return running_apps_list



JSON_FILE = "blocked_apps.json"
def load_blocked_apps():
    """Load app statuses from JSON, ensuring all apps are stored."""
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r") as f:
            return json.load(f)
    return {}  # Return empty dictionary if file doesn't exist


def save_blocked_apps(data):
    """Save updated app statuses to JSON."""
    with open(JSON_FILE, "w") as f:
        json.dump(data, f, indent=4)


@sio.on("W-manageApps")
def modify_blocked_apps(data):
    """Modify the block status of an app and store it permanently."""

    action = data.get("action")  # "add" (block) or "remove" (unblock)
    app_name = data.get("app_name")  # App name

    if not app_name:
        print("❌ No app name provided!")
        return

    blocked_apps = load_blocked_apps()

    if action == "add":
        blocked_apps[app_name] = "blocked"
    elif action == "remove":
        blocked_apps[app_name] = "unblocked"

    save_blocked_apps(blocked_apps)
    print(f"✅ Updated App List: {blocked_apps}")


def block_apps():
    """Continuously monitor and kill blocked apps."""
    while True:
        blocked_apps = load_blocked_apps()
        for process in psutil.process_iter(['pid', 'name']):
            app_name = process.info['name']
            if blocked_apps.get(app_name) == "blocked":
                try:
                    os.kill(process.info['pid'], 9)  # Force kill process
                    print(
                        f"❌ Blocked: {app_name} (PID: {process.info['pid']})")
                except Exception as e:
                    print(f"⚠️ Error stopping {app_name}: {e}")
        time.sleep(2)  # Check every 2 seconds


def run_as_admin():
    """ Relaunch the script with admin privileges if not already running as admin. """
    if ctypes.windll.shell32.IsUserAnAdmin():
        return  # Already running as admin

    script = sys.argv[0]
    params = " ".join(f'"{arg}"' for arg in sys.argv[1:])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
    sys.exit()

# def find_and_uninstall_app(app_name):
#     """ Finds and uninstalls the specified application silently. """
#     try:
#         run_as_admin()  # Ensure script is running as admin

#         # Search for the application's uninstall string in the registry
#         reg_query = subprocess.check_output(
#             f'reg query HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall /s | findstr /i "{app_name}"',
#             shell=True, text=True, errors="ignore"
#         )

#         uninstall_path = None
#         for line in reg_query.split("\n"):
#             if "UninstallString" in line:
#                 uninstall_path = line.split("    ")[-1].strip()
#                 break

#         if not uninstall_path:
#             print(f"Uninstall command for '{app_name}' not found in the registry.")
#             return

#         print(f"Found uninstall command: {uninstall_path}")

#         # Remove extra quotes around the path
#         uninstall_path = uninstall_path.strip('"')

#         # Ensure silent uninstallation
#         if "msiexec" in uninstall_path.lower():
#             command = f'{uninstall_path} /quiet /norestart'
#         else:
#             command = f'"{uninstall_path}" /S'

#         # Run the silent uninstall command
#         subprocess.run(command, shell=True, check=True)
#         print(f"{app_name} uninstalled successfully.")

#     except subprocess.CalledProcessError as e:
#         print(f"Error uninstalling {app_name}: {e}")
#     except Exception as e:
#         print(f"Unexpected error: {e}")

# # Example Usage
# app_to_uninstall = "Notepad++"
# find_and_uninstall_app(app_to_uninstall)


def disable_usb():
    """Disables USB storage devices via Windows Registry."""
    subprocess.run(
        'reg add HKLM\\SYSTEM\\CurrentControlSet\\Services\\USBSTOR /v Start /t REG_DWORD /d 4 /f',
        shell=True
    )
    print("USB storage devices disabled.")

def enable_usb():
    """Enables USB storage devices via Windows Registry (Restores on Exit)."""
    subprocess.run(
        'reg add HKLM\\SYSTEM\\CurrentControlSet\\Services\\USBSTOR /v Start /t REG_DWORD /d 3 /f',
        shell=True
    )
    print("USB storage devices enabled.")

# Run as admin before executing USB modifications
run_as_admin()

# Restore USB on script exit wala part
atexit.register(enable_usb)

# Disable USB while script runs wala part
disable_usb()

# Script chalti rahegi for usb
try:
    while True:
        time.sleep(5)
except KeyboardInterrupt:
    print("Script terminated. USB ports will be re-enabled.")
