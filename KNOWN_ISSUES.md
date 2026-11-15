# Known Issues / 已知问题

> **文档范围** —— 本文件记录**已实测确认**的缺陷与设计陷阱，面向维护者与二次开发者。
> 每条包含：状态、严重级别、影响范围、根因、实测证据、修复方案与验证方式。
> 仅收录有复现记录的问题，不收录推测。
>
> **工具声明** —— 本文件的实测数据采集、根因分析与排版由 AI 编程助手 **WorkBuddy** 协助完成；
> 所有结论均已在作者本机环境复现并人工复核。如有疑义，请以源码与文中的复现步骤为准。
>
> **Tooling disclosure** —— The measurements, root-cause analysis and formatting in this document
> were produced with the assistance of the AI coding assistant **WorkBuddy**. Every finding was
> reproduced on the author's machine and reviewed manually; when in doubt, trust the source code
> and the reproduction steps below over this document.

通过 `git blame` / 提交记录可追溯每条的修复提交。

**索引 / Index**

| ID | 主题 | 影响 / Affects | 严重级别 | 状态 | 最后更新 |
|---|---|---|---|---|---|
| #1 | `_safe_print` 打印兜底为死代码（3 处复制） | `sites/BBooru/B_scraper.py`、`sites/hypnohub/H_scraper.py`、`sites/rule34us/R_scraper.py` | 低 | ✅ 已修复 | 2026-09-22 |
| #2 | e-hentai 搜索分页：`&page=N` 为无效参数 | `sites/e-hentai/EH_scraper_v2.py`（搜索模式） | 高（静默失败） | ✅ 已修复 | 2026-09-27 |
| #3 | 统一入口的站点→目录映射错误（`ehentai` / `fa`） | `felinepaw_tool.py` — `build_command()` | 中 | ✅ 已修复 | 2026-09-27 |
| #4 | `--pick` 落盘文件名不得重新编号 | e-hentai 的 pick / 续传逻辑 | 高（静默丢图） | ✅ 实现时已规避 | 2026-09-27 |
| #5 | `safe_name` 未定义 → `NameError`（原 BUGS B1） | `sites/furaffinity/FA_scraper.py:542` | 高（必崩） | ✅ 已修复 | 2026-10-18 |
| #6 | yiff 自动模式 `requests` 未导入（原 BUGS B2） | `sites/yiff/yiff_auto_scraper.py:210` | 中（吞异常） | ✅ 已修复 | 2026-10-18 |
| #7 | `probe.py` 的 `urlparse` 未导入（原 BUGS B3） | `felinepaw_auto/probe.py:36` | 低 | ✅ 已修复 | 2026-10-18 |
| #8 | BBooru 用译文当模式身份（原 BUGS B4） | `sites/BBooru/gui/app.py:429` | 低（静默回退） | ✅ 已修复 | 2026-10-18 |
| #9 | e621 Pool 的编号顺序被 API 返回序打乱（001 是池子最后一张） | `sites/e621/pool_scraper.py`、`sites/e621/e621.py` | 高（顺序全错，静默） | ✅ 已修复 | 2026-11-15 |
| #10 | `pool_scraper` 续传时重复下载并整体错位 | `sites/e621/pool_scraper.py` | 高（重复占盘 + 顺序错） | ✅ 已修复 | 2026-11-15 |
| #11 | 顺序编号不补零 → `10.jpg` 排在 `2.jpg` 前面 | yiff / yiff_auto / e621 三件套 / e-hentai | 中（排序错，内容不丢） | ✅ 已修复 | 2026-11-15 |
| #12 | e621 脚本伪装浏览器 UA，匿名请求被 403 | `sites/e621/*.py`（5 个） | 高（无 key 时整个站不可用） | ✅ 已修复 | 2026-11-15 |

**速览 / Quick scan** —— 每条一句话，细节点进对应小节：

