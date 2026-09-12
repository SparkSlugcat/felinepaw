"""
R_scraper.py — 从 rule34.us (rule34.us) 按标签批量下载原图
========================================================

站点特性（自定义引擎，非标准 Gelbooru）：
  列表页:   https://rule34.us/index.php?r=posts/index&tags=<tag>
  详情页:   https://rule34.us/index.php?r=posts/view&id=<id>
  原图位置: 详情页中 <li class="character-tag"> 内文本为 "Original" 的 <a> 的 href
  翻页:     URL 参数 &page=N（从 1 开始，需探测确认）
  代理:     127.0.0.1:7897 (Clash)

用法示例：
  python R_scraper.py --tags landscape
  python R_scraper.py --tags "cute dog" --limit 50
  python R_scraper.py --tags fox --limit inf --threads 12 -o D:/pictures
  python R_scraper.py --tags cat --proxy off
  python R_scraper.py --tags cat --page 2
  python R_scraper.py --tags cat --dry-run

输出文件: p<id>.<ext>   (与 B_scraper 一致的命名格式)
"""

import os
import re
import sys
import time
import argparse
import threading
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

import html as html_mod

# Windows GBK 控制台 Unicode 兜底
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    except Exception:
        pass
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
detect_proxy = common.detect_proxy
normalize_proxy = common.normalize_proxy

# ---------- 常量 ----------
BASE_URL = "https://rule34.us"
LIST_URL = f"{BASE_URL}/index.php?r=posts/index"
DETAIL_URL = f"{BASE_URL}/index.php?r=posts/view"
ORIGINAL_TEXT = "Original"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
# -------------------------

_local = threading.local()


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def get_extension_from_url(url, default='.jpg'):
    path = urlparse(url).path
    ext = os.path.splitext(path)[1]
    return ext if ext else default


def make_session(proxy=None):
    s = common.create_session(proxy, {"User-Agent": UA})
    return s


def get_session(proxy=None):
    s = getattr(_local, 'sess', None)
    if s is None:
        s = make_session(proxy)
        _local.sess = s
    return s


# ============================================================
# 翻页探测
# ============================================================

def probe_pagination(session, tags):
    """探测列表页的翻页参数。

    在 HTML 中查找:
      - "next" / "Next" 翻页链接
      - 数字页码链接 (href 中包含 &page=N)
      - "Last" 链接

    返回 dict:
      {
        "has_pagination": bool,    # 是否有翻页机制
        "page_param": "page",      # 翻页参数名 (默认 "page")
        "first_page": 1,           # 起始页码 (默认 1)
        "example_url": str,        # 示例翻页 URL
        "last_page": int or None,  # 最后页码（如果可探测）
        "note": str or None,       # 探测过程中的提示
      }
    """
    url = f"{LIST_URL}&tags={tags}"
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        return {"has_pagination": False, "page_param": "page",
                "first_page": 1, "example_url": None, "last_page": None,
                "note": f"Failed to load list page: {e}"}

    html = r.text
    result = {
        "has_pagination": False,
        "page_param": "page",
        "first_page": 1,
        "example_url": None,
        "last_page": None,
        "note": "No pagination controls detected, will only fetch page 1."
    }

    # 1) 查找 "Next" 链接 (翻页关键标志)
    # 常见的翻页结构: <a href="...&page=N">Next</a>
    # 先找所有 <a> 标签中的翻页链接
    page_numbers = set()
    next_exists = False
    last_page_num = None

    for m in re.finditer(r'<a\b[^>]*href="([^"]*)"[^>]*>', html, re.IGNORECASE):
        href = m.group(1)
        text_after = html[m.end():]

        # 找文本 "Next" / "下一页"
        next_m = re.match(r'(?:\s*Next\s*|›|»|>\s*)</a>', text_after, re.IGNORECASE)
        # 也找完整 <a>xxx</a> 中文本含 Next
        full_m = re.match(r'([^<]*)</a>', text_after, re.IGNORECASE)
        link_text = full_m.group(1).strip() if full_m else ""

        if re.search(r'(Next|下一页|›|»)', link_text, re.IGNORECASE):
            next_exists = True

        # 提取 page 参数值
        pm = re.search(r'[?&]page=(\d+)', href)
        if pm:
            page_numbers.add(int(pm.group(1)))

    # 2) 也检查 HTML 中独立出现的数字页码链接
    for m in re.finditer(r'<a\b[^>]*href="([^"]*)"[^>]*>(\s*\d+\s*)</a>', html, re.IGNORECASE):
        href = m.group(1)
        num = int(m.group(2).strip())
        page_numbers.add(num)

    # 3) 检查分页条区域常见的 class/结构
    # 有时页码在 <div class="pagination"> 中
    pagination_blocks = re.findall(
        r'<[^>]*class="[^"]*pagination[^"]*"[^>]*>.*?</\s*(?:div|ul)',
        html, re.IGNORECASE | re.DOTALL)

    if not page_numbers and not next_exists and not pagination_blocks:
        # 可能没有翻页机制
        return result

    # 排序页码
    sorted_pages = sorted(page_numbers) if page_numbers else []
    if sorted_pages:
        result["last_page"] = sorted_pages[-1]

    # 构造示例翻页 URL
    first_page_url = f"{LIST_URL}&tags={tags}&page=2"
    result["example_url"] = first_page_url

    if next_exists:
        result["has_pagination"] = True
        if sorted_pages:
            result["note"] = (f"Pagination detected (page param: page, "
                              f"pages found: {sorted_pages[0]}-{sorted_pages[-1]})")
        else:
            result["note"] = "Pagination detected (has Next link)"
    elif sorted_pages:
        result["has_pagination"] = True
        result["note"] = (f"Pagination detected via page numbers: "
                          f"{sorted_pages[0]}-{sorted_pages[-1]}")
    else:
        result["note"] = "Pagination controls not found conclusively, will only fetch page 1."

    return result


