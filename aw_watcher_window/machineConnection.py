import subprocess
import uuid
import socket

def get_hardware_id():
    cmd = 'wmic csproduct get uuid'
    uuid = subprocess.check_output(cmd, shell=True).decode().split("\n")[1].strip()
    return uuid
hardwareBasedId = get_hardware_id()
macAdd = uuid.UUID(int=uuid.getnode()).hex[-12:]  # Last 12 characters of MAC
socketBasedId = socket.gethostname()

