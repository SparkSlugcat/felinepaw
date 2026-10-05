#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
e-hentai 画廊下载器 v3
============================================================
在 v2（单画廊下载）基础上新增三件事：**标签搜索**、**dry-run 名单**、**按序号挑着下**。

用法：

    # ① 单画廊（v2 老用法，完全兼容）
    python EH_scraper_v2.py "https://e-hentai.org/g/3817181/3b0370c5a1/"

    # ② 标签搜索 + 只看名单（不下载）
    python EH_scraper_v2.py --tags "language:chinese$ female:anal" --limit 30 --dry-run

    # ③ 挑着下：借的 30 个里只要第 2,3,4,7 个
    python EH_scraper_v2.py --tags "language:chinese$" --limit 30 --pick 2-4,7

    # ④ 精确复现（先 dry-run 存名单，再从名单挑 —— 不受搜索结果变动影响）
    python EH_scraper_v2.py --tags "language:chinese$" --limit 30 --dry-run --manifest pick.json
    python EH_scraper_v2.py --from-manifest pick.json --pick 2-4,7

--limit / --pick 作用于「当次名单」（这套设计的唯一规则）：

    搜索模式 -> 名单 = 搜出来的**画廊**      --limit 30 收前 30 个画廊；--pick 挑第几个画廊
    单画廊   -> 名单 = 画廊里的**图片**      --limit 50 收前 50 张图；  --pick 挑第几张图

一句话：**你 dry-run 看到的编号，就是 --pick 要写的编号。**

⚠️ e-hentai 的搜索结果翻页是**游标式**（`&next=<gid>`），不是 `&page=N`。
   实测 `page=0/1/50` 返回的是**同一批数据**（静默重复，不会报错）—— 本脚本已用游标实现，
   见 PROJECT_STATUS / probe 里的反向基线。

