# Known issues / 已知问题

> 本文件记录 **已实测确认** 的问题，供后续维护参考。
> 只写复现过的，不写猜测；每条都注明影响面和建议修法。
> 建立：2026-09-21

---

## #1 `_safe_print` 是死代码（3 个站点复制粘贴）

**状态**：✅ **已修复（2026-09-22）** —— 按下方「建议修法 A」把三处死代码全部删除；
三个文件 `py_compile` 通过，`_safe_print` / `_builtins` 残留为 0。原实测记录保留在下方备查。
**影响面**（修复前）：`sites/BBooru/B_scraper.py`、`sites/hypnohub/H_scraper.py`、`sites/rule34us/R_scraper.py`
**当前危害**：**低**——因为有它上面那 4 行 `reconfigure` 在兜底，程序不会崩。
真正的问题是**这段补丁给了虚假的安全感**：它看起来在防 GBK 崩溃，实际贡献为 0。

### 位置

| 站点 | 文件 | 行号 |
|---|---|---|
| BBooru | `sites/BBooru/B_scraper.py` | 62–75 |
| HypnoHub | `sites/hypnohub/H_scraper.py` | 43–56 |
| Rule34.us | `sites/rule34us/R_scraper.py` | 43–55 |

三份代码**逐字节相同**：

```python
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    except Exception:
        pass
# 更通用的兜底：把所有 print 输出转成 GBK 可显示的字符   ← 这句注释是错的
import builtins as _builtins
_orig_print = _builtins.print
def _safe_print(*args, **kwargs):
    new_args = []
    for a in args:
        if isinstance(a, str):
            try:
                a.encode(sys.stdout.encoding or 'utf-8', errors='replace')   # ← 问题在这
            except (UnicodeEncodeError, LookupError):                        # ← 永远进不来
                a = a.encode('gbk', errors='replace').decode('gbk')
        new_args.append(a)
    _orig_print(*new_args, **kwargs)
_builtins.print = _safe_print
```

### 为什么是死代码

`str.encode(enc, errors='replace')` 的语义是「**编不出来的字符就替换成 `?`，别抛异常**」。
既然它保证不抛，那么第 71 行的 `except (UnicodeEncodeError, LookupError)` **永远不可能命中**——
兜底分支是死的，`_safe_print` 干的事只有「原样转发给 `print`」。

### 实测证据（`PYTHONIOENCODING=gbk` 模拟 cmd 真实环境）

| 场景 | 结果 |
|---|---|
| 什么都不做 | **UnicodeEncodeError 崩溃** ← 问题真实存在 |
| 只加 `reconfigure(errors="replace")` | emoji → `?`，**正常工作** |
| `reconfigure` **+** `_safe_print` | emoji → `?`，**与上一行逐字节相同** |

→ 真正救场的是 `reconfigure`；`_safe_print` 贡献 **0**。

### 附带隐患（同一段代码）

第 70 行读了 `sys.stdout.encoding`。当 `sys.stdout` 是 **None** 或**没有 `encoding` 属性**时
（`PyInstaller --noconsole` 打包、GUI 以无控制台方式调起子进程）会抛 `AttributeError`，
而 `except` 只接 `UnicodeEncodeError / LookupError`，**接不住** → 直接崩在第一行输出之前。

### 建议修法（二选一，推荐 A）

**A. 直接删掉**（最省事，且已被证明足够）：
- BBooru 删 62–75 行、hypnohub 删 43–56 行、rule34us 删 43–55 行
- 理由：`reconfigure(errors="replace")` 已经覆盖全部需求

**B. 保留但修对**：把 `a.encode(sys.stdout.encoding or 'utf-8', errors='replace')`
改成不带 `errors` 的 `a.encode(enc)`，让异常真能抛出；同时把取 `encoding` 改成
`getattr(sys.stdout, "encoding", None) or "utf-8"`。

> 另注：三个站点的这段是复制粘贴关系，**要改就得三处都改**。
> 若想一劳永逸，可提取到 `common.py` 里做一次 —— 但这属于重构，按需再说。

### 反向对照（活体证明）

`sites/wilddream/W_scraper.py` 第 14–17 行**只有 `reconfigure`、没有 `_safe_print`**：

```python
# Windows GBK 控制台可能编不了个别字符（emoji 等）→ 打印时替换为 '?'，避免 UnicodeEncodeError 崩溃
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
```

它的注释描述准确、行为正确。**这就是其他三个站点应该长的样子。**

---

## #2 e-hentai 搜索分页：`&page=N` 是**死参数**（静默重复第一页）

**状态**：✅ **已修复（2026-09-27）** —— v3 的 `EH_scraper_v2.py` 改用游标翻页；
接口本身没变，是**我们的用法**错了。
**影响面**（修复前）：任何按 `&page=N` 翻页的 e-hentai 搜索代码
**危害**：**高（且隐蔽）** —— 它**不报错、不空返回**，只是把第一页反复给你。

### 症状

写 `for n in range(pages): url = f"...&f_search=X&page={n}"` 这种循环，
每一轮拿到的都是**同样 25 个画廊**。你以为是站点"只给第一页"，实际上参数被忽略了。

### 实测证据（2026-09-27）

```
page=0  -> 200  rows=25  first=4215544  last=4215292
page=1  -> 200  rows=25  first=4215544  last=4215292   ← 完全相同
page=2  -> 200  rows=25  first=4215544  last=4215292   ← 完全相同
与 page=0 重叠 24 个
```

`page=0` 与 `page=50` 的 gid 序列**逐字节相同**。参数被吞掉，没有任何提示。

### 正确做法（游标翻页）

分页游标藏在页面底部：

