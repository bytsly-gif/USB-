# USB权限管理器 - 工具集

本目录包含USB权限管理器的相关工具和文档。

## 📁 文件说明

### 🔧 程序文件
- **usb_manager.py** - 基础版本，简单的USB控制功能
- **usb_manager_complete.py** - 完整版本，包含所有高级功能
- **usb_access_monitor.py** - 独立的USB访问监控器
- **test_watchdog.py** - 看门狗功能测试工具

### 📖 文档文件
- **权限管理说明.md** - 详细的权限管理功能说明
- **看门狗功能说明.md** - 看门狗保护功能详细说明

### 🚀 启动脚本
- **start_usb_manager.bat** - 多版本启动选择器

## 🎯 使用指南

### 主程序启动
```bash
# 返回上级目录启动主程序
cd ..
python usb_manager_enhanced.py
# 或使用
start.bat
```

### 多版本选择器
```bash
# 在tools目录下运行
start_usb_manager.bat
```

### 测试看门狗功能
```bash
python test_watchdog.py
```

## 📋 版本对比

| 版本 | 功能 | 推荐场景 |
|------|------|----------|
| usb_manager.py | 基础USB控制 | 简单环境 |
| usb_manager_enhanced.py | 主程序，看门狗+权限管理 | 生产环境 |
| usb_manager_complete.py | 所有功能集 | 完整部署 |

## ⚠️ 注意事项

1. **主程序**位于上级目录：`../usb_manager_enhanced.py`
2. **配置文件**位于上级目录：`../admin_password.json`
3. 运行时注意Python路径和依赖库
4. 看门狗功能需要管理员权限

## 🔗 相关链接

- 主程序：`../usb_manager_enhanced.py`
- 配置文件：`../admin_password.json`
- 启动脚本：`../start.bat`

---
**开发者：BH2VLF**  
**版权所有 © 2025**