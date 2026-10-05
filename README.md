# 🐾 felinepaw

Multi-site furry image downloader scripts — **e621 / yiffverse / e-hentai / FurAffinity / BBooru / WildDream / HypnoHub / Rule34.us** in one place.
All scripts share the same CLI conventions (`-o`, `--limit`, `--proxy`, `-w`, `-d`,
`--delay`, `--jitter`, `--cooldown`, `--force`) and a common
base library ([`common.py`](common.py)) for proxy detection, sessions, resume, limits,
request pacing and a fail-fast proxy preflight.
A unified launcher ([`felinepaw_tool.py`](felinepaw_tool.py), CLI + tkinter GUI) dispatches all sites from one command.

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

### BBooru artist mode / 艺术家模式说明

Artist mode answers "which pools does this tag appear in, and what else is in them":

1. Search the tag through the JSON API (fast — one request per 100 posts, originals via `file_url`).
2. Check each post's `post-pool-list` page to learn which pools it belongs to.
3. For every pool found, fetch that pool's full post list and download it into its own folder.
4. Posts that are in no pool go to `others/` (add `--skip-others` to drop them).

Only the first 10 posts are probed by default; if none of them belongs to a pool the remaining
checks are skipped — that is the common case, since most tags have no pools at all. Use
`--force-pool-check` for a full scan when you suspect pools appear later in the list.

## 🖥 BBooru GUI / standalone exe（图形界面版）

Don't want to touch the command line? `sites/BBooru/gui/` wraps the same engine in a tkinter GUI
and can be frozen into a single `.exe`:

```bat
python sites/BBooru/gui/app.py      :: run the GUI from source
cd sites/BBooru/gui & build_exe.bat :: build dist\BBooruDownloader.exe (needs PyInstaller)
```

The GUI calls `B_scraper.main(argv)` **in-process** (no subprocess), pipes the engine log into the
window and wires the Stop button to the engine's `request_cancel()`. It exposes the same three
modes as the CLI: tags / pool / artist.

> Prebuilt `BBooruDownloader.exe` is published under
> [Releases](../../releases) rather than committed here — a 12 MB binary in git history would
> bloat every clone forever.

## 🔒 Security / 安全

- Scripts contain **no real credentials**. e621 keys come from env vars; FA uses a local cookies file.
- `fa_cookies.json` and any `config.json` are **sensitive** — never commit them (see `.gitignore`).
- Downloaded content folders are **not** part of the repo — keep them out of commits.

## 🐞 Known issues / 已知问题

Found and reproduced while building the sister project **pixivpaw** (a pixiv downloader that
copies `common.py`). Only **measured** issues are listed here — no speculation.
Full write-ups live in [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md).

| # | Issue | Affects | Status |
|---|---|---|---|
| 1 | `_safe_print` was dead code: `str.encode(enc, errors="replace")` can never raise, so its `except (UnicodeEncodeError, LookupError)` branch was unreachable and the wrapper only forwarded the original string. Measured with `PYTHONIOENCODING=gbk` — output was **byte-identical with and without the patch**; the `reconfigure(errors="replace")` lines *above* it are what actually prevent the crash. It also read `sys.stdout.encoding` unguarded, which raises `AttributeError` when stdout is `None` (e.g. a `--noconsole` frozen build). | `sites/BBooru/B_scraper.py`, `sites/hypnohub/H_scraper.py`, `sites/rule34us/R_scraper.py` — three byte-for-byte identical copies | ✅ **Fixed 2026-09-22** — all three copies deleted; `reconfigure(errors="replace")` alone was always sufficient |
| 2 | **e-hentai search pagination is cursor-based, not page-numbered.** `&page=0`, `&page=5` and `&page=50` returned the **same 25 galleries** (byte-identical gid sequence) — the parameter is silently ignored, so a "paginate by `page=N`" loop re-downloads page 1 forever without erroring. The real cursor is `&next=<gid>` (the last gid on the current page), taken from `<a id="unext">`. Total count comes from `Found about N results`. | `sites/e-hentai/EH_scraper_v2.py` (search mode) | ✅ **Fixed 2026-09-27** — cursor paging implemented; a probe now asserts `page=N` stays a no-op so a future revert gets caught |
| 3 | **Two site→directory mappings in the unified CLI were wrong**: `ehentai` resolved to `sites/ehentai/` and `fa` to `sites/fa/`, but the actual folders are `sites/e-hentai/` and `sites/furaffinity/`. `python felinepaw_tool.py ehentai ...` therefore died with `[Errno 2] No such file or directory` — the paths never existed. (Running the site scripts directly was unaffected, which is why it went unnoticed.) | `felinepaw_tool.py` — `build_command()` | ✅ **Fixed 2026-09-27** — mapping table corrected (`ehentai → e-hentai`, `fa → furaffinity`); both routes verified end-to-end |
| 4 | **(Lesson, not a live bug)** After `--pick 2-4`, files must keep their **original list index** (`2.* 3.* 4.*`), not be renumbered from 1. Renumbering makes a later `--pick 5-6` write `1.* 2.*`, which collides with existing files and gets silently skipped by the resume check. Also: the "already exists?" glob must exclude `.part`, or a half-written file permanently blocks its index. | e-hentai pick/resume logic | ✅ Avoided in implementation 2026-09-27 — see [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) #4 |