依赖：requests + lxml
"""

import argparse
import json
import os
import random
import re
import socket
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, quote_plus

import requests
from lxml import etree

# ---- GBK 终端兜底：标题里的日文/中文不会让整个脚本崩掉 ----
try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

# ---------- 配置 ----------
SITE = "https://e-hentai.org"
API = "https://api.e-hentai.org/api.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
GALLERY_LINKS_PER_PAGE = 20    # 画廊详情页每页 20 个图片链接
SEARCH_PAGE_SIZE = 25          # 搜索结果每页 25 个画廊

#: 搜索模式的默认画廊数（--limit 不填时用它；单画廊模式仍是家族默认 120 张图）
SEARCH_DEFAULT_LIMIT = 30
#: 搜索模式的硬上限。`--limit inf` 也最多收这么多 —— 防止一条命令去拉 25 万个画廊。
SEARCH_HARD_CAP = 1000
#: 目录名最长字符数（Windows 路径总长有限，标题可能极长）
MAX_DIRNAME = 80

# ---- 定位并导入共享模块 common.py（felinepaw 基础库） ----
_here = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.dirname(os.path.dirname(_here)), os.path.dirname(_here), _here):
    if os.path.exists(os.path.join(_p, "common.py")):
        sys.path.insert(0, _p)
        break
import common
# 共享函数别名
create_session = common.create_session
sanitize_filename = common.sanitize_filename
parse_limit = common.parse_limit
parse_pick = common.parse_pick


# ============================================================
# URL / 目录名
# ============================================================

def parse_gallery_url(url: str):
    """从画廊 URL 提取 gid 和 token。"""
    path = urlparse(url.strip()).path
    m = re.search(r"/g/(\d+)/([a-f0-9]+)", path)
    if not m:
        raise ValueError(f"无法从 URL 解析 gid/token: {url}")
    return m.group(1), m.group(2)


def search_url(query: str) -> str:
    """标签搜索的入口 URL。

    e-hentai 的搜索语法（原样写进 --tags 即可，空格分隔多个标签）：
        language:chinese$      精确标签（$ = 完全匹配）
        female:anal            普通标签
        -male:anal             排除某标签
        ~anal                  模糊匹配
    这里用 quote_plus：空格 -> '+'，':' -> '%3A'，'$' -> '%24'（实测均有效）。
    """
    return "%s/?f_search=%s" % (SITE, quote_plus(str(query).strip()))


def safe_dir(name: str, maxlen: int = MAX_DIRNAME) -> str:
    """给目录用的安全名（去掉非法字符并限长）。"""
    s = sanitize_filename(name)
    if len(s) > maxlen:
        s = s[:maxlen].rstrip(" .")
    return s or "untitled"


def query_dir_name(query: str) -> str:
    """把一条搜索语句变成能当目录名的 slug。

    标签语法里的 `$`（精确匹配）和 `~`（模糊匹配）是**语法符号**，不是搜索内容：
    `--tags 'language:chinese$'` 想要的是「中文」这个标签，不是「中文$」。
    但 `sanitize_filename` 只挡 Windows 的非法字符（\\ / : * ? " < > |），
    `$ ~` 在 Windows 下合法，于是会被原样带进目录名 —— 实测长这样：

        eh_language_chinese$

    所以这里先剔掉语法符号，再把空白折成下划线（标签之间通常用空格分隔）：

        'language:chinese$ female:anal'  ->  eh_language_chinese_female_anal

    注意 `-male:anal`（排除某标签）里的 `-` 保留：它是标签名的一部分，
    去掉反而会让目录名表达相反的意思。
    """
    s = re.sub(r"[~$]", "", str(query))
    s = re.sub(r"\s+", "_", s.strip())
    return safe_dir("eh_" + s)


#: 本机 Clash 类代理的常见混合端口（按优先级）。
CLASH_PORTS = (7897, 7890, 7891)


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    """看本地某个端口有没有人在监听。"""
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def resolve_proxy(arg):
    """决定这次用什么代理。返回 `(proxy, 说明)`。

    `--proxy` 留空时**不问系统、直接探本地 Clash 端口**，原因：
      * e-hentai 境内直连必然失败（DNS 污染 + 目标被丢包），没有"直连试试"的余地；
      * 系统/环境变量里可能有别的代理端口（能连上、但出不了网），
        auto 检测拿到它就只能在真请求时才失败，等于让你白跑一次。

    显式 `--proxy off` / `--proxy auto` / `--proxy <URL>` 一律尊重用户输入。
    """
    if arg:                                   # 用户明确指定了
        return arg, ""
    for port in CLASH_PORTS:
        if _port_open("127.0.0.1", port):
            url = "http://127.0.0.1:%d" % port
            return url, "自动选中本地代理 %s（--proxy 可覆盖）" % url
    return None, ""                           # 没探到，交给 common 的 auto 检测


# ============================================================
# 解析：搜索页
# ============================================================

def parse_search_page(html: str):
    """解析一页搜索结果，返回 `(items, total, next_url)`。

    实测（2026-09-27）到的 DOM 结构：
        <table class="itg">
          <tr>                                   <- 每一行是一个画廊
            <td class="gl1c glcat"><div class="cn ct1">Manga</div></td>
            <td class="gl2c"><div class="glthumb"><img alt=标题 src=封面></div></td>
            <td class="gl3c glname">
              <a href="https://e-hentai.org/g/{gid}/{token}/">
                <div class="glink">标题</div>
                <div>
                  <div class="gt" title="language:chinese">chinese</div>   <- 标签在这里
                </div>
              </a>
            </td>
            <td class="gl4c glhide"><a>上传者</a><div>109 pages</div></td>
          </tr>
        </table>
        <div class="searchtext"><p>Found about 253,679 results.</p></div>
        <a id="unext" href="...&next=4215292">Next &gt;</a>   <- 游标翻页

    `next_url` 为 None 表示已是最后一页。
    """
    tree = etree.HTML(html)
    items = []

    for tr in tree.xpath('//table[contains(@class,"itg")]//tr'):
        a = tr.xpath('.//a[div[@class="glink"]]')
        if not a:
            continue                       # 分类筛选行 / 表头行，跳过
        a = a[0]
        href = a.get("href") or ""
        m = re.search(r"/g/(\d+)/([0-9a-f]+)/", href)
        if not m:
            continue

        title = " ".join("".join(a.xpath('.//div[@class="glink"]//text()')).split())
        tags = [t for t in a.xpath('.//div[@class="gt"]/@title') if t]
        cat = tr.xpath('.//td[contains(@class,"glcat")]//div[contains(@class,"cn")]/text()')

        pages = 0
        for txt in tr.xpath('.//td[contains(@class,"gl4c")]//div/text()'):
            mm = re.search(r"(\d+)\s+pages?", txt)
            if mm:
                pages = int(mm.group(1))
                break

        upl = tr.xpath('.//td[contains(@class,"gl4c")]//a/text()')
        items.append({
            "gid": m.group(1),
            "token": m.group(2),
            "url": "%s/g/%s/%s/" % (SITE, m.group(1), m.group(2)),
            "title": title,
            "category": (cat[0].strip() if cat and cat[0].strip() else ""),
            "tags": tags,
            "pages": pages,
            "uploader": (upl[0].strip() if upl else ""),
        })

    total = 0
    mt = re.search(r"Found about ([\d,]+) results", html)
    if mt:
        total = int(mt.group(1).replace(",", ""))

    nxt = tree.xpath('//a[@id="unext"]/@href')
    next_url = nxt[0] if nxt else None
    if next_url:
        next_url = next_url.replace("&amp;", "&")   # lxml 已解码，这里兜底
    return items, total, next_url


def collect_search(session: requests.Session, query: str, want: int,
                   pacing=None, log=print):
    """按游标翻页收集搜索结果，直到收够 `want` 个或没有下一页。

    返回 `(items, total)`；items 长度 ≤ want。
    """
    items, seen, page_no, total = [], set(), 0, 0
    url = search_url(query)

    while len(items) < want:
        page_no += 1
        if pacing:
            pacing.wait()
        resp = session.get(url, timeout=25)
        resp.raise_for_status()
        got, total, nxt = parse_search_page(resp.text)

        fresh = [it for it in got if it["gid"] not in seen]
        for it in fresh:
            seen.add(it["gid"])
        items.extend(fresh)

        log("  搜索第 %d 页: 解析 %d 条（新增 %d，累计 %d%s）"
            % (page_no, len(got), len(fresh), len(items),
               ("/%d" % total) if total else ""))

        if not nxt or not fresh:     # 到底了，或页面不再给出新内容
            break
        if len(items) >= want:
            break
        url = nxt

    return items[:want], total


# ============================================================
# 解析：单画廊
# ============================================================

def fetch_gallery_meta(session: requests.Session, gid: str, token: str):
    """调用官方 gdata API 获取画廊信息；失败返回 None（回退 HTML 解析）。"""
    try:
        payload = {"method": "gdata", "gidlist": [[int(gid), token]], "namespace": 1}
        r = session.post(API, json=payload, timeout=20)
        r.raise_for_status()
        gmeta = r.json().get("gmetadata", [{}])[0]
        if gmeta.get("gid") != int(gid):
            return None
        return gmeta
    except Exception:
        return None


def fetch_gallery_links(session: requests.Session, gid: str, token: str,
                        log=print, pacing=None, max_links=None):
    """翻页抓取画廊全部图片详情页链接，返回有序 `[(detail_url, filename), ...]`。

    e-hentai 画廊页每页只放 20 个链接（GALLERY_LINKS_PER_PAGE），
    大画廊必须翻页（`?p=N`），否则会漏掉 20 张之后的图。

    `max_links` 给"只要前 N 张"的场景用（如搜索模式的 `--pages 2`）：
    收够就停，一个 900 页的画廊从 47 个请求降到 1 个。
    """
    links = []
    page = 0
    while True:
        url = f"{SITE}/g/{gid}/{token}/?p={page}"
        if pacing:
            pacing.wait()
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        tree = etree.HTML(resp.text)

        found = []
        for a in tree.xpath('//div[@id="gdt"]/a'):
            href = a.get("href", "")
            if "/s/" not in href:
                continue
            title = a.get("title", "") or ""
            fname = ""
            m = re.search(r"Page \d+:\s*(.+)$", title)
            if m:
                fname = m.group(1).strip()
            found.append((href, fname))

        if not found:
            break
        links.extend(found)
        log(f"  画廊第 {page + 1} 页: {len(found)} 个链接（累计 {len(links)}）")
        if max_links and len(links) >= max_links:
            links = links[:max_links]
            log(f"  已够 {max_links} 张，停止翻页")
            break
        if len(found) < GALLERY_LINKS_PER_PAGE:
            break
        page += 1
    return links


def fetch_image_url(session: requests.Session, detail_url: str):
    """访问详情页，提取原图 URL。"""
    resp = session.get(detail_url, timeout=20)
    resp.raise_for_status()
    tree = etree.HTML(resp.text)
    srcs = tree.xpath('//div[@id="i3"]/a/img/@src')
    if not srcs:
        return None
    return srcs[0]


# ============================================================
# 名单（manifest）
# ============================================================

def save_manifest(path, payload):
    """把本次名单落盘，供 `--from-manifest` 精确复现。"""
    try:
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                              encoding="utf-8")
        return True
    except OSError as e:
        print("名单写入失败：%s" % e)
        return False


def load_manifest(path):
    """读回名单。返回 payload dict；失败返回 None。"""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        print("找不到名单文件：%s" % path)
    except (OSError, ValueError) as e:
        print("名单文件读不了（%s）：%s" % (type(e).__name__, e))
    return None


# ============================================================
# 展示
# ============================================================

def show_gallery_list(items, total, limit_note=""):
    """回车库名单（搜索模式）。"""
    print("\n===== 搜索结果%s =====" % (("（共 %s 个%s）" % (f"{total:,}", limit_note))
                                       if total else ""))
    print("  %3s  %6s  %-9s  %s" % ("#", "页数", "分类", "标题"))
    for i, it in enumerate(items, 1):
        title = it["title"]
        if len(title) > 58:
            title = title[:57] + "…"
        print("  %3d  %6s  %-9s  %s"
              % (i, it["pages"] or "-", (it["category"] or "-")[:9], title))
    print("  （共 %d 个。用 --pick 2-4,7 挑着下，编号就是上面的 #）" % len(items))


def show_image_list(links):
    """回图片名单（单画廊模式）。"""
    print("\n===== 图片名单（共 %d 张）=====" % len(links))
    for i, (url, fname) in enumerate(links, 1):
        print("  %3d  %s" % (i, fname or url))


# ============================================================
# 参数
# ============================================================

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="e-hentai 画廊下载器 v3（单画廊 / 标签搜索 / dry-run / 挑着下）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  %(prog)s "https://e-hentai.org/g/3817181/3b0370c5a1/"
  %(prog)s --tags "language:chinese$ female:anal" --limit 30 --dry-run
  %(prog)s --tags "language:chinese$" --limit 30 --pick 2-4,7
  %(prog)s --from-manifest eh_manifest.json --pick 2-4,7

--limit / --pick 作用于「当次名单」:
  搜索模式 = 搜出来的画廊;  单画廊模式 = 画廊里的图片
""")

    p.add_argument("url", nargs="?", default=None,
                   help="画廊 URL，例如 https://e-hentai.org/g/3817181/3b0370c5a1/")
    p.add_argument("-t", "--tags", default=None,
                   help="标签搜索（与 URL 二选一）。语法: language:chinese$ / female:anal / "
                        "-male:anal / ~anal，空格分隔多个")

    p.add_argument("-o", "--output", default=None,
                   help="保存目录（搜索模式: 根目录; 单画廊: 该画廊目录）")
    p.add_argument("--limit", default=None,
                   help="搜索模式: 取前 N 个画廊（默认 %d，inf=全部）; "
                        "单画廊模式: 下前 N 张图（默认 120）" % SEARCH_DEFAULT_LIMIT)
    p.add_argument("--pick", default=None,
                   help="按名单序号挑着下，如 2-4,7 / 3- / all（编号 = dry-run 看到的 #）")
    p.add_argument("--pages", default=None,
                   help="搜索模式专用: 每个画廊最多下 N 张图（默认 inf=全部）")
    p.add_argument("--dry-run", action="store_true",
                   help="只拉名单不下载（同时把名单写进 --manifest 指的文件）")
    p.add_argument("--manifest", default="eh_manifest.json",
                   help="--dry-run 保存名单的文件名（默认 eh_manifest.json）")
    p.add_argument("--from-manifest", default=None, metavar="FILE",
                   help="从这个名单文件读结果，跳过搜索请求（配合 --pick 精确复现）")

    p.add_argument("-w", "--workers", type=int, default=4, help="并发线程数（默认4）")
    p.add_argument("-d", "--delay", type=float, default=1.0,
                   help="每次请求前的随机延迟上限秒（默认1.0）。e-hentai 风控较紧，别调太小")
    p.add_argument("--cooldown", type=float, default=20.0,
                   help="吃到 429/503 时全体线程一起安静的秒数，默认 20")
    p.add_argument("--force", action="store_true",
                   help="重新下载已存在的图（默认：存在就跳过）")
    p.add_argument("--proxy", default=None,
                   help="代理: 留空=自动检测, off=直连, 或 http://127.0.0.1:7897")
    p.add_argument("--no-preflight", action="store_true",
                   help="跳过发包前的代理预检")
    return p