```html
<a id="unext" href="https://e-hentai.org/?f_search=language:chinese%24&amp;next=4215292">Next &gt;</a>
```

`next=<gid>` 里的 gid 是**当前页最后一个画廊的 id**。所以流程是：

1. 请求 `https://e-hentai.org/?f_search=<urlencoded>`
2. 从 HTML 里取 `//a[@id="unext"]/@href`（也可用 JS 变量 `var nexturl="..."`，两者一致）
3. 用这个 URL 请求下一页；没有 `#unext` 就是最后一页

实测三页零重叠：

```
第1页 rows=25  first=4215544 last=4215292 -> next=4215292
第2页 rows=25  first=4215291 last=4214885 -> next=4214885
第3页 rows=25  first=4214884 last=4214761 -> next=4214761
累计 unique: 75
```

### 顺带记下的三个接口事实

| 事实 | 值 | 备注 |
|---|---|---|
| 搜索入口 | `GET /?f_search=<urlencoded>` | 空格用 `+`，`:` 用 `%3A`，`$` 用 `%24` |
| 每页条数 | **25** | 与画廊内页的 20 张不同，别混 |
| 结果总数 | `<div class="searchtext"><p>Found about 253,679 results.</p></div>` | 用正则 `Found about ([\d,]+) results` 取 |
| 列表容器 | `<table class="itg">` 的每个 `<tr>` | 分类行/表头行没有 `div.glink`，用 `a[div[@class="glink"]]` 过滤 |
| 单条数据 | 标题 `div.glink`、标签 `div.gt@title`、分类 `td.glcat div.cn`、页数 `td.gl4c` 里的 `N pages` | 搜索页**自带完整元数据**，不必再打 gdata API |

### 防回归

新代码里保留一条**反向基线断言**：

* `&page=5` 必须继续与 `&page=0` 返回**相同**内容。

若哪天两者不同了，说明站点把 `page=` 改回来了 —— 这条断言会失败并提醒你，
而不是让你继续用旧的翻页写法静默重复第一页。

（写测试时注意：这是一种「断言某个参数**继续失效**」的反向基线，
和常见的「断言功能正常」相反，但不这样钉住就查不出来。）

---

## #3 统一入口的站点→目录映射错了两个（`ehentai` / `fa`）

**状态**：✅ **已修复（2026-09-27）**
**影响面**（修复前）：`felinepaw_tool.py` 的 `build_command()`
**危害**：**中**（直接报错，不会静默出错，但功能等于不存在）

### 症状

```
>>> ...\python.exe ...\felinepaw\sites\ehentai\EH_scraper_v2.py --tags ... --dry-run
can't open file '...\sites\ehentai\EH_scraper_v2.py': [Errno 2] No such file or directory
```

### 原因

```python
site_dir = {"bbooru": "BBooru", "hypnohub": "hypnohub", "rule34us": "rule34us"}.get(site, site)
```

映射表只列了 3 个站点，其余**直接拿站点名当目录名**。但实际目录是：

| 站点名（CLI） | 实际目录 | 结果 |
|---|---|---|
| `ehentai` | `sites/e-hentai/` | ❌ 拼成 `sites/ehentai/` |
| `fa` | `sites/furaffinity/` | ❌ 拼成 `sites/fa/` |
| `e621` / `e926` | `sites/e621/` | ✅ 有专门的 if 分支兜底 |
| `yiff` / `wilddream` / `bbooru` / `hypnohub` / `rule34us` | 同名 | ✅ |

**为什么一直没被发现**：README 和用户习惯都是**直接跑站点脚本**
（`python sites/e-hentai/EH_scraper_v2.py ...`），绕过了统一入口。
`felinepaw_tool.py ehentai` 这条路从加上起就没成功过。

### 修法

```python
site_dir = {"bbooru": "BBooru", "hypnohub": "hypnohub", "rule34us": "rule34us",
            "ehentai": "e-hentai", "fa": "furaffinity"}.get(site, site)
```

### 教训

**「站点名」和「目录名」是两个东西，不要用 `.get(site, site)` 这种默认值偷懒。**
每加一个新站点，除了注册脚本名，还要检查目录是否同名 —— 这条应该进
`felinepaw_tool.py` 新增站点的检查清单。

---

## #4 `--pick` 挑着下时，文件名不能重新编号

**状态**：✅ **已在实现时规避（2026-09-27）**（记录在此，因为它极易在后继站点重犯）

### 问题

`--pick 2-4` 挑出第 2、3、4 项。若下载时用 `enumerate(picked, 1)` 重新编号，
落盘的文件名会变成 `1.* / 2.* / 3.*` —— 而不是 `2.* / 3.* / 4.*`。

**后果是静默漏图**：下次再跑 `--pick 5-6`，它又会写出 `1.* / 2.*`，
与已有的 `1.* / 2.*` **撞名**，被断点续传（"存在就跳过"）判为已完成 —— 用户以为下过了。

### 正确做法

文件名一律用**该项在完整名单里的原始序号**：

```python
picked = [(i, items[i - 1]) for i in idx]   # i 是名单序号，不是新的 1..N
jobs = [(i, u) for i, (u, _f) in picked]
```

### 实测对照

```
--pick 2-4  ->  2.webp  3.webp  4.webp
--pick 5-6  ->  5.webp  6.webp
最终目录: 2/3/4/5/6 共 5 个（无覆盖、无跳过）
```

### 附带一条

断点续传判"已存在"时要**排除 `.part`**：

```python
existing = [p for p in out.glob(f"{idx}.*") if not p.name.endswith(".part")]
```

否则上轮下到一半的 `1.jpg.part` 会让 `glob("1.*")` 命中，把 1 号图永久跳过。