# ============================================================
# 列表页解析
# ============================================================

def fetch_list_page(session, tags, page=1):
    """抓一页列表页，返回 [{'id': str, 'page_url': str}, ...]。

    帖子链接在：class="thumbail-container" 内的
    <a href="...r=posts/view&id=NNNNN"> 中。
    """
    url = f"{LIST_URL}&tags={tags}&page={page}" if page > 1 else f"{LIST_URL}&tags={tags}"
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  [WARN] List page {page} failed: {e}")
        return []

    html = r.text
    posts = []
    seen = set()

    # 在整个 HTML 中找 posts/view 链接
    for am in re.finditer(
            r'<a\b[^>]*href="([^"]*r=posts/view[^"]*id=(\d+)[^"]*)"[^>]*>',
            html, re.IGNORECASE):
        pid = am.group(2)
        if pid in seen:
            continue
        seen.add(pid)
        full_url = urljoin(url, html_mod.unescape(am.group(1)))
        posts.append({"id": pid, "page_url": full_url})

    return posts


# ============================================================
# 详情页解析 - 获取原图 URL
# ============================================================

def parse_original_from_detail(html, detail_url):
    """从详情页 HTML 中提取原图 URL。

    规则:
      <li class="character-tag"> 内的 <a>，其文本为 "Original" 的 href。
    示例:
      <a href="https://img2.rule34.us/images/3d/19/...png">
        <li class="character-tag" ...>Original</li>
      </a>

    注意: <a> 包裹 <li> 这种结构是反常规的，用正则匹配。
    优先匹配: <a href="..."><li class="character-tag" ...>Original</li></a>
    """
    # 方法 1: <a href="..."><li class="character-tag"...>Original</li></a>
    for m in re.finditer(
            r'<a\b[^>]*href="([^"]*)"[^>]*>\s*<li[^>]*class="character-tag"[^>]*>\s*Original\s*</li>\s*</a>',
            html, re.IGNORECASE | re.DOTALL):
        return urljoin(detail_url, m.group(1))

    # 方法 2: <li class="character-tag"> 内包含 <a>Original</a>
    for m in re.finditer(
            r'<li[^>]*class="character-tag"[^>]*>\s*<a\b[^>]*href="([^"]*)"[^>]*>\s*Original\s*</a>\s*</li>',
            html, re.IGNORECASE | re.DOTALL):
        return urljoin(detail_url, m.group(1))

    # 方法 3: 宽松匹配 - 找 <li class="character-tag"> 所在区块中的 "Original" 和 href
    for m in re.finditer(
            r'<li[^>]*class="character-tag"[^>]*>.*?Original.*?</li>',
            html, re.IGNORECASE | re.DOTALL):
        block = m.group(0)
        # 找 block 内最近的 <a href="...">
        hm = re.search(r'<a\b[^>]*href="([^"]*)"', block)
        if hm:
            return urljoin(detail_url, hm.group(1))

    return None


