@echo off
REM Campus Network Keep-Alive build script.

echo ============================================
echo Campus Network Keep-Alive Build Script
echo ============================================
echo.

REM Check Python.
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found in PATH
    pause
    exit /b 1
)

REM Check PyInstaller.
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

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
echo Building EXE...
pyinstaller KeepAlive.spec --clean
if errorlevel 1 (
    echo.
    echo Build failed!
    pause
    exit /b 1
)

if not exist "dist" mkdir "dist"
copy /Y "config.example.yaml" "dist\config.example.yaml" >nul
if errorlevel 1 (
    echo Failed to copy config.example.yaml
    pause
    exit /b 1
)

echo.
echo ============================================
echo Build successful!
echo Output: dist\KeepAlive.exe
echo ============================================
echo.
echo To use:
echo   1. Run dist\KeepAlive.exe
echo   2. Use Settings to configure campus network credentials if needed
echo   3. Keep dist\config.example.yaml as the editable template
echo.

pause