- **#1** `_safe_print` 是死代码（已删）—— `str.encode(enc, errors="replace")` 永远不会抛异常，它那个
  `except` 分支根本走不到；实测加不加输出都一样。真正防崩的是它上面几行 `reconfigure(errors="replace")`。
- **#2** e-hentai 搜索翻页是**游标式**，`&page=N` 被静默忽略（`page=0/5/50` 返回同一批 25 个画廊）；
  真正的游标是 `&next=<gid>`。
- **#3** 统一入口的「站点 → 目录」映射曾写错（`ehentai` → `sites/ehentai/`），直接跑会
  `No such file or directory`。
- **#4** `--pick` 落盘必须保留**原名单序号**，重新编号会让下一次 `--pick` 撞名并被续传判定静默跳过。
- **#5–#8** 三处缺失的 `import`（只有真执行才炸，`py_compile` 查不出来）与一处把**界面译文**
  当模式身份的比较 —— 切英文界面后会静默回退到默认模式。


---

## #1 `_safe_print` 打印兜底为死代码（3 处复制粘贴）

| 字段 | 内容 |
|---|---|
| **状态** | ✅ 已修复（2026-09-22）—— 三处代码均已删除 |
| **严重级别** | 低 —— 上层 `reconfigure` 已兜底，不导致崩溃 |
| **影响范围** | `sites/BBooru/B_scraper.py`、`sites/hypnohub/H_scraper.py`、`sites/rule34us/R_scraper.py` |
| **问题性质** | 无效代码 —— 提供虚假的防护保证 |

**Summary (EN)** — The `_safe_print` wrapper never fired: `str.encode(enc, errors="replace")`
cannot raise, so its `except (UnicodeEncodeError, LookupError)` branch was unreachable and the
wrapper only forwarded its arguments to `print`. The `reconfigure(errors="replace")` lines above it
are what actually prevent the GBK console crash. Removed from all three copies.

### 定位（修复前）

| 站点 | 文件 | 行号 |
|---|---|---|
| BBooru | `sites/BBooru/B_scraper.py` | 62–75 |
| HypnoHub | `sites/hypnohub/H_scraper.py` | 43–56 |
| Rule34.us | `sites/rule34us/R_scraper.py` | 43–55 |

三份代码逐字节相同：

```python
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    except Exception:
        pass
# 更通用的兜底：把所有 print 输出转成 GBK 可显示的字符   ← 该注释描述不实
import builtins as _builtins
_orig_print = _builtins.print
def _safe_print(*args, **kwargs):
    new_args = []
    for a in args:
        if isinstance(a, str):
            try:
                a.encode(sys.stdout.encoding or 'utf-8', errors='replace')   # ← 问题所在
            except (UnicodeEncodeError, LookupError):                        # ← 分支不可达
                a = a.encode('gbk', errors='replace').decode('gbk')
        new_args.append(a)
    _orig_print(*new_args, **kwargs)
_builtins.print = _safe_print
```

### 根因

`str.encode(enc, errors="replace")` 的语义是「无法编码的字符替换为 `?`，不抛异常」。因此其外层
`except (UnicodeEncodeError, LookupError)` 分支**不可达**，`_safe_print` 的实际行为退化为
「原样转发给 `print`」，对防止 GBK 编码崩溃的贡献为 **0**。

真正生效的是其上方第 28–33 行的：

```python
sys.stdout.reconfigure(errors="replace")
sys.stderr.reconfigure(errors="replace")
```

### 实测证据

环境：`PYTHONIOENCODING=gbk`（模拟 Windows `cmd` 真实控制台）

| 配置 | 输出含 emoji 时的行为 |
|---|---|
| 不做任何处理 | `UnicodeEncodeError` 崩溃（问题真实存在） |
| 仅 `reconfigure(errors="replace")` | emoji → `?`，正常输出 |
| `reconfigure` **+** `_safe_print` | emoji → `?`，**与上一行逐字节相同** |

