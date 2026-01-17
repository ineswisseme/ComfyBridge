import maya.cmds as cmds
import maya.mel as mel
import sys
import os
import subprocess

PORT = 7001


# Ensure commandPort is open

try:
    open_ports = cmds.commandPort(query=True, listPorts=True) or []
    if not any(f":{PORT}" in p for p in open_ports):
        cmds.commandPort(name=f":{PORT}", sourceType="python")
        print(f"[ComfyBridge] Maya commandPort opened on :{PORT}")
    else:
        print(f"[ComfyBridge] Maya commandPort already open on :{PORT}")
except Exception as e:
    cmds.warning(f"[ComfyBridge] Failed to open commandPort: {e}")


# Resolve ComfyBridge install root under Maya scripts


try:
    user_scripts_dir = cmds.internalVar(userScriptDir=True)  # ends with /scripts/
    project_root = os.path.normpath(os.path.join(user_scripts_dir, "ComfyBridge"))
    project_root_fs = project_root
    project_root_mel = project_root.replace("\\", "/")

    if not os.path.isdir(project_root_fs):
        raise RuntimeError(f"ComfyBridge folder not found at: {project_root_fs}")


except Exception as e:
    cmds.warning(f"[ComfyBridge] Could not resolve ComfyBridge path: {e}")
    raise



# Launch external viewer using venv python.exe + add logs for debugging.
try:
    venv_scripts = os.path.join(project_root_fs, "_venv", "Scripts")
    venv_python  = os.path.join(venv_scripts, "python.exe")
    viewer_py    = os.path.join(project_root_fs, "src", "comfybridge", "qt", "viewer_GUI.py")
    log_path     = os.path.join(project_root_fs, "viewer_launch.log")

    if not os.path.isfile(venv_python):
        raise RuntimeError(f"Venv python not found: {venv_python}")
    if not os.path.isfile(viewer_py):
        raise RuntimeError(f"viewer_GUI.py not found at: {viewer_py}")

    env = os.environ.copy()

    # Clean up env vars that may interfere with venv
    for k in ("PYTHONHOME", "PYTHONPATH", "PYTHONUSERBASE"):
        env.pop(k, None)

    # Make the venv “win” in PATH resolution
    env["VIRTUAL_ENV"] = os.path.join(project_root_fs, "_venv")
    env["PATH"] = venv_scripts + os.pathsep + env.get("PATH", "")
    env["COMFYBRIDGE_ROOT"] = project_root_fs

    # prevents user site-packages from interfering
    env["PYTHONNOUSERSITE"] = "1"

    with open(log_path, "w", encoding="utf-8") as log:
        subprocess.Popen(
            [venv_python, viewer_py],
            cwd=project_root_fs,
            env=env,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW,  
        )

    print(f"[ComfyBridge] Image viewer launched. Log: {log_path}")

except Exception as e:
    cmds.warning(f"[ComfyBridge] Failed to launch viewer: {e}")



# Launch toolbar_viewer.py

try:
    
    src_root = os.path.join(project_root_fs, "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from comfybridge.qt import toolbar_viewer
    
    toolbar_viewer.launch()

    print("[ComfyBridge] Toolbar launched.")

except Exception as e:
    cmds.warning(f"[ComfyBridge] Failed to launch toolbar: {e}")
