"""
INVINCIBLES - Final Multi-Sensor Output (Spec Section 25)
============================================================
Individual sensor layers are preserved separately rather than collapsed
into a single blended grayscale image. Because the five sensors differ in
channel count/dtype, a single naive stack is not always safe; a
scientifically safe multi-layer NPZ archive is produced (each layer kept
at its own dtype/valid-mask) plus a human-viewable PNG stack for quick
inspection, together with a metadata JSON describing every layer.

Extended: composite false-color overlay and per-sensor comparison strips.
"""
from __future__ import annotations
import os
import json
import numpy as np
import cv2


def _norm_u8(img: np.ndarray) -> np.ndarray:
    """Normalize any array to uint8 [0,255]."""
    if img is None:
        return None
    arr = img.astype(np.float32)
    mn, mx = arr.min(), arr.max()
    if mx - mn < 1e-6:
        return np.zeros(img.shape[:2], dtype=np.uint8)
    return ((arr - mn) / (mx - mn) * 255).astype(np.uint8)


def _to_gray_u8(img: np.ndarray) -> np.ndarray:
    if img is None:
        return None
    if img.ndim == 3:
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        if img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            img = img[..., 0]
    return _norm_u8(img)


def generate_composite_overlay(run_dir: str, layers: dict) -> str | None:
    """
    Create a meaningful false-color RGB composite image from registered sensor layers.
    Channel assignment (SIH-grade scientific rationale):
      R = OHRC  (high-resolution optical reference — fine surface texture)
      G = IIRS  (infrared spectral brightness — material response variation)
      B = SAR   (radar backscatter — surface roughness, shadowed areas)
    If a sensor is missing, its channel is filled with the OHRC grey.
    Fallback channels:
      If IIRS absent: use TMC-Slope (terrain morphology proxy for G)
      If SAR absent: use TMC-Azimuth (illumination-direction proxy for B)

    The composite is saved as composite_registered.png in run_dir.
    Returns the saved path or None on failure.
    """
    try:
        # Extract and normalize each layer to uint8
        def _get(key):
            entry = layers.get(key)
            if entry is None:
                return None
            return _to_gray_u8(entry["image"])

        ohrc  = _get("OHRC")
        iirs  = _get("IIRS")
        sar   = _get("SAR")
        slope = _get("TMC-Slope")
        azim  = _get("TMC-Azimuth")

        if ohrc is None:
            return None  # Cannot produce composite without the reference

        h, w = ohrc.shape[:2]

        def _resize(img):
            if img is None:
                return None
            if img.shape[:2] != (h, w):
                return cv2.resize(img, (w, h), interpolation=cv2.INTER_LINEAR)
            return img

        iirs  = _resize(iirs)
        sar   = _resize(sar)
        slope = _resize(slope)
        azim  = _resize(azim)

        R = ohrc
        G = iirs  if iirs  is not None else (slope if slope is not None else ohrc)
        B = sar   if sar   is not None else (azim  if azim  is not None else ohrc)

        composite = cv2.merge([B, G, R])  # OpenCV is BGR

        # Burn a small legend strip at the bottom
        legend_h = 28
        legend = np.zeros((legend_h, w, 3), dtype=np.uint8)
        labels = [
            (f"R=OHRC (Optical Reference)", (0, 0, 220)),
            (f"G={'IIRS' if iirs is not None else 'TMC-Slope'} (IR/Terrain)", (0, 180, 0)),
            (f"B={'SAR' if sar is not None else 'TMC-Azimuth'} (Radar/Azim)", (200, 0, 0)),
        ]
        x_pos = 8
        font = cv2.FONT_HERSHEY_SIMPLEX
        for txt, color in labels:
            text_size = cv2.getTextSize(txt, font, 0.38, 1)[0]
            cv2.putText(legend, txt, (x_pos, 18), font, 0.38, color, 1, cv2.LINE_AA)
            x_pos += text_size[0] + 20
            if x_pos > w - 40:
                break

        composite_with_legend = np.vstack([composite, legend])
        out_path = os.path.join(run_dir, "composite_registered.png")
        cv2.imwrite(out_path, composite_with_legend)
        return out_path
    except Exception as e:
        print(f"[multiband] composite generation failed: {e}")
        return None