结论：`_safe_print` 贡献为 0。第一行证明问题真实存在，第三行证明该补丁无附加收益。

### 附带缺陷（同一段代码）

该段读取 `sys.stdout.encoding` 时未做保护。当 `sys.stdout` 为 `None` 或不具备 `encoding` 属性时
（例如 PyInstaller `--noconsole` 打包产物、GUI 以无控制台方式启动子进程），将抛出
`AttributeError`；而该处 `except` 仅捕获 `UnicodeEncodeError` / `LookupError`，**无法捕获**，
导致程序在第一行输出之前即崩溃。

### 修复方案

采用方案 A —— 直接删除。理由：`reconfigure(errors="replace")` 已完整覆盖需求，保留无效代码
只会增加维护成本与误读风险。

| 文件 | 操作 |
|---|---|
| `sites/BBooru/B_scraper.py` | 删除 62–75 行 |
| `sites/hypnohub/H_scraper.py` | 删除 43–56 行 |
| `sites/rule34us/R_scraper.py` | 删除 43–55 行 |

备选方案 B（保留并修正：为 `encode` 去掉 `errors` 参数、`encoding` 改用
`getattr(sys.stdout, "encoding", None) or "utf-8"`）未采用 —— 收益不抵维护成本。

### 验证

- 三处文件 `py_compile` 通过
- 全仓库检索 `_safe_print` / `_builtins` 残留为 **0**

### 参考实现

`sites/wilddream/W_scraper.py` 第 14–17 行仅保留 `reconfigure`、不含 `_safe_print`，注释准确、
行为正确，为同类代码的规范写法：

```python
# Windows GBK 控制台可能编不了个别字符（emoji 等）→ 打印时替换为 '?'，避免 UnicodeEncodeError 崩溃
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
```

### 遗留事项

该段代码由复制粘贴产生于三处。若后续需统一维护，建议提取至 `common.py`；属重构范畴，暂不实施。

---

## #2 e-hentai 搜索分页：`&page=N` 为无效参数

| 字段 | 内容 |
|---|---|
| **状态** | ✅ 已修复（2026-09-27）—— `EH_scraper_v2.py` 改用游标翻页 |
| **严重级别** | **高** —— 静默失败，无异常、无空响应 |
| **影响范围** | 所有依赖 `&page=N` 翻页的 e-hentai 搜索代码 |
| **问题性质** | 我方接口用法错误（站点侧接口未变更） |

**Summary (EN)** — `&page=0`, `&page=5` and `&page=50` return a byte-identical set of 25 galleries;
the parameter is silently ignored, so a naive `for page in range(n)` loop re-fetches page 1 without
raising anything. Pagination is cursor-based: read `next=<gid>` (the last gallery id on the current
page) from `<a id="unext">`, or from the JS variable `var nexturl="..."`.

### 现象

按 `page` 参数循环翻页时，每次迭代返回**相同的 25 个画廊**。无异常、无空响应，仅重复第一页内容，
容易误判为「站点只提供第一页」。

### 实测证据（2026-09-27）

```
page=0  -> 200  rows=25  first=4215544  last=4215292
page=1  -> 200  rows=25  first=4215544  last=4215292
page=2  -> 200  rows=25  first=4215544  last=4215292
```

`page=0` 与 `page=50` 返回的 gid 序列逐字节相同：该参数被静默忽略。

### 根因与正确做法

站点采用**游标分页**，游标位于页面底部：

```html
<a id="unext" href="https://e-hentai.org/?f_search=language:chinese%24&amp;next=4215292">Next &gt;</a>
```

`next=<gid>` 中的 gid 为**当前页最后一个画廊的 id**。正确流程：

1. 请求 `https://e-hentai.org/?f_search=<urlencoded>`
2. 从 HTML 中提取 `//a[@id="unext"]/@href`（等价的 JS 变量 `var nexturl="..."` 亦可用，两者一致）
3. 以该 URL 请求下一页；页面中不存在 `#unext` 即为末页

