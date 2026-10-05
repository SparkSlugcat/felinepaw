#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
common.py - 多站点爬虫共享模块（felinepaw 基础库）
==============================================
统一提供：
- 代理检测与应用（Windows 系统代理、环境变量）
- 带重试与代理的 requests 会话
- 文件名清理、断点续传扫描、--limit 解析
- 节流（Pacing：基准延时 + 随机抖动 + 429 全局刹车）
- 代理预检（fail-fast：代理没开时立刻说清，而不是卡很久）

供 sites/ 下各站点脚本复用，避免每个脚本复制一份相同代码。
用法：脚本内先定位本文件再 import：
    import os, sys
    _here = os.path.dirname(os.path.abspath(__file__))
    for _p in (os.path.dirname(_here), _here):
        if os.path.exists(os.path.join(_p, "common.py")):
            sys.path.insert(0, _p); break
    import common
"""

import os
import random
import re
import threading
import time
from pathlib import Path
from typing import Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


#: 预检探针等"裸请求"用的 UA（与各站点自己的 UA 无关，只求不被当成脚本拒绝）。
DEFAULT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


# ============================================================
# 代理支持
# ============================================================

def _fix_proxy_scheme(url: str) -> str:
    """Windows 注册表里的 https 代理前缀对本地 Clash 类代理是错的，回环地址改成 http。"""
    low = url.strip().lower()
    if low.startswith("https://"):
        try:
            from urllib.parse import urlparse
            host = (urlparse(url).hostname or "").lower()
        except Exception:
            host = ""
        if host in ("127.0.0.1", "localhost", "::1") or host.startswith("127."):
            return "http://" + url[len("https://"):]
    return url


def detect_proxy() -> str:
    """自动检测代理：环境变量 -> Windows 系统代理设置；找不到返回空串。"""
    for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        v = os.environ.get(key, "").strip()
        if v:
            return _fix_proxy_scheme(v)
    try:
        import urllib.request
        proxies = urllib.request.getproxies()
        for key in ("https", "http"):
            v = (proxies.get(key) or "").strip()
            if v and "://" in v:
                return _fix_proxy_scheme(v)
    except Exception:
        pass
    return ""


def normalize_proxy(proxy: Optional[str]) -> str:
    """把用户填的代理整理成标准 URL；'off'/'auto' 等关键字分别处理。"""
    p = (proxy or "").strip()
    if not p:
        return ""
    low = p.lower()
    if low in ("off", "direct", "none", "不使用代理", "关闭"):
        return ""
    if low in ("auto", "自动", "跟随系统", "系统"):
        return detect_proxy()
    if "://" not in p:
        p = "http://" + p
    return _fix_proxy_scheme(p)


def apply_proxy(session: requests.Session, proxy: Optional[str] = None) -> None:
    """给会话应用代理。

    proxy: None/"" = 自动检测；"off" = 直连；其他 = 代理 URL。
    注意：requests 2.27 下仅设置 session.proxies 不生效，
    必须同时关闭 trust_env 才会使用显式代理。
    """
    if proxy is None or str(proxy).strip() == "":
        detected = detect_proxy()
        if detected:
            session.proxies = {"http": detected, "https": detected}
            session.trust_env = False
    else:
        p = normalize_proxy(proxy)
        if p:
            session.proxies = {"http": p, "https": p}
            session.trust_env = False


def create_session(proxy: Optional[str] = None,
                   headers: Optional[dict] = None) -> requests.Session:
    """创建带重试和代理的会话。"""
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1,
                  status_forcelist=[500, 502, 503, 504], allowed_methods=["GET"])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    if headers:
        session.headers.update(headers)
    apply_proxy(session, proxy)
    return session


# ============================================================
# 通用工具
# ============================================================

def sanitize_filename(name: str) -> str:
    """去除文件名/文件夹名中的非法字符。"""
    name = re.sub(r'[\\/*?:"<>|]', "_", name or "")
    name = re.sub(r"[\s.]+$", "", name).strip()
    return name or "untitled"


def find_existing_max(out_dir: Path) -> int:
    """扫描目录中已有的数字文件名，返回最大序号（断点续传用）。"""
    max_num = 0
    try:
        for f in out_dir.iterdir():
            if f.is_file() and f.stem.isdigit():
                try:
                    n = int(f.stem)
                except ValueError:
                    continue
                if n > max_num:
                    max_num = n
    except OSError:
        pass
    return max_num


def parse_limit(limit_str, total: int):
    """--limit 语义（各站点统一）：默认 120；inf=全部；正整数=前 N 个。

    参数非法时打印提示并返回 None（调用方应中止）。
    """
    if limit_str is None:
        return 120
    s = str(limit_str).strip().lower()
    if s == "inf":
        return total
    try:
        n = int(s)
    except ValueError:
        print("--limit 需要是正整数或 inf。")
        return None
    if n <= 0:
        print("--limit 需要是正整数或 inf。")
        return None
    return n


def parse_pick(spec, total: int):
    """解析「挑着下」的序号表达式，返回 1-based 升序去重的序号列表。

    打印机式的写法都能用（假设名单 total=10）：

        "2-4,7"     -> [2, 3, 4, 7]
        "1,3,5"     -> [1, 3, 5]
        "3-"        -> [3, 4, 5, 6, 7, 8, 9, 10]   （省略终点 = 到末尾）
        "-3"        -> [1, 2, 3]                    （省略起点 = 从头）
        "8-10"      -> [8, 9, 10]
        "all" / "*" -> [1, 2, ..., 10]

    参数非法时打印提示并返回 None（调用方应中止）。
    越界序号**只忽略不报错**（搜索结果的总数会变，用户看到的名单可能并非最新），
    但会打印一行提示，避免用户以为"我明明写了却没下"。
    """
    s = str(spec).strip().lower()
    if s in ("all", "*"):
        return list(range(1, total + 1))
    if not s:
        print("--pick 是空的。写成 2-4,7 这样的序号（或 all）。")
        return None

    picked = set()
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d*)\s*-\s*(\d*)", part)
        if m:
            a, b = m.group(1), m.group(2)
            if not a and not b:              # 光一个 "-"
                print("--pick 里的 '-' 两边至少要有一个数字：%r" % part)
                return None
            start = int(a) if a else 1
            end = int(b) if b else total
            if start > end:
                print("--pick 的区间写反了（%s > %s）：%r" % (start, end, part))
                return None
            picked.update(range(start, end + 1))
        elif part.isdigit():
            picked.add(int(part))
        else:
            print("--pick 看不懂这一段：%r（支持 2-4,7 / 3- / -3 / all）" % part)
            return None

    keep = sorted(i for i in picked if 1 <= i <= total)
    dropped = sorted(i for i in picked if i not in keep)
    if dropped:
        if len(dropped) > 5:
            print("--pick 里有超出范围的序号已忽略：%d 个（%d~%d 等，当前名单只有 %d 个）"
                  % (len(dropped), dropped[0], dropped[-1], total))
        else:
            print("--pick 里有超出范围的序号已忽略：%s（当前名单只有 %d 个）"
                  % (", ".join(str(i) for i in dropped), total))
    if not keep:
        print("--pick 挑完之后一个都不剩。")
        return None
    return keep


# ============================================================
# 节流（礼貌请求）
# ============================================================

class Pacing:
    """全局限速器：每次请求前等一个「基准延时 + 随机抖动」，
    并且支持遇到 429 时把**所有线程**一起按住（`penalize`）。

    为什么需要它——现在的三个站点只有"失败重试的退避"（`sleep(0.4*(attempt+1))`），
    那是**撞墙之后才退**；并发 8~32 个线程同时撞限流时，各退各的，站方看到的
    仍然是一串密集请求。两件事能改善：

    * **随机抖动**：固定间隔的请求节奏很好认（像机器）。加 jitter 让间隔在
      `[delay, delay+jitter]` 之间随机，接近人的节奏。
    * **全局刹车**：某个线程吃到 429，说明站方已经在限速了 —— 这时让**全部**
      线程安静 `cooldown` 秒，比各线程各自撞墙再各自退避有效得多。

    默认 `delay=0, jitter=0` 时行为与改动前完全一致（只有 `penalize` 是新增的），
    所以不传 `--delay/--jitter` 的老用法不受影响。
    """

    def __init__(self, delay: float = 0.0, jitter: float = 0.0, cooldown: float = 20.0):
        self.delay = max(0.0, float(delay or 0.0))
        self.jitter = max(0.0, float(jitter or 0.0))
        self.cooldown = max(0.0, float(cooldown or 0.0))
        self._lock = threading.Lock()
        self._until = 0.0

    @property
    def active(self) -> bool:
        """完全不限速时返回 False，调用方可据此省掉一次锁开销。"""
        return self.delay > 0 or self.jitter > 0

    def wait(self) -> None:
        with self._lock:
            remain = self._until - time.time()
        if remain > 0:
            time.sleep(min(remain, 120.0))
        d = self.delay + (random.uniform(0.0, self.jitter) if self.jitter else 0.0)
        if d > 0:
            time.sleep(d)

    def penalize(self, seconds: float) -> None:
        """触发风控后，让全部线程安静 `seconds` 秒。"""
        with self._lock:
            self._until = max(self._until, time.time() + max(0.0, float(seconds or 0.0)))

    def penalize_on_ratelimit(self, exc: BaseException) -> bool:
        """异常若是 429/503（被限流），就自动刹车 `self.cooldown` 秒，返回是否刹了车。

        站点 `download_one` 的 except 里一行即可：
            if pacing: pacing.penalize_on_ratelimit(e)
        """
        if is_ratelimit(exc):
            self.penalize(self.cooldown)
            return True
        return False


def is_ratelimit(exc: BaseException) -> bool:
    """异常的响应码是不是"被限流"（429 / 503）。

    `requests.raise_for_status()` 抛的 `HTTPError` 上挂着 `.response`；
    连接层异常（超时、ProxyError）没有，一律不算限流。
    """
    resp = getattr(exc, "response", None)
    return getattr(resp, "status_code", None) in (429, 503)


def make_pacing(args) -> Pacing:
    """从 `args` 里取 `--delay/--jitter/--cooldown` 造一个 Pacing（各站点统一入口）。"""
    return Pacing(getattr(args, "delay", 0.0), getattr(args, "jitter", 0.0),
                  getattr(args, "cooldown", 20.0))


def add_pacing_args(parser) -> None:
    """给站点 parser 注册统一的节流参数（--delay / --jitter / --cooldown）。"""
    parser.add_argument("--delay", type=float, default=0.0,
                        help="每次请求前的基准延时秒数，默认 0（不限速）。"
                             "被站点限流时试试 --delay 1.0")
    parser.add_argument("--jitter", type=float, default=0.0,
                        help="在基准延时上叠加的随机抖动秒数，默认 0。"
                             "配合 --delay 用（如 --delay 1 --jitter 1.5）让节奏不像机器")
    parser.add_argument("--cooldown", type=float, default=20.0,
                        help="吃到 429/503 时让所有线程一起安静多少秒，默认 20")


def add_preflight_args(parser) -> None:
    """给站点 parser 注册 `--no-preflight`（跳过发包前的链路预检）。"""
    parser.add_argument("--no-preflight", action="store_true",
                        help="跳过发包前的代理预检（默认会先花约 1 秒确认链路，"
                             "失败时能立刻说清是 Clash 没开还是节点问题）")


# ============================================================
# 代理预检（fail-fast）
# ============================================================

#: 预检各步的上界。**刻意压得很短**——预检的全部意义就是"快"。
#: ⚠️ TCP 上界必须 ≥ 2.5s：实测本机连**本地已关闭端口**要 ~2.03s 才返回
#: `ConnectionRefusedError(10061)`，不是立刻拒连。给 1.5s 只会拿到一个假的
#: `timeout`，结论虽然一样，但说不清"拒连"和"被丢包"。
PROBE_TCP_TIMEOUT = 2.5      # TCP 连代理端口
PROBE_CONNECT_TIMEOUT = 2.0  # HTTP 建连
PROBE_READ_TIMEOUT = 6.0     # HTTP 等首包
#: HTTP 探针的尝试次数。**只在"抛异常"时重试**（拿到状态码就认），
#: 目的是滤掉瞬时抖动——单次失败不足以判死刑。
PROBE_ATTEMPTS = 2


class ProxyCheck:
    """预检结果。**不抛异常**，调用方只看 `.ok` / `.code` / `.message` / `.hint`。"""

    __slots__ = ("ok", "code", "message", "hint", "elapsed")

    def __init__(self, ok, code, message, hint="", elapsed=0.0):
        self.ok = bool(ok)
        self.code = code
        self.message = message
        self.hint = hint
        self.elapsed = elapsed

    def __bool__(self):
        return self.ok

    def __repr__(self):
        return "<ProxyCheck %s %s>" % ("OK" if self.ok else "FAIL", self.code)

    @property
    def fatal(self) -> bool:
        """要不要**硬拦**这次任务。

        只有「结构上根本不可能成功」的两种才算 fatal：
          * `proxy_down`    —— 端口没人监听，**每一个**请求都会失败
          * `bad_proxy_url` —— 代理串自己就是坏的
        其余（`proxy_bad` 隧道抖 / `no_proxy_blocked` 用户自己选的直连）**只警告不拦**：
        预检终究是启发式判据，单次失败不足以致命，真实下载自带退避重试。
        """
        return self.code in ("proxy_down", "bad_proxy_url")


def effective_proxy(proxy: Optional[str]) -> str:
    """算出**实际会用的**代理 URL（空串 = 直连）。

    必须与 `apply_proxy()` 的判定逐字一致，否则预检说"代理没问题"、
    真实请求却走了另一条路（或反过来）。
    """
    if proxy is None or str(proxy).strip() == "":
        return detect_proxy()
    return normalize_proxy(proxy)


def _split_hostport(proxy_url: str) -> Tuple[str, int]:
    """从 `http://127.0.0.1:7897` 抠出 (host, port)。解析不出来返回 ("", 0)。

    ⚠️ `urlparse().port` 遇到非法端口（如 `http://127.0.0.1:abc`）会抛 `ValueError`，
    必须兜住——否则用户手滑填错代理串，预检自己先崩了。
    """
    from urllib.parse import urlparse
    try:
        u = urlparse(proxy_url if "://" in proxy_url else "http://" + proxy_url)
        port = u.port or (443 if (u.scheme or "").lower() == "https" else 80)
        return (u.hostname or ""), int(port)
    except ValueError:
        return "", 0


def _tcp_probe(host: str, port: int,
               timeout: float = PROBE_TCP_TIMEOUT) -> Tuple[bool, str]:
    """只连 TCP、不发任何字节。返回 (通否, 失败原因码: ''|'dns'|'refused'|'timeout')。"""
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, ""
    except socket.gaierror:
        return False, "dns"
    except ConnectionRefusedError:
        return False, "refused"
    except OSError:
        return False, "timeout"


def _probe_http_once(url: str, proxy: str = "",
                     connect_timeout: float = PROBE_CONNECT_TIMEOUT,
                     read_timeout: float = PROBE_READ_TIMEOUT) -> int:
    """**不重试**的 GET，返回状态码。

    刻意不用 `create_session()`——那个挂了 urllib3 的 `Retry(total=3)`，
    正是"Clash 没开时卡几十秒"的一半原因。
    """
    s = requests.Session()
    s.trust_env = False
    if proxy:
        s.proxies = {"http": proxy, "https": proxy}
    s.headers.update({"User-Agent": DEFAULT_UA})
    try:
        r = s.get(url, timeout=(connect_timeout, read_timeout), stream=True)
        try:
            return r.status_code
        finally:
            r.close()
    finally:
        s.close()


def check_proxy(proxy: Optional[str] = None, probe_url: Optional[str] = None,
                connect_timeout: float = PROBE_CONNECT_TIMEOUT,
                read_timeout: float = PROBE_READ_TIMEOUT,
                attempts: int = PROBE_ATTEMPTS) -> ProxyCheck:
    """发包前的链路预检——目的只有一个字：**快**。

    没预检时，"Clash 没启动"的表现是**卡很久再丢一个 `ProxyError`**
    （连接层重试 × 指数退避）。预检把它压成 **TCP 探一下（≤2.5s）+ 不重试的 GET**，
    典型 1 秒多就有结论，而且能**说清是哪一段坏**（端口 / 隧道 / 目标站）。

    `probe_url` 传了才做 HTTP 那一步；只在 `probe_url` 为 None 时退化成"只测端口"。

    `code` 取值（★ = `fatal`，调用方应当硬拦）：
      ok_proxy         走代理，目标站通
      ok_proxy_no_url  走代理，端口通（未做 HTTP 探测）
      ok_direct        没配代理，直连（境外网络 / TUN 模式）
      ok_direct_no_url 没配代理，直接放行
    ★ proxy_down       代理端口没人监听 → **Clash 没启动**
      proxy_bad        端口通但过不去目标站 → 节点/订阅问题（不是 Clash 没开）
      no_proxy_blocked 没配代理且直连不通（境内默认就是这个）
    ★ bad_proxy_url    `--proxy` 填的东西解析不出主机名
    """
    t0 = time.time()

    def done(ok, code, message, hint=""):
        return ProxyCheck(ok, code, message, hint, time.time() - t0)

    p = effective_proxy(proxy)

    # ---------- 配了代理 ----------
    if p:
        host, port = _split_hostport(p)
        if not host:
            return done(False, "bad_proxy_url",
                        "代理地址解析不出主机名：%r" % p,
                        "检查 --proxy，形如 http://127.0.0.1:7897；'off' = 直连，'auto' = 自动检测。")

        alive, why = _tcp_probe(host, port)
        if not alive:
            if why == "dns":
                return done(False, "bad_proxy_url",
                            "代理主机名解析失败：%s" % host,
                            "检查 --proxy 里的主机名拼写。")
            detail = ("端口被拒连（ConnectionRefused）" if why == "refused"
                      else "端口 %.1fs 内无响应（可能没监听，也可能被防火墙丢包）"
                           % PROBE_TCP_TIMEOUT)
            return done(False, "proxy_down",
                        "代理端口 %s:%d 连不上 —— %s" % (host, port, detail),
                        "**Clash 没启动**。双击 Clash Verge 图标启动，"
                        "再用 `python clash.py status` 确认。\n"
                        "      如果你其实是 TUN 模式直接上网、根本不需要 HTTP 代理，"
                        "改用 `--proxy off`。")

        if not probe_url:
            return done(True, "ok_proxy_no_url",
                        "代理端口 %s:%d 通（未做目标站探测）" % (host, port))

        last = None
        for _i in range(max(1, int(attempts))):
            try:
                status = _probe_http_once(probe_url, p, connect_timeout, read_timeout)
                if 200 <= status < 400:
                    return done(True, "ok_proxy",
                                "代理 %s:%d 通，目标站 %s → HTTP %d" % (host, port, probe_url, status))
                if status in (403, 404, 429):
                    # 站点对裸请求的拒绝/限流：**通道是通的**，这不是代理故障。
                    return done(True, "ok_proxy",
                                "代理链路通，目标站回 HTTP %d（站点策略，不是链路问题）" % status)
                return done(False, "proxy_bad",
                            "代理端口通，但目标站返回 HTTP %d" % status,
                            "站点可能临时故障，或需要特定请求头。预检不过仍会继续跑。")
            except requests.exceptions.Timeout:
                last = "%.0fs 内没等到响应" % read_timeout
            except requests.exceptions.ProxyError as e:
                last = "到目标站的隧道建不起来（ProxyError）"
            except Exception as e:                                   # noqa: BLE001
                last = "%s: %s" % (type(e).__name__, str(e)[:80])
        return done(False, "proxy_bad",
                    "代理端口通，但访问 %s 失败（已试 %d 次）：%s" % (probe_url, attempts, last),
                    "这是**节点/订阅**的问题，不是 Clash 没开。换个节点再试。\n"
                    "      预检没过**仍会继续跑**（万一只是瞬时抖动）；真想中止按 Ctrl-C。")

    # ---------- 没配代理（直连） ----------
    if not probe_url:
        return done(True, "ok_direct_no_url", "未配置代理，直接出网")
    for _i in range(max(1, int(attempts))):
        try:
            status = _probe_http_once(probe_url, "", connect_timeout, read_timeout)
            if status < 500:
                return done(True, "ok_direct",
                            "直连 %s → HTTP %d" % (probe_url, status))
            last = "HTTP %d" % status
        except Exception as e:                                       # noqa: BLE001
            last = "%s" % type(e).__name__
    return done(False, "no_proxy_blocked",
                "没配代理，直连 %s 失败（已试 %d 次）：%s" % (probe_url, attempts, last),
                "这个站点在境内通常需要代理。加 `--proxy http://127.0.0.1:7897`"
                "（或让它自动检测）再试。\n"
                "      预检没过**仍会继续跑**；真想中止按 Ctrl-C。")


def run_preflight(args, probe_url: Optional[str] = None,
                  target_name: str = "") -> bool:
    """站点 `main()` 的标准预检入口。返回 True = 可以继续，False = 应当中止。

    各站点只需一行：`if not common.run_preflight(args, MAIN_SITE): return`
    输出统一走英文（与各站点既有 CLI 输出保持一致），避免 GBK 终端下混排乱码。
    """
    if getattr(args, "no_preflight", False):
        return True
    pf = check_proxy(getattr(args, "proxy", None), probe_url)
    tag = (" " + target_name) if target_name else ""
    if pf.ok:
        print("Preflight%s: OK (%.1fs) - %s" % (tag, pf.elapsed, pf.message))
        return True
    level = "FAILED" if pf.fatal else "WARN"
    print("Preflight%s: %s (%.1fs) - %s" % (tag, level, pf.elapsed, pf.message))
    if pf.hint:
        print("  %s" % pf.hint)
    if pf.fatal:
        print("  (--no-preflight skips this check)")
        return False
    return True
