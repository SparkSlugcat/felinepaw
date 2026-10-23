# 🆘 Troubleshooting / 排错手册

> **Scope** — everything that can go wrong **before or during a run**: the launcher refusing to start,
> missing modules, proxy errors, rate limits, and how to file a useful bug report.
> The README keeps a four-row cheat sheet; every detail lives here.
>
> **文档范围** —— 本文件收录**装不上、跑不起来、跑到一半报错**的全部排查流程：启动器起不来、
> 依赖缺失、代理报错、限速、以及怎么报一个有用的 bug。README 只保留一张四行速查表，细节都在这里。

> **Tooling disclosure** — the measurements, reproductions and formatting in this document were produced
> with the assistance of the AI coding assistant **WorkBuddy**; every finding was reproduced on the
> author's machine and reviewed manually. When in doubt, trust the source code and the steps below.
>
> **工具声明** —— 本文件的实测数据、复现过程与排版由 AI 编程助手 **WorkBuddy** 协助完成，
> 所有结论均在作者本机复现并人工复核。如有疑义，请以源码与文中的步骤为准。

**Index / 索引**

| § | Topic / 主题 |
|---|---|
| 1 | Double-click does nothing / 双击没反应、窗口一闪就没 |
| 2 | `No module named ...` — missing dependency / 依赖没装 |
| 3 | Point the launcher at your Python / 用 `PYTHON_EXE` 指定解释器 |
| 4 | Can't find Python at all / 实在找不到 Python 在哪 |
| 5 | Proxy and network errors / 代理与网络报错 |
| 6 | Site blocks and rate limits / 站点拦截与限速 |
| 7 | What to include in a bug report / 报 bug 要带什么 |

---

## 1 Double-click does nothing / 双击没反应

If you double-clicked `启动.bat` and saw a wall of Chinese error text, the most common cause is a
misconfigured Python. **Read the last line of the traceback first** — nothing else matters as much.

> 双击 `启动.bat` 后看到一堆报错，最常见的原因就是 Python 环境没配好。**先看报错的最后一行**，
> 那一行的信息量比上面几十行加起来都大。

| Error sample / 报错样例 | Meaning / 含义 | Fix / 修法 |
|---|---|---|
| `'python' is not recognized` | System can't find `python.exe` | Go to §3, set `PYTHON_EXE` |
| `ModuleNotFoundError: No module named 'requests'` | Python found, but the dep is missing | Go to §2 |
| `DLL load failed while importing _tkinter` | Conda env lacks tkinter | `conda install -n YOUR_ENV tk` |
| `pythonw.exe not found` | Same as "python not found" | Same as above / 同第一条 |
| No error, but the window flashes and disappears | The silent launcher's self-check failed | Run `启动.bat` once from a cmd window — it pauses and leaves the error on screen |
| No error, but the GUI opens and closes instantly | Same self-check failure, silent path | Same fix / 同上 |

> 💡 The launcher self-check is `import felinepaw_gui`. If that import fails, the window closes before
> you can read anything. Running the `.bat` **from an already-open cmd** is what makes the error visible.
>
> 💡 启动器只自检 `import felinepaw_gui` 这一句。它失败时窗口来不及显示就关了，
> **所以一定要先在 cmd 里敲一次 `启动.bat`**，错误才会被 `pause` 留在屏幕上。

---

## 2 `No module named ...` — missing dependency / 依赖没装

A full traceback usually looks like this. **Only the last line matters.**

> 完整报错一般长这样，**只看最后一行**就够了。

```text
Traceback (most recent call last):
  File "D:\path\to\felinepaw\sites\e-hentai\EH_scraper_v2.py", line 52, in <module>
    from lxml import etree
ModuleNotFoundError: No module named 'lxml'
```

```bat
python -m pip install requests lxml          :: lxml is only used by the e-hentai site
python -m pip install DrissionPage           :: optional: FA cookies / yiff-auto browser variant
```

