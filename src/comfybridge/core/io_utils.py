"""
io_utils.py
Core utilities for image conversion, mask operations,
filesystem handling, and lightweight logging.

"""

import os
import time
import numpy as np
from typing import Tuple, Optional
from rembg import remove
import cv2
import io
from PIL import Image
from PySide6.QtGui import QImage



# Logging:


def log(msg: str):
    """Simple unified logger for ComfyMayaBridge."""
    print(f"[ComfyMayaBridge] {msg}")



class Timer: # for TripoSR timing.
    """with Timer('name'): ..."""
    def __init__(self, name="Timer"):
        self.name = name
        self.t0 = None

    def __enter__(self):
        self.t0 = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        dt = (time.time() - self.t0) * 1000
        log(f"{self.name}: {dt:.2f} ms")



# QImage to Numpy conversion:


def qimage_to_numpy(qimg: QImage) -> np.ndarray:
    """
    Convert QImage to a uint8 numpy array (H,W,4).
    Always returns RGBA.
    """
    qimg = qimg.convertToFormat(QImage.Format_RGBA8888)
    width = qimg.width()
    height = qimg.height()

   
    data = qimg.bits().tobytes()
    arr = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 4))
    return arr


def numpy_to_qimage(arr: np.ndarray) -> QImage:
    """
    Convert numpy array (H,W,3) or (H,W,4) into QImage.
    Ensures RGBA8888 format.
    """

    if arr.dtype != np.uint8:
        arr = arr.astype(np.uint8)

    h, w = arr.shape[:2]

    # Add alpha if necessary
    if arr.shape[2] == 3:
        alpha = np.full((h, w, 1), 255, dtype=np.uint8)
        arr = np.concatenate([arr, alpha], axis=2)

    qimg = QImage(arr.data, w, h, w * 4, QImage.Format_RGBA8888)
    return qimg.copy()


def clamp_highlights_soft(rgb, threshold=220):
    """
    Smoothly compress highlights above a given threshold.
    rgb: uint8 HxWx3 array in RGB order.
    Returns: uint8 array of same shape.
    """
    rgb = rgb.astype(np.float32)

    # mask of pixels above threshold
    mask = rgb > threshold
    if not np.any(mask):
        return rgb.astype(np.uint8)

    # range above threshold
    high = rgb[mask]

    # soft curve compression
    span = 255 - threshold
    normalized = (high - threshold) / span  # 0..1
    compressed = threshold + span * np.sqrt(normalized)

    rgb[mask] = compressed
    return rgb.astype(np.uint8)


def generate_multiview_images(input_path: str, output_dir: str) -> list:
    """
    Generates multi-view augmented images for TripoSR inference.
    Returns a list of file paths to the augmented images.

    Views:
      - original
      - horizontal flip
      - slightly darkened (reduces highlight dominance)
    """

    img = cv2.imread(input_path, cv2.IMREAD_UNCHANGED)  # keep BGRA
    if img is None:
        raise RuntimeError(f"Failed to load image for multiview: {input_path}")

    views = []

    path_original = input_path
    views.append(path_original)

    flipped = cv2.flip(img, 1)
    path_flip = os.path.join(output_dir, "view_flip.png")
    cv2.imwrite(path_flip, flipped)
    views.append(path_flip)


   
    dark = img.copy().astype(np.float32)
    dark[..., :3] *= 0.88  # reduce specular brightness
    dark = np.clip(dark, 0, 255).astype(np.uint8)

    path_dark = os.path.join(output_dir, "view_dark.png")
    cv2.imwrite(path_dark, dark)
    views.append(path_dark)

    return views


# Rembg:

