"""Settings dialog for detection, resolution, click method, languages."""

from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from app.config import (
    LANGS,
    RESOLUTION_PRESETS,
    AppConfig,
)

BG = "#0c0e14"
PANEL = "#141824"
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


class SettingsDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        config: AppConfig,
        on_apply: Optional[Callable[[AppConfig], None]] = None,
    ) -> None:
        super().__init__(master)
        self.title("設定")
        self.geometry("520x640")
        self.minsize(480, 560)
        self.configure(fg_color=BG)
        self.config_data = config
        self.on_apply = on_apply

        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(
            self,
            text="設定",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=20, weight="bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=22, pady=(18, 4))
        ctk.CTkLabel(
            self,
            text="變更會立即套用並寫入 config.json",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=11),
            text_color=MUTED,
        ).pack(anchor="w", padx=22, pady=(0, 8))

        self.tab = ctk.CTkTabview(
            self,
            fg_color=PANEL,
            segmented_button_fg_color="#1c2233",
            segmented_button_selected_color=ACCENT_DIM,
            segmented_button_selected_hover_color="#226655",
            segmented_button_unselected_color="#1c2233",
            segmented_button_unselected_hover_color="#2a3348",
            text_color=TEXT,
        )
        self.tab.pack(fill="both", expand=True, padx=18, pady=8)
        self.tab.add("偵測")
        self.tab.add("解析度")
        self.tab.add("熱鍵")
        self.tab.add("語系")

        self._build_detect_tab(self.tab.tab("偵測"))
        self._build_res_tab(self.tab.tab("解析度"))
        self._build_hotkey_tab(self.tab.tab("熱鍵"))
        self._build_lang_tab(self.tab.tab("語系"))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=18, pady=(4, 16))
        ctk.CTkButton(
            footer,
            text="重設為預設",
            width=120,
            fg_color="#2a3348",
            hover_color="#3a4660",
            command=self._reset_defaults,
        ).pack(side="left")
        ctk.CTkButton(
            footer,
            text="關閉",
            width=90,
            fg_color="#2a3348",
            hover_color="#3a4660",
            command=self.destroy,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            footer,
            text="套用並儲存",
            width=120,
            fg_color=BLUE,
            hover_color="#388bfd",
            command=self._apply,
        ).pack(side="right")

    # ── Tabs ────────────────────────────────────────────────
    def _build_detect_tab(self, parent) -> None:
        self.threshold_var = ctk.DoubleVar(value=self.config_data.threshold)
        self.interval_var = ctk.DoubleVar(value=self.config_data.scan_interval)
        self.wait_var = ctk.DoubleVar(value=self.config_data.confirm_wait)
        self.skip_delay_var = ctk.DoubleVar(
            value=float(getattr(self.config_data, "skip_click_delay", 0.1))
        )
        self.grace_var = ctk.DoubleVar(value=self.config_data.confirm_grace)
        self.scale_var = ctk.BooleanVar(value=self.config_data.scale_match)
        self.reinforce_var = ctk.BooleanVar(
            value=getattr(self.config_data, "reinforce_enabled", True)
        )
        self.confirm_text_var = ctk.BooleanVar(
            value=getattr(self.config_data, "confirm_require_text", True)
        )
        self.reinforce_max_var = ctk.DoubleVar(
            value=float(getattr(self.config_data, "reinforce_max", 50))
        )

        self._slider(parent, "比對閾值", self.threshold_var, 0.50, 0.99)
        self._slider(parent, "掃描間隔（秒）", self.interval_var, 0.01, 1.0)
        self._slider(
            parent, "偵測 Skip 後點擊前等待（秒）", self.skip_delay_var, 0.0, 1.0
        )
        self._slider(parent, "Skip 後等待確認（秒）", self.wait_var, 0.1, 2.0)
        self._slider(parent, "確認逾時放棄（秒）", self.grace_var, 1.0, 8.0)
        self._slider(
            parent, "強化模板上限", self.reinforce_max_var, 2, 200, fmt_int=True
        )

        ctk.CTkCheckBox(
            parent,
            text="多比例縮放比對（視窗略有縮放時較穩）",
            variable=self.scale_var,
            text_color=TEXT,
            fg_color=ACCENT_DIM,
            hover_color="#226655",
            checkmark_color=ACCENT,
            border_color="#3a4660",
        ).pack(anchor="w", padx=14, pady=(16, 8))

        ctk.CTkCheckBox(
            parent,
            text="成功 Skip→確認 時自動記錄強化模板",
            variable=self.reinforce_var,
            text_color=TEXT,
            fg_color=ACCENT_DIM,
            hover_color="#226655",
            checkmark_color=ACCENT,
            border_color="#3a4660",
        ).pack(anchor="w", padx=14, pady=(4, 8))

        ctk.CTkCheckBox(
            parent,
            text="確認按鈕必須偵測到「確認」文字才點擊",
            variable=self.confirm_text_var,
            text_color=TEXT,
            fg_color=ACCENT_DIM,
            hover_color="#226655",
            checkmark_color=ACCENT,
            border_color="#3a4660",
        ).pack(anchor="w", padx=14, pady=(4, 8))

    def _build_res_tab(self, parent) -> None:
        ctk.CTkLabel(
            parent,
            text="目標客戶區解析度",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=13, weight="bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(
            parent,
            text="請與遊戲視窗設定一致，並在此解析度下擷取模板。",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=11),
            text_color=MUTED,
            wraplength=440,
            justify="left",
        ).pack(anchor="w", padx=14, pady=(0, 10))

        preset_labels = [p[0] for p in RESOLUTION_PRESETS]
        current = f"{self.config_data.expected_width} × {self.config_data.expected_height}"
        matched = next(
            (
                p[0]
                for p in RESOLUTION_PRESETS
                if p[1] == self.config_data.expected_width
                and p[2] == self.config_data.expected_height
            ),
            None,
        )
        self.preset_var = ctk.StringVar(value=matched or "自訂")
        values = preset_labels + ["自訂"]
        ctk.CTkOptionMenu(
            parent,
            variable=self.preset_var,
            values=values,
            width=280,
            fg_color="#1c2233",
            button_color="#2a3348",
            button_hover_color="#3a4660",
            command=self._on_preset,
        ).pack(anchor="w", padx=14, pady=4)

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(anchor="w", padx=14, pady=(12, 4))
        self.width_var = ctk.StringVar(value=str(self.config_data.expected_width))
        self.height_var = ctk.StringVar(value=str(self.config_data.expected_height))
        ctk.CTkLabel(row, text="寬", text_color=MUTED).pack(side="left")
        ctk.CTkEntry(
            row, textvariable=self.width_var, width=90, fg_color="#1c2233"
        ).pack(side="left", padx=(6, 16))
        ctk.CTkLabel(row, text="高", text_color=MUTED).pack(side="left")
        ctk.CTkEntry(
            row, textvariable=self.height_var, width=90, fg_color="#1c2233"
        ).pack(side="left", padx=(6, 0))

        self.normalize_var = ctk.BooleanVar(
            value=self.config_data.normalize_resolution
        )
        ctk.CTkCheckBox(
            parent,
            text="自動正規化到目標解析度再比對（客戶區略有差異時建議開啟）",
            variable=self.normalize_var,
            text_color=TEXT,
            fg_color=ACCENT_DIM,
            hover_color="#226655",
            checkmark_color=ACCENT,
            border_color="#3a4660",
        ).pack(anchor="w", padx=14, pady=(16, 8))

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
        ).pack(anchor="w", padx=14, pady=(8, 4))

        # silence unused
        _ = current

    def _build_hotkey_tab(self, parent) -> None:
        ctk.CTkLabel(
            parent,
            text="熱鍵",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=13, weight="bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(
            parent,
            text="點擊固定使用 pydirectinput（螢幕座標 moveTo + click）。",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=11),
            text_color=MUTED,
            wraplength=440,
            justify="left",
        ).pack(anchor="w", padx=14, pady=(0, 12))

        hk = ctk.CTkFrame(parent, fg_color="transparent")
        hk.pack(anchor="w", padx=14, pady=4)
        self.hotkey_start_var = ctk.StringVar(value=self.config_data.hotkey_start)
        self.hotkey_stop_var = ctk.StringVar(value=self.config_data.hotkey_stop)
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
            text="例如 f6 / f7（需重新啟動程式後熱鍵才會更新）",
            font=ctk.CTkFont(size=11),
            text_color=MUTED,
        ).pack(anchor="w", padx=14, pady=(6, 4))

    def _build_lang_tab(self, parent) -> None:
        ctk.CTkLabel(
            parent,
            text="同時比對的語系模板",
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=13, weight="bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=14, pady=(12, 8))

        self.lang_vars = {}
        for lang in LANGS:
            var = ctk.BooleanVar(value=lang in self.config_data.enabled_langs)
            self.lang_vars[lang] = var
            ctk.CTkCheckBox(
                parent,
                text=LANG_LABELS[lang],
                variable=var,
                text_color=TEXT,
                fg_color=ACCENT_DIM,
                hover_color="#226655",
                checkmark_color=ACCENT,
                border_color="#3a4660",
            ).pack(anchor="w", padx=14, pady=6)

    # ── Helpers ─────────────────────────────────────────────
    def _slider(self, parent, title, var, lo, hi, *, fmt_int: bool = False) -> None:
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.pack(fill="x", padx=14, pady=(10, 2))
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
            top,
            text=_fmt(var.get()),
            font=ctk.CTkFont(size=12),
            text_color=TEXT,
        )
        val_lbl.pack(side="right")

        def on_change(v):
            val_lbl.configure(text=_fmt(float(v)))

        slider_kwargs = {
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
            slider_kwargs["number_of_steps"] = max(1, int(hi - lo))
        ctk.CTkSlider(box, **slider_kwargs).pack(fill="x", pady=(4, 0))

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

    def _collect(self) -> AppConfig:
        cfg = self.config_data
        cfg.threshold = float(self.threshold_var.get())
        cfg.scan_interval = float(self.interval_var.get())
        cfg.confirm_wait = float(self.wait_var.get())
        cfg.skip_click_delay = float(self.skip_delay_var.get())
        cfg.confirm_grace = float(self.grace_var.get())
        cfg.scale_match = bool(self.scale_var.get())
        cfg.reinforce_enabled = bool(self.reinforce_var.get())
        cfg.confirm_require_text = bool(self.confirm_text_var.get())
        cfg.reinforce_max = max(0, min(500, int(round(float(self.reinforce_max_var.get())))))
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
        self.destroy()

    def _reset_defaults(self) -> None:
        defaults = AppConfig()
        self.threshold_var.set(defaults.threshold)
        self.interval_var.set(defaults.scan_interval)
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
            var.set(True)
