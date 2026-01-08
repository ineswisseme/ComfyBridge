# comfybridge/core/maya_bridge.py

import socket
import textwrap
from pathlib import Path
from comfybridge.config import load_config, PROJECT_ROOT

cfg = load_config()

MAYA_HOST = cfg.get("maya_host", "127.0.0.1") # later: allow hostname ??
MAYA_PORT = int(cfg.get("maya_port", 7001)) 



def is_maya_running() -> bool:
    """Check if Maya's commandPort is open."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.2)
        s.connect((MAYA_HOST, MAYA_PORT))
        s.close()
        return True
    except:
        return False



def send_python_to_maya(code: str) -> bool:
    """Send Python code string to Maya through commandPort."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((MAYA_HOST, MAYA_PORT))

        
        if not code.endswith("\n"):
            code += "\n"

        s.sendall(code.encode("utf-8"))
        s.close()

        print(" Code successfully sent to Maya.")
        return True

    except Exception as e:
        print(f" ERROR sending code: {e}, check if port is correct.")
        return False



def import_obj_into_maya(obj_path: str) -> bool:
    """Import OBJ into Maya and assign shader."""
    
    
    
    if not is_maya_running():
        print("Maya commandPort not open")
        return False

   
    
    maya_cmd = textwrap.dedent(f"""
        import maya.cmds as cmds
        import os
        import math
        import sys
        
        
        # path env:
        
        PROJECT_ROOT = None

        for p in sys.path:
            candidate = os.path.join(p, "ComfyBridge")
            if os.path.isdir(candidate):
                PROJECT_ROOT = candidate
            else:
                pass
      
        
        OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'output')
        FRAMES_DIR = os.path.join(OUTPUT_DIR, 'frames')
        
        OBJ_PATH = r"{obj_path}"
        
        
        try:
        
           

            nodes_before = set(cmds.ls(tr=True))
            cmds.file(OBJ_PATH, i=True, type="OBJ", ignoreVersion=True,
                      ra=True, mergeNamespacesOnClash=False, options="mo=1", pr=True)
            nodes_after = set(cmds.ls(tr=True))

            new_nodes = list(nodes_after - nodes_before)
            print(" New nodes:", new_nodes)
            
            for n in new_nodes:
                try:
                    # Scale Y by -1
                    cmds.setAttr(n + ".scaleY", -1)

                    # Rotate Z by 90 degrees
                    cmds.setAttr(n + ".rotateZ", 90)
                    
                    

                    # Freeze transforms to bake the correction
                    cmds.makeIdentity(
                        n,
                        apply=True,
                        translate=False,
                        rotate=True,
                        scale=True,
                        normal=False
                    )

                except Exception as e:
                    print("Transform fix failed on", n, ":", str(e))

            for n in new_nodes:
                
                try:
                    cmds.sets(n, e=True, forceElement="lambert1SG")
                except:
                    pass
            cmds.rename('mesh_Mesh', 'BridgeMesh')
            print(" OBJ import complete.")
           
            
            image_dir = FRAMES_DIR  
                
            n_views = 8
            radius = 2.0
            trs_list = []
            
            
            cams = cmds.ls("BridgeCam_*", type="transform")
            if cams:
                cmds.delete(cams)
                
            for i in range(n_views):
                cam_name = "BridgeCam*"
                cam, cam_shape = cmds.camera(name=cam_name)
                trs_list.append(cam)
                
            for i, cam in enumerate(trs_list):
                angle_deg = (360.0 / n_views) * i
                angle_rad = angle_deg * 3.141592653589793 / 180.0
                
                x = radius * math.sin(angle_rad)
                z = radius * math.cos(angle_rad)
                
                cmds.move(0,0,0, cam + ".scalePivot", ".rotatePivot", absolute=True)
                cmds.rotate(0, angle_deg, 0, cam, absolute=True)
                
                cmds.setAttr(cam + ".translateX", x)
                cmds.setAttr(cam + ".translateY", 0)
                cmds.setAttr(cam + ".translateZ", z)

            camera_list = cmds.ls("BridgeCam_*", type="transform") or []
            
            if not camera_list:
                cmds.warning("No BridgeCam cameras found.")
                
            for cam in camera_list:
                
                cam_index = cam.split("_")[-1]
                frame_str = cam_index.zfill(3)

                            
                img_path = image_dir + "/render_" + frame_str + ".png"
                cam_shapes = cmds.listRelatives(cam, shapes=True, type="camera") or []
                
                cam_shape = cam_shapes[0]
                
                
                try:
                    _, img_plane = cmds.imagePlane(camera=cam_shape)
                    cmds.setAttr(img_plane + ".imageName", img_path, type="string")                        
                    cmds.setAttr(img_plane + ".displayOnlyIfCurrent", 1)
                    cmds.setAttr(img_plane + ".fit", 1)
                    cmds.setAttr(img_plane + ".depth", 100)
                    print("Cameras imported into Maya.")
                
                except Exception as e:
                    cmds.warning("Failed to attach image plane to " + cam + ": " + str(e))

        except Exception as e:
            print(" Maya OBJ Import Error:", str(e))
            
       
                
    
    """)

    return send_python_to_maya(maya_cmd)



