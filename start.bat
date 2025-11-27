@echo off
echo =============================================
echo USB存储设备权限管理器 - 主程序
echo =============================================
echo.

echo 启动主程序 (usb_manager_enhanced.py)...
echo.

python usb_manager_enhanced.py

if errorlevel 1 (
    echo.
    echo 程序运行出错，请检查Python环境和依赖库
    echo.
    pause
)