| Pitfall / 坑 | Symptom / 现象 | Fix / 怎么办 |
|---|---|---|
| `pip install` instead of `python -m pip install` | Same `No module named` after "installing" | With several Pythons, bare `pip` may hit a different one. **Always `python -m pip`** / 电脑有多个 Python 时必须用 `python -m pip` |
| Installed into the wrong interpreter / 装错解释器 | `python -c "import sys; print(sys.executable)"` prints a path outside the env in the traceback | Run `-m pip install` with that env's own interpreter |
| Downloads hang → `ReadTimeoutError` | pip spins, then times out | Use a mirror: `-i https://pypi.tuna.tsinghua.edu.cn/simple` |
| `ImportError: DLL load failed while importing etree` | lxml binary doesn't match your Python | `python -m pip install --force-reinstall lxml`, or `conda install lxml` |
| `'pip' is not recognized` | pip not on PATH | Use `python -m pip` |

Verify / 装完验证（must print `ok`）：

```bat
python -c "import requests, lxml; print('ok')"
```

> ⚠️ **Note the difference / 注意区分**：`启动.bat` only self-checks `import felinepaw_gui`, which needs
> just `requests` + `tkinter`. So **a missing `lxml` will not stop the window from opening** — it only blows
> up when you actually run the e-hentai site. If the GUI opens but the log shows
> `ModuleNotFoundError: No module named 'lxml'`, that's this case.
>
> 缺 `lxml` 时窗口照样能开，只在跑 e-hentai 站点时才报错 —— 日志框里出现上面那行就是这个情况。

---

## 3 Point the launcher at your Python / 用 `PYTHON_EXE` 指定解释器

If you already have a Python / conda env (named anything, not just `py39` — `myenv` / `ai` / `work` all
work), you don't need to rename it. Just point the launcher at its `python.exe` full path.

> 已经有 Python / conda 环境的话（环境名不叫 `py39` 也行），**不需要改名**，
> 把它的 `python.exe` 完整路径告诉启动器就行。

**Permanent (writes to registry, global) / 永久** — open any cmd and copy-paste (replace the path):

```bat
:: 1. Find your python.exe first / 先找 python.exe
where python
:: Output is like: C:\Users\YOUR_NAME\miniconda3\envs\myenv\python.exe

:: 2. Adapt the line above and paste this into cmd
setx PYTHON_EXE "C:\Users\YOUR_NAME\miniconda3\envs\myenv\python.exe"
```

`setx` writes to the registry; **you must reopen any cmd for it to take effect**. Then double-click
`启动.bat` again.

> `setx` 写的是注册表，**执行后必须重新开一个 cmd 才生效**。然后重新双击 `启动.bat`。

**Temporary (current cmd only) / 临时（仅当前窗口）**：

```bat
set PYTHON_EXE=C:\Users\YOUR_NAME\miniconda3\envs\myenv\python.exe
启动.bat
```

---

## 4 Can't find Python at all / 实在找不到 Python 在哪

Open any cmd, type / 打开任意 cmd，敲：

```bat
where python
```

The **first line** of the output is the full path to `python.exe`. Set it as `PYTHON_EXE` and you're done.

> 输出的**第一行**就是 `python.exe` 的完整路径，把它配到 `PYTHON_EXE` 即可。

If `where python` returns nothing, you don't have Python installed — install one:

- Official: <https://www.python.org/downloads/> (✓ check **"Add Python to PATH"**)
- Or Miniconda: <https://docs.conda.io/en/latest/miniconda.html>

> 如果 `where python` 一行都没输出，说明**根本没装 Python**。装的时候记得勾上 **"Add Python to PATH"**。

Don't want to install Python at all? The sister projects ship ready-to-run `.exe` builds — see the
**"No Python? Try a packaged GUI / 不装 Python？试试打包好的 GUI"** section in the [README](README.md).

---

## 5 Proxy and network errors / 代理与网络报错

Most of these sites are unreachable from mainland China without a proxy. The default is
`http://127.0.0.1:7897` (Clash / Clash Verge / mihomo mixed port).

