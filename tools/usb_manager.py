import os
import sys
import tkinter as tk
from tkinter import messagebox
import ctypes
import winreg

# 路径设置：使用当前脚本所在目录，确保中文路径正确
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

REG_PATH = r"SYSTEM\\CurrentControlSet\\Services\\USBSTOR"
REG_VALUE = "Start"


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
    r"""直接写注册表，将 USBSTOR\Start 设置为指定值 (3/4)。"""
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


def build_ui(root: tk.Tk):
    root.title("USB 存储设备管理")
    root.geometry("360x180")

    frame = tk.Frame(root, padx=12, pady=12)
    frame.pack(fill=tk.BOTH, expand=True)

    tk.Label(frame, text="将 USB 启用/禁用设置成两个按钮：").pack(anchor='w')

    btn_frame = tk.Frame(frame)
    btn_frame.pack(pady=8)

    btn_enable = tk.Button(btn_frame, text="启用 USB", width=14, command=on_enable)
    btn_enable.pack(side=tk.LEFT, padx=6)

    btn_disable = tk.Button(btn_frame, text="禁用 USB", width=14, command=on_disable)
    btn_disable.pack(side=tk.LEFT, padx=6)

    status_label = tk.Label(frame, textvariable=status_var, anchor='w', justify='left')
    status_label.pack(fill=tk.X, pady=10)

    refresh_btn = tk.Button(frame, text="刷新状态", command=lambda: status_var.set(read_usb_status()))
    refresh_btn.pack(anchor='e')


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
    root.mainloop()


if __name__ == "__main__":
    main()