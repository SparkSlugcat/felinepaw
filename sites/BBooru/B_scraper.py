"""
从 bbooru.com（Gelbooru 系）按标签批量下载原图。

v5（2026-09-02，新增 Artist 模式、--page、--pool-rev）：
  * 【三大新增功能】：
    1. Artist 模式（--mode artist）：给定标签 → API 搜索帖子 → 对每个帖子查
       post-pool-list 页面判定所属 pool → 按 pool 分组下载池内全部帖子 →
       不属于任何 pool 的放 others/（--skip-others 跳过）。
    2. Page 模式（--page N）：配合 --tags 指定只下载 API 翻页的某一页。
    3. Pool-rev（--pool-rev）：--pool 模式下反转编号顺序（与 e621.py 反转版一致）。
  * 保持 v4 所有功能、参数、管线完全兼容。

v4（2026-09-02，JSON API 优先 + HTML 兜底）：
  * 【主模式】Gelbooru 标准 JSON API（--mode auto/api，默认 auto）：
      GET /index.php?page=dapi&s=post&q=index&json=1&tags=...&pid=..&limit=100
      返回裸数组（部分变体用 {"post":[...]} 包装，已兼容），file_url 直接给原图直链
      → 1 次请求拿整页，无需详情页。
      API 实测：offset = pid * limit；越界/到尾返回 []；超大 pid 返回 XML abuse 报错（需容错）。
  * 【兜底】HTML 模式（--mode html）保留 v3 逻辑：HTML 翻页收集 → 每帖进详情页找
      "Original image" 链接 → 下载（每张 2 次请求）。API 模式首屏失败时 auto 自动回退。
  * 【Pool】--pool <show页URL或id>：bbooru 的 dapi 不支持 pool 过滤，pool 帖子列表
      走 HTML pool show 页收集（/index.php?page=pool&s=show&id=<池id>），
      每帖仍是 HTML 任务（进详情页取原图），复用同一下载管线与断点续传。
  * 两种模式任务统一为 {'id': 'p<帖子id>', 'dl': 原图直链或None, 'page': 详情URL或None}，
     文件名均以 p<id> 开头 → 跨模式断点续传兼容（已存在的文件跳过）。
  * 关键点：session 必须带 cookie adult_mode=1（否则 adult 贴被隐藏）。
  * 断点续传/原子写：.part 临时文件 + os.replace；多线程下载（--threads）；失败重试（--retry）。

用法示例：
    python B_scraper.py --tags landscape --limit 100
    python B_scraper.py --tags "cute fox" --limit inf --threads 12 -o D:/pictures
    python B_scraper.py --tags landscape --mode html --limit 50   # 强制 HTML 兜底模式
    python B_scraper.py --tags landscape --limit 500 --dry-run     # 只收集不下载
    python B_scraper.py --pool https://bbooru.com/index.php?page=pool&s=show&id=33976
    python B_scraper.py --pool 33976 --limit 20 -o D:/pics         # pool 也可只给 id
    # v5 新增
    python B_scraper.py --tags artist_name --mode artist           # Artist 模式
    python B_scraper.py --tags artist_name --mode artist --skip-others  # 跳过不属于pool的
    python B_scraper.py --tags fox --page 2                        # 仅下载第 2 页
    python B_scraper.py --pool 33976 --pool-rev                    # pool 反转编号
"""

import os
import re
import sys
import time
import argparse
import threading
import html as html_mod
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# Windows GBK 控制台可能编不了个别字符（emoji 等）→ 打印时替换为 '?'，避免 UnicodeEncodeError 崩溃
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    except Exception:
        pass
# 更通用的兜底：把所有 print 输出转成 GBK 可显示的字符
import builtins as _builtins
_orig_print = _builtins.print
def _safe_print(*args, **kwargs):
    new_args = []
    for a in args:
        if isinstance(a, str):
            try:
                a.encode(sys.stdout.encoding or 'utf-8', errors='replace')
            except (UnicodeEncodeError, LookupError):
                a = a.encode('gbk', errors='replace').decode('gbk')
        new_args.append(a)
    _orig_print(*new_args, **kwargs)
_builtins.print = _safe_print

# ---- 定位并导入共享模块 common.py（felinepaw 基础库） ----
_here = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.dirname(os.path.dirname(_here)), os.path.dirname(_here), _here):
    if os.path.exists(os.path.join(_p, "common.py")):
        sys.path.insert(0, _p)
        break
import common
sanitize_filename = common.sanitize_filename
parse_limit = common.parse_limit

# ---------- 常量配置 ----------
API_LIST_URL = "https://bbooru.com/index.php?page=dapi&s=post&q=index"   # Gelbooru JSON API
HTML_LIST_URL = "https://bbooru.com/index.php?page=post&s=list"           # HTML 列表页
ORIGINAL_TEXT = "Original image"
API_PAGE_SIZE = 100     # API 单页条数（Gelbooru limit ≤100；offset = pid*limit）
HTML_PAGE_SIZE = 42     # HTML 列表每页条目数
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
# ---------------------------


class ApiError(Exception):
    """API 请求/解析异常（触发 auto 回退到 HTML 模式）"""


# 每线程一个 requests.Session（复用 keep-alive 连接）
_local = threading.local()


def ensure_dir(path):
    """确保目录存在"""
    if not os.path.exists(path):
        os.makedirs(path)


