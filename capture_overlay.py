"""Fullscreen translucent overlay for click-drag region selection."""

import tkinter as tk
import mss
from PIL import Image, ImageTk, ImageEnhance


class CaptureOverlay:
    def __init__(self, on_capture, root=None):
        """
        on_capture(image): called with the cropped PIL image on success.
        root: pass an existing Tk root to reuse its mainloop (e.g. from the editor).
              If None, a new Tk root is created and mainloop is started here.
        """
        self.on_capture = on_capture
        self.start_x = self.start_y = 0
        self.rect_id = None
        self._bright_photo = None

        self._owns_root = root is None
        if self._owns_root:
            self.root = tk.Tk()
            self.root.withdraw()
        else:
            self.root = root

        # Grab full desktop
        with mss.mss() as sct:
            full = sct.grab(sct.monitors[0])
            self.full_width = full.width
            self.full_height = full.height
            self.bg_image_pil = Image.frombytes("RGB", full.size, full.bgra, "raw", "BGRX")

        self.overlay = tk.Toplevel(self.root)
        self.overlay.overrideredirect(True)
        self.overlay.attributes("-topmost", True)
        self.overlay.geometry(f"{self.full_width}x{self.full_height}+0+0")
        self.overlay.configure(cursor="crosshair")

        self.canvas = tk.Canvas(
            self.overlay,
            width=self.full_width,
            height=self.full_height,
            highlightthickness=0,
            cursor="crosshair",
        )
        self.canvas.pack()

        darkened = ImageEnhance.Brightness(self.bg_image_pil).enhance(0.45)
        self.bg_photo = ImageTk.PhotoImage(darkened)
        self.canvas.create_image(0, 0, anchor="nw", image=self.bg_photo)

        self.canvas.create_text(
            self.full_width // 2, 40,
            text="Click and drag to capture a region  •  ESC to cancel",
            fill="white",
            font=("Segoe UI", 14),
        )

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.overlay.bind("<Escape>", lambda e: self._cancel())

        if self._owns_root:
            self.root.mainloop()

    def _draw_selection(self, x1, y1, x2, y2):
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.canvas.delete("bright_patch", "size_label")

        self.rect_id = self.canvas.create_rectangle(
            x1, y1, x2, y2,
            outline="#00B4FF", width=2, dash=(4, 2),
        )
        if abs(x2 - x1) > 2 and abs(y2 - y1) > 2:
            rx1, ry1 = min(x1, x2), min(y1, y2)
            rx2, ry2 = max(x1, x2), max(y1, y2)
            crop = self.bg_image_pil.crop((rx1, ry1, rx2, ry2))
            self._bright_photo = ImageTk.PhotoImage(crop)
            self.canvas.create_image(rx1, ry1, anchor="nw", image=self._bright_photo, tags="bright_patch")

        w, h = abs(x2 - x1), abs(y2 - y1)
        lx = min(x1, x2)
        ly = max(y1, y2) + 6
        if ly + 20 > self.full_height:
            ly = min(y1, y2) - 22
        self.canvas.create_text(
            lx, ly, text=f"{w} × {h}", anchor="nw",
            fill="white", font=("Segoe UI", 10, "bold"), tags="size_label",
        )

    def _on_press(self, event):
        self.start_x, self.start_y = event.x, event.y

    def _on_drag(self, event):
        self._draw_selection(self.start_x, self.start_y, event.x, event.y)

    def _on_release(self, event):
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        self._close_overlay()
        if x2 - x1 >= 5 and y2 - y1 >= 5:
            region = self.bg_image_pil.crop((x1, y1, x2, y2))
            self.on_capture(region)
        elif not self._owns_root:
            self.root.deiconify()

    def _cancel(self):
        self._close_overlay()
        if not self._owns_root:
            self.root.deiconify()

    def _close_overlay(self):
        self.overlay.destroy()
        if self._owns_root:
            self.root.destroy()
