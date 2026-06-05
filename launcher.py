"""
Desktop launcher for Freight Daddy CRM.
Starts the Flask server and opens a browser window automatically.
Used as the PyInstaller entry point.
"""
import sys
import os
import threading
import webbrowser
import time
from pathlib import Path

# Set resource/data dirs before importing app
if getattr(sys, "frozen", False):
    os.environ["CRM_RESOURCE_DIR"] = sys._MEIPASS
    os.environ["CRM_DATA_DIR"]     = str(Path(sys.executable).parent)

from app import app

PORT = 5000

def _open_browser():
    time.sleep(1.5)
    webbrowser.open(f"http://localhost:{PORT}")

if __name__ == "__main__":
    print("=" * 40)
    print("  Freight Daddy CRM")
    print(f"  http://localhost:{PORT}")
    print("  Close this window to stop the app.")
    print("=" * 40)
    threading.Thread(target=_open_browser, daemon=True).start()
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
