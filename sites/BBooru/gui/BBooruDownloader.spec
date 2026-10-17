# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — BBooru 下载器（单文件 GUI exe）
构建：python -m PyInstaller --noconfirm BBooruDownloader.spec
（PyInstaller 环境：本文件所在目录的说明见 build_exe.bat / README.md）
"""
import os
import sys
from PyInstaller.utils.hooks import collect_all

HERE = os.path.abspath(SPECPATH)                 # .../sites/BBooru/gui
SITE = os.path.dirname(HERE)                     # .../sites/BBooru  (B_scraper.py)
REPO = os.path.dirname(os.path.dirname(SITE))    # .../felinepaw     (common.py)
ICON = os.path.join(HERE, "assets", "icon.ico")

datas = [(ICON, "assets")]
binaries = []
hiddenimports = ["B_scraper", "common"]

# ---- conda 专用补丁：tcl/tk 的 DLL 在 <env>\Library\bin，不在 <env>\DLLs\ ----
# 不显式带上，打包出来的 windowed exe 会报：
#   ImportError: DLL load failed while importing _tkinter
_ENV_LIB_BIN = os.path.join(sys.prefix, "Library", "bin")
for _dll in ("tcl86t.dll", "tk86t.dll", "ffi-8.dll"):
    _p = os.path.join(_ENV_LIB_BIN, _dll)
    if os.path.exists(_p):
        binaries.append((_p, "."))
    else:
        print("[spec] WARNING: %s 不存在，打出来的 exe 可能起不来" % _p)

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