def parse_args(argv=None):
    return build_parser().parse_args(argv)


# ============================================================
# 主流程
# ============================================================

def download_gallery(session, gallery, out, args, pacing,
                     index=None, total_galleries=1):
    """下载**一个**画廊的全部图片（搜索模式逐画廊调用）。返回 `(ok, skip, fail)`。

    ⚠️ 这里**刻意不看 `args.pick`**：搜索模式下 `--pick` 挑的是「第几个画廊」，
    已经在 `_run_search()` 里消费掉了。若这里再看一次，`--pick 2` 会变成
    「第 2 个画廊里的第 2 张图」—— 同名参数被复用两次，不是用户要的语义。
    本函数只受 `--pages`（每个画廊最多 N 张）约束。
    """
    gid, token, title = gallery["gid"], gallery["token"], gallery["title"]

    prefix = ("[%d/%d] " % (index, total_galleries)) if index else ""
    print("\n%s%s (gid=%s, %s pages)"
          % (prefix, title, gid, gallery.get("pages") or "?"))

    try:
        per_cap = _parse_pages(args.pages)      # None = 不限
    except ValueError as e:
        print("  %s" % e)
        return (0, 0, 0)

    try:
        # per_cap 直接当 max_links：只要前 N 张就没必要翻完整个画廊
        links = fetch_gallery_links(session, gid, token, log=print, pacing=pacing,
                                    max_links=per_cap)
    except requests.RequestException as e:
        print("  获取画廊页面失败：%s" % e)
        return (0, 0, 0)

    if not links:
        print("  未找到任何图片链接（画廊可能已被删除或需要登录）。")
        return (0, 0, 0)

    if per_cap:
        print("  --pages %d：本画廊只取下前 %d 张" % (per_cap, len(links)))

    out.mkdir(parents=True, exist_ok=True)
    print("  输出目录: %s" % out.resolve())

    jobs = [(k, u) for k, (u, _f) in enumerate(links, 1)]
    return _download_jobs(session, jobs, out, len(links), args, pacing)


