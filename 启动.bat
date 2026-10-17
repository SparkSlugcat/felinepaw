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
rem  自动定位 py39 环境（requests / lxml / bs4 等依赖都装在那儿），
rem  不依赖 PATH 里排第一的 python：本机 PATH 里第一个 python 是
rem  3.13，没装本项目要的库，用它起不来。定位顺序见下面那段。
rem
rem  参数 silent：连"出错要按任意键"都免了（保留兼容，日常可不传）。
rem
rem  只想用命令行（不开界面）：在本目录开个终端，敲
rem      python felinepaw_tool.py --help
rem ============================================================

set "SILENT="
if /i "%~1"=="silent" set "SILENT=1"

rem ==== 自动定位 Python 环境（本文件不含任何绝对路径 / 用户名）====
rem  按顺序取第一个存在的：
rem    1) 环境变量 PYTHON_EXE —— 想手动指定就用它
rem    2) %USERPROFILE% 下 conda 的 py39 环境（miniconda3 / anaconda3）
rem    3) 当前已激活的 conda 环境 %CONDA_PREFIX%
rem    4) PATH 里第一个 python
rem  换机器、换环境都不用改这个文件。
set "PY="
if defined PYTHON_EXE if exist "%PYTHON_EXE%" set "PY=%PYTHON_EXE%"
if not defined PY if exist "%USERPROFILE%\miniconda3\envs\py39\python.exe" set "PY=%USERPROFILE%\miniconda3\envs\py39\python.exe"
if not defined PY if exist "%USERPROFILE%\anaconda3\envs\py39\python.exe" set "PY=%USERPROFILE%\anaconda3\envs\py39\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\miniconda3\envs\py39\python.exe" set "PY=%LOCALAPPDATA%\miniconda3\envs\py39\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Continuum\anaconda3\envs\py39\python.exe" set "PY=%LOCALAPPDATA%\Continuum\anaconda3\envs\py39\python.exe"
if not defined PY if exist "%USERPROFILE%\miniconda3\envs\py310\python.exe" set "PY=%USERPROFILE%\miniconda3\envs\py310\python.exe"
if not defined PY if exist "%USERPROFILE%\anaconda3\envs\py310\python.exe" set "PY=%USERPROFILE%\anaconda3\envs\py310\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\miniconda3\envs\py310\python.exe" set "PY=%LOCALAPPDATA%\miniconda3\envs\py310\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Continuum\anaconda3\envs\py310\python.exe" set "PY=%LOCALAPPDATA%\Continuum\anaconda3\envs\py310\python.exe"
if not defined PY if exist "%USERPROFILE%\miniconda3\envs\py311\python.exe" set "PY=%USERPROFILE%\miniconda3\envs\py311\python.exe"
if not defined PY if exist "%USERPROFILE%\anaconda3\envs\py311\python.exe" set "PY=%USERPROFILE%\anaconda3\envs\py311\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\miniconda3\envs\py311\python.exe" set "PY=%LOCALAPPDATA%\miniconda3\envs\py311\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Continuum\anaconda3\envs\py311\python.exe" set "PY=%LOCALAPPDATA%\Continuum\anaconda3\envs\py311\python.exe"
if not defined PY if exist "%USERPROFILE%\miniconda3\envs\py312\python.exe" set "PY=%USERPROFILE%\miniconda3\envs\py312\python.exe"
if not defined PY if exist "%USERPROFILE%\anaconda3\envs\py312\python.exe" set "PY=%USERPROFILE%\anaconda3\envs\py312\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\miniconda3\envs\py312\python.exe" set "PY=%LOCALAPPDATA%\miniconda3\envs\py312\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Continuum\anaconda3\envs\py312\python.exe" set "PY=%LOCALAPPDATA%\Continuum\anaconda3\envs\py312\python.exe"
if not defined PY if exist "%USERPROFILE%\miniconda3\envs\py313\python.exe" set "PY=%USERPROFILE%\miniconda3\envs\py313\python.exe"
if not defined PY if exist "%USERPROFILE%\anaconda3\envs\py313\python.exe" set "PY=%USERPROFILE%\anaconda3\envs\py313\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\miniconda3\envs\py313\python.exe" set "PY=%LOCALAPPDATA%\miniconda3\envs\py313\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Continuum\anaconda3\envs\py313\python.exe" set "PY=%LOCALAPPDATA%\Continuum\anaconda3\envs\py313\python.exe"
if not defined PY if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PY=%CONDA_PREFIX%\python.exe"
if not defined PY for /f "delims=" %%I in ('where python 2^>nul') do if not defined PY set "PY=%%I"
if defined PY for %%I in ("%PY%") do set "PYDIR=%%~dpI"
set "PYW=%PYDIR%pythonw.exe"

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
echo 没有找到可用的 Python 环境（需要 requests / lxml / bs4 等依赖）。
echo.
echo 两种指定办法（任选其一）：
echo   1) 把任意 python.exe 的完整路径配给 PYTHON_EXE 环境变量（永久）
echo     命令: setx PYTHON_EXE "C:\你的\python.exe"
echo     注意: setx 写注册表,新开 cmd 才生效;先用 set 试一次也行
echo   2) 建一个名为 py39~py313 的 conda 环境（任选其一），脚本会自动找到它
echo.
if not defined SILENT pause
exit /b 1