实测连续三页零重叠：

```
page 1  rows=25  first=4215544  last=4215292  -> next=4215292
page 2  rows=25  first=4215291  last=4214885  -> next=4214885
page 3  rows=25  first=4214884  last=4214761  -> next=4214761
unique total: 75
```

### 接口事实备忘

| 项目 | 值 / 规则 |
|---|---|
| 搜索入口 | `GET /?f_search=<urlencoded>`；空格用 `+`、冒号用 `%3A`、`$` 用 `%24` |
| 每页条数 | **25**（画廊内页为 20，两者不同，勿混） |
| 结果总数 | `<div class="searchtext"><p>Found about 253,679 results.</p></div>`，正则 `Found about ([\d,]+) results` |
| 列表容器 | `<table class="itg">` 的每个 `<tr>`；分类行与表头行不含 `div.glink`，用 `a[div[@class="glink"]]` 过滤 |
| 单条字段 | 标题 `div.glink`、标签 `div.gt@title`、分类 `td.glcat div.cn`、页数 `td.gl4c` 的 `N pages` |
| 元数据 | 搜索页自带完整元数据，无需另行调用 `gdata` API |

### 防回归

保留一条**反向基线断言**：`&page=5` 必须继续与 `&page=0` 返回相同内容。

该断言刻意与常规测试相反 —— 它断言某参数**持续失效**。若站点恢复了 `page=` 参数，断言将失败并
给出提示，从而避免旧代码被无声地恢复使用。不这样钉住，此类问题无法被检出。

---

## #3 统一入口的站点→目录映射错误

| 字段 | 内容 |
|---|---|
| **状态** | ✅ 已修复（2026-09-27） |
| **严重级别** | 中 —— 直接报错，无静默错误，但功能等于不存在 |
| **影响范围** | `felinepaw_tool.py` 的 `build_command()` |
| **问题性质** | 实现缺陷 |

**Summary (EN)** — The unified CLI resolved `ehentai` to `sites/ehentai/` and `fa` to `sites/fa/`,
but the real folders are `sites/e-hentai/` and `sites/furaffinity/`. Any
`felinepaw_tool.py ehentai ...` invocation therefore died with
`[Errno 2] No such file or directory`. Running the site scripts directly was unaffected, which is
why it went unnoticed.

### 现象

```
>>> ...\python.exe ...\felinepaw\sites\ehentai\EH_scraper_v2.py --tags ... --dry-run
can't open file '...\sites\ehentai\EH_scraper_v2.py': [Errno 2] No such file or directory
```

### 根因

```python
site_dir = {"bbooru": "BBooru", "hypnohub": "hypnohub", "rule34us": "rule34us"}.get(site, site)
```

映射表仅列出 3 个站点，其余**直接以站点名作为目录名**。实际目录对照如下：

| 站点名（CLI） | 实际目录 | 结果 |
|---|---|---|
| `ehentai` | `sites/e-hentai/` | ❌ 被拼成 `sites/ehentai/` |
| `fa` | `sites/furaffinity/` | ❌ 被拼成 `sites/fa/` |
| `e621` / `e926` | `sites/e621/` | ✅ 有独立 `if` 分支兜底 |
| `yiff` / `wilddream` / `bbooru` / `hypnohub` / `rule34us` | 同名 | ✅ |

**未被及时发现的原因**：README 与日常习惯均为**直接运行站点脚本**
（`python sites/e-hentai/EH_scraper_v2.py ...`），绕过了统一入口。`felinepaw_tool.py ehentai`
这条路径从加上之日起就未成功过。

### 修复方案

```python
site_dir = {"bbooru": "BBooru", "hypnohub": "hypnohub", "rule34us": "rule34us",
            "ehentai": "e-hentai", "fa": "furaffinity"}.get(site, site)
```

### 验证

两条路径均端到端验证通过（直接运行站点脚本 / 经统一入口调用）。

