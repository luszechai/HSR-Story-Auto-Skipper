"""Mouse click helpers via pydirectinput (screen absolute coordinates)."""

from __future__ import annotations

import time
from typing import Optional, Tuple

import pydirectinput

try:
    import win32api
    import win32con
    import win32gui
    import win32process
except ImportError:  # pragma: no cover
    win32api = None  # type: ignore
    win32con = None  # type: ignore
    win32gui = None  # type: ignore
    win32process = None  # type: ignore

pydirectinput.PAUSE = 0.05
pydirectinput.FAILSAFE = True


def short_pause(seconds: float) -> None:
    time.sleep(max(0.0, seconds))


def click_at_screen(
    screen_x: int,
    screen_y: int,
    *,
    target_hwnd: Optional[int] = None,
    client_position: Optional[Tuple[int, int]] = None,
) -> None:
    """Move and click, cancelling if the target loses focus."""
    x, y = int(screen_x), int(screen_y)
    pydirectinput.moveTo(x, y)
    short_pause(0.1)
    if target_hwnd is not None:
        if not is_foreground(target_hwnd):
            raise RuntimeError("target window lost focus before click")
        if client_position is not None:
            if win32gui is None or not win32gui.IsWindow(target_hwnd):
                raise RuntimeError("target window is unavailable before click")
            x, y = win32gui.ClientToScreen(
                target_hwnd,
                (int(client_position[0]), int(client_position[1])),
            )
            pydirectinput.moveTo(int(x), int(y))
            if not is_foreground(target_hwnd):
                raise RuntimeError("target window lost focus before click")
    pydirectinput.click()


def click_match(
    *,
    hwnd: int,
    screen_x: int,
    screen_y: int,
    client_x: int = 0,
    client_y: int = 0,
    method: str = "cursor",
) -> None:
    """Click the current client position only while its window is focused."""
    click_at_screen(
        screen_x,
        screen_y,
        target_hwnd=hwnd,
        client_position=(client_x, client_y),
    )


def click_client(
    hwnd: int,
    client_x: int,
    client_y: int,
    *,
    method: str = "cursor",
) -> None:
    if not hwnd or win32gui is None:
        raise RuntimeError("win32gui unavailable")
    sx, sy = win32gui.ClientToScreen(hwnd, (int(client_x), int(client_y)))
    click_at_screen(sx, sy)


def click_screen(x: int, y: int, clicks: int = 1) -> None:
    for _ in range(max(1, clicks)):
        click_at_screen(x, y)


def click_relative(
    origin: Tuple[int, int],
    rel_x: int,
    rel_y: int,
) -> None:
    sx, sy = origin
    click_at_screen(sx + rel_x, sy + rel_y)


def move_to(x: int, y: int) -> None:
    pydirectinput.moveTo(int(x), int(y))


def is_foreground(hwnd: Optional[int]) -> bool:
    """True when *hwnd* (or one of its child windows) is the foreground window."""
    if not hwnd or win32gui is None:
        return False
    try:
        if not win32gui.IsWindow(hwnd):
            return False
        fg = win32gui.GetForegroundWindow()
        if not fg:
            return False
        if fg == hwnd:
            return True
        # Some clients focus a child HWND; treat the game root as focused.
        try:
            root = win32gui.GetAncestor(fg, 2)  # GA_ROOT
            if root == hwnd:
                return True
        except Exception:
            pass
        return False
    except Exception:
        return False


def ensure_foreground(hwnd: Optional[int]) -> bool:
    if not hwnd or win32gui is None or win32con is None:
        return False
    try:
        if not win32gui.IsWindow(hwnd):
            return False
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

        fg = win32gui.GetForegroundWindow()
        if fg == hwnd:
            win32gui.BringWindowToTop(hwnd)
            return True

        current_tid = win32api.GetCurrentThreadId()
        fg_tid, _ = win32process.GetWindowThreadProcessId(fg) if fg else (0, 0)
        target_tid, _ = win32process.GetWindowThreadProcessId(hwnd)

        attached_fg = False
        attached_target = False
        try:
            if fg and fg_tid and fg_tid != current_tid:
                attached_fg = bool(
                    win32process.AttachThreadInput(current_tid, fg_tid, True)
                )
            if target_tid and target_tid != current_tid:
                attached_target = bool(
                    win32process.AttachThreadInput(current_tid, target_tid, True)
                )
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
            try:
                win32gui.SetActiveWindow(hwnd)
            except Exception:
                pass
        finally:
            if attached_target:
                win32process.AttachThreadInput(current_tid, target_tid, False)
            if attached_fg:
                win32process.AttachThreadInput(current_tid, fg_tid, False)

        short_pause(0.15)
        return win32gui.GetForegroundWindow() == hwnd
    except Exception:
        try:
            win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception:
            return False
