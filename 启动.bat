@echo off
chcp 936 >nul 2>&1
cd /d "%~dp0"

rem 第一行 chcp 的理由：本机系统 ANSI 代码页 = 936，这个文件也按
rem GBK 存（跟 pixivpaw / e-hentai-paw 的启动器一致），cmd 默认就
rem 能正确解析下面的中文。万一哪天把终端改成 UTF-8 代码页，cmd 会
rem 拿 UTF-8 去解这份 GBK 文件、中文 echo 全变乱码 —— 这行是保险。
rem 改本文件请用能选编码的编辑器存成 GBK；存成 UTF-8 会全乱。
rem （Python 自己的输出不受这行影响：它走 WriteConsoleW 直接写
rem   Unicode，与代码页无关。）

rem ============================================================
rem  felinepaw 启动器 —— 双击直接打开图形界面
rem
rem  用写死的 py39 环境（requests / lxml / bs4 等依赖都装在那儿），
rem  不依赖 PATH 里排第一的 python：本机 PATH 里第一个 python 是
rem  3.13，没装本项目要的库，用它起不来。
rem
rem  参数 silent：连"出错要按任意键"都免掉。只有
rem  「启动(无窗口).vbs」会传它 —— 那个 .vbs 把本文件跑在一个
rem  **隐藏**的 cmd 里，里头的 pause 会永远挂着、表现成"双击了但
rem  什么都没发生"，是最难查的那种失败。日常双击本文件不用传参。
rem
rem  ★ 想双击时连命令行窗口都不闪 → 双击「启动(无窗口).vbs」。
rem    .bat 这一步必须由 cmd.exe 解析，窗口一定会闪一下；想零窗口，
rem    入口就不能是 .bat。
rem
rem  只想用命令行（不开界面）：在本目录开个终端，敲
rem      python felinepaw_tool.py --help
rem ============================================================

set "SILENT="
if /i "%~1"=="silent" set "SILENT=1"

set "PY39=%USERPROFILE%\miniconda3\envs\py39"
set "PY=%PY39%\python.exe"
set "PYW=%PY39%\pythonw.exe"

if not exist "%PY%"  goto :nopython
if not exist "%PYW%" goto :nopython

rem 先做一次导入自检。pythonw 启动失败是【静默】的 —— 双击后
rem "什么都没发生"是最难查的故障，所以起之前先测一发，有问题就
rem 让 python 把 traceback 打在这个窗口里。
"%PY%" -c "import felinepaw_gui" >nul 2>&1
if errorlevel 1 (
    echo.
    echo 启动失败，下面是原因：
    echo.
    "%PY%" -c "import felinepaw_gui"
    echo.
    if not defined SILENT pause
    exit /b 1
)

start "" "%PYW%" "%~dp0felinepaw_gui.py"
exit /b 0

:nopython
echo.
echo 没有找到 felinepaw 使用的 Python 环境：
echo     %PY%
echo.
echo 如果 conda 环境搬过位置，用记事本改本文件顶部的 PY39 那一行。
echo.
if not defined SILENT pause
exit /b 1