def export_object_with_rembg(full_image_np, rough_mask_np, output_path,
                             padding_ratio=0.15, min_border_px=4):
    """
    1) Crop using the provided mask.
    2) Run rembg on that crop (same as original, color-safe).
    3) Use alpha channel from rembg output to:
       - find a tight bounding box,
       - center the object in a square BGRA canvas with padding.
    """

    
    ys, xs = np.where(rough_mask_np > 0)
    if len(xs) == 0 or len(ys) == 0:
        raise RuntimeError("Mask is empty — no object detected.")

    x_min, x_max = xs.min(), xs.max()
    y_min, y_max = ys.min(), ys.max()

   
    roi = full_image_np[y_min:y_max + 1, x_min:x_max + 1]
    
        
    
    roi = clamp_highlights_soft(roi, threshold=150) # clamping the highlights to avoid geo issues

    
    ok, encoded = cv2.imencode(".png", cv2.cvtColor(roi, cv2.COLOR_RGB2BGR))
    if not ok:
        raise RuntimeError("Failed to encode ROI before rembg.")

    result_bytes = remove(encoded.tobytes())

    arr = np.frombuffer(result_bytes, np.uint8)
    out_bgra = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)

    if out_bgra is None:
        raise RuntimeError("Failed to decode rembg output.")

    if out_bgra.shape[2] != 4:
        
        h_r, w_r = out_bgra.shape[:2]
        alpha = np.full((h_r, w_r, 1), 255, dtype=np.uint8)
        out_bgra = np.concatenate([out_bgra, alpha], axis=2)

    h, w = out_bgra.shape[:2]  
    alpha = out_bgra[..., 3]
    mask_fg = alpha > 10

    ys_fg, xs_fg = np.where(mask_fg)
    if len(xs_fg) == 0 or len(ys_fg) == 0:
        
        bbox_x_min, bbox_x_max = 0, w - 1
        bbox_y_min, bbox_y_max = 0, h - 1
    else:
        bbox_x_min, bbox_x_max = xs_fg.min(), xs_fg.max()
        bbox_y_min, bbox_y_max = ys_fg.min(), ys_fg.max()

    expand_y = max(int((bbox_y_max - bbox_y_min + 1) * 0.02), 1)
    expand_x = max(int((bbox_x_max - bbox_x_min + 1) * 0.02), 1)
    bbox_y_min = max(0, bbox_y_min - expand_y)
    bbox_y_max = min(h - 1, bbox_y_max + expand_y)
    bbox_x_min = max(0, bbox_x_min - expand_x)
    bbox_x_max = min(w - 1, bbox_x_max + expand_x)

    crop_bgra = out_bgra[bbox_y_min:bbox_y_max + 1, bbox_x_min:bbox_x_max + 1]
    ch, cw = crop_bgra.shape[:2]
    base_size = max(ch, cw)
    extra_pad = int(base_size * padding_ratio)
    canvas_size = base_size + 2 * max(extra_pad, min_border_px)
    canvas = np.zeros((canvas_size, canvas_size, 4), dtype=np.uint8)

    y_off = (canvas_size - ch) // 2
    x_off = (canvas_size - cw) // 2

    canvas[y_off:y_off + ch, x_off:x_off + cw] = crop_bgra
    cv2.imwrite(output_path, canvas)

    return output_path



# Mask: 

def mask_bounding_box(mask: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Return bounding box of mask (x_min, x_max, y_min, y_max).
    Returns None if mask is empty.
    """
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return None
    return xs.min(), xs.max(), ys.min(), ys.max()


def crop_by_mask(image: np.ndarray, mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Crops both image and mask to the mask bounding box.
    Returns, (cropped_image, cropped_mask).
    """

    bbox = mask_bounding_box(mask)
    if bbox is None:
        raise RuntimeError("Cannot crop: mask is empty")

    x_min, x_max, y_min, y_max = bbox

    crop_img = image[y_min:y_max+1, x_min:x_max+1]
    crop_mask = mask[y_min:y_max+1, x_min:x_max+1]

    return crop_img, crop_mask


def mask_to_rgba(mask: np.ndarray, color=(0, 180, 255), alpha=120) -> np.ndarray:
    """
    Convert mask (H,W,1 or H,W) to RGBA heatmap for overlay.
    """
    h, w = mask.shape[:2]
    rgba = np.zeros((h, w, 4), dtype=np.uint8)

    rgba[..., 0] = color[0]
    rgba[..., 1] = color[1]
    rgba[..., 2] = color[2]
    rgba[..., 3] = (mask > 0).astype(np.uint8) * alpha

    return rgba


def feather_mask(mask: np.ndarray, radius: int) -> np.ndarray:
    """
    Apply Gaussian blur to soften mask edges.
    """
    radius = max(1, int(radius))
    blurred = cv2.GaussianBlur(mask, (radius | 1, radius | 1), 0)
    _, binary = cv2.threshold(blurred, 10, 255, cv2.THRESH_BINARY)
    return binary

# Image saving:

def ensure_dir(path: str):
    """Create folder if it does not exist."""
    os.makedirs(path, exist_ok=True)


def safe_path(base: str, suffix: str) -> str:
    """
    Returns `<base>_<suffix>` with extension preserved.
    Example:
        safe_path("C:/img/object.png", "mask")
        -> C:/img/object_mask.png
    """
    root, ext = os.path.splitext(base)
    return f"{root}_{suffix}{ext}"



def save_png_rgba(path: str, rgba: np.ndarray):
    """
    Save an RGBA numpy array to disk.
    """
    if rgba.shape[2] != 4:
        raise ValueError("RGBA array must have 4 channels")
    cv2.imwrite(path, cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA))
    return path
