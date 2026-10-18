# Pending Bugs / 待修复问题

> **文档范围** —— 本文件记录 **2026-10-18 中英双语化改造**期间通过静态分析发现的、**尚未修复**的缺陷
> 与设计陷阱。与 `KNOWN_ISSUES.md` 的分工是：那边收"已复现并定论（多数已修）"的条目，本文件收**待办**。
> 每条给出：严重级别、影响范围、触发条件、根因、修法与验证方式。修复后请把条目迁进 `KNOWN_ISSUES.md` 并在此标记。
>
> **2026-10-18 晚更新** —— B1–B4 已修复并迁入 `KNOWN_ISSUES.md` #5–#8（四条均已离线验证：
> 命名空间用 `importlib` 复核，B4 用真实 Tk 窗口 `withdraw` 后切换下拉框实测）。
> 仍未处理：B5（等 spark 决定是否统一 `.pawout`）、B7（下次发版重打包）、B8（有意跳过）、B9（旧快照去留）。
>
> **Scope (EN)** —— This file lists defects and design traps found by static analysis during the
> 2026-10-18 bilingual (zh/en) refactor and **not yet fixed**. `KNOWN_ISSUES.md` holds reproduced,
> settled items (mostly fixed); this file holds the **open backlog**. Each entry gives severity,
> scope, trigger condition, root cause, a suggested fix and how to verify it.
>
> **工具声明 / Tooling disclosure** —— 本文件的静态分析、跨文件比对与排版由 AI 编程助手 **WorkBuddy**
> 完成。B1–B3 的"名字确实不存在"是用 `importlib` 导入模块后检查命名空间确认的（见 §复现方式），
> 并非仅靠肉眼推断；未联网、未实跑登录流程。**Tooling disclosure:** the static analysis, cross-file
> diffing and formatting were produced with the AI coding assistant **WorkBuddy**. B1–B3 were
> confirmed by importing each module and inspecting its namespace, not by eyeballing alone; no
> network access and no login flow was exercised.

**索引 / Index**

| ID | 主题 | 严重级别 | 影响面 | 状态 |
|---|---|---|---|---|
| B1 | `safe_name` 未定义 → `NameError` | 高（必崩） | CLI 直跑 FA 且不带 `-o` | ✅ 已修 2026-10-18 → #5 |
| B2 | `requests` 未导入 → `NameError` | 中（吞异常） | yiff 自动模式的 HEAD 探测 | ✅ 已修 2026-10-18 → #6 |
| B3 | `urlparse` 未导入 → `NameError` | 低 | `felinepaw_auto/probe.py --try-api` | ✅ 已修 2026-10-18 → #7 |
| B4 | BBooru 用**译文**当模式身份 | 低（静默回退） | BBooru GUI 模式下拉 | ✅ 已修 2026-10-18 → #8 |
| B5 | `sites/e-hentai/EH_scraper_v2.py` 未跟进 `.pawout` | 中（行为不一致） | felinepaw 的 EH 站点 | ⬜ 待定 |
| B6 | `清单已存:` 是跨进程契约 | 设计陷阱 | pixivpaw GUI ↔ CLI | ⚠️ 已加注释保护 |
| B7 | 已发布的 exe 未重打包 | 待发布 | `BBooruDownloader.exe` / `E621Downloader.exe` | ⬜ 下次发版 |
| B8 | `felinepaw_auto` 未双语化 | 低 | 该工具全部输出 | ⬜ 有意跳过 |
| B9 | `爬虫项目/scraper/` 是旧快照 | 低 | 非仓库目录 | ⬜ 待决定 |

---

## B1 `safe_name` 未定义 → `NameError`（高）

| 字段 | 内容 |
|---|---|
| **状态** | ✅ 已修 2026-10-18 → `KNOWN_ISSUES.md` **#5**（`safe_name(...)` → `sanitize_filename(...)`，已用 `importlib` 复核命名空间） |
| **严重级别** | 高 —— 走到就**必崩**，不是偶发 |
| **影响范围** | `sites/furaffinity/FA_scraper.py:542` |
| **触发条件** | **直接跑站点脚本** `FA_scraper.py`，**不带 `-o/--output`**，且**不是** `--dry-run` |

**Summary (EN)** — `FA_scraper.py` calls `safe_name(...)` at line 542 but never defines or imports
it: the file aliases only `sanitize_filename` (line 68). `safe_name` is not in `common.py` either.
Importing the module succeeds and `hasattr(mod, "safe_name")` is `False`, so the failure surfaces
only at that line.

