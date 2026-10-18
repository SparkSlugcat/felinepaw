#!/usr/bin/env python3
"""
e621 / e926 Tags 图片爬虫（支持指定页码）
用法示例：
    # 下载某个标签的全部图片
    python ./Spyder/scraper/e6_taged_page_scraper.py --tags "arcanis_(hahaluckyme) order:hot"
    # 只下载第 2 页
    python ./Spyder/scraper/e6_taged_page_scraper.py --tags "arcanis_(hahaluckyme) order:hot" --page 2
    # 指定输出目录
    python ./Spyder/scrapere6_taged_page_scraper.py --tags "lya_(jarnqk)" -o ./lya_pics

支持登录（设置环境变量 E621_USER / E621_KEY，未设置=游客）
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
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
    "DNT": "1",
    "Connection": "keep-alive",
    "Referer": "https://e621.net/",
}
API_BASE = os.environ.get("E621_BASE", "https://e621.net")          # 可改为 https://e926.net
POSTS_PER_REQUEST = 320              # 单次最多获取帖子数
REQUEST_DELAY = 1.0                    # 请求间隔（秒），可适当增大

# ===== 登录凭据（环境变量，留空=游客） =====
API_USER = os.environ.get("E621_USER", "")    # 你的 e621/e926 用户名
API_KEY = os.environ.get("E621_KEY", "")      # 在账户设置中生成的 API Key
# ===================================================
# --------------------------

def create_session(proxy=None):
    """创建带重试和认证的 requests 会话"""
    session = common.create_session(proxy, HEADERS)
    if API_USER and API_KEY:
        session.auth = (API_USER, API_KEY)
        print(i18n.t("e6_logged_in"))
    else:
        print(i18n.t("e6_guest_limited_tags"))
    return session


session = create_session()


def fetch_post_ids(tags: str, page_num: int = None) -> list[int]:
    """
    获取匹配标签的帖子 ID 列表。
    page_num: 指定页码则只返回该页的 ID，否则遍历所有页。
    """
    all_ids = []
    current_page = page_num if page_num else 1

    while True:
        params = {
            "tags": tags,
            "limit": POSTS_PER_REQUEST,
            "page": current_page,
            "filter_id": 0,          # 关闭内容过滤器，确保与网页端一致
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
            print(i18n.t("e6_page_fetched", page=current_page, got=len(posts),
                         total=len(all_ids)))

            if page_num is not None:
                break   # 指定了页码，只取一页
            if len(posts) < POSTS_PER_REQUEST:
                break   # 最后一页
            current_page += 1
            time.sleep(REQUEST_DELAY)
        except requests.exceptions.JSONDecodeError:
            print(i18n.t("e6_not_json", body=resp.content[:200]))
            break
        except requests.RequestException as e:
            print(i18n.t("e6_list_failed_page", page=current_page, e=e))
            print(i18n.t("e6_wait_retry"))
            time.sleep(5)
            continue
    return all_ids


def fetch_posts_batch(post_ids: list[int]) -> list[dict]:
    """批量获取帖子详细信息（一次最多 POSTS_PER_REQUEST 个）"""
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
    优先 file.url，若不存在则尝试 sample.url。
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
    """去除文件名中的非法字符"""
    return "".join(c for c in name if c.isalnum() or c in (" ", ".", "_", "-")).rstrip()


def main():
    parser = argparse.ArgumentParser(description=i18n.t("e6_page_desc"))
    parser.add_argument("--tags", required=True, help=i18n.t("e6_page_tags_help"))
    parser.add_argument("--page", type=int, default=None, help=i18n.t("e6_page_help"))
    parser.add_argument("-o", "--output", default=None, help=i18n.t("e6_output_help_tags"))
    args = parser.parse_args()

    tags = args.tags.strip()
    print(i18n.t("e6_search_tags", tags=tags))
    if args.page:
        print(i18n.t("e6_only_page", page=args.page))
    else:
        print(i18n.t("e6_all_pages"))

    # 1. 获取帖子 ID 列表
    print(i18n.t("e6_id_list_fetching"))
    try:
        all_ids = fetch_post_ids(tags, page_num=args.page)
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

    # 2. 批量获取帖子详细信息，构建可下载列表
    downloadable = []   # (post_id, url, ext)
    failed_ids = []     # 没有可用 URL 的帖子 ID

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

    print(i18n.t("e6_downloadable_and_missing", ok=len(downloadable), bad=len(failed_ids)))
    if not downloadable:
        print(i18n.t("e6_no_images"))
        return

    # 3. 断点续传准备
    existing_max = 0
    for f in output_dir.iterdir():
        if f.is_file() and f.stem.isdigit():
            num = int(f.stem)
            if num > existing_max:
                existing_max = num
    start_index = existing_max + 1
    if existing_max > 0:
        print(i18n.t("e6_resume_from", n=existing_max, start=start_index))



    # 4. 多线程下载
    downloaded = 0
    skipped = 0
    download_failed = []
    lock = threading.Lock()  # 用于保护共享计数器

    # 构建下载任务列表（仅含真正需要下载的任务）
    tasks = []
    for idx, (pid, url, ext) in enumerate(downloadable):
        if idx < existing_max:
            continue

        target_index = start_index + (idx - existing_max)
        filename = f"{target_index}.{ext}"
        filepath = output_dir / filename

        if filepath.exists():
            print(i18n.t("e6_post_skip_tagged", idx=target_index, total=len(downloadable),
                         pid=pid, name=filename))
            with lock:
                skipped += 1
            continue

        tasks.append((pid, url, filepath, target_index))

    total_tasks = len(tasks)
    print(i18n.t("e6_task_count", n=total_tasks))

    def download_task(pid, url, filepath, target_index):
        """单个下载任务"""
        try:
            with session.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(filepath, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            os.utime(filepath, None)
            return True, pid, target_index
        except Exception as e:
            return False, pid, target_index, str(e)

    # 使用线程池并发下载，最大并发数设为 8（可根据网络调整）
    MAX_WORKERS = 2
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_task = {
            executor.submit(download_task, pid, url, path, idx): (pid, url, path, idx)
            for pid, url, path, idx in tasks
        }

        for future in as_completed(future_to_task):
            result = future.result()
            if result[0]:  # 成功
                success, pid, idx = result[0], result[1], result[2]
                with lock:
                    downloaded += 1
                print(i18n.t("e6_post_done", idx=idx, total=len(downloadable),
                             pid=pid, name=filepath.name))
            else:  # 失败
                success, pid, idx, error = result
                with lock:
                    download_failed.append(pid)
                print(i18n.t("e6_post_failed", idx=idx, total=len(downloadable),
                             pid=pid, err=error))
                # 删除可能残留的残缺文件
                if filepath.exists():
                    filepath.unlink()

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