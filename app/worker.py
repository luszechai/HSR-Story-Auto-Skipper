"""Background detection / auto-click worker."""

from __future__ import annotations

import copy
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Deque, Dict, Optional

import cv2
import numpy as np

from app import clicker
from app.config import AppConfig
from app.detector import MatchResult, TemplateDetector
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
    ERROR = "error"


@dataclass
class WorkerStatus:
    state: WorkerState = WorkerState.IDLE
    message_key: str = "status.idle"
    message_kwargs: Dict[str, Any] = field(default_factory=dict)
    last_score: float = 0.0
    last_button: str = ""
    last_lang: str = ""
    window_title: str = ""
    preview_bgr: Optional[np.ndarray] = None
    skip_count: int = 0
    confirm_count: int = 0
    detect_fps: float = 0.0
    client_size: str = ""


StatusCallback = Callable[[WorkerStatus], None]


class MatchConsensus:
    """Require spatially stable detections within a rolling frame window."""

    def __init__(self) -> None:
        self._samples: Deque[Optional[MatchResult]] = deque()
        self._window = 0

    def observe(
        self,
        match: MatchResult,
        *,
        required: int,
        window: int,
    ) -> tuple[bool, int]:
        window = max(1, int(window))
        required = min(window, max(1, int(required)))
        if window != self._window:
            self._samples = deque(self._samples, maxlen=window)
            self._window = window
        self._samples.append(match if match.found else None)

        positives = [sample for sample in self._samples if sample is not None]
        if not positives:
            return False, 0
        latest = positives[-1]
        tolerance = max(4.0, max(latest.w, latest.h) * 0.4)
        lx, ly = latest.center
        stable = [
            sample
            for sample in positives
            if abs(sample.center[0] - lx) <= tolerance
            and abs(sample.center[1] - ly) <= tolerance
        ]
        count = len(stable)
        if count >= required:
            self.reset()
            return True, count
        return False, count

    def reset(self) -> None:
        self._samples.clear()


class PostClickVerifier:
    """Track whether Skip remains absent for consecutive frames."""

    def __init__(self) -> None:
        self._missing_frames = 0
        self.disappeared = False

    def observe(self, *, skip_found: bool, required_misses: int) -> bool:
        if skip_found:
            self.reset()
            return False
        self._missing_frames += 1
        if self._missing_frames >= max(1, int(required_misses)):
            self.disappeared = True
        return self.disappeared

    def reset(self) -> None:
        self._missing_frames = 0
        self.disappeared = False


class ConfirmClickTracker:
    """Verify Confirm disappears and bound repeated click attempts."""

    def __init__(self) -> None:
        self.attempts = 0
        self._missing_frames = 0
        self.retry_at = 0.0

    @property
    def awaiting_dismissal(self) -> bool:
        return self.attempts > 0

    def record_click(self, *, now: float, retry_delay: float) -> None:
        self.attempts += 1
        self._missing_frames = 0
        self.retry_at = now + max(0.0, retry_delay)

    def observe(
        self,
        *,
        confirm_found: bool,
        required_misses: int,
    ) -> bool:
        if not self.awaiting_dismissal:
            return False
        if confirm_found:
            self._missing_frames = 0
            return False
        self._missing_frames += 1
        return self._missing_frames >= max(1, int(required_misses))

    def can_click(self, *, now: float, max_attempts: int) -> bool:
        return (
            self.attempts < max(1, int(max_attempts))
            and now >= self.retry_at
        )

    def exhausted(self, *, now: float, max_attempts: int) -> bool:
        return (
            self.attempts >= max(1, int(max_attempts))
            and now >= self.retry_at
        )

    def reset(self) -> None:
        self.attempts = 0
        self._missing_frames = 0
        self.retry_at = 0.0


