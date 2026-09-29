"""
resources.py
-------------
Locates bundled asset files (logo/icon) correctly whether the app is
running from source (`python app/main.py`) or from a PyInstaller-frozen
.exe, where bundled data lives under a temporary `sys._MEIPASS` directory
instead of next to the .py files.
"""
import os
import sys


def resource_path(*relative_parts):
    """Absolute path to a bundled resource, e.g.
    resource_path("assets", "dotsec_logo.png")."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, *relative_parts)
