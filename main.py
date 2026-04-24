"""Screenshot Tool — main entry point.

The app opens to the home window on launch.
The home window stays in the system tray when closed.
Hotkey: Ctrl+Shift+S — triggers a new snip from anywhere.
Only one instance is allowed at a time.
"""

import os
import sys
import ctypes
import ctypes.wintypes
import datetime
import threading
from pathlib import Path
from PIL import Image
from version import __version__

# Must be called before any UI or screen capture — makes tkinter and
# ImageGrab agree on pixel coordinates on high-DPI displays.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # type: ignore[attr-defined]
except Exception:  # noqa: BLE001
    try:
        ctypes.windll.user32.SetProcessDPIAware()  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

# ── Config ────────────────────────────────────────────────────────────────────
SAVE_DIR = Path.home() / "Pictures" / "Screenshots"
SAVE_DIR.mkdir(parents=True, exist_ok=True)

# ── State ─────────────────────────────────────────────────────────────────────
_mutex_handle = None  # keeps single-instance mutex alive


# ── Single instance ───────────────────────────────────────────────────────────

def _acquire_single_instance() -> bool:
    global _mutex_handle
    error_already_exists = 183
    _mutex_handle = ctypes.windll.kernel32.CreateMutexW(  # type: ignore[attr-defined]
        None, False, "ScreenshotTool_SingleInstance_Mutex"
    )
    return ctypes.windll.kernel32.GetLastError() != error_already_exists  # type: ignore[attr-defined]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _icon_path() -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "screenshot_tool_icon.png")


def auto_save(image: Image.Image, save_dir=None) -> str:
    folder = Path(save_dir) if save_dir else SAVE_DIR
    folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = folder / f"screenshot_{timestamp}.png"
    image.convert("RGB").save(str(path))
    return str(path)


# ── Global hotkey via Win32 RegisterHotKey ────────────────────────────────────

def _hotkey_loop(tk_root):
    mod_control = 0x0002
    mod_shift   = 0x0004
    vk_s        = 0x53
    hotkey_id   = 1
    wm_hotkey   = 0x0312

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    if not user32.RegisterHotKey(None, hotkey_id, mod_control | mod_shift, vk_s):
        print("Could not register Ctrl+Shift+S — may already be in use by another app.")
        return

    msg = ctypes.wintypes.MSG()
    while user32.GetMessageA(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == wm_hotkey and msg.wParam == hotkey_id:
            tk_root.after(0, _hotkey_snip)
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageA(ctypes.byref(msg))

    user32.UnregisterHotKey(None, hotkey_id)


def _hotkey_snip():
    from main_window import get_instance
    mw = get_instance()
    if mw:
        mw.start_snip(delay=0)


# ── System tray ───────────────────────────────────────────────────────────────

def _setup_tray(tk_root):
    try:
        import pystray

        png = _icon_path()
        if os.path.exists(png):
            icon_image = Image.open(png).convert("RGBA")
        else:
            icon_image = Image.new("RGBA", (64, 64), "#1E88E5")

        def on_open(_icon, _item):
            from main_window import get_instance
            mw = get_instance()
            if mw:
                tk_root.after(0, mw.show)

        def on_snip(_icon, _item):
            tk_root.after(0, _hotkey_snip)

        def on_exit(tray_icon, _item):
            tray_icon.stop()
            os._exit(0)

        menu = pystray.Menu(
            pystray.MenuItem("Open", on_open, default=True),
            pystray.MenuItem("New Snip  (Ctrl+Shift+S)", on_snip),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", on_exit),
        )
        icon = pystray.Icon(
            "ScreenshotTool", icon_image,
            f"Screenshot Tool v{__version__}", menu,
        )
        icon.run()
    except Exception as e:
        print(f"Tray setup failed: {e}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    if not _acquire_single_instance():
        ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
            None,
            "Screenshot Tool is already running.\n\nCheck the system tray.",
            "Screenshot Tool",
            0x40,
        )
        sys.exit(0)

    print(f"Screenshot Tool v{__version__} started")
    print(f"Save folder : {SAVE_DIR}")
    print(f"Hotkey      : Ctrl+Shift+S")

    import tkinter as tk
    tk_root = tk.Tk()
    tk_root.withdraw()

    # Set icon on the hidden root so Toplevel windows inherit it
    _base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    _ico = os.path.join(_base, "screenshot_tool_icon.ico")
    if os.path.exists(_ico):
        tk_root.iconbitmap(_ico)

    # Hotkey listener on background thread
    threading.Thread(target=_hotkey_loop, args=(tk_root,), daemon=True).start()

    # System tray on background thread
    threading.Thread(target=_setup_tray, args=(tk_root,), daemon=True).start()

    # Show the home window
    from main_window import MainWindow
    MainWindow(tk_root, str(SAVE_DIR))

    tk_root.mainloop()


if __name__ == "__main__":
    main()
