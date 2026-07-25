"""Always-on-top mini overlay: live preview + start/stop (frameless)."""

from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk
import cv2
from PIL import Image, ImageTk

from app.i18n import t
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
        ui_lang: str,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(master)
        self.on_start = on_start
        self.on_stop = on_stop
        self._on_close_cb = on_close
        self._ui_lang = ui_lang
        self._photo: Optional[ImageTk.PhotoImage] = None
        self._drag_x = 0
        self._drag_y = 0
        self._preview_visible = True
        self._expanded_size = (320, 280)

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
            self.wm_attributes("-toolwindow", True)
        except Exception:
            pass

        self.protocol("WM_DELETE_WINDOW", self._handle_close)

        header = ctk.CTkFrame(self, fg_color="#0e121a", corner_radius=0, height=34)
        header.pack(fill="x")
        header.pack_propagate(False)

        self.title_label = ctk.CTkLabel(
            header,
            text=self._tt("preview.title"),
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=13, weight="bold"),
            text_color=TEXT,
        )
        self.title_label.pack(side="left", padx=12)

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

        self.collapse_btn = ctk.CTkButton(
            header,
            text="▾",
            width=32,
            height=28,
            corner_radius=6,
            fg_color="transparent",
            hover_color="#2a3348",
            text_color=MUTED,
            font=ctk.CTkFont(size=14),
            command=self._toggle_preview,
        )
        self.collapse_btn.pack(side="right", padx=(0, 2), pady=3)

        for widget in (header, self.title_label, self.status_dot):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._on_drag)

        self.status_label = ctk.CTkLabel(
            self,
            text=self._tt("status.idle"),
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=11),
            text_color=MUTED,
            anchor="w",
            justify="left",
            wraplength=280,
        )
        self.status_label.pack(fill="x", padx=12, pady=(6, 4))

        self.preview_wrap = ctk.CTkFrame(self, fg_color="#06080e", corner_radius=10)
        self.preview_wrap.pack(fill="both", expand=True, padx=12, pady=4)
        self.preview_label = ctk.CTkLabel(
            self.preview_wrap,
            text=self._tt("overlay.waiting"),
            text_color=MUTED,
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=11),
        )
        self.preview_label.pack(fill="both", expand=True, padx=4, pady=4)

        self.btns = ctk.CTkFrame(self, fg_color="transparent")
        self.btns.pack(fill="x", padx=12, pady=(6, 12))
        self.btns.grid_columnconfigure((0, 1), weight=1)

        self.btn_start = ctk.CTkButton(
            self.btns,
            text=self._tt("overlay.start"),
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
            self.btns,
            text=self._tt("controls.stop"),
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

        self._sync_collapse_chrome()
        self.after(2000, self._keep_topmost)

    def _tt(self, key: str, **kwargs) -> str:
        return t(key, lang=self._ui_lang, **kwargs)

    def set_ui_lang(self, lang: str) -> None:
        if lang == self._ui_lang:
            return
        self._ui_lang = lang
        self.title_label.configure(text=self._tt("preview.title"))
        self.btn_start.configure(text=self._tt("overlay.start"))
        self.btn_stop.configure(text=self._tt("controls.stop"))
        if self._photo is None:
            self.preview_label.configure(text=self._tt("overlay.waiting"))
        self._sync_collapse_chrome()

    def _sync_collapse_chrome(self) -> None:
        if self._preview_visible:
            self.collapse_btn.configure(text="▾")
            try:
                self.collapse_btn.configure(hover_color="#2a3348")
            except Exception:
                pass
        else:
            self.collapse_btn.configure(text="▸")

    def _toggle_preview(self) -> None:
        if self._preview_visible:
            self._expanded_size = (max(260, self.winfo_width()), max(220, self.winfo_height()))
            self.preview_wrap.pack_forget()
            self._preview_visible = False
            self.minsize(260, 118)
            collapsed_h = 34 + 48 + 52
            self.geometry(f"{self._expanded_size[0]}x{collapsed_h}")
        else:
            self.preview_wrap.pack(
                fill="both", expand=True, padx=12, pady=4, before=self.btns
            )
            self._preview_visible = True
            self.minsize(260, 220)
            w, h = self._expanded_size
            self.geometry(f"{w}x{h}")
        self._sync_collapse_chrome()

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
        self.status_label.configure(text=message, text_color=TEXT)
        # Keep wrap width roughly matched to current window.
        wrap = max(160, self.winfo_width() - 40)
        self.status_label.configure(wraplength=wrap)

    def update_preview(self, frame_bgr) -> None:
        if not self.winfo_exists() or frame_bgr is None or not self._preview_visible:
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
