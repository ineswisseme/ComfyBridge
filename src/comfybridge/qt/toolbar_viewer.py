
# tooldbar_viewer.py
import os
import sys
import maya.cmds as cmds
import math
import mtoa.utils as mutils
import maya.mel as mel


TOOLBAR_NAME = "BridgeyMayaToolbar"
WINDOW_WIDTH = 200
WINDOW_HEIGHT = 600


def launch():
    """
    Entry point called from shelf button.
    Creates (or recreates) the ComfyBridge toolbar.
    """

    # Delete existing toolbar if it exists
    if cmds.workspaceControl(TOOLBAR_NAME, exists=True):
        cmds.deleteUI(TOOLBAR_NAME)

    # Create dockable workspace control
    cmds.workspaceControl(
        TOOLBAR_NAME,
        label="Bridge",
        widthProperty="fixed",
        initialWidth=WINDOW_WIDTH,
        initialHeight=WINDOW_HEIGHT,
        fl = True
    )

    
    build_ui(TOOLBAR_NAME)


# helpers:


# camera radius adjustment
def set_camera_radius(radius):
    """
    Repositions BridgeCam_* cameras on a circle using their rotateY.
    """
    cams = cmds.ls("BridgeCam_*", type="transform") or []

    if not cams:
        cmds.warning("No BridgeCam_* cameras found.")
        return

    for cam in cams:
        try:
            angle_deg = cmds.getAttr(cam + ".rotateY")
            angle_rad = angle_deg * math.pi / 180.0

            x = math.sin(angle_rad) * radius
            z = math.cos(angle_rad) * radius

            cmds.setAttr(cam + ".translateX", x)
            cmds.setAttr(cam + ".translateZ", z)

        except Exception as e:
            cmds.warning(f"Failed to update {cam}: {e}")

    


def apply_radius_from_ui():
    radius = cmds.floatField("cb_radiusField", query=True, value=True)
    set_camera_radius(radius)


# texture projection and baking


def project_textures():
    
    PROJECT_ROOT = None

    for p in sys.path:
        candidate = os.path.join(p, "ComfyBridge")
        if os.path.isdir(candidate):
            PROJECT_ROOT = candidate
        else:
            pass
      
        
    OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'output')
    FRAMES_DIR = os.path.join(OUTPUT_DIR, 'frames')
   
   

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    
    # Find mesh
    meshes = cmds.ls("BridgeMesh", type="transform")
    if not meshes:
        cmds.warning("BridgeMesh not found.")
        return
    mesh = meshes[0]

   
    # Find cameras
    CAM_IDS = {1,2,3,4,5,6,7,8}

    
    cameras = cmds.ls("BridgeCam_*", type="transform") or []
    if not cameras:
        cmds.warning("No BridgeCam_* cameras found.")
        return

    def cam_index(name):
        try:
            return int(name.split("_")[-1])
        except ValueError:
            return -1

    cameras = sorted(cameras, key=cam_index)
    cameras = [c for c in cameras if cam_index(c) in CAM_IDS]

    if not cameras:
        cmds.warning("No allowed cameras found.")
        return


    
    # Create layered texture
    
    layered = cmds.shadingNode("layeredTexture", asTexture=True, name="bridge_layeredTex")
    
    # Build projections
    for i, cam in enumerate(cameras):
        idx = cam.split("_")[-1].zfill(3)
        img_path = f"{FRAMES_DIR}/render_{idx}.png"

        if not os.path.exists(img_path):
            cmds.warning(f"Missing frame: {img_path}")
            continue
    

        # File
        file_node = cmds.shadingNode("file", asTexture=True, name=f"bridge_file_{idx}")
        place2d = cmds.shadingNode("place2dTexture", asUtility=True)

        cmds.connectAttr(place2d + ".outUV", file_node + ".uvCoord", force=True)
        cmds.connectAttr(place2d + ".outUvFilterSize", file_node + ".uvFilterSize", force=True)
        cmds.setAttr(file_node + ".fileTextureName", img_path, type="string")

        # Projection
        proj = cmds.shadingNode("projection", asUtility=True, name=f"bridge_proj_{idx}")
        
       
        # Camera-facing mask
        sampler = cmds.shadingNode("samplerInfo", asUtility=True, name=f"bridge_sampler_{idx}")

        # Dot(normal, viewVector)
        dot = cmds.shadingNode("vectorProduct", asUtility=True, name=f"bridge_dot_{idx}")
        cmds.setAttr(dot + ".operation", 1)  # Dot product
        cmds.setAttr(dot + ".normalizeOutput", 1)

        cmds.connectAttr(sampler + ".normalCamera", dot + ".input1", f=True)

        # Camera view direction (0,0,-1 in camera space)
        cmds.setAttr(dot + ".input2X", 0)
        cmds.setAttr(dot + ".input2Y", 0)
        cmds.setAttr(dot + ".input2Z", -1)

        # Remap to 0–1 mask
        remap = cmds.shadingNode("remapValue", asUtility=True, name=f"bridge_maskRemap_{idx}")
        cmds.connectAttr(dot + ".outputX", remap + ".inputValue", f=True)

        # Soft falloff control
        cmds.setAttr(remap + ".inputMin", 0.0)
        cmds.setAttr(remap + ".inputMax", 0.3)
        cmds.setAttr(remap + ".outputMin", 0.0)
        cmds.setAttr(remap + ".outputMax", 1.0)

        
        # Multiply projection by mask
        mult = cmds.shadingNode("multiplyDivide", asUtility=True, name=f"bridge_projMult_{idx}")

        cmds.connectAttr(proj + ".outColor", mult + ".input1", f=True)
        cmds.connectAttr(remap + ".outValue", mult + ".input2X", f=True)
        cmds.connectAttr(remap + ".outValue", mult + ".input2Y", f=True)
        cmds.connectAttr(remap + ".outValue", mult + ".input2Z", f=True)

      
        # Connect masked result to layered texture
        layer = f"{layered}.inputs[{i}]"
        cmds.connectAttr(mult + ".output", layer + ".color", f=True)
        cmds.setAttr(layer + ".alpha", 1)
        cmds.setAttr(proj + ".projType", 8)  # Camera
        cmds.connectAttr(file_node + ".outColor", proj + ".image", force=True)
        cmds.setAttr(proj + ".fitFill", 2)
        cam_shape = cmds.listRelatives(cam, shapes=True, type="camera")[0]
        cmds.connectAttr(cam_shape + ".worldMatrix[0]", proj + ".linkedCamera", force=True)

        # Connect into layered texture
        layer = f"{layered}.inputs[{i}]"
        cmds.connectAttr(proj + ".outColor", layer + ".color", force=True)
        cmds.setAttr(layer + ".alpha", 1)
       

    # Create surface shader
    shader = cmds.shadingNode("surfaceShader", asShader=True, name="bridgeMerged_surface")
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=shader + "SG")

    cmds.connectAttr(layered + ".outColor", shader + ".outColor", force=True)
    cmds.connectAttr(shader + ".outColor", sg + ".surfaceShader", force=True)

    cmds.sets(mesh, edit=True, forceElement=sg)
    cmds.modelPanel('modelPanel4', edit=True, camera="BridgeCam_1")
    
    

