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


# Launch external viewer using _venv (pythonw.exe)

try:
    venv_pythonw = os.path.join(project_root_fs, "_venv", "Scripts", "pythonw.exe")
    venv_python = os.path.join(project_root_fs, "_venv", "Scripts", "python.exe")

    viewer_py = os.path.join(project_root_fs, "src", "comfybridge", "qt", "viewer_GUI.py")

    if not os.path.isfile(viewer_py):
        raise RuntimeError(f"viewer_GUI.py not found at: {viewer_py}")

    # get correct venv python if not fallback to python.exe
    py_exec = venv_pythonw if os.path.isfile(venv_pythonw) else venv_python
    if not os.path.isfile(py_exec):
        raise RuntimeError(
            "ComfyBridge venv python not found, check install.\n"
            f"Expected: {venv_pythonw} or {venv_python}"
        )

    # pass project root via env var so external app can resolve paths
    env = os.environ.copy()
    env["COMFYBRIDGE_ROOT"] = project_root_fs

    subprocess.Popen([py_exec, viewer_py], cwd=project_root_fs, env=env)
    print("[ComfyBridge] Image viewer launched.")

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