def get_extension_from_url(url, default='.jpg'):
    """从 URL 中提取文件扩展名，若没有则返回默认值"""
    path = urlparse(url).path
    ext = os.path.splitext(path)[1]
    return ext if ext else default


def parse_args():
    parser = argparse.ArgumentParser(
        description="从 bbooru.com 下载原图：--tags 按标签（JSON API 优先），或 --pool 按合集（HTML）")
    parser.add_argument("--tags", default=None,
                        help="标签，多个用空格分开，如 'cute fox' 或 landscape（与 --pool 二选一）")
    parser.add_argument("--pool", default=None,
                        help="pool 的 show 页 URL 或纯 id，如 https://bbooru.com/index.php?page=pool&s=show&id=33976 或 33976")
    parser.add_argument("--mode", choices=["auto", "api", "html", "artist"], default="auto",
                        help="下载引擎: auto=API优先失败自动回退HTML(默认), api=强制API, html=强制HTML, artist=Artist模式(需配合--tags)")
    parser.add_argument("--limit", default=None,
                        help="下载数量: 正整数 或 inf(全部)；不填默认只下载前 120 个")
    parser.add_argument("--adult", choices=['y', 'n'], default='y',
                        help="是否包含成人内容（y=是，n=否），默认 y。n 时原图会被站点隐藏")
    parser.add_argument("--name", default=None, help="自定义下载文件夹名称，默认与 --tags 相同")
    parser.add_argument("-o", "--o", "--output", dest="output_dir", default='.',
                        help="输出根目录，默认为当前目录")
    parser.add_argument("--threads", type=int, default=8, help="并发线程数（翻页+下载），默认 8")
    parser.add_argument("--retry", type=int, default=2, help="单个任务失败重试次数，默认 2")
    parser.add_argument("--proxy", default=None,
                        help="代理: 留空=自动检测, off=直连, 或 http://127.0.0.1:7897")
    parser.add_argument("--dry-run", action="store_true", help="只收集列表，不下载（用于测试翻页）")
    # v5 新增参数
    parser.add_argument("--skip-others", action="store_true",
                        help="Artist 模式：跳过不属于任何 pool 的帖子（不放入 others/ 文件夹）")
    parser.add_argument("--page", type=int, default=None,
                        help="配合 --tags 指定只下载 API 翻页的某一页（从 1 开始）")
    parser.add_argument("--pool-rev", action="store_true",
                        help="--pool mode: reverse numbering order")
    parser.add_argument("--force-pool-check", action="store_true",
                        help="artist mode: force full post-pool-list query for all posts (default: check first 10 only)")
    return parser.parse_args()


def make_session(adult_flag, proxy=None):
    """新建带 UA、代理和 adult_mode cookie 的 Session"""
    s = common.create_session(proxy, {"User-Agent": UA})
    # adult_mode=1 显示成人内容；=0 只看 general/safe（站内模式名 general）
    s.cookies.set('adult_mode', '1' if adult_flag else '0', domain='bbooru.com')
    return s


def get_session(adult_flag, proxy=None):
    """线程级 Session（keep-alive 复用）"""
    s = getattr(_local, 'sess', None)
    if s is None:
        s = make_session(adult_flag, proxy)
        _local.sess = s
    return s


# ============================================================
# API 模式（JSON API）
# ============================================================

def fetch_api_page(session, tags, pid):
    """抓一页 API 数据，返回该页 post 列表（可能是 []）。异常抛 ApiError。"""
    try:
        r = session.get(API_LIST_URL, params={
            "json": 1, "tags": tags, "pid": pid, "limit": API_PAGE_SIZE,
        }, timeout=25)
        r.raise_for_status()
    except requests.RequestException as e:
        raise ApiError(f"API 请求失败: {e}")
    return parse_api_response(r)


def parse_api_response(r):
    """解析 API 响应为 post 列表。

    实测 bbooru 返回【裸数组】；部分 Gelbooru 变体用 {"post": [...]} 包装；
    超大 pid / 被限流时返回 XML <response success="false" .../>（非 JSON）。
    """
    text = (r.text or "").lstrip()
    if not text:
        raise ApiError("API 返回空响应")
    if text.startswith(("<", "<?xml")):
        raise ApiError("API 返回非 JSON（可能被限流/abuse）: " + text[:120].replace("\n", " "))
    try:
        data = r.json()
    except ValueError as e:
        raise ApiError(f"API 返回非法 JSON: {e}")
    if isinstance(data, dict):
        # 兼容 {"post":[...]} / {"posts":[...]} 包装形态
        data = data.get("post", data.get("posts", None))
        if data is None:
            raise ApiError("未知 API 结构: " + str(list(dict(data).keys()))[:120])
    if not isinstance(data, list):
        raise ApiError("未知 API 结构，不是数组: " + str(data)[:120])
    return data


def api_post_to_task(p):
    """API post 记录 → 统一任务 dict（id 以 p 开头便于与 HTML 模式命名一致）。"""
    pid_v = p.get("id")
    if pid_v is None:
        return None
    url = p.get("file_url") or p.get("sample_url")
    return {"id": f"p{pid_v}", "dl": url, "page": None}


def fetch_api_page_single(session, tags, pid):
    """抓一页 API 数据，返回 [post,...]；支持单页模式（--page 用）。"""
    return fetch_api_page(session, tags, pid)