class AutoSkipWorker:
    def __init__(
        self,
        config: AppConfig,
        detector: TemplateDetector,
        on_status: Optional[StatusCallback] = None,
    ) -> None:
        self.config = copy.deepcopy(config)
        self.detector = detector
        self.on_status = on_status
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.status = WorkerStatus()
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._emit(WorkerState.IDLE, "worker.stopped")

    def update_config(self, config: AppConfig) -> None:
        with self._lock:
            self.config = copy.deepcopy(config)

    def _emit(
        self,
        state: WorkerState,
        message_key: str,
        *,
        msg_kwargs: Optional[Dict[str, Any]] = None,
        score: Optional[float] = None,
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
        kwargs = dict(msg_kwargs or {})

        with self._lock:
            if preview_out is not None:
                self.status.preview_bgr = preview_out
            if window_title:
                self.status.window_title = window_title
            if client_size:
                self.status.client_size = client_size
            self.status.state = state
            self.status.message_key = message_key
            self.status.message_kwargs = kwargs
            if score is not None:
                self.status.last_score = score
            if button:
                self.status.last_button = button
            if lang:
                self.status.last_lang = lang
            snap = WorkerStatus(
                state=self.status.state,
                message_key=self.status.message_key,
                message_kwargs=dict(self.status.message_kwargs),
                last_score=self.status.last_score,
                last_button=self.status.last_button,
                last_lang=self.status.last_lang,
                window_title=self.status.window_title,
                preview_bgr=preview_out,
                skip_count=self.status.skip_count,
                confirm_count=self.status.confirm_count,
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

    def _detect_match(
        self,
        frame: np.ndarray,
        cfg: AppConfig,
        button: str,
    ) -> MatchResult:
        if button == "skip" and getattr(cfg, "skip_fixed", True):
            return self.detector.match_skip_fixed(
                frame,
                rel_x=float(getattr(cfg, "skip_rel_x", 0.82125)),
                rel_y=float(getattr(cfg, "skip_rel_y", 0.055556)),
                box_w=float(getattr(cfg, "skip_box_w", 0.04)),
                box_h=float(getattr(cfg, "skip_box_h", 0.045)),
                threshold=float(cfg.threshold),
                require_presence=bool(
                    getattr(cfg, "skip_fixed_require_presence", True)
                ),
            )
        return self.detector.match(
            frame,
            button=button,
            threshold=cfg.threshold,
            scale_match=cfg.scale_match,
            require_confirm_text=getattr(cfg, "confirm_require_text", True),
        )

    def _loop(self) -> None:
        self._emit(WorkerState.RUNNING, "worker.detecting")
        window: Optional[WindowInfo] = None
        phase = "skip"  # skip | confirm
        confirm_deadline = 0.0
        focused_once = False
        capturer = ScreenCapturer()
        last_preview_at = 0.0
        last_status_at = 0.0
        preview_interval = 0.04
        status_interval = 0.12
        window_check_at = 0.0
        fps_counter = 0
        fps_start = time.monotonic()

        failure_key = "worker.stopped"
        failure_kwargs: Optional[Dict[str, Any]] = None
        try:
            capturer.open()
            self._run_loop(
                window,
                phase,
                confirm_deadline,
                focused_once,
                capturer,
                last_preview_at,
                last_status_at,
                preview_interval,
                status_interval,
                window_check_at,
                fps_counter,
                fps_start,
            )
        except Exception as exc:
            failure_key = "worker.error_stopped"
            failure_kwargs = {"err": f"{type(exc).__name__}: {exc}"}
        finally:
            capturer.close()

        self._emit(WorkerState.IDLE, failure_key, msg_kwargs=failure_kwargs)

    def _run_loop(
        self,
        window,
        phase,
        confirm_deadline,
        focused_once,
        capturer: ScreenCapturer,
        last_preview_at: float,
        last_status_at: float,
        preview_interval: float,
        status_interval: float,
        window_check_at: float,
        fps_counter: int,
        fps_start: float,
    ) -> None:
        unfocused = False
        focus_pause_at = 0.0
        skip_consensus = MatchConsensus()
        post_click = PostClickVerifier()
        confirm_click = ConfirmClickTracker()
        skip_cooldown_until = 0.0
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
                    unfocused = False
                    focus_pause_at = 0.0
                    skip_consensus.reset()
                    self._emit(WorkerState.ERROR, "worker.no_window")
                    self._wait(0.5)
                    continue

            if not focused_once:
                ok = clicker.ensure_foreground(window.hwnd)
                focused_once = True
                self._emit(
                    WorkerState.RUNNING,
                    "worker.focus_ok" if ok else "worker.focus_try",
                    window_title=window.title,
                    client_size=f"{window.width}×{window.height}",
                )
                self._wait(0.15)

            # Pause matching/clicking while the game is not the foreground window.
            # Keep the worker running and auto-resume when focus returns
            # (same recoverable pattern as "找不到遊戲視窗").
            if not clicker.is_foreground(window.hwnd):
                if not unfocused:
                    unfocused = True
                    focus_pause_at = time.monotonic()
                    skip_consensus.reset()
                    self._emit(
                        WorkerState.ERROR,
                        "worker.paused_unfocused",
                        window_title=window.title,
                        client_size=f"{window.width}×{window.height}",
                    )
                self._wait(0.25)
                continue

            if unfocused:
                paused_for = time.monotonic() - focus_pause_at
                if phase == "confirm" and paused_for > 0:
                    confirm_deadline += paused_for
                unfocused = False
                focus_pause_at = 0.0
                self._emit(
                    WorkerState.RUNNING,
                    "worker.focus_resumed",
                    window_title=window.title,
                    client_size=f"{window.width}×{window.height}",
                )

            try:
                capture = capturer.capture(window)
            except Exception as exc:
                self._emit(
                    WorkerState.ERROR,
                    "worker.capture_fail",
                    msg_kwargs={"exc": str(exc)},
                )
                self._wait(0.3)
                continue

            frame = capture.frame
            size_label = f"{capture.width}×{capture.height}"
            match_frame, sx, sy = self._prepare_frame(frame, cfg)

            now = time.monotonic()
            grace = getattr(cfg, "confirm_grace", 3.0)
            if phase == "confirm" and now >= confirm_deadline + grace:
                if confirm_click.awaiting_dismissal:
                    self._emit(
                        WorkerState.ERROR,
                        "worker.confirm_stuck",
                        window_title=window.title,
                        client_size=size_label,
                    )
                    return
                cooldown = (
                    float(getattr(cfg, "skip_verified_cooldown", 0.75))
                    if post_click.disappeared
                    else float(getattr(cfg, "skip_retry_cooldown", 2.0))
                )
                skip_cooldown_until = now + cooldown
                if post_click.disappeared:
                    self._emit(
                        WorkerState.RUNNING,
                        "worker.skip_gone_no_confirm",
                        window_title=window.title,
                        client_size=size_label,
                    )
                else:
                    self._emit(
                        WorkerState.RUNNING,
                        "worker.skip_unverified",
                        msg_kwargs={"cooldown": cooldown},
                        window_title=window.title,
                        client_size=size_label,
                    )
                phase = "skip"
                post_click.reset()
                skip_consensus.reset()
                self._wait(cfg.scan_interval)
                continue

            if phase == "skip" and now < skip_cooldown_until:
                if (now - last_status_at) >= status_interval:
                    remaining = max(0.0, skip_cooldown_until - now)
                    self._emit(
                        WorkerState.RUNNING,
                        "worker.skip_cooldown",
                        msg_kwargs={"remaining": remaining},
                        window_title=window.title,
                        client_size=size_label,
                    )
                    last_status_at = now
                self._wait(min(cfg.scan_interval, skip_cooldown_until - now))
                continue

            button = "confirm" if phase == "confirm" else "skip"
            match = self._detect_match(match_frame, cfg, button)
            ready_to_click = match.found
            consensus_count = 0
            if button == "skip":
                ready_to_click, consensus_count = skip_consensus.observe(
                    match,
                    required=int(getattr(cfg, "skip_consensus_required", 2)),
                    window=int(getattr(cfg, "skip_consensus_window", 3)),
                )
            elif confirm_click.awaiting_dismissal:
                dismissed = confirm_click.observe(
                    confirm_found=match.found,
                    required_misses=int(
                        getattr(cfg, "confirm_disappear_frames", 2)
                    ),
                )
                if dismissed:
                    phase = "skip"
                    skip_consensus.reset()
                    post_click.reset()
                    confirm_click.reset()
                    skip_cooldown_until = (
                        now
                        + float(getattr(cfg, "skip_verified_cooldown", 0.75))
                    )
                    self._emit(
                        WorkerState.RUNNING,
                        "worker.confirm_gone",
                        window_title=window.title,
                        client_size=size_label,
                    )
                    self._wait(cfg.scan_interval)
                    continue
                max_attempts = int(
                    getattr(cfg, "confirm_max_click_attempts", 3)
                )
                if confirm_click.exhausted(
                    now=now,
                    max_attempts=max_attempts,
                ):
                    self._emit(
                        WorkerState.ERROR,
                        "worker.confirm_retry_stuck",
                        window_title=window.title,
                        client_size=size_label,
                    )
                    return
                ready_to_click = match.found and confirm_click.can_click(
                    now=now,
                    max_attempts=max_attempts,
                )

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

            if (
                phase == "confirm"
                and not ready_to_click
                and now >= confirm_deadline
            ):
                skip_probe = self._detect_match(match_frame, cfg, "skip")
                post_click.observe(
                    skip_found=skip_probe.found,
                    required_misses=int(
                        getattr(cfg, "skip_disappear_frames", 2)
                    ),
                )

            if ready_to_click:
                if button == "skip":
                    delay = float(getattr(cfg, "skip_click_delay", 0.3))
                    if delay > 0:
                        self._wait(delay)
                        if self._stop.is_set():
                            return
                        if not clicker.is_foreground(window.hwnd):
                            continue

                # Click with the current-frame match — no second capture/detect.
                if not clicker.is_foreground(capture.hwnd):
                    continue
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
                    self._emit(
                        WorkerState.ERROR,
                        "worker.click_fail",
                        msg_kwargs={"exc": str(exc)},
                    )
                    self._wait(cfg.scan_interval)
                    continue

                if button == "skip":
                    with self._lock:
                        self.status.skip_count += 1
                    self._emit(
                        WorkerState.CLICKED_SKIP,
                        "worker.clicked_skip",
                        msg_kwargs={
                            "lang": match.lang,
                            "score": match.score,
                        },
                        score=match.score,
                        button="skip",
                        lang=match.lang,
                        preview=annotated,
                        window_title=window.title,
                        client_size=size_label,
                    )
                    phase = "confirm"
                    confirm_deadline = time.monotonic() + cfg.confirm_wait
                    post_click.reset()
                    confirm_click.reset()
                    self._wait(cfg.confirm_wait)
                else:
                    first_attempt = confirm_click.attempts == 0
                    confirm_click.record_click(
                        now=time.monotonic(),
                        retry_delay=float(
                            getattr(cfg, "confirm_retry_delay", 0.5)
                        ),
                    )
                    if first_attempt:
                        with self._lock:
                            self.status.confirm_count += 1
                    if first_attempt:
                        confirm_key = "worker.clicked_confirm"
                        confirm_kwargs = {
                            "lang": match.lang,
                            "score": match.score,
                        }
                    else:
                        confirm_key = "worker.clicked_confirm_retry"
                        confirm_kwargs = {
                            "attempt": confirm_click.attempts,
                            "lang": match.lang,
                            "score": match.score,
                        }
                    self._emit(
                        WorkerState.CLICKED_CONFIRM,
                        confirm_key,
                        msg_kwargs=confirm_kwargs,
                        score=match.score,
                        button="confirm",
                        lang=match.lang,
                        preview=annotated,
                        window_title=window.title,
                        client_size=size_label,
                    )
                    confirm_deadline = time.monotonic()
                    self._wait(0.1)
            else:
                # Idle detect: refresh preview often, text status less often
                if want_preview or (now - last_status_at) >= status_interval:
                    size_mismatch = (
                        window.width != cfg.expected_width
                        or window.height != cfg.expected_height
                    )
                    common_kwargs: Dict[str, Any] = {
                        "score": match.score,
                        "fps": float(self.status.detect_fps),
                        "size_mismatch": size_mismatch,
                        "actual": size_label,
                        "target": cfg.resolution_label(),
                    }
                    if phase == "confirm":
                        msg_key = "worker.waiting_confirm"
                        common_kwargs["skip_gone"] = post_click.disappeared
                    elif match.found:
                        msg_key = "worker.skip_candidate"
                        common_kwargs["count"] = consensus_count
                        common_kwargs["required"] = int(
                            getattr(cfg, "skip_consensus_required", 2)
                        )
                    else:
                        msg_key = "worker.detecting_score"
                    state = (
                        WorkerState.WAITING_CONFIRM
                        if phase == "confirm"
                        else WorkerState.RUNNING
                    )
                    self._emit(
                        state,
                        msg_key,
                        msg_kwargs=common_kwargs,
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
