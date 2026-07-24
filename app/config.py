"""Persistent application settings."""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Tuple


def app_root() -> Path:
    """Writable project / install folder (next to .exe when frozen)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bundle_root() -> Path:
    """Read-only PyInstaller extract dir (or project root in dev)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", app_root()))
    return app_root()


def bootstrap_runtime_files() -> None:
    """On first launch of the .exe, copy bundled assets next to the executable."""
    if not getattr(sys, "frozen", False):
        return
    root = app_root()
    bundled = bundle_root()
    for name in ("templates", "brand"):
        src = bundled / "assets" / name
        dst = root / "assets" / name
        if src.exists() and not dst.exists():
            shutil.copytree(src, dst)


ROOT = app_root()
CONFIG_PATH = ROOT / "config.json"
TEMPLATES_DIR = ROOT / "assets" / "templates"

LANGS = ("zh_tw", "zh_cn", "en", "jp")
WINDOW_TITLE_KEYWORDS = (
    "崩壞：星穹鐵道",
    "崩坏：星穹铁道",
    "Honkai: Star Rail",
    "Honkai Star Rail",
)

# Common windowed presets: (label, width, height)
RESOLUTION_PRESETS: Tuple[Tuple[str, int, int], ...] = (
    ("1600 × 900（推薦）", 1600, 900),
    ("1920 × 1080", 1920, 1080),
    ("1280 × 720", 1280, 720),
    ("1366 × 768", 1366, 768),
)

CLICK_METHODS = ("cursor",)


@dataclass
class AppConfig:
    threshold: float = 0.90
    scan_interval: float = 1.0 / 30.0  # target ~30 FPS
    confirm_wait: float = 0.1
    confirm_grace: float = 3.0
    # After Skip is detected, wait before clicking
    skip_click_delay: float = 0.3
    enabled_langs: List[str] = field(default_factory=lambda: list(LANGS))
    hotkey_start: str = "f6"
    hotkey_stop: str = "f7"
    window_keywords: List[str] = field(
        default_factory=lambda: list(WINDOW_TITLE_KEYWORDS)
    )
    scale_match: bool = True
    # Target client resolution (templates should be captured at this size)
    expected_width: int = 1600
    expected_height: int = 900
    # Scale capture to expected size before matching, then map clicks back
    normalize_resolution: bool = True
    # Always pydirectinput screen move+click
    click_method: str = "cursor"
    # Confirm click requires detecting the word 確認 in the button area
    confirm_require_text: bool = True
    # Skip: click a fixed client-relative point (stable across scene BG changes)
    skip_fixed: bool = True
    # When True, fixed coords still need a Skip-glyph presence score >= threshold
    skip_fixed_require_presence: bool = True
    # Center of Skip icon as fraction of client width/height (measured @ 1600×900)
    skip_rel_x: float = 0.82125
    skip_rel_y: float = 0.055556
    # Hit box size as fraction of client size (for preview / presence probe)
    skip_box_w: float = 0.04
    skip_box_h: float = 0.045
    # Require stable Skip detections before moving the cursor.
    skip_consensus_required: int = 2
    skip_consensus_window: int = 3
    # Verify that Skip disappears after clicking; otherwise delay retries.
    skip_disappear_frames: int = 2
    skip_verified_cooldown: float = 0.75
    skip_retry_cooldown: float = 2.0
    confirm_disappear_frames: int = 2
    confirm_retry_delay: float = 0.5
    confirm_max_click_attempts: int = 3

    def resolution_label(self) -> str:
        return f"{self.expected_width}×{self.expected_height}"

    def save(self, path: Path = CONFIG_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(f"{path.suffix}.tmp")
        temp_path.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temp_path.replace(path)

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "AppConfig":
        if not path.exists():
            cfg = cls()
            cfg.save(path)
            return cfg
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return cls()
        if not isinstance(data, dict):
            return cls()
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        try:
            cfg = cls(**filtered)
        except (TypeError, ValueError):
            return cls()
        if cfg.click_method not in CLICK_METHODS:
            cfg.click_method = "cursor"
        try:
            cfg.threshold = min(0.99, max(0.5, float(cfg.threshold)))
            cfg.expected_width = max(320, int(cfg.expected_width))
            cfg.expected_height = max(240, int(cfg.expected_height))
            cfg.skip_click_delay = max(
                0.0, float(getattr(cfg, "skip_click_delay", 0.3))
            )
            cfg.confirm_wait = max(0.0, float(cfg.confirm_wait))
            cfg.confirm_grace = max(0.0, float(cfg.confirm_grace))
            cfg.scan_interval = max(0.01, float(cfg.scan_interval))
            cfg.skip_rel_x = float(
                min(0.99, max(0.01, getattr(cfg, "skip_rel_x", 0.82125)))
            )
            cfg.skip_rel_y = float(
                min(0.99, max(0.01, getattr(cfg, "skip_rel_y", 0.055556)))
            )
            cfg.skip_box_w = float(
                min(0.2, max(0.01, getattr(cfg, "skip_box_w", 0.04)))
            )
            cfg.skip_box_h = float(
                min(0.2, max(0.01, getattr(cfg, "skip_box_h", 0.045)))
            )
            cfg.skip_consensus_window = min(
                8, max(1, int(getattr(cfg, "skip_consensus_window", 3)))
            )
            cfg.skip_consensus_required = min(
                cfg.skip_consensus_window,
                max(1, int(getattr(cfg, "skip_consensus_required", 2))),
            )
            cfg.skip_disappear_frames = min(
                8, max(1, int(getattr(cfg, "skip_disappear_frames", 2)))
            )
            cfg.skip_verified_cooldown = min(
                10.0,
                max(0.0, float(getattr(cfg, "skip_verified_cooldown", 0.75))),
            )
            cfg.skip_retry_cooldown = min(
                30.0,
                max(0.0, float(getattr(cfg, "skip_retry_cooldown", 2.0))),
            )
            cfg.confirm_disappear_frames = min(
                8, max(1, int(getattr(cfg, "confirm_disappear_frames", 2)))
            )
            cfg.confirm_retry_delay = min(
                5.0,
                max(0.1, float(getattr(cfg, "confirm_retry_delay", 0.5))),
            )
            cfg.confirm_max_click_attempts = min(
                5, max(1, int(getattr(cfg, "confirm_max_click_attempts", 3)))
            )
        except (TypeError, ValueError):
            return cls()
        defaults = cls()
        for field_name in (
            "scale_match",
            "normalize_resolution",
            "confirm_require_text",
            "skip_fixed",
            "skip_fixed_require_presence",
        ):
            if not isinstance(getattr(cfg, field_name), bool):
                setattr(cfg, field_name, getattr(defaults, field_name))
        enabled_langs = cfg.enabled_langs if isinstance(cfg.enabled_langs, list) else []
        cfg.enabled_langs = [
            lang for lang in enabled_langs if isinstance(lang, str) and lang in LANGS
        ] or list(LANGS)
        window_keywords = (
            cfg.window_keywords if isinstance(cfg.window_keywords, list) else []
        )
        cfg.window_keywords = [
            keyword
            for keyword in window_keywords
            if isinstance(keyword, str) and keyword.strip()
        ] or list(WINDOW_TITLE_KEYWORDS)
        return cfg