def api_collect_tasks(tags, limit, adult_flag, threads=8, proxy=None, page=None):
    """API 多线程翻页收集。offset=pid*limit。返回 [task,...]；失败抛 ApiError。

    page 参数（v5）：若指定则只收集该页（从 1 开始，pid = page - 1）。
    """
    if page is not None:
        # 单页模式：只请求指定页
        pid = page - 1  # page=1 → pid=0
        print(f"API mode collect (--page={page}, single page {API_PAGE_SIZE} items) ...")
        session = get_session(adult_flag, proxy)
        posts = fetch_api_page(session, tags, pid)
        tasks = []
        for p in posts:
            t = api_post_to_task(p)
            if t and t["dl"]:
                tasks.append(t)
        if limit is not None:
            tasks = tasks[:limit]
        return tasks

    pages = {}                       # pid -> [post, ...]
    page_workers = max(1, min(threads, 4))   # API 单页量大(100)，并发适度防 abuse
    pid = 0
    done = False
    print(f"API mode collect ({API_PAGE_SIZE} per page, {page_workers} concurrent) ...")

    while not done:
        pids = [pid + i for i in range(page_workers)]
        results = {}
        with ThreadPoolExecutor(page_workers) as ex:
            futs = {ex.submit(fetch_api_page, get_session(adult_flag, proxy), tags, p): p
                    for p in pids}
            for f in as_completed(futs):
                p = futs[f]
                try:
                    results[p] = f.result()
                except ApiError as e:
                    if p == 0:
                        raise                       # 首屏失败 → 交给上层决定回退
                    print(f"  [WARN] API page pid={p} failed: {e} (truncated at this page)")
                    results[p] = "ERR"

        empty_seen = False
        for p in sorted(results):
            posts = results[p]
            if empty_seen:
                continue
            if posts == "ERR":
                empty_seen = True          # 中段失败当截断
                continue
            if not posts:
                empty_seen = True          # 空页 = 到底
                continue
            pages[p] = posts

        count = sum(len(v) for v in pages.values())
        if empty_seen:
            print(f"  Last page / truncated. Collected {count} items.")
            done = True
        elif limit is not None and count >= limit:
            print(f"  Reached limit {limit}, stop collecting (API mode).")
            done = True
        elif pid + page_workers > 5000:            # 5e5 帖不可能，防 abuse 保护
            print("  pid abnormal, force stop (API mode).")
            done = True
        else:
            pid += page_workers
            print(f"  Collected {count} items (flipping to pid={pid}) ...")

    tasks = []
    for p in sorted(pages):
        for post in pages[p]:
            t = api_post_to_task(post)
            if t and t["dl"]:               # 无任何直链的记录丢弃（deleted/仅元数据）
                tasks.append(t)
            if limit is not None and len(tasks) >= limit:
                return tasks[:limit]
    return tasks


# ============================================================
# API 批量按 id 获取（Artist 模式复用）
# ============================================================

def fetch_api_posts_by_ids(session, post_ids, adult_flag, proxy=None):
    """通过 API 批量获取指定 id 的帖子（id: 语法）。
    返回 dict: {post_id_str: post_dict, ...}
    """
    if not post_ids:
        return {}
    # Gelbooru API 支持 id:123,456 语法
    id_tag = "id:" + ",".join(str(i) for i in post_ids)
    try:
        posts = fetch_api_page(session, id_tag, 0)
    except ApiError:
        return {}
    result = {}
    for p in posts:
        pid_v = p.get("id")
        if pid_v is not None:
            result[str(pid_v)] = p
    return result


# ============================================================
# Artist 模式（v5 新增）
# ============================================================

def check_post_pools(session, post_id, proxy=None):
    """检查一个帖子属于哪些 pool。

    请求 post-pool-list 页面，解析 pool 信息。
    返回 [{"pool_id": str, "pool_name": str}, ...]；
    如果帖子不在任何 pool 中返回 []。
    """
    url = f"https://bbooru.com/index.php?page=pool&s=post-pool-list&id={post_id}"
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
    except requests.RequestException:
        return []
    html = r.text

    # 没有 pool 的标志
    if "Nobody here but us chickens!" in html:
        return []

    pools = []
    # 查找 <table> 中的 pool 行：<a href="index.php?page=pool&s=show&id=N">pool_name</a>
    for m in re.finditer(r'<a\b[^>]*page=pool&s=show[^>]*>', html):
        tag = m.group(0)
        hm = re.search(r'\bhref="([^"]+)"', tag)
        if not hm:
            continue
        href = hm.group(1)
        idm = re.search(r'[?&]id=(\d+)', href)
        if not idm:
            continue
        pool_id = idm.group(1)
        # pool name 在 <a>...</a> 之间
        # 从 m.end() 或 tag 后找闭合 </a>
        rest = html[m.end():]
        namem = re.match(r'([^<]*)', rest)
        pool_name = namem.group(1).strip() if namem else f"pool_{pool_id}"
        pool_name = html_mod.unescape(pool_name)
        if pool_name:
            pools.append({"pool_id": pool_id, "pool_name": pool_name})

    return pools


