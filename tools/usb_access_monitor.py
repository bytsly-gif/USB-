import os
import sys
import time
import threading
import ctypes
import winreg
from ctypes import wintypes
import tkinter as tk
from tkinter import messagebox

# Windows API常量
FILE_READ_DATA = 0x0001
FILE_WRITE_DATA = 0x0002
FILE_APPEND_DATA = 0x0004
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
GENERIC_ALL = 0x10000000

OPEN_EXISTING = 3
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_ATTRIBUTE_NORMAL = 0x00000080

class USBAccessMonitor:
    def __init__(self, permission_manager):
        self.permission_manager = permission_manager
        self.monitoring = False
        self.monitor_thread = None
        self.usb_drives = set()
        
    def get_usb_drives(self):
        """获取所有USB驱动器"""
        usb_drives = []
        drives = ['A:', 'B:', 'C:', 'D:', 'E:', 'F:', 'G:', 'H:', 'I:', 'J:', 'K:', 'L:', 'M:', 
                 'N:', 'O:', 'P:', 'Q:', 'R:', 'S:', 'T:', 'U:', 'V:', 'W:', 'X:', 'Y:', 'Z:']
        
        for drive in drives:
            if os.path.exists(drive):
                try:
                    # 检查是否为可移动磁盘
                    drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive + '\\')
                    if drive_type == 2:  # DRIVE_REMOVABLE
                        usb_drives.append(drive)
                except:
                    pass
        
        return usb_drives
    
    def start_monitoring(self):
        """开始监控USB访问"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("USB访问监控已启动")
    
    def stop_monitoring(self):
        """停止监控USB访问"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
        print("USB访问监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                # 检查当前USB驱动器
                current_drives = set(self.get_usb_drives())
                
                # 如果是访问员权限，监控文件操作
                if (self.permission_manager.current_user == "visitor" and 
                    self.permission_manager.is_authenticated):
                    self._monitor_file_access(current_drives)
                
                time.sleep(1)  # 每秒检查一次
                
            except Exception as e:
                print(f"监控错误: {e}")
                time.sleep(5)
    
    def _monitor_file_access(self, drives):
        """监控文件访问（简化版本）"""
        for drive in drives:
            try:
                drive_path = drive + '\\'
                # 这里可以实现更复杂的文件访问监控
                # 由于Windows文件系统监控比较复杂，这里提供基础框架
                pass
            except Exception as e:
                print(f"监控驱动器 {drive} 时出错: {e}")

class USBWriteProtector:
    """USB写入保护器"""
    
    def __init__(self, permission_manager):
        self.permission_manager = permission_manager
        self.protection_active = False
        
    def enable_write_protection(self):
        """启用写入保护（访问员模式）"""
        if self.permission_manager.current_user != "visitor":
            return False
        
        try:
            # 方法1：通过注册表禁用USB写入
            self._set_registry_write_protection(1)
            self.protection_active = True
            return True
        except Exception as e:
            print(f"启用写入保护失败: {e}")
            return False
    
    def disable_write_protection(self):
        """禁用写入保护"""
        try:
            self._set_registry_write_protection(0)
            self.protection_active = False
            return True
        except Exception as e:
            print(f"禁用写入保护失败: {e}")
            return False
    
    def _set_registry_write_protection(self, enable):
        """通过注册表设置写入保护"""
        try:
            # 创建或打开注册表项
            key_path = r"SYSTEM\CurrentControlSet\Control\StorageDevicePolicies"
            
            try:
                key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key_path)
            except:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_SET_VALUE)
            
            # 设置WriteProtect值
            winreg.SetValueEx(key, "WriteProtect", 0, winreg.REG_DWORD, enable)
            key.Close()
            
        except Exception as e:
            raise Exception(f"注册表操作失败: {e}")

