"""Windows DPI helpers — match screenshot pixels to physical screen coords."""

from __future__ import annotations

import ctypes


def set_dpi_aware() -> None:
    """Same approach as the reference script: raw resolution under 125%/150% scaling."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        return
    except Exception:
        pass
    try:
        DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
        ctypes.windll.user32.SetProcessDpiAwarenessContext(
            DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        )
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def get_dpi_for_window(hwnd: int) -> int:
    try:
        return int(ctypes.windll.user32.GetDpiForWindow(hwnd))
    except Exception:
        return 96
