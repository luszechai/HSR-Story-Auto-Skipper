"""High-end dark CustomTkinter control panel."""

from __future__ import annotations

import threading
from typing import Optional

import customtkinter as ctk
import cv2
from PIL import Image, ImageTk
from pynput import keyboard

from app.config import AppConfig
from app.detector import TemplateDetector
from app.blacklist import SkipBlacklist
from app.overlay import FloatingOverlay
from app.reinforce import ReinforceStore
from app.settings_dialog import SettingsDialog
from app.template_capture import TemplateCaptureDialog
from app.worker import AutoSkipWorker, WorkerState, WorkerStatus

# Visual system
BG = "#080a10"
PANEL = "#10141e"
PANEL_ALT = "#141a26"
ACCENT = "#3ee0b0"
ACCENT_DIM = "#1a4a3c"
AMBER = "#f0a050"
DANGER = "#f85149"
TEXT = "#e8ecf4"
MUTED = "#7a8499"
BLUE = "#1f6feb"

STATE_COLORS = {
    WorkerState.IDLE: MUTED,
    WorkerState.RUNNING: ACCENT,
    WorkerState.WAITING_CONFIRM: AMBER,
    WorkerState.CLICKED_SKIP: ACCENT,
    WorkerState.CLICKED_CONFIRM: ACCENT,
    WorkerState.AVOIDED: AMBER,
    WorkerState.ERROR: DANGER,
}


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title("HSR Auto Skip")
        self.geometry("1080x680")
        self.minsize(960, 600)
        self.configure(fg_color=BG)
        self._apply_window_icon()

        self.config_data = AppConfig.load()
        self.detector = TemplateDetector()
        self.detector.reload(self.config_data.enabled_langs)
        self.blacklist = SkipBlacklist()
        self.reinforce = ReinforceStore()
        self.worker = AutoSkipWorker(
            self.config_data,
            self.detector,
            on_status=self._on_worker_status,
            blacklist=self.blacklist,
            reinforce=self.reinforce,
        )
        self._preview_photo: Optional[ImageTk.PhotoImage] = None
        self._pulse_on = False
        self._hotkey_listener: Optional[keyboard.GlobalHotKeys] = None
        self._pending_status: Optional[WorkerStatus] = None
        self._status_lock = threading.Lock()
        self._overlay: Optional[FloatingOverlay] = None

        self._build_ui()
        self._refresh_template_info()
        self._update_res_label()
        self._refresh_blacklist_button()
        self._start_hotkeys()
        self.after(50, self._drain_status)

    def _apply_window_icon(self) -> None:
        """Set taskbar / title-bar icon from bundled brand assets."""
        from app.config import ROOT, bundle_root

        roots = (ROOT, bundle_root())
        ico = next(
            (r / "assets" / "brand" / "app.ico" for r in roots if (r / "assets" / "brand" / "app.ico").exists()),
            None,
        )
        png = next(
            (r / "assets" / "brand" / "app.png" for r in roots if (r / "assets" / "brand" / "app.png").exists()),
            None,
        )
        try:
            if ico is not None:
                self.iconbitmap(str(ico))
            if png is not None:
                from PIL import Image, ImageTk

                img = Image.open(png)
                self._wm_icon = ImageTk.PhotoImage(img)
                self.iconphoto(True, self._wm_icon)
        except Exception:
            pass
        self.after(600, self._pulse_status)
        self.after(200, self._open_overlay)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Layout ──────────────────────────────────────────────
    def _build_ui(self) -> None:
        root = ctk.CTkFrame(self, fg_color=BG)
        root.pack(fill="both", expand=True, padx=18, pady=16)
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(0, weight=1)

        self._build_sidebar(root)
        self._build_preview(root)
        self._build_controls(root)

    def _build_sidebar(self, parent) -> None:
        side = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=16, width=240)
        side.grid(row=0, column=0, sticky="nsw", padx=(0, 12))
        side.grid_propagate(False)

        brand = ctk.CTkFrame(side, fg_color="transparent")
        brand.pack(fill="x", padx=20, pady=(28, 8))
        ctk.CTkLabel(
            brand,
            text="HSR",
            font=ctk.CTkFont(family="Segoe UI Semibold", size=28, weight="bold"),
            text_color=ACCENT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            brand,
            text="Auto Skip",
            font=ctk.CTkFont(family="Segoe UI", size=20),
            text_color=TEXT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            brand,
            text="劇情自動跳過",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=12),
            text_color=MUTED,
        ).pack(anchor="w", pady=(4, 0))

        status_box = ctk.CTkFrame(side, fg_color=PANEL_ALT, corner_radius=12)
        status_box.pack(fill="x", padx=16, pady=(24, 8))
        row = ctk.CTkFrame(status_box, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=14)
        self.status_dot = ctk.CTkLabel(
            row, text="●", font=ctk.CTkFont(size=14), text_color=MUTED, width=20
        )
        self.status_dot.pack(side="left")
        self.status_label = ctk.CTkLabel(
            row,
            text="待命",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=13),
            text_color=TEXT,
            anchor="w",
        )
        self.status_label.pack(side="left", fill="x", expand=True)

        self.window_label = ctk.CTkLabel(
            side,
            text="視窗：—",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=11),
            text_color=MUTED,
            anchor="w",
            wraplength=200,
        )
        self.window_label.pack(fill="x", padx=20, pady=(8, 4))

        self.res_label = ctk.CTkLabel(
            side,
            text="解析度：—",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=11),
            text_color=MUTED,
            anchor="w",
            wraplength=200,
        )
        self.res_label.pack(fill="x", padx=20, pady=2)

        self.score_label = ctk.CTkLabel(
            side,
            text="分數：—",
            font=ctk.CTkFont(size=11),
            text_color=MUTED,
            anchor="w",
        )
        self.score_label.pack(fill="x", padx=20, pady=2)

        self.fps_label = ctk.CTkLabel(
            side,
            text="偵測：— FPS",
            font=ctk.CTkFont(size=11),
            text_color=MUTED,
            anchor="w",
        )
        self.fps_label.pack(fill="x", padx=20, pady=2)

        self.count_label = ctk.CTkLabel(
            side,
            text="Skip 0 · 確認 0",
            font=ctk.CTkFont(size=11),
            text_color=MUTED,
            anchor="w",
        )
        self.count_label.pack(fill="x", padx=20, pady=2)

        self.blacklist_label = ctk.CTkLabel(
            side,
            text="誤判名單：0",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=11),
            text_color=MUTED,
            anchor="w",
        )
        self.blacklist_label.pack(fill="x", padx=20, pady=2)

        self.reinforce_label = ctk.CTkLabel(
            side,
            text=f"強化模板：{self.reinforce.count()}/{self.config_data.reinforce_max}",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=11),
            text_color=MUTED,
            anchor="w",
        )
        self.reinforce_label.pack(fill="x", padx=20, pady=2)

        self.template_label = ctk.CTkLabel(
            side,
            text="模板：0",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=11),
            text_color=MUTED,
            anchor="w",
            wraplength=200,
        )
        self.template_label.pack(fill="x", padx=20, pady=(12, 4))

        hk = ctk.CTkFrame(side, fg_color=PANEL_ALT, corner_radius=12)
        hk.pack(side="bottom", fill="x", padx=16, pady=20)
        ctk.CTkLabel(
            hk,
            text="熱鍵",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=MUTED,
        ).pack(anchor="w", padx=14, pady=(12, 2))
        self.hotkey_hint = ctk.CTkLabel(
            hk,
            text=self._hotkey_text(),
            font=ctk.CTkFont(family="Consolas", size=12),
            text_color=TEXT,
            justify="left",
        )
        self.hotkey_hint.pack(anchor="w", padx=14, pady=(0, 12))

    def _build_preview(self, parent) -> None:
        mid = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=16)
        mid.grid(row=0, column=1, sticky="nsew")
        mid.grid_rowconfigure(1, weight=1)
        mid.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(mid, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 4))
        ctk.CTkLabel(
            head,
            text="即時預覽",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=14, weight="bold"),
            text_color=TEXT,
        ).pack(side="left")
        ctk.CTkLabel(
            head,
            text="命中時會標示按鈕區域",
            font=ctk.CTkFont(size=11),
            text_color=MUTED,
        ).pack(side="right")

        preview_wrap = ctk.CTkFrame(mid, fg_color="#06080e", corner_radius=12)
        preview_wrap.grid(row=1, column=0, sticky="nsew", padx=16, pady=(4, 16))
        self.preview_label = ctk.CTkLabel(
            preview_wrap,
            text="啟動後顯示遊戲畫面",
            text_color=MUTED,
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=13),
        )
        self.preview_label.pack(fill="both", expand=True, padx=8, pady=8)

    def _build_controls(self, parent) -> None:
        right = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=16, width=280)
        right.grid(row=0, column=2, sticky="nse", padx=(12, 0))
        right.grid_propagate(False)

        ctk.CTkLabel(
            right,
            text="控制",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=14, weight="bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=18, pady=(20, 12))

        self.btn_start = ctk.CTkButton(
            right,
            text="開始偵測",
            height=42,
            corner_radius=10,
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=14, weight="bold"),
            fg_color=ACCENT_DIM,
            hover_color="#226655",
            text_color=ACCENT,
            border_width=1,
            border_color=ACCENT,
            command=self.start_detection,
        )
        self.btn_start.pack(fill="x", padx=18, pady=(0, 8))

        self.btn_stop = ctk.CTkButton(
            right,
            text="停止",
            height=42,
            corner_radius=10,
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=14),
            fg_color="#2a2030",
            hover_color="#3d2a38",
            text_color=DANGER,
            border_width=1,
            border_color="#6e3038",
            command=self.stop_detection,
            state="disabled",
        )
        self.btn_stop.pack(fill="x", padx=18, pady=(0, 16))

        # Quick summary of current settings
        self.settings_summary = ctk.CTkLabel(
            right,
            text="",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=11),
            text_color=MUTED,
            justify="left",
            anchor="w",
            wraplength=240,
        )
        self.settings_summary.pack(fill="x", padx=18, pady=(0, 12))
        self._update_settings_summary()

        ctk.CTkButton(
            right,
            text="設定",
            height=40,
            corner_radius=10,
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=14, weight="bold"),
            fg_color="#1c2233",
            hover_color="#2a3348",
            text_color=TEXT,
            border_width=1,
            border_color="#3a4660",
            command=self._open_settings,
        ).pack(fill="x", padx=18, pady=(4, 8))

        ctk.CTkButton(
            right,
            text="浮動預覽窗",
            height=36,
            corner_radius=8,
            fg_color="#1c2233",
            hover_color="#2a3348",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=13),
            command=self._open_overlay,
        ).pack(fill="x", padx=18, pady=(0, 8))

        ctk.CTkButton(
            right,
            text="擷取模板",
            height=36,
            corner_radius=8,
            fg_color=BLUE,
            hover_color="#388bfd",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=13),
            command=self._open_capture,
        ).pack(fill="x", padx=18, pady=(4, 8))

        ctk.CTkButton(
            right,
            text="重新載入模板",
            height=36,
            corner_radius=8,
            fg_color="#2a3348",
            hover_color="#3a4660",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=13),
            command=self._reload_templates,
        ).pack(fill="x", padx=18, pady=(0, 8))

        self.btn_blacklist = ctk.CTkButton(
            right,
            text=self._blacklist_btn_text(),
            height=36,
            corner_radius=8,
            fg_color=ACCENT_DIM if self.config_data.blacklist_enabled else "#2a3348",
            hover_color="#226655" if self.config_data.blacklist_enabled else "#3a4660",
            text_color=ACCENT if self.config_data.blacklist_enabled else MUTED,
            border_width=1,
            border_color=ACCENT if self.config_data.blacklist_enabled else "#3a4660",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=13),
            command=self._toggle_blacklist,
        )
        self.btn_blacklist.pack(fill="x", padx=18, pady=(0, 8))

        ctk.CTkButton(
            right,
            text="清空誤判名單",
            height=36,
            corner_radius=8,
            fg_color="#2a2030",
            hover_color="#3d2a38",
            text_color=AMBER,
            border_width=1,
            border_color="#6e5030",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=13),
            command=self._clear_blacklist,
        ).pack(fill="x", padx=18, pady=(0, 8))

        ctk.CTkButton(
            right,
            text="清空強化模板",
            height=36,
            corner_radius=8,
            fg_color="#2a2030",
            hover_color="#3d2a38",
            text_color=AMBER,
            border_width=1,
            border_color="#6e5030",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=13),
            command=self._clear_reinforce,
        ).pack(fill="x", padx=18, pady=(0, 20))

    def _hotkey_text(self) -> str:
        start = self.config_data.hotkey_start.upper()
        stop = self.config_data.hotkey_stop.upper()
        return f"{start}  開始\n{stop}  停止\n角落 緊急停止"

    def _update_res_label(self) -> None:
        self.res_label.configure(
            text=f"目標：{self.config_data.resolution_label()}"
        )

    def _update_settings_summary(self) -> None:
        cfg = self.config_data
        langs = "、".join(cfg.enabled_langs) if cfg.enabled_langs else "—"
        self.settings_summary.configure(
            text=(
                f"解析度 {cfg.resolution_label()}\n"
                f"閾值 {cfg.threshold:.2f} · 間隔 {cfg.scan_interval:.2f}s\n"
                f"Skip 點擊前 {getattr(cfg, 'skip_click_delay', 0.1):.2f}s\n"
                f"確認等待 {cfg.confirm_wait:.2f}s\n"
                f"語系：{langs}"
            )
        )

    # ── Actions ─────────────────────────────────────────────
    def start_detection(self) -> None:
        self.worker.update_config(self.config_data)
        counts = self.detector.count_by_button()
        if counts.get("skip", 0) == 0:
            self.status_label.configure(text="請先擷取 Skip 模板")
            self.status_dot.configure(text_color=DANGER)
            return
        self.worker.start()
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        if self._overlay is not None and self._overlay.winfo_exists():
            self._overlay.set_running(True)

    def stop_detection(self) -> None:
        self.worker.stop()
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        if self._overlay is not None and self._overlay.winfo_exists():
            self._overlay.set_running(False)

    def _open_overlay(self) -> None:
        if self._overlay is not None and self._overlay.winfo_exists():
            self._overlay.attributes("-topmost", True)
            self._overlay.lift()
            self._overlay.focus_force()
            return
        self._overlay = FloatingOverlay(
            self,
            on_start=self.start_detection,
            on_stop=self.stop_detection,
            on_close=self._on_overlay_closed,
        )
        self._overlay.set_running(self.worker.is_running)

    def _on_overlay_closed(self) -> None:
        self._overlay = None

    def _open_settings(self) -> None:
        SettingsDialog(self, self.config_data, on_apply=self._on_settings_applied)

    def _on_settings_applied(self, cfg: AppConfig) -> None:
        self.config_data = cfg
        self.worker.update_config(cfg)
        self.detector.reload(cfg.enabled_langs)
        self._refresh_template_info()
        self._update_res_label()
        self._update_settings_summary()
        self.hotkey_hint.configure(text=self._hotkey_text())
        self.status_label.configure(text="設定已套用")
        self.status_dot.configure(text_color=ACCENT)

    def _open_capture(self) -> None:
        TemplateCaptureDialog(
            self,
            keywords=self.config_data.window_keywords,
            on_saved=self._refresh_template_info,
        )

    def _blacklist_btn_text(self) -> str:
        on = getattr(self.config_data, "blacklist_enabled", True)
        return "誤判名單：開啟" if on else "誤判名單：關閉"

    def _refresh_blacklist_button(self) -> None:
        on = getattr(self.config_data, "blacklist_enabled", True)
        self.btn_blacklist.configure(
            text=self._blacklist_btn_text(),
            fg_color=ACCENT_DIM if on else "#2a3348",
            hover_color="#226655" if on else "#3a4660",
            text_color=ACCENT if on else MUTED,
            border_color=ACCENT if on else "#3a4660",
        )
        size = self.blacklist.count()
        state = "開" if on else "關"
        self.blacklist_label.configure(text=f"誤判名單：{size}（{state}）")

    def _toggle_blacklist(self) -> None:
        self.config_data.blacklist_enabled = not getattr(
            self.config_data, "blacklist_enabled", True
        )
        self.config_data.save()
        self.worker.update_config(self.config_data)
        self._refresh_blacklist_button()
        self.status_label.configure(
            text=(
                "誤判名單已開啟"
                if self.config_data.blacklist_enabled
                else "誤判名單已關閉"
            )
        )

    def _clear_blacklist(self) -> None:
        self.worker.clear_blacklist()
        self._refresh_blacklist_button()
        self.status_label.configure(text="已清空誤判名單")

    def _clear_reinforce(self) -> None:
        self.worker.clear_reinforce()
        self.reinforce_label.configure(
            text=f"強化模板：0/{self.config_data.reinforce_max}"
        )
        self._refresh_template_info()
        self.status_label.configure(text="已清空強化模板")

    def _reload_templates(self) -> None:
        n = self.detector.reload(self.config_data.enabled_langs)
        self._refresh_template_info()
        self.status_label.configure(text=f"已載入 {n} 個模板")

    def _refresh_template_info(self) -> None:
        self.detector.reload(self.config_data.enabled_langs)
        counts = self.detector.count_by_button()
        self.template_label.configure(
            text=f"模板：Skip {counts.get('skip', 0)} · 確認 {counts.get('confirm', 0)}"
        )

    # ── Status / preview ────────────────────────────────────
    def _on_worker_status(self, status: WorkerStatus) -> None:
        with self._status_lock:
            self._pending_status = status

    def _drain_status(self) -> None:
        status = None
        with self._status_lock:
            if self._pending_status is not None:
                status = self._pending_status
                self._pending_status = None
        if status is not None:
            self._apply_status(status)
        self.after(16, self._drain_status)

    def _apply_status(self, status: WorkerStatus) -> None:
        color = STATE_COLORS.get(status.state, MUTED)
        self.status_dot.configure(text_color=color)
        self.status_label.configure(text=status.message)
        if status.window_title:
            title = status.window_title
            if len(title) > 28:
                title = title[:26] + "…"
            self.window_label.configure(text=f"視窗：{title}")
        if status.client_size:
            self.res_label.configure(
                text=(
                    f"實際 {status.client_size} · 目標 "
                    f"{self.config_data.resolution_label()}"
                )
            )
        if status.last_score:
            extra = f" · {status.last_lang}" if status.last_lang else ""
            self.score_label.configure(
                text=f"分數：{status.last_score:.2f}{extra}"
            )
        if status.detect_fps:
            self.fps_label.configure(
                text=f"偵測：{status.detect_fps:.0f} FPS"
            )
        self.count_label.configure(
            text=(
                f"Skip {status.skip_count} · 確認 {status.confirm_count}"
                f" · 避開 {status.avoid_count}"
            )
        )
        self.blacklist_label.configure(
            text=(
                f"誤判名單：{status.blacklist_size}"
                f"（{'開' if getattr(self.config_data, 'blacklist_enabled', True) else '關'}）"
            )
        )
        self.reinforce_label.configure(
            text=f"強化模板：{status.reinforce_size}/{status.reinforce_max}"
        )
        if status.preview_bgr is not None:
            self._show_preview(status.preview_bgr)
            if self._overlay is not None and self._overlay.winfo_exists():
                self._overlay.update_preview(status.preview_bgr)
        if self._overlay is not None and self._overlay.winfo_exists():
            self._overlay.update_status(status.state, status.message)
        if status.state == WorkerState.IDLE:
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            if self._overlay is not None and self._overlay.winfo_exists():
                self._overlay.set_running(False)

    def _show_preview(self, frame_bgr) -> None:
        self.update_idletasks()
        max_w = max(200, self.preview_label.winfo_width() - 16)
        max_h = max(160, self.preview_label.winfo_height() - 16)
        h, w = frame_bgr.shape[:2]
        scale = min(max_w / w, max_h / h, 1.0)
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA)
        img = Image.fromarray(resized)
        self._preview_photo = ImageTk.PhotoImage(img)
        self.preview_label.configure(image=self._preview_photo, text="")

    def _pulse_status(self) -> None:
        if self.worker.is_running:
            self._pulse_on = not self._pulse_on
            base = STATE_COLORS.get(self.worker.status.state, ACCENT)
            self.status_dot.configure(
                text_color=base if self._pulse_on else MUTED
            )
        self.after(600, self._pulse_status)

    # ── Hotkeys ─────────────────────────────────────────────
    def _start_hotkeys(self) -> None:
        start = f"<{self.config_data.hotkey_start.lower()}>"
        stop = f"<{self.config_data.hotkey_stop.lower()}>"
        mapping = {
            start: lambda: self.after(0, self.start_detection),
            stop: lambda: self.after(0, self.stop_detection),
        }
        try:
            self._hotkey_listener = keyboard.GlobalHotKeys(mapping)
            self._hotkey_listener.start()
        except Exception:
            self._hotkey_listener = None

    def _on_close(self) -> None:
        self.stop_detection()
        if self._overlay is not None and self._overlay.winfo_exists():
            try:
                self._overlay.destroy()
            except Exception:
                pass
            self._overlay = None
        if self._hotkey_listener:
            try:
                self._hotkey_listener.stop()
            except Exception:
                pass
        self.config_data.save()
        self.destroy()


def run() -> None:
    app = App()
    app.mainloop()
