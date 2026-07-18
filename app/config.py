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
    """On first launch of the .exe, copy bundled assets/config next to the exe."""
    if not getattr(sys, "frozen", False):
        return
    root = app_root()
    bundled = bundle_root()
    cfg_dst = root / "config.json"
    cfg_src = bundled / "config.json"
    if not cfg_dst.exists() and cfg_src.exists():
        shutil.copy2(cfg_src, cfg_dst)
    for name in ("templates", "brand"):
        src = bundled / "assets" / name
        dst = root / "assets" / name
        if src.exists() and not dst.exists():
            shutil.copytree(src, dst)
    (root / "assets" / "reinforce").mkdir(parents=True, exist_ok=True)
    (root / "assets" / "blacklist").mkdir(parents=True, exist_ok=True)


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
    threshold: float = 0.85
    scan_interval: float = 0.03
    confirm_wait: float = 0.5
    confirm_grace: float = 3.0
    # After Skip is detected, wait before clicking
    skip_click_delay: float = 0.1
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
    # Learn successful Skip→Confirm crops as extra templates
    reinforce_enabled: bool = True
    reinforce_max: int = 50
    # Avoid / record false-positive Skip locations
    blacklist_enabled: bool = True
    # Confirm click requires detecting the word 確認 in the button area
    confirm_require_text: bool = True

    def resolution_label(self) -> str:
        return f"{self.expected_width}×{self.expected_height}"

    def save(self, path: Path = CONFIG_PATH) -> None:
        path.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "AppConfig":
        if not path.exists():
            cfg = cls()
            cfg.save(path)
            return cfg
        data = json.loads(path.read_text(encoding="utf-8"))
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        cfg = cls(**filtered)
        if cfg.click_method not in CLICK_METHODS:
            cfg.click_method = "cursor"
        cfg.expected_width = max(320, int(cfg.expected_width))
        cfg.expected_height = max(240, int(cfg.expected_height))
        cfg.reinforce_max = max(0, min(500, int(cfg.reinforce_max)))
        cfg.skip_click_delay = max(0.0, float(getattr(cfg, "skip_click_delay", 0.1)))
        cfg.scan_interval = max(0.01, float(cfg.scan_interval))
        return cfg
