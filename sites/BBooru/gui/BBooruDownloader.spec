# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — BBooru 下载器（单文件 GUI exe）
构建：python -m PyInstaller --noconfirm BBooruDownloader.spec
（PyInstaller 环境：本文件所在目录的说明见 build_exe.bat / README.md）
"""
import os
from PyInstaller.utils.hooks import collect_all

HERE = os.path.abspath(SPECPATH)                 # .../sites/BBooru/gui
SITE = os.path.dirname(HERE)                     # .../sites/BBooru  (B_scraper.py)
REPO = os.path.dirname(os.path.dirname(SITE))    # .../felinepaw     (common.py)
ICON = os.path.join(HERE, "assets", "icon.ico")

datas = [(ICON, "assets")]
binaries = []
hiddenimports = ["B_scraper", "common"]

# 打包 requests（e621-downloader 同款做法）
tmp_ret = collect_all("requests")
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

a = Analysis(
    ["app.py"],
    pathex=[REPO, SITE],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name="BBooruDownloader",
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
    icon=[ICON],
)