> 这些站点多数在国内不挂代理连不上。默认走 `http://127.0.0.1:7897`（Clash / Clash Verge / mihomo 混合端口）。

| Message / 报错 | Meaning / 含义 | Fix / 怎么办 |
|---|---|---|
| `proxy_down` | The preflight TCP probe says nothing is listening on that port | Start Clash, or pass the right `--proxy`; if direct access works, use `--proxy off` |
| `bad_proxy_url` | Proxy string isn't a valid URL | Needs the scheme: `http://127.0.0.1:7897` |
| `ProxyError` on every request | The port answers but the proxy isn't forwarding | Check the node is alive; try `--no-preflight` to see the raw error |
| Everything times out, no error | Usually a dead proxy node | Switch node in Clash, then retry |
| Works for one site, 403 for another | That site blocked your exit IP (see §6) | Switch node / use a residential exit |

The preflight runs once before any download: one TCP probe plus one non-retried `GET`, roughly a second.
`proxy_down` / `bad_proxy_url` abort the run; anything else only warns.

> 开跑前会做一次**代理预检**：一次 TCP 探测 + 一次不重试的 GET，约 1 秒。
> `proxy_down` / `bad_proxy_url` 会中止本次运行，其余情况只警告、不拦你。

---

## 6 Site blocks and rate limits / 站点拦截与限速

| Symptom / 现象 | Cause / 原因 | Fix / 怎么办 |
|---|---|---|
| HTTP `429` / `503` | Rate-limited by the site | All threads back off together for `--cooldown` seconds (default 20). Also raise `--delay` / `--jitter` |
| `403` + `Just a moment...` + `cf-mitigated: challenge` header | Cloudflare judged your exit IP suspicious — the whole site is behind it | Switch proxy node. `requests` cannot pass a browser challenge; for FurAffinity the cookie helper ([`sites/furaffinity/FA_get_cookies.py`](sites/furaffinity/FA_get_cookies.py)) is the way in |
| `e926` always fails in the GUI | e926 is Cloudflare-protected and the GUI disables it on purpose | Use `e621` (same content, SFW filter available) or a browser |
| Downloads start fast then crawl | The site starts throttling as volume grows | Lower `-w`, add `--delay` |

> `--delay` / `--jitter` / `--cooldown` 是节流三件套：基准间隔、随机抖动、撞到 429/503 时全体刹车。
> 站点开始变慢就是在提醒你调大它们，而不是加线程。
> ⚠️ 这三个参数**只对 BBooru / HypnoHub / Rule34.us 生效**；e-hentai 与 FurAffinity 的 `-d` 是
> 「随机延迟上限」，等价于 `--delay 0 --jitter d`。
>
> Note: `--delay` / `--jitter` / `--cooldown` apply to **BBooru / HypnoHub / Rule34.us only**.
> For e-hentai and FurAffinity, `-d` means "random delay ceiling" (`--delay 0 --jitter d`).

---

## 7 Filing a bug report / 报 bug 要带什么

A report with these five items can usually be diagnosed in one round-trip:

1. **The command you ran** (full line, including flags) — or "double-clicked `启动.bat`" if that's all
2. **The last 10 lines of output**, not a screenshot of the first error
3. **`python -c "import sys; print(sys.executable)"`** — which interpreter actually ran
4. **Which site** (`e621` / `ehentai` / `fa` / …) and whether `--proxy off` changes anything
5. **What you expected vs. what happened**

> 带上这五项，通常一轮就能定位：
> ① 完整命令行；② 输出**最后 10 行**（不要截第一屏）；③ `python -c "import sys; print(sys.executable)"` 的结果；
> ④ 哪个站点、换成 `--proxy off` 有没有变化；⑤ 你期望什么、实际发生了什么。

Open an issue at <https://github.com/SparkSlugcat/felinepaw/issues>.
Known defects and their status live in [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) — check that first.

> 已知缺陷和修复状态在 [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md)，提 issue 前先扫一眼。
