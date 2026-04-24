# Screenshot Tool

A lightweight screenshot and annotation tool for Windows, inspired by the Windows Snipping Tool.

## Features

- **Click and drag** to capture any region of the screen
- **Auto-saves** every capture to `~/Pictures/Screenshots/`
- **Home window** — app opens to a launcher with Snip Now, 3s Timer, and 5s Timer buttons
- **Capture timer** — 3 or 5 second countdown with a corner overlay before capture begins
- **Custom save location** — choose any folder from the home window; persists between sessions
- **System tray** — app lives in the tray after the home window is closed; right-click for Open, New Snip, or Exit
- **Global hotkey** — `Ctrl+Shift+S` triggers a new snip from anywhere, even when minimized to tray
- **Annotation tools:**
  - Pen — freehand drawing
  - Marker — semi-transparent highlight
  - Eraser — erase to white or erase to original screenshot
  - Line, Arrow, Rectangle, Ellipse
  - Text
- **10 preset colors** + custom color picker
- **6 brush sizes** + opacity slider for the marker
- **Undo / Redo** (Ctrl+Z / Ctrl+Y, up to 50 steps)
- **Copy to clipboard** (Ctrl+C)
- **Save As** dialog (Ctrl+S)
- **New Snip** button to capture again without reopening

## Requirements

- Python 3.10+
- Windows 10 / 11

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

The app opens to the home window. Choose Snip Now, 3s Timer, or 5s Timer — or use the global hotkey `Ctrl+Shift+S` from anywhere. After capture, annotate in the editor, then copy or save.

## Dependencies

| Package | Purpose |
|---|---|
| Pillow | Image capture, processing, and drawing |
| pystray | System tray icon |
| pywin32 | Clipboard support and Win32 API access |
