@echo off
:: ============================================================
:: build.bat — builds ScreenshotTool and installer
:: Run from the project folder:  build.bat
:: Requires:
::   pip install pyinstaller
::   Inno Setup 6  (https://jrsoftware.org/isinfo.php)
:: ============================================================

:: Read version from version.py
for /f "tokens=3 delims= " %%v in ('findstr "__version__" version.py') do set VERSION=%%~v

echo ============================================================
echo  Building Screenshot Tool v%VERSION%
echo ============================================================
echo.

:: ── Step 1: PyInstaller ──────────────────────────────────────
echo [1/3] Cleaning previous build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [1/3] Running PyInstaller...
pyinstaller ^
    --onedir ^
    --windowed ^
    --name=ScreenshotTool ^
    --add-data="main_window.py;." ^
    --add-data="config.py;." ^
    --icon=screenshot_tool_icon.ico ^
    --add-data="screenshot_tool_icon.ico;." ^
    --add-data="screenshot_tool_icon.png;." ^
    --hidden-import=PIL._tkinter_finder ^
    --collect-all=PIL ^
    --collect-all=pystray ^
    --hidden-import=pystray._win32 ^
    --hidden-import=win32api ^
    --hidden-import=win32con ^
    --hidden-import=win32gui ^
    --hidden-import=win32gui_struct ^
    --hidden-import=win32clipboard ^
    main.py

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)
echo [1/3] PyInstaller complete.
echo.

:: ── Step 2: Inno Setup installer ─────────────────────────────
echo [2/3] Building installer with Inno Setup...

set ISCC=""
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set ISCC="%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"

if %ISCC%=="" (
    echo.
    echo WARNING: Inno Setup 6 not found. Skipping installer creation.
    echo          Download from: https://jrsoftware.org/isinfo.php
    echo          Then re-run build.bat.
    echo.
    goto :zips
)

%ISCC% /DMyAppVersion=%VERSION% installer.iss
if errorlevel 1 (
    echo.
    echo ERROR: Inno Setup build failed.
    pause
    exit /b 1
)
echo [2/3] Installer created: dist\ScreenshotToolSetup.exe
echo.

:: ── Step 3: Create zips ──────────────────────────────────────
:zips
echo [3/3] Creating zip archives...

powershell -Command "Compress-Archive -Path 'dist\ScreenshotTool\ScreenshotTool.exe' -DestinationPath 'dist\ScreenshotTool.zip' -Force"
echo   Created: dist\ScreenshotTool.zip  (auto-updater)

powershell -Command "Compress-Archive -Path 'dist\ScreenshotTool' -DestinationPath 'dist\ScreenshotTool_FullInstall.zip' -Force"
echo   Created: dist\ScreenshotTool_FullInstall.zip  (manual install)

echo.
echo ============================================================
echo  Build complete — v%VERSION%
echo ============================================================
echo.
echo  dist\ScreenshotTool\ScreenshotTool.exe        ^<-- test this first
echo  dist\ScreenshotToolSetup.exe                   ^<-- installer
echo  dist\ScreenshotTool.zip                        ^<-- auto-updater zip
echo  dist\ScreenshotTool_FullInstall.zip            ^<-- manual install zip
echo.
echo  Upload to GitHub Release:
echo    - ScreenshotTool.zip          (required for auto-updater)
echo    - ScreenshotToolSetup.exe     (recommended for new users)
echo.
pause