def _parse_pages(spec):
    """解析 `--pages`：None / '' / inf -> None（不限制）；非法 -> 抛 ValueError。"""
    if spec is None:
        return None
    s = str(spec).strip().lower()
    if s in ("", "inf"):
        return None
    try:
        n = int(s)
    except ValueError:
        raise ValueError("--pages 需要是正整数或 inf。")
    if n <= 0:
        raise ValueError("--pages 需要是正整数或 inf。")
    return n


def _download_jobs(session, jobs, out, total, args, pacing):
    """多线程下载 `jobs`（`[(序号, 详情页URL), ...]`）到 `out`。返回 (ok, skip, fail)。"""
    lock = threading.Lock()
    stat = {"ok": 0, "skip": 0, "fail": 0}

    def job(idx, detail_url):
        if pacing:
            pacing.wait()
        # 断点续传：目录里已有 {idx}.<ext> 则跳过（--force 时重下）。
        # 注意排除 .part —— 那是上轮下到一半的残留，不该被当成"已完成"。
        existing = [p for p in out.glob(f"{idx}.*") if not p.name.endswith(".part")]
        if not args.force and existing:
            with lock:
                stat["skip"] += 1
            print("  [%d] 已存在，跳过" % idx)
            return
        try:
            img_url = fetch_image_url(session, detail_url)
            if not img_url:
                raise RuntimeError("详情页未找到图片 src")
            ext = Path(urlparse(img_url).path).suffix.lstrip(".") or "jpg"
            filepath = out / f"{idx}.{ext}"
            tmp = filepath.with_suffix(filepath.suffix + ".part")
            with session.get(img_url, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        f.write(chunk)
            if tmp.stat().st_size == 0:
                tmp.unlink()
                raise RuntimeError("下载文件为空")
            os.replace(tmp, filepath)
            with lock:
                stat["ok"] += 1
                done = stat["ok"] + stat["skip"] + stat["fail"]
            print("  #%d 完成 -> %s（进度 %d/%d）" % (idx, filepath.name, done, total))
        except Exception as e:
            if pacing:
                pacing.penalize_on_ratelimit(e)
            with lock:
                stat["fail"] += 1
            print("  [%d] 失败: %s" % (idx, e))

    workers = max(1, min(int(args.workers or 4), 16))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(job, i, u) for i, u in jobs]
        for _ in as_completed(futures):
            pass    # 异常已在 job 内处理

    return stat["ok"], stat["skip"], stat["fail"]


