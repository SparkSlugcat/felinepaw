"""
从 hypnohub.net（Gelbooru/Shimmie 系）按标签批量下载原图。

站点特性：
  - 列表页: https://hypnohub.net/index.php?page=post&s=list&tags=<tag>&pid=<page>
  - 详情页: https://hypnohub.net/index.php?page=post&s=view&id=<post_id>
  - 原图: <img id="image" src="...">（从 src 属性取）
  - 每页 42 条，pid 从 0 开始
  - 需要 adult_mode=1 cookie
  - 代理: 默认 Clash (127.0.0.1:7897)，自动检测系统代理
  - 不支提供 JSON API（dapi 返回 XML 且 count=0）
  - 文件名格式: p<id>.<ext>（与 B_scraper 一致，跨脚本断点续传兼容）

"Swirling thoughts, fractured realities — welcome to HypnoHub."

用法示例：
    python H_scraper.py --tags landscape --limit 100
    python H_scraper.py --tags "cute fox" --limit inf --threads 12 -o D:/pictures
    python H_scraper.py --tags landscape --limit 500 --dry-run
    python H_scraper.py --tags hypnotic --page 2
    python H_scraper.py --tags spiral --limit inf --proxy off
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
BASE_URL = "https://hypnohub.net"
LIST_URL = f"{BASE_URL}/index.php?page=post&s=list"
VIEW_URL = f"{BASE_URL}/index.php?page=post&s=view"
HTML_PAGE_SIZE = 42     # HTML 列表每页条目数
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
# ---------------------------


def ensure_dir(path):
    """确保目录存在"""
    if not os.path.exists(path):
        os.makedirs(path)


def get_extension_from_url(url, default='.jpg'):
    """从 URL 中提取文件扩展名，若没有则返回默认值"""
    path = urlparse(url).path
    ext = os.path.splitext(path)[1]
    return ext if ext else default


# 每线程一个 requests.Session（复用 keep-alive 连接）
_local = threading.local()


def make_session(adult_flag, proxy=None):
    """新建带 UA、代理和 adult_mode cookie 的 Session"""
    s = common.create_session(proxy, {"User-Agent": UA})
    s.cookies.set('adult_mode', '1' if adult_flag else '0', domain='hypnohub.net')
    return s


def get_session(adult_flag, proxy=None):
    """线程级 Session（keep-alive 复用）"""
    s = getattr(_local, 'sess', None)
    if s is None:
        s = make_session(adult_flag, proxy)
        _local.sess = s
    return s


# ============================================================
# 列表页收集（HTML 模式）
# ============================================================

def fetch_list_page(session, tags, pid):
    """抓一页 HTML 列表，返回 [task,...]；空页返回 []"""
    params = {"page": "post", "s": "list", "tags": tags}
    if pid > 0:
        params["pid"] = pid
    r = session.get(LIST_URL, params=params, timeout=20)
    r.raise_for_status()
    return parse_list_page(r.text, r.url)


def parse_list_page(html, base_url):
    """从 HTML 列表页提取帖子任务。

    HypnoHub DOM 结构与 BBooru 相同：
    #content > span.thumb > a[href*="s=view"]
    按属性特征切 a 标签（与层级无关），兼容属性顺序/换行。
    """
    out = []
    for m in re.finditer(r'<a\b[^>]*>', html):
        tag = m.group(0)
        if 's=view' not in tag:
            continue
        idm = re.search(r'\bhref="[^"]*[?&]id=(\d+)"', tag)
        hm = re.search(r'\bhref="([^"]+)"', tag)
        if not idm or not hm:
            continue
        href = hm.group(1)
        if href.startswith('javascript'):
            continue
        post_id = idm.group(1)
        out.append({"id": f"p{post_id}", "dl": None,
                    "page": urljoin(base_url, html_mod.unescape(href)),
                    "post_id": post_id})
    return out


def collect_tasks(tags, limit, adult_flag, threads=8, proxy=None, page=None):
    """多线程并发翻页收集，直到遇空页或达到 limit。返回 [task,...]

    page 参数：若指定则只下载该单页（从 1 开始，pid = page - 1）。
    """
    if page is not None:
        # 单页模式
        pid = page - 1  # page=1 → pid=0
        print(f"Collection (--page={page}, single page {HTML_PAGE_SIZE} items) ...")
        session = get_session(adult_flag, proxy)
        tasks = fetch_list_page(session, tags, pid)
        if limit is not None:
            tasks = tasks[:limit]
        return tasks

    pages = {}               # pid -> [task,...]
    page_workers = max(1, min(threads, 6))
    pid = 0
    done = False
    print(f"Collection ({HTML_PAGE_SIZE} per page, {page_workers} concurrent) ...")

    while not done:
        pids = [pid + i * HTML_PAGE_SIZE for i in range(page_workers)]
        results = {}
        with ThreadPoolExecutor(page_workers) as ex:
            futs = {ex.submit(fetch_list_page, get_session(adult_flag, proxy), tags, p): p
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
            print(f"  Reached limit {limit}, stop collecting.")
            done = True
        elif pid + page_workers * HTML_PAGE_SIZE > 100000:
            print("  pid abnormal, force stop traversal.")
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


# ============================================================
# 详情页原图提取
# ============================================================

def parse_original_url(html, detail_url):
    """详情页 HTML 中找 <img id="image">，返回其 src 绝对 URL。

    HypnoHub 原图位置：
        <img id="image" src="https://img.hypnohub.net/.../filename.ext">
    """
    m = re.search(r'<img\b[^>]*\bid=["\']image["\'][^>]*>', html)
    if not m:
        return None
    tag = m.group(0)
    sm = re.search(r'\bsrc="([^"]+)"', tag)
    if sm:
        return urljoin(detail_url, html_mod.unescape(sm.group(1)))
    return None


# ============================================================
# 下载
# ============================================================

def download_one(task, download_dir, adult_flag, retries, proxy=None):
    """处理单个任务：先抓详情页取原图 URL，再下载。
    返回 (item_id, ok/fail/skip, 说明)"""
    item_id = task["id"]
    s = get_session(adult_flag, proxy)
    last_err = None

    for attempt in range(1 + retries):
        try:
            # 进详情页找原图
            r = s.get(task["page"], timeout=20)
            r.raise_for_status()
            url = parse_original_url(r.text, task["page"])
            if not url:
                hint = ("; adult content may be hidden, try --adult y" if not adult_flag else "")
                raise RuntimeError(f"No image found (cannot find <img id=\"image\"> in detail page){hint}")

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


# ============================================================
# 参数解析与主入口
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="从 hypnohub.net 按标签批量下载原图（HTML only，不支持 JSON API）")
    parser.add_argument("--tags", required=True,
                        help="标签，多个用空格分开，如 'cute fox' 或 landscape")
    parser.add_argument("--limit", default=None,
                        help="下载数量: 正整数 或 inf(全部)；不填默认只下载前 120 个")
    parser.add_argument("--adult", choices=['y', 'n'], default='y',
                        help="是否包含成人内容（y=是，n=否），默认 y。n 时原图会被站点隐藏")
    parser.add_argument("--name", default=None,
                        help="自定义下载文件夹名称，默认与 --tags 相同")
    parser.add_argument("-o", "--o", "--output", dest="output_dir", default='.',
                        help="输出根目录，默认为当前目录")
    parser.add_argument("--threads", type=int, default=8,
                        help="并发线程数（翻页+下载），默认 8")
    parser.add_argument("--retry", type=int, default=2,
                        help="单个任务失败重试次数，默认 2")
    parser.add_argument("--proxy", default=None,
                        help="代理: 留空=自动检测, off=直连, 或 http://127.0.0.1:7897")
    parser.add_argument("--dry-run", action="store_true",
                        help="只收集列表，不下载（用于测试翻页）")
    parser.add_argument("--page", type=int, default=None,
                        help="指定只下载某一页（从 1 开始）")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.threads < 1:
        print("--threads must be >= 1")
        return
    if args.page is not None and args.page < 1:
        print("--page must be >= 1.")
        return

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

    # --limit
    limit = parse_limit(args.limit, 10 ** 9)
    if limit is None:
        return

    extra = f" | --page={args.page}" if args.page is not None else ""
    print(f"Target: tags {tags} | Adult: {'on' if adult_flag else 'off'} | "
          f"Threads: {args.threads}{extra}")
    print(f"Output dir: {os.path.abspath(download_dir)}")

    # 收集
    tasks = collect_tasks(tags, limit, adult_flag, args.threads, _p, page=args.page)
    if not tasks:
        print("No tasks collected, exiting.")
        return

    print(f"Collected {len(tasks)} tasks.")
    if args.dry_run:
        print("(--dry-run, showing first 5 only)")
        for t in tasks[:5]:
            print(f"  {t['id']}  {t['page']}")
        return

    download_images(tasks, download_dir, adult_flag, args.threads, args.retry, _p)


if __name__ == "__main__":
    main()
