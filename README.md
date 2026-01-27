# ComfyBridge:

This plug-in is designed to run on Maya 2026. Previous versions aren't supported.
Minimum GPU RAM required is 8GB, however you can install and run it as CPU only. 
Python 3.11 and above required.

This plug-in uses **TripoSR** (https://github.com/VAST-AI-Research/TripoSR) to generate the 3D model. 

# How to Install:

- Download the files and paste to:
```
    C:\Users\<UserName>\Documents\maya\2026\scripts

```
Make sure the path is specifically ...\\Documents\maya\2026\scripts\ComfyBridge\

- Run install in windows cmd:
```
    python install.py
```
This will create a temporary .venv folder containing all the needed dependencies. Let it run until you see "print('ComfyBridge install OK')" in the terminal.

The default install is for GPU usage. To install the CPU version add --cpu at the end of the command.
```
    python install.py --cpu
```

Uninstall deletes the .venv files.

- Open Maya 2026, drag-and-drop the following script into the script editor, then with middle mouse button drag it in any shelf of your choice:

  C:\Users\<UserName>\Documents\maya\2026\scripts\ComfyBridge\src\comfybridge\qt\maya_shelf_btn.py

You can edit the shelf button name as you wish and add the icon.png found at the root of the directory.

- Run the script via the maya shelf button you just created. The button opens Maya Port Command (needed to send file to maya from the plug-in) and launches both the toolbar and the viewer GUI.

# About the plug-in:

This plug-in use TripoSR to generate the 3D object in the image. TripoSR is a lightweight model with its own limitations, it does not handle symmetry or high-level model generation. You can tweak TripoSR's targeted polymesh count here:

```
    C:\Users\<UserName>\Documents\maya\2026\scripts\ComfyBridge\src\comfybridge\models\TripoSR\run.py
```
# Use rendered image inside ComfyUI: 

You can use the final product of this plug-in to re-generate the original image inside ComfyUI following this template:


<img width="1621" height="915" alt="ComfyBridge_ComfyUI_Example" src="https://github.com/user-attachments/assets/37186bbb-fa5e-4b82-b541-63f3f05be38b" />

In this template we use SAM 3 to create a mask of the targeted object, and flux-fill-dev to re-generate a specific part of the image using text and visual guidance. 

Enjoy!
