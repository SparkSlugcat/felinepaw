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