def fetch_pool_page_posts(session, pool_id, adult_flag, proxy=None):
    """从 pool show 页获取该 pool 中所有帖子的 id。
    返回 [{"id": str, "page_url": str}, ...]（page_url 是详情页 URL）。
    """
    tasks = []
    seen = set()
    pid = 0
    for _guard in range(200):
        base = f"https://bbooru.com/index.php?page=pool&s=show&id={pool_id}"
        url = base if pid == 0 else f"{base}&pid={pid}"
        try:
            r = session.get(url, timeout=20)
            r.raise_for_status()
        except requests.RequestException:
            break
        html = r.text

        page_tasks = 0
        for m in re.finditer(r'<a\b[^>]*s=view[^>]*>', html):
            tag = m.group(0)
            hm = re.search(r'\bhref="([^"]+)"', tag)
            im = re.search(r'[?&]id=(\d+)', hm.group(1)) if hm else None
            if not im:
                continue
            key = im.group(1)
            if key in seen:
                continue
            seen.add(key)
            tasks.append({"id": key, "page_url": urljoin(url, html_mod.unescape(hm.group(1)))})
            page_tasks += 1

        # 找本 pool 的下一页
        next_pid = None
        for m in re.finditer(r'<a\b[^>]*>', html):
            tag = m.group(0)
            hm = re.search(r'\bhref="([^"]+)"', tag)
            if not hm:
                continue
            href = hm.group(1)
            if "page=pool&s=show" not in href or f"id={pool_id}" not in href:
                continue
            pm = re.search(r'[?&]pid=(\d+)', href)
            if not pm:
                continue
            np_ = int(pm.group(1))
            if np_ > pid and (next_pid is None or np_ < next_pid):
                next_pid = np_

        if page_tasks == 0 and next_pid is None:
            break
        if next_pid is None:
            break
        pid = next_pid

    return tasks