### 经验教训

**「站点名」与「目录名」是两个独立概念，不应以 `.get(site, site)` 这类默认值偷懒。**
新增站点时，除注册脚本名之外，必须同时检查目录是否同名 —— 此项应纳入 `felinepaw_tool.py`
的新增站点检查清单。

---

## #4 `--pick` 落盘文件名不得重新编号

| 字段 | 内容 |
|---|---|
| **状态** | ✅ 实现时已规避（2026-09-27） |
| **严重级别** | **高** —— 静默丢图 |
| **影响范围** | e-hentai 的 `--pick` 选择与断点续传逻辑 |
| **问题性质** | 设计陷阱（记录在此，因其极易在后续站点重犯） |

**Summary (EN)** — After `--pick 2-4`, output files must keep their **original list index**
(`2.* 3.* 4.*`), not be renumbered from 1. Renumbering makes a later `--pick 5-6` write `1.* 2.*`,
which collides with existing files and is silently skipped by the resume check. The "already
exists?" glob must also exclude `.part`.

### 问题

`--pick 2-4` 选出名单中的第 2、3、4 项。若下载时以 `enumerate(picked, 1)` 重新编号，落盘文件名
将变为 `1.* / 2.* / 3.*`，而非 `2.* / 3.* / 4.*`。

**后果为静默丢图**：下次执行 `--pick 5-6` 时同样写出 `1.* / 2.*`，与已有文件**撞名**，被断点续传
（「存在即跳过」）判定为已完成，用户误以为已下载。

### 正确做法

文件名一律采用**该项在完整名单中的原始序号**：

```python
picked = [(i, items[i - 1]) for i in idx]   # i 为名单序号，而非新生成的 1..N
jobs = [(i, u) for i, (u, _f) in picked]
```

### 实测对照

```
--pick 2-4  ->  2.webp  3.webp  4.webp
--pick 5-6  ->  5.webp  6.webp
最终目录: 2/3/4/5/6 共 5 个（无覆盖、无跳过）
```

### 附带事项

断点续传判定「已存在」时须**排除 `.part`**：

```python
existing = [p for p in out.glob(f"{idx}.*") if not p.name.endswith(".part")]
```

否则上一轮中断留下的 `1.jpg.part` 会被 `glob("1.*")` 命中，导致 1 号图被永久跳过。


---

## #5 `safe_name` 未定义 → `NameError`（高，必崩）

| 字段 | 内容 |
|---|---|
| **状态** | ✅ 已修复（2026-10-18）—— 改用 `sanitize_filename` |
| **严重级别** | 高 —— 走到即崩，不是偶发 |
| **影响范围** | `sites/furaffinity/FA_scraper.py:542` |
| **首次出现** | `0e9af61 init`（2026-08-31）起一直存在 |

**Summary (EN)** — `FA_scraper.py` called `safe_name(...)` but only aliased `sanitize_filename`.
The name never existed in the module or in `common.py`; importing the module succeeded, so
`py_compile` and every syntax check stayed green and the failure surfaced only at that line.

### 为什么长期没被发现

`felinepaw_tool.py:203` 里是 `_add("-o", args.output or str(common.local_out_root()))` ——
统一入口永远补一个 `-o`，所以 `args.output` 恒非空，`else` 分支是死代码。只有绕过统一入口、
直接敲站点脚本且不带 `-o` 才会踩到。

### 修复

```diff
-    out = Path(args.output) if args.output else Path(safe_name(series_key or title))
+    out = Path(args.output) if args.output else Path(sanitize_filename(series_key or title))
```

两处语义等价：`sanitize_filename` 本来就是做「文件名安全化」的那一个，且它已在第 68 行被
alias 进来。修复后 `import FA_scraper` 的命名空间里 `sanitize_filename` 存在且
`is common.sanitize_filename` 为 `True`。

### 验证

