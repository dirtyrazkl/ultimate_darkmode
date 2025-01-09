import psutil
import sys
import os

def is_script_already_running(script_name):
    current_pid = os.getpid()
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.pid == current_pid:
                continue
            if proc.name().lower().startswith('python'):
                cmdline = proc.cmdline()
                if any(script_name in cmd for cmd in cmdline):
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False