def artist_collect_tasks(tags, limit, adult_flag, threads=8, proxy=None,
                         skip_others=False, page=None, force_pool_check=False):
    """Artist 模式主流程。

    1. API 搜索标签获得帖子列表（带 file_url 直链）
    2. 对每个帖子并发查询 post-pool-list
    3. 按 pool 分组，pool 内尽量复用第一步的 API 数据
    4. 不属于任何 pool 的放 others/
    5. 返回 list of (task, pool_folder_name) 二元组
    """
    # 第一步：API 搜索
    print(f"Artist mode: API search tags {tags!r} ...")
    all_posts = []
    if page is not None:
        # 单页模式
        pid = page - 1
        session = get_session(adult_flag, proxy)
        posts = fetch_api_page(session, tags, pid)
        all_posts = [(p.get("id"), p) for p in posts if p.get("id") is not None and (p.get("file_url") or p.get("sample_url"))]
    else:
        # 多页收集
        pages = {}
        page_workers = max(1, min(threads, 4))
        pid = 0
        done = False
        while not done:
            pids = [pid + i for i in range(page_workers)]
            results = {}
            with ThreadPoolExecutor(page_workers) as ex:
                futs = {ex.submit(fetch_api_page, get_session(adult_flag, proxy), tags, p): p
                        for p in pids}
                for f in as_completed(futs):
                    p = futs[f]
                    try:
                        results[p] = f.result()
                    except ApiError as e:
                        print(f"  [WARN] Artist API page pid={p} failed: {e}")
                        results[p] = "ERR"

            empty_seen = False
            for p in sorted(results):
                posts = results[p]
                if empty_seen:
                    continue
                if posts == "ERR":
                    empty_seen = True
                    continue
                if not posts:
                    empty_seen = True
                    continue
                pages[p] = posts

            count = sum(len(v) for v in pages.values())
            if empty_seen:
                print(f"  Artist API last page / truncated. Collected {count} items.")
                done = True
            elif limit is not None and count >= limit:
                print(f"  Artist API reached limit {limit}, stop collecting.")
                done = True
            elif pid + page_workers > 5000:
                print("  Artist API pid abnormal, force stop.")
                done = True
            else:
                pid += page_workers
                print(f"  Artist API collected {count} items (flipping to pid={pid}) ...")

        for p in sorted(pages):
            for post in pages[p]:
                pid_v = post.get("id")
                if pid_v is not None and (post.get("file_url") or post.get("sample_url")):
                    all_posts.append((pid_v, post))
                if limit is not None and len(all_posts) >= limit:
                    all_posts = all_posts[:limit]
                    break
            if limit is not None and len(all_posts) >= limit:
                break

    if not all_posts:
        print("Artist mode: API found no posts.")
        return []

    print(f"Artist mode: API found {len(all_posts)} posts, checking post-pool-list ...")

    # 第二步：快速预检——先并发查前 10 个帖子（除非 --force-pool-check）
    # 如果前 10 个全不在任何 pool 中，大概率整个标签都没有 pool，跳过剩余查询
    post_pool_map = {}   # post_id -> {"pools": [...], "post": post_dict}
    pool_names = {}      # pool_id -> pool_name

    check_workers = max(1, min(threads, 16))

    if force_pool_check:
        # 全量查询
        print(f"  force-pool-check enabled, querying all {len(all_posts)} posts ...")
        with ThreadPoolExecutor(check_workers) as ex:
            futs = {}
            for pid_v, post in all_posts:
                sid = str(pid_v)
                post_pool_map.setdefault(sid, {"pools": None, "post": post})
                futs[ex.submit(check_post_pools, get_session(adult_flag, proxy), sid, proxy)] = sid
            for fut in as_completed(futs):
                sid = futs[fut]
                try:
                    pools = fut.result()
                except Exception:
                    pools = []
                post_pool_map[sid]["pools"] = pools
                for pp in pools:
                    pool_names[pp["pool_id"]] = pp["pool_name"]
    else:
        # 预检阶段：只查前 10 个
        quick_sample = all_posts[:10]
        pool_found_any = False
        with ThreadPoolExecutor(min(check_workers, 10)) as ex:
            futs = {}
            for pid_v, post in quick_sample:
                sid = str(pid_v)
                post_pool_map.setdefault(sid, {"pools": None, "post": post})
                futs[ex.submit(check_post_pools, get_session(adult_flag, proxy), sid, proxy)] = sid
            for fut in as_completed(futs):
                sid = futs[fut]
                try:
                    pools = fut.result()
                except Exception:
                    pools = []
                post_pool_map[sid]["pools"] = pools
                if pools:
                    pool_found_any = True
                    for pp in pools:
                        pool_names[pp["pool_id"]] = pp["pool_name"]

        if not pool_found_any:
            print(f"  First 10 posts are not in any pool, skipping remaining {len(all_posts)-10} queries.")
            print("  Use --force-pool-check to query all posts if you suspect pools exist.")
            # 所有帖子标记为无 pool，回落 others
            for pid_v, post in all_posts[10:]:
                sid = str(pid_v)
                post_pool_map.setdefault(sid, {"pools": [], "post": post})
        else:
            print(f"  Found pools, continuing to query remaining {len(all_posts)-10} posts ...")
            with ThreadPoolExecutor(check_workers) as ex:
                futs = {}
                for pid_v, post in all_posts[10:]:
                    sid = str(pid_v)
                    post_pool_map.setdefault(sid, {"pools": None, "post": post})
                    futs[ex.submit(check_post_pools, get_session(adult_flag, proxy), sid, proxy)] = sid
                for fut in as_completed(futs):
                    sid = futs[fut]
                    try:
                        pools = fut.result()
                    except Exception:
                        pools = []
                    post_pool_map[sid]["pools"] = pools
                    for pp in pools:
                        pool_names[pp["pool_id"]] = pp["pool_name"]

    print(f"  Found {len(pool_names)} pools: {', '.join(pool_names.values())}")

    # 第三步：按 pool 分组
    pool_post_ids = {}      # pool_id -> set of post_id strings
    others_ids = []         # 不属于任何 pool 的帖子 id

    for sid, info in post_pool_map.items():
        pools = info["pools"]
        if not pools:
            others_ids.append(sid)
            continue
        for pp in pools:
            pid_k = pp["pool_id"]
            pool_post_ids.setdefault(pid_k, set()).add(sid)

    # 第四步：对每个 pool，获取池内全部帖子 ID（pool show 页）
    # 并只用 API 下载
    all_tasks_with_folders = []   # [(task, folder_name), ...]

    for pool_id_str in sorted(pool_post_ids.keys(), key=lambda x: pool_names.get(x, x)):
        pool_name = pool_names.get(pool_id_str, f"pool_{pool_id_str}")
        safe_folder = sanitize_filename(pool_name)
        print(f"\n  Pool [{pool_id_str}]: {pool_name}")
        print(f"    This pool already has {len(pool_post_ids[pool_id_str])} posts from step 1.")

        # 获取 pool 全部帖子
        session = get_session(adult_flag, proxy)
        pool_all_posts = fetch_pool_page_posts(session, pool_id_str, adult_flag, proxy)
        pool_all_ids = {pp["id"] for pp in pool_all_posts}
        print(f"    Pool actually has {len(pool_all_ids)} posts total.")

        # 找出第一步已覆盖的帖子 id
        covered_ids = pool_post_ids[pool_id_str] & pool_all_ids
        missing_ids = pool_all_ids - pool_post_ids[pool_id_str]

        # 已有的直接复用 post_pool_map 的数据
        tasks_for_this_pool = []
        for sid in covered_ids:
            info = post_pool_map.get(sid)
            if info and info["post"]:
                t = api_post_to_task(info["post"])
                if t and t["dl"]:
                    tasks_for_this_pool.append(t)

        # 缺失的用 API id: 批量获取
        if missing_ids:
            print(f"    {len(missing_ids)} missing from step 1, fetch via API batch ...")
            id_posts = fetch_api_posts_by_ids(session, list(missing_ids), adult_flag, proxy)
            for sid, post in id_posts.items():
                t = api_post_to_task(post)
                if t and t["dl"]:
                    tasks_for_this_pool.append(t)

        # 对 pool show 页中的帖子顺序排序，保证一致性
        # 按 pool 页面中的顺序排列
        id_order = {pp["id"]: idx for idx, pp in enumerate(pool_all_posts)}
        tasks_for_this_pool.sort(key=lambda t: id_order.get(t["id"][1:], 999999))

        print(f"    Actually downloadable: {len(tasks_for_this_pool)} posts.")
        all_tasks_with_folders.extend((t, safe_folder) for t in tasks_for_this_pool)

    # 第五步：处理 others（不属于任何 pool 的帖子）
    if others_ids and not skip_others:
        print(f"\n  Posts not in any pool: {len(others_ids)} (placed in others/ folder)")
        for sid in others_ids:
            info = post_pool_map.get(sid)
            if info and info["post"]:
                t = api_post_to_task(info["post"])
                if t and t["dl"]:
                    all_tasks_with_folders.append((t, "others"))

    return all_tasks_with_folders


# ============================================================
# HTML 模式（保留 v3 逻辑，作为 API 不可用时的兜底）
# ============================================================

def fetch_html_page(session, tags, pid):
    """抓一页 HTML 列表，返回 [task,...]；空页返回 []"""
    params = {"page": "post", "s": "list", "tags": tags}
    if pid > 0:
        params["pid"] = pid
    r = session.get(HTML_LIST_URL, params=params, timeout=20)
    r.raise_for_status()
    return parse_html_page(r.text, r.url)


