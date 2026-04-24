# Screenshot Tool

A lightweight screenshot and annotation tool for Windows, inspired by the Windows Snipping Tool.

## Features

- **Click and drag** to capture any region of the screen
- **Auto-saves** every capture to `~/Pictures/Screenshots/`
- **System tray** — app lives in the tray after launch; right-click for New Snip or Exit
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

The capture overlay opens immediately. Click and drag to select a region, then annotate in the editor.

## Dependencies

| Package | Purpose |
|---|---|
| Pillow | Image processing and drawing |
| mss | Fast multi-monitor screen capture |
| pynput | Global hotkey listener |
| pywin32 | Copy to clipboard on Windows |
