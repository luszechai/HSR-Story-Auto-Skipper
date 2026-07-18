"""In-app settings page: scrollable, ordinal steps (not a popup)."""

from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from app.config import LANGS, RESOLUTION_PRESETS, AppConfig

BG = "#080a10"
PANEL = "#10141e"
PANEL_ALT = "#141a26"
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

STEPS = (
    ("偵測", "調整比對速度與點擊時機"),
    ("解析度", "對齊遊戲視窗客戶區大小"),
    ("熱鍵", "設定開始／停止快捷鍵"),
    ("語系", "選擇要比對的模板語系"),
)


class SettingsPage(ctk.CTkFrame):
    """Embedded settings view with step-by-step flow."""

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
        self.step = 0
        self._step_bodies: list[ctk.CTkFrame] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_stepper()
        self._build_scroll_area()
        self._build_footer()
        self._init_vars()
        self._populate_steps()
        self._show_step(0)

    def load_from_config(self, config: AppConfig) -> None:
        """Refresh widgets when opening the page."""
        self.config_data = config
        self.threshold_var.set(config.threshold)
        self.fps_var.set(self._interval_to_fps(config.scan_interval))
        self.wait_var.set(config.confirm_wait)
        self.skip_delay_var.set(float(getattr(config, "skip_click_delay", 0.1)))
        self.grace_var.set(config.confirm_grace)
        self.scale_var.set(config.scale_match)
        self.reinforce_var.set(getattr(config, "reinforce_enabled", True))
        self.confirm_text_var.set(getattr(config, "confirm_require_text", True))
        self.reinforce_max_var.set(float(getattr(config, "reinforce_max", 50)))
        self.normalize_var.set(config.normalize_resolution)
        self._set_res(config.expected_width, config.expected_height)
        self.hotkey_start_var.set(config.hotkey_start)
        self.hotkey_stop_var.set(config.hotkey_stop)
        for lang, var in self.lang_vars.items():
            var.set(lang in config.enabled_langs)
        self._show_step(0)

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
            text="依步驟調整 · 可捲動 · 套用後寫入 config.json",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=12),
            text_color=MUTED,
        ).pack(side="left", padx=(14, 0))

    def _build_stepper(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=PANEL_ALT, corner_radius=12)
        bar.grid(row=1, column=0, sticky="ew", padx=18, pady=(4, 8))
        self._step_btns: list[ctk.CTkButton] = []
        for i, (title, _hint) in enumerate(STEPS):
            btn = ctk.CTkButton(
                bar,
                text=f"{i + 1}. {title}",
                height=34,
                corner_radius=8,
                font=ctk.CTkFont(family="Microsoft JhengHei UI", size=13),
                fg_color="transparent",
                hover_color="#2a3348",
                text_color=MUTED,
                command=lambda idx=i: self._show_step(idx),
            )
            btn.pack(side="left", padx=(10 if i == 0 else 4, 4), pady=10)
            self._step_btns.append(btn)

        self.step_hint = ctk.CTkLabel(
            bar,
            text="",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=12),
            text_color=MUTED,
        )
        self.step_hint.pack(side="right", padx=14)

    def _build_scroll_area(self) -> None:
        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=BG,
            corner_radius=12,
            scrollbar_button_color="#2a3348",
            scrollbar_button_hover_color="#3a4660",
        )
        self.scroll.grid(row=2, column=0, sticky="nsew", padx=18, pady=4)
        self.scroll.grid_columnconfigure(0, weight=1)

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=18, pady=(8, 16))

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

        self.btn_next = ctk.CTkButton(
            footer,
            text="下一步",
            width=100,
            height=36,
            fg_color=BLUE,
            hover_color="#388bfd",
            command=self._next_step,
        )
        self.btn_next.pack(side="right")
        self.btn_prev = ctk.CTkButton(
            footer,
            text="上一步",
            width=100,
            height=36,
            fg_color="#2a3348",
            hover_color="#3a4660",
            command=self._prev_step,
        )
        self.btn_prev.pack(side="right", padx=(0, 8))
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
        ).pack(side="right", padx=(0, 8))

    def _init_vars(self) -> None:
        cfg = self.config_data
        self.threshold_var = ctk.DoubleVar(value=cfg.threshold)
        self.fps_var = ctk.DoubleVar(value=self._interval_to_fps(cfg.scan_interval))
        self.wait_var = ctk.DoubleVar(value=cfg.confirm_wait)
        self.skip_delay_var = ctk.DoubleVar(
            value=float(getattr(cfg, "skip_click_delay", 0.1))
        )
        self.grace_var = ctk.DoubleVar(value=cfg.confirm_grace)
        self.scale_var = ctk.BooleanVar(value=cfg.scale_match)
        self.reinforce_var = ctk.BooleanVar(
            value=getattr(cfg, "reinforce_enabled", True)
        )
        self.confirm_text_var = ctk.BooleanVar(
            value=getattr(cfg, "confirm_require_text", True)
        )
        self.reinforce_max_var = ctk.DoubleVar(
            value=float(getattr(cfg, "reinforce_max", 50))
        )
        self.normalize_var = ctk.BooleanVar(value=cfg.normalize_resolution)
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

    def _populate_steps(self) -> None:
        for body in self._step_bodies:
            body.destroy()
        self._step_bodies.clear()

        detect = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self._build_detect(detect)
        self._step_bodies.append(detect)

        res = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self._build_res(res)
        self._step_bodies.append(res)

        hotkey = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self._build_hotkey(hotkey)
        self._step_bodies.append(hotkey)

        lang = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self._build_lang(lang)
        self._step_bodies.append(lang)

    def _step_title(self, parent, index: int) -> None:
        title, hint = STEPS[index]
        ctk.CTkLabel(
            parent,
            text=f"步驟 {index + 1}／{len(STEPS)} · {title}",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=16, weight="bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=8, pady=(8, 2))
        ctk.CTkLabel(
            parent,
            text=hint,
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=12),
            text_color=MUTED,
        ).pack(anchor="w", padx=8, pady=(0, 12))

    def _build_detect(self, parent) -> None:
        self._step_title(parent, 0)
        self._slider(parent, "比對閾值", self.threshold_var, 0.50, 0.99)
        self._slider(parent, "偵測目標 FPS", self.fps_var, 1, 60, fmt_int=True)
        self._slider(
            parent, "偵測 Skip 後點擊前等待（秒）", self.skip_delay_var, 0.0, 1.0
        )
        self._slider(parent, "Skip 後等待確認（秒）", self.wait_var, 0.1, 2.0)
        self._slider(parent, "確認逾時放棄（秒）", self.grace_var, 1.0, 8.0)
        self._slider(
            parent, "強化模板上限", self.reinforce_max_var, 2, 200, fmt_int=True
        )
        self._checkbox(
            parent, "多比例縮放比對（視窗略有縮放時較穩）", self.scale_var
        )
        self._checkbox(
            parent, "成功 Skip→確認 時自動記錄強化模板", self.reinforce_var
        )
        self._checkbox(
            parent, "確認按鈕必須偵測到「確認」文字才點擊", self.confirm_text_var
        )

    def _build_res(self, parent) -> None:
        self._step_title(parent, 1)
        ctk.CTkLabel(
            parent,
            text="請與遊戲視窗設定一致，並在此解析度下擷取模板。",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=12),
            text_color=MUTED,
            wraplength=640,
            justify="left",
        ).pack(anchor="w", padx=8, pady=(0, 10))

        values = [p[0] for p in RESOLUTION_PRESETS] + ["自訂"]
        ctk.CTkOptionMenu(
            parent,
            variable=self.preset_var,
            values=values,
            width=280,
            fg_color="#1c2233",
            button_color="#2a3348",
            button_hover_color="#3a4660",
            command=self._on_preset,
        ).pack(anchor="w", padx=8, pady=4)

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(anchor="w", padx=8, pady=(12, 4))
        ctk.CTkLabel(row, text="寬", text_color=MUTED).pack(side="left")
        ctk.CTkEntry(
            row, textvariable=self.width_var, width=90, fg_color="#1c2233"
        ).pack(side="left", padx=(6, 16))
        ctk.CTkLabel(row, text="高", text_color=MUTED).pack(side="left")
        ctk.CTkEntry(
            row, textvariable=self.height_var, width=90, fg_color="#1c2233"
        ).pack(side="left", padx=(6, 0))

        self._checkbox(
            parent,
            "自動正規化到目標解析度再比對（客戶區略有差異時建議開啟）",
            self.normalize_var,
        )
        ctk.CTkButton(
            parent,
            text="套用 1600 × 900",
            width=160,
            fg_color=ACCENT_DIM,
            hover_color="#226655",
            text_color=ACCENT,
            border_width=1,
            border_color=ACCENT,
            command=lambda: self._set_res(1600, 900),
        ).pack(anchor="w", padx=8, pady=(10, 4))

    def _build_hotkey(self, parent) -> None:
        self._step_title(parent, 2)
        ctk.CTkLabel(
            parent,
            text="點擊固定使用 pydirectinput（螢幕座標 moveTo + click）。",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=12),
            text_color=MUTED,
            wraplength=640,
            justify="left",
        ).pack(anchor="w", padx=8, pady=(0, 12))

        hk = ctk.CTkFrame(parent, fg_color="transparent")
        hk.pack(anchor="w", padx=8, pady=4)
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
        ctk.CTkLabel(
            parent,
            text="例如 f6 / f7（變更熱鍵後需重新啟動程式才會生效）",
            font=ctk.CTkFont(size=11),
            text_color=MUTED,
        ).pack(anchor="w", padx=8, pady=(8, 4))

    def _build_lang(self, parent) -> None:
        self._step_title(parent, 3)
        for lang in LANGS:
            self._checkbox(parent, LANG_LABELS[lang], self.lang_vars[lang])

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
        ).pack(anchor="w", padx=8, pady=(8, 4))

    def _slider(self, parent, title, var, lo, hi, *, fmt_int: bool = False) -> None:
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.pack(fill="x", padx=8, pady=(10, 2))
        top = ctk.CTkFrame(box, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(
            top,
            text=title,
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=12),
            text_color=MUTED,
        ).pack(side="left")

        def _fmt(v: float) -> str:
            return f"{int(round(float(v)))}" if fmt_int else f"{float(v):.2f}"

        val_lbl = ctk.CTkLabel(
            top, text=_fmt(var.get()), font=ctk.CTkFont(size=12), text_color=TEXT
        )
        val_lbl.pack(side="right")

        def on_change(v):
            val_lbl.configure(text=_fmt(float(v)))

        kwargs = {
            "from_": lo,
            "to": hi,
            "variable": var,
            "command": on_change,
            "progress_color": ACCENT,
            "button_color": ACCENT,
            "button_hover_color": "#5eefc4",
            "fg_color": "#1c2233",
        }
        if fmt_int:
            kwargs["number_of_steps"] = max(1, int(hi - lo))
        ctk.CTkSlider(box, **kwargs).pack(fill="x", pady=(4, 0))

    def _show_step(self, index: int) -> None:
        self.step = max(0, min(len(STEPS) - 1, index))
        for i, body in enumerate(self._step_bodies):
            if i == self.step:
                body.pack(fill="both", expand=True, padx=4, pady=4)
            else:
                body.pack_forget()
        for i, btn in enumerate(self._step_btns):
            active = i == self.step
            btn.configure(
                fg_color=ACCENT_DIM if active else "transparent",
                text_color=ACCENT if active else MUTED,
                border_width=1 if active else 0,
                border_color=ACCENT if active else "#2a3348",
            )
        title, hint = STEPS[self.step]
        self.step_hint.configure(text=f"{title}：{hint}")
        self.btn_prev.configure(state="normal" if self.step > 0 else "disabled")
        last = self.step >= len(STEPS) - 1
        self.btn_next.configure(text="完成" if last else "下一步")

    def _prev_step(self) -> None:
        self._show_step(self.step - 1)

    def _next_step(self) -> None:
        if self.step >= len(STEPS) - 1:
            self._apply()
            return
        self._show_step(self.step + 1)

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
        return max(1.0, min(60.0, round(1.0 / max(0.01, float(interval)))))

    @staticmethod
    def _fps_to_interval(fps: float) -> float:
        return 1.0 / max(1.0, min(60.0, float(fps)))

    def _collect(self) -> AppConfig:
        cfg = self.config_data
        cfg.threshold = float(self.threshold_var.get())
        cfg.scan_interval = self._fps_to_interval(self.fps_var.get())
        cfg.confirm_wait = float(self.wait_var.get())
        cfg.skip_click_delay = float(self.skip_delay_var.get())
        cfg.confirm_grace = float(self.grace_var.get())
        cfg.scale_match = bool(self.scale_var.get())
        cfg.reinforce_enabled = bool(self.reinforce_var.get())
        cfg.confirm_require_text = bool(self.confirm_text_var.get())
        cfg.reinforce_max = max(
            0, min(500, int(round(float(self.reinforce_max_var.get()))))
        )
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
        langs = [lang for lang, var in self.lang_vars.items() if var.get()]
        cfg.enabled_langs = langs or list(LANGS)
        return cfg

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
        self.threshold_var.set(defaults.threshold)
        self.fps_var.set(self._interval_to_fps(defaults.scan_interval))
        self.wait_var.set(defaults.confirm_wait)
        self.skip_delay_var.set(float(defaults.skip_click_delay))
        self.grace_var.set(defaults.confirm_grace)
        self.scale_var.set(defaults.scale_match)
        self.reinforce_var.set(defaults.reinforce_enabled)
        self.confirm_text_var.set(defaults.confirm_require_text)
        self.reinforce_max_var.set(float(defaults.reinforce_max))
        self.normalize_var.set(defaults.normalize_resolution)
        self._set_res(defaults.expected_width, defaults.expected_height)
        self.hotkey_start_var.set(defaults.hotkey_start)
        self.hotkey_stop_var.set(defaults.hotkey_stop)
        for lang, var in self.lang_vars.items():
            var.set(lang in defaults.enabled_langs)


# Back-compat alias (no longer a Toplevel popup)
SettingsDialog = SettingsPage
