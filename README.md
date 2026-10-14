# 🐾 felinepaw

Multi-site furry image downloader scripts — **e621 / yiffverse / e-hentai / FurAffinity / BBooru / WildDream / HypnoHub / Rule34.us** in one place.
All scripts share the same CLI conventions (`-o`, `--limit`, `--proxy`, `-w`, `-d`,
`--delay`, `--jitter`, `--cooldown`, `--force`) and a common
base library ([`common.py`](common.py)) for proxy detection, sessions, resume, limits,
request pacing and a fail-fast proxy preflight.
A unified launcher ([`felinepaw_tool.py`](felinepaw_tool.py), CLI + tkinter GUI) dispatches all sites from one command.

> 多站点兽向图片下载脚本 —— **e621 / yiffverse / e-hentai / FurAffinity / BBooru / WildDream / HypnoHub / Rule34.us** 全在一处。
> 所有脚本共用同一套命令行约定（`-o`、`--limit`、`--proxy`、`-w`、`-d`、`--delay`、`--jitter`、`--cooldown`、`--force`），
> 以及一个公共基础库 [`common.py`](common.py)，负责代理探测、会话复用、断点续传、数量上限、请求节流，
> 以及发包前的快速代理预检。
> 还有一个统一入口 [`felinepaw_tool.py`](felinepaw_tool.py)（命令行 + tkinter 图形界面），一条命令调度所有站点。

> ⭐ If this project helps you, a Star would mean a lot. Thanks!
>
> 如果这个项目对你有帮助，欢迎点个 ⭐ Star，非常感谢！

