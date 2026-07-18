"""Background detection / auto-click worker."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

import cv2
import numpy as np

from app import clicker
from app.blacklist import SkipBlacklist
from app.config import AppConfig
from app.detector import MatchResult, TemplateDetector
from app.reinforce import ReinforceStore
from app.window_capture import (
    ScreenCapturer,
    WindowInfo,
    capture_to_client_coords,
    find_game_window,
    refresh_window,
)


class WorkerState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_CONFIRM = "waiting_confirm"
    CLICKED_SKIP = "clicked_skip"
    CLICKED_CONFIRM = "clicked_confirm"
    AVOIDED = "avoided"
    ERROR = "error"


@dataclass
class WorkerStatus:
    state: WorkerState = WorkerState.IDLE
    message: str = "待命"
    last_score: float = 0.0
    last_button: str = ""
    last_lang: str = ""
    window_title: str = ""
    preview_bgr: Optional[np.ndarray] = None
    skip_count: int = 0
    confirm_count: int = 0
    avoid_count: int = 0
    blacklist_size: int = 0
    reinforce_size: int = 0
    reinforce_max: int = 50
    detect_fps: float = 0.0
    client_size: str = ""


StatusCallback = Callable[[WorkerStatus], None]


class AutoSkipWorker:
    def __init__(
        self,
        config: AppConfig,
        detector: TemplateDetector,
        on_status: Optional[StatusCallback] = None,
        blacklist: Optional[SkipBlacklist] = None,
        reinforce: Optional[ReinforceStore] = None,
    ) -> None:
        self.config = config
        self.detector = detector
        self.on_status = on_status
        self.blacklist = blacklist or SkipBlacklist()
        self.reinforce = reinforce or ReinforceStore()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.status = WorkerStatus(
            blacklist_size=self.blacklist.count(),
            reinforce_size=self.reinforce.count(),
            reinforce_max=getattr(config, "reinforce_max", 50),
        )
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        self.blacklist.load()
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._emit(WorkerState.IDLE, "已停止")

    def update_config(self, config: AppConfig) -> None:
        with self._lock:
            self.config = config

    def clear_blacklist(self) -> None:
        self.blacklist.clear()
        with self._lock:
            self.status.blacklist_size = 0
        self._emit(WorkerState.IDLE, "已清空誤判名單")

    def clear_reinforce(self) -> None:
        self.reinforce.clear()
        with self._lock:
            langs = list(self.config.enabled_langs)
            self.status.reinforce_size = 0
        self.detector.reload(langs)
        self._emit(WorkerState.IDLE, "已清空強化模板")

    def _emit(
        self,
        state: WorkerState,
        message: str,
        *,
        score: float = 0.0,
        button: str = "",
        lang: str = "",
        preview: Optional[np.ndarray] = None,
        window_title: str = "",
        client_size: str = "",
    ) -> None:
        # Only ship a NEW preview frame when provided — never re-copy old HD frames
        preview_out: Optional[np.ndarray] = None
        if preview is not None:
            preview_out = self._downscale_preview(preview)

        with self._lock:
            if preview_out is not None:
                self.status.preview_bgr = preview_out
            if window_title:
                self.status.window_title = window_title
            if client_size:
                self.status.client_size = client_size
            self.status.state = state
            self.status.message = message
            self.status.blacklist_size = self.blacklist.count()
            self.status.reinforce_size = self.reinforce.count()
            self.status.reinforce_max = int(
                getattr(self.config, "reinforce_max", 50)
            )
            if score:
                self.status.last_score = score
            if button:
                self.status.last_button = button
            if lang:
                self.status.last_lang = lang
            snap = WorkerStatus(
                state=self.status.state,
                message=self.status.message,
                last_score=self.status.last_score,
                last_button=self.status.last_button,
                last_lang=self.status.last_lang,
                window_title=self.status.window_title,
                preview_bgr=preview_out,
                skip_count=self.status.skip_count,
                confirm_count=self.status.confirm_count,
                avoid_count=self.status.avoid_count,
                blacklist_size=self.status.blacklist_size,
                reinforce_size=self.status.reinforce_size,
                reinforce_max=self.status.reinforce_max,
                detect_fps=self.status.detect_fps,
                client_size=self.status.client_size,
            )
        if self.on_status:
            self.on_status(snap)

    @staticmethod
    def _downscale_preview(frame_bgr: np.ndarray, max_w: int = 480) -> np.ndarray:
        """Shrink preview for UI — full 1600×900 copies were killing FPS."""
        h, w = frame_bgr.shape[:2]
        if w <= max_w:
            return frame_bgr
        scale = max_w / w
        nw, nh = max_w, max(1, int(h * scale))
        return cv2.resize(frame_bgr, (nw, nh), interpolation=cv2.INTER_AREA)

    @staticmethod
    def _prepare_frame(
        frame: np.ndarray, cfg: AppConfig
    ) -> tuple[np.ndarray, float, float]:
        h, w = frame.shape[:2]
        ew, eh = cfg.expected_width, cfg.expected_height
        if (
            not cfg.normalize_resolution
            or ew <= 0
            or eh <= 0
            or (w == ew and h == eh)
        ):
            return frame, 1.0, 1.0
        normalized = cv2.resize(frame, (ew, eh), interpolation=cv2.INTER_AREA)
        return normalized, w / ew, h / eh

    def _loop(self) -> None:
        self._emit(WorkerState.RUNNING, "偵測中…")
        window: Optional[WindowInfo] = None
        phase = "skip"  # skip | confirm
        confirm_deadline = 0.0
        focused_once = False
        pending_skip: Optional[MatchResult] = None
        pending_frame: Optional[np.ndarray] = None
        capturer = ScreenCapturer()
        capturer.open()
        last_preview_at = 0.0
        last_status_at = 0.0
        preview_interval = 0.04
        status_interval = 0.12
        window_check_at = 0.0
        fps_counter = 0
        fps_start = time.monotonic()

        try:
            self._run_loop(
                window,
                phase,
                confirm_deadline,
                focused_once,
                pending_skip,
                pending_frame,
                capturer,
                last_preview_at,
                last_status_at,
                preview_interval,
                status_interval,
                window_check_at,
                fps_counter,
                fps_start,
            )
        finally:
            capturer.close()

        self._emit(WorkerState.IDLE, "已停止")

    def _run_loop(
        self,
        window,
        phase,
        confirm_deadline,
        focused_once,
        pending_skip,
        pending_frame,
        capturer: ScreenCapturer,
        last_preview_at: float,
        last_status_at: float,
        preview_interval: float,
        status_interval: float,
        window_check_at: float,
        fps_counter: int,
        fps_start: float,
    ) -> None:
        while not self._stop.is_set():
            with self._lock:
                cfg = self.config

            now = time.monotonic()
            # FPS counter (same idea as the reference script)
            fps_counter += 1
            if now - fps_start >= 1.0:
                with self._lock:
                    self.status.detect_fps = float(fps_counter)
                fps_counter = 0
                fps_start = now
            if window is None or now - window_check_at >= 0.5:
                window = refresh_window(window) if window else None
                if window is None:
                    window = find_game_window(cfg.window_keywords)
                window_check_at = now
                if window is None:
                    self._emit(
                        WorkerState.ERROR,
                        "找不到遊戲視窗（請以視窗模式開啟）",
                    )
                    self._wait(0.5)
                    continue

            if not focused_once:
                ok = clicker.ensure_foreground(window.hwnd)
                focused_once = True
                self._emit(
                    WorkerState.RUNNING,
                    "已聚焦遊戲視窗" if ok else "嘗試聚焦遊戲視窗…",
                    window_title=window.title,
                    client_size=f"{window.width}×{window.height}",
                )
                self._wait(0.15)

            try:
                capture = capturer.capture(window)
            except Exception as exc:
                self._emit(WorkerState.ERROR, f"截圖失敗：{exc}")
                self._wait(0.3)
                continue

            frame = capture.frame
            size_label = f"{capture.width}×{capture.height}"
            match_frame, sx, sy = self._prepare_frame(frame, cfg)

            now = time.monotonic()
            grace = getattr(cfg, "confirm_grace", 3.0)
            if phase == "confirm" and now >= confirm_deadline + grace:
                if pending_skip is not None and pending_frame is not None:
                    if getattr(cfg, "blacklist_enabled", True):
                        self.blacklist.add_false_positive(
                            pending_frame, pending_skip
                        )
                        self._emit(
                            WorkerState.AVOIDED,
                            f"無確認彈窗，已記錄誤判（名單 {self.blacklist.count()}）",
                            preview=self.detector.annotate(
                                pending_frame, pending_skip
                            ),
                            window_title=window.title,
                            client_size=size_label,
                        )
                    else:
                        self._emit(
                            WorkerState.RUNNING,
                            "無確認彈窗（誤判名單已關閉）",
                            window_title=window.title,
                            client_size=size_label,
                        )
                pending_skip = None
                pending_frame = None
                phase = "skip"

            button = "confirm" if phase == "confirm" else "skip"
            match = self.detector.match(
                match_frame,
                button=button,
                threshold=cfg.threshold,
                scale_match=cfg.scale_match,
                require_confirm_text=getattr(
                    cfg, "confirm_require_text", True
                ),
            )

            if (
                button == "skip"
                and match.found
                and getattr(cfg, "blacklist_enabled", True)
            ):
                if self.blacklist.is_blocked(match_frame, match):
                    with self._lock:
                        self.status.avoid_count += 1
                    if now - last_preview_at >= preview_interval:
                        small = self._downscale_preview(match_frame, max_w=480)
                        sh, sw = small.shape[:2]
                        fh, fw = match_frame.shape[:2]
                        scaled_match = MatchResult(
                            found=True,
                            score=match.score,
                            x=int(match.x * sw / max(fw, 1)),
                            y=int(match.y * sh / max(fh, 1)),
                            w=max(1, int(match.w * sw / max(fw, 1))),
                            h=max(1, int(match.h * sh / max(fh, 1))),
                            lang=match.lang,
                            template_name=match.template_name,
                            button=match.button,
                        )
                        annotated = self.detector.annotate(
                            small, scaled_match, color=(80, 80, 200)
                        )
                        self._emit(
                            WorkerState.AVOIDED,
                            f"避開已知誤判 Skip（名單 {self.blacklist.count()}）",
                            score=match.score,
                            button="skip",
                            lang=match.lang,
                            preview=annotated,
                            window_title=window.title,
                            client_size=size_label,
                        )
                        last_preview_at = now
                    self._wait(cfg.scan_interval)
                    continue

            want_preview = (now - last_preview_at) >= preview_interval or match.found
            annotated = None
            if want_preview:
                # Annotate a downscaled copy so UI work stays cheap
                small = self._downscale_preview(match_frame, max_w=480)
                sh, sw = small.shape[:2]
                fh, fw = match_frame.shape[:2]
                sx_p = sw / max(fw, 1)
                sy_p = sh / max(fh, 1)
                if match.found:
                    scaled_match = MatchResult(
                        found=True,
                        score=match.score,
                        x=int(match.x * sx_p),
                        y=int(match.y * sy_p),
                        w=max(1, int(match.w * sx_p)),
                        h=max(1, int(match.h * sy_p)),
                        lang=match.lang,
                        template_name=match.template_name,
                        button=match.button,
                    )
                    annotated = self.detector.annotate(small, scaled_match)
                else:
                    annotated = small
                last_preview_at = now

            if match.found:
                if button == "skip":
                    delay = float(getattr(cfg, "skip_click_delay", 0.1))
                    if delay > 0:
                        self._wait(delay)
                        if self._stop.is_set():
                            return

                cap_x = match.center[0] * sx
                cap_y = match.center[1] * sy
                screen_x, screen_y = capture.to_screen(cap_x, cap_y)

                live = capturer.cached_info or window
                client_x, client_y = capture_to_client_coords(
                    cap_x,
                    cap_y,
                    capture.width,
                    capture.height,
                    live.width,
                    live.height,
                )
                try:
                    clicker.click_match(
                        hwnd=capture.hwnd,
                        screen_x=screen_x,
                        screen_y=screen_y,
                        client_x=client_x,
                        client_y=client_y,
                        method=getattr(cfg, "click_method", "cursor"),
                    )
                except Exception as exc:
                    self._emit(WorkerState.ERROR, f"點擊失敗：{exc}")
                    self._wait(cfg.scan_interval)
                    continue

                if button == "skip":
                    with self._lock:
                        self.status.skip_count += 1
                    pending_skip = match
                    pending_frame = match_frame.copy()
                    self._emit(
                        WorkerState.CLICKED_SKIP,
                        f"已點 Skip（{match.lang} · {match.score:.2f}）",
                        score=match.score,
                        button="skip",
                        lang=match.lang,
                        preview=annotated,
                        window_title=window.title,
                        client_size=size_label,
                    )
                    phase = "confirm"
                    confirm_deadline = time.monotonic() + cfg.confirm_wait
                    self._wait(cfg.confirm_wait)
                else:
                    with self._lock:
                        self.status.confirm_count += 1
                    reinforce_msg = ""
                    if (
                        getattr(cfg, "reinforce_enabled", True)
                        and pending_skip is not None
                        and pending_frame is not None
                    ):
                        saved, reinforce_msg = self.reinforce.try_record(
                            skip_frame=pending_frame,
                            skip_match=pending_skip,
                            confirm_frame=match_frame,
                            confirm_match=match,
                            max_templates=int(
                                getattr(cfg, "reinforce_max", 50)
                            ),
                        )
                        if saved:
                            self.detector.reload(cfg.enabled_langs)
                    pending_skip = None
                    pending_frame = None
                    status_text = (
                        f"已點確認（{match.lang} · {match.score:.2f}）"
                    )
                    if reinforce_msg:
                        status_text = f"{status_text} · {reinforce_msg}"
                    self._emit(
                        WorkerState.CLICKED_CONFIRM,
                        status_text,
                        score=match.score,
                        button="confirm",
                        lang=match.lang,
                        preview=annotated,
                        window_title=window.title,
                        client_size=size_label,
                    )
                    phase = "skip"
                    self._wait(0.1)
            else:
                # Idle detect: refresh preview often, text status less often
                if want_preview or (now - last_status_at) >= status_interval:
                    warn = ""
                    if (
                        window.width != cfg.expected_width
                        or window.height != cfg.expected_height
                    ):
                        warn = (
                            f" · 實際 {size_label} / 目標 "
                            f"{cfg.resolution_label()}"
                        )
                    msg = (
                        f"等待確認… {match.score:.2f} · {self.status.detect_fps:.0f} FPS{warn}"
                        if phase == "confirm"
                        else f"偵測中… {match.score:.2f} · {self.status.detect_fps:.0f} FPS{warn}"
                    )
                    state = (
                        WorkerState.WAITING_CONFIRM
                        if phase == "confirm"
                        else WorkerState.RUNNING
                    )
                    self._emit(
                        state,
                        msg,
                        score=match.score,
                        preview=annotated,
                        window_title=window.title,
                        client_size=size_label,
                    )
                    last_status_at = now
                self._wait(cfg.scan_interval)

    def _wait(self, seconds: float) -> None:
        # Fine-grained sleep so short scan intervals (high FPS) stay responsive
        end = time.monotonic() + max(0.0, seconds)
        while time.monotonic() < end:
            if self._stop.is_set():
                return
            remaining = end - time.monotonic()
            time.sleep(min(0.005, max(0.0, remaining)))