### 为什么一直没被发现

`felinepaw_tool.py:203` 里是 `_add("-o", args.output or str(common.local_out_root()))` ——
**统一入口永远会补一个 `-o`**，所以 GUI 和 `felinepaw_tool.py` 走这条路时 `args.output` 恒非空，
`else` 分支是死的。只有"绕过统一入口、直接敲站点脚本"才会踩到。

### 现场

```python
# sites/furaffinity/FA_scraper.py:68
sanitize_filename = common.sanitize_filename        # 只 alias 了这一个

# sites/furaffinity/FA_scraper.py:542
out = Path(args.output) if args.output else Path(safe_name(series_key or title))
#                                            ^^^^^^^^^ 未定义
```

### 建议修法

```python
out = Path(args.output) if args.output else Path(sanitize_filename(series_key or title))
```

（两处语义等价：`sanitize_filename` 就是用来做"文件名安全化"的那一个。若当初 `safe_name`
另有语义——例如还加了长度截断——再单独补一个函数，别直接替换。）

### 验证

```bash
python sites/furaffinity/FA_scraper.py <某个 view URL> --dry-run   # 只验证能过 --dry-run
python sites/furaffinity/FA_scraper.py <某个 view URL>             # 不带 -o，应能落盘到当前目录
```

---

## B2 `requests` 未导入 → `except` 分支自己抛 `NameError`（中）

| 字段 | 内容 |
|---|---|
| **状态** | ✅ 已修 2026-10-18 → `KNOWN_ISSUES.md` **#6**（文件顶部补 `import requests`，导入后 `hasattr` 为 `True`） |
| **严重级别** | 中 —— 只在 HEAD 请求抛异常时命中；命中即**把"跳过这张"变成"整个函数中断"** |
| **影响范围** | `sites/yiff/yiff_auto_scraper.py:210` |
| **触发条件** | 自动模式的扩展名探测里，`session.head(url, timeout=20)` 抛任意 `requests` 层异常 |

**Summary (EN)** — Line 210 reads `except requests.RequestException:` but `requests` is never
imported in that file (`import requests` is absent; only `yiff_scraper` is imported as `ys` and
`common` is used). The handler's class expression is evaluated *when an exception arrives*, so a
network hiccup turns "skip this extension" into `NameError: name 'requests' is not defined`,
aborting the rest of the loop.

### 现场

```python
# sites/yiff/yiff_auto_scraper.py:204-211
for ext in exts:
    url = ys.build_original_url(pid, kind, chunk, ext)
    try:
        r = session.head(url, timeout=20, allow_redirects=True)
    except requests.RequestException:     # ← requests 没 import
        continue
```

### 建议修法

顶部补 `import requests`。**不要**改成 `ys.requests` —— 那是在依赖"邻居碰巧也 import 了 requests"，
`yiff_scraper.py` 哪天去掉这个 import 就会二次踩坑。

### 验证

模块导入后 `hasattr(mod, "requests")` 应为 `True`；再确认 `except` 分支被走到时不再抛 `NameError`
（可临时把 `session.head` 换成一个 `raise requests.ConnectionError` 的桩，离线可测）。

---

## B3 `urlparse` 未导入 → `NameError`（低）

| 字段 | 内容 |
|---|---|
| **状态** | ✅ 已修 2026-10-18 → `KNOWN_ISSUES.md` **#7**（补 `from urllib.parse import urlparse`） |
| **严重级别** | 低 —— 只有 `--try-api` 才走 |
| **影响范围** | `felinepaw_auto/probe.py:36` |
| **触发条件** | 带 `--try-api` 跑 `probe.py` |

**Summary (EN)** — `probe.py` imports `argparse`, `json`, `sys`, `requests`, `core` and
`from core import select_values, polite_get, ensure_query, urljoin` — but not `urlparse`.
Line 36 uses it twice in one expression.

### 现场

```python
# felinepaw_auto/probe.py:36
scheme_host = urlparse(start_url).scheme + "://" + urlparse(start_url).netloc
```

### 建议修法

在 `from core import ...` 那一行后面补：

```python
from urllib.parse import urlparse
```

（`core.py` 里若已经 import 了 `urlparse`，也**不要**靠 `from core import urlparse` 蹭——
那是隐式依赖，`core` 一改就断。）

