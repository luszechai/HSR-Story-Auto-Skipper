# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: builds a windowed Windows app (no console)."""

from PyInstaller.utils.hooks import collect_all

block_cipher = None

ctk_datas, ctk_binaries, ctk_hiddenimports = collect_all("customtkinter")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=ctk_binaries,
    datas=ctk_datas
    + [
        ("assets/templates", "assets/templates"),
        ("assets/brand", "assets/brand"),
    ],
    hiddenimports=ctk_hiddenimports
    + [
        "pydirectinput",
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
        "win32timezone",
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
    name="HSR Auto Skip",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # real GUI app — no terminal
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/brand/app.ico",
    uac_admin=True,  # always prompt: Run as administrator
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="HSR Auto Skip",
)
