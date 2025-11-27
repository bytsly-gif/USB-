#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试看门狗功能
"""
import sys
import os
sys.path.append('.')

from usb_manager_enhanced import permission_manager, watchdog, exit_allowed

def test_watchdog():
    print("=== 看门狗功能测试 ===")
    print(f"看门狗状态: {'运行中' if watchdog.running else '已停止'}")
    print(f"退出权限: {'允许' if exit_allowed else '禁止'}")
    
    # 测试权限检查
    print(f"当前用户: {permission_manager.current_user}")
    print(f"是否已认证: {permission_manager.is_authenticated}")
    
    # 启动看门狗
    if not watchdog.running:
        watchdog.start()
        print("看门狗已启动")
    
    print("测试完成，按Ctrl+C测试信号处理...")
    
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n收到中断信号，退出权限: {'允许' if exit_allowed else '禁止'}")
        if not exit_allowed:
            print("程序受保护，无法终止")
            return False
        else:
            print("程序正常退出")
            return True

if __name__ == "__main__":
    test_watchdog()