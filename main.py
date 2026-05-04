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

try:
    RESAMPLE_LANCZOS = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE_LANCZOS = getattr(Image, "LANCZOS")

# Must be called before any UI or screen capture — makes tkinter and
# ImageGrab agree on pixel coordinates on high-DPI displays.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # type: ignore[attr-defined]
except (AttributeError, OSError):
    try:
        ctypes.windll.user32.SetProcessDPIAware()  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass


def _configure_tcl_tk_paths():
    base = Path(getattr(sys, "_MEIPASS", sys.base_prefix))
    tcl_root = base / "tcl"
    tcl_library = tcl_root / "tcl8.6"
    tk_library = tcl_root / "tk8.6"
    if tcl_library.exists():
        os.environ.setdefault("TCL_LIBRARY", str(tcl_library))
    if tk_library.exists():
        os.environ.setdefault("TK_LIBRARY", str(tk_library))


_configure_tcl_tk_paths()

import tkinter as tk

# ── Config ────────────────────────────────────────────────────────────────────
SAVE_DIR = Path.home() / "Pictures" / "Screenshots"
try:
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    SAVE_DIR = Path.home()

# ── State ─────────────────────────────────────────────────────────────────────
_mutex_handle = None  # keeps single-instance mutex alive
_shutdown_event = threading.Event()
_hotkey_thread_id = None


class AutoSaveError(RuntimeError):
    """Raised when a screenshot cannot be written to disk."""


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


def copy_image_to_clipboard(image: Image.Image) -> bool:
    """Copy a PIL image to the Windows clipboard as a DIB. Returns True on success."""
    import io
    import win32clipboard
    import pywintypes
    output = io.BytesIO()
    image.convert("RGB").save(output, format="BMP")
    data = output.getvalue()[14:]
    opened = False
    try:
        win32clipboard.OpenClipboard()
        opened = True
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        return True
    except pywintypes.error:
        return False
    finally:
        if opened:
            try:
                win32clipboard.CloseClipboard()
            except pywintypes.error:
                pass


def auto_save(image: Image.Image, save_dir=None) -> str:
    folder = Path(save_dir) if save_dir else SAVE_DIR
    try:
        folder.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
        path = folder / f"screenshot_{timestamp}.png"
        image.convert("RGB").save(str(path))
        return str(path)
    except OSError as exc:
        raise AutoSaveError(f"Could not save screenshot to {folder}:\n{exc}") from exc


def _schedule_on_tk(tk_root, callback):
    if _shutdown_event.is_set():
        return
    try:
        if tk_root.winfo_exists():
            tk_root.after(0, callback)
    except tk.TclError:
        pass


def request_shutdown(tk_root=None, tray_icon=None):
    _shutdown_event.set()
    if tray_icon is not None:
        try:
            tray_icon.stop()
        except AttributeError:
            pass

    thread_id = _hotkey_thread_id
    if thread_id:
        try:
            post_thread_message = getattr(ctypes.windll.user32, "PostThreadMessageW")
            post_thread_message(thread_id, 0x0012, 0, 0)  # WM_QUIT
        except (AttributeError, OSError):
            pass

    if tk_root is not None:
        try:
            if tk_root.winfo_exists():
                tk_root.after(0, tk_root.destroy)
        except tk.TclError:
            pass


# ── Global hotkey via Win32 RegisterHotKey ────────────────────────────────────

def _hotkey_loop(tk_root):
    global _hotkey_thread_id
    mod_control = 0x0002
    mod_shift   = 0x0004
    vk_s        = 0x53
    hotkey_id   = 1
    wm_hotkey   = 0x0312
    _hotkey_thread_id = ctypes.windll.kernel32.GetCurrentThreadId()  # type: ignore[attr-defined]

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    if not user32.RegisterHotKey(None, hotkey_id, mod_control | mod_shift, vk_s):  # type: ignore[attr-defined]
        print("Could not register Ctrl+Shift+S — may already be in use by another app.")
        return

    msg = ctypes.wintypes.MSG()
    try:
        while not _shutdown_event.is_set() and user32.GetMessageA(ctypes.byref(msg), None, 0, 0) != 0:  # type: ignore[attr-defined]
            if msg.message == wm_hotkey and msg.wParam == hotkey_id:
                _schedule_on_tk(tk_root, _hotkey_snip)
            user32.TranslateMessage(ctypes.byref(msg))  # type: ignore[attr-defined]
            user32.DispatchMessageA(ctypes.byref(msg))  # type: ignore[attr-defined]
    finally:
        user32.UnregisterHotKey(None, hotkey_id)  # type: ignore[attr-defined]


def _hotkey_snip():
    from editor_window import get_editor_instance
    editor = get_editor_instance()
    if editor is not None:
        try:
            if editor._root_exists():
                editor._new_snip()
                return
        except Exception:
            pass
    from main_window import get_instance
    mw = get_instance()
    if mw:
        mw.start_snip(delay=0)


# ── System tray ───────────────────────────────────────────────────────────────

def _setup_tray(tk_root):
    try:
        import pystray
    except ImportError as e:
        print(f"Tray setup failed: {e}")
        return

    try:
        png = _icon_path()
        if os.path.exists(png):
            icon_image = Image.open(png).convert("RGBA").resize((64, 64), RESAMPLE_LANCZOS)
        else:
            icon_image = Image.new("RGBA", (64, 64), "#1E88E5")

        def on_open(_icon, _item):
            from main_window import get_instance
            mw = get_instance()
            if mw:
                _schedule_on_tk(tk_root, mw.show)

        def on_snip(_icon, _item):
            _schedule_on_tk(tk_root, _hotkey_snip)

        def on_exit(tray_icon, _item):
            request_shutdown(tk_root, tray_icon)

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
    except OSError as e:
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
