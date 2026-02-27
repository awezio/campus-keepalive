@echo off
REM Campus Network Keep-Alive Build Script
REM 校园网保活程序打包脚本

echo ============================================
echo Campus Network Keep-Alive Build Script
echo ============================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found in PATH
    pause
    exit /b 1
)

REM 检查 PyInstaller
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM 安装依赖
echo.
echo Installing dependencies...
pip install -r requirements.txt

REM 创建临时图标（如果不存在）
if not exist "assets\icon.ico" (
    echo.
    echo Creating default icon...
    python -c "
from PIL import Image, ImageDraw
img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)
draw.ellipse([20, 20, 236, 236], fill=(46, 204, 113), outline=(255, 255, 255), width=8)
draw.ellipse([60, 60, 196, 196], fill=(39, 174, 96))
img.save('assets/icon.ico', format='ICO')
print('Icon created: assets/icon.ico')
"
)

REM 打包
echo.
echo Building EXE...
pyinstaller ^
    --onefile ^
    --noconsole ^
    --name "KeepAlive" ^
    --icon "assets\icon.ico" ^
    --add-data "assets;assets" ^
    --hidden-import "pystray._win32" ^
    --hidden-import "PIL._tkinter_finder" ^
    src\keepalive.py

if errorlevel 1 (
    echo.
    echo Build failed!
    pause
    exit /b 1
)

echo.
echo ============================================
echo Build successful!
echo Output: dist\KeepAlive.exe
echo ============================================
echo.

REM 复制配置文件模板
if not exist "dist\config.example.yaml" (
    echo Creating example config...
    python -c "
import sys
sys.path.insert(0, 'src')
from config_manager import ConfigManager
manager = ConfigManager()
manager.create_example()
import shutil
shutil.copy('config.example.yaml', 'dist/config.example.yaml')
print('Config template copied to dist/')
"
)

echo.
echo To use:
echo   1. Copy dist\KeepAlive.exe to your desired location
echo   2. Copy config.example.yaml to config.yaml in the same folder
echo   3. Edit config.yaml with your campus network credentials
echo   4. Run KeepAlive.exe
echo.

pause
