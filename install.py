"""
ComfyBridge installer. Creates a venv for dependencies plus torch CPU no GPU.



"""

from __future__ import annotations
import subprocess
import shutil
import sys
from pathlib import Path
import venv
import argparse


def run(cmd):
    print("\n[ComfyBridge][installer] >", " ".join(cmd))
    subprocess.check_call(cmd)


def main():
    root = Path(__file__).resolve().parent
    venv_dir = root / "_venv"
    req_file = root / "requirements.txt"

    if not req_file.exists():
        print("[ComfyBridge][installer] ERROR: requirements.txt not found.")
        return 1

    if venv_dir.exists():
        print("[ComfyBridge][installer] Existing venv found.")
    else:
        print(f"[ComfyBridge][installer] Creating venv at {venv_dir}")
        venv.EnvBuilder(with_pip=True).create(venv_dir)

    py = venv_dir / "Scripts" / "python.exe"
    pyw = venv_dir / "Scripts" / "pythonw.exe"

    if not py.exists():
        print("[ComfyBridge][installer] ERROR: python.exe not found in venv.")
        return 2

    # Install packages
    run([str(py), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
    
    parser= argparse.ArgumentParser(description="ComfyBridge Installer")
    parser.add_argument("--cpu", action="store_true", help="Install CPU-only torch/torchvision")
    args = parser.parse_args()

   
    if args.cpu:
        # CPU wheels from PyPI
        run([str(py), "-m", "pip", "install", "torch==2.2.0", "torchvision==0.17.0"])
    else:
    # CUDA 11.8 wheels from PyTorch index
        run([str(py), "-m", "pip", "install", "--index-url", "https://download.pytorch.org/whl/cu118", "torch==2.2.0", "torchvision==0.17.0"])


   
    run([str(py), "-m", "pip", "install", "-r", str(req_file)])

    
    run([
        str(py),
        "-c",
        "import numpy, cv2, rembg, torch, PIL; print('ComfyBridge install OK')"
    ])
    
    run([str(py), "-m", "pip", "install", "-e", str(root)])


    print("\n[ComfyBridge][installer] Installation complete.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())