def main(argv=None):
    args = parse_args(argv)

    # ---------- 0. 参数检查：URL 与 --tags 二选一（--from-manifest 时两者都不需要）----------
    if not args.from_manifest and bool(args.url) == bool(args.tags):
        print("请给出画廊 URL 或 --tags 标签（二选一）。")
        print('  例：python EH_scraper_v2.py "https://e-hentai.org/g/xxx/yyy/"')
        print('  例：python EH_scraper_v2.py --tags "language:chinese$" --limit 30 --dry-run')
        print('  例：python EH_scraper_v2.py --from-manifest eh_manifest.json --pick 2-4,7')
        return 1

    # ---------- 0.5 决定代理（留空时优先探本地 Clash 端口） ----------
    resolved_proxy, note = resolve_proxy(args.proxy)
    if note:
        print(note)
    if resolved_proxy is not None:
        args.proxy = resolved_proxy       # 让预检与真实请求用同一个代理

    session = create_session(resolved_proxy, HEADERS)
    session.trust_env = False          # 显式代理优先，别被环境变量覆盖
    if session.proxies:
        print("已启用代理: %s" % list(session.proxies.values())[0])
    else:
        print("未使用代理（直连）—— e-hentai 境内通常直连不通，不通就加 "
              "--proxy http://127.0.0.1:7897")

    pacing = common.Pacing(delay=0.0, jitter=args.delay, cooldown=args.cooldown)

    if not common.run_preflight(args, SITE, "e-hentai"):
        return 1

    # =========================================================
    # A. 搜索模式（--tags，或从搜索名单复现）
    # =========================================================
    if args.tags or args.from_manifest:
        return _run_search(args, session, pacing)

    # =========================================================
    # B. 单画廊模式
    # =========================================================
    return _run_gallery(args, session, pacing)


