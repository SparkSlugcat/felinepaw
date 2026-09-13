@echo off
cd /d "%~dp0"
echo ============================================
echo   BBooru 下载器 - 打包成独立 exe
echo ============================================

rem 优先复用 e621-downloader 已装好的 PyInstaller 环境（_pyi_env），避免重复下载安装
set "PYI_ENV=%~dp0..\..\..\..\scraper\e621\e621_gui\_pyi_env"
if exist "%PYI_ENV%\PyInstaller" (
    echo 使用已有 PyInstaller 环境: %PYI_ENV%
    set "PYTHONPATH=%PYI_ENV%"
) else (
    echo 未找到 _pyi_env，尝试安装 PyInstaller ...
    pip install pyinstaller
)

echo 开始打包（约需 1-3 分钟）...
python -m PyInstaller --noconfirm BBooruDownloader.spec

echo.
if exist "dist\BBooruDownloader.exe" (
    echo 打包完成！生成文件：dist\BBooruDownloader.exe
    echo 可自检：dist\BBooruDownloader.exe --selftest   然后看 %%TEMP%%\bbooru_selftest.txt
) else (
    echo 打包失败，请查看上面的错误信息。
)
pause