```bash
python sites/furaffinity/FA_scraper.py "https://www.furaffinity.net/view/xxxxx/" --dry-run
python sites/furaffinity/FA_scraper.py "https://www.furaffinity.net/view/xxxxx/"   # 不带 -o
```

---

## #6 yiff 自动模式下 `requests` 未导入（中）

| 字段 | 内容 |
|---|---|
| **状态** | ✅ 已修复（2026-10-18）—— 文件顶部补 `import requests` |
| **严重级别** | 中 —— 只在 HEAD 探测抛异常时命中；命中即把「跳过这张」变成「整个循环中断」 |
| **影响范围** | `sites/yiff/yiff_auto_scraper.py:210` |

**Summary (EN)** — The `except requests.RequestException:` handler referenced a module that was
never imported. The class expression is evaluated only when an exception arrives, so the defect
stayed invisible until a real network hiccup turned it into
`NameError: name 'requests' is not defined`, aborting the rest of the extension-probing loop.

### 修复

在标准库 import 块之后、`_HERE` 环境准备之前补入：

```python
import requests
```

**没有**写成 `ys.requests` —— 那是在依赖「邻居碰巧也 import 了 requests」，
`yiff_scraper.py` 哪天去掉这个 import 就会二次踩坑。

### 验证

`import yiff_auto_scraper` 后 `hasattr(mod, "requests")` 为 `True`（修复前为 `False`）。

---

## #7 `probe.py` 的 `urlparse` 未导入（低）

| 字段 | 内容 |
|---|---|
| **状态** | ✅ 已修复（2026-10-18）—— 补 `from urllib.parse import urlparse` |
| **严重级别** | 低 —— 只有带 `--try-api` 才走 |
| **影响范围** | `felinepaw_auto/probe.py:36` |

**Summary (EN)** — `probe_api()` used `urlparse` twice in one expression, but the module never
imported it; `--try-api` was the only path that reached it, so the normal probe flow hid it.

### 修复

```python
from urllib.parse import urlparse      # 放在标准库 import 块内
```

同样**没有**用 `from core import urlparse` 蹭邻居 —— 那是隐式依赖。

### 验证

`import probe` 后 `hasattr(mod, "urlparse")` 为 `True`（修复前为 `False`）。

---

## #8 BBooru 用「译文」当模式身份（低，静默回退）

| 字段 | 内容 |
|---|---|
| **状态** | ✅ 已修复（2026-10-18）—— 改为按下拉框**下标**取模式 |
| **严重级别** | 低 —— 译文撞车时静默回退成 `tags`，不报错 |
| **影响范围** | `sites/BBooru/gui/app.py`（`_init_vars` / `_build_params` / `_mode_key_from_display` / `_on_mode_selected`） |

**Summary (EN)** — The mode picker reverse-mapped the Combobox *display text* back to an internal
key by comparing `i18n.t("bb_mode_" + k) == disp`. Any collision (two modes translating identically,
or a locale added later) silently fell back to `"tags"`. `pixivpaw`'s picker and `felinepaw_gui.py`
already used the index; BBooru was the odd one out.

### 修复

状态改为持有下标 `self._mode_idx`，下拉框用 `current()` 读写，重建界面时按 `current(idx)` 回填：

```python
self._mode_idx = MODE_KEYS.index(self._mode_key)   # _init_vars

self.mode_cb = cb = ttk.Combobox(..., values=[i18n.t("bb_mode_" + k) for k in MODE_KEYS])
cb.current(self._mode_idx)                          # _build_params：按 index 回填

def _mode_key_from_display(self):                   # 不再读 mode_var 的文案
    idx = self.mode_cb.current()
    return MODE_KEYS[idx] if 0 <= idx < len(MODE_KEYS) else self._mode_key

def _on_mode_selected(self, event=None):
    self._mode_key = self._mode_key_from_display()
    self._mode_idx = MODE_KEYS.index(self._mode_key)
    self._on_mode()
```

