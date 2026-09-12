# 🐾 felinepaw

Multi-site furry image downloader scripts — **e621 / yiffverse / e-hentai / FurAffinity / BBooru / WildDream / HypnoHub / Rule34.us** in one place.
All scripts share the same CLI conventions (`-o`, `--limit`, `--proxy`, `-w`, `-d`) and a common
base library ([`common.py`](common.py)) for proxy detection, sessions, resume and limits.
A unified launcher ([`felinepaw_tool.py`](felinepaw_tool.py), CLI + tkinter GUI) dispatches all sites from one command.

> ⭐ If this project helps you, a Star would mean a lot. Thanks!
>
> 如果这个项目对你有帮助，欢迎点个 ⭐ Star，非常感谢！

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
| **e621 / e926** | `sites/e621/` | Official JSON API. Credentials via `E621_USER` / `E621_KEY` env vars (guest if unset) |
| **yiffverse** | `sites/yiff/` | SSR + browser-auto (DrissionPage) variants; no pools, tag-based |
| **e-hentai** | `sites/e-hentai/` | Official `gdata` API for metadata + HTML for image links |
| **FurAffinity** | `sites/furaffinity/` | Title-normalization series detection; login via cookies (`FA_get_cookies.py`) |
| **BBooru** | `sites/BBooru/B_scraper.py` | Gelbooru-style built-in JSON API, **no API key**. Tags (`--tags`), pools (`--pool <show URL / id>`), auto HTML fallback, `--adult y/n`, **artist mode** (pool-grouped download) |
| **WildDream** | `sites/wilddream/W_scraper.py` | Comic-gallery (folder) downloads from a gallery URL; polite throttling + atomic `.part` resume; threaded (`--threads`); `--limit` default 80 |
| **HypnoHub** | `sites/hypnohub/H_scraper.py` | Gelbooru/Shimmie engine, **HTML only** (no usable JSON API); original taken from `img#image`; `--page` for a single page |
| **Rule34.us** | `sites/rule34us/R_scraper.py` | Custom engine, **HTML only**; original linked by `<li class="character-tag">Original</li>`; automatic pagination probe |

## ✨ Common features / 通用特性

- **Proxy auto-detect** — follows Windows system proxy / env vars (`--proxy off` to disable)
- **`--limit`** — default 120 (WildDream: 80), `--limit N`, `--limit inf` (download everything)
- **Resume** — existing files are skipped (atomic `.part` + rename on BBooru / WildDream / HypnoHub / Rule34.us)
- **Concurrency** — threaded downloads (BBooru / WildDream / HypnoHub / Rule34.us: `--threads`) with polite delays
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

:: e-hentai（画廊）
python sites/e-hentai/EH_scraper_v2.py "https://e-hentai.org/g/xxx/yyy/" -o ./gallery

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

## 🔒 Security / 安全

- Scripts contain **no real credentials**. e621 keys come from env vars; FA uses a local cookies file.
- `fa_cookies.json` and any `config.json` are **sensitive** — never commit them (see `.gitignore`).
- Downloaded content folders are **not** part of the repo — keep them out of commits.

## ⚠️ Disclaimers / 免责声明

- These tools are intended **only for personal appreciation, translation and learning**.
  **Commercial use or illegal profit-making is strictly prohibited.** Users bear all responsibility.
- **FurAffinity** explicitly prohibits automated bulk downloads in its ToS — using the FA scripts
  may risk your account. Use at your own risk; the author is not liable for any account action.
- **e621 / e-hentai / BBooru / WildDream / HypnoHub / Rule34.us**: comply with each site's API /
  automation guidelines and avoid excessive request rates; these are adult-oriented sites and the
  scripts include adult-rated content by default (`--adult`), use responsibly.
- Use at your own risk. The author is not liable for downloaded content or account safety.

## 🔗 Related

- [e621-downloader](https://github.com/SparkSlugcat/e621-downloader) — the GUI version of the e621
  downloader (tkinter, bilingual UI, standalone exe). CLI scripts here share its engine concepts.

## 📁 Layout / 结构

```
felinepaw/
├── common.py               # shared base library
├── felinepaw_tool.py       # unified CLI launcher (all sites, whitelist param passthrough)
├── felinepaw_gui.py        # unified tkinter GUI
└── sites/
    ├── e621/               # 5 CLI scripts (tags / page / artist / pool / pool-reversed)
    ├── e-hentai/           # EH_scraper_v2.py (API + HTML)
    ├── yiff/               # yiff_scraper.py + yiff_auto_scraper.py (browser)
    ├── furaffinity/        # FA_scraper.py + FA_get_cookies.py
    ├── BBooru/             # B_scraper.py (JSON API tags / pools / artist mode)
    ├── wilddream/          # W_scraper.py (comic gallery downloader)
    ├── hypnohub/           # H_scraper.py (HTML only)
    └── rule34us/           # R_scraper.py (HTML only)
```

## License

[MIT](LICENSE)
