"""Multi-language OpenCV template matching."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from app.config import LANGS, ROOT, TEMPLATES_DIR
from app.mask_utils import (
    draw_canonical_skip_glyph,
    is_exploration_hud,
    load_mask,
    refine_skip_mask,
    scale_mask,
    skip_feature_map,
)

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
    mask: Optional[np.ndarray] = None  # color mask sidecar (skip)


class TemplateDetector:
    """Fast template matcher inspired by single-template mss loops.

    Skip with a sidecar mask matches a BG-robust feature map (tophat/local
    contrast) against the canonical |>| glyph — not scene-derived colors.
    We only compare a small active set each frame (like the reference's one template).
    """

    # Cap active templates per button — reference script uses 1
    MAX_MANUAL = 2

    def __init__(self, templates_dir: Path = TEMPLATES_DIR) -> None:
        self.templates_dir = templates_dir
        self.confirm_text_dir = templates_dir / "confirm_text"
        self.templates: List[TemplateEntry] = []
        self.confirm_text_templates: List[np.ndarray] = []
        self.reload()

    def reload(self, enabled_langs: Optional[Sequence[str]] = None) -> int:
        langs = set(enabled_langs or LANGS)
        templates: List[TemplateEntry] = []
        self._load_tree(self.templates_dir, langs, templates)
        confirm_text_templates = self._load_confirm_text()
        self.templates = templates
        self.confirm_text_templates = confirm_text_templates
        return len(self.templates)

    def _load_confirm_text(self) -> List[np.ndarray]:
        """Glyph templates for the word 確認 — required to accept a Confirm hit."""
        templates: List[np.ndarray] = []
        if not self.confirm_text_dir.exists():
            return templates
        for pattern in ("*.png", "*.jpg"):
            for path in sorted(self.confirm_text_dir.glob(pattern)):
                img = cv2.imread(str(path), cv2.IMREAD_COLOR)
                if img is None or img.size == 0:
                    continue
                templates.append(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
        return templates

    def _load_tree(
        self,
        root: Path,
        langs: set,
        templates: List[TemplateEntry],
    ) -> None:
        for button in ("skip", "confirm"):
            button_dir = root / button
            if not button_dir.exists():
                continue
            for lang_dir in sorted(button_dir.iterdir()):
                if not lang_dir.is_dir():
                    continue
                if lang_dir.name not in langs:
                    continue
                self._load_images(button, lang_dir.name, lang_dir, templates)

    def _load_images(
        self,
        button: str,
        lang: str,
        folder: Path,
        templates: List[TemplateEntry],
    ) -> None:
        for pattern in ("*.png", "*.jpg"):
            for path in sorted(folder.glob(pattern)):
                if path.stem.endswith("_mask"):
                    continue
                img = cv2.imread(str(path), cv2.IMREAD_COLOR)
                if img is None or img.size == 0:
                    continue
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                mask = load_mask(path, img) if button == "skip" else None
                templates.append(
                    TemplateEntry(
                        button=button,
                        lang=lang,
                        path=path,
                        image=img,
                        gray=gray,
                        mask=mask,
                    )
                )

    def add_image(
        self,
        button: str,
        lang: str,
        path: Path,
        image: np.ndarray,
        mask: Optional[np.ndarray] = None,
    ) -> None:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        if mask is None and button == "skip":
            mask = load_mask(path, image)
        self.templates.append(
            TemplateEntry(
                button=button,
                lang=lang,
                path=path,
                image=image,
                gray=gray,
                mask=mask,
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
        manual = [t for t in self.templates if t.button == button]
        # Skip: if any sidecar mask exists, only use masked templates.
        # Old gray-only crops (button_14 etc.) false-positive on HUD edges.
        if button == "skip":
            masked = [t for t in manual if t.mask is not None]
            if masked:
                manual = masked

        def manual_key(t: TemplateEntry) -> tuple:
            name = t.path.name.lower()
            # Prefer the official 確認 button asset first
            prefer = 0 if "confirm_btn" in name or "確認" in t.path.stem else 1
            # Prefer live-captured skip_1600 (correct glyph at client res)
            live = 0 if "skip_1600" in name else 1
            has_mask = 0 if t.mask is not None else 1
            return (prefer, live, has_mask, name)

        return sorted(manual, key=manual_key)[: self.MAX_MANUAL]

    @staticmethod
    def _roi_for_button(
        frame: np.ndarray, button: str
    ) -> tuple[np.ndarray, int, int]:
        """Smaller search region ⇒ higher FPS (as the reference notes)."""
        fh, fw = frame.shape[:2]
        if button == "skip":
            # Skip button: top 20% × right 25% of the client area
            x0 = int(fw * 0.75)
            y0 = 0
            x1 = fw
            y1 = int(fh * 0.20)
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

    @staticmethod
    def _match_one(
        roi_bgr: np.ndarray,
        roi_gray: np.ndarray,
        entry: TemplateEntry,
        scale: float,
        roi_feat: Optional[np.ndarray] = None,
    ) -> Optional[Tuple[float, int, int, int, int, bool]]:
        """Return (score, x, y, w, h, used_mask) in ROI coords, or None."""
        th, tw = entry.image.shape[:2]
        if scale != 1.0:
            new_w = max(8, int(tw * scale))
            new_h = max(8, int(th * scale))
        else:
            new_w, new_h = tw, th

        rh, rw = roi_bgr.shape[:2]
        if new_h > rh or new_w > rw:
            return None

        tmpl_gray = (
            entry.gray
            if scale == 1.0
            else cv2.resize(
                entry.gray, (new_w, new_h), interpolation=cv2.INTER_AREA
            )
        )

        # Skip + mask: compare local-contrast feature maps inside the glyph mask.
        # Raw scene colors are ignored, while the captured anti-aliased stroke
        # shape is retained (more accurate than a synthetic triangle/bar).
        use_mask = entry.mask is not None and entry.button == "skip"
        if use_mask:
            mask = scale_mask(entry.mask, new_w, new_h)
            feat = roi_feat if roi_feat is not None else skip_feature_map(roi_gray)
            template_feat = skip_feature_map(tmpl_gray)
            # Sidecar masks cover the filled |>| silhouette. The real icon is
            # an outline, so a broad mask also admits animated scene texture.
            # Restrict it to the template's strokes while retaining slight
            # dilation for anti-aliasing and capture variance.
            glyph = refine_skip_mask(template_feat, mask[:, :, 0])
            result = cv2.matchTemplate(
                feat, template_feat, cv2.TM_CCORR_NORMED, mask=glyph
            )
            result = np.nan_to_num(
                result,
                copy=False,
                nan=-1.0,
                posinf=-1.0,
                neginf=-1.0,
            )
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            x, y = int(max_loc[0]), int(max_loc[1])
            patch = feat[y : y + new_h, x : x + new_w]
            binary = patch >= 12
            expected_features = template_feat >= 12
            mask_pixels = glyph > 0
            binary &= mask_pixels
            expected_features &= mask_pixels
            intersection = int(np.count_nonzero(binary & expected_features))
            union = int(np.count_nonzero(binary | expected_features))
            iou = intersection / union if union else 0.0
            score = float(max_val) * (
                0.70 + 0.30 * min(1.0, iou / 0.22)
            )
            if iou < 0.08:
                score = min(score, float(max_val) * 0.65)
            return (
                score,
                x,
                y,
                new_w,
                new_h,
                True,
            )

        result = cv2.matchTemplate(roi_gray, tmpl_gray, cv2.TM_CCOEFF_NORMED)
        result = np.nan_to_num(
            result,
            copy=False,
            nan=-1.0,
            posinf=-1.0,
            neginf=-1.0,
        )
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        return (
            float(max_val),
            int(max_loc[0]),
            int(max_loc[1]),
            new_w,
            new_h,
            False,
        )

    def _match_skip_near_fixed(
        self,
        frame_bgr: np.ndarray,
        *,
        center_x: int,
        center_y: int,
        box_w: int,
        box_h: int,
        threshold: float,
    ) -> Optional[MatchResult]:
        """Search actual Skip feature templates near the calibrated point."""
        candidates = self._pick_candidates("skip")
        if not candidates:
            return None
        fh, fw = frame_bgr.shape[:2]
        search_w = max(96, box_w * 3)
        search_h = max(72, box_h * 3)
        x0 = max(0, center_x - search_w // 2)
        y0 = max(0, center_y - search_h // 2)
        x1 = min(fw, center_x + search_w // 2)
        y1 = min(fh, center_y + search_h // 2)
        roi_bgr = frame_bgr[y0:y1, x0:x1]
        if roi_bgr.size == 0:
            return None
        roi_gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
        roi_feat = skip_feature_map(roi_gray)
        best: Optional[MatchResult] = None
        for entry in candidates:
            for scale in (1.0, 0.92, 1.08):
                hit = self._match_one(
                    roi_bgr,
                    roi_gray,
                    entry,
                    scale,
                    roi_feat,
                )
                if hit is None:
                    continue
                score, mx, my, width, height, _ = hit
                if best is None or score > best.score:
                    best = MatchResult(
                        found=score >= threshold,
                        score=score,
                        x=x0 + mx,
                        y=y0 + my,
                        w=width,
                        h=height,
                        lang=entry.lang,
                        template_name=f"{entry.path.name}|fixed-local|feat",
                        button="skip",
                    )
        return best

    def match_skip_fixed(
        self,
        frame_bgr: np.ndarray,
        rel_x: float,
        rel_y: float,
        box_w: float = 0.04,
        box_h: float = 0.045,
        threshold: float = 0.85,
        require_presence: bool = True,
    ) -> MatchResult:
        """Click Skip at a fixed client-relative point.

        Coordinates only answer WHERE. Presence check answers WHETHER the
        Skip glyph is actually there (exploration HUD must not count as Skip).
        """
        empty = MatchResult(
            found=False,
            score=0.0,
            x=0,
            y=0,
            w=0,
            h=0,
            lang="",
            template_name="",
            button="skip",
        )
        if frame_bgr is None or frame_bgr.size == 0:
            return empty
        # Overworld menu row occupies the same corner as Skip — hard veto.
        if is_exploration_hud(frame_bgr):
            return MatchResult(
                found=False,
                score=0.0,
                x=0,
                y=0,
                w=0,
                h=0,
                lang="fixed",
                template_name="veto:exploration_hud",
                button="skip",
            )
        fh, fw = frame_bgr.shape[:2]
        cx = int(round(fw * rel_x))
        cy = int(round(fh * rel_y))
        bw = max(16, int(round(fw * box_w)))
        bh = max(16, int(round(fh * box_h)))
        x = max(0, min(fw - bw, cx - bw // 2))
        y = max(0, min(fh - bh, cy - bh // 2))

        score = 1.0
        if require_presence:
            local_match = self._match_skip_near_fixed(
                frame_bgr,
                center_x=cx,
                center_y=cy,
                box_w=bw,
                box_h=bh,
                threshold=threshold,
            )
            if local_match is not None:
                return local_match
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            feat = skip_feature_map(gray)
            patch = feat[y : y + bh, x : x + bw]
            if patch.shape[0] != bh or patch.shape[1] != bw:
                return empty
            glyph = draw_canonical_skip_glyph(bh, bw)
            # CCORR alone false-positives on bright HUD; require glyph-shaped
            # bright mass (IoU) in addition to correlation.
            result = cv2.matchTemplate(
                patch, glyph, cv2.TM_CCORR_NORMED, mask=glyph
            )
            corr = float(result[0, 0])
            binary = patch >= 12
            g = glyph > 0
            inter = int(np.count_nonzero(binary & g))
            union = int(np.count_nonzero(binary | g))
            iou = inter / union if union else 0.0
            # Real Skip: high corr + moderate IoU. Bright HUD: high corr + low IoU
            # or extremely high fill outside glyph.
            score = corr * (0.35 + 0.65 * min(1.0, iou / 0.35))
            if iou < 0.22:
                score = min(score, corr * 0.5)

        found = (not require_presence) or (score >= threshold)
        return MatchResult(
            found=found,
            score=score,
            x=x,
            y=y,
            w=bw,
            h=bh,
            lang="fixed",
            template_name=f"fixed@{rel_x:.4f},{rel_y:.4f}|pres={score:.2f}",
            button="skip",
        )

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

        # Same corner as Skip: overworld icon row must never count as Skip.
        if button == "skip" and is_exploration_hud(frame_bgr):
            empty.template_name = "veto:exploration_hud"
            return empty

        candidates = self._pick_candidates(button)
        if not candidates:
            return empty

        roi_bgr, ox, oy = self._roi_for_button(frame_bgr, button)
        if roi_bgr.size == 0:
            roi_bgr, ox, oy = frame_bgr, 0, 0
        roi_gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
        roi_feat: Optional[np.ndarray] = None
        if button == "skip" and any(t.mask is not None for t in candidates):
            roi_feat = skip_feature_map(roi_gray)

        best: Optional[MatchResult] = None
        # Wider band for resolution / DPI mismatch (templates often captured
        # at a different client size than the live window).
        scales = (1.0, 0.92, 1.08, 0.80, 0.70, 1.10) if scale_match else (1.0,)
        early_exit = min(0.96, threshold + 0.06)

        for entry in candidates:
            for scale in scales:
                hit = self._match_one(roi_bgr, roi_gray, entry, scale, roi_feat)
                if hit is None:
                    continue
                max_val, mx, my, new_w, new_h, used_mask = hit
                if best is None or max_val > best.score:
                    tag = entry.path.name
                    if used_mask:
                        tag = f"{tag}|mask|feat"
                    best = MatchResult(
                        found=max_val >= threshold,
                        score=float(max_val),
                        x=int(mx) + ox,
                        y=int(my) + oy,
                        w=new_w,
                        h=new_h,
                        lang=entry.lang,
                        template_name=tag,
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
        ):
            if not self.confirm_text_templates:
                best.found = False
                best.template_name = f"{best.template_name}|missing_確認_template"
            elif not self.contains_confirm_text(
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