### 实测（2026-10-18，py39 / 真实 Tk，窗口 withdraw）

```
初始 _mode_key='tags' idx=0
选第 1 项后 _mode_key='pool'   idx=1
选第 2 项后 _mode_key='artist' idx=2
当前语言 zh，译文 ['标签 (Tags)', '合集 (Pool)', '艺术家 (Artist)']
重建后 _mode_key='artist' idx=2 current=2
重建后下拉框文本='艺术家 (Artist)'
```

切语言重建界面后模式身份不丢，且不再依赖译文比较。

---

## #9 e621 Pool 的编号顺序被 API 返回序打乱

**严重级别**：高（顺序全错，而且**不报错**）

**现象**

`pool_scraper.py` 下载一个 Pool，`001.jpg` 不是池子里的第一张。池子越"人为排过序"，
错得越明显。

**根因**

`posts.json?tags=id:A,B,C` 的**返回顺序跟请求里写的顺序无关** —— e621 是按 **id 降序**返回的。
而 `downloadable` 是按 API 返回顺序 `append` 的，从没按 `pool.post_ids` 重排：

```python
for post in posts:                      # posts 是 API 顺序 = id 降序
    downloadable.append((pid, url, ext))
```

于是「顺序编号」实际排的是 id 倒序，`001` 落地成池子的最后一张。

`sites/e621/e621.py` 的 docstring 写着「反转编号版」，`reversed(downloadable)` 之后拿到的是
id **升序** —— 两个方向都不是池序。当初那个「反转」选项，某种意义上是在给这个 bug 打补丁。

**实测证据（2026-11-15，走 Clash 7897）**

抽样 199 个 5~60 帖的 Pool，**44 个（22%）的 `post_ids` 不是升序**，也就是作者真的调整过顺序：

```
pool 60309  post_ids : [6811627, 6773744, 6794599, 6814220, 6819281]
            API 返回 : [6819281, 6814220, 6811627, 6794599, 6773744]   ← 严格降序
```

**修复**

```python
order = {pid: i for i, pid in enumerate(post_ids)}
downloadable.sort(key=lambda t: order.get(t[0], len(post_ids)))
```

`failed_ids`（拿不到 URL 的帖子）不在 `downloadable` 里，排完序缺位是正常的。

**验证**

真实下载 pool 60309（5 张），`001.png` 与池子第一张（pid=6811627）的 md5 完全一致：

```
期望 md5 : 1fc628d5bf17efec2a3127ebdf8a3223
001.png  : 1fc628d5bf17efec2a3127ebdf8a3223
```

编号与 `post_ids` 逐位对应：001=6811627 / 002=6773744 / 003=6794599 / 004=6814220 / 005=6819281。

---

## #10 `pool_scraper` 续传时重复下载并整体错位

**严重级别**：高（重复占盘 + 顺序错，且不报错）

**现象**

第一次跑到第 5 张中断，第二次重跑，池子的**第一张**被存成 `006.jpg`，后面依次 +5。

**根因**

续传用的是「接着最大序号往后编」，但循环里**没有跳过已下载任务的守卫**：

```python
start_index = existing_max + 1
for idx in range(len(downloadable)):
    target_index = start_index + idx        # idx=0 -> 6，而它其实是池子第 1 张
```

`e6_scraper.py` / `yiff_auto_scraper.py` 有 `if idx < existing_max: continue` 那道守卫，所以没炸；
但它们写的 `start_index + (idx - existing_max)` 在代数上**恒等于 `idx + 1`** —— `start_index` 和
`existing_max` 是纯粹的摆设，日志里"从 6 开始续传"是假的。

**修复**

编号改成「池内位置」，判重按**数值集合**：

```python
got = common.existing_seq(output_dir)      # {1, 2, 3, ...}
for idx in range(len(downloadable)):
    target_index = idx + 1                 # 池子第几张，幂等
    if target_index in got: skip
```

