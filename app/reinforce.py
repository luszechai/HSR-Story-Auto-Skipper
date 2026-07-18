"""Record successful Skip→Confirm crops to reinforce template matching."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

from app.config import ROOT
from app.detector import MatchResult

REINFORCE_DIR = ROOT / "assets" / "reinforce"
REINFORCE_INDEX = REINFORCE_DIR / "index.json"


class ReinforceStore:
    """Saves successful button crops used as extra match templates."""

    def __init__(self, directory: Path = REINFORCE_DIR) -> None:
        self.directory = directory
        self.index_path = directory / "index.json"
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / "skip").mkdir(parents=True, exist_ok=True)
        (self.directory / "confirm").mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self._write_index([])

    def _write_index(self, rows: list) -> None:
        self.index_path.write_text(
            json.dumps(rows, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _read_index(self) -> list:
        if not self.index_path.exists():
            return []
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def count(self) -> int:
        """Total reinforce template image files."""
        n = 0
        for button in ("skip", "confirm"):
            d = self.directory / button
            if d.exists():
                n += len(list(d.glob("*.png")))
        return n

    def pair_count(self) -> int:
        return len(self._read_index())

    def clear(self) -> None:
        for button in ("skip", "confirm"):
            d = self.directory / button
            if d.exists():
                for path in d.glob("*.png"):
                    try:
                        path.unlink()
                    except OSError:
                        pass
        self._write_index([])

    @staticmethod
    def _crop(frame: np.ndarray, match: MatchResult, pad: int = 2) -> Optional[np.ndarray]:
        fh, fw = frame.shape[:2]
        x0 = max(0, match.x - pad)
        y0 = max(0, match.y - pad)
        x1 = min(fw, match.x + match.w + pad)
        y1 = min(fh, match.y + match.h + pad)
        if x1 - x0 < 8 or y1 - y0 < 8:
            return None
        return frame[y0:y1, x0:x1].copy()

    def _too_similar(self, button: str, crop: np.ndarray, threshold: float = 0.95) -> bool:
        folder = self.directory / button
        if not folder.exists():
            return False
        th, tw = crop.shape[:2]
        for path in folder.glob("*.png"):
            existing = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if existing is None:
                continue
            eh, ew = existing.shape[:2]
            # Compare at min size
            w = min(tw, ew)
            h = min(th, eh)
            if w < 8 or h < 8:
                continue
            a = cv2.resize(crop, (w, h), interpolation=cv2.INTER_AREA)
            b = cv2.resize(existing, (w, h), interpolation=cv2.INTER_AREA)
            result = cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            if float(max_val) >= threshold:
                return True
        return False

    def try_record(
        self,
        *,
        skip_frame: np.ndarray,
        skip_match: MatchResult,
        confirm_frame: np.ndarray,
        confirm_match: MatchResult,
        max_templates: int,
    ) -> Tuple[bool, str]:
        """Save a successful pair if under the template cap.

        Returns (saved, message).
        """
        max_templates = max(0, int(max_templates))
        current = self.count()
        if current >= max_templates:
            return False, f"強化模板已滿（{current}/{max_templates}）"

        # Need room for 2 images; if only 1 slot left, still allow 1? Prefer pair.
        if current + 2 > max_templates:
            return False, f"強化模板剩餘不足一對（{current}/{max_templates}）"

        skip_crop = self._crop(skip_frame, skip_match)
        confirm_crop = self._crop(confirm_frame, confirm_match)
        if skip_crop is None or confirm_crop is None:
            return False, "裁切失敗，略過記錄"

        if self._too_similar("skip", skip_crop) and self._too_similar(
            "confirm", confirm_crop
        ):
            return False, "與既有強化模板過於相似，略過"

        uid = uuid.uuid4().hex[:10]
        skip_name = f"ok_{uid}_skip.png"
        confirm_name = f"ok_{uid}_confirm.png"
        skip_path = self.directory / "skip" / skip_name
        confirm_path = self.directory / "confirm" / confirm_name
        cv2.imwrite(str(skip_path), skip_crop)
        cv2.imwrite(str(confirm_path), confirm_crop)

        rows = self._read_index()
        rows.append(
            {
                "id": uid,
                "skip": f"skip/{skip_name}",
                "confirm": f"confirm/{confirm_name}",
                "skip_lang": skip_match.lang,
                "confirm_lang": confirm_match.lang,
                "created_at": time.time(),
            }
        )
        self._write_index(rows)
        n = self.count()
        return True, f"已強化記錄（{n}/{max_templates}）"
