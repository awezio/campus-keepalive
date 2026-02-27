@echo off
chcp 65001 >nul
echo ========================================
echo KeepAlive - 版本回退工具
echo ========================================
echo.

if "%1"=="" (
    echo 用法: rollback.bat [备份目录名]
    echo.
    echo 可用备份版本:
    dir /b /ad backup_* 2>nul
    echo.
    echo 示例: rollback.bat backup_20260228_012032
    pause
    exit /b 1
)

set BACKUP_DIR=%1

if not exist "%BACKUP_DIR%" (
    echo [错误] 备份目录不存在: %BACKUP_DIR%
    pause
    exit /b 1
)

echo [确认] 将从 %BACKUP_DIR% 恢复源代码和配置
echo.
echo 这将会覆盖当前目录下的 src/ 和 KeepAlive.spec
echo.
set /p CONFIRM=确认回退？(Y/N):

if /i not "%CONFIRM%"=="Y" (
    echo [取消] 回退操作已取消
    pause
    exit /b 0
)

echo.
echo [步骤 1/3] 恢复源代码...
xcopy /E /I /Y "%BACKUP_DIR%\src" "src" >nul
if %errorlevel% neq 0 (
    echo [错误] 源代码恢复失败
    pause
    exit /b 1
)
echo [完成] src/ 已恢复

echo [步骤 2/3] 恢复配置文件...
copy /Y "%BACKUP_DIR%\KeepAlive.spec" "KeepAlive.spec" >nul
copy /Y "%BACKUP_DIR%\config.yaml" "config.yaml" >nul
echo [完成] 配置文件已恢复

echo [步骤 3/3] 重新打包 EXE...
pyinstaller KeepAlive.spec --clean
if %errorlevel% neq 0 (
    echo [错误] EXE 打包失败
    pause
    exit /b 1
)
echo [完成] EXE 已重新打包

echo.
echo ========================================
echo 回退成功！
echo ========================================
echo.
echo 已恢复到版本: %BACKUP_DIR%
echo 新 EXE 位置: dist\KeepAlive.exe
echo.
pause