顺带解决另一个场景：池子被作者插了新图，按位置编号不会整体错位（按「接着编」则会）。

**验证**

```
删掉 004/005 后重跑  -> skipped 3, downloaded 2（001-003 未重下）
把 001.png 改名 1.png 后重跑 -> skipped 5, downloaded 0（老的不补零文件也认得出）
```

---

## #11 顺序编号不补零

**严重级别**：中（内容不丢，只是排序错）

**现象**

`10.jpg` 排在 `2.jpg` 前面。Windows 资源管理器用自然排序看不出问题，但 Python `sorted()`、
`ls`、部分播放器和同步工具会错。

**根因**

所有顺序编号的站都直接写 `f"{idx}.{ext}"`。

**修复**

`common.py` 新增三个函数，13 个脚本统一调用：

| 函数 | 作用 |
|---|---|
| `seq_width(max_index, out_dir=None)` | 零填充宽度。**按本批最大序号算**（不是总数）—— `--pick 995-1000` 只有 6 张却要编到 1000；同时沿用目录里已有序号文件的宽度，防止续传跨 10 的幂时 `001` 和 `1000` 并存 |
| `existing_seq(out_dir)` | 已有序号**集合**。按数值比，`1.jpg`（旧）和 `001.jpg`（新）都认得出 |
| `find_existing_max(out_dir, max_width=5)` | 加了位数上限，只认 ≤5 位的纯数字文件名 |

**注意**：`find_existing_max` 的位数上限不是可选项。e621 的 post id 是 6~7 位，混在同一目录里时
`1234567.png` 会被当成「已经下了 123 万张」，续传直接把整批任务跳过。

**验证**

| 场景 | 结果 |
|---|---|
| yiff 下载 2 张 | `001.jpg` / `002.jpg` |
| e621 pool 5 张 | `001.png` … `005.png` |
| EH 序号 1 / 2 / 1000 | `0001.bin` / `0002.bin` / `1000.bin`（宽度取 4） |
| EH 目录里已有不补零的 `3.jpg` | 认出、跳过、不覆盖 |
| 目录有 `1.jpg` `002.jpg` `003.jpg.part` `1234567.jpg` | `existing_seq` = {1, 2}，`.part` 与 post id 都不算 |

**遗留**：跨过 10 的幂时那几张（`1000.jpg` 必然是 4 位，而前面的 `001` 是 3 位）无法共存于同一宽度。
彻底解决要重命名全部旧文件，风险大于收益，不做。

---

## #12 e621 脚本伪装浏览器 UA，匿名请求被 403

**严重级别**：高（没设 `E621_USER` / `E621_KEY` 时整个站不可用）

**现象**

所有 e621 请求返回 403，或者直接 `SSLError(SSLZeroReturnError)`
（Cloudflare 连 TLS 都不给握完）。

**根因**

五个脚本的 `User-Agent` 都是 Chrome 125 的浏览器串。e621 的 API 明确要求**描述性的 UA**
（说明是什么程序、找谁），浏览器 UA 会被当成爬虫直接拦。

**实测（2026-11-15，同一节点同一个 URL）**

```
UA = Mozilla/5.0 ... Chrome/125.0.0.0 Safari/537.36   -> 403（238 bytes）
UA = felinepaw/1.0 (by SparkSlugcat)                 -> 200（395 bytes）
```

**修复**

5 个文件统一改成：

```python
"User-Agent": "felinepaw/1.0 (by SparkSlugcat on e621; +https://github.com/SparkSlugcat/felinepaw)",
```

**附带发现**：e621 这几个脚本**没有 `--proxy` 参数**（B/H/R/W/FA/EH 都有），session 在模块
import 时就建好了。本机靠系统代理或环境变量能跑，但换节点、或环境里有别的代理变量时没法显式指定。

**未修**：`--proxy` 参数没加，属于跨 5 个文件的小重构，等下次动这几个脚本时一起做。