def _download_gallery_manifest(payload, args, session, pacing):
    """从**单画廊**名单（`mode=gallery`）挑图下载（`--from-manifest` 用）。"""
    items = payload.get("items") or []
    title = payload.get("title") or "gallery"
    if not items:
        print("名单里没有图片。")
        return 1

    print("从名单读回 %d 张图：%s" % (len(items), title))
    show_image_list([(it.get("url", ""), it.get("name", "")) for it in items])

    picked = items
    if args.pick:
        idx = parse_pick(args.pick, len(items))
        if idx is None:
            return 1
        # 同上：文件名保留名单原始序号，避免和别的批次撞名
        picked = [(i, items[i - 1]) for i in idx]
        print("--pick 挑出 %d 张（文件名用原始序号）" % len(picked))
    else:
        picked = list(enumerate(items, 1))

    out = Path(args.output) if args.output else Path(safe_dir(title))
    out.mkdir(parents=True, exist_ok=True)
    print("输出目录: %s" % out.resolve())

    jobs = [(i, it["url"]) for i, it in picked]
    ok, skip, fail = _download_jobs(session, jobs, out, len(picked), args, pacing)

    print("\n===== 下载完成 =====")
    print("成功: %d | 跳过: %d | 失败: %d" % (ok, skip, fail))
    print("文件保存至: %s" % out.resolve())
    return 0 if fail == 0 else 2


