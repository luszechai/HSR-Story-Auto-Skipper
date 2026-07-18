"""Multi-language OpenCV template matching."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from app.config import LANGS, ROOT, TEMPLATES_DIR

REINFORCE_DIR = ROOT / "assets" / "reinforce"
CONFIRM_TEXT_DIR = TEMPLATES_DIR / "confirm_text"


@dataclass
class MatchResult:
    found: bool
    score: float
    x: int
    y: int
    w: int
    h: int
    lang: str
    template_name: str
    button: str  # "skip" | "confirm"

    @property
    def center(self) -> Tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2


@dataclass
class TemplateEntry:
    button: str
    lang: str
    path: Path
    image: np.ndarray  # BGR
    gray: np.ndarray  # grayscale for fast matching


class TemplateDetector:
    """Fast template matcher inspired by single-template mss loops.

    Matching many reinforce crops was dropping preview to ~2 FPS. We only
    compare a small active set each frame (like the reference's one template).
    """

    # Cap active templates per button — reference script uses 1
    MAX_MANUAL = 2
    MAX_LEARNED = 2

    def __init__(self, templates_dir: Path = TEMPLATES_DIR) -> None:
        self.templates_dir = templates_dir
        self.templates: List[TemplateEntry] = []
        self.confirm_text_templates: List[np.ndarray] = []
        self.reload()

    def reload(self, enabled_langs: Optional[Sequence[str]] = None) -> int:
        langs = set(enabled_langs or LANGS)
        self.templates.clear()
        self._load_tree(self.templates_dir, langs, learned=False)
        self._load_reinforce(langs)
        self._load_confirm_text()
        return len(self.templates)

    def _load_confirm_text(self) -> None:
        """Glyph templates for the word 確認 — required to accept a Confirm hit."""
        self.confirm_text_templates.clear()
        if not CONFIRM_TEXT_DIR.exists():
            return
        for pattern in ("*.png", "*.jpg"):
            for path in sorted(CONFIRM_TEXT_DIR.glob(pattern)):
                img = cv2.imread(str(path), cv2.IMREAD_COLOR)
                if img is None or img.size == 0:
                    continue
                self.confirm_text_templates.append(
                    cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                )

    def _load_tree(
        self, root: Path, langs: set, *, learned: bool
    ) -> None:
        for button in ("skip", "confirm"):
            button_dir = root / button
            if not button_dir.exists():
                continue
            for lang_dir in sorted(button_dir.iterdir()):
                if not lang_dir.is_dir():
                    continue
                if learned:
                    continue
                if lang_dir.name not in langs:
                    continue
                self._load_images(button, lang_dir.name, lang_dir)

    def _load_reinforce(self, langs: set) -> None:
        if not REINFORCE_DIR.exists():
            return
        lang_tag = "learned"
        for button in ("skip", "confirm"):
            folder = REINFORCE_DIR / button
            if folder.exists():
                self._load_images(button, lang_tag, folder)

    def _load_images(self, button: str, lang: str, folder: Path) -> None:
        for pattern in ("*.png", "*.jpg"):
            for path in sorted(folder.glob(pattern)):
                img = cv2.imread(str(path), cv2.IMREAD_COLOR)
                if img is None or img.size == 0:
                    continue
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                self.templates.append(
                    TemplateEntry(
                        button=button,
                        lang=lang,
                        path=path,
                        image=img,
                        gray=gray,
                    )
                )

    def add_image(
        self, button: str, lang: str, path: Path, image: np.ndarray
    ) -> None:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        self.templates.append(
            TemplateEntry(
                button=button, lang=lang, path=path, image=image, gray=gray
            )
        )

    def count_by_button(self) -> Dict[str, int]:
        counts = {"skip": 0, "confirm": 0}
        for t in self.templates:
            counts[t.button] = counts.get(t.button, 0) + 1
        return counts

    # Prefer confirm_btn.png (with 確認) when picking manuals
    def _pick_candidates(self, button: str) -> List[TemplateEntry]:
        """Keep the hot path close to single-template speed."""
        manual = [
            t
            for t in self.templates
            if t.button == button and t.lang != "learned"
        ]
        learned = [
            t
            for t in self.templates
            if t.button == button and t.lang == "learned"
        ]

        def manual_key(t: TemplateEntry) -> tuple:
            name = t.path.name.lower()
            # Prefer the official 確認 button asset first
            prefer = 0 if "confirm_btn" in name or "確認" in t.path.stem else 1
            return (prefer, name)

        manual_sorted = sorted(manual, key=manual_key)
        learned_sorted = sorted(
            learned,
            key=lambda t: t.path.stat().st_mtime if t.path.exists() else 0,
            reverse=True,
        )
        return (
            manual_sorted[: self.MAX_MANUAL]
            + learned_sorted[: self.MAX_LEARNED]
        )

    @staticmethod
    def _roi_for_button(
        frame: np.ndarray, button: str
    ) -> tuple[np.ndarray, int, int]:
        """Smaller search region ⇒ higher FPS (as the reference notes)."""
        fh, fw = frame.shape[:2]
        if button == "skip":
            # HSR skip sits in the upper-right
            x0 = int(fw * 0.62)
            y0 = 0
            x1 = fw
            y1 = int(fh * 0.28)
        else:
            x0 = int(fw * 0.28)
            y0 = int(fh * 0.32)
            x1 = int(fw * 0.72)
            y1 = int(fh * 0.78)
        return frame[y0:y1, x0:x1], x0, y0

    def contains_confirm_text(
        self,
        frame_bgr: np.ndarray,
        match: Optional[MatchResult] = None,
        threshold: float = 0.75,
    ) -> bool:
        """Return True if the word 確認 is visible near the confirm match / ROI."""
        if not self.confirm_text_templates:
            return False
        fh, fw = frame_bgr.shape[:2]
        if match is not None and match.w > 0 and match.h > 0:
            pad_x = max(8, match.w // 4)
            pad_y = max(8, match.h // 2)
            x0 = max(0, match.x - pad_x)
            y0 = max(0, match.y - pad_y)
            x1 = min(fw, match.x + match.w + pad_x)
            y1 = min(fh, match.y + match.h + pad_y)
            region = frame_bgr[y0:y1, x0:x1]
        else:
            region, _, _ = self._roi_for_button(frame_bgr, "confirm")
        if region.size == 0:
            return False
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        rh, rw = gray.shape[:2]
        best = 0.0
        for tmpl in self.confirm_text_templates:
            th, tw = tmpl.shape[:2]
            for scale in (0.85, 1.0, 1.15):
                nw = max(8, int(tw * scale))
                nh = max(8, int(th * scale))
                if nh > rh or nw > rw:
                    continue
                scaled = (
                    tmpl
                    if scale == 1.0
                    else cv2.resize(tmpl, (nw, nh), interpolation=cv2.INTER_AREA)
                )
                result = cv2.matchTemplate(gray, scaled, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)
                best = max(best, float(max_val))
                if best >= threshold:
                    return True
        return False

    def match(
        self,
        frame_bgr: np.ndarray,
        button: str,
        threshold: float = 0.85,
        scale_match: bool = True,
        require_confirm_text: bool = True,
    ) -> MatchResult:
        empty = MatchResult(
            found=False,
            score=0.0,
            x=0,
            y=0,
            w=0,
            h=0,
            lang="",
            template_name="",
            button=button,
        )
        if frame_bgr is None or frame_bgr.size == 0:
            return empty

        candidates = self._pick_candidates(button)
        if not candidates:
            return empty

        roi_bgr, ox, oy = self._roi_for_button(frame_bgr, button)
        if roi_bgr.size == 0:
            roi_bgr, ox, oy = frame_bgr, 0, 0
        roi_gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)

        best: Optional[MatchResult] = None
        scales = (1.0, 1.08) if scale_match else (1.0,)
        early_exit = min(0.96, threshold + 0.06)

        for entry in candidates:
            tmpl = entry.gray
            th, tw = tmpl.shape[:2]
            for scale in scales:
                if scale != 1.0:
                    new_w = max(8, int(tw * scale))
                    new_h = max(8, int(th * scale))
                    scaled = cv2.resize(
                        tmpl, (new_w, new_h), interpolation=cv2.INTER_AREA
                    )
                else:
                    scaled = tmpl
                    new_w, new_h = tw, th

                rh, rw = roi_gray.shape[:2]
                if new_h > rh or new_w > rw:
                    continue

                result = cv2.matchTemplate(
                    roi_gray, scaled, cv2.TM_CCOEFF_NORMED
                )
                _, max_val, _, max_loc = cv2.minMaxLoc(result)
                if best is None or max_val > best.score:
                    best = MatchResult(
                        found=max_val >= threshold,
                        score=float(max_val),
                        x=int(max_loc[0]) + ox,
                        y=int(max_loc[1]) + oy,
                        w=new_w,
                        h=new_h,
                        lang=entry.lang,
                        template_name=entry.path.name,
                        button=button,
                    )
                    if best.score >= early_exit:
                        break
            if best is not None and best.score >= early_exit:
                break

        if best is None:
            return empty
        best.found = best.score >= threshold

        # Confirm must also contain the word 確認
        if (
            button == "confirm"
            and best.found
            and require_confirm_text
            and self.confirm_text_templates
        ):
            if not self.contains_confirm_text(
                frame_bgr, best, threshold=max(0.70, threshold - 0.12)
            ):
                best.found = False
                best.template_name = f"{best.template_name}|no_確認"

        return best

    def annotate(
        self, frame_bgr: np.ndarray, match: MatchResult, color=(0, 220, 180)
    ) -> np.ndarray:
        out = frame_bgr.copy()
        if match.found:
            cv2.rectangle(
                out,
                (match.x, match.y),
                (match.x + match.w, match.y + match.h),
                color,
                2,
            )
            label = f"{match.button} {match.lang} {match.score:.2f}"
            cv2.putText(
                out,
                label,
                (match.x, max(16, match.y - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
                cv2.LINE_AA,
            )
        return out
