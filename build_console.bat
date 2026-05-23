@echo off
REM Campus Network Keep-Alive console build script for debugging.

echo ============================================
echo Building Console Version
echo ============================================
echo.

echo Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo Generating icons...
python scripts\generate_icons.py
if errorlevel 1 (
    echo Failed to generate icons
    pause
    exit /b 1
)

echo.
echo Building debug EXE...
pyinstaller ^
    --onefile ^
    --console ^
    --name "KeepAlive_Debug" ^
    --icon "assets\icon.ico" ^
    --add-data "assets;assets" ^
    --add-data "config.example.yaml;." ^
    src\keepalive.py
if errorlevel 1 (
    echo Build failed
    pause
    exit /b 1
)

echo.
echo Build complete: dist\KeepAlive_Debug.exe
pause