def bake_textures():
    """ Bake projected textures into an exr using Arnold. """
    # check if arnold is loaded, it should auto-load but let's make sure.
    if not cmds.pluginInfo("mtoa", query=True, loaded=True):
        cmds.loadPlugin("mtoa")
        
    PROJECT_ROOT = None

    for p in sys.path:
        candidate = os.path.join(p, "ComfyBridge")
        if os.path.isdir(candidate):
            PROJECT_ROOT = candidate
        else:
            pass
      
        
    OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'output')

    output_dir = os.path.join(OUTPUT_DIR, 'bake')  
                   
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
        
    shape = cmds.ls("BridgeMeshShape")
    cmds.select(shape, replace=True)
    
      # Auto UVs 
    cmds.polyRetopo(targetFaceCount=10000, symmetry=0)
    cmds.polyProjection('BridgeMesh.f[0:]', t="Planar", md="p")
  

    # Arnold Render 
                      
    cmds.arnoldRenderToTexture(folder=output_dir, resolution=1048)

    # Add original shader lambert back with newly created texture file:
    shading_group = "initialShadingGroup"
    cmds.sets("BridgeMesh", edit=True, forceElement=shading_group)
    bake_text = cmds.shadingNode("file", asTexture=True, name="bridge_baked_file")
    place2d = cmds.shadingNode("place2dTexture",asUtility=True,name="bridge_baked_place2d")
    cmds.connectAttr(place2d + ".outUV", bake_text + ".uvCoord", f=True)
    cmds.connectAttr(place2d + ".outUvFilterSize", bake_text + ".uvFilterSize", f=True)
    texture_path = os.path.join(output_dir, "BridgeMeshShape.exr")
    cmds.setAttr(bake_text + ".fileTextureName", texture_path, type="string")
    cmds.setAttr(bake_text + ".colorSpace", "Raw", type="string")
    cmds.connectAttr(bake_text + ".outColor","openPBR_shader1.baseColor",f=True)
  
def render_scene():
    """ Render from camera_1, save as png in /render folder. """
    
    # get path     
    PROJECT_ROOT = None

    for p in sys.path:
        candidate = os.path.join(p, "ComfyBridge")
        if os.path.isdir(candidate):
            PROJECT_ROOT = candidate
        else:
            pass
      
        
    OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'output')

    render_dir = os.path.join(OUTPUT_DIR, 'render')  
    os.makedirs(render_dir, exist_ok=True)
    render_path = os.path.join(render_dir, "render.png").replace("\\", "/")
    
    mutils.createLocator("aiSkyDomeLight", asLight=True) # not removing any existing lights before creating new one.
    
    cmds.arnoldRenderView(cam="BridgeCam_1")
    mel.eval(f'arnoldRenderView -opt "Save Image (original)" "{render_path}"')   


def build_ui(parent):
    """
    Build the actual UI layout.
    """

    cmds.setParent(parent)

    # layout
    cmds.columnLayout(
        adjustableColumn=True,
        rowSpacing=10,
        columnAlign="center"
    )

    cmds.separator(height=10, style="in")

    cmds.text(label="Camera:")
    cmds.separator(height=15, style="in")
    cmds.floatField(
        "cb_radiusField",
        minValue=0.0,
        maxValue=500.0,      
        h=30,
        value=2.0,
        precision=2
    )

    cmds.button(
        label="Set new radius",
        height=30,
        command=lambda *_: apply_radius_from_ui()
    )

    cmds.separator(height=20)
    
    cmds.text(label="Rendering:")

    cmds.separator(height=15, style="in")
    cmds.button(
        label="Project Textures",
        height=40,
        command=lambda *_:project_textures()
    )
    
    cmds.separator(height=20)
    
    cmds.button(
        label="Bake Textures",
        height=40,
        command=lambda *_:bake_textures()
    )
    
    cmds.separator(height=20)

    cmds.button(
        label="Render Scene",
        height=40,
        command=lambda *_:render_scene()
    )
    
    cmds.separator(height=20)

   
    cmds.separator(height=20, style="none")
  

launch()