def create_access_monitor_gui(permission_manager):
    """创建访问监控的GUI界面"""
    root = tk.Tk()
    root.title("USB访问监控")
    root.geometry("400x300")
    
    monitor = USBAccessMonitor(permission_manager)
    protector = USBWriteProtector(permission_manager)
    
    frame = tk.Frame(root, padx=15, pady=15)
    frame.pack(fill=tk.BOTH, expand=True)
    
    # 状态显示
    status_label = tk.Label(frame, text="监控状态: 未启动", font=("微软雅黑", 10))
    status_label.pack(pady=(0, 10))
    
    protection_label = tk.Label(frame, text="写入保护: 未启用", font=("微软雅黑", 10))
    protection_label.pack(pady=(0, 15))
    
    # 控制按钮
    def start_monitor():
        if not permission_manager.is_authenticated:
            messagebox.showwarning("未认证", "请先进行身份认证")
            return
        
        monitor.start_monitoring()
        status_label.config(text="监控状态: 运行中", foreground="green")
        
        # 如果是访问员，自动启用写入保护
        if permission_manager.current_user == "visitor":
            if protector.enable_write_protection():
                protection_label.config(text="写入保护: 已启用", foreground="orange")
                messagebox.showinfo("提示", "访问员模式：已启用USB写入保护\n只能读取U盘文件，无法写入")
    
    def stop_monitor():
        monitor.stop_monitoring()
        status_label.config(text="监控状态: 已停止", foreground="red")
        
        if protector.protection_active:
            protector.disable_write_protection()
            protection_label.config(text="写入保护: 已禁用", foreground="black")
    
    def toggle_protection():
        if not permission_manager.is_authenticated:
            messagebox.showwarning("未认证", "请先进行身份认证")
            return
        
        if permission_manager.current_user != "visitor":
            messagebox.showinfo("提示", "只有访问员模式需要写入保护")
            return
        
        if protector.protection_active:
            protector.disable_write_protection()
            protection_label.config(text="写入保护: 已禁用", foreground="black")
        else:
            if protector.enable_write_protection():
                protection_label.config(text="写入保护: 已启用", foreground="orange")
    
    btn_frame = tk.Frame(frame)
    btn_frame.pack(pady=10)
    
    start_btn = tk.Button(btn_frame, text="启动监控", width=12, command=start_monitor)
    start_btn.pack(side=tk.LEFT, padx=5)
    
    stop_btn = tk.Button(btn_frame, text="停止监控", width=12, command=stop_monitor)
    stop_btn.pack(side=tk.LEFT, padx=5)
    
    protection_btn = tk.Button(btn_frame, text="切换写入保护", width=12, command=toggle_protection)
    protection_btn.pack(side=tk.LEFT, padx=5)
    
    # USB驱动器列表
    drives_frame = tk.LabelFrame(frame, text="当前USB驱动器", padx=10, pady=10)
    drives_frame.pack(fill=tk.BOTH, expand=True, pady=(15, 0))
    
    drives_listbox = tk.Listbox(drives_frame, height=6)
    drives_listbox.pack(fill=tk.BOTH, expand=True)
    
    def refresh_drives():
        drives_listbox.delete(0, tk.END)
        drives = monitor.get_usb_drives()
        if drives:
            for drive in drives:
                drives_listbox.insert(tk.END, f"{drive}\\ - 可移动磁盘")
        else:
            drives_listbox.insert(tk.END, "未检测到USB驱动器")
    
    refresh_btn = tk.Button(drives_frame, text="刷新", command=refresh_drives)
    refresh_btn.pack(anchor='e', pady=(5, 0))
    
    # 初始刷新
    refresh_drives()
    
    # 说明文字
    info_text = """访问员权限说明：
• 只能读取U盘文件，无法写入或修改
• 写入保护通过注册表实现
• 管理员权限不受限制"""
    
    info_label = tk.Label(frame, text=info_text, justify=tk.LEFT, font=("微软雅黑", 9))
    info_label.pack(anchor='w', pady=(10, 0))
    
    return root

if __name__ == "__main__":
    # 测试用
    class MockPermissionManager:
        def __init__(self):
            self.current_user = "visitor"
            self.is_authenticated = True
    
    mock_manager = MockPermissionManager()
    root = create_access_monitor_gui(mock_manager)
    root.mainloop()