def _run_search(args, session, pacing):
    """搜索模式主流程。"""
    query = args.tags or ""

    # ---------- 0. 从名单复现时，先看是哪种名单 ----------
    if args.from_manifest:
        payload = load_manifest(args.from_manifest)
        if not payload:
            return 1
        if (payload.get("mode") or "search") == "gallery":
            return _download_gallery_manifest(payload, args, session, pacing)

    # ---------- 1. 拿名单 ----------
    if args.from_manifest:
        items = payload.get("items") or []
        total = payload.get("total") or 0
        query = payload.get("query") or query
        print("从名单读回 %d 个画廊（原搜索: %s）" % (len(items), query or "(未记录)"))
        if not items:
            print("名单里没有画廊。")
            return 1
    else:
        want_str = args.limit if args.limit is not None else str(SEARCH_DEFAULT_LIMIT)
        want = parse_limit(want_str, SEARCH_HARD_CAP)
        if want is None:
            return 1
        if want > SEARCH_HARD_CAP:
            print("--limit 太大，搜到 %d 个就够了（硬上限 %d）。" % (SEARCH_HARD_CAP, SEARCH_HARD_CAP))
            want = SEARCH_HARD_CAP
        print("\n搜索: %s" % args.tags)
        print("目标: 收前 %d 个画廊" % want)
        try:
            items, total = collect_search(session, args.tags, want, pacing, log=print)
        except requests.RequestException as e:
            print("搜索请求失败：%s" % e)
            return 1
        if not items:
            print("没搜到任何画廊。检查一下标签写法（如 language:chinese$）。")
            return 1

    # ---------- 2. 展示名单 ----------
    show_gallery_list(items, total)

    # ---------- 3. 存名单（dry-run 时一定存；非 dry-run 时若用了 --pick 也存）----------
    manifest_payload = {
        "mode": "search",
        "query": query,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": total,
        "items": items,
    }
    if args.dry_run:
        if save_manifest(args.manifest, manifest_payload):
            print("\n名单已保存: %s" % Path(args.manifest).resolve())
            print("下次可用: python %s --from-manifest %s --pick 2-4,7"
                  % (Path(sys.argv[0]).name, args.manifest))
        return 0

    # ---------- 4. 挑序号 ----------
    if args.pick:
        idx = parse_pick(args.pick, len(items))
        if idx is None:
            return 1
        picked = [(i, items[i - 1]) for i in idx]
        print("\n--pick 挑出 %d 个画廊: %s" % (len(picked), ", ".join(str(i) for i in idx)))
    else:
        picked = list(enumerate(items, 1))

    # ---------- 5. 逐画廊下载 ----------
    out_root = Path(args.output) if args.output else Path(query_dir_name(query))
    print("\n输出根目录: %s" % out_root.resolve())

    ok = skip = fail = 0
    for seq, (no, gal) in enumerate(picked, 1):
        sub = out_root / ("%03d_%s" % (no, safe_dir(gal["title"])))
        a, b, c = download_gallery(session, gal, sub, args, pacing,
                                   index=seq, total_galleries=len(picked))
        ok += a
        skip += b
        fail += c

    print("\n===== 全部完成 =====")
    print("画廊: 选中 %d 个" % len(picked))
    print("图片: 成功 %d | 跳过 %d | 失败 %d" % (ok, skip, fail))
    print("保存至: %s" % out_root.resolve())
    return 0 if fail == 0 else 2


