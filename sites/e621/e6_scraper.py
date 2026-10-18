#!/usr/bin/env python3
"""
e621 / e926 Tags 图片爬虫
用法示例：
    python ./Spyder/scraper/e6_scraper.py --tags "aubrey_(iceink)"
    python e621_tags_scraper.py --tags "aubrey_(iceink)" -o ./aubrey_pics

按顺序下载所有匹配标签的图片，编号 1.jpg, 2.png ...
支持登录（设置环境变量 E621_USER / E621_KEY，未设置=游客）
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from urllib.parse import quote_plus

import requests

# ---- 定位并导入共享模块 common.py（felinepaw 基础库） ----
_here = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.dirname(os.path.dirname(_here)), os.path.dirname(_here), _here):
    if os.path.exists(os.path.join(_p, "common.py")):
        sys.path.insert(0, _p)
        break
import common
# i18n 词条表与 common.py 同在项目根，上面的 sys.path 已把它放好
import i18n

# ---------- 配置 ----------
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",

    "DNT": "1",                     # Do Not Track
    "Connection": "keep-alive",
    "Referer": "https://e621.net/",
}
API_BASE = os.environ.get("E621_BASE", "https://e621.net")          # 也可改为 https://e926.net
POSTS_PER_REQUEST = 320                # 单次最多获取 320 个帖子
REQUEST_DELAY = 2.0                    # 请求间隔（秒）

# ===== 登录凭据（环境变量，留空则游客访问） =====
API_USER = os.environ.get("E621_USER", "")     # e621/e926 登录用户名
API_KEY = os.environ.get("E621_KEY", "")       # 在账户设置中生成的 API Key
# =====================================
# --------------------------

def create_session(proxy=None):
    """创建带重试和认证的会话"""
    session = common.create_session(proxy, HEADERS)
    if API_USER and API_KEY:
        session.auth = (API_USER, API_KEY)
        print(i18n.t("e6_logged_in"))
    else:
        print(i18n.t("e6_guest_mode"))
    return session


session = create_session()

def fetch_all_post_ids(tags: str, limit: int = None) -> list[int]:
    all_ids = []
    page = 1
    while True:
        # 如果指定了 limit，则直接请求第一页，并设置请求的 limit 为指定数量
        request_limit = min(limit, POSTS_PER_REQUEST) if limit else POSTS_PER_REQUEST
        params = {
            "tags": tags,
            "limit": request_limit,
            "page": page,
        }
        url = f"{API_BASE}/posts.json"
        try:
            resp = session.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            posts = data.get("posts", [])
            if not posts:
                break
            for post in posts:
                all_ids.append(post["id"])
            print(i18n.t("e6_page_fetched", page=page, got=len(posts), total=len(all_ids)))

            if limit is not None:          # 指定了 limit，只取一页
                break
            if len(posts) < POSTS_PER_REQUEST:
                break
            page += 1
            time.sleep(REQUEST_DELAY)
        except requests.exceptions.JSONDecodeError:
            print(i18n.t("e6_not_json", body=resp.content[:200]))
            break
        except requests.RequestException as e:
            print(i18n.t("e6_list_failed_page", page=page, e=e))
            print(i18n.t("e6_wait_retry"))
            time.sleep(5)
            continue
    return all_ids


def fetch_posts_batch(post_ids: list[int]) -> list[dict]:
    """批量获取帖子详细信息（与 Pool 爬虫完全相同）"""
    if not post_ids:
        return []
    ids_str = ",".join(str(pid) for pid in post_ids)
    url = f"{API_BASE}/posts.json"
    params = {
        "tags": f"id:{ids_str}",
        "limit": POSTS_PER_REQUEST,
    }
    resp = session.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    return data.get("posts", [])


def get_download_url(post: dict):
    """
    从帖子数据中提取可下载的 URL 和扩展名。
    优先 file.url，其次 sample.url。
    """
    file_data = post.get("file") or {}
    url = file_data.get("url")
    ext = file_data.get("ext")
    if url:
        return url, ext

    sample_data = post.get("sample") or {}
    url = sample_data.get("url")
    if url:
        ext = sample_data.get("ext") or ext or "jpg"
        return url, ext

    return None, None


def sanitize_filename(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in (" ", ".", "_", "-")).rstrip()


def main():
    parser = argparse.ArgumentParser(description=i18n.t("e6_tags_desc"))
    parser.add_argument("--tags", required=True, help=i18n.t("e6_tags_help"))
    parser.add_argument("--limit", type=int, default=None, help=i18n.t("e6_limit_help")) ;  parser.add_argument("-o", "--output", default=None, help=i18n.t("e6_output_help_tags"))
    args = parser.parse_args()

    tags = args.tags.strip()
    print(i18n.t("e6_search_tags", tags=tags))

    # 1. 获取所有帖子 ID
    print(i18n.t("e6_id_list_fetching_paged"))
    try:
        all_ids = fetch_all_post_ids(tags, limit=args.limit)
    except Exception as e:
        print(i18n.t("e6_id_list_failed", e=e))
        sys.exit(1)

    if not all_ids:
        print(i18n.t("e6_no_posts_found"))
        return

    print(i18n.t("e6_total_found", n=len(all_ids)))

    # 确定输出目录
    if args.output:
        output_dir = Path(args.output)
    else:
        safe_tag = sanitize_filename(tags.replace(" ", "_"))
        output_dir = Path(safe_tag)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 2. 批量获取详细信息，构建可下载列表
    downloadable = []   # (post_id, url, ext)
    failed_ids = []

    print(i18n.t("e6_posts_detail_fetching"))
    for i in range(0, len(all_ids), POSTS_PER_REQUEST):
        batch_ids = all_ids[i:i + POSTS_PER_REQUEST]
        print(i18n.t("e6_batch_n", n=i//POSTS_PER_REQUEST + 1, start=i+1,
                     end=min(i+POSTS_PER_REQUEST, len(all_ids)), total=len(all_ids)))
        try:
            posts = fetch_posts_batch(batch_ids)
        except requests.RequestException as e:
            print(i18n.t("e6_batch_failed_retry", e=e))
            time.sleep(5)
            try:
                posts = fetch_posts_batch(batch_ids)
            except requests.RequestException as e2:
                print(i18n.t("e6_batch_retry_failed", e=e2))
                continue

        for post in posts:
            pid = post.get("id")
            url, ext = get_download_url(post)
            if url:
                downloadable.append((pid, url, ext or "jpg"))
            else:
                failed_ids.append(pid)
        time.sleep(REQUEST_DELAY)

    print(i18n.t("e6_downloadable_and_missing_short", ok=len(downloadable), bad=len(failed_ids)))
    if not downloadable:
        print(i18n.t("e6_no_images"))
        return

    # 3. 断点续传准备（与 Pool 爬虫相同）
    existing_max = 0
    for f in output_dir.iterdir():
        if f.is_file() and f.stem.isdigit():
            num = int(f.stem)
            if num > existing_max:
                existing_max = num
    start_index = existing_max + 1
    if existing_max > 0:
        print(i18n.t("e6_resume_from", n=existing_max, start=start_index))

    # 4. 下载
    downloaded = 0
    skipped = 0
    download_failed = []

    for idx, (pid, url, ext) in enumerate(downloadable):
        if idx < existing_max:   # 跳过已下载完成的
            continue

        target_index = start_index + (idx - existing_max)
        filename = f"{target_index}.{ext}"
        filepath = output_dir / filename

        if filepath.exists():
            print(i18n.t("e6_post_skip_plain", idx=target_index,
                         pid=pid, name=filename))
            skipped += 1
            continue

        print(i18n.t("e6_post_download_plain", idx=target_index, total=len(downloadable),
                     pid=pid, name=filename))
        try:
            with session.get(url, stream=True) as r:
                r.raise_for_status()
                with open(filepath, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            os.utime(filepath, None)
            downloaded += 1
        except requests.RequestException as e:
            print(i18n.t("e6_download_failed_indent", e=e))
            download_failed.append(pid)
            if filepath.exists():
                filepath.unlink()
        time.sleep(REQUEST_DELAY)

    # 5. 汇总
    print(i18n.t("e6_done_header"))
    print(i18n.t("e6_tags_line", tags=tags))
    print(i18n.t("e6_total_posts_tags", n=len(all_ids)))
    print(i18n.t("e6_downloaded_count", n=downloaded))
    print(i18n.t("e6_skipped_count", n=skipped))
    if download_failed:
        print(i18n.t("e6_failed_with_ids", n=len(download_failed),
                     ids=", ".join(map(str, download_failed))))
    if failed_ids:
        print(i18n.t("e6_no_url_with_ids", n=len(failed_ids),
                     ids=", ".join(map(str, failed_ids))))
    print(i18n.t("e6_saved_to", path=output_dir.resolve()))


if __name__ == "__main__":
    main()