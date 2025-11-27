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
import atexit
import signal

# 尝试导入系统托盘库
try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False
    print("警告：未安装pystray，无法使用系统托盘功能")

# 路径设置：使用当前脚本所在目录，确保中文路径正确
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PASSWORD_FILE = os.path.join(BASE_DIR, "admin_password.json")
BACKUP_FILE = os.path.join(BASE_DIR, "admin_password.json.bak")

REG_PATH = r"SYSTEM\CurrentControlSet\Services\USBSTOR"
REG_VALUE = "Start"

class USBPermissionManager:
    def __init__(self):
        self.current_user = None  # None, "visitor", "admin"
        self.is_authenticated = False
        self.password_file = PASSWORD_FILE
        self.backup_file = BACKUP_FILE
        
    def hash_password(self, password):
        """密码哈希"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def generate_time_based_password(self):
        """生成基于时间戳的默认密码（年月日格式）"""
        from datetime import datetime
        # 使用年月日作为密码，格式：20251127
        time_password = datetime.now().strftime("%Y%m%d")
        return time_password
    
    def load_admin_password(self):
        """加载管理员密码"""
        # 尝试从主文件加载
        try:
            if os.path.exists(self.password_file):
                with open(self.password_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    password = data.get("admin_password")
                    if password:
                        # 验证密码哈希格式
                        if len(password) == 64 and all(c in '0123456789abcdefABCDEF' for c in password):
                            return password
        except Exception as e:
            print(f"读取主密码文件失败: {e}")
        
        # 尝试从备份文件加载
        try:
            if os.path.exists(self.backup_file):
                with open(self.backup_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    password = data.get("admin_password")
                    if password:
                        print("从备份文件恢复密码")
                        # 恢复主文件
                        self.save_admin_password(password)
                        return password
        except Exception as e:
            print(f"读取备份文件失败: {e}")
        
        # 如果都失败，使用基于时间的默认密码并创建新文件
        time_password = self.generate_time_based_password()
        print(f"使用基于时间的默认密码: {time_password}")
        default_password = self.hash_password(time_password)
        self.save_admin_password(default_password)
        return default_password
    
    def save_admin_password(self, password_hash):
        """保存管理员密码"""
        try:
            # 创建备份
            if os.path.exists(self.password_file):
                try:
                    import shutil
                    shutil.copy2(self.password_file, self.backup_file)
                except Exception as e:
                    print(f"创建备份失败: {e}")
            
            # 保存新密码
            data = {}
            if os.path.exists(self.password_file):
                try:
                    with open(self.password_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except:
                    data = {}
            
            data["admin_password"] = password_hash
            data["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            
            # 原子写入：先写临时文件，再重命名
            temp_file = self.password_file + ".tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # 原子替换
            if os.name == 'nt':  # Windows
                if os.path.exists(self.password_file):
                    os.remove(self.password_file)
            os.rename(temp_file, self.password_file)
            
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
            return True
        return False
    
    def authenticate_visitor(self):
        """访问员认证（无需密码）"""
        self.current_user = "visitor"
        self.is_authenticated = True
        return True
    
    def logout(self):
        """登出"""
        self.current_user = None
        self.is_authenticated = False
    
    def can_write_usb(self):
        """检查是否有USB写入权限"""
        return self.current_user == "admin"
    
    def can_read_usb(self):
        """检查是否有USB读取权限"""
        return self.is_authenticated  # 访问员和管理员都可以读取
    
    def repair_password_file(self):
        """修复密码文件"""
        try:
            # 检查主文件
            if os.path.exists(self.password_file):
                try:
                    with open(self.password_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if "admin_password" in data:
                            return True, "密码文件正常"
                except:
                    pass
            
            # 尝试从备份恢复
            if os.path.exists(self.backup_file):
                try:
                    with open(self.backup_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        password = data.get("admin_password")
                        if password:
                            self.save_admin_password(password)
                            return True, "从备份文件恢复成功"
                except:
                    pass
            
            # 创建基于时间的默认密码文件
            time_password = self.generate_time_based_password()
            default_password = self.hash_password(time_password)
            if self.save_admin_password(default_password):
                return True, f"已重置为基于时间的默认密码：{time_password}"
            
            return False, "修复失败"
        except Exception as e:
            return False, f"修复失败: {e}"

# 全局权限管理器
permission_manager = USBPermissionManager()

# 看门狗相关变量
watchdog_active = True
watchdog_thread = None
exit_allowed = False

class Watchdog:
    """看门狗类，防止程序被非法关闭"""
    
    def __init__(self):
        self.running = True
        self.thread = None
    
    def start(self):
        """启动看门狗"""
        self.running = True
        self.thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """停止看门狗"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
    
    def _watchdog_loop(self):
        """看门狗循环"""
        while self.running:
            time.sleep(1)  # 每秒检查一次
    
    def allow_exit(self):
        """允许退出程序"""
        global exit_allowed
        exit_allowed = True

