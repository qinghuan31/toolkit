# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Toolkit v1.5.0
- 单文件模式 onefile（用户双击即用）
- 包含 resources/ 图标
- 排除 GUI 无关的大库（可选）
"""

import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# 项目根目录
PROJECT_ROOT = os.path.abspath('.')

# 收集 peel_data 插件的子模块（动态导入需要）
hiddenimports = []
hiddenimports += collect_submodules('plugins.peel_data')
hiddenimports += collect_submodules('core')

# 资源文件（图标）
datas = [
    (os.path.join(PROJECT_ROOT, 'resources', 'app_icon.ico'), 'resources'),
    (os.path.join(PROJECT_ROOT, 'resources', 'app_icon_512.png'), 'resources'),
    (os.path.join(PROJECT_ROOT, 'resources', 'app_icon_1024.png'), 'resources'),
]

a = Analysis(
    ['main.py'],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy.tests', 'scipy', 'pandas',
        'PyQt5', 'PyQt6', 'tkinter', 'test',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Toolkit_v1.5.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # GUI 模式，无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(PROJECT_ROOT, 'resources', 'app_icon.ico'),
)
