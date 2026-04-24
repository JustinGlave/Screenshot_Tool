"""Screenshot Tool — main entry point.

The app lives in the system tray after first launch.
Hotkey: Ctrl+Shift+S — triggers a new snip from anywhere.
Only one instance is allowed at a time.
"""

import os
import sys
import ctypes
import ctypes.wintypes
import datetime
import threading
import queue
from pathlib import Path
from PIL import Image
from version import __version__

# Must be called before any UI or screen capture — makes tkinter and
# ImageGrab agree on pixel coordinates on high-DPI displays.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# ── Config ────────────────────────────────────────────────────────────────────
SAVE_DIR = Path.home() / "Pictures" / "Screenshots"
SAVE_DIR.mkdir(parents=True, exist_ok=True)

# ── State ─────────────────────────────────────────────────────────────────────
_capture_queue = queue.Queue()
_busy = False
_mutex_handle = None  # kept alive for the lifetime of the process


# ── Single instance enforcement ───────────────────────────────────────────────

def _acquire_single_instance():
    """
    Create a named Windows mutex. Returns True if this is the first instance,
    False if another instance is already running.
    """
    global _mutex_handle
    ERROR_ALREADY_EXISTS = 183
    _mutex_handle = ctypes.windll.kernel32.CreateMutexW(
        None, False, "ScreenshotTool_SingleInstance_Mutex"
    )
    return ctypes.windll.kernel32.GetLastError() != ERROR_ALREADY_EXISTS


# ── Helpers ───────────────────────────────────────────────────────────────────

def _icon_path():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "screenshot_tool_icon.png")


def auto_save(image: Image.Image, save_dir=None) -> str:
    folder = Path(save_dir) if save_dir else SAVE_DIR
    folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = folder / f"screenshot_{timestamp}.png"
    image.convert("RGB").save(str(path))
    return str(path)


def trigger_capture():
    """Queue a capture — ignored if one is already in progress."""
    if not _busy:
        _capture_queue.put(True)


def start_capture():
    from capture_overlay import CaptureOverlay

    def capture_and_open(image):
        path = auto_save(image)
        open_editor(image, path)

    CaptureOverlay(capture_and_open)


def open_editor(image: Image.Image, auto_saved_path: str = None):
    from editor_window import EditorWindow
    EditorWindow(image, str(SAVE_DIR), auto_saved_path)


# ── Global hotkey via Win32 RegisterHotKey ────────────────────────────────────

def _hotkey_loop():
    MOD_CONTROL = 0x0002
    MOD_SHIFT   = 0x0004
    VK_S        = 0x53
    HOTKEY_ID   = 1
    WM_HOTKEY   = 0x0312

    user32 = ctypes.windll.user32
    if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_SHIFT, VK_S):
        print("Could not register Ctrl+Shift+S — may already be in use by another app.")
        return

    msg = ctypes.wintypes.MSG()
    while user32.GetMessageA(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
            trigger_capture()
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageA(ctypes.byref(msg))

    user32.UnregisterHotKey(None, HOTKEY_ID)


# ── System tray ───────────────────────────────────────────────────────────────

def _setup_tray():
    try:
        import pystray

        png = _icon_path()
        if os.path.exists(png):
            icon_image = Image.open(png).convert("RGBA")
        else:
            # Fallback: plain coloured square so the tray entry is always visible
            icon_image = Image.new("RGBA", (64, 64), "#1E88E5")

        def on_snip(icon, item):
            trigger_capture()

        def on_exit(icon, item):
            icon.stop()
            os._exit(0)

        menu = pystray.Menu(
            pystray.MenuItem("New Snip  (Ctrl+Shift+S)", on_snip, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", on_exit),
        )
        icon = pystray.Icon(
            "ScreenshotTool",
            icon_image,
            f"Screenshot Tool v{__version__}",
            menu,
        )
        icon.run()
    except Exception as e:
        print(f"Tray setup failed: {e}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    if not _acquire_single_instance():
        ctypes.windll.user32.MessageBoxW(
            None,
            "Screenshot Tool is already running.\n\nCheck the system tray.",
            "Screenshot Tool",
            0x40,  # MB_ICONINFORMATION
        )
        sys.exit(0)

    print(f"Screenshot Tool v{__version__} started")
    print(f"Save folder : {SAVE_DIR}")
    print(f"Hotkey      : Ctrl+Shift+S")

    # Hotkey listener — Win32 message pump on background thread
    threading.Thread(target=_hotkey_loop, daemon=True).start()

    # System tray — keeps the app alive in the background
    threading.Thread(target=_setup_tray, daemon=True).start()

    # Trigger the first capture immediately on launch
    trigger_capture()

    # Main loop — wait for capture triggers from hotkey or tray
    global _busy
    while True:
        _capture_queue.get()
        _busy = True
        try:
            start_capture()
        finally:
            _busy = False


if __name__ == "__main__":
    main()