---

## B4 BBooru 用「译文」当模式身份（低，静默回退）

| 字段 | 内容 |
|---|---|
| **状态** | ✅ 已修 2026-10-18 → `KNOWN_ISSUES.md` **#8**（改按下拉框 `current()` 下标取模式，真实 Tk 实测通过） |
| **严重级别** | 低 —— 当前三种语言下译文互不相同，所以看不出来 |
| **影响范围** | `sites/BBooru/gui/app.py:431` `_mode_key_from_display()` |
| **触发条件** | 任意两个模式在**同一语言下译文相同**；或以后加第三种语言时译名撞车 |

**Summary (EN)** — `_mode_key_from_display()` reverse-maps the Combobox **display string** back to
an internal mode key by comparing `i18n.t("bb_mode_" + k) == disp`. Any collision (two modes
translating identically, or a new locale) silently falls back to `"tags"`. pixivpaw's picker
already does this correctly with `Combobox.current()` (index), and so does `felinepaw_gui.py`.

### 现场

```python
# sites/BBooru/gui/app.py:429-434
def _mode_key_from_display(self):
    disp = self.mode_var.get()
    for k in MODE_KEYS:
        if i18n.t("bb_mode_" + k) == disp:
            return k
    return "tags"                    # ← 撞车时静默变成 tags
```

### 建议修法

跟 pixivpaw 一致：状态只存**下标**（`self._mode_idx`），下拉框绑
`cb.bind("<<ComboboxSelected>>", lambda e: cb.current())`；重建界面时用 `cb.current(self._mode_idx)`
回填，不要拿 `mode_var` 的文案去反查。

### 验证

造一个临时词条让两个模式译文相同（如都填 `"X"`），选第二个模式，看 `self._mode_key` 是否仍是第二个。

---

## B5 `sites/e-hentai/EH_scraper_v2.py` 未跟进 `.pawout` 统一（中，行为不一致）

| 字段 | 内容 |
|---|---|
| **状态** | 🟡 待定 —— 需要 spark 决定"统一"还是"保持两份独立行为" |
| **严重级别** | 中 —— 不是崩溃，是**同一个站点的两份拷贝下载落点不同** |
| **影响范围** | `felinepaw/sites/e-hentai/EH_scraper_v2.py` vs `e-hentai-paw/EH_scraper_v2.py` |
| **差异数量** | 4 处（3 处落盘目录 + 1 处 `--output` 帮助文案） |

**Summary (EN)** — The two copies are the same code, but the felinepaw copy has **not** picked up
the `.pawout` default-output change (2026-10-16). It falls back to the *current working directory*
instead of the configured `.pawout` root. During the bilingual refactor this divergence was
**deliberately preserved verbatim**; unifying it would change where files land.

| # | 位置（两份对齐行号） | e-hentai-paw 版（新） | felinepaw 版（旧，保留） |
|---|---|---|---|
| 1 | 448 `--output` 的 help | `eh_help_output`（说明留空读 `.pawout`） | `eh_help_output_nopawout`（只说 搜索/单画廊） |
| 2 | 661 | `common.local_out_root() / safe_dir(title)` | `Path(safe_dir(title))` |
| 3 | 745 | `common.local_out_root() / query_dir_name(query)` | `Path(query_dir_name(query))` |
| 4 | 840 | `common.local_out_root() / safe_dir(title)` | `Path(safe_dir(title))` |

### 建议

统一（改成读 `local_out_root()`），并在 README / 提交说明里写清"**下载落点变了**"。
不统一也行，但要在 `felinepaw/README.md` 的 e-hentai 小节显式写明"默认落到当前目录，不读 `.pawout`"，
否则使用者会以为两个项目行为一致。

### 验证

统一后：在项目根放一个 `.pawout` 指向临时目录，跑一次 `--dry-run` 之外的真实下载，
确认落点是 `.pawout` 里那个目录而不是 cwd。

---

## B6 `清单已存:` 是跨进程契约（设计陷阱，已加注释）

| 字段 | 内容 |
|---|---|
| **状态** | ⚠️ 已在本轮加注释保护，**未做代码层加固** |
| **严重级别** | 高（静默失效）—— 不报错，只是清单复用悄悄无效、每次重跑检索 |
| **影响范围** | `pixivpaw/pixivpaw_tool.py` 收尾那行 ↔ `pixivpaw/pixivpaw_gui.py` 的 `MANIFEST_TAG` |

