"""Annotation editor – draw shapes, freehand, arrows, text on a captured screenshot."""

import os
import tkinter as tk
from tkinter import colorchooser, filedialog
from PIL import Image, ImageDraw, ImageTk


TOOLS = ["select", "pen", "marker", "eraser", "line", "arrow", "rect", "ellipse", "text"]
TOOL_NAMES = {
    "select": "Select",
    "pen": "Pen",
    "marker": "Marker",
    "eraser": "Eraser",
    "line": "Line",
    "arrow": "Arrow",
    "rect": "Rectangle",
    "ellipse": "Ellipse",
    "text": "Text",
}


class _ToolTip:
    def __init__(self, widget, text):
        self._tip = None
        widget.bind("<Enter>", lambda e: self._show(widget, text))
        widget.bind("<Leave>", lambda e: self._hide())

    def _show(self, widget, text):
        x = widget.winfo_rootx() + widget.winfo_width() + 6
        y = widget.winfo_rooty() + (widget.winfo_height() // 2) - 10
        self._tip = tk.Toplevel(widget)
        self._tip.overrideredirect(True)
        self._tip.attributes("-topmost", True)
        self._tip.geometry(f"+{x}+{y}")
        tk.Label(
            self._tip, text=text,
            bg="#FFFFCC", fg="#1A1A1A",
            font=("Segoe UI", 9),
            relief="solid", bd=1, padx=5, pady=3,
        ).pack()

    def _hide(self):
        if self._tip:
            self._tip.destroy()
            self._tip = None
COLORS = ["#E53935", "#FF9800", "#FFEB3B", "#43A047", "#1E88E5", "#8E24AA",
          "#000000", "#FFFFFF", "#BDBDBD", "#795548"]
SIZES = [2, 4, 6, 10, 16, 24]


class EditorWindow:
    def __init__(self, image: Image.Image, save_dir: str,
                 auto_saved_path: str | None = None, tk_root: tk.Tk | None = None):
        self.original = image.copy()
        self.capture = image.copy()  # untouched original for "erase to original"
        self.save_dir = save_dir
        self.auto_saved_path = auto_saved_path

        # drawing state
        self.tool = "pen"
        self.color = "#E53935"
        self.size = 4
        self.history: list[Image.Image] = []  # undo stack
        self.redo_stack: list[Image.Image] = []

        # canvas drawing state
        self._erase_to_original = False
        self._drawing = False
        self._last_x = self._last_y = 0
        self._shape_start = (0, 0)
        self._preview_id = None
        self._text_entry = None

        from version import __version__
        import sys, os
        self._tk_root = tk_root  # persistent root when called from main window
        _owns_root = tk_root is None

        if _owns_root:
            self.root = tk.Tk()
        else:
            self.root = tk.Toplevel(tk_root)

        self.root.title(f"Screenshot Tool v{__version__}")
        self.root.configure(bg="#2B2B2B")
        self.root.resizable(True, True)
        self.root.geometry("1100x700")
        self.root.minsize(800, 550)
        _base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        _ico = os.path.join(_base, "screenshot_tool_icon.ico")
        if os.path.exists(_ico):
            self.root.iconbitmap(_ico)

        self._build_ui()
        self._push_history()
        self._refresh_canvas()
        self._start_update_check()

        if _owns_root:
            self.root.mainloop()
        else:
            tk_root.wait_window(self.root)

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Top toolbar ──
        toolbar = tk.Frame(self.root, bg="#1E1E1E", pady=4)
        toolbar.pack(fill="x", side="top")

        # Action buttons
        for label, cmd in [
            ("New Snip", self._new_snip),
            ("Undo", self._undo),
            ("Redo", self._redo),
            ("Copy", self._copy_to_clipboard),
            ("Save As…", self._save_as),
            ("Copy Path", self._copy_path),
        ]:
            tk.Button(
                toolbar, text=label, command=cmd,
                bg="#3C3F41", fg="white", relief="flat",
                padx=10, pady=4, font=("Segoe UI", 9),
                activebackground="#4C5052", activeforeground="white",
                cursor="hand2",
            ).pack(side="left", padx=2)

        # Status label (auto-save path)
        self._status_var = tk.StringVar()
        if self.auto_saved_path:
            self._status_var.set(f"Auto-saved: {self.auto_saved_path}")
        tk.Label(toolbar, textvariable=self._status_var, bg="#1E1E1E",
                 fg="#8A8A8A", font=("Segoe UI", 8)).pack(side="right", padx=10)

        # ── Left tool panel ──
        tool_panel = tk.Frame(self.root, bg="#252526", width=56)
        tool_panel.pack(fill="y", side="left")
        tool_panel.pack_propagate(False)

        tool_icons = {
            "select": "↖",
            "pen": "✏",
            "marker": "▊",
            "eraser": "◻",
            "line": "╱",
            "arrow": "→",
            "rect": "▭",
            "ellipse": "⬭",
            "text": "T",
        }
        self._tool_buttons = {}
        for t in TOOLS:
            btn = tk.Button(
                tool_panel, text=tool_icons[t], width=3,
                bg="#252526", fg="#CCCCCC", relief="flat",
                font=("Segoe UI", 14), pady=6,
                activebackground="#007ACC", activeforeground="white",
                cursor="hand2",
                command=lambda tool=t: self._select_tool(tool),
            )
            btn.pack(fill="x", pady=1, padx=4)
            self._tool_buttons[t] = btn
            _ToolTip(btn, TOOL_NAMES[t])

        # ── Right properties panel ──
        prop_panel = tk.Frame(self.root, bg="#252526", width=160)
        prop_panel.pack(fill="y", side="right")
        prop_panel.pack_propagate(False)

        tk.Label(prop_panel, text="Color", bg="#252526", fg="#AAAAAA",
                 font=("Segoe UI", 9)).pack(anchor="w", padx=8, pady=(10, 2))

        color_grid = tk.Frame(prop_panel, bg="#252526")
        color_grid.pack(padx=8)
        self._color_btns = {}
        for i, c in enumerate(COLORS):
            btn = tk.Button(
                color_grid, bg=c, width=2, height=1,
                relief="solid", bd=1, cursor="hand2",
                command=lambda col=c: self._select_color(col),
            )
            btn.grid(row=i // 2, column=i % 2, padx=2, pady=2)
            self._color_btns[c] = btn

        custom_btn = tk.Button(
            prop_panel, text="Custom…", command=self._pick_custom_color,
            bg="#3C3F41", fg="white", relief="flat",
            font=("Segoe UI", 8), pady=3, cursor="hand2",
        )
        custom_btn.pack(fill="x", padx=8, pady=4)

        self._color_preview = tk.Label(prop_panel, bg=self.color, height=2)
        self._color_preview.pack(fill="x", padx=8, pady=2)

        tk.Label(prop_panel, text="Size", bg="#252526", fg="#AAAAAA",
                 font=("Segoe UI", 9)).pack(anchor="w", padx=8, pady=(10, 2))

        size_frame = tk.Frame(prop_panel, bg="#252526")
        size_frame.pack(padx=8, fill="x")
        self._size_buttons = {}
        for s in SIZES:
            btn = tk.Button(
                size_frame, text=str(s), width=3,
                bg="#3C3F41", fg="white", relief="flat",
                font=("Segoe UI", 8), cursor="hand2",
                command=lambda sz=s: self._select_size(sz),
            )
            btn.pack(side="left", padx=1)
            self._size_buttons[s] = btn
        self._select_size(4)

        # opacity slider for marker
        tk.Label(prop_panel, text="Opacity", bg="#252526", fg="#AAAAAA",
                 font=("Segoe UI", 9)).pack(anchor="w", padx=8, pady=(10, 2))
        self._opacity_var = tk.IntVar(value=128)
        tk.Scale(
            prop_panel, from_=30, to=255, orient="horizontal",
            variable=self._opacity_var, bg="#252526", fg="white",
            troughcolor="#3C3F41", highlightthickness=0, sliderlength=12,
        ).pack(fill="x", padx=8)

        # eraser mode toggle
        tk.Label(prop_panel, text="Eraser Mode", bg="#252526", fg="#AAAAAA",
                 font=("Segoe UI", 9)).pack(anchor="w", padx=8, pady=(12, 2))
        self._erase_mode_var = tk.StringVar(value="white")
        for label, val in [("Erase to White", "white"), ("Erase to Original", "original")]:
            tk.Radiobutton(
                prop_panel, text=label, variable=self._erase_mode_var, value=val,
                bg="#252526", fg="#CCCCCC", selectcolor="#007ACC",
                activebackground="#252526", activeforeground="white",
                font=("Segoe UI", 8), cursor="hand2",
                command=self._update_erase_mode,
            ).pack(anchor="w", padx=8)

        # ── Canvas area with scrollbars ──
        canvas_frame = tk.Frame(self.root, bg="#1A1A1A")
        canvas_frame.pack(fill="both", expand=True)

        self._hbar = tk.Scrollbar(canvas_frame, orient="horizontal")
        self._vbar = tk.Scrollbar(canvas_frame, orient="vertical")
        self._hbar.pack(side="bottom", fill="x")
        self._vbar.pack(side="right", fill="y")

        img_w, img_h = self.original.size
        self.canvas = tk.Canvas(
            canvas_frame,
            width=min(img_w, 1200),
            height=min(img_h, 800),
            bg="#1A1A1A",
            cursor="crosshair",
            xscrollcommand=self._hbar.set,
            yscrollcommand=self._vbar.set,
            scrollregion=(0, 0, img_w, img_h),
        )
        self.canvas.pack(fill="both", expand=True)
        self._hbar.config(command=self.canvas.xview)
        self._vbar.config(command=self.canvas.yview)

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.root.bind("<Control-z>", lambda e: self._undo())
        self.root.bind("<Control-y>", lambda e: self._redo())
        self.root.bind("<Control-c>", lambda e: self._copy_to_clipboard())
        self.root.bind("<Control-s>", lambda e: self._save_as())
        self._select_tool("pen")

        # Update banner (hidden until an update is found)
        self._update_banner = tk.Frame(self.root, bg="#007ACC", pady=4)
        self._update_label = tk.Label(
            self._update_banner, text="", bg="#007ACC", fg="white",
            font=("Segoe UI", 9),
        )
        self._update_label.pack(side="left", padx=10)
        tk.Button(
            self._update_banner, text="Install & Restart",
            bg="#005A9E", fg="white", relief="flat",
            font=("Segoe UI", 9, "bold"), padx=8, cursor="hand2",
            activebackground="#004A8A", activeforeground="white",
            command=self._apply_update,
        ).pack(side="left", padx=4)
        tk.Button(
            self._update_banner, text="✕", bg="#007ACC", fg="white",
            relief="flat", font=("Segoe UI", 9), cursor="hand2",
            activebackground="#0060AA", activeforeground="white",
            command=lambda: self._update_banner.pack_forget(),
        ).pack(side="right", padx=6)
        self._pending_update = None

    # ── Tool / color / size selection ────────────────────────────────────────

    def _select_tool(self, tool):
        self.tool = tool
        for t, btn in self._tool_buttons.items():
            btn.configure(bg="#007ACC" if t == tool else "#252526")
        cursor = "xterm" if tool == "text" else ("crosshair" if tool != "select" else "arrow")
        self.canvas.configure(cursor=cursor)

    def _update_erase_mode(self):
        self._erase_to_original = self._erase_mode_var.get() == "original"

    def _select_color(self, color):
        self.color = color
        self._color_preview.configure(bg=color)

    def _pick_custom_color(self):
        result = colorchooser.askcolor(color=self.color, title="Choose color")
        if result and result[1]:
            self._select_color(result[1])

    def _select_size(self, size):
        self.size = size
        for s, btn in self._size_buttons.items():
            btn.configure(bg="#007ACC" if s == size else "#3C3F41")

    # ── Canvas event handlers ─────────────────────────────────────────────────

    def _canvas_coords(self, event):
        return self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

    def _on_press(self, event):
        x, y = self._canvas_coords(event)
        self._drawing = True
        self._shape_start = (x, y)
        self._last_x, self._last_y = x, y

        if self.tool == "text":
            self._place_text_entry(x, y)
            self._drawing = False

    def _on_drag(self, event):
        if not self._drawing:
            return
        x, y = self._canvas_coords(event)

        if self.tool in ("pen", "eraser"):
            if self.tool == "eraser" and self._erase_to_original:
                r = self.size
                # Create a circular mask for the stroke area
                mask = Image.new("L", self.original.size, 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse([x - r, y - r, x + r, y + r], fill=255)
                mask_draw.line([self._last_x, self._last_y, x, y], fill=255, width=self.size * 2)
                self.original.paste(self.capture, mask=mask)
            else:
                draw = ImageDraw.Draw(self.original)
                color = "#FFFFFF" if self.tool == "eraser" else self.color
                r = self.size // 2
                draw.ellipse([x - r, y - r, x + r, y + r], fill=color)
                draw.line([self._last_x, self._last_y, x, y], fill=color, width=self.size)
            self._last_x, self._last_y = x, y
            self._refresh_canvas()

        elif self.tool == "marker":
            draw = ImageDraw.Draw(self.original, "RGBA")
            c = self._hex_to_rgba(self.color, self._opacity_var.get())
            r = self.size
            draw.ellipse([x - r, y - r, x + r, y + r], fill=c)
            draw.line([self._last_x, self._last_y, x, y], fill=c, width=self.size * 2)
            self._last_x, self._last_y = x, y
            self._refresh_canvas()

        elif self.tool in ("line", "arrow", "rect", "ellipse"):
            # Preview on canvas without committing
            self._draw_shape_preview(x, y)

    def _on_release(self, event):
        if not self._drawing:
            return
        self._drawing = False
        x, y = self._canvas_coords(event)

        if self.tool in ("line", "arrow", "rect", "ellipse"):
            if self._preview_id:
                self.canvas.delete(self._preview_id)
                self._preview_id = None
            self._commit_shape(self._shape_start[0], self._shape_start[1], x, y)

        elif self.tool in ("pen", "eraser", "marker"):
            self._push_history()

    def _draw_shape_preview(self, x2, y2):
        if self._preview_id:
            self.canvas.delete(self._preview_id)
        x1, y1 = self._shape_start
        color = self.color

        if self.tool == "line":
            self._preview_id = self.canvas.create_line(x1, y1, x2, y2, fill=color, width=self.size, dash=(4, 2))
        elif self.tool == "arrow":
            self._preview_id = self.canvas.create_line(x1, y1, x2, y2, fill=color, width=self.size,
                                                        arrow="last", arrowshape=(12, 15, 4))
        elif self.tool == "rect":
            self._preview_id = self.canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=self.size, dash=(4,2))
        elif self.tool == "ellipse":
            self._preview_id = self.canvas.create_oval(x1, y1, x2, y2, outline=color, width=self.size, dash=(4,2))

    def _commit_shape(self, x1, y1, x2, y2):
        draw = ImageDraw.Draw(self.original)
        w = self.size

        if self.tool == "line":
            draw.line([x1, y1, x2, y2], fill=self.color, width=w)

        elif self.tool == "arrow":
            self._draw_arrow_pil(draw, x1, y1, x2, y2, self.color, w)

        elif self.tool == "rect":
            draw.rectangle([x1, y1, x2, y2], outline=self.color, width=w)

        elif self.tool == "ellipse":
            draw.ellipse([x1, y1, x2, y2], outline=self.color, width=w)

        self._push_history()
        self._refresh_canvas()

    @staticmethod
    def _draw_arrow_pil(draw, x1, y1, x2, y2, color, w):
        import math
        draw.line([x1, y1, x2, y2], fill=color, width=w)
        angle = math.atan2(y2 - y1, x2 - x1)
        head = 16 + w * 2
        spread = 0.5
        for a in [angle + math.pi - spread, angle + math.pi + spread]:
            hx = x2 + head * math.cos(a)
            hy = y2 + head * math.sin(a)
            draw.line([x2, y2, hx, hy], fill=color, width=w)

    def _place_text_entry(self, x, y):
        if self._text_entry:
            self._commit_text()
        frame = tk.Frame(self.canvas, bg=self.color, bd=1, relief="solid")
        entry = tk.Entry(frame, font=("Segoe UI", self.size + 8),
                         fg=self.color, bg="white", relief="flat",
                         insertbackground=self.color, width=18)
        entry.pack(padx=2, pady=2)
        self._text_window = self.canvas.create_window(x, y, anchor="nw", window=frame)
        entry.focus_set()
        entry.bind("<Return>", lambda e: self._commit_text())
        entry.bind("<Escape>", lambda e: self._cancel_text())
        self._text_entry = entry
        self._text_pos = (x, y)

    def _commit_text(self):
        if not self._text_entry:
            return
        text = self._text_entry.get()
        x, y = self._text_pos
        if text.strip():
            draw = ImageDraw.Draw(self.original)
            draw.text((x, y), text, fill=self.color)
            self._push_history()
            self._refresh_canvas()
        self.canvas.delete(self._text_window)
        self._text_entry = None

    def _cancel_text(self):
        if self._text_entry:
            self.canvas.delete(self._text_window)
            self._text_entry = None

    # ── History ──────────────────────────────────────────────────────────────

    def _push_history(self):
        self.history.append(self.original.copy())
        self.redo_stack.clear()
        if len(self.history) > 50:
            self.history.pop(0)

    def _undo(self):
        if len(self.history) > 1:
            self.redo_stack.append(self.history.pop())
            self.original = self.history[-1].copy()
            self._refresh_canvas()

    def _redo(self):
        if self.redo_stack:
            state = self.redo_stack.pop()
            self.history.append(state)
            self.original = state.copy()
            self._refresh_canvas()

    # ── Canvas refresh ────────────────────────────────────────────────────────

    def _refresh_canvas(self):
        img = self.original.convert("RGB")
        self._photo = ImageTk.PhotoImage(img)
        if hasattr(self, "_canvas_img_id"):
            self.canvas.itemconfigure(self._canvas_img_id, image=self._photo)
        else:
            self._canvas_img_id = self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
        self.canvas.configure(scrollregion=(0, 0, img.width, img.height))

    # ── Actions ───────────────────────────────────────────────────────────────

    def _new_snip(self):
        self.root.withdraw()
        # Wait for the window to fully disappear before grabbing the screen
        # noinspection PyTypeChecker
        self.root.after(300, lambda: self._start_new_snip())

    def _start_new_snip(self):
        from capture_overlay import CaptureOverlay
        # Use the persistent tk root when available so the overlay is a proper Toplevel
        overlay_root = self._tk_root if self._tk_root else self.root
        CaptureOverlay(self._on_new_capture, on_cancel=self.root.deiconify, root=overlay_root)

    def _on_new_capture(self, image):
        from main import auto_save
        self.root.deiconify()
        path = auto_save(image, self.save_dir)
        self.original = image.copy()
        self.capture = image.copy()
        self.history.clear()
        self.redo_stack.clear()
        self._push_history()
        self._refresh_canvas()
        self.auto_saved_path = path
        self._status_var.set(f"Auto-saved: {path}")

    # ── Auto-update ───────────────────────────────────────────────────────────

    def _start_update_check(self):
        import threading
        threading.Thread(target=self._bg_update_check, daemon=True).start()

    def _bg_update_check(self):
        try:
            from updater import check_for_update
            info = check_for_update()
            if info:
                self.root.after(0, self._show_update_banner, info)
        except (ImportError, OSError, RuntimeError):
            pass

    def _show_update_banner(self, info):
        self._pending_update = info
        self._update_label.configure(
            text=f"Update available: v{info.current_version} → v{info.latest_version}"
        )
        self._update_banner.pack(fill="x", before=self.canvas.master)

    def _apply_update(self):
        if not self._pending_update:
            return
        import threading
        from tkinter import messagebox

        # Disable button and show progress in the banner label
        for w in self._update_banner.winfo_children():
            if isinstance(w, tk.Button) and "Install" in w.cget("text"):
                w.configure(state="disabled", text="Downloading…")
                break

        def run():
            try:
                from updater import download_and_apply

                def progress(done, total):
                    if total:
                        pct = int(done / total * 100)
                        label_text = f"Downloading update… {pct}%"
                        # noinspection PyTypeChecker
                        self.root.after(0, lambda: self._update_label.configure(text=label_text))

                download_and_apply(self._pending_update, progress_callback=progress)
            except (OSError, RuntimeError) as e:
                err_msg = str(e)
                # noinspection PyTypeChecker
                self.root.after(0, lambda: messagebox.showerror("Update Failed", err_msg))
                # noinspection PyTypeChecker
                self.root.after(0, lambda: self._show_update_banner(self._pending_update))

        threading.Thread(target=run, daemon=True).start()

    def _copy_to_clipboard(self):
        import win32clipboard
        import io
        output = io.BytesIO()
        img = self.original.convert("RGB")
        img.save(output, format="BMP")
        data = output.getvalue()[14:]
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()
        self._status_var.set("Copied to clipboard")

    def _copy_path(self):
        if not self.auto_saved_path:
            self._status_var.set("No saved path to copy")
            return
        import win32clipboard
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(self.auto_saved_path, win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
        self._status_var.set(f"Path copied: {self.auto_saved_path}")

    def _save_as(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG image", "*.png"), ("JPEG image", "*.jpg"), ("All files", "*.*")],
            initialdir=self.save_dir,
        )
        if path:
            self.original.convert("RGB").save(path)
            if (self.auto_saved_path
                    and os.path.exists(self.auto_saved_path)
                    and os.path.abspath(self.auto_saved_path) != os.path.abspath(path)):
                os.remove(self.auto_saved_path)
            self.auto_saved_path = path
            self._status_var.set(f"Saved: {path}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _hex_to_rgba(hex_color: str, alpha: int) -> tuple:
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return r, g, b, alpha