# 全局看门狗实例
watchdog = Watchdog()

# 系统托盘相关
tray_icon = None

def create_tray_icon():
    """创建系统托盘图标"""
    if not TRAY_AVAILABLE:
        return None
    
    # 创建简单的图标
    def create_image():
        image = Image.new('RGB', (64, 64), color='blue')
        d = ImageDraw.Draw(image)
        d.text((10, 20), "USB", fill='white')
        return image
    
    def show_window(icon, item):
        """显示主窗口"""
        if root.state() == 'withdrawn':
            root.deiconify()
            root.lift()
            root.focus_force()
    
    def exit_app(icon, item):
        """退出应用"""
        global exit_allowed
        if permission_manager.current_user == "admin":
            exit_allowed = True
            watchdog.stop()
            icon.stop()
            root.quit()
            sys.exit(0)
        else:
            messagebox.showerror("权限不足", "只有管理员可以退出程序")
    
    # 创建托盘菜单
    menu = pystray.Menu(
        pystray.MenuItem("显示主窗口", show_window),
        pystray.MenuItem("退出程序", exit_app)
    )
    
    # 创建托盘图标
    icon = pystray.Icon("usb_manager", create_image(), menu=menu)
    return icon

def hide_to_tray():
    """隐藏到系统托盘"""
    if TRAY_AVAILABLE and tray_icon:
        root.withdraw()
        if not tray_icon._running:
            threading.Thread(target=tray_icon.run, daemon=True).start()

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def read_usb_status():
    """读取USB存储服务的启动类型，返回友好状态字符串。"""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_PATH) as key:
            value, regtype = winreg.QueryValueEx(key, REG_VALUE)
            # 3 = 手动(启用)，4 = 禁用
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
    """直接写注册表，将 USBSTOR\\Start 设置为指定值 (3/4)。"""
    access = winreg.KEY_SET_VALUE
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_PATH, 0, access) as key:
        winreg.SetValueEx(key, REG_VALUE, 0, winreg.REG_DWORD, int(value))

def elevate_and_set(value: int) -> bool:
    """以管理员权限重新调用当前Python脚本执行 --set <value>，尽量不弹出控制台窗口。"""
    script = os.path.abspath(__file__)
    exe_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(exe_dir, 'pythonw.exe')
    interpreter = pythonw if os.path.exists(pythonw) else sys.executable
    params = f'"{script}" --set {int(value)}'
    # 使用 SW_HIDE(0) 尝试隐藏窗口；配合 pythonw.exe 通常不会出现第二窗口
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
            messagebox.showinfo("成功", "管理员登录成功！")
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
        btn_enable.config(state='disabled')
        btn_disable.config(state='disabled')
        change_password_btn.config(state='disabled')

def on_visitor_login():
    """访问员登录"""
    permission_manager.authenticate_visitor()
    messagebox.showinfo("成功", "访问员登录成功！\n权限：只能读取U盘文件，无法修改USB设置")
    update_ui_state()

def on_logout():
    """登出"""
    permission_manager.logout()
    messagebox.showinfo("成功", "已登出")
    update_ui_state()

