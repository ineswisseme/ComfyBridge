from pathlib import Path
import shutil

root = Path(__file__).resolve().parent
venv = root / "_venv"

if venv.exists():
    shutil.rmtree(venv)
    print("[ComfyBridge] venv removed.")
else:
    print("[ComfyBridge] Nothing to uninstall.")