def _run_gallery(args, session, pacing):
    """单画廊模式主流程（v2 老用法 + dry-run / --pick）。"""
    try:
        gid, token = parse_gallery_url(args.url)
    except ValueError as e:
        print(e)
        return 1
    print("gid=%s token=%s" % (gid, token))

    # ---------- 1. API 元数据（标题用于目录命名） ----------
    meta = fetch_gallery_meta(session, gid, token)
    if meta:
        title = meta.get("title") or f"gallery_{gid}"
        filecount = meta.get("filecount")
        print("画廊标题: %s | 文件数: %s | 分类: %s"
              % (title, filecount, meta.get("category")))
    else:
        print("gdata API 未返回信息，回退用 URL 命名目录。")
        title = f"gallery_{gid}"

    # ---------- 2. 抓取全部详情页链接 ----------
    print("正在翻页抓取图片详情页链接...")
    try:
        detail_links = fetch_gallery_links(session, gid, token, log=print, pacing=pacing)
    except requests.RequestException as e:
        print(f"获取画廊页面失败: {e}")
        return 1

    if not detail_links:
        print("未找到任何图片链接（画廊可能已被删除或需要登录）。")
        return 1

    # ---------- 3. dry-run：只列名单 ----------
    if args.dry_run:
        show_image_list(detail_links)
        payload = {
            "mode": "gallery",
            "url": args.url,
            "gid": gid,
            "token": token,
            "title": title,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total": len(detail_links),
            "items": [{"url": u, "name": f} for u, f in detail_links],
        }
        if save_manifest(args.manifest, payload):
            print("\n名单已保存: %s" % Path(args.manifest).resolve())
        return 0

    # ---------- 4. limit / pick ----------
    limit = parse_limit(args.limit, len(detail_links))
    if limit is None:
        return 1
    picked = detail_links[:limit]

    if args.pick:
        idx = parse_pick(args.pick, len(picked))
        if idx is None:
            return 1
        # ⚠️ 保留**名单里的原始序号**当文件名，不能重新编号：
        #    否则 --pick 2-4 会写出 1/2/3.*，下次 --pick 5-6 又写出 1/2.*
        #    与已有的撞名，被断点续传当成"已存在"跳过 —— 静默漏图。
        picked = [(i, picked[i - 1]) for i in idx]
        print("--pick 挑出 %d 张（在名单前 %d 张里挑；文件名用原始序号 %s）"
              % (len(picked), limit, ",".join(str(i) for i in idx)))
    else:
        picked = list(enumerate(picked, 1))

    print("共 %d 张图片（下载上限 %d），%d 线程，随机延迟 0~%ss"
          % (len(picked), limit, args.workers, args.delay))

    # ---------- 5. 输出目录（修 v2 的 safe_name NameError） ----------
    out = Path(args.output) if args.output else Path(safe_dir(title))
    out.mkdir(parents=True, exist_ok=True)

    # ---------- 6. 下载 ----------
    jobs = [(i, u) for i, (u, _f) in picked]
    ok, skip, fail = _download_jobs(session, jobs, out, len(picked), args, pacing)

    # ---------- 7. 汇总 ----------
    print("\n===== 下载完成 =====")
    print(f"画廊: {title} (gid={gid})")
    print(f"成功: {ok} | 跳过: {skip} | 失败: {fail}")
    print(f"文件保存至: {out.resolve()}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