def fetch_detail_get_image(post_info, session):
    """进详情页抓原图 URL。返回 URL 或 None。"""
    try:
        r = session.get(post_info["page_url"], timeout=20)
        r.raise_for_status()
    except requests.RequestException:
        return None

    url = parse_original_from_detail(r.text, post_info["page_url"])
    return url


# ============================================================
# 收集任务
# ============================================================

def collect_tasks(tags, limit, proxy=None, threads=8, page=None):
    """收集下载任务。

    返回 [{'id': 'p<id>', 'dl': <原图URL>, 'page': <详情URL>}, ...]

    page 参数: 指定只下载某一页（从 1 开始）。
    否则多页翻页收集，直到遇空页或达到 limit。
    """
    session = get_session(proxy)

    if page is not None:
        # 单页模式
        print(f"Collecting page {page} only ...")
        posts = fetch_list_page(session, tags, page)
        tasks = []
        for p in posts:
            dl_url = fetch_detail_get_image(p, session)
            if dl_url:
                tasks.append({"id": f"p{p['id']}", "dl": dl_url, "page": p["page_url"]})
        if limit is not None:
            tasks = tasks[:limit]
        return tasks

    # 先探测翻页
    pagination = probe_pagination(session, tags)
    print(f"Pagination probe: {pagination['note']}")

    if not pagination["has_pagination"]:
        # 只抓第一页
        print("No pagination detected, fetching only page 1.")
        posts = fetch_list_page(session, tags, 1)
        tasks = []
        for p in posts:
            dl_url = fetch_detail_get_image(p, session)
            if dl_url:
                tasks.append({"id": f"p{p['id']}", "dl": dl_url, "page": p["page_url"]})
            if limit is not None and len(tasks) >= limit:
                return tasks[:limit]
        return tasks

    # 多页收集
    page_num = 1
    all_tasks = []
    page_workers = max(1, min(threads, 4))
    print(f"Collecting posts (multi-page, {page_workers} concurrent) ...")

    done = False
    while not done:
        # 并发抓取列表页
        page_nums = [page_num + i for i in range(page_workers)]
        list_results = {}

        with ThreadPoolExecutor(page_workers) as ex:
            futs = {ex.submit(fetch_list_page, get_session(proxy), tags, pn): pn
                    for pn in page_nums}
            for f in as_completed(futs):
                pn = futs[f]
                try:
                    list_results[pn] = f.result()
                except Exception as e:
                    print(f"  [WARN] List page {pn} failed: {e}")
                    list_results[pn] = None

        # 收集帖子
        batch_posts = []  # [(post, page_url), ...]
        empty_seen = False
        for pn in sorted(list_results):
            posts = list_results[pn]
            if posts is None:
                empty_seen = True
                continue
            if not posts:
                empty_seen = True
                continue
            for p in posts:
                batch_posts.append(p)

        if not batch_posts:
            print("  No more posts found, pagination done.")
            break

        # 并发抓取详情页取原图
        print(f"  List page {page_num}+: {len(batch_posts)} posts, fetching details ...")
        detail_workers = max(1, min(threads, 8))
        with ThreadPoolExecutor(detail_workers) as ex:
            futs2 = {ex.submit(fetch_detail_get_image, p, get_session(proxy)): p
                     for p in batch_posts}
            for f in as_completed(futs2):
                p = futs2[f]
                try:
                    dl_url = f.result()
                except Exception:
                    dl_url = None
                if dl_url:
                    all_tasks.append({"id": f"p{p['id']}", "dl": dl_url,
                                      "page": p["page_url"]})
                    if limit is not None and len(all_tasks) >= limit:
                        all_tasks = all_tasks[:limit]
                        done = True
                        break

        print(f"  Collected {len(all_tasks)} image URLs so far.")
        if done:
            break
        if empty_seen:
            print("  Reached last page or empty page, done.")
            break
        if limit is not None and len(all_tasks) >= limit:
            break
        if page_num > 5000:
            print("  Reached safety limit (5000 pages), stopping.")
            break

        page_num += page_workers

    return all_tasks


