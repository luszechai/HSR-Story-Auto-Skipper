"""Locate the game window and capture its client area."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Tuple

import mss
import numpy as np
import cv2

try:
    import win32gui
except ImportError:  # pragma: no cover
    win32gui = None  # type: ignore


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    left: int
    top: int
    width: int
    height: int

    @property
    def bbox(self) -> dict:
        return {
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class CaptureResult:
    """Screenshot tied to the exact screen origin used for the grab."""

    frame: np.ndarray  # BGR
    origin_x: int
    origin_y: int
    hwnd: int

    @property
    def width(self) -> int:
        return int(self.frame.shape[1])

    @property
    def height(self) -> int:
        return int(self.frame.shape[0])

    def to_screen(self, capture_x: float, capture_y: float) -> Tuple[int, int]:
        """Capture-relative pixel → absolute screen pixel (pydirectinput coords)."""
        return (
            int(round(self.origin_x + capture_x)),
            int(round(self.origin_y + capture_y)),
        )


class ScreenCapturer:
    """Reusable mss handle — creating mss every frame is a major FPS killer."""

    def __init__(self) -> None:
        self._sct: Optional[Any] = None
        self._cached: Optional[WindowInfo] = None
        self._cache_mono: float = 0.0
        self._cache_ttl: float = 0.25  # refresh window rect at most 4×/s

    @property
    def cached_info(self) -> Optional[WindowInfo]:
        return self._cached

    def open(self) -> None:
        if self._sct is None:
            self._sct = mss.mss()

    def close(self) -> None:
        if self._sct is not None:
            try:
                self._sct.close()
            except Exception:
                pass
            self._sct = None

    def __enter__(self) -> "ScreenCapturer":
        self.open()
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def capture(self, info: WindowInfo, *, force_refresh: bool = False) -> CaptureResult:
        self.open()
        assert self._sct is not None

        now = time.monotonic()
        if (
            force_refresh
            or self._cached is None
            or self._cached.hwnd != info.hwnd
            or now - self._cache_mono >= self._cache_ttl
        ):
            fresh = _client_info(info.hwnd, info.title) or info
            self._cached = fresh
            self._cache_mono = now
        else:
            fresh = self._cached

        bbox = fresh.bbox
        # Same pattern as the reference script: persistent sct.grab + BGRA→BGR
        shot = self._sct.grab(bbox)
        screen_np = np.array(shot)
        frame = cv2.cvtColor(screen_np, cv2.COLOR_BGRA2BGR)
        return CaptureResult(
            frame=frame,
            origin_x=int(bbox["left"]),
            origin_y=int(bbox["top"]),
            hwnd=fresh.hwnd,
        )


def capture_client(info: WindowInfo) -> CaptureResult:
    """One-shot capture (dialogs). Prefer ScreenCapturer in the hot loop."""
    with ScreenCapturer() as cap:
        return cap.capture(info, force_refresh=True)


def _enum_windows() -> list[Tuple[int, str]]:
    if win32gui is None:
        raise RuntimeError("pywin32 is required on Windows")

    results: list[Tuple[int, str]] = []

    def callback(hwnd: int, _: object) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if title:
            results.append((hwnd, title))
        return True

    win32gui.EnumWindows(callback, None)
    return results


def find_game_window(keywords: Iterable[str]) -> Optional[WindowInfo]:
    keys = list(keywords)
    for hwnd, title in _enum_windows():
        title_l = title.lower()
        for k in keys:
            if k in title or k.lower() in title_l:
                info = _client_info(hwnd, title)
                if info is not None:
                    return info
    return None


def _client_info(hwnd: int, title: str) -> Optional[WindowInfo]:
    if win32gui is None:
        return None
    if win32gui.IsIconic(hwnd):
        return None

    try:
        _l, _t, right, bottom = win32gui.GetClientRect(hwnd)
        width = right - _l
        height = bottom - _t
        if width <= 0 or height <= 0:
            return None
        screen_left, screen_top = win32gui.ClientToScreen(hwnd, (0, 0))
    except Exception:
        return None

    return WindowInfo(
        hwnd=hwnd,
        title=title,
        left=screen_left,
        top=screen_top,
        width=width,
        height=height,
    )


def refresh_window(info: WindowInfo) -> Optional[WindowInfo]:
    if win32gui is None or not win32gui.IsWindow(info.hwnd):
        return None
    title = win32gui.GetWindowText(info.hwnd)
    return _client_info(info.hwnd, title or info.title)


def capture_to_client_coords(
    capture_x: float,
    capture_y: float,
    capture_w: int,
    capture_h: int,
    client_w: int,
    client_h: int,
) -> Tuple[int, int]:
    if capture_w <= 0 or capture_h <= 0:
        return int(capture_x), int(capture_y)
    cx = capture_x * client_w / capture_w
    cy = capture_y * client_h / capture_h
    return int(round(cx)), int(round(cy))


def client_to_screen(info: WindowInfo, x: int, y: int) -> Tuple[int, int]:
    if win32gui is not None:
        try:
            return win32gui.ClientToScreen(info.hwnd, (int(x), int(y)))
        except Exception:
            pass
    return info.left + int(x), info.top + int(y)
