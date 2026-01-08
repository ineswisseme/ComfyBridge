# comfybridge/core/generate_model.py

"""
Full pipeline for generating a 3D model:
1. Export cropped object using Rembg
2. Run TripoSR via CLI
3. Import into Maya if its port is open
"""

import os
import shutil
import subprocess
import sys
import cv2
from comfybridge.core.io_utils import export_object_with_rembg, generate_multiview_images
from comfybridge.core.maya_bridge import is_maya_running, import_obj_into_maya
from comfybridge.config import TRIPOSR_RUN, OUTPUT_DIR



# CONFIG

PYTHON_EXE = sys.executable

os.makedirs(OUTPUT_DIR, exist_ok=True)


# Run TripoSR

def run_triposr_cli(input_png: str) -> str:
    
    views = generate_multiview_images(input_png, OUTPUT_DIR)
   
     
    cmd = [
        PYTHON_EXE,
        TRIPOSR_RUN,
    ]

   
    cmd.extend(views)
    cmd.extend([
        "--output-dir",
        OUTPUT_DIR,
        "--render",
        
    ])


    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    for line in process.stdout:
        print("[TripoSR]", line.strip())

    process.wait()

    if process.returncode != 0:
        err = process.stderr.read()
        raise RuntimeError(f"TripoSR failed:\n{err}")

        
    newest_obj = None
    newest_time = -1

    for root, dir, files in os.walk(OUTPUT_DIR):
        for f in files:
            if f.endswith(".obj"):
                full = os.path.join(root, f)
                t = os.path.getmtime(full)
                if t > newest_time:
                    newest_time = t
                    newest_obj = full

    if not newest_obj:
        raise RuntimeError("Mesh generation finished but no obj file.")

    
    return newest_obj


def generate_3d_model(full_image_np, mask_np, basename="model",
                      progress_callback=None) -> dict:


    
    crop_path = os.path.join(OUTPUT_DIR, f"{basename}.png")

    if progress_callback:
        progress_callback(10, "Analysing image…")

    export_object_with_rembg(full_image_np, mask_np, crop_path)

    if progress_callback:
        progress_callback(40, "Generating 3D model…")

    obj_path = run_triposr_cli(crop_path)
    
    if progress_callback:
        progress_callback(50, "Cleaning up render alpha…")
    
    

    if progress_callback:
        progress_callback(70, "Building cameras…")

    maya_imported_obj = False

   
    if is_maya_running():
        print(" Maya detected, importing model & cameras")

        if progress_callback:
            progress_callback(80, "Importing OBJ in Maya…")

        maya_imported_obj = import_obj_into_maya(obj_path)
        
             

    else:
        print("Maya not found, skipping import")

    if progress_callback:
        progress_callback(100, "Done!")

    return {
        "crop_path": crop_path,
        "obj_path": obj_path,
        "maya_imported": maya_imported_obj,
        "maya_imported_obj": maya_imported_obj
       
    }
