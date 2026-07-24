"""Sidecar mask helpers for OpenCV masked template matching.

Skip masks are a canonical |>| glyph drawn for the crop size — never derived
from scene pixels. Backgrounds change every shot; one brightness/threshold
heuristic cannot recover the glyph reliably.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np


def mask_path_for(template_path: Path) -> Path:
    """button.png → button_mask.png"""
    return template_path.with_name(f"{template_path.stem}_mask{template_path.suffix}")


def load_mask(template_path: Path, template_bgr: np.ndarray) -> Optional[np.ndarray]:
    """Load a sidecar mask if present and size-matched. Color, like the reference."""
    side = mask_path_for(template_path)
    if not side.exists():
        return None
    mask = cv2.imread(str(side), cv2.IMREAD_COLOR)
    if mask is None or mask.shape[:2] != template_bgr.shape[:2]:
        return None
    return mask


def scale_mask(mask: np.ndarray, width: int, height: int) -> np.ndarray:
    if mask.shape[1] == width and mask.shape[0] == height:
        return mask
    return cv2.resize(mask, (width, height), interpolation=cv2.INTER_NEAREST)


def refine_skip_mask(
    template_feature: np.ndarray,
    glyph_mask: np.ndarray,
) -> np.ndarray:
    """Limit a broad glyph mask to the template's visible anti-aliased strokes."""
    strokes = (template_feature >= 12).astype(np.uint8) * 255
    strokes = cv2.dilate(strokes, np.ones((2, 2), dtype=np.uint8), iterations=1)
    strokes = cv2.bitwise_and(strokes, glyph_mask)
    minimum_pixels = max(8, int(np.count_nonzero(glyph_mask) * 0.05))
    if np.count_nonzero(strokes) < minimum_pixels:
        return glyph_mask
    return strokes


def draw_canonical_skip_glyph(
    height: int,
    width: int,
    *,
    margin: float = 0.18,
) -> np.ndarray:
    """Draw a clean |>| (triangle + bar) binary mask, independent of any scene."""
    mask = np.zeros((height, width), dtype=np.uint8)
    if height < 8 or width < 8:
        return mask

    pad_x = max(1, int(round(width * margin)))
    pad_y = max(1, int(round(height * margin)))
    x0, y0 = pad_x, pad_y
    x1, y1 = width - pad_x, height - pad_y
    gw = max(4, x1 - x0)
    gh = max(4, y1 - y0)

    # Layout: [ triangle ~62% ][ gap ][ bar ~12% ]
    tri_w = max(3, int(round(gw * 0.62)))
    bar_w = max(2, int(round(gw * 0.12)))
    gap = max(1, int(round(gw * 0.08)))
    if x0 + tri_w + gap + bar_w > x1:
        bar_w = max(2, x1 - (x0 + tri_w + gap))
        if bar_w < 2:
            tri_w = max(3, gw - gap - 2)
            bar_w = 2

    tri = np.array(
        [
            [x0, y0],
            [x0, y1 - 1],
            [x0 + tri_w, (y0 + y1) // 2],
        ],
        dtype=np.int32,
    )
    cv2.fillConvexPoly(mask, tri, 255)

    bx0 = x0 + tri_w + gap
    bx1 = min(x1, bx0 + bar_w)
    cv2.rectangle(mask, (bx0, y0), (bx1 - 1, y1 - 1), 255, thickness=-1)
    return mask


def make_sidecar_mask(template_bgr: np.ndarray) -> np.ndarray:
    """Build a Skip sidecar mask: always the canonical |>| for this crop size.

    Scene-derived masks are intentionally not used — changing BG makes any
    single brightness/edge rule fail on the next shot. Crop tightly around
    the Skip icon so the canonical glyph aligns with the real button.
    """
    h, w = template_bgr.shape[:2]
    glyph = draw_canonical_skip_glyph(h, w)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    glyph = cv2.dilate(glyph, k, iterations=1)
    return cv2.cvtColor(glyph, cv2.COLOR_GRAY2BGR)


def skip_feature_map(gray: np.ndarray) -> np.ndarray:
    """BG-robust feature for Skip matching: local bright strokes (tophat ∪ local)."""
    blur = cv2.GaussianBlur(gray, (7, 7), 0)
    local = np.clip(gray.astype(np.int16) - blur.astype(np.int16), 0, 255).astype(
        np.uint8
    )
    h, w = gray.shape[:2]
    ksize = max(5, (min(h, w) // 4) | 1)
    tophat = cv2.morphologyEx(
        gray,
        cv2.MORPH_TOPHAT,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksize, ksize)),
    )
    return cv2.addWeighted(tophat, 0.65, local, 0.35, 0)


def count_exploration_hud_icons(frame_bgr: np.ndarray) -> int:
    """Count large near-square icons in the top-right overworld menu row.

    Exploration HUD has many circular/square menu buttons. Dialogue Skip bar
    has only ~3 small glyphs — this count stays low. Used to veto false Skip.
    """
    fh, fw = frame_bgr.shape[:2]
    tr = frame_bgr[8 : max(9, int(fh * 0.12)), int(fw * 0.68) : fw]
    if tr.size == 0:
        return 0
    gray = cv2.cvtColor(tr, cv2.COLOR_BGR2GRAY)
    bright = (gray >= 150).astype(np.uint8) * 255
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    bright = cv2.morphologyEx(bright, cv2.MORPH_OPEN, k, iterations=1)
    n, _labels, stats, _ = cv2.connectedComponentsWithStats(bright, 8)
    icons = 0
    for i in range(1, n):
        _x, _y, w, h, area = stats[i]
        if area < 180 or area > 3500:
            continue
        if w < 14 or h < 14 or w > 75 or h > 75:
            continue
        aspect = max(w, h) / max(1, min(w, h))
        if aspect > 2.0:
            continue
        icons += 1
    return icons


def is_exploration_hud(frame_bgr: np.ndarray, min_icons: int = 5) -> bool:
    """True when the overworld top-right icon row is visible (no Skip)."""
    return count_exploration_hud_icons(frame_bgr) >= min_icons
