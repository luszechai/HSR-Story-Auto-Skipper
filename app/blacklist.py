"""Remember false-positive Skip clicks (no Confirm followed) and avoid them."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

from app.config import ROOT
from app.detector import MatchResult

BLACKLIST_DIR = ROOT / "assets" / "blacklist"
BLACKLIST_INDEX = BLACKLIST_DIR / "index.json"

# Normalized center distance below this → treat as same hotspot
CENTER_DIST = 0.045
# Relative size must be similar
SIZE_RATIO_MIN = 0.55
SIZE_RATIO_MAX = 1.8
# Optional visual confirm against saved crop
CROP_MATCH_THRESHOLD = 0.88


@dataclass
class BlacklistEntry:
    id: str
    nx: float
    ny: float
    nw: float
    nh: float
    crop: str = ""
    created_at: float = 0.0
    avoid_count: int = 0

    def center_dist(self, nx: float, ny: float) -> float:
        return ((self.nx - nx) ** 2 + (self.ny - ny) ** 2) ** 0.5


class SkipBlacklist:
    def __init__(self, directory: Path = BLACKLIST_DIR) -> None:
        self.directory = directory
        self.index_path = directory / "index.json"
        self.entries: List[BlacklistEntry] = []
        self._crops: dict[str, np.ndarray] = {}
        self.directory.mkdir(parents=True, exist_ok=True)
        self.load()

    def load(self) -> None:
        self.entries.clear()
        self._crops.clear()
        if not self.index_path.exists():
            self.save()
            return
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except Exception:
            data = []
        for raw in data:
            try:
                entry = BlacklistEntry(
                    id=str(raw["id"]),
                    nx=float(raw["nx"]),
                    ny=float(raw["ny"]),
                    nw=float(raw["nw"]),
                    nh=float(raw["nh"]),
                    crop=str(raw.get("crop", "")),
                    created_at=float(raw.get("created_at", 0)),
                    avoid_count=int(raw.get("avoid_count", 0)),
                )
            except (KeyError, TypeError, ValueError):
                continue
            self.entries.append(entry)
            if entry.crop:
                path = self.directory / entry.crop
                if path.exists():
                    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
                    if img is not None:
                        self._crops[entry.id] = img

    def save(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        payload = [asdict(e) for e in self.entries]
        self.index_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def count(self) -> int:
        return len(self.entries)

    def clear(self) -> None:
        for path in self.directory.glob("fp_*.png"):
            try:
                path.unlink()
            except OSError:
                pass
        self.entries.clear()
        self._crops.clear()
        self.save()

    @staticmethod
    def _norm(match: MatchResult, frame_w: int, frame_h: int) -> tuple[float, float, float, float]:
        fw = max(frame_w, 1)
        fh = max(frame_h, 1)
        cx, cy = match.center
        return cx / fw, cy / fh, match.w / fw, match.h / fh

    def add_false_positive(self, match_frame: np.ndarray, match: MatchResult) -> BlacklistEntry:
        """Record a Skip click that was not followed by a Confirm dialog."""
        fh, fw = match_frame.shape[:2]
        nx, ny, nw, nh = self._norm(match, fw, fh)

        # If already near an entry, just bump avoid_count / refresh crop
        for entry in self.entries:
            if entry.center_dist(nx, ny) <= CENTER_DIST:
                entry.avoid_count += 1
                self._refresh_crop(entry, match_frame, match)
                self.save()
                return entry

        entry_id = uuid.uuid4().hex[:10]
        crop_name = f"fp_{entry_id}.png"
        entry = BlacklistEntry(
            id=entry_id,
            nx=nx,
            ny=ny,
            nw=nw,
            nh=nh,
            crop=crop_name,
            created_at=time.time(),
            avoid_count=0,
        )
        self._refresh_crop(entry, match_frame, match)
        self.entries.append(entry)
        self.save()
        return entry

    def _refresh_crop(
        self, entry: BlacklistEntry, match_frame: np.ndarray, match: MatchResult
    ) -> None:
        fh, fw = match_frame.shape[:2]
        pad = 4
        x0 = max(0, match.x - pad)
        y0 = max(0, match.y - pad)
        x1 = min(fw, match.x + match.w + pad)
        y1 = min(fh, match.y + match.h + pad)
        if x1 - x0 < 4 or y1 - y0 < 4:
            return
        crop = match_frame[y0:y1, x0:x1].copy()
        path = self.directory / (entry.crop or f"fp_{entry.id}.png")
        entry.crop = path.name
        cv2.imwrite(str(path), crop)
        self._crops[entry.id] = crop

    def is_blocked(self, match_frame: np.ndarray, match: MatchResult) -> bool:
        if not match.found or not self.entries:
            return False
        fh, fw = match_frame.shape[:2]
        nx, ny, nw, nh = self._norm(match, fw, fh)

        for entry in self.entries:
            near = entry.center_dist(nx, ny) <= CENTER_DIST
            size_ok = True
            if entry.nw > 0 and entry.nh > 0:
                wr = nw / entry.nw
                hr = nh / entry.nh
                size_ok = (
                    SIZE_RATIO_MIN <= wr <= SIZE_RATIO_MAX
                    and SIZE_RATIO_MIN <= hr <= SIZE_RATIO_MAX
                )
            crop_ok = self._crop_similar(entry, match_frame, match)

            if near and (size_ok or crop_ok):
                entry.avoid_count += 1
                self.save()
                return True
            if not near and crop_ok:
                entry.avoid_count += 1
                self.save()
                return True
        return False

    def _crop_similar(
        self, entry: BlacklistEntry, match_frame: np.ndarray, match: MatchResult
    ) -> bool:
        tmpl = self._crops.get(entry.id)
        if tmpl is None or tmpl.size == 0:
            return False
        fh, fw = match_frame.shape[:2]
        pad = 6
        x0 = max(0, match.x - pad)
        y0 = max(0, match.y - pad)
        x1 = min(fw, match.x + match.w + pad)
        y1 = min(fh, match.y + match.h + pad)
        region = match_frame[y0:y1, x0:x1]
        if region.size == 0:
            return False
        th, tw = tmpl.shape[:2]
        rh, rw = region.shape[:2]
        if rh < th or rw < tw:
            # Resize template down to fit
            scale = min(rh / max(th, 1), rw / max(tw, 1), 1.0)
            if scale < 0.4:
                return False
            tmpl = cv2.resize(
                tmpl,
                (max(8, int(tw * scale)), max(8, int(th * scale))),
                interpolation=cv2.INTER_AREA,
            )
            th, tw = tmpl.shape[:2]
            if rh < th or rw < tw:
                return False
        result = cv2.matchTemplate(region, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        return float(max_val) >= CROP_MATCH_THRESHOLD
