"""
从 bbooru.com（Gelbooru 系）按标签批量下载原图。

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
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")

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
    parser.add_argument("--mode", choices=["auto", "api", "html"], default="auto",
                        help="下载引擎（仅 tags 模式）: auto=API优先失败自动回退HTML(默认), api=强制API, html=强制HTML")
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
    return parser.parse_args()


def make_session(adult_flag, proxy=None):
    """新建带 UA、代理和 adult_mode cookie 的 Session"""
    s = common.create_session(proxy, {"User-Agent": UA})
    # adult_mode=1 显示成人内容；=0 只显示 safe
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
    pid = p.get("id")
    if pid is None:
        return None
    url = p.get("file_url") or p.get("sample_url")
    return {"id": f"p{pid}", "dl": url, "page": None}


def api_collect_tasks(tags, limit, adult_flag, threads=8, proxy=None):
    """API 多线程翻页收集。offset=pid*limit。返回 [task,...]；失败抛 ApiError。"""
    pages = {}                       # pid -> [post, ...]
    page_workers = max(1, min(threads, 4))   # API 单页量大(100)，并发适度防 abuse
    pid = 0
    done = False
    print(f"API 模式收集（每页 {API_PAGE_SIZE} 条，并发 {page_workers}）……")

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
                    print(f"  [WARN] API 页 pid={p} 失败：{e}（截断到该页为止）")
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
            print(f"  到尾页/截断。已收集 {count} 条。")
            done = True
        elif limit is not None and count >= limit:
            print(f"  已达到限制 {limit}，停止收集。")
            done = True
        elif pid + page_workers > 5000:            # 5e5 帖不可能，防 abuse 保护
            print("  pid 异常，强制停止。")
            done = True
        else:
            pid += page_workers
            print(f"  已收集 {count} 条（翻到 pid={pid}）……")

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
    print(f"HTML 模式收集（每页 {HTML_PAGE_SIZE} 条，并发 {page_workers}）……")

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
                    print(f"  [WARN] 列表页 pid={p} 抓取失败：{e}")
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
            print(f"  遇到空页，翻页结束。当前收集 {count} 条。")
            done = True
        elif limit is not None and count >= limit:
            print(f"  已达到限制 {limit}，停止收集。")
            done = True
        elif pid + page_workers * HTML_PAGE_SIZE > 100000:
            print("  pid 异常，强制停止遍历。")
            done = True
        else:
            pid += page_workers * HTML_PAGE_SIZE
            print(f"  已收集 {count} 条（翻到 pid={pid}）……")

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


def pool_collect_tasks(pool_id, limit=None, adult_flag=True, proxy=None):
    """从 pool show 页收集帖子任务（HTML 任务：下载时进详情页取原图）。

    实测：小 pool 单页展示全部；大 pool 用 &pid= 分页，循环跟"下一页"直到没有。
    返回 [{'id':'p<id>','dl':None,'page':详情URL}, ...]
    """
    s = get_session(adult_flag, proxy)
    tasks, seen = [], set()
    pid = 0
    for _guard in range(200):                     # 防呆上限
        url = pool_show_url(pool_id, pid)
        print(f"  读取 pool 页 pid={pid}：{url}")
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
            print("  本页无新帖也无下一页，pool 收集结束。")
            break
        if next_pid is None:
            print(f"  已收集 {len(tasks)} 条，没有下一页。")
            break
        pid = next_pid

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
    """多线程并发下载"""
    ensure_dir(download_dir)
    total = len(tasks)
    print(f"\n开始下载，共 {total} 个任务，并发 {threads}。保存目录：{download_dir}")

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
                print(f"[{done_count}/{total}] [跳过] {info}")
            else:
                fail += 1
                print(f"[{done_count}/{total}] [FAIL] {item_id} 失败：{info}")

    print("\n" + "=" * 50)
    print(f"下载完成：成功 {ok}，已跳过 {skip}，失败 {fail}")
    print(f"图片保存在：{os.path.abspath(download_dir)}")
    return ok, fail


def main():
    args = parse_args()
    if args.threads < 1:
        print("--threads 必须 >= 1")
        return

    # ---- 目标校验：--tags 与 --pool 二选一 ----
    if args.tags and args.pool:
        print("--tags 与 --pool 只能二选一，请勿同时给出。")
        return
    if not args.tags and not args.pool:
        print("需要 --tags <标签> 或 --pool <pool id/URL>。用 --help 查看用法。")
        return
    pool_mode = bool(args.pool)
    if pool_mode:
        try:
            pool_id = extract_pool_id(args.pool)
        except ValueError as e:
            print(f"参数错误：{e}")
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
        print(f"代理：自动检测（{'启用: ' + _p if _p else '未启用，直连'}）")
    elif args.proxy.lower() in ("off", "direct", "none"):
        _p = ""
        print("代理：直连（--proxy off）")
    else:
        _p = common.normalize_proxy(args.proxy)
        print(f"代理：{_p}")

    # --limit 家族语义：默认 120 / inf / 数字
    limit = parse_limit(args.limit, 10 ** 9)
    if limit is None:
        return

    target = f"pool {pool_id}" if pool_mode else f"标签 {tags}"
    mode_str = "pool" if pool_mode else args.mode
    print(f"目标：{target} | 模式：{mode_str} | 成人内容：{'开' if adult_flag else '关'} | "
          f"线程：{args.threads}")
    print(f"输出目录：{os.path.abspath(download_dir)}")

    # ---- 收集 ----
    if pool_mode:
        # pool 走 HTML show 页（dapi 不支持 pool 过滤）
        tasks = pool_collect_tasks(pool_id, limit, adult_flag, _p)
    else:
        # ---- tags 收集（auto: API 失败自动回退 HTML）----
        tasks = None
        if args.mode in ("auto", "api"):
            try:
                tasks = api_collect_tasks(tags, limit, adult_flag, args.threads, _p)
            except ApiError as e:
                print(f"[WARN] API 模式不可用：{e}")
                if args.mode == "api":
                    print("--mode api 下 API 失败即终止。可改用 --mode html 或默认 auto（自动回退）。")
                    return
                print("auto 模式：回退到 HTML 模式……")
                args.mode = "html"
            except Exception as e:
                print(f"[WARN] API 模式异常：{e}")
                if args.mode == "api":
                    raise
                print("auto 模式：回退到 HTML 模式……")
                args.mode = "html"
        if tasks is None:
            tasks = html_collect_tasks(tags, limit, adult_flag, args.threads, _p)

    if not tasks:
        print("没有收集到任何任务，程序退出。")
        return

    print(f"共收集 {len(tasks)} 个任务（{mode_str} 模式）。")
    if args.dry_run:
        print("（--dry-run，仅展示前 5 条）")
        for t in tasks[:5]:
            if t["dl"]:
                print(f"  {t['id']}  {t['dl']}")
            else:
                print(f"  {t['id']}  {t['page']}")
        return

    download_images(tasks, download_dir, adult_flag, args.threads, args.retry, _p)


if __name__ == "__main__":
    main()
