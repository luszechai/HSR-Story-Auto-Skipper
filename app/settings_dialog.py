"""In-app settings page: scrollable single page with discrete slider steps."""

from __future__ import annotations

from typing import Callable, Optional

import cv2
import customtkinter as ctk
import numpy as np

from app.config import LANGS, RESOLUTION_PRESETS, AppConfig
from app.window_capture import capture_client, find_game_window

BG = "#080a10"
PANEL = "#10141e"
TEXT = "#e8ecf4"
MUTED = "#7a8499"
ACCENT = "#3ee0b0"
ACCENT_DIM = "#1a4a3c"
BLUE = "#1f6feb"

LANG_LABELS = {
    "zh_tw": "繁體中文",
    "zh_cn": "簡體中文",
    "en": "English",
    "jp": "日本語",
}


class SettingsPage(ctk.CTkFrame):
    """Embedded settings view (same window, scrollable)."""

    def __init__(
        self,
        master,
        config: AppConfig,
        *,
        on_apply: Optional[Callable[[AppConfig], None]] = None,
        on_back: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(master, fg_color=PANEL, corner_radius=16)
        self.config_data = config
        self.on_apply = on_apply
        self.on_back = on_back

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_scroll()
        self._build_footer()
        self._init_vars()
        self._build_form(self.scroll)

    def load_from_config(self, config: AppConfig) -> None:
        self.config_data = config
        self.threshold_var.set(self._snap(config.threshold, 0.50, 0.99, 0.01))
        self.fps_var.set(self._snap(self._interval_to_fps(config.scan_interval), 1, 30, 1))
        self.wait_var.set(self._snap(config.confirm_wait, 0.1, 2.0, 0.1))
        self.skip_delay_var.set(
            self._snap(float(getattr(config, "skip_click_delay", 0.3)), 0.0, 1.0, 0.1)
        )
        self.grace_var.set(self._snap(config.confirm_grace, 1.0, 8.0, 0.5))
        self.scale_var.set(config.scale_match)
        self.confirm_text_var.set(getattr(config, "confirm_require_text", True))
        self.normalize_var.set(config.normalize_resolution)
        self.skip_fixed_var.set(getattr(config, "skip_fixed", True))
        self.skip_presence_var.set(
            getattr(config, "skip_fixed_require_presence", True)
        )
        self.skip_rel_x_var.set(f"{float(getattr(config, 'skip_rel_x', 0.82125)):.5f}")
        self.skip_rel_y_var.set(f"{float(getattr(config, 'skip_rel_y', 0.055556)):.5f}")
        self._set_res(config.expected_width, config.expected_height)
        self.hotkey_start_var.set(config.hotkey_start)
        self.hotkey_stop_var.set(config.hotkey_stop)
        for lang, var in self.lang_vars.items():
            var.set(lang in config.enabled_langs)

    def _build_header(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 6))
        ctk.CTkLabel(
            head,
            text="設定",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=22, weight="bold"),
            text_color=TEXT,
        ).pack(side="left")
        ctk.CTkLabel(
            head,
            text="同一視窗 · 可捲動 · 數值依固定間隔調整",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=12),
            text_color=MUTED,
        ).pack(side="left", padx=(14, 0))

    def _build_scroll(self) -> None:
        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=BG,
            corner_radius=12,
            scrollbar_button_color="#2a3348",
            scrollbar_button_hover_color="#3a4660",
        )
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=18, pady=4)
        self.scroll.grid_columnconfigure(0, weight=1)

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=18, pady=(8, 16))
        ctk.CTkButton(
            footer,
            text="返回主畫面",
            width=110,
            height=36,
            fg_color="#2a3348",
            hover_color="#3a4660",
            command=self._back,
        ).pack(side="left")
        ctk.CTkButton(
            footer,
            text="重設為預設",
            width=110,
            height=36,
            fg_color="#2a3348",
            hover_color="#3a4660",
            command=self._reset_defaults,
        ).pack(side="left", padx=(8, 0))
        ctk.CTkButton(
            footer,
            text="套用並儲存",
            width=120,
            height=36,
            fg_color=ACCENT_DIM,
            hover_color="#226655",
            text_color=ACCENT,
            border_width=1,
            border_color=ACCENT,
            command=self._apply,
        ).pack(side="right")

    def _init_vars(self) -> None:
        cfg = self.config_data
        self.threshold_var = ctk.DoubleVar(
            value=self._snap(cfg.threshold, 0.50, 0.99, 0.01)
        )
        self.fps_var = ctk.DoubleVar(
            value=self._snap(self._interval_to_fps(cfg.scan_interval), 1, 30, 1)
        )
        self.wait_var = ctk.DoubleVar(value=self._snap(cfg.confirm_wait, 0.1, 2.0, 0.1))
        self.skip_delay_var = ctk.DoubleVar(
            value=self._snap(float(getattr(cfg, "skip_click_delay", 0.3)), 0.0, 1.0, 0.1)
        )
        self.grace_var = ctk.DoubleVar(value=self._snap(cfg.confirm_grace, 1.0, 8.0, 0.5))
        self.scale_var = ctk.BooleanVar(value=cfg.scale_match)
        self.confirm_text_var = ctk.BooleanVar(
            value=getattr(cfg, "confirm_require_text", True)
        )
        self.normalize_var = ctk.BooleanVar(value=cfg.normalize_resolution)
        self.skip_fixed_var = ctk.BooleanVar(value=getattr(cfg, "skip_fixed", True))
        self.skip_presence_var = ctk.BooleanVar(
            value=getattr(cfg, "skip_fixed_require_presence", True)
        )
        self.skip_rel_x_var = ctk.StringVar(
            value=f"{float(getattr(cfg, 'skip_rel_x', 0.82125)):.5f}"
        )
        self.skip_rel_y_var = ctk.StringVar(
            value=f"{float(getattr(cfg, 'skip_rel_y', 0.055556)):.5f}"
        )
        self.width_var = ctk.StringVar(value=str(cfg.expected_width))
        self.height_var = ctk.StringVar(value=str(cfg.expected_height))
        matched = next(
            (
                p[0]
                for p in RESOLUTION_PRESETS
                if p[1] == cfg.expected_width and p[2] == cfg.expected_height
            ),
            "自訂",
        )
        self.preset_var = ctk.StringVar(value=matched)
        self.hotkey_start_var = ctk.StringVar(value=cfg.hotkey_start)
        self.hotkey_stop_var = ctk.StringVar(value=cfg.hotkey_stop)
        self.lang_vars = {
            lang: ctk.BooleanVar(value=lang in cfg.enabled_langs) for lang in LANGS
        }

    def _section(self, parent, title: str, hint: str = "") -> ctk.CTkFrame:
        box = ctk.CTkFrame(parent, fg_color="#0e121a", corner_radius=12)
        box.pack(fill="x", padx=6, pady=(0, 12))
        ctk.CTkLabel(
            box,
            text=title,
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=15, weight="bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=14, pady=(12, 2))
        if hint:
            ctk.CTkLabel(
                box,
                text=hint,
                font=ctk.CTkFont(family="Microsoft JhengHei UI", size=11),
                text_color=MUTED,
            ).pack(anchor="w", padx=14, pady=(0, 6))
        return box

    def _build_form(self, parent) -> None:
        detect = self._section(parent, "偵測", "數值以固定間隔跳動（例如 FPS 每次 ±10）")
        self._slider(detect, "比對閾值", self.threshold_var, 0.50, 0.99, step=0.01)
        self._slider(detect, "偵測目標 FPS", self.fps_var, 1, 30, step=1, fmt_int=True)
        self._slider(
            detect, "偵測 Skip 後點擊前等待（秒）", self.skip_delay_var, 0.0, 1.0, step=0.1
        )
        self._slider(detect, "Skip 後等待確認（秒）", self.wait_var, 0.1, 2.0, step=0.1)
        self._slider(detect, "確認逾時放棄（秒）", self.grace_var, 1.0, 8.0, step=0.5)
        self._checkbox(detect, "多比例縮放比對（視窗略有縮放時較穩）", self.scale_var)
        self._checkbox(
            detect, "確認按鈕必須偵測到「確認」文字才點擊", self.confirm_text_var
        )

        fixed = self._section(
            parent,
            "Skip 固定座標",
            "Skip 在客戶區位置固定時建議開啟（不依賴模板／背景）",
        )
        self._checkbox(fixed, "使用固定座標點擊 Skip", self.skip_fixed_var)
        self._checkbox(
            fixed,
            "固定座標仍需確認 Skip 圖示存在（避免探索 HUD 誤點）",
            self.skip_presence_var,
        )
        row_f = ctk.CTkFrame(fixed, fg_color="transparent")
        row_f.pack(anchor="w", padx=14, pady=(4, 4))
        ctk.CTkLabel(row_f, text="相對 X", text_color=MUTED).pack(side="left")
        ctk.CTkEntry(
            row_f, textvariable=self.skip_rel_x_var, width=90, fg_color="#1c2233"
        ).pack(side="left", padx=(6, 16))
        ctk.CTkLabel(row_f, text="相對 Y", text_color=MUTED).pack(side="left")
        ctk.CTkEntry(
            row_f, textvariable=self.skip_rel_y_var, width=90, fg_color="#1c2233"
        ).pack(side="left", padx=(6, 0))
        self.skip_fixed_hint = ctk.CTkLabel(
            fixed,
            text=self._fixed_coord_hint(),
            text_color=MUTED,
            anchor="w",
            justify="left",
        )
        self.skip_fixed_hint.pack(fill="x", padx=14, pady=(2, 6))
        ctk.CTkButton(
            fixed,
            text="從遊戲視窗重新定位 Skip",
            width=200,
            fg_color=ACCENT_DIM,
            hover_color="#226655",
            text_color=ACCENT,
            border_width=1,
            border_color=ACCENT,
            command=self._locate_skip,
        ).pack(anchor="w", padx=14, pady=(4, 12))

        res = self._section(parent, "解析度", "請與遊戲視窗設定一致，並在此解析度下擷取模板")
        values = [p[0] for p in RESOLUTION_PRESETS] + ["自訂"]
        ctk.CTkOptionMenu(
            res,
            variable=self.preset_var,
            values=values,
            width=280,
            fg_color="#1c2233",
            button_color="#2a3348",
            button_hover_color="#3a4660",
            command=self._on_preset,
        ).pack(anchor="w", padx=14, pady=4)
        row = ctk.CTkFrame(res, fg_color="transparent")
        row.pack(anchor="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(row, text="寬", text_color=MUTED).pack(side="left")
        ctk.CTkEntry(
            row, textvariable=self.width_var, width=90, fg_color="#1c2233"
        ).pack(side="left", padx=(6, 16))
        ctk.CTkLabel(row, text="高", text_color=MUTED).pack(side="left")
        ctk.CTkEntry(
            row, textvariable=self.height_var, width=90, fg_color="#1c2233"
        ).pack(side="left", padx=(6, 0))
        self._checkbox(
            res,
            "自動正規化到目標解析度再比對（客戶區略有差異時建議開啟）",
            self.normalize_var,
        )
        ctk.CTkButton(
            res,
            text="套用 1600 × 900",
            width=160,
            fg_color=ACCENT_DIM,
            hover_color="#226655",
            text_color=ACCENT,
            border_width=1,
            border_color=ACCENT,
            command=lambda: self._set_res(1600, 900),
        ).pack(anchor="w", padx=14, pady=(10, 12))

        hotkey = self._section(parent, "熱鍵", "套用設定後立即生效")
        hk = ctk.CTkFrame(hotkey, fg_color="transparent")
        hk.pack(anchor="w", padx=14, pady=(4, 12))
        ctk.CTkLabel(hk, text="開始", text_color=MUTED, width=40).grid(
            row=0, column=0, padx=(0, 6)
        )
        ctk.CTkEntry(
            hk, textvariable=self.hotkey_start_var, width=80, fg_color="#1c2233"
        ).grid(row=0, column=1, padx=(0, 16))
        ctk.CTkLabel(hk, text="停止", text_color=MUTED, width=40).grid(
            row=0, column=2, padx=(0, 6)
        )
        ctk.CTkEntry(
            hk, textvariable=self.hotkey_stop_var, width=80, fg_color="#1c2233"
        ).grid(row=0, column=3)

        lang = self._section(parent, "語系", "同時比對的模板語系")
        for code in LANGS:
            self._checkbox(lang, LANG_LABELS[code], self.lang_vars[code])
        ctk.CTkFrame(lang, fg_color="transparent", height=8).pack()

    def _checkbox(self, parent, text: str, var: ctk.BooleanVar) -> None:
        ctk.CTkCheckBox(
            parent,
            text=text,
            variable=var,
            text_color=TEXT,
            fg_color=ACCENT_DIM,
            hover_color="#226655",
            checkmark_color=ACCENT,
            border_color="#3a4660",
        ).pack(anchor="w", padx=14, pady=(8, 4))

    def _slider(
        self,
        parent,
        title: str,
        var: ctk.DoubleVar,
        lo: float,
        hi: float,
        *,
        step: float,
        fmt_int: bool = False,
    ) -> None:
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.pack(fill="x", padx=14, pady=(10, 2))
        top = ctk.CTkFrame(box, fg_color="transparent")
        top.pack(fill="x")
        step_txt = f"{int(step)}" if float(step).is_integer() else f"{step:g}"
        ctk.CTkLabel(
            top,
            text=f"{title}（間隔 {step_txt}）",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=12),
            text_color=MUTED,
        ).pack(side="left")

        def _fmt(v: float) -> str:
            snapped = self._snap(float(v), lo, hi, step)
            return f"{int(round(snapped))}" if fmt_int else f"{snapped:.2f}"

        val_lbl = ctk.CTkLabel(
            top, text=_fmt(var.get()), font=ctk.CTkFont(size=12), text_color=TEXT
        )
        val_lbl.pack(side="right")

        def on_change(v):
            snapped = self._snap(float(v), lo, hi, step)
            if abs(float(var.get()) - snapped) > 1e-9:
                var.set(snapped)
            val_lbl.configure(text=_fmt(snapped))

        steps = max(1, int(round((hi - lo) / step)))
        ctk.CTkSlider(
            box,
            from_=lo,
            to=hi,
            variable=var,
            command=on_change,
            number_of_steps=steps,
            progress_color=ACCENT,
            button_color=ACCENT,
            button_hover_color="#5eefc4",
            fg_color="#1c2233",
        ).pack(fill="x", pady=(4, 0))

    @staticmethod
    def _snap(value: float, lo: float, hi: float, step: float) -> float:
        value = max(lo, min(hi, float(value)))
        if step <= 0:
            return value
        n = round((value - lo) / step)
        return round(lo + n * step, 10)

    def _on_preset(self, choice: str) -> None:
        for label, w, h in RESOLUTION_PRESETS:
            if label == choice:
                self._set_res(w, h)
                return

    def _set_res(self, w: int, h: int) -> None:
        self.width_var.set(str(w))
        self.height_var.set(str(h))
        matched = next(
            (p[0] for p in RESOLUTION_PRESETS if p[1] == w and p[2] == h),
            "自訂",
        )
        self.preset_var.set(matched)

    @staticmethod
    def _interval_to_fps(interval: float) -> float:
        return max(1.0, min(30.0, round(1.0 / max(0.01, float(interval)))))

    @staticmethod
    def _fps_to_interval(fps: float) -> float:
        return 1.0 / max(1.0, min(30.0, float(fps)))

    def _collect(self) -> AppConfig:
        cfg = self.config_data
        cfg.threshold = float(self.threshold_var.get())
        cfg.scan_interval = self._fps_to_interval(self.fps_var.get())
        cfg.confirm_wait = float(self.wait_var.get())
        cfg.skip_click_delay = float(self.skip_delay_var.get())
        cfg.confirm_grace = float(self.grace_var.get())
        cfg.scale_match = bool(self.scale_var.get())
        cfg.confirm_require_text = bool(self.confirm_text_var.get())
        cfg.normalize_resolution = bool(self.normalize_var.get())
        try:
            cfg.expected_width = max(320, int(self.width_var.get().strip()))
            cfg.expected_height = max(240, int(self.height_var.get().strip()))
        except ValueError:
            cfg.expected_width = 1600
            cfg.expected_height = 900
        cfg.click_method = "cursor"
        cfg.hotkey_start = self.hotkey_start_var.get().strip().lower() or "f6"
        cfg.hotkey_stop = self.hotkey_stop_var.get().strip().lower() or "f7"
        cfg.skip_fixed = bool(self.skip_fixed_var.get())
        cfg.skip_fixed_require_presence = bool(self.skip_presence_var.get())
        try:
            cfg.skip_rel_x = float(min(0.99, max(0.01, float(self.skip_rel_x_var.get()))))
            cfg.skip_rel_y = float(min(0.99, max(0.01, float(self.skip_rel_y_var.get()))))
        except ValueError:
            cfg.skip_rel_x = 0.82125
            cfg.skip_rel_y = 0.055556
        langs = [lang for lang, var in self.lang_vars.items() if var.get()]
        cfg.enabled_langs = langs or list(LANGS)
        return cfg

    def _fixed_coord_hint(self) -> str:
        try:
            rx = float(self.skip_rel_x_var.get())
            ry = float(self.skip_rel_y_var.get())
            w = int(self.width_var.get() or 1600)
            h = int(self.height_var.get() or 900)
            return f"約等於客戶區像素 ({int(round(w * rx))}, {int(round(h * ry))}) @ {w}×{h}"
        except ValueError:
            return "請輸入 0～1 的相對座標"

    def _locate_skip(self) -> None:
        """Capture game client and set Skip to the left icon of the top-right bar."""
        info = find_game_window(self.config_data.window_keywords)
        if info is None:
            self.skip_fixed_hint.configure(
                text="找不到遊戲視窗，請先以視窗模式開啟遊戲", text_color="#f85149"
            )
            return
        try:
            frame = capture_client(info).frame
        except Exception as exc:
            self.skip_fixed_hint.configure(
                text=f"截圖失敗：{exc}", text_color="#f85149"
            )
            return
        fh, fw = frame.shape[:2]
        # Known layout: Skip is leftmost of the three top-right icons.
        x0 = int(fw * 0.75)
        y1 = int(fh * 0.12)
        band = frame[0:y1, x0:fw]
        gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (7, 7), 0)
        diff = np.clip(gray.astype(np.int16) - blur.astype(np.int16), 0, 255).astype(
            np.uint8
        )
        mask = ((diff >= 8) & (gray >= 125)).astype(np.uint8) * 255
        n, _labels, stats, cents = cv2.connectedComponentsWithStats(mask, 8)
        cands = []
        for i in range(1, n):
            x, _y, bw, bh, area = stats[i]
            if area < 20 or area > 800:
                continue
            if bh < 6 or bw < 4:
                continue
            cands.append((x, float(cents[i][0]), float(cents[i][1])))
        if not cands:
            rx, ry = 0.82125, 0.055556
            self.skip_fixed_var.set(True)
            self.skip_rel_x_var.set(f"{rx:.5f}")
            self.skip_rel_y_var.set(f"{ry:.5f}")
            self.skip_fixed_hint.configure(
                text="自動定位失敗，已套用預設相對座標（請確認 Skip 可見）",
                text_color="#f0883e",
            )
            return
        cands.sort(key=lambda t: t[0])
        _x, lcx, lcy = cands[0]
        cx = x0 + int(round(lcx))
        cy = int(round(lcy))
        rx = cx / fw
        ry = cy / fh
        self.skip_fixed_var.set(True)
        self.skip_rel_x_var.set(f"{rx:.5f}")
        self.skip_rel_y_var.set(f"{ry:.5f}")
        self.width_var.set(str(fw))
        self.height_var.set(str(fh))
        self.skip_fixed_hint.configure(
            text=f"已定位 Skip 中心 ({cx}, {cy}) @ {fw}×{fh} → 相對 ({rx:.5f}, {ry:.5f})",
            text_color=ACCENT,
        )

    def _apply(self) -> None:
        cfg = self._collect()
        cfg.save()
        if self.on_apply:
            self.on_apply(cfg)
        self._back()

    def _back(self) -> None:
        if self.on_back:
            self.on_back()

    def _reset_defaults(self) -> None:
        defaults = AppConfig()
        self.threshold_var.set(self._snap(defaults.threshold, 0.50, 0.99, 0.01))
        self.fps_var.set(30)
        self.wait_var.set(self._snap(defaults.confirm_wait, 0.1, 2.0, 0.1))
        self.skip_delay_var.set(self._snap(defaults.skip_click_delay, 0.0, 1.0, 0.1))
        self.grace_var.set(self._snap(defaults.confirm_grace, 1.0, 8.0, 0.5))
        self.scale_var.set(defaults.scale_match)
        self.confirm_text_var.set(defaults.confirm_require_text)
        self.normalize_var.set(defaults.normalize_resolution)
        self.skip_fixed_var.set(defaults.skip_fixed)
        self.skip_presence_var.set(defaults.skip_fixed_require_presence)
        self.skip_rel_x_var.set(f"{defaults.skip_rel_x:.5f}")
        self.skip_rel_y_var.set(f"{defaults.skip_rel_y:.5f}")
        self._set_res(defaults.expected_width, defaults.expected_height)
        self.hotkey_start_var.set(defaults.hotkey_start)
        self.hotkey_stop_var.set(defaults.hotkey_stop)
        for lang, var in self.lang_vars.items():
            var.set(lang in defaults.enabled_langs)
        self.skip_fixed_hint.configure(text=self._fixed_coord_hint(), text_color=MUTED)


SettingsDialog = SettingsPage
