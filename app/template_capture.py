"""Template capture dialog — select a region from the game window."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk
import cv2
from PIL import Image, ImageTk

from app.config import LANGS, ROOT, TEMPLATES_DIR
from app.mask_utils import make_sidecar_mask, mask_path_for
from app.window_capture import capture_client, find_game_window


class TemplateCaptureDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        keywords,
        on_saved: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(master)
        self.title("擷取按鈕模板")
        self.geometry("920x640")
        self.minsize(720, 520)
        self.configure(fg_color="#0c0e14")
        self.keywords = keywords
        self.on_saved = on_saved
        self._frame_bgr = None
        self._photo = None
        self._scale = 1.0
        self._start = None
        self._rect_id = None

        self.transient(master)
        self.grab_set()

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 8))
        ctk.CTkLabel(
            header,
            text="從遊戲視窗框選按鈕",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="#e8ecf4",
        ).pack(side="left")

        opts = ctk.CTkFrame(self, fg_color="#141824", corner_radius=12)
        opts.pack(fill="x", padx=20, pady=8)

        self.button_var = ctk.StringVar(value="skip")
        self.lang_var = ctk.StringVar(value="zh_tw")
        self.name_var = ctk.StringVar(value="button")

        ctk.CTkLabel(opts, text="類型", text_color="#9aa3b5").grid(
            row=0, column=0, padx=(14, 6), pady=12
        )
        ctk.CTkOptionMenu(
            opts,
            variable=self.button_var,
            values=["skip", "confirm"],
            width=120,
            fg_color="#1c2233",
            button_color="#2a3348",
            button_hover_color="#3a4660",
        ).grid(row=0, column=1, padx=6, pady=12)

        ctk.CTkLabel(opts, text="語系", text_color="#9aa3b5").grid(
            row=0, column=2, padx=(14, 6), pady=12
        )
        ctk.CTkOptionMenu(
            opts,
            variable=self.lang_var,
            values=list(LANGS),
            width=120,
            fg_color="#1c2233",
            button_color="#2a3348",
            button_hover_color="#3a4660",
        ).grid(row=0, column=3, padx=6, pady=12)

        ctk.CTkLabel(opts, text="檔名", text_color="#9aa3b5").grid(
            row=0, column=4, padx=(14, 6), pady=12
        )
        ctk.CTkEntry(
            opts, textvariable=self.name_var, width=140, fg_color="#1c2233"
        ).grid(row=0, column=5, padx=6, pady=12)

        ctk.CTkButton(
            opts,
            text="重新截圖",
            width=100,
            fg_color="#1f6feb",
            hover_color="#388bfd",
            command=self.refresh_capture,
        ).grid(row=0, column=6, padx=(14, 14), pady=12)

        canvas_frame = ctk.CTkFrame(self, fg_color="#0a0c12", corner_radius=12)
        canvas_frame.pack(fill="both", expand=True, padx=20, pady=8)

        self.canvas = ctk.CTkCanvas(
            canvas_frame,
            bg="#0a0c12",
            highlightthickness=0,
            cursor="crosshair",
        )
        self.canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(4, 16))
        self.hint = ctk.CTkLabel(
            footer,
            text="在預覽上拖曳框選按鈕區域，放開後儲存",
            text_color="#7a8499",
            anchor="w",
        )
        self.hint.pack(side="left")
        ctk.CTkButton(
            footer,
            text="關閉",
            width=90,
            fg_color="#2a3348",
            hover_color="#3a4660",
            command=self.destroy,
        ).pack(side="right")

        self.after(100, self.refresh_capture)

    def refresh_capture(self) -> None:
        info = find_game_window(self.keywords)
        if info is None:
            self.hint.configure(
                text="找不到遊戲視窗，請以視窗模式開啟遊戲後再試",
                text_color="#f85149",
            )
            return
        try:
            self._frame_bgr = capture_client(info).frame
        except Exception as exc:
            self.hint.configure(text=f"截圖失敗：{exc}", text_color="#f85149")
            return
        self._show_frame()
        self.hint.configure(
            text=f"已擷取「{info.title}」· {info.width}×{info.height} — 拖曳框選",
            text_color="#7a8499",
        )

    def _show_frame(self) -> None:
        if self._frame_bgr is None:
            return
        self.update_idletasks()
        cw = max(100, self.canvas.winfo_width())
        ch = max(100, self.canvas.winfo_height())
        h, w = self._frame_bgr.shape[:2]
        self._scale = min(cw / w, ch / h, 1.0)
        disp_w = max(1, int(w * self._scale))
        disp_h = max(1, int(h * self._scale))
        rgb = cv2.cvtColor(self._frame_bgr, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (disp_w, disp_h), interpolation=cv2.INTER_AREA)
        img = Image.fromarray(resized)
        self._photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(
            cw // 2, ch // 2, image=self._photo, anchor="center", tags="img"
        )
        self._ox = (cw - disp_w) // 2
        self._oy = (ch - disp_h) // 2

    def _on_press(self, event) -> None:
        self._start = (event.x, event.y)
        if self._rect_id:
            self.canvas.delete(self._rect_id)
            self._rect_id = None

    def _on_drag(self, event) -> None:
        if not self._start:
            return
        if self._rect_id:
            self.canvas.delete(self._rect_id)
        self._rect_id = self.canvas.create_rectangle(
            self._start[0],
            self._start[1],
            event.x,
            event.y,
            outline="#3ee0b0",
            width=2,
        )

    def _on_release(self, event) -> None:
        if not self._start or self._frame_bgr is None:
            return
        x0, y0 = self._start
        x1, y1 = event.x, event.y
        self._start = None

        # Map canvas coords to image coords
        ix0 = int((min(x0, x1) - self._ox) / self._scale)
        iy0 = int((min(y0, y1) - self._oy) / self._scale)
        ix1 = int((max(x0, x1) - self._ox) / self._scale)
        iy1 = int((max(y0, y1) - self._oy) / self._scale)

        h, w = self._frame_bgr.shape[:2]
        ix0, iy0 = max(0, ix0), max(0, iy0)
        ix1, iy1 = min(w, ix1), min(h, iy1)
        if ix1 - ix0 < 8 or iy1 - iy0 < 8:
            self.hint.configure(text="選取區域太小", text_color="#f0883e")
            return

        crop = self._frame_bgr[iy0:iy1, ix0:ix1]
        button = self.button_var.get()
        lang = self.lang_var.get()
        name = self.name_var.get().strip() or "button"
        name = "".join(c for c in name if c.isalnum() or c in "-_")
        out_dir = TEMPLATES_DIR / button / lang
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{name}.png"
        # Avoid overwrite
        idx = 1
        while out_path.exists():
            out_path = out_dir / f"{name}_{idx}.png"
            idx += 1
        cv2.imwrite(str(out_path), crop)
        if button == "skip":
            mask = make_sidecar_mask(crop)
            cv2.imwrite(str(mask_path_for(out_path)), mask)
        try:
            rel = out_path.relative_to(ROOT)
        except ValueError:
            rel = out_path
        self.hint.configure(
            text=f"已儲存 {rel}"
            + (" + 標準 |>| mask" if button == "skip" else ""),
            text_color="#3ee0b0",
        )
        if self.on_saved:
            self.on_saved()
