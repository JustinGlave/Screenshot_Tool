"""Home/launcher window — shown on startup and after each snip session."""

import tkinter as tk
from tkinter import filedialog, messagebox
import os
import sys
from pathlib import Path

from version import __version__
from config import load_config, save_config

_instance = None  # active MainWindow


def get_instance():
    return _instance


class MainWindow:
    def __init__(self, tk_root: tk.Tk, default_save_dir: str):
        global _instance
        _instance = self

        self._tk_root = tk_root
        self._cfg = load_config()
        self._countdown_win = None
        self._cd_label = None

        self.win = tk.Toplevel(tk_root)
        self.win.title(f"Screenshot Tool v{__version__}")
        self.win.configure(bg="#2B2B2B")
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self.hide)

        _base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        _ico = os.path.join(_base, "screenshot_tool_icon.ico")
        if os.path.exists(_ico):
            self.win.iconbitmap(_ico)

        self._default_save_dir = default_save_dir
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        tk.Label(
            self.win, text="Screenshot Tool",
            font=("Segoe UI", 16, "bold"), bg="#2B2B2B", fg="white",
        ).pack(pady=(28, 4))
        tk.Label(
            self.win, text=f"v{__version__}",
            font=("Segoe UI", 9), bg="#2B2B2B", fg="#666666",
        ).pack(pady=(0, 22))

        # Capture buttons
        btn_frame = tk.Frame(self.win, bg="#2B2B2B")
        btn_frame.pack(padx=36, pady=4)
        for label, delay in [("Snip Now", 0), ("3s Timer", 3), ("5s Timer", 5)]:
            tk.Button(
                btn_frame, text=label,
                command=lambda d=delay: self.start_snip(d),
                bg="#007ACC", fg="white", relief="flat",
                font=("Segoe UI", 11, "bold"), padx=16, pady=12,
                cursor="hand2",
                activebackground="#005A9E", activeforeground="white",
            ).pack(side="left", padx=5)

        # Divider
        tk.Frame(self.win, bg="#3C3F41", height=1).pack(fill="x", padx=28, pady=(28, 14))

        # Save location
        tk.Label(
            self.win, text="Save Location",
            font=("Segoe UI", 9), bg="#2B2B2B", fg="#AAAAAA",
        ).pack(anchor="w", padx=30)

        path_frame = tk.Frame(self.win, bg="#2B2B2B")
        path_frame.pack(fill="x", padx=28, pady=(6, 4))

        saved = self._valid_or_default_save_dir(self._cfg.get("save_dir", self._default_save_dir))
        self._path_var = tk.StringVar(value=saved)
        self._last_valid_save_dir = saved

        path_entry = tk.Entry(
            path_frame, textvariable=self._path_var,
            font=("Segoe UI", 9), bg="#3C3F41", fg="white",
            relief="flat", insertbackground="white", width=38,
        )
        path_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 6))
        path_entry.bind("<FocusOut>", self._on_path_focus_out)

        tk.Button(
            path_frame, text="Browse…", command=self._browse,
            bg="#3C3F41", fg="white", relief="flat",
            font=("Segoe UI", 9), padx=10, pady=6,
            cursor="hand2", activebackground="#4C5052",
        ).pack(side="right")

        # Hotkey hint
        tk.Label(
            self.win, text="Hotkey: Ctrl+Shift+S",
            font=("Segoe UI", 8), bg="#2B2B2B", fg="#444444",
        ).pack(pady=(16, 24))

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_path_focus_out(self, _event=None):
        path = self._path_var.get().strip()
        if not self._is_writable_dir(path):
            self._path_var.set(self._last_valid_save_dir)
            messagebox.showerror(
                "Invalid Save Location",
                "Choose an existing folder that this app can write to.",
            )
            return

        self._last_valid_save_dir = str(Path(path).expanduser())
        self._path_var.set(self._last_valid_save_dir)
        self._cfg["save_dir"] = self._last_valid_save_dir
        try:
            save_config(self._cfg)
        except OSError as exc:
            messagebox.showerror("Config Save Failed", str(exc))

    def _browse(self):
        current = self._path_var.get()
        folder = filedialog.askdirectory(
            initialdir=current if os.path.isdir(current) else str(Path.home())
        )
        if folder:
            self._path_var.set(folder)
            self._last_valid_save_dir = folder
            self._cfg["save_dir"] = folder
            try:
                save_config(self._cfg)
            except OSError as exc:
                messagebox.showerror("Config Save Failed", str(exc))

    def get_save_dir(self) -> str:
        path = self._path_var.get().strip()
        if self._is_writable_dir(path):
            return path
        return self._default_save_dir

    def show(self):
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()

    def hide(self):
        self.win.withdraw()

    def start_snip(self, delay: int = 0):
        self.hide()
        if delay > 0:
            self._tk_root.after(300, lambda: self._tick_countdown(delay))
        else:
            self._tk_root.after(300, self._do_snip)

    # ── Countdown ─────────────────────────────────────────────────────────────

    def _tick_countdown(self, remaining: int):
        if self._countdown_win is None:
            cw = tk.Toplevel(self._tk_root)
            cw.overrideredirect(True)
            cw.attributes("-topmost", True)
            cw.attributes("-alpha", 0.88)
            sw = self._tk_root.winfo_screenwidth()
            sh = self._tk_root.winfo_screenheight()
            cw.geometry(f"130x90+{sw - 155}+{sh - 130}")
            cw.configure(bg="#1E1E1E")
            self._countdown_win = cw
            self._cd_label = tk.Label(
                cw, font=("Segoe UI", 44, "bold"), fg="white", bg="#1E1E1E"
            )
            self._cd_label.pack(expand=True)
            tk.Label(
                cw, text="Get ready…", font=("Segoe UI", 9), fg="#777777", bg="#1E1E1E"
            ).pack(pady=(0, 8))

        self._cd_label.configure(text=str(remaining))

        if remaining > 0:
            self._tk_root.after(1000, lambda: self._tick_countdown(remaining - 1))
        else:
            self._countdown_win.destroy()
            self._countdown_win = None
            self._cd_label = None
            self._do_snip()

    # ── Capture ───────────────────────────────────────────────────────────────

    def _do_snip(self):
        from capture_overlay import CaptureError, CaptureOverlay
        try:
            CaptureOverlay(self._on_capture, on_cancel=self.show, root=self._tk_root)
        except CaptureError as exc:
            messagebox.showerror("Capture Failed", str(exc))
            self.show()

    def _on_capture(self, image):
        from main import AutoSaveError, auto_save, copy_image_to_clipboard
        from editor_window import EditorWindow
        save_dir = self.get_save_dir()
        try:
            path = auto_save(image, save_dir)
        except AutoSaveError as exc:
            path = None
            messagebox.showerror("Auto-save Failed", str(exc))
        clipboard_ok = copy_image_to_clipboard(image)
        EditorWindow(image, save_dir, path, tk_root=self._tk_root, clipboard_copied=clipboard_ok)
        self.show()

    def _valid_or_default_save_dir(self, path: str) -> str:
        if self._is_writable_dir(path):
            return str(Path(path).expanduser())
        return self._default_save_dir

    @staticmethod
    def _is_writable_dir(path: str) -> bool:
        if not path:
            return False
        candidate = Path(path).expanduser()
        if not candidate.is_dir():
            return False
        test_file = candidate / f".screenshot_tool_write_test_{os.getpid()}"
        try:
            test_file.write_text("", encoding="utf-8")
            test_file.unlink(missing_ok=True)
            return True
        except OSError:
            return False
