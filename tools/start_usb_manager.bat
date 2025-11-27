@echo off
echo =============================================
echo USB存储设备权限管理器
echo =============================================
echo.

echo 选择要启动的版本:
echo 1. 基础版本 (tools\usb_manager.py)
echo 2. 增强版本 (usb_manager_enhanced.py) - 主程序
echo 3. 完整版本 (tools\usb_manager_complete.py)
echo 4. 访问监控器 (tools\usb_access_monitor.py)
echo 5. 看门狗测试 (tools\test_watchdog.py)
echo.

set /p choice="请输入选择 (1-5): "

if "%choice%"=="1" (
    echo 启动基础版本...
    python tools\usb_manager.py
) else if "%choice%"=="2" (
    echo 启动增强版本...
    python usb_manager_enhanced.py
) else if "%choice%"=="3" (
    echo 启动完整版本...
    python tools\usb_manager_complete.py
) else if "%choice%"=="4" (
    echo 启动访问监控器...
    python tools\usb_access_monitor.py
) else if "%choice%"=="5" (
    echo 启动看门狗测试...
    python tools\test_watchdog.py
) else (
    echo 无效选择，启动主程序...
    python usb_manager_enhanced.py
)

pause