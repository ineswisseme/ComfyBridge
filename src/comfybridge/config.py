import os
import json
from pathlib import Path

DEFAULT_CONFIG = {
    "maya_host": "127.0.0.1",
    "maya_port": 7001,
}

CONFIG_PATH = os.path.expanduser("~/.comfybridge/config.json")

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return DEFAULT_CONFIG

    try:
        with open(CONFIG_PATH, "r") as f:
            user_cfg = json.load(f)
        return {**DEFAULT_CONFIG, **user_cfg}
    except Exception:
        return DEFAULT_CONFIG




def get_project_root() -> Path:
    env_root = os.environ.get("COMFYBRIDGE_ROOT")
    if env_root and Path(env_root).is_dir():
        return Path(env_root).resolve()

    cfg = load_config()
    cfg_root = cfg.get("tool_root")
    if cfg_root and Path(cfg_root).is_dir():
        return Path(cfg_root).resolve()

  
    return Path(__file__).resolve().parents[2] 

PROJECT_ROOT = get_project_root()
PACKAGE_ROOT = Path(__file__).resolve().parent  # .../src/comfybridge

OUTPUT_DIR  = str(PROJECT_ROOT / "output")
MODELS_DIR  = str(PACKAGE_ROOT / "models")
BAKE_DIR    = str(Path(OUTPUT_DIR) / "bake")
FRAMES_DIR  = str(Path(OUTPUT_DIR) / "frames")

TRIPOSR_DIR = str(Path(MODELS_DIR) / "TripoSR")
TRIPOSR_RUN = str(Path(TRIPOSR_DIR) / "run.py")