> 🖥 **Prefer a window over the terminal? / 不想敲命令行？**
> Try **[e621-downloader](https://github.com/SparkSlugcat/e621-downloader)** — a standalone GUI for
> e621 with a **no-install `.exe`**, bilingual UI and tag / page / artist modes.
> / 试试同系列的 **e621 图形界面版**：免装 Python，下载 exe 双击即用。

---

## 🚀 Quick start / 快速上手（统一入口）

```bat
python felinepaw_tool.py bbooru --tags landscape --limit 200 -o ./out
python felinepaw_tool.py bbooru --pool 33976 --limit inf -o ./out
python felinepaw_tool.py bbooru --tags <artist_tag> --mode artist -o ./out
python felinepaw_tool.py hypnohub --tags spiral --limit 50 -o ./out
python felinepaw_tool.py rule34us --tags landscape --limit 50 -o ./out
python felinepaw_tool.py wilddream "https://www.wilddream.net/art/userpage/gallery?userpagename=xxx&folderid=485" --limit inf -o ./out
```

Or launch the GUI: `python felinepaw_gui.py`

> 或者直接开图形界面：`python felinepaw_gui.py`

**Windows: just double-click `启动.bat`.** It auto-detects a local Python 3.9 environment
(a conda `py39` under `%USERPROFILE%`, or whatever `PYTHON_EXE` points at — no PATH fiddling)
and runs an import self-check first, so a missing dependency shows up as a readable traceback
instead of a window that silently never appears. Want no console flash at all? Double-click
**`启动(无窗口).vbs`** instead.

> **Windows 用户：双击 `启动.bat` 就能开图形界面。** 它会自动找到本机的 Python 3.9 环境
> （`%USERPROFILE%` 下的 conda `py39`，或环境变量 `PYTHON_EXE` 指向的那个），不用你自己配 PATH；
> 启动前先做一次导入自检，缺依赖时会把 traceback 直接打出来，而不是"双击了没反应"。
> 若想连那一闪而过的命令行窗口都省掉，双击 **`启动(无窗口).vbs`**。
>
> ⚠️ 脚本里**不含任何写死的路径** —— 换机器、换 conda 环境都不用改文件；真找不到环境时，
> 它会告诉你怎么用 `PYTHON_EXE` 指定。

## 📦 Sites / 支持的站点

| Site | Scripts | Notes |
|---|---|---|
| **e621 / e926** | `sites/e621/` | Official JSON API. Credentials via `E621_USER` / `E621_KEY` env vars (guest if unset). 🖥 **GUI version → [e621-downloader](https://github.com/SparkSlugcat/e621-downloader)** |
| **yiffverse** | `sites/yiff/` | SSR + browser-auto (DrissionPage) variants; no pools, tag-based |
| **e-hentai** | `sites/e-hentai/` | Official `gdata` API for metadata + HTML for image links. **Tag search** (`--tags`), **dry-run list + pick by index** (`--dry-run` / `--pick 2-4,7`), cursor paging (`&next=<gid>`) |
| **FurAffinity** | `sites/furaffinity/` | Title-normalization series detection; login via cookies (`FA_get_cookies.py`) |
| **BBooru** | `sites/BBooru/B_scraper.py` | Gelbooru-style built-in JSON API, **no API key**. Tags (`--tags`), pools (`--pool <show URL / id>`), auto HTML fallback, `--adult y/n`, **artist mode** (pool-grouped download), **GUI/exe** in `gui/` |
| **WildDream** | `sites/wilddream/W_scraper.py` | Comic-gallery (folder) downloads from a gallery URL; polite throttling + atomic `.part` resume; threaded (`--threads`); `--limit` default 80 |
| **HypnoHub** | `sites/hypnohub/H_scraper.py` | Gelbooru/Shimmie engine, **HTML only** (no usable JSON API); original taken from `img#image`; `--page` for a single page |
| **Rule34.us** | `sites/rule34us/R_scraper.py` | Custom engine, **HTML only**; original linked by `<li class="character-tag">Original</li>`; automatic pagination probe |

> **中文速览**
>
> - **e621 / e926** —— `sites/e621/`：官方 JSON API，凭据走 `E621_USER` / `E621_KEY` 环境变量（不设则以游客身份）。🖥 图形界面版 → [e621-downloader](https://github.com/SparkSlugcat/e621-downloader)
> - **yiffverse** —— `sites/yiff/`：SSR 版 + 浏览器自动加载版（DrissionPage）两种；没有池子，只按标签。
> - **e-hentai** —— `sites/e-hentai/`：官方 `gdata` API 取元数据 + HTML 取图片链接。支持**标签搜索**（`--tags`）、**dry-run 出名单再按序号挑**（`--dry-run` / `--pick 2-4,7`）、游标翻页（`&next=<gid>`）。
> - **FurAffinity** —— `sites/furaffinity/`：靠标题规范化识别系列；用 cookies 登录（`FA_get_cookies.py`）。
> - **BBooru** —— `sites/BBooru/B_scraper.py`：Gelbooru 系内置 JSON API，**不需要 API key**。标签（`--tags`）、池子（`--pool <show URL / id>`）、自动 HTML 兜底、`--adult y/n`、**artist 模式**（按池分组下载）、`gui/` 里有图形界面 / exe。
> - **WildDream** —— `sites/wilddream/W_scraper.py`：从画廊 URL 下载整本漫画（文件夹）；礼貌节流 + `.part` 原子续传；多线程（`--threads`）；`--limit` 默认 80。
> - **HypnoHub** —— `sites/hypnohub/H_scraper.py`：Gelbooru / Shimmie 引擎，**只有 HTML**（没有可用的 JSON API）；原图取 `img#image`；`--page` 指定单页。
> - **Rule34.us** —— `sites/rule34us/R_scraper.py`：自建引擎，**只有 HTML**；原图由 `<li class="character-tag">Original</li>` 给出；自动探测翻页。

## ✨ Common features / 通用特性

- **Proxy auto-detect** — follows Windows system proxy / env vars (`--proxy off` to disable)
- **Proxy preflight (fail-fast)** — before a run, one TCP probe + one no-retry GET tell you in
  ~1s whether the proxy port is even listening, instead of hanging for tens of seconds on a
  `ProxyError`. `--no-preflight` skips it. `proxy_down` / `bad_proxy_url` abort the run;
  everything else only warns
- **`--limit`** — default 120 (WildDream: 80), `--limit N`, `--limit inf` (download everything)
- **Resume** — existing files are skipped (atomic `.part` + rename on BBooru / WildDream / HypnoHub / Rule34.us)
- **`--force`** — re-download files that already exist (BBooru / HypnoHub / Rule34.us),
  useful for repairing half-written images
- **Request pacing** — BBooru / HypnoHub / Rule34.us accept `--delay` (base interval) and
  `--jitter` (random extra), so traffic doesn't look machine-regular; on HTTP 429/503 every
  worker thread backs off together for `--cooldown` seconds (default 20) instead of each
  thread hitting the wall on its own. Defaults (`0` / `0`) keep the old behaviour
  (e-hentai / FurAffinity use `-d` as a random delay cap, which equals `--delay 0 --jitter d`)
- **Concurrency** — threaded downloads (BBooru / WildDream / HypnoHub / Rule34.us: `--threads`) with polite delays
- **Named-list workflow (e-hentai)** — `--dry-run` prints the list **and** saves it to a JSON
  manifest; `--pick 2-4,7` downloads exactly those rows. Search results drift as new uploads
  appear, so the saved manifest is what makes `--pick` reproducible
  (`--from-manifest eh_manifest.json --pick 2-4,7`). The same `--pick` syntax (`2-4,7` / `3-` /
  `-3` / `all`) lives in `common.py`, so other sites can reuse it
- **No hardcoded credentials** — env vars / cookies only
- **Console-safe output** — GBK-safe ASCII markers (no emoji that crash cp936 terminals)
- **Uniform file naming** — `p<post_id>.<ext>` across the booru sites, so resume works across modes

> **中文**
>
> - **代理自动探测** —— 跟随 Windows 系统代理 / 环境变量（`--proxy off` 可关掉）
> - **代理预检（fail-fast）** —— 开跑前先做一次 TCP 探测 + 一次不重试的 GET，约 1 秒内告诉你代理端口到底有没有在监听，而不是卡在 `ProxyError` 上几十秒。`--no-preflight` 可跳过。`proxy_down` / `bad_proxy_url` 会中止本次运行，其余情况只警告
> - **`--limit`** —— 默认 120（WildDream：80），`--limit N` 取 N 个，`--limit inf` 全部下载
> - **断点续传** —— 已存在的文件跳过（BBooru / WildDream / HypnoHub / Rule34.us 用 `.part` + 改名原子落盘）
> - **`--force`** —— 重下已存在的文件（BBooru / HypnoHub / Rule34.us），适合修下到一半的坏图
> - **请求节流** —— BBooru / HypnoHub / Rule34.us 支持 `--delay`（基准间隔）和 `--jitter`（随机额外量），让流量看起来不像机器在定时打点；遇到 HTTP 429/503 时所有工作线程一起退避 `--cooldown` 秒（默认 20），而不是各自撞墙。默认值（`0` / `0`）保持原行为（e-hentai / FurAffinity 的 `-d` 是随机延迟上限，等价于 `--delay 0 --jitter d`）
> - **并发** —— 多线程下载（BBooru / WildDream / HypnoHub / Rule34.us：`--threads`），带礼貌延时
> - **名单工作流（e-hentai）** —— `--dry-run` 打印名单**并**存成 JSON 清单文件；`--pick 2-4,7` 精确下载这几行。搜索结果会随新投稿漂移，所以存下来的清单才是 `--pick` 可复现的关键（`--from-manifest eh_manifest.json --pick 2-4,7`）。同一套 `--pick` 语法（`2-4,7` / `3-` / `-3` / `all`）在 `common.py` 里，其他站点可以复用
> - **不硬编码凭据** —— 只用环境变量 / cookies
> - **控制台安全输出** —— GBK 安全的 ASCII 标记（不用会让 cp936 终端崩掉的 emoji）
> - **统一文件命名** —— booru 各站统一 `p<post_id>.<ext>`，跨模式也能续传

## 🚀 Usage / 用法

```bat
:: e621（凭据可选，用环境变量）
set E621_USER=yourname & set E621_KEY=yourkey
python sites/e621/e6_scraper.py --tags feline -o ./feline

:: yiffverse（每标签 SSR 仅约 30 帖；浏览器版可滚动加载更多）
python sites/yiff/yiff_scraper.py feline --limit 50

:: e-hentai（单画廊）
python sites/e-hentai/EH_scraper_v2.py "https://e-hentai.org/g/xxx/yyy/" -o ./gallery

:: e-hentai（标签搜索 → 只看名单，不下载）
python sites/e-hentai/EH_scraper_v2.py --tags "language:chinese$ female:anal" --limit 30 --dry-run

:: e-hentai（挑着下：名单里的第 2,3,4,7 个）
python sites/e-hentai/EH_scraper_v2.py --tags "language:chinese$" --limit 30 --pick 2-4,7

:: e-hentai（精确复现：从名单文件挑，不受搜索结果变动影响）
python sites/e-hentai/EH_scraper_v2.py --from-manifest eh_manifest.json --pick 2-4,7

:: e-hentai（搜索模式下每个画廊只取前 5 张，免得一次拉满）
python sites/e-hentai/EH_scraper_v2.py --tags "language:chinese$" --limit 30 --pages 5

:: FurAffinity（需登录；先导出 cookies）
python sites/furaffinity/FA_get_cookies.py
python sites/furaffinity/FA_scraper.py "https://www.furaffinity.net/view/xxx/" --cookies fa_cookies.json

:: BBooru（JSON API；池子两种输入方式均可；--adult n 只看 general/safe，对应站内 set=general）
python sites/BBooru/B_scraper.py --tags "cute fox" --limit 100 --threads 12 -o ./out
python sites/BBooru/B_scraper.py --pool https://bbooru.com/index.php?page=pool&s=show&id=33976 -o ./out

:: BBooru artist 模式（按 pool 分组；不属于任何 pool 的进 others/）
python sites/BBooru/B_scraper.py --tags <artist_tag> --mode artist -o ./out
python sites/BBooru/B_scraper.py --tags <artist_tag> --mode artist --skip-others -o ./out
python sites/BBooru/B_scraper.py --tags <artist_tag> --mode artist --force-pool-check -o ./out

:: BBooru 单页 / 反转编号
python sites/BBooru/B_scraper.py --tags fox --page 2 -o ./out
python sites/BBooru/B_scraper.py --pool 33976 --pool-rev -o ./out

:: HypnoHub（纯 HTML，需代理；--adult n 时不显示成人原图）
python sites/hypnohub/H_scraper.py --tags spiral --limit 50 --threads 8 -o ./out

:: Rule34.us（纯 HTML；翻页自动探测）
python sites/rule34us/R_scraper.py --tags landscape --limit 50 --threads 8 -o ./out

:: WildDream（整本漫画；URL 两种形态自动兼容；--threads 并发下载）
python sites/wilddream/W_scraper.py "https://www.wilddream.net/art/userpage/gallery?userpagename=xxx&folderid=485" --limit inf --threads 12 -o ./out

:: 被站点限速时：放慢节奏 + 撞到 429 时全体刹车（bbooru / hypnohub / rule34us）
python sites/BBooru/B_scraper.py --tags fox --delay 1 --jitter 1.5 --cooldown 30 --threads 4 -o ./out

:: 重新下载已存在的图（修下到一半的坏文件；bbooru / hypnohub / rule34us）
python sites/hypnohub/H_scraper.py --tags spiral --force -o ./out

:: 链路正常但预检误报时，跳过预检
python sites/rule34us/R_scraper.py --tags landscape --no-preflight -o ./out
```

Dependencies: `requests` (+ `lxml` for e-hentai / FA / WildDream, + DrissionPage for yiff-auto / FA cookies).

> 依赖：`requests`（e-hentai / FA / WildDream 另需 `lxml`；yiff-auto / FA 取 cookies 另需 DrissionPage）。

### BBooru artist mode / 艺术家模式说明

Artist mode answers "which pools does this tag appear in, and what else is in them":

1. Search the tag through the JSON API (fast — one request per 100 posts, originals via `file_url`).
2. Check each post's `post-pool-list` page to learn which pools it belongs to.
3. For every pool found, fetch that pool's full post list and download it into its own folder.
4. Posts that are in no pool go to `others/` (add `--skip-others` to drop them).

Only the first 10 posts are probed by default; if none of them belongs to a pool the remaining
checks are skipped — that is the common case, since most tags have no pools at all. Use
`--force-pool-check` for a full scan when you suspect pools appear later in the list.

> 艺术家模式回答的是「这个标签出现在哪些池子里，那些池子里还有什么别的东西」：
>
> 1. 先用 JSON API 搜这个标签（很快 —— 每 100 帖一个请求，原图从 `file_url` 取）。
> 2. 逐个查帖子的 `post-pool-list` 页，看它属于哪些池子。
> 3. 对每个找到的池子，拉它的完整帖子列表，下到自己的文件夹里。
> 4. 不属于任何池子的帖子进 `others/`（加 `--skip-others` 就丢弃）。
>
> 默认只探测前 10 个帖子；如果一个池子都没命中，剩下的检查就跳过 —— 这是常见情况，因为大多数标签根本没有池子。
> 怀疑池子出现在列表后面时，用 `--force-pool-check` 做全量扫描。

## 🖥 BBooru GUI / standalone exe（图形界面版）

Don't want to touch the command line? `sites/BBooru/gui/` wraps the same engine in a tkinter GUI
and can be frozen into a single `.exe`:

> 不想碰命令行？`sites/BBooru/gui/` 把同一套引擎包进 tkinter 图形界面，还能冻成单文件 `.exe`：

```bat
python sites/BBooru/gui/app.py      :: run the GUI from source
cd sites/BBooru/gui & build_exe.bat :: build dist\BBooruDownloader.exe (needs PyInstaller)
```

The GUI calls `B_scraper.main(argv)` **in-process** (no subprocess), pipes the engine log into the
window and wires the Stop button to the engine's `request_cancel()`. It exposes the same three
modes as the CLI: tags / pool / artist.

> 图形界面**同进程**调用 `B_scraper.main(argv)`（不是起子进程），把引擎日志接到窗口里，Stop 按钮直接调引擎的 `request_cancel()`。
> 三种模式和命令行完全一致：标签 / 池子 / 艺术家。

> Prebuilt `BBooruDownloader.exe` is published under
> [Releases](../../releases) rather than committed here — a 12 MB binary in git history would
> bloat every clone forever.
>
> 预编译的 `BBooruDownloader.exe` 发布在 [Releases](../../releases) 里，**不进仓库** —— 12 MB 的二进制塞进 git 历史会让每次 clone 都变重。

## 🔒 Security / 安全

- Scripts contain **no real credentials**. e621 keys come from env vars; FA uses a local cookies file.
- `fa_cookies.json` and any `config.json` are **sensitive** — never commit them (see `.gitignore`).
- Downloaded content folders are **not** part of the repo — keep them out of commits.

> - 脚本里**没有任何真实凭据**。e621 的 key 走环境变量；FA 用本地 cookies 文件。
> - `fa_cookies.json` 和任何 `config.json` 都是**敏感文件** —— 绝不要提交（见 `.gitignore`）。
> - 下载的内容文件夹**不属于**仓库 —— 别把它们提交进去。

## 🐞 Known issues / 已知问题

Found and reproduced while building the sister project **pixivpaw** (a pixiv downloader that
copies `common.py`). Only **measured** issues are listed here — no speculation.
Full write-ups live in [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md), compiled with the help of the AI
coding assistant **WorkBuddy** — every finding was reproduced and manually reviewed.

> 这些问题是做姊妹项目 **pixivpaw**（一个拷贝了 `common.py` 的 pixiv 下载器）时发现并复现的。
> 这里只列**实测过**的问题，不做任何猜测。完整记录在 [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md)，
> 借助 AI 编程助手 **WorkBuddy** 整理 —— 每条都经过复现和人工复核。

> **Quick scan** — #1 a dead-code patch (removed); #2 e-hentai search needs **cursor paging**,
> `&page=N` is silently ignored; #3 the unified CLI's site→directory mapping is fixed; #4 `--pick`
> output filenames keep their **original list index**.
>
> **速览** —— #1 一段死代码补丁（已删除）；#2 e-hentai 搜索必须**游标翻页**，`&page=N` 会被静默忽略；
> #3 统一入口的站点→目录映射已修；#4 `--pick` 落盘文件名保留**原名单序号**。

| # | Issue | Affects | Status |
|---|---|---|---|
| 1 | `_safe_print` was dead code: `str.encode(enc, errors="replace")` can never raise, so its `except (UnicodeEncodeError, LookupError)` branch was unreachable and the wrapper only forwarded the original string. Measured with `PYTHONIOENCODING=gbk` — output was **byte-identical with and without the patch**; the `reconfigure(errors="replace")` lines *above* it are what actually prevent the crash. It also read `sys.stdout.encoding` unguarded, which raises `AttributeError` when stdout is `None` (e.g. a `--noconsole` frozen build). | `sites/BBooru/B_scraper.py`, `sites/hypnohub/H_scraper.py`, `sites/rule34us/R_scraper.py` — three byte-for-byte identical copies | ✅ **Fixed 2026-09-22** — all three copies deleted; `reconfigure(errors="replace")` alone was always sufficient |
| 2 | **e-hentai search pagination is cursor-based, not page-numbered.** `&page=0`, `&page=5` and `&page=50` returned the **same 25 galleries** (byte-identical gid sequence) — the parameter is silently ignored, so a "paginate by `page=N`" loop re-downloads page 1 forever without erroring. The real cursor is `&next=<gid>` (the last gid on the current page), taken from `<a id="unext">`. Total count comes from `Found about N results`. | `sites/e-hentai/EH_scraper_v2.py` (search mode) | ✅ **Fixed 2026-09-27** — cursor paging implemented; a probe now asserts `page=N` stays a no-op so a future revert gets caught |
| 3 | **Two site→directory mappings in the unified CLI were wrong**: `ehentai` resolved to `sites/ehentai/` and `fa` to `sites/fa/`, but the actual folders are `sites/e-hentai/` and `sites/furaffinity/`. `python felinepaw_tool.py ehentai ...` therefore died with `[Errno 2] No such file or directory` — the paths never existed. (Running the site scripts directly was unaffected, which is why it went unnoticed.) | `felinepaw_tool.py` — `build_command()` | ✅ **Fixed 2026-09-27** — mapping table corrected (`ehentai → e-hentai`, `fa → furaffinity`); both routes verified end-to-end |
| 4 | **(Lesson, not a live bug)** After `--pick 2-4`, files must keep their **original list index** (`2.* 3.* 4.*`), not be renumbered from 1. Renumbering makes a later `--pick 5-6` write `1.* 2.*`, which collides with existing files and gets silently skipped by the resume check. Also: the "already exists?" glob must exclude `.part`, or a half-written file permanently blocks its index. | e-hentai pick/resume logic | ✅ Avoided in implementation 2026-09-27 — see [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) #4 |

> **表格中文速览**（完整英文记录见上表与 [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md)）
>
> 1. **`_safe_print` 是死代码**（已删）—— `str.encode(enc, errors="replace")` 永远不会抛异常，所以它那个 `except` 分支根本走不到；
>    实测加不加都一样。真正防崩的是它上面那几行 `reconfigure(errors="replace")`。它还会在 stdout 为 `None` 时报 `AttributeError`。
> 2. **e-hentai 搜索翻页是游标式，不是 `page=N`**（已修）—— `&page=0/5/50` 返回同一批 25 个画廊，参数被静默忽略；
>    真正的游标是 `&next=<gid>`（本页最后一个 gid），从 `<a id="unext">` 取。
> 3. **统一入口的「站点 → 目录」映射写错了**（已修）—— `ehentai` 被映射到 `sites/ehentai/`、`fa` 到 `sites/fa/`，
>    而真实目录是 `sites/e-hentai/` 和 `sites/furaffinity/`，于是直接跑会报 `No such file or directory`。
> 4. **`--pick` 落盘必须保留原名单序号**（经验教训，非线上 bug）—— 重新编号会让下一次 `--pick` 与已有文件撞名、
>    被续传判定静默跳过；判「已存在」的 glob 还必须排除 `.part`。

## ⚠️ Disclaimers / 免责声明

- These tools are intended **only for personal appreciation, translation and learning**.
  **Commercial use or illegal profit-making is strictly prohibited.** Users bear all responsibility.
- **FurAffinity** explicitly prohibits automated bulk downloads in its ToS — using the FA scripts
  may risk your account. Use at your own risk; the author is not liable for any account action.
- **e621 / e-hentai / BBooru / WildDream / HypnoHub / Rule34.us**: comply with each site's API /
  automation guidelines and avoid excessive request rates; these are adult-oriented sites and the
  scripts include adult-rated content by default (`--adult`), use responsibly.
- Use at your own risk. The author is not liable for downloaded content or account safety.

> - 这些工具**仅供个人欣赏、翻译和学习**使用。**严禁商业用途或非法盈利**，责任由使用者自负。
> - **FurAffinity** 的服务条款明确禁止自动化批量下载 —— 用 FA 脚本可能危及你的账号。风险自负，作者不对任何账号处置负责。
> - **e621 / e-hentai / BBooru / WildDream / HypnoHub / Rule34.us**：请遵守各站点的 API / 自动化规范，避免过高的请求频率；
>   这些都是成人向站点，脚本默认就包含成人分级内容（`--adult`），请自行斟酌使用。
> - 使用风险自负。作者不对下载到的内容、也不对账号安全承担任何责任。

## 🔗 Related / 相关项目

### 🖥 [e621-downloader](https://github.com/SparkSlugcat/e621-downloader) — e621 的图形界面版

不想敲命令行？这是 e621 专用的 tkinter GUI，**免装 Python**，下载一个 exe 双击就能用。

[![Latest release](https://img.shields.io/github/v/release/SparkSlugcat/e621-downloader?label=Download&style=for-the-badge&color=brightgreen)](https://github.com/SparkSlugcat/e621-downloader/releases/latest)
[![Stars](https://img.shields.io/github/stars/SparkSlugcat/e621-downloader?style=for-the-badge&color=yellow)](https://github.com/SparkSlugcat/e621-downloader/stargazers)

- **No Python required** — grab `E621Downloader.exe` from
  [Releases](https://github.com/SparkSlugcat/e621-downloader/releases/latest) and double-click
- **Tag / Tag-page / Artist** download modes, bilingual (中文 / English) UI, live log + Stop button
- Shares the same engine design as the CLI scripts in [`sites/e621/`](sites/e621/) here

> - **无需 Python** —— 从 [Releases](https://github.com/SparkSlugcat/e621-downloader/releases/latest) 下载 `E621Downloader.exe` 双击即用
> - **标签 / 标签分页 / 画师** 三种下载模式，中英双语界面，实时日志 + 停止按钮
> - 与这里的 [`sites/e621/`](sites/e621/) 命令行脚本共用同一套引擎设计

> 💡 一句话：**想要命令行** → 用本仓库的 `sites/e621/`；**想要鼠标点** → 用 e621-downloader。

---

## 📁 Layout / 结构

```
felinepaw/
├── common.py               # shared base library / 公共基础库
├── KNOWN_ISSUES.md         # verified issues, with repro + suggested fixes / 已复现的问题，含复现步骤与建议修法
├── felinepaw_tool.py       # unified CLI launcher (all sites, whitelist param passthrough) / 统一命令行入口（全站点，白名单参数透传）
├── felinepaw_gui.py        # unified tkinter GUI / 统一 tkinter 图形界面
├── 启动.bat               # Windows: double-click → GUI (auto-detects Python + import self-check) / Windows 双击启动图形界面（自动定位 Python + 导入自检）
├── 启动(无窗口).vbs        # same, with zero console flash / 同上，零命令行窗口
└── sites/
    ├── e621/               # 5 CLI scripts (tags / page / artist / pool / pool-reversed) / 5 个 CLI 脚本（标签 / 分页 / 画师 / 池子 / 池子反转）
    ├── e-hentai/           # EH_scraper_v2.py (API + HTML)
    ├── yiff/               # yiff_scraper.py + yiff_auto_scraper.py (browser) / （浏览器版）
    ├── furaffinity/        # FA_scraper.py + FA_get_cookies.py
    ├── BBooru/             # B_scraper.py (JSON API tags / pools / artist mode) / （JSON API：标签 / 池子 / 艺术家模式）
    │   └── gui/            # app.py + BBooruDownloader.spec (tkinter GUI / single-file exe) / （tkinter 界面 / 单文件 exe）
    ├── wilddream/          # W_scraper.py (comic gallery downloader) / （整本漫画下载）
    ├── hypnohub/           # H_scraper.py (HTML only) / （仅 HTML）
    └── rule34us/           # R_scraper.py (HTML only) / （仅 HTML）
```

## License

[MIT](LICENSE)

## 🙏 Acknowledgements / 鸣谢

感谢项目发布近一个月来所有为它点 star 的 **3 位朋友**，这将成为我更新的一大动力！

Thanks to everyone who starred this project over its first month — **three of you** so far — it is a
real motivation to keep shipping.
