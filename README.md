# 🐾 felinepaw

Multi-site furry image downloader scripts — **e621 / yiffverse / e-hentai / FurAffinity / BBooru / WildDream** in one place.
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
| **BBooru** | `sites/BBooru/B_scraper.py` | Gelbooru-style built-in JSON API, **no API key**. Tags (`--tags`) or pools (`--pool <show URL / id>`), auto HTML fallback, `--adult y/n` |
| **WildDream** | `sites/wilddream/W_scraper.py` | Comic-gallery (folder) downloads from a gallery URL; polite throttling + atomic `.part` resume; `--limit` default 80 |

## ✨ Common features / 通用特性

- **Proxy auto-detect** — follows Windows system proxy / env vars (`--proxy off` to disable)
- **`--limit`** — default 120 (WildDream: 80), `--limit N`, `--limit inf` (download everything)
- **Resume** — existing files are skipped (atomic `.part` + rename on BBooru / WildDream)
- **Concurrency** — threaded downloads (BBooru: `--threads`) with polite delays
- **No hardcoded credentials** — env vars / cookies only
- **Console-safe output** — GBK-safe markers (no emoji that crash cp936 terminals)

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

:: BBooru（JSON API；池子两种输入方式均可；--adult n 只看 safe）
python sites/BBooru/B_scraper.py --tags "cute fox" --limit 100 --threads 12 -o ./out
python sites/BBooru/B_scraper.py --pool https://bbooru.com/index.php?page=pool&s=show&id=33976 -o ./out

:: WildDream（整本漫画；URL 两种形态自动兼容）
python sites/wilddream/W_scraper.py "https://www.wilddream.net/art/userpage/gallery?userpagename=xxx&folderid=485" --limit inf -o ./out
```

Dependencies: `requests` (+ `lxml` for e-hentai / FA / WildDream, + DrissionPage for yiff-auto / FA cookies).

## 🔒 Security / 安全

- Scripts contain **no real credentials**. e621 keys come from env vars; FA uses a local cookies file.
- `fa_cookies.json` and any `config.json` are **sensitive** — never commit them (see `.gitignore`).
- Downloaded content folders are **not** part of the repo — keep them out of commits.

## ⚠️ Disclaimers / 免责声明

- These tools are intended **only for personal appreciation, translation and learning**.
  **Commercial use or illegal profit-making is strictly prohibited.** Users bear all responsibility.
- **FurAffinity** explicitly prohibits automated bulk downloads in its ToS — using the FA scripts
  may risk your account. Use at your own risk; the author is not liable for any account action.
- **e621 / e-hentai / BBooru / WildDream**: comply with each site's API / automation guidelines and
  avoid excessive request rates; some scripts include adult-rated content by default (`--adult`),
  use responsibly.
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
    ├── BBooru/             # B_scraper.py (JSON API tags / HTML pools)
    └── wilddream/          # W_scraper.py (comic gallery downloader)
```

## License

[MIT](LICENSE)
