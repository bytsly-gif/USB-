import os
import sys
import tkinter as tk
from tkinter import messagebox, ttk
import ctypes
import winreg
import hashlib
import json
import threading
import time

# 路径设置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PASSWORD_FILE = os.path.join(BASE_DIR, "admin_password.json")

# 注册表路径
REG_PATH = r"SYSTEM\CurrentControlSet\Services\USBSTOR"
REG_VALUE = "Start"
WRITE_PROTECT_PATH = r"SYSTEM\CurrentControlSet\Control\StorageDevicePolicies"

class USBPermissionManager:
    """USB权限管理器"""
    
    def __init__(self):
        self.current_user = None  # None, "visitor", "admin"
        self.is_authenticated = False
        self.password_file = PASSWORD_FILE
        self.monitoring = False
        self.write_protection_active = False
        
    def hash_password(self, password):
        """密码哈希"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def load_admin_password(self):
        """加载管理员密码"""
        try:
            if os.path.exists(self.password_file):
                with open(self.password_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("admin_password")
        except:
            pass
        # 默认密码
        return self.hash_password("admin123")
    
    def save_admin_password(self, password_hash):
        """保存管理员密码"""
        try:
            data = {}
            if os.path.exists(self.password_file):
                with open(self.password_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            data["admin_password"] = password_hash
            
            with open(self.password_file, 'w', encoding='utf-8') as f:
                json.dump(data, f)
            return True
        except Exception as e:
            messagebox.showerror("错误", f"保存密码失败: {e}")
            return False
    
    def authenticate_admin(self, password):
        """验证管理员密码"""
        saved_hash = self.load_admin_password()
        if self.hash_password(password) == saved_hash:
            self.current_user = "admin"
            self.is_authenticated = True
            self._apply_user_permissions()
            return True
        return False
    
    def authenticate_visitor(self):
        """访问员认证（无需密码）"""
        self.current_user = "visitor"
        self.is_authenticated = True
        self._apply_user_permissions()
        return True
    
    def logout(self):
        """登出"""
        self._cleanup_permissions()
        self.current_user = None
        self.is_authenticated = False
    
    def _apply_user_permissions(self):
        """应用用户权限"""
        if self.current_user == "visitor":
            # 访问员：启用写入保护
            self._enable_write_protection()
        elif self.current_user == "admin":
            # 管理员：禁用写入保护
            self._disable_write_protection()
    
    def _cleanup_permissions(self):
        """清理权限设置"""
        self._disable_write_protection()
    
    def _enable_write_protection(self):
        """启用USB写入保护"""
        try:
            key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, WRITE_PROTECT_PATH)
            winreg.SetValueEx(key, "WriteProtect", 0, winreg.REG_DWORD, 1)
            key.Close()
            self.write_protection_active = True
            return True
        except Exception as e:
            print(f"启用写入保护失败: {e}")
            return False
    
    def _disable_write_protection(self):
        """禁用USB写入保护"""
        try:
            key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, WRITE_PROTECT_PATH)
            winreg.SetValueEx(key, "WriteProtect", 0, winreg.REG_DWORD, 0)
            key.Close()
            self.write_protection_active = False
            return True
        except Exception as e:
            print(f"禁用写入保护失败: {e}")
            return False
    
    def can_write_usb(self):
        """检查是否有USB写入权限"""
        return self.current_user == "admin"
    
    def can_read_usb(self):
        """检查是否有USB读取权限"""
        return self.is_authenticated  # 访问员和管理员都可以读取
    
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

# 全局权限管理器
permission_manager = USBPermissionManager()

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def read_usb_status():
    """读取USB存储服务的启动类型"""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_PATH) as key:
            value, regtype = winreg.QueryValueEx(key, REG_VALUE)
            if value == 3:
                return "当前状态：已启用(值=3)"
            elif value == 4:
                return "当前状态：已禁用(值=4)"
            else:
                return f"当前状态：未知(值={value})"
    except PermissionError:
        return "无法读取状态：需要管理员权限"
    except FileNotFoundError:
        return "无法读取状态：注册表项不存在"
    except Exception as e:
        return f"读取状态异常：{e}"

def set_usb_start(value: int):
    """设置USB存储服务启动类型"""
    access = winreg.KEY_SET_VALUE
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_PATH, 0, access) as key:
        winreg.SetValueEx(key, REG_VALUE, 0, winreg.REG_DWORD, int(value))

def elevate_and_set(value: int) -> bool:
    """以管理员权限执行设置"""
    script = os.path.abspath(__file__)
    exe_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(exe_dir, 'pythonw.exe')
    interpreter = pythonw if os.path.exists(pythonw) else sys.executable
    params = f'"{script}" --set {int(value)}'
    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", interpreter, params, BASE_DIR, 0)
    return ret > 32

def on_enable():
    """启用USB存储"""
    if not permission_manager.is_authenticated:
        messagebox.showwarning("未认证", "请先进行身份认证")
        return
    
    if not permission_manager.can_write_usb():
        messagebox.showwarning("权限不足", "访问员权限无法修改USB设置，需要管理员权限")
        return
    
    if is_admin():
        try:
            set_usb_start(3)
            messagebox.showinfo("完成", "USB存储已启用(值=3)。")
        except PermissionError:
            messagebox.showerror("权限不足", "需要管理员权限才能写入注册表。")
        except Exception as e:
            messagebox.showerror("异常", f"设置失败：{e}")
        finally:
            status_var.set(read_usb_status())
    else:
        if elevate_and_set(3):
            messagebox.showinfo("已请求", "已请求以管理员身份启用USB。")
            if 'root' in globals() and isinstance(root, tk.Tk):
                root.after(1500, lambda: status_var.set(read_usb_status()))
        else:
            messagebox.showerror("执行失败", "无法触发管理员提升。")

def on_disable():
    """禁用USB存储"""
    if not permission_manager.is_authenticated:
        messagebox.showwarning("未认证", "请先进行身份认证")
        return
    
    if not permission_manager.can_write_usb():
        messagebox.showwarning("权限不足", "访问员权限无法修改USB设置，需要管理员权限")
        return
    
    if is_admin():
        try:
            set_usb_start(4)
            messagebox.showinfo("完成", "USB存储已禁用(值=4)。")
        except PermissionError:
            messagebox.showerror("权限不足", "需要管理员权限才能写入注册表。")
        except Exception as e:
            messagebox.showerror("异常", f"设置失败：{e}")
        finally:
            status_var.set(read_usb_status())
    else:
        if elevate_and_set(4):
            messagebox.showinfo("已请求", "已请求以管理员身份禁用USB。")
            if 'root' in globals() and isinstance(root, tk.Tk):
                root.after(1500, lambda: status_var.set(read_usb_status()))
        else:
            messagebox.showerror("执行失败", "无法触发管理员提升。")

def show_admin_login():
    """显示管理员登录对话框"""
    dialog = tk.Toplevel(root)
    dialog.title("管理员登录")
    dialog.geometry("300x150")
    dialog.resizable(False, False)
    dialog.transient(root)
    dialog.grab_set()
    
    # 居中显示
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
    y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
    dialog.geometry(f"+{x}+{y}")
    
    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)
    
    ttk.Label(frame, text="管理员密码:", font=("微软雅黑", 10)).pack(pady=(0, 5))
    
    password_var = tk.StringVar()
    password_entry = ttk.Entry(frame, textvariable=password_var, show="*", width=25)
    password_entry.pack(pady=(0, 15))
    password_entry.focus()
    
    def login():
        password = password_var.get()
        if not password:
            messagebox.showerror("错误", "请输入密码")
            return
        
        if permission_manager.authenticate_admin(password):
            messagebox.showinfo("成功", "管理员登录成功！\n权限：完全控制USB读写和设置")
            update_ui_state()
            dialog.destroy()
        else:
            messagebox.showerror("错误", "密码错误")
    
    def cancel():
        dialog.destroy()
    
    btn_frame = ttk.Frame(frame)
    btn_frame.pack()
    
    ttk.Button(btn_frame, text="登录", command=login, width=10).grid(row=0, column=0, padx=5)
    ttk.Button(btn_frame, text="取消", command=cancel, width=10).grid(row=0, column=1, padx=5)
    
    password_entry.bind('<Return>', lambda e: login())
    dialog.bind('<Escape>', lambda e: cancel())

def show_change_password():
    """显示修改密码对话框"""
    if not permission_manager.is_authenticated or permission_manager.current_user != "admin":
        messagebox.showwarning("权限不足", "只有管理员可以修改密码")
        return
    
    dialog = tk.Toplevel(root)
    dialog.title("修改管理员密码")
    dialog.geometry("350x200")
    dialog.resizable(False, False)
    dialog.transient(root)
    dialog.grab_set()
    
    # 居中显示
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
    y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
    dialog.geometry(f"+{x}+{y}")
    
    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)
    
    ttk.Label(frame, text="当前密码:", font=("微软雅黑", 10)).pack(pady=(0, 5))
    current_var = tk.StringVar()
    current_entry = ttk.Entry(frame, textvariable=current_var, show="*", width=25)
    current_entry.pack(pady=(0, 10))
    
    ttk.Label(frame, text="新密码:", font=("微软雅黑", 10)).pack(pady=(0, 5))
    new_var = tk.StringVar()
    new_entry = ttk.Entry(frame, textvariable=new_var, show="*", width=25)
    new_entry.pack(pady=(0, 10))
    
    ttk.Label(frame, text="确认新密码:", font=("微软雅黑", 10)).pack(pady=(0, 5))
    confirm_var = tk.StringVar()
    confirm_entry = ttk.Entry(frame, textvariable=confirm_var, show="*", width=25)
    confirm_entry.pack(pady=(0, 15))
    
    def change_password():
        current = current_var.get()
        new = new_var.get()
        confirm = confirm_var.get()
        
        if not current or not new or not confirm:
            messagebox.showerror("错误", "请填写所有字段")
            return
        
        if not permission_manager.authenticate_admin(current):
            messagebox.showerror("错误", "当前密码错误")
            return
        
        if new != confirm:
            messagebox.showerror("错误", "两次输入的新密码不一致")
            return
        
        if len(new) < 6:
            messagebox.showerror("错误", "新密码长度至少6位")
            return
        
        if permission_manager.save_admin_password(permission_manager.hash_password(new)):
            messagebox.showinfo("成功", "密码修改成功！")
            dialog.destroy()
    
    def cancel():
        dialog.destroy()
    
    btn_frame = ttk.Frame(frame)
    btn_frame.pack()
    
    ttk.Button(btn_frame, text="确定", command=change_password, width=10).grid(row=0, column=0, padx=5)
    ttk.Button(btn_frame, text="取消", command=cancel, width=10).grid(row=0, column=1, padx=5)

def update_ui_state():
    """更新UI状态"""
    if permission_manager.is_authenticated:
        user_text = "管理员" if permission_manager.current_user == "admin" else "访问员"
        status_label.config(text=f"当前用户: {user_text}", foreground="green")
        
        # 更新写入保护状态
        if permission_manager.write_protection_active:
            protection_label.config(text="写入保护: 已启用", foreground="orange")
        else:
            protection_label.config(text="写入保护: 已禁用", foreground="black")
        
        # 更新按钮状态
        if permission_manager.current_user == "admin":
            btn_enable.config(state='normal')
            btn_disable.config(state='normal')
            change_password_btn.config(state='normal')
        else:  # visitor
            btn_enable.config(state='disabled')
            btn_disable.config(state='disabled')
            change_password_btn.config(state='disabled')
    else:
        status_label.config(text="当前用户: 未认证", foreground="red")
        protection_label.config(text="写入保护: 未启用", foreground="black")
        btn_enable.config(state='disabled')
        btn_disable.config(state='disabled')
        change_password_btn.config(state='disabled')

def on_visitor_login():
    """访问员登录"""
    permission_manager.authenticate_visitor()
    messagebox.showinfo("成功", "访问员登录成功！\n权限：只能读取U盘文件，无法写入和修改USB设置")
    update_ui_state()

def on_logout():
    """登出"""
    permission_manager.logout()
    messagebox.showinfo("成功", "已登出")
    update_ui_state()

def refresh_usb_drives():
    """刷新USB驱动器列表"""
    drives_listbox.delete(0, tk.END)
    drives = permission_manager.get_usb_drives()
    if drives:
        for drive in drives:
            drives_listbox.insert(tk.END, f"{drive}\\ - 可移动磁盘")
    else:
        drives_listbox.insert(tk.END, "未检测到USB驱动器")

def build_ui(root: tk.Tk):
    root.title("USB 存储设备权限管理器 v2.0")
    root.geometry("500x550")
    
    # 创建菜单栏
    menubar = tk.Menu(root)
    root.config(menu=menubar)
    
    # 用户菜单
    user_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="用户", menu=user_menu)
    user_menu.add_command(label="访问员登录", command=on_visitor_login)
    user_menu.add_command(label="管理员登录", command=show_admin_login)
    user_menu.add_separator()
    user_menu.add_command(label="登出", command=on_logout)
    
    # 设置菜单
    settings_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="设置", menu=settings_menu)
    settings_menu.add_command(label="修改管理员密码", command=show_change_password)
    
    # 帮助菜单
    help_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="帮助", menu=help_menu)
    help_menu.add_command(label="关于", command=lambda: messagebox.showinfo("关于", 
        "USB存储设备权限管理器 v2.0\n\n权限说明:\n"
        "• 访问员：只能读取U盘文件，无法写入和修改USB设置\n"
        "• 管理员：完全控制权限，可读写U盘和修改USB设置\n\n"
        "默认管理员密码：admin123\n\n"
        "功能特点:\n"
        "• 访问员自动启用USB写入保护\n"
        "• 管理员自动禁用USB写入保护\n"
        "• 实时显示USB驱动器状态"))
    
    frame = tk.Frame(root, padx=15, pady=15)
    frame.pack(fill=tk.BOTH, expand=True)
    
    # 用户状态显示
    global status_label, protection_label
    status_label = tk.Label(frame, text="当前用户: 未认证", font=("微软雅黑", 12, "bold"), foreground="red")
    status_label.pack(pady=(0, 5))
    
    protection_label = tk.Label(frame, text="写入保护: 未启用", font=("微软雅黑", 10))
    protection_label.pack(pady=(0, 15))
    
    # 认证按钮区域
    auth_frame = tk.LabelFrame(frame, text="用户认证", padx=10, pady=10)
    auth_frame.pack(fill=tk.X, pady=(0, 15))
    
    auth_btn_frame = tk.Frame(auth_frame)
    auth_btn_frame.pack()
    
    visitor_btn = tk.Button(auth_btn_frame, text="访问员登录", width=12, command=on_visitor_login)
    visitor_btn.pack(side=tk.LEFT, padx=5)
    
    admin_btn = tk.Button(auth_btn_frame, text="管理员登录", width=12, command=show_admin_login)
    admin_btn.pack(side=tk.LEFT, padx=5)
    
    logout_btn = tk.Button(auth_btn_frame, text="登出", width=12, command=on_logout)
    logout_btn.pack(side=tk.LEFT, padx=5)
    
    # USB控制区域
    control_frame = tk.LabelFrame(frame, text="USB存储控制", padx=10, pady=10)
    control_frame.pack(fill=tk.X, pady=(0, 15))
    
    btn_frame = tk.Frame(control_frame)
    btn_frame.pack(pady=5)
    
    global btn_enable, btn_disable, change_password_btn
    btn_enable = tk.Button(btn_frame, text="启用 USB", width=14, command=on_enable, state='disabled')
    btn_enable.pack(side=tk.LEFT, padx=6)
    
    btn_disable = tk.Button(btn_frame, text="禁用 USB", width=14, command=on_disable, state='disabled')
    btn_disable.pack(side=tk.LEFT, padx=6)
    
    # 状态显示
    status_container = tk.Frame(control_frame)
    status_container.pack(fill=tk.X, pady=(10, 0))
    
    usb_status_label = tk.Label(status_container, textvariable=status_var, anchor='w', justify='left')
    usb_status_label.pack(fill=tk.X)
    
    refresh_btn = tk.Button(status_container, text="刷新状态", command=lambda: status_var.set(read_usb_status()))
    refresh_btn.pack(anchor='e', pady=(5, 0))
    
    # USB驱动器列表
    drives_frame = tk.LabelFrame(frame, text="当前USB驱动器", padx=10, pady=10)
    drives_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
    
    global drives_listbox
    drives_listbox = tk.Listbox(drives_frame, height=4)
    drives_listbox.pack(fill=tk.BOTH, expand=True)
    
    refresh_drives_btn = tk.Button(drives_frame, text="刷新驱动器", command=refresh_usb_drives)
    refresh_drives_btn.pack(anchor='e', pady=(5, 0))
    
    # 权限说明
    info_frame = tk.LabelFrame(frame, text="权限说明", padx=10, pady=10)
    info_frame.pack(fill=tk.X)
    
    info_text = """• 访问员权限：只能读取U盘文件，无法写入和修改USB设置
• 管理员权限：完全控制权限，可读写U盘和修改USB设置
• 访问员登录时自动启用USB写入保护
• 管理员登录时自动禁用USB写入保护
• 默认管理员密码：admin123"""
    
    info_label = tk.Label(info_frame, text=info_text, justify=tk.LEFT, font=("微软雅黑", 9))
    info_label.pack(anchor='w')

def main():
    # CLI模式：被提升的子进程执行注册表写入并退出
    if len(sys.argv) >= 3 and sys.argv[1] == "--set":
        try:
            target = int(sys.argv[2])
            set_usb_start(target)
            sys.exit(0)
        except Exception:
            sys.exit(1)

    global root, status_var
    root = tk.Tk()
    status_var = tk.StringVar(master=root)
    status_var.set(read_usb_status())
    
    build_ui(root)
    update_ui_state()
    
    # 初始刷新USB驱动器
    refresh_usb_drives()
    
    root.mainloop()

if __name__ == "__main__":
    main()