**Summary (EN)** — The GUI scrapes the manifest path out of the child process's stdout by searching
for the literal `清单已存:`. The line is now `Manifest saved / 清单已存: <path>` — the English part
**must stay in front**, because the GUI does `find("清单已存:")`; putting English first would make
the search miss and manifest reuse would fail silently.

### 建议加固（可选）

把契约文本提到 `pixivpaw_tool.py` 的模块常量（例如 `MANIFEST_TAG = "清单已存:"`），
GUI 直接 `from pixivpaw_tool import MANIFEST_TAG`，两边共用一个字面量。改一处就行，
不会再有"改了工具忘了 GUI"的可能。

---

## B7 已发布的 exe 未重打包（待发布）

| 字段 | 内容 |
|---|---|
| **状态** | ⬜ 下次发版一起做（2026-10-18 决定） |
| **影响** | `BBooruDownloader.exe`、`E621Downloader.exe` 内的界面文案仍是**打包那一刻的中文快照** |

**Summary (EN)** — The published binaries are frozen snapshots; their UI is still Chinese-only even
though the source now supports zh/en. Rebuild with the existing `.spec` files (they already carry
the `tcl86t.dll`/`tk86t.dll` fix) and re-run `--selftest` before publishing.

---

## B8 `felinepaw_auto` 未双语化（低，有意跳过）

| 字段 | 内容 |
|---|---|
| **状态** | ⬜ 有意跳过（2026-10-18 spark 决定：auto 不管） |
| **规模** | 约 14 处中文串（GUI / CLI 输出） |

**Summary (EN)** — `felinepaw_auto/` was intentionally excluded from the bilingual refactor.
Adding it later means: create `i18n.py` with its own `APP_ID`, add `PAW_LANG` to its GUI's
child-process env, then convert the prints. Follow `_i18n_spec.md` in the workspace root.

---

## B9 `爬虫项目/scraper/` 是旧快照（低）

| 字段 | 内容 |
|---|---|
| **状态** | ⬜ 待决定：删除 / 归档 / 明确标注 |
| **问题** | 该目录**不是 git 仓库**，内容是 `felinepaw` + `e-hentai-paw` 的早期拷贝，含**同样的 B1 / B2 缺陷** |

**Summary (EN)** — `爬虫项目/scraper/` is a stale, non-versioned copy containing the same B1/B2
defects. It is easy to mistake for the live tree. Either delete it or add a `README` at its root
saying "archived snapshot, do not edit".

---

## 本轮已顺手修掉（留档，供查证）

| ID | 问题 | 文件 | 后果 |
|---|---|---|---|
| F1 | 词条 `px_err_not_json` 写的是 `{url}`，调用点传的是 `head=` | `pixivpaw/px_api.py:751` | 跑到该分支即 `KeyError`（由 `check_i18n_calls.py` 抓出） |
| F2 | `"…%s" % msg or url` 的 `%` 优先级让 fallback 永不到达 | `pixivpaw/px_api.py` | message 为空时打印字符串 `None` |
| F3 | `QueueWriter` 里 `self.encoding = "utf-8"` 给只读描述符赋值 | `felinepaw/sites/BBooru/gui/app.py` | 每点一次开始下载就在线程里 `AttributeError` |
| F4 | `felinepaw/sites/e-hentai/…` 与 `e-hentai-paw/…` 的双语词条不一致 | `i18n.py` / `i18n_sites_misc.py` | `eh_` 前缀词条已逐条对齐 |

---

## 复现方式（B1–B3 的"名字确实不存在"是如何确认的）

不联网、不登录，只用导入后看命名空间：

```python
import importlib, sys
sys.path[:0] = [r"…\felinepaw", r"…\felinepaw\sites\furaffinity"]
m = importlib.import_module("FA_scraper")
print(hasattr(m, "safe_name"))      # False
```

实测输出（2026-10-18，py39 / Windows 11）：

```
sites/furaffinity/FA_scraper.py    导入 OK | 有 safe_name  ? False
sites/yiff/yiff_auto_scraper.py    导入 OK | 有 requests   ? False
felinepaw_auto/probe.py            导入 OK | 有 urlparse   ? False
```

模块**能正常导入**，说明这不是循环依赖或语法问题 —— 纯粹的"用了一个不存在的名字"，
所以 `python -m py_compile` 和任何语法检查都抓不到，只有真正执行到那一行才炸。