# ============================================================
# 下载
# ============================================================

def download_one(task, download_dir, retries=2, proxy=None):
    """下载一张原图。返回 (item_id, status, info)。

    状态: 'ok' / 'skip' / 'fail'
    """
    item_id = task["id"]
    url = task["dl"]
    if not url:
        return (item_id, 'fail', 'No download URL')

    s = get_session(proxy)
    last_err = None

    for attempt in range(1 + retries):
        try:
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


def download_images(tasks, download_dir, threads=8, retries=2, proxy=None):
    """多线程并发下载。"""
    ensure_dir(download_dir)
    total = len(tasks)
    print(f"\nStarting download, {total} tasks, {threads} concurrent.")
    print(f"Save dir: {download_dir}")

    ok = fail = skip = 0
    done_count = 0
    workers = max(1, min(threads, 32))

    with ThreadPoolExecutor(workers) as ex:
        futs = [ex.submit(download_one, t, download_dir, retries, proxy)
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
                print(f"[{done_count}/{total}] [FAIL] {item_id}: {info}")

    print("\n" + "=" * 50)
    print(f"Download complete: {ok} ok, {skip} skipped, {fail} failed")
    print(f"Images saved in: {os.path.abspath(download_dir)}")
    return ok, fail


# ============================================================
# CLI
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Download images from rule34.us by tags.")
    parser.add_argument("--tags", default=None, required=True,
                        help="Search tags (space-separated, e.g. 'cute dog')")
    parser.add_argument("--limit", default=None,
                        help="Download count: positive integer or 'inf' (default: 120)")
    parser.add_argument("-o", "--o", "--output", dest="output_dir", default='.',
                        help="Output root directory (default: current dir)")
    parser.add_argument("--proxy", default=None,
                        help="Proxy: empty=auto detect, off=direct, or URL like http://127.0.0.1:7897")
    parser.add_argument("--page", type=int, default=None,
                        help="Download only a specific page number")
    parser.add_argument("--threads", type=int, default=8,
                        help="Concurrent download threads (default: 8)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only collect metadata, do not download")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.threads < 1:
        print("--threads must be >= 1")
        return

    tags = args.tags.strip()
    folder_name = sanitize_filename(tags)
    download_dir = os.path.join(args.output_dir, folder_name)

    # ---- 代理设置 ----
    if args.proxy is None:
        proxy = detect_proxy()
        print(f"Proxy: auto detect ({'enabled' if proxy else 'not set, direct'})")
    elif args.proxy.lower() in ("off", "direct", "none"):
        proxy = ""
        print("Proxy: direct (--proxy off)")
    else:
        proxy = normalize_proxy(args.proxy)
        print(f"Proxy: {proxy}")

    # ---- limit 解析 ----
    limit = parse_limit(args.limit, 10 ** 9)
    if limit is None:
        return

    print(f"Tags: {tags} | Limit: {limit} | Threads: {args.threads}")
    if args.page is not None:
        print(f"Page: {args.page} (single page only)")
    print(f"Output dir: {os.path.abspath(download_dir)}")

    # ---- 收集任务 ----
    tasks = collect_tasks(tags, limit, proxy, args.threads, args.page)

    if not tasks:
        print("No tasks collected, exiting.")
        return

    print(f"Collected {len(tasks)} image URLs.")

    if args.dry_run:
        print("(--dry-run, showing first 10)")
        for t in tasks[:10]:
            print(f"  {t['id']}  {t['dl']}")
        return

    # ---- 下载 ----
    download_images(tasks, download_dir, args.threads, proxy=proxy)


if __name__ == "__main__":
    main()
