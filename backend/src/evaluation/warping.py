"""
INVINCIBLES - Information-Preserving Warping (Spec Section 24)
=================================================================
Warps ORIGINAL (unmodified) source sensor data into the OHRC coordinate
frame. Continuous-valued sensors use bicubic interpolation; discrete /
derived terrain products (TMC-Azimuth, TMC-Slope) use nearest-neighbor so
no intermediate values are invented for what are semantically
categorical/derived quantities.
"""
from __future__ import annotations
import numpy as np
import cv2

DISCRETE_SENSORS = {"TMC-Azimuth", "TMC-Slope"}


def warp_original(sensor_key: str, original_img: np.ndarray, matrix, out_shape):
    """
    matrix: 2x3 affine (similarity/affine model) or 3x3 homography.
    Returns (warped_image, valid_mask uint8 0/255)
    """
    h, w = out_shape[:2]
    M = np.array(matrix, dtype=np.float64)

    interp = cv2.INTER_NEAREST if sensor_key in DISCRETE_SENSORS else cv2.INTER_CUBIC

    ones = np.ones(original_img.shape[:2], dtype=np.uint8) * 255

    if M.shape == (2, 3):
        warped = cv2.warpAffine(original_img, M, (w, h), flags=interp, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        mask = cv2.warpAffine(ones, M, (w, h), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    else:
        warped = cv2.warpPerspective(original_img, M, (w, h), flags=interp, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        mask = cv2.warpPerspective(ones, M, (w, h), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)

    return warped, mask


def checkerboard(ref_gray: np.ndarray, warped_gray: np.ndarray, tile: int = 32):
    """Section 26 - visual sanity-check checkerboard between OHRC and a
    registered source, built from the ACTUAL registered images."""
    h, w = ref_gray.shape[:2]
    warped_resized = cv2.resize(warped_gray, (w, h)) if warped_gray.shape[:2] != (h, w) else warped_gray
    board = np.zeros((h, w), dtype=np.uint8)
    for y in range(0, h, tile):
        for x in range(0, w, tile):
            take_ref = ((x // tile) + (y // tile)) % 2 == 0
            src = ref_gray if take_ref else warped_resized
            board[y:y + tile, x:x + tile] = src[y:y + tile, x:x + tile]
    return board
