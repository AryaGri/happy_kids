# -*- mode: python ; coding: utf-8 -*-
# Сборка: pyinstaller desktop_client/platform.spec
# Результат: папка dist/Платформа/ с exe и библиотеками (архивируйте для раздачи)

import sys
import os

block_cipher = None

# Путь к customtkinter (для включения шрифтов и тем)
def get_ctk_path():
    import customtkinter as ctk
    return os.path.dirname(ctk.__file__)

ctk_path = get_ctk_path()
spec_dir = os.path.dirname(os.path.abspath(__file__))

a = Analysis(
    [os.path.join(spec_dir, 'app.py')],
    pathex=[spec_dir],
    binaries=[],
    datas=[
        (os.path.join(ctk_path, 'assets'), 'customtkinter/assets'),
    ],
    hiddenimports=[
        'customtkinter',
        'webview',
        'requests',
        'PIL',
        'PIL._tkinter_finder',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Платформа',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Платформа',
)
