"""Always-on-top mini overlay: live preview + start/stop (frameless)."""

from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk
import cv2
from PIL import Image, ImageTk

from app.worker import WorkerState

BG = "#080a10"
ACCENT = "#3ee0b0"
ACCENT_DIM = "#1a4a3c"
DANGER = "#f85149"
TEXT = "#e8ecf4"
MUTED = "#7a8499"

STATE_COLORS = {
    WorkerState.IDLE: MUTED,
    WorkerState.RUNNING: ACCENT,
    WorkerState.WAITING_CONFIRM: "#f0a050",
    WorkerState.CLICKED_SKIP: ACCENT,
    WorkerState.CLICKED_CONFIRM: ACCENT,
    WorkerState.ERROR: DANGER,
}


class FloatingOverlay(ctk.CTkToplevel):
    """Compact always-on-top control panel with scaled live preview."""

    def __init__(
        self,
        master,
        *,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(master)
        self.on_start = on_start
        self.on_stop = on_stop
        self._on_close_cb = on_close
        self._photo: Optional[ImageTk.PhotoImage] = None
        self._drag_x = 0
        self._drag_y = 0

        self.geometry("320x280+40+80")
        self.minsize(260, 220)
        self.configure(fg_color=BG)
        self.attributes("-topmost", True)
        try:
            self.wm_attributes("-topmost", True)
        except Exception:
            pass

        # Remove Windows title bar / chrome
        self.overrideredirect(True)
        try:
            # Keep a thin borderless look on Windows
            self.wm_attributes("-toolwindow", True)
        except Exception:
            pass

        self.protocol("WM_DELETE_WINDOW", self._handle_close)

        # Drag handle + close (replaces system title bar)
        header = ctk.CTkFrame(self, fg_color="#0e121a", corner_radius=0, height=34)
        header.pack(fill="x")
        header.pack_propagate(False)

        title = ctk.CTkLabel(
            header,
            text="即時預覽",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=13, weight="bold"),
            text_color=TEXT,
        )
        title.pack(side="left", padx=12)

        self.status_dot = ctk.CTkLabel(
            header, text="●", font=ctk.CTkFont(size=12), text_color=MUTED
        )
        self.status_dot.pack(side="left", padx=(4, 0))

        close_btn = ctk.CTkButton(
            header,
            text="×",
            width=32,
            height=28,
            corner_radius=6,
            fg_color="transparent",
            hover_color="#3d2a38",
            text_color=MUTED,
            font=ctk.CTkFont(size=16),
            command=self._handle_close,
        )
        close_btn.pack(side="right", padx=6, pady=3)

        for widget in (header, title, self.status_dot):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._on_drag)

        self.status_label = ctk.CTkLabel(
            self,
            text="待命",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=11),
            text_color=MUTED,
            anchor="w",
        )
        self.status_label.pack(fill="x", padx=12, pady=(6, 4))

        preview_wrap = ctk.CTkFrame(self, fg_color="#06080e", corner_radius=10)
        preview_wrap.pack(fill="both", expand=True, padx=12, pady=4)
        self.preview_label = ctk.CTkLabel(
            preview_wrap,
            text="等待畫面…",
            text_color=MUTED,
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=11),
        )
        self.preview_label.pack(fill="both", expand=True, padx=4, pady=4)

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=12, pady=(6, 12))
        btns.grid_columnconfigure((0, 1), weight=1)

        self.btn_start = ctk.CTkButton(
            btns,
            text="開始",
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=13, weight="bold"),
            fg_color=ACCENT_DIM,
            hover_color="#226655",
            text_color=ACCENT,
            border_width=1,
            border_color=ACCENT,
            command=self.on_start,
        )
        self.btn_start.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self.btn_stop = ctk.CTkButton(
            btns,
            text="停止",
            height=34,
            corner_radius=8,
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=13),
            fg_color="#2a2030",
            hover_color="#3d2a38",
            text_color=DANGER,
            border_width=1,
            border_color="#6e3038",
            command=self.on_stop,
            state="disabled",
        )
        self.btn_stop.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self.after(2000, self._keep_topmost)

    def _start_drag(self, event) -> None:
        self._drag_x = event.x_root - self.winfo_x()
        self._drag_y = event.y_root - self.winfo_y()

    def _on_drag(self, event) -> None:
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.geometry(f"+{x}+{y}")

    def _keep_topmost(self) -> None:
        if not self.winfo_exists():
            return
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass
        self.after(2000, self._keep_topmost)

    def _handle_close(self) -> None:
        if self._on_close_cb:
            self._on_close_cb()
        self.destroy()

    def set_running(self, running: bool) -> None:
        if not self.winfo_exists():
            return
        if running:
            self.btn_start.configure(state="disabled")
            self.btn_stop.configure(state="normal")
        else:
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")

    def update_status(self, state: WorkerState, message: str) -> None:
        if not self.winfo_exists():
            return
        color = STATE_COLORS.get(state, MUTED)
        self.status_dot.configure(text_color=color)
        text = message if len(message) <= 36 else message[:34] + "…"
        self.status_label.configure(text=text, text_color=TEXT)

    def update_preview(self, frame_bgr) -> None:
        if not self.winfo_exists() or frame_bgr is None:
            return
        self.update_idletasks()
        max_w = max(120, self.preview_label.winfo_width() - 8)
        max_h = max(80, self.preview_label.winfo_height() - 8)
        h, w = frame_bgr.shape[:2]
        scale = min(max_w / w, max_h / h, 1.0)
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA)
        img = Image.fromarray(resized)
        self._photo = ImageTk.PhotoImage(img)
        self.preview_label.configure(image=self._photo, text="")