def parse_html_page(html, base_url):
    """从 HTML 列表页提取帖子任务。

    真实 DOM：div#content > div#post-list > div.image-list > span.thumb > a#p<ID>。
    按属性特征切 a 标签（与层级无关），兼容属性顺序/换行。
    """
    out = []
    for m in re.finditer(r'<a\b[^>]*>', html):
        tag = m.group(0)
        if 's=view' not in tag:
            continue
        idm = re.search(r'\bid="(p\d+)"', tag)
        hm = re.search(r'\bhref="([^"]+)"', tag)
        if not idm or not hm:
            continue
        href = hm.group(1)
        if href.startswith('javascript'):
            continue
        out.append({"id": idm.group(1), "dl": None,
                    "page": urljoin(base_url, html_mod.unescape(href))})
    return out


def html_collect_tasks(tags, limit, adult_flag, threads=8, proxy=None):
    """HTML 多线程并发翻页收集，直到遇空页或达到 limit。返回 [task,...]"""
    pages = {}               # pid -> [task,...]
    page_workers = max(1, min(threads, 6))
    pid = 0
    done = False
    print(f"HTML mode collect ({HTML_PAGE_SIZE} per page, {page_workers} concurrent) ...")

    while not done:
        pids = [pid + i * HTML_PAGE_SIZE for i in range(page_workers)]
        results = {}
        with ThreadPoolExecutor(page_workers) as ex:
            futs = {ex.submit(fetch_html_page, get_session(adult_flag, proxy), tags, p): p
                    for p in pids}
            for f in as_completed(futs):
                p = futs[f]
                try:
                    results[p] = f.result()
                except Exception as e:
                    print(f"  [WARN] List page pid={p} fetch failed: {e}")
                    results[p] = None

        empty_seen = False
        for p in sorted(results):
            links = results[p]
            if empty_seen:
                continue
            if links is None:
                continue
            if not links:
                empty_seen = True
                continue
            pages[p] = links

        count = sum(len(v) for v in pages.values())
        if empty_seen:
            print(f"  Empty page, pagination done. Collected {count} items.")
            done = True
        elif limit is not None and count >= limit:
            print(f"  Reached limit {limit}, stop collecting (HTML mode).")
            done = True
        elif pid + page_workers * HTML_PAGE_SIZE > 100000:
            print("  pid abnormal, force stop traversal (HTML mode).")
            done = True
        else:
            pid += page_workers * HTML_PAGE_SIZE
            print(f"  Collected {count} items (flipping to pid={pid}) ...")

    tasks = []
    for p in sorted(pages):
        for t in pages[p]:
            tasks.append(t)
            if limit is not None and len(tasks) >= limit:
                return tasks[:limit]
    return tasks


def parse_original_url(html, detail_url):
    """详情页 HTML 中找文本为 "Original image" 的 <a>，返回其绝对 href。"""
    for m in re.finditer(r'<a\b[^>]*>\s*Original image\s*</a>', html, re.IGNORECASE):
        seg = m.group(0)
        hm = re.search(r'\bhref="([^"]+)"', seg)
        if hm:
            return urljoin(detail_url, hm.group(1))
    return None


# ============================================================
# Pool 模式（bbooru 的 dapi 不支持 pool: 过滤 → 走 HTML show 页）
# ============================================================

def pool_show_url(pool_id, pid=0):
    """构造 pool show 页 URL（pid>0 时追加分页参数）"""
    base = f"https://bbooru.com/index.php?page=pool&s=show&id={pool_id}"
    return base if pid == 0 else f"{base}&pid={pid}"


def extract_pool_id(pool_arg):
    """从用户输入提取 pool id：支持 show 页 URL 或纯数字"""
    if pool_arg.isdigit():
        return pool_arg
    m = re.search(r'(?:[?&]id=|s=show[^"&\s]*id=)(\d+)', pool_arg)
    if m:
        return m.group(1)
    raise ValueError(f"无法从 {pool_arg!r} 解析 pool id（请给 show 页 URL 或纯数字）")


def pool_collect_tasks(pool_id, limit=None, adult_flag=True, proxy=None, pool_rev=False):
    """从 pool show 页收集帖子任务（HTML 任务：下载时进详情页取原图）。

    实测：小 pool 单页展示全部；大 pool 用 &pid= 分页，循环跟"下一页"直到没有。
    返回 [{'id':'p<id>','dl':None,'page':详情URL}, ...]
    若 pool_rev=True，反转任务顺序（编号从大到小）。
    """
    s = get_session(adult_flag, proxy)
    tasks, seen = [], set()
    pid = 0
    for _guard in range(200):                     # 防呆上限
        url = pool_show_url(pool_id, pid)
        print(f"  Reading pool page pid={pid}: {url}")
        r = s.get(url, timeout=20)
        r.raise_for_status()
        html = r.text

        page_tasks = 0
        for m in re.finditer(r'<a\b[^>]*s=view[^>]*>', html):
            tag = m.group(0)
            hm = re.search(r'\bhref="([^"]+)"', tag)
            im = re.search(r'[?&]id=(\d+)', hm.group(1)) if hm else None
            if not im:
                continue
            key = im.group(1)
            if key in seen:
                continue
            seen.add(key)
            tasks.append({"id": f"p{key}", "dl": None,
                          "page": urljoin(url, html_mod.unescape(hm.group(1)))})
            page_tasks += 1
            if limit is not None and len(tasks) >= limit:
                if pool_rev:
                    tasks.reverse()
                return tasks[:limit]

        # 找本 pool 的下一页（href 同时含 page=pool&s=show、id=<本池>、pid=）
        next_pid = None
        for m in re.finditer(r'<a\b[^>]*>', html):
            tag = m.group(0)
            hm = re.search(r'\bhref="([^"]+)"', tag)
            if not hm:
                continue
            href = hm.group(1)
            if "page=pool&s=show" not in href or f"id={pool_id}" not in href:
                continue
            pm = re.search(r'[?&]pid=(\d+)', href)
            if not pm:
                continue
            np_ = int(pm.group(1))
            if np_ > pid and (next_pid is None or np_ < next_pid):
                next_pid = np_

        if page_tasks == 0 and next_pid is None:
            print("  No new posts and no next page, pool collection done.")
            break
        if next_pid is None:
            print(f"  Collected {len(tasks)} items, no next page.")
            break
        pid = next_pid

    if pool_rev:
        tasks.reverse()
    return tasks


