# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\user\\my-projects\\jaylin-yt-translator\\gui_main.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\user\\my-projects\\jaylin-yt-translator\\src\\i18n\\languages.json', 'src/i18n'), ('C:\\Users\\user\\my-projects\\jaylin-yt-translator\\src\\gui\\assets\\logo.png', 'src/gui/assets'), ('C:\\Users\\user\\my-projects\\jaylin-yt-translator\\src\\gui\\assets\\icon.ico', 'src/gui/assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='J-LIN-Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\user\\my-projects\\jaylin-yt-translator\\src\\gui\\assets\\icon.ico'],
)
