# -*- coding: utf-8 -*-
"""工具集启动脚本 - 静默启动，无控制台窗口"""
import subprocess
import sys
import os

# 项目根目录（与启动脚本同目录）
project_dir = os.path.dirname(os.path.abspath(__file__))
venv_python = os.path.join(project_dir, ".venv", "Scripts", "pythonw.exe")
main_script = os.path.join(project_dir, "main.py")

# 优先使用 pythonw.exe（无控制台），若不存在则回退到 python.exe + CREATE_NO_WINDOW
if not os.path.exists(venv_python):
    venv_python = os.path.join(project_dir, ".venv", "Scripts", "python.exe")

# 检查虚拟环境
if not os.path.exists(venv_python):
    import ctypes
    ctypes.windll.user32.MessageBoxW(
        0,
        f"未找到虚拟环境!\n\n期望路径: {venv_python}\n\n"
        f"请先运行以下命令创建虚拟环境并安装依赖:\n"
        f"  python -m venv \"{os.path.join(project_dir, '.venv')}\"\n"
        f"  venv Python -m pip install -r requirements.txt",
        "工具集 - 启动错误",
        0x10,  # MB_ICONERROR
    )
    sys.exit(1)

# 检查主脚本
if not os.path.exists(main_script):
    import ctypes
    ctypes.windll.user32.MessageBoxW(
        0,
        f"未找到主程序:\n{main_script}",
        "工具集 - 启动错误",
        0x10,
    )
    sys.exit(1)

# 启动应用（完全无控制台窗口）
try:
    # CREATE_NO_WINDOW = 0x08000000，确保子进程不创建控制台
    subprocess.Popen(
        [venv_python, main_script],
        cwd=project_dir,
        creationflags=0x08000000,
        close_fds=True,
    )
except Exception as e:
    import ctypes
    ctypes.windll.user32.MessageBoxW(
        0,
        f"启动失败:\n{e}",
        "工具集 - 启动错误",
        0x10,
    )
    sys.exit(1)
