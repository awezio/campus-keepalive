@echo off
REM Campus Network Keep-Alive Build Script (Console Version)
REM 带控制台窗口的版本，便于调试

echo ============================================
echo Building Console Version (for debugging)
echo ============================================
echo.

REM 安装依赖
pip install -r requirements.txt

REM 创建临时图标
if not exist "assets\icon.ico" (
    python -c "
from PIL import Image, ImageDraw
img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)
draw.ellipse([20, 20, 236, 236], fill=(46, 204, 113), outline=(255, 255, 255), width=8)
draw.ellipse([60, 60, 196, 196], fill=(39, 174, 96))
img.save('assets/icon.ico', format='ICO')
"
)

REM 打包（带控制台）
pyinstaller ^
    --onefile ^
    --console ^
    --name "KeepAlive_Debug" ^
    --icon "assets\icon.ico" ^
    --add-data "assets;assets" ^
    --hidden-import "pystray._win32" ^
    --hidden-import "PIL._tkinter_finder" ^
    src\keepalive.py

echo.
echo Build complete: dist\KeepAlive_Debug.exe
pause