> **中文小结**：那段 `_safe_print` 补丁实测无效 —— 真正起作用的是它上面 4 行的
> `reconfigure(errors="replace")`；它在 3 个站点各复制了一份，**已于 2026-09-22 三处一并删除**。
> 保留此条只作记录：`sites/wilddream/W_scraper.py` 只有 `reconfigure`，那才是正确写法。
> 复现与推理过程见 [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md)。

## ⚠️ Disclaimers / 免责声明

- These tools are intended **only for personal appreciation, translation and learning**.
  **Commercial use or illegal profit-making is strictly prohibited.** Users bear all responsibility.
- **FurAffinity** explicitly prohibits automated bulk downloads in its ToS — using the FA scripts
  may risk your account. Use at your own risk; the author is not liable for any account action.
- **e621 / e-hentai / BBooru / WildDream / HypnoHub / Rule34.us**: comply with each site's API /
  automation guidelines and avoid excessive request rates; these are adult-oriented sites and the
  scripts include adult-rated content by default (`--adult`), use responsibly.
- Use at your own risk. The author is not liable for downloaded content or account safety.

## 🔗 Related / 相关项目

### 🖥 [e621-downloader](https://github.com/SparkSlugcat/e621-downloader) — e621 的图形界面版

不想敲命令行？这是 e621 专用的 tkinter GUI，**免装 Python**，下载一个 exe 双击就能用。

[![Latest release](https://img.shields.io/github/v/release/SparkSlugcat/e621-downloader?label=Download&style=for-the-badge&color=brightgreen)](https://github.com/SparkSlugcat/e621-downloader/releases/latest)
[![Stars](https://img.shields.io/github/stars/SparkSlugcat/e621-downloader?style=for-the-badge&color=yellow)](https://github.com/SparkSlugcat/e621-downloader/stargazers)

- **No Python required** — grab `E621Downloader.exe` from
  [Releases](https://github.com/SparkSlugcat/e621-downloader/releases/latest) and double-click
- **Tag / Tag-page / Artist** download modes, bilingual (中文 / English) UI, live log + Stop button
- Shares the same engine design as the CLI scripts in [`sites/e621/`](sites/e621/) here

> 💡 一句话：**想要命令行** → 用本仓库的 `sites/e621/`；**想要鼠标点** → 用 e621-downloader。

---

## 📁 Layout / 结构

```
felinepaw/
├── common.py               # shared base library
├── KNOWN_ISSUES.md         # verified issues, with repro + suggested fixes
├── felinepaw_tool.py       # unified CLI launcher (all sites, whitelist param passthrough)
├── felinepaw_gui.py        # unified tkinter GUI
└── sites/
    ├── e621/               # 5 CLI scripts (tags / page / artist / pool / pool-reversed)
    ├── e-hentai/           # EH_scraper_v2.py (API + HTML)
    ├── yiff/               # yiff_scraper.py + yiff_auto_scraper.py (browser)
    ├── furaffinity/        # FA_scraper.py + FA_get_cookies.py
    ├── BBooru/             # B_scraper.py (JSON API tags / pools / artist mode)
    │   └── gui/            # app.py + BBooruDownloader.spec (tkinter GUI / single-file exe)
    ├── wilddream/          # W_scraper.py (comic gallery downloader)
    ├── hypnohub/           # H_scraper.py (HTML only)
    └── rule34us/           # R_scraper.py (HTML only)
```

## License

[MIT](LICENSE)

## 🙏 Acknowledgements / 鸣谢

感谢项目发布近一个月来所有点 star 的人（尽管只有我和另一个人），这将成为我更新的一大动力！

Thanks to everyone who starred this project over its first month — even if it is just one other
person and me, it is a real motivation to keep shipping.