def on_closing():
    """窗口关闭事件处理"""
    global exit_allowed
    
    # 如果有系统托盘，隐藏到托盘而不是关闭
    if TRAY_AVAILABLE:
        result = messagebox.askyesno("最小化到托盘", 
            "是否最小化到系统托盘？\\n\\n选择'否'将完全关闭程序")
        if result:
            hide_to_tray()
            return
    
    # 完全关闭程序
    if not permission_manager.is_authenticated:
        messagebox.showwarning("权限不足", "请先登录后再关闭程序")
        return
    
    if permission_manager.current_user != "admin":
        messagebox.showwarning("权限不足", "只有管理员可以关闭程序")
        return
    
    # 管理员确认关闭
    result = messagebox.askyesno("确认关闭", 
        "确定要关闭USB权限管理器吗？\n\n关闭后将失去USB设备保护功能！")
    
    if result:
        exit_allowed = True
        watchdog.stop()
        if tray_icon:
            tray_icon.stop()
        root.destroy()
        sys.exit(0)

def build_ui(root: tk.Tk):
    root.title("USB 存储设备权限管理器")
    root.geometry("450x350")
    
    # 禁用窗口关闭按钮，只允许通过菜单退出
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
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
    user_menu.add_separator()
    user_menu.add_command(label="退出程序", command=on_closing)
    
    # 设置菜单
    settings_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="设置", menu=settings_menu)
    settings_menu.add_command(label="修改管理员密码", command=show_change_password)
    
    # 帮助菜单
    help_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="帮助", menu=help_menu)
    help_menu.add_command(label="关于", command=lambda: messagebox.showinfo("关于", 
        "USB存储设备权限管理器 v2.0\n\n"
        "版权所有 © 2025\n"
        "开发者：BH2VLF\n\n"
        "权限说明:\n"
        "• 访问员：只能读取U盘文件，无法修改USB设置\n"
        "• 管理员：完全控制权限，可读写U盘和修改USB设置\n\n"
        "使用说明:\n"
        "• 首次使用请先登录管理员并修改密码\n"
        "• 配置文件丢失时会自动恢复\n\n"
        "本软件提供USB设备安全管理功能，\n"
        "包含看门狗保护和权限控制机制。"))
    
    frame = tk.Frame(root, padx=15, pady=15)
    frame.pack(fill=tk.BOTH, expand=True)
    
    # 用户状态显示
    global status_label
    status_label = tk.Label(frame, text="当前用户: 未认证", font=("微软雅黑", 12, "bold"), foreground="red")
    status_label.pack(pady=(0, 15))
    
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
    
    change_password_btn = tk.Button(btn_frame, text="修改密码", width=14, command=show_change_password, state='disabled')
    change_password_btn.pack(side=tk.LEFT, padx=6)
    
    # 状态显示
    status_container = tk.Frame(control_frame)
    status_container.pack(fill=tk.X, pady=(10, 0))
    
    usb_status_label = tk.Label(status_container, textvariable=status_var, anchor='w', justify='left')
    usb_status_label.pack(fill=tk.X)
    
    refresh_btn = tk.Button(status_container, text="刷新状态", command=lambda: status_var.set(read_usb_status()))
    refresh_btn.pack(anchor='e', pady=(5, 0))
    
    

def signal_handler(signum, frame):
    """信号处理器"""
    global exit_allowed
    
    if not exit_allowed:
        print("程序受到保护，无法通过信号终止")
        return
    
    print("程序正常退出")
    sys.exit(0)

def setup_signal_handlers():
    """设置信号处理器"""
    if os.name != 'nt':  # 非Windows系统
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

def main():
    # CLI模式：被提升的子进程执行注册表写入并退出
    if len(sys.argv) >= 3 and sys.argv[1] == "--set":
        try:
            target = int(sys.argv[2])
            set_usb_start(target)
            sys.exit(0)
        except Exception:
            sys.exit(1)

    # 设置信号处理器
    setup_signal_handlers()
    
    # 启动看门狗
    watchdog.start()
    
    global root, status_var, tray_icon
    root = tk.Tk()
    status_var = tk.StringVar(master=root)
    status_var.set(read_usb_status())
    
    # 创建系统托盘图标
    tray_icon = create_tray_icon()
    
    build_ui(root)
    update_ui_state()
    
    # 注册退出处理
    atexit.register(watchdog.stop)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        if not exit_allowed:
            print("程序受到保护，无法通过Ctrl+C终止")
            # 重新启动主循环
            root.mainloop()
        else:
            print("程序正常退出")
            sys.exit(0)

if __name__ == "__main__":
    main()