def generate_comparison_strip(
    run_dir: str,
    sensor_key: str,
    original_path: str,
    registered_image: np.ndarray,
    ohrc_image: np.ndarray,
) -> str | None:
    """
    Generate a side-by-side comparison strip:
      LEFT:  Original unregistered sensor image (raw input, as-is)
      MIDDLE: OHRC reference image
      RIGHT: Registered sensor image (warped to OHRC frame)

    All three are normalised to uint8, resized to the same height, and
    placed on a black canvas with white label overlays.
    Saved as comparison_{sensor_key}.png in run_dir.
    """
    try:
        orig_raw = cv2.imread(original_path, cv2.IMREAD_UNCHANGED)
        if orig_raw is None:
            return None

        orig_gray   = _norm_u8(_to_gray_u8(orig_raw))
        ohrc_gray   = _norm_u8(_to_gray_u8(ohrc_image))
        warped_gray = _norm_u8(_to_gray_u8(registered_image))

        # Target display height = 320 px; widths scaled proportionally
        TARGET_H = 320
        def _fit(img):
            h, w = img.shape[:2]
            scale = TARGET_H / h
            return cv2.resize(img, (max(1, int(w * scale)), TARGET_H), interpolation=cv2.INTER_LINEAR)

        orig_fit   = _fit(orig_gray)
        ohrc_fit   = _fit(ohrc_gray)
        warped_fit = _fit(warped_gray)

        # Convert to BGR for colored labels
        orig_bgr   = cv2.cvtColor(orig_fit,   cv2.COLOR_GRAY2BGR)
        ohrc_bgr   = cv2.cvtColor(ohrc_fit,   cv2.COLOR_GRAY2BGR)
        warped_bgr = cv2.cvtColor(warped_fit, cv2.COLOR_GRAY2BGR)

        # Label bar height
        LABEL_H = 30
        font = cv2.FONT_HERSHEY_SIMPLEX

        def _add_label(img, text, color=(255, 255, 255)):
            h, w = img.shape[:2]
            bar = np.zeros((LABEL_H, w, 3), dtype=np.uint8)
            (tw, th), _ = cv2.getTextSize(text, font, 0.48, 1)
            x = max(4, (w - tw) // 2)
            cv2.putText(bar, text, (x, 20), font, 0.48, color, 1, cv2.LINE_AA)
            return np.vstack([img, bar])

        orig_bgr   = _add_label(orig_bgr,   f"{sensor_key} (ORIGINAL INPUT)",   color=(100, 200, 255))
        ohrc_bgr   = _add_label(ohrc_bgr,   "OHRC (REFERENCE)",                  color=(180, 255, 180))
        warped_bgr = _add_label(warped_bgr, f"{sensor_key} (REGISTERED→OHRC)",  color=(255, 200, 80))

        # Add thin separator lines between panels
        SEP_W = 4
        sep = np.full((TARGET_H + LABEL_H, SEP_W, 3), 60, dtype=np.uint8)

        strip = np.hstack([orig_bgr, sep, ohrc_bgr, sep, warped_bgr])

        out_path = os.path.join(run_dir, f"comparison_{sensor_key}.png")
        cv2.imwrite(out_path, strip)
        return out_path
    except Exception as e:
        print(f"[multiband] comparison strip for {sensor_key} failed: {e}")
        return None


def save_multiband_output(run_dir: str, reference_key: str, layers: dict):
    """
    layers: { sensor_key: {"image": ndarray, "mask": ndarray, "role": str,
                            "interpolation": str} }
    Writes:
      - multiband.npz  (all layers, safe multi-dtype archive)
      - layer_<sensor>.png (viewable grayscale preview per layer)
      - layers_metadata.json
      - composite_registered.png (false-color RGB overlay)
      - comparison_<sensor>.png  (per-source-sensor before/after strip)
    """
    os.makedirs(run_dir, exist_ok=True)
    npz_payload = {}
    metadata = {"reference_sensor": reference_key, "layers": {}}

    for key, entry in layers.items():
        img = entry["image"]
        mask = entry["mask"]
        npz_payload[f"{key}_image"] = img
        npz_payload[f"{key}_mask"] = mask

        preview = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.shape[-1] == 3 else img[..., 0]
        preview_norm = cv2.normalize(preview.astype(np.float32), None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        cv2.imwrite(os.path.join(run_dir, f"layer_{key}.png"), preview_norm)

        valid_fraction = float(np.mean(mask > 0))
        metadata["layers"][key] = {
            "role": entry.get("role"),
            "interpolation": entry.get("interpolation"),
            "dtype": str(img.dtype),
            "shape": list(img.shape),
            "valid_pixel_fraction": valid_fraction,
        }

    np.savez_compressed(os.path.join(run_dir, "multiband.npz"), **npz_payload)
    with open(os.path.join(run_dir, "layers_metadata.json"), "w") as fh:
        json.dump(metadata, fh, indent=2)

    # Generate composite overlay
    composite_path = generate_composite_overlay(run_dir, layers)

    return {
        "npz_path": os.path.join(run_dir, "multiband.npz"),
        "metadata_path": os.path.join(run_dir, "layers_metadata.json"),
        "metadata": metadata,
        "composite_path": composite_path,
    }