# ============================================================
# 下载（两种模式共用）
# ============================================================

def download_one(task, download_dir, adult_flag, retries, proxy=None):
    """处理单个任务：API 任务直接用直链；HTML 任务先抓详情页取原图。
    返回 (item_id, ok/fail/skip, 说明)"""
    item_id = task["id"]
    s = get_session(adult_flag, proxy)
    last_err = None

    for attempt in range(1 + retries):
        try:
            url = task["dl"]
            if not url:                       # HTML 任务：进详情页找原图
                r = s.get(task["page"], timeout=20)
                r.raise_for_status()
                url = parse_original_url(r.text, task["page"])
                if not url:
                    hint = ("；可能成人内容被隐藏，试试 --adult y" if not adult_flag else "")
                    raise RuntimeError(f"未找到 '{ORIGINAL_TEXT}' 链接{hint}")

            ext = get_extension_from_url(url)
            filename = sanitize_filename(item_id) + ext
            save_path = os.path.join(download_dir, filename)

            if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                return (item_id, 'skip', filename)

            with s.get(url, timeout=120, stream=True) as img:
                img.raise_for_status()
                tmp = save_path + '.part'
                with open(tmp, 'wb') as f:
                    for chunk in img.iter_content(1 << 16):
                        f.write(chunk)
                os.replace(tmp, save_path)
            return (item_id, 'ok', filename)

        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(0.4 * (attempt + 1))

    return (item_id, 'fail', str(last_err))


def download_images(tasks, download_dir, adult_flag, threads=8, retries=2, proxy=None):
    """多线程并发下载（普通模式）"""
    ensure_dir(download_dir)
    total = len(tasks)
    print(f"\nStarting download, {total} tasks, {threads} concurrent. Save dir: {download_dir}")

    ok = fail = skip = 0
    done_count = 0
    workers = max(1, min(threads, 32))

    with ThreadPoolExecutor(workers) as ex:
        futs = [ex.submit(download_one, t, download_dir, adult_flag, retries, proxy)
                for t in tasks]
        for fut in as_completed(futs):
            done_count += 1
            item_id, status, info = fut.result()
            if status == 'ok':
                ok += 1
                print(f"[{done_count}/{total}] [OK] {info}")
            elif status == 'skip':
                skip += 1
                print(f"[{done_count}/{total}] [Skip] {info}")
            else:
                fail += 1
                print(f"[{done_count}/{total}] [FAIL] {item_id} failed: {info}")

    print("\n" + "=" * 50)
    print(f"Download complete: {ok} ok, {skip} skipped, {fail} failed")
    print(f"Images saved in: {os.path.abspath(download_dir)}")
    return ok, fail


def download_images_with_folders(tasks_with_folders, base_dir, adult_flag,
                                  threads=8, retries=2, proxy=None):
    """按文件夹分组下载（Artist 模式用）。
    tasks_with_folders: [(task, folder_name), ...]
    """
    # 先按文件夹分组
    folder_tasks = {}
    for task, folder in tasks_with_folders:
        folder_tasks.setdefault(folder, []).append(task)

    total = len(tasks_with_folders)
    print(f"\nStarting download (Artist mode), {total} tasks, "
          f"in {len(folder_tasks)} folders. {threads} concurrent.")
    print(f"Root dir: {base_dir}")

    ok = fail = skip = 0
    done_count = 0
    workers = max(1, min(threads, 32))

    # 将所有任务扁平化处理，但分别记录文件夹
    flat_items = []
    for folder, tasks in folder_tasks.items():
        folder_dir = os.path.join(base_dir, folder)
        ensure_dir(folder_dir)
        for t in tasks:
            flat_items.append((t, folder_dir))

    with ThreadPoolExecutor(workers) as ex:
        def _wrap(t_d):
            t, d = t_d
            return download_one(t, d, adult_flag, retries, proxy)

        futs = [ex.submit(_wrap, item) for item in flat_items]
        for fut in as_completed(futs):
            done_count += 1
            item_id, status, info = fut.result()
            if status == 'ok':
                ok += 1
                print(f"[{done_count}/{total}] [OK] {info}")
            elif status == 'skip':
                skip += 1
                print(f"[{done_count}/{total}] [Skip] {info}")
            else:
                fail += 1
                print(f"[{done_count}/{total}] [FAIL] {item_id} failed: {info}")

    print("\n" + "=" * 50)
    print(f"Download complete: {ok} ok, {skip} skipped, {fail} failed")
    print(f"Images saved in: {os.path.abspath(base_dir)}")
    return ok, fail


