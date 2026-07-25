"""In-app settings page: tabbed categories with discrete slider steps."""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

import cv2
import customtkinter as ctk
import numpy as np

from app.config import LANGS, RESOLUTION_PRESETS, AppConfig
from app.i18n import LANG_DISPLAY, lang_display, lang_from_display, t
from app.window_capture import capture_client, find_game_window

BG = "#080a10"
PANEL = "#10141e"
TEXT = "#e8ecf4"
MUTED = "#7a8499"
ACCENT = "#3ee0b0"
ACCENT_DIM = "#1a4a3c"
BLUE = "#1f6feb"


class SettingsPage(ctk.CTkFrame):
    """Embedded settings view (same window, tabbed by category)."""

    _TAB_KEYS = (
        "settings.detect",
        "settings.skip_fixed_section",
        "settings.resolution",
        "settings.hotkeys",
        "settings.language",
    )

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
        self._ui_lang = config.ui_lang
        self.tabview: Optional[ctk.CTkTabview] = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_footer()
        self._init_vars()
        self._build_tabs()

    def _tt(self, key: str, **kwargs) -> str:
        return t(key, lang=self._ui_lang, **kwargs)

    def set_ui_lang(self, lang: str) -> None:
        """Rebuild visible strings when the app UI language changes."""
        if lang == self._ui_lang:
            return
        self._ui_lang = lang
        self.title_label.configure(text=self._tt("settings.title"))
        self.subtitle_label.configure(text=self._tt("settings.subtitle"))
        self.btn_back.configure(text=self._tt("settings.back"))
        self.btn_reset.configure(text=self._tt("settings.reset"))
        self.btn_apply.configure(text=self._tt("settings.apply"))
        self._build_tabs()
        self.load_from_config(self.config_data)

    def load_from_config(self, config: AppConfig) -> None:
        self.config_data = config
        self.threshold_var.set(self._snap(config.threshold, 0.50, 0.99, 0.01))
        self.fps_var.set(self._snap(self._interval_to_fps(config.scan_interval), 1, 30, 1))
        self.wait_var.set(self._snap(config.confirm_wait, 0.0, 2.0, 0.1))
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
        self.ui_lang_var.set(lang_display(getattr(config, "ui_lang", "zh_tw")))
        self.game_lang_var.set(lang_display(getattr(config, "game_lang", "zh_tw")))

    def _build_header(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 6))
        self.title_label = ctk.CTkLabel(
            head,
            text=self._tt("settings.title"),
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=22, weight="bold"),
            text_color=TEXT,
        )
        self.title_label.pack(side="left")
        self.subtitle_label = ctk.CTkLabel(
            head,
            text=self._tt("settings.subtitle"),
            font=ctk.CTkFont(family="Microsoft JhengHei UI", size=12),
            text_color=MUTED,
        )
        self.subtitle_label.pack(side="left", padx=(14, 0))

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=18, pady=(8, 16))
        self.btn_back = ctk.CTkButton(
            footer,
            text=self._tt("settings.back"),
            width=110,
            height=36,
            fg_color="#2a3348",
            hover_color="#3a4660",
            command=self._back,
        )
        self.btn_back.pack(side="left")
        self.btn_reset = ctk.CTkButton(
            footer,
            text=self._tt("settings.reset"),
            width=110,
            height=36,
            fg_color="#2a3348",
            hover_color="#3a4660",
            command=self._reset_defaults,
        )
        self.btn_reset.pack(side="left", padx=(8, 0))
        self.btn_apply = ctk.CTkButton(
            footer,
            text=self._tt("settings.apply"),
            width=120,
            height=36,
            fg_color=ACCENT_DIM,
            hover_color="#226655",
            text_color=ACCENT,
            border_width=1,
            border_color=ACCENT,
            command=self._apply,
        )
        self.btn_apply.pack(side="right")

    def _init_vars(self) -> None:
        cfg = self.config_data
        self.threshold_var = ctk.DoubleVar(
            value=self._snap(cfg.threshold, 0.50, 0.99, 0.01)
        )
        self.fps_var = ctk.DoubleVar(
            value=self._snap(self._interval_to_fps(cfg.scan_interval), 1, 30, 1)
        )
        self.wait_var = ctk.DoubleVar(value=self._snap(cfg.confirm_wait, 0.0, 2.0, 0.1))
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
        self.preset_var = ctk.StringVar(
            value=self._preset_label_for(cfg.expected_width, cfg.expected_height)
        )
        self.hotkey_start_var = ctk.StringVar(value=cfg.hotkey_start)
        self.hotkey_stop_var = ctk.StringVar(value=cfg.hotkey_stop)
        self.ui_lang_var = ctk.StringVar(
            value=lang_display(getattr(cfg, "ui_lang", "zh_tw"))
        )
        self.game_lang_var = ctk.StringVar(
            value=lang_display(getattr(cfg, "game_lang", "zh_tw"))
        )

    def _tab_body(self, parent, hint: str = "") -> ctk.CTkFrame:
        """Content panel inside a tab (title already shown on the tab bar)."""
        box = ctk.CTkFrame(parent, fg_color="#0e121a", corner_radius=12)
        box.pack(fill="both", expand=True, padx=4, pady=4)
        if hint:
            ctk.CTkLabel(
                box,
                text=hint,
                font=ctk.CTkFont(family="Microsoft JhengHei UI", size=11),
                text_color=MUTED,
            ).pack(anchor="w", padx=14, pady=(12, 6))
        return box

    def _lang_values(self) -> List[str]:
        return [LANG_DISPLAY[code] for code in LANGS]

    def _format_preset_label(self, base: str, recommended: bool) -> str:
        if recommended:
            return self._tt("settings.preset_recommended", size=base)
        return base

    def _preset_choices(self) -> List[str]:
        return [
            self._format_preset_label(base, recommended)
            for base, _w, _h, recommended in RESOLUTION_PRESETS
        ] + [self._tt("settings.preset_custom")]

    def _preset_label_for(self, width: int, height: int) -> str:
        for base, w, h, recommended in RESOLUTION_PRESETS:
            if w == width and h == height:
                return self._format_preset_label(base, recommended)
        return self._tt("settings.preset_custom")

    def _make_tab_scroll(self, title: str) -> ctk.CTkScrollableFrame:
        assert self.tabview is not None
        tab = self.tabview.add(title)
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        scroll = ctk.CTkScrollableFrame(
            tab,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color="#2a3348",
            scrollbar_button_hover_color="#3a4660",
        )
        scroll.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        scroll.grid_columnconfigure(0, weight=1)
        return scroll

    def _build_tabs(self) -> None:
        # Keep the same category after rebuild (e.g. UI language change).
        tab_index = 0
        if self.tabview is not None:
            try:
                current = self.tabview.get()
                prev_titles = getattr(self, "_tab_titles", [])
                if current in prev_titles:
                    tab_index = prev_titles.index(current)
            except (ValueError, RuntimeError):
                tab_index = 0
            self.tabview.destroy()
            self.tabview = None

        self.tabview = ctk.CTkTabview(
            self,
            fg_color=BG,
            corner_radius=12,
            border_width=0,
            segmented_button_fg_color="#1c2233",
            segmented_button_selected_color=ACCENT_DIM,
            segmented_button_selected_hover_color="#226655",
            segmented_button_unselected_color="#1c2233",
            segmented_button_unselected_hover_color="#2a3348",
            text_color=TEXT,
        )
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=18, pady=4)

        self._tab_titles = [self._tt(key) for key in self._TAB_KEYS]
        detect_scroll = self._make_tab_scroll(self._tab_titles[0])
        fixed_scroll = self._make_tab_scroll(self._tab_titles[1])
        res_scroll = self._make_tab_scroll(self._tab_titles[2])
        hotkey_scroll = self._make_tab_scroll(self._tab_titles[3])
        lang_scroll = self._make_tab_scroll(self._tab_titles[4])

        self._build_detect_tab(detect_scroll)
        self._build_skip_fixed_tab(fixed_scroll)
        self._build_resolution_tab(res_scroll)
        self._build_hotkeys_tab(hotkey_scroll)
        self._build_language_tab(lang_scroll)

        tab_index = max(0, min(tab_index, len(self._tab_titles) - 1))
        self.tabview.set(self._tab_titles[tab_index])

    def _build_detect_tab(self, parent) -> None:
        detect = self._tab_body(parent, self._tt("settings.detect_hint"))
        self._slider(
            detect, self._tt("settings.threshold"), self.threshold_var, 0.50, 0.99, step=0.01
        )
        self._slider(
            detect, self._tt("settings.fps"), self.fps_var, 1, 30, step=1, fmt_int=True
        )
        self._slider(
            detect,
            self._tt("settings.skip_delay"),
            self.skip_delay_var,
            0.0,
            1.0,
            step=0.1,
        )
        self._slider(
            detect, self._tt("settings.confirm_wait"), self.wait_var, 0.0, 2.0, step=0.1
        )
        self._slider(
            detect, self._tt("settings.confirm_grace"), self.grace_var, 1.0, 8.0, step=0.5
        )
        self._checkbox(detect, self._tt("settings.scale_match"), self.scale_var)
        self._checkbox(
            detect,
            self._tt("settings.confirm_text"),
            self.confirm_text_var,
        )

    def _build_skip_fixed_tab(self, parent) -> None:
        fixed = self._tab_body(parent, self._tt("settings.skip_fixed_hint"))
        self._checkbox(fixed, self._tt("settings.skip_fixed"), self.skip_fixed_var)
        self._checkbox(
            fixed,
            self._tt("settings.skip_presence"),
            self.skip_presence_var,
        )
        row_f = ctk.CTkFrame(fixed, fg_color="transparent")
        row_f.pack(anchor="w", padx=14, pady=(4, 4))
        self.lbl_rel_x = ctk.CTkLabel(
            row_f, text=self._tt("settings.rel_x"), text_color=MUTED
        )
        self.lbl_rel_x.pack(side="left")
        ctk.CTkEntry(
            row_f, textvariable=self.skip_rel_x_var, width=90, fg_color="#1c2233"
        ).pack(side="left", padx=(6, 16))
        self.lbl_rel_y = ctk.CTkLabel(
            row_f, text=self._tt("settings.rel_y"), text_color=MUTED
        )
        self.lbl_rel_y.pack(side="left")
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
        self.btn_locate = ctk.CTkButton(
            fixed,
            text=self._tt("settings.locate_skip"),
            width=220,
            fg_color=ACCENT_DIM,
            hover_color="#226655",
            text_color=ACCENT,
            border_width=1,
            border_color=ACCENT,
            command=self._locate_skip,
        )
        self.btn_locate.pack(anchor="w", padx=14, pady=(4, 12))

    def _build_resolution_tab(self, parent) -> None:
        res = self._tab_body(parent, self._tt("settings.resolution_hint"))
        self.preset_menu = ctk.CTkOptionMenu(
            res,
            variable=self.preset_var,
            values=self._preset_choices(),
            width=280,
            fg_color="#1c2233",
            button_color="#2a3348",
            button_hover_color="#3a4660",
            command=self._on_preset,
        )
        self.preset_menu.pack(anchor="w", padx=14, pady=4)
        row = ctk.CTkFrame(res, fg_color="transparent")
        row.pack(anchor="w", padx=14, pady=(12, 4))
        self.lbl_width = ctk.CTkLabel(
            row, text=self._tt("settings.width"), text_color=MUTED
        )
        self.lbl_width.pack(side="left")
        ctk.CTkEntry(
            row, textvariable=self.width_var, width=90, fg_color="#1c2233"
        ).pack(side="left", padx=(6, 16))
        self.lbl_height = ctk.CTkLabel(
            row, text=self._tt("settings.height"), text_color=MUTED
        )
        self.lbl_height.pack(side="left")
        ctk.CTkEntry(
            row, textvariable=self.height_var, width=90, fg_color="#1c2233"
        ).pack(side="left", padx=(6, 0))
        self._checkbox(
            res,
            self._tt("settings.normalize"),
            self.normalize_var,
        )
        self.btn_res_1600 = ctk.CTkButton(
            res,
            text=self._tt("settings.apply_1600"),
            width=160,
            fg_color=ACCENT_DIM,
            hover_color="#226655",
            text_color=ACCENT,
            border_width=1,
            border_color=ACCENT,
            command=lambda: self._set_res(1600, 900),
        )
        self.btn_res_1600.pack(anchor="w", padx=14, pady=(10, 12))

    def _build_hotkeys_tab(self, parent) -> None:
        hotkey = self._tab_body(parent, self._tt("settings.hotkeys_hint"))
        hk = ctk.CTkFrame(hotkey, fg_color="transparent")
        hk.pack(anchor="w", padx=14, pady=(4, 12))
        self.lbl_hk_start = ctk.CTkLabel(
            hk, text=self._tt("settings.hotkey_start"), text_color=MUTED, width=40
        )
        self.lbl_hk_start.grid(row=0, column=0, padx=(0, 6))
        ctk.CTkEntry(
            hk, textvariable=self.hotkey_start_var, width=80, fg_color="#1c2233"
        ).grid(row=0, column=1, padx=(0, 16))
        self.lbl_hk_stop = ctk.CTkLabel(
            hk, text=self._tt("settings.hotkey_stop"), text_color=MUTED, width=40
        )
        self.lbl_hk_stop.grid(row=0, column=2, padx=(0, 6))
        ctk.CTkEntry(
            hk, textvariable=self.hotkey_stop_var, width=80, fg_color="#1c2233"
        ).grid(row=0, column=3)

    def _build_language_tab(self, parent) -> None:
        lang = self._tab_body(parent, self._tt("settings.language_hint"))
        lang_values = self._lang_values()
        ui_row = ctk.CTkFrame(lang, fg_color="transparent")
        ui_row.pack(fill="x", padx=14, pady=(8, 4))
        ctk.CTkLabel(
            ui_row,
            text=self._tt("settings.ui_lang"),
            text_color=MUTED,
            width=180,
            anchor="w",
        ).pack(side="left")
        self.ui_lang_menu = ctk.CTkOptionMenu(
            ui_row,
            variable=self.ui_lang_var,
            values=lang_values,
            width=160,
            fg_color="#1c2233",
            button_color="#2a3348",
            button_hover_color="#3a4660",
        )
        self.ui_lang_menu.pack(side="left", padx=(8, 0))

        game_row = ctk.CTkFrame(lang, fg_color="transparent")
        game_row.pack(fill="x", padx=14, pady=(8, 12))
        ctk.CTkLabel(
            game_row,
            text=self._tt("settings.game_lang"),
            text_color=MUTED,
            width=180,
            anchor="w",
        ).pack(side="left")
        self.game_lang_menu = ctk.CTkOptionMenu(
            game_row,
            variable=self.game_lang_var,
            values=lang_values,
            width=160,
            fg_color="#1c2233",
            button_color="#2a3348",
            button_hover_color="#3a4660",
        )
        self.game_lang_menu.pack(side="left", padx=(8, 0))

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
            text=f"{title}{self._tt('settings.step_suffix', step=step_txt)}",
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
        for base, w, h, recommended in RESOLUTION_PRESETS:
            if self._format_preset_label(base, recommended) == choice:
                self._set_res(w, h)
                return

    def _set_res(self, w: int, h: int) -> None:
        self.width_var.set(str(w))
        self.height_var.set(str(h))
        self.preset_var.set(self._preset_label_for(w, h))

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
        cfg.ui_lang = lang_from_display(self.ui_lang_var.get(), cfg.ui_lang)
        cfg.game_lang = lang_from_display(self.game_lang_var.get(), cfg.game_lang)
        return cfg

    def _fixed_coord_hint(self) -> str:
        try:
            rx = float(self.skip_rel_x_var.get())
            ry = float(self.skip_rel_y_var.get())
            w = int(self.width_var.get() or 1600)
            h = int(self.height_var.get() or 900)
            return self._tt(
                "settings.fixed_coord_hint",
                x=int(round(w * rx)),
                y=int(round(h * ry)),
                w=w,
                h=h,
            )
        except ValueError:
            return self._tt("settings.fixed_coord_invalid")

    def _locate_skip(self) -> None:
        """Capture game client and set Skip to the left icon of the top-right bar."""
        info = find_game_window(self.config_data.window_keywords)
        if info is None:
            self.skip_fixed_hint.configure(
                text=self._tt("settings.locate_no_window"), text_color="#f85149"
            )
            return
        try:
            frame = capture_client(info).frame
        except Exception as exc:
            self.skip_fixed_hint.configure(
                text=self._tt("settings.locate_capture_fail", exc=exc),
                text_color="#f85149",
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
        cands: List[Tuple[int, float, float]] = []
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
                text=self._tt("settings.locate_fallback"),
                text_color="#f0883e",
            )
            return
        cands.sort(key=lambda item: item[0])
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
            text=self._tt(
                "settings.locate_ok",
                cx=cx,
                cy=cy,
                fw=fw,
                fh=fh,
                rx=rx,
                ry=ry,
            ),
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
        self.wait_var.set(self._snap(defaults.confirm_wait, 0.0, 2.0, 0.1))
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
        self.ui_lang_var.set(lang_display(defaults.ui_lang))
        self.game_lang_var.set(lang_display(defaults.game_lang))
        self.skip_fixed_hint.configure(text=self._fixed_coord_hint(), text_color=MUTED)


SettingsDialog = SettingsPage
