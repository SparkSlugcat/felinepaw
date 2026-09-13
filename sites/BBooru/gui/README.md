# BBooru 下载器（GUI / exe）

基于 `../B_scraper.py`（v5）的图形界面，打包成单文件 exe，仿 e621-downloader 的做法。

## 直接使用（打包后）

双击 `dist\BBooruDownloader.exe`，界面里：

- **模式**：标签(Tags) / 合集(Pool) / 艺术家(Artist)
- 标签模式：填 `--tags`（多标签空格分隔），引擎可选 auto/api/html
- 合集模式：填 pool 的 show 页 URL 或纯 id，可勾选反转编号
- 艺术家模式：填艺术家标签，可勾选跳过非池帖子
- 其余：数量 limit（留空=120，`inf`=全部）、线程、重试、成人 y/n、输出目录、代理（留空=自动检测/off=直连）
- 先「开始下载」，随时「停止」（已下载文件保留，重跑自动续传）

自检（不开窗口，验证依赖完整）：
```
dist\BBooruDownloader.exe --selftest
:: 然后查看 %TEMP%\bbooru_selftest.txt
```

## 打包

```bat
build_exe.bat
```
或手动（复用 e621-downloader 的 PyInstaller 环境，避免重复安装）：
```bat
set PYTHONPATH=..\..\..\..\scraper\e621\e621_gui\_pyi_env
python -m PyInstaller --noconfirm BBooruDownloader.spec
```

产出：`dist\BBooruDownloader.exe`（单文件、无控制台、图标 assets/icon.ico）。

## 说明 / 依赖关系

- `app.py` 在**进程内**调用 `B_scraper.main(argv)`（不是子进程），输出重定向到窗口日志；
  因此 B_scraper 的 `main()` 支持传入 argv、并提供 `request_cancel()/reset_cancel()` 供「停止」使用。
- 打包时 `B_scraper.py`、`common.py` 由 spec 的 `pathex` + `hiddenimports` 一并收进 exe。
- 图标来自 `felinepaw/assets/icon.png` 转换（多尺寸 ico）。
- 构建产物 `build/`、`dist/` 已被 repo 的 .gitignore 排除。