def main():
    args = parse_args()
    if args.threads < 1:
        print("--threads must be >= 1")
        return

    # ---- 参数校验 ----
    if args.page is not None and args.pool:
        print("--page is only for --tags mode, cannot be used with --pool.")
        return
    if args.pool_rev and not args.pool:
        print("--pool-rev is only for --pool mode.")
        return
    if args.mode == "artist" and not args.tags:
        print("--mode artist requires --tags.")
        return
    if args.mode == "artist" and args.pool:
        print("--mode artist cannot be used with --pool.")
        return
    if args.skip_others and args.mode != "artist":
        print("--skip-others is only for --mode artist.")
        return
    if args.page is not None and args.page < 1:
        print("--page must be >= 1.")
        return

    # ---- 目标校验：--tags 与 --pool 二选一 ----
    if args.tags and args.pool:
        print("--tags and --pool are mutually exclusive, please provide only one.")
        return
    if not args.tags and not args.pool:
        print("Need --tags <tag> or --pool <pool id/URL>. Use --help for usage.")
        return
    pool_mode = bool(args.pool)
    if pool_mode:
        try:
            pool_id = extract_pool_id(args.pool)
        except ValueError as e:
            print(f"Argument error: {e}")
            return
        folder_name = sanitize_filename(args.name if args.name else f"pool_{pool_id}")
    else:
        tags = args.tags.strip()
        folder_name = sanitize_filename(args.name if args.name else tags)

    adult_flag = args.adult == 'y'
    download_dir = os.path.join(args.output_dir, folder_name)

    # 代理
    if args.proxy is None:
        _p = common.detect_proxy()
        print(f"Proxy: auto detect ({'enabled: ' + _p if _p else 'not set, direct'})")
    elif args.proxy.lower() in ("off", "direct", "none"):
        _p = ""
        print("Proxy: direct (--proxy off)")
    else:
        _p = common.normalize_proxy(args.proxy)
        print(f"Proxy: {_p}")

    # --limit 家族语义：默认 120 / inf / 数字
    limit = parse_limit(args.limit, 10 ** 9)
    if limit is None:
        return

    target = f"pool {pool_id}" if pool_mode else f"tags {tags}"
    mode_str = "pool" if pool_mode else args.mode
    extra_info = ""
    if args.page is not None:
        extra_info += f" | --page={args.page}"
    if args.pool_rev:
        extra_info += " | --pool-rev"
    if args.skip_others:
        extra_info += " | --skip-others"
    print(f"Target: {target} | Mode: {mode_str} | Adult: {'on' if adult_flag else 'off'} | "
          f"Threads: {args.threads}{extra_info}")
    print(f"Output dir: {os.path.abspath(download_dir)}")

    # ---- 收集 ----
    if pool_mode:
        # pool 走 HTML show 页（dapi 不支持 pool 过滤）
        tasks = pool_collect_tasks(pool_id, limit, adult_flag, _p, pool_rev=args.pool_rev)
    elif args.mode == "artist":
        # Artist 模式
        print("Artist mode starting ...")
        atf = artist_collect_tasks(
            tags, limit, adult_flag, args.threads, _p,
            skip_others=args.skip_others, page=args.page,
            force_pool_check=args.force_pool_check)
        if not atf:
            print("No Artist tasks collected, exiting.")
            return
        print(f"Artist mode collected {len(atf)} tasks.")
        if args.dry_run:
            print("(--dry-run, showing first 5 only)")
            for t, fld in atf[:5]:
                if t["dl"]:
                    print(f"  [{fld}] {t['id']}  {t['dl']}")
                else:
                    print(f"  [{fld}] {t['id']}  {t['page']}")
            return
        download_images_with_folders(
            atf, download_dir, adult_flag, args.threads, args.retry, _p)
        return
    else:
        # ---- tags 收集（auto: API 失败自动回退 HTML）----
        tasks = None
        if args.mode in ("auto", "api"):
            try:
                tasks = api_collect_tasks(tags, limit, adult_flag, args.threads, _p,
                                          page=args.page)
            except ApiError as e:
                print(f"[WARN] API mode unavailable: {e}")
                if args.mode == "api":
                    print("--mode api failed, use --mode html or default auto (auto-fallback) instead.")
                    return
                print("auto mode: fallback to HTML mode ...")
                args.mode = "html"
            except Exception as e:
                print(f"[WARN] API mode exception: {e}")
                if args.mode == "api":
                    raise
                print("auto mode: fallback to HTML mode ...")
                args.mode = "html"
            # --page 只在 API 模式下生效，回退到 HTML 时不支持 --page
            if args.page is not None and args.mode == "html" and tasks is None:
                print("--page only works in API mode, not supported in HTML fallback.")
                return
        if tasks is None:
            tasks = html_collect_tasks(tags, limit, adult_flag, args.threads, _p)

    if not tasks:
        print("No tasks collected, exiting.")
        return

    print(f"Collected {len(tasks)} tasks ({mode_str} mode).")
    if args.dry_run:
        print("(--dry-run, showing first 5 only)")
        for t in tasks[:5]:
            if t["dl"]:
                print(f"  {t['id']}  {t['dl']}")
            else:
                print(f"  {t['id']}  {t['page']}")
        return

    download_images(tasks, download_dir, adult_flag, args.threads, args.retry, _p)


if __name__ == "__main__":
    main()
