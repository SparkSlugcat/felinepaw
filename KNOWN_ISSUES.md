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

| ID | 主题 | 严重级别 | 状态 | 最后更新 |
|---|---|---|---|---|
| #1 | `_safe_print` 打印兜底为死代码（3 处复制） | 低 | ✅ 已修复 | 2026-09-22 |
| #2 | e-hentai 搜索分页：`&page=N` 为无效参数 | 高（静默失败） | ✅ 已修复 | 2026-09-27 |
| #3 | 统一入口的站点→目录映射错误（`ehentai` / `fa`） | 中 | ✅ 已修复 | 2026-09-27 |
| #4 | `--pick` 落盘文件名不得重新编号 | 高（静默丢图） | ✅ 实现时已规避 | 2026-09-27 |

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
