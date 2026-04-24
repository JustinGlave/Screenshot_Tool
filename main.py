"""Screenshot Tool – main entry point.

Launch:  python main.py
Hotkey:  Ctrl+Shift+S  (system-wide, starts a new snip)
"""

import os
import sys
import datetime
import threading
from pathlib import Path
from PIL import Image
from version import __version__

# ── Config ───────────────────────────────────────────────────────────────────
SAVE_DIR = Path.home() / "Pictures" / "Screenshots"
SAVE_DIR.mkdir(parents=True, exist_ok=True)

HOTKEY = "<ctrl>+<shift>+s"


# ── Helpers ──────────────────────────────────────────────────────────────────

def auto_save(image: Image.Image, save_dir=None) -> str:
    folder = Path(save_dir) if save_dir else SAVE_DIR
    folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = folder / f"screenshot_{timestamp}.png"
    image.convert("RGB").save(str(path))
    return str(path)


def start_capture(on_capture=None):
    """Open the fullscreen overlay; call on_capture(image) when done."""
    from capture_overlay import CaptureOverlay

    def capture_and_open(image):
        path = auto_save(image)
        if on_capture:
            on_capture(image, path)
        else:
            open_editor(image, path)

    CaptureOverlay(capture_and_open)


def open_editor(image: Image.Image, auto_saved_path: str = None):
    from editor_window import EditorWindow
    EditorWindow(image, str(SAVE_DIR), auto_saved_path)


# ── Global hotkey listener ────────────────────────────────────────────────────

def _setup_hotkey():
    try:
        from pynput import keyboard

        combo = {keyboard.Key.ctrl, keyboard.Key.shift, keyboard.KeyCode.from_char("s")}
        current = set()

        def on_press(key):
            current.add(key)
            if all(k in current for k in combo):
                threading.Thread(target=start_capture, daemon=True).start()

        def on_release(key):
            current.discard(key)

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.daemon = True
        listener.start()
        return listener
    except Exception as e:
        print(f"Hotkey setup failed: {e}")
        return None


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print(f"Screenshot Tool started")
    print(f"Save folder : {SAVE_DIR}")
    print(f"Hotkey      : Ctrl+Shift+S")
    print(f"Starting capture overlay…\n")

    # Start hotkey listener in background
    _setup_hotkey()

    # Launch first snip immediately
    start_capture()


if __name__ == "__main__":
    main()
