#!/usr/bin/env python3
"""
e621 / e926 Pool 爬虫（改进版）
- 图片按作品顺序重命名为 1.jpg, 2.png ...
- 原图不可用时自动下载 sample
- 支持断点续传
- 需要登录时，请设置环境变量 E621_USER / E621_KEY（未设置=游客）
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from urllib.parse import urlparse

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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}
API_BASE = os.environ.get("E621_BASE", "https://e621.net")          # 可根据需要改为 https://e926.net
REQUEST_DELAY = 1.0                    # 请求间隔（秒）
POSTS_PER_REQUEST = 320                # 单次最多获取作品数
MAX_RETRIES = 3
# --------------------------


def create_session(proxy=None):
    """创建一个带重试机制的 requests 会话"""
    session = common.create_session(proxy, HEADERS)
    user = os.environ.get("E621_USER", "")
    key = os.environ.get("E621_KEY", "")
    if user and key:
        session.auth = (user, key)
    return session


session = create_session()


def extract_pool_id(pool_url: str) -> str:
    """从 Pool 页面 URL 中提取 Pool ID"""
    path = urlparse(pool_url).path.rstrip("/")
    parts = path.split("/")
    if "pools" in parts:
        idx = parts.index("pools")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    raise ValueError(i18n.t("e6_err_pool_id", url=pool_url))


def get_pool_info(pool_id: str) -> dict:
    """获取 Pool 的详细信息（含 post_ids）"""
    url = f"{API_BASE}/pools/{pool_id}.json"
    resp = session.get(url)
    resp.raise_for_status()
    data = resp.json()
    if "pool" in data:
        return data["pool"]
    return data


def fetch_posts_batch(post_ids: list[int]) -> list[dict]:
    """批量获取作品详细信息"""
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
    从作品数据中提取可下载的 URL 和对应的扩展名。
    优先返回 (file.url, file.ext)，若不存在则返回 (sample.url, sample.ext)。
    如果两者都没有，返回 (None, None)。
    """
    file_data = post.get("file") or {}
    url = file_data.get("url")
    ext = file_data.get("ext")
    if url:
        return url, ext

    sample_data = post.get("sample") or {}
    url = sample_data.get("url")
    if url:
        # sample 通常也有 ext，如果没有就用 file 的 ext
        ext = sample_data.get("ext") or ext or "jpg"
        return url, ext

    return None, None


def sanitize_filename(name: str) -> str:
    """去除文件名中的非法字符"""
    return "".join(c for c in name if c.isalnum() or c in (" ", ".", "_", "-")).rstrip()


def main():
    parser = argparse.ArgumentParser(description=i18n.t("e6_seq_desc"))
    parser.add_argument("pool_url", help=i18n.t("e6_pool_url_help"))
    parser.add_argument("-o", "--output", default=None, help=i18n.t("e6_output_help_pool"))
    args = parser.parse_args()

    pool_url = args.pool_url.strip()
    try:
        pool_id = extract_pool_id(pool_url)
    except ValueError as e:
        print(i18n.t("e6_err_prefix", e=e))
        sys.exit(1)

    print(i18n.t("e6_pool_id_parsed", id=pool_id))

    # 1. 获取 Pool 信息
    print(i18n.t("e6_pool_info_fetching"))
    try:
        pool_info = get_pool_info(pool_id)
    except requests.RequestException as e:
        print(i18n.t("e6_pool_info_failed", e=e))
        sys.exit(1)

    pool_name = pool_info.get("name", f"pool_{pool_id}")
    post_ids = pool_info.get("post_ids", [])
    if not post_ids:
        print(i18n.t("e6_pool_empty"))
        return

    print(i18n.t("e6_pool_name", name=pool_name))
    print(i18n.t("e6_post_count", n=len(post_ids)))

    # 确定输出目录
    if args.output:
        output_dir = Path(args.output)
    else:
        safe_name = sanitize_filename(pool_name)
        output_dir = Path(safe_name)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 2. 分批次获取所有作品的详细信息，并构建可下载列表
    downloadable = []   # 元素: (post_id, url, ext)
    failed_ids = []     # 无任何可用 URL 的作品 ID

    print(i18n.t("e6_posts_detail_fetching"))
    total_posts = len(post_ids)
    for i in range(0, total_posts, POSTS_PER_REQUEST):
        batch_ids = post_ids[i: i + POSTS_PER_REQUEST]
        print(i18n.t("e6_batch_progress_indent", start=i + 1,
                     end=min(i + POSTS_PER_REQUEST, total_posts), total=total_posts))
        try:
            posts = fetch_posts_batch(batch_ids)
        except requests.RequestException as e:
            print(i18n.t("e6_batch_failed_retry_indent", e=e))
            time.sleep(5)
            try:
                posts = fetch_posts_batch(batch_ids)
            except requests.RequestException as e2:
                print(i18n.t("e6_batch_retry_failed_indent", e=e2))
                continue

        for post in posts:
            pid = post.get("id")
            url, ext = get_download_url(post)
            if url:
                downloadable.append((pid, url, ext or "jpg"))
            else:
                failed_ids.append(pid)
        time.sleep(REQUEST_DELAY)

    print(i18n.t("e6_downloadable_count", n=len(downloadable)))
    if failed_ids:
        print(i18n.t("e6_no_url_posts", n=len(failed_ids),
                     ids=", ".join(map(str, failed_ids))))

    # 3. 确定起始序号（断点续传）
    # 扫描输出目录中已有的 "数字.扩展名" 文件，找出最大序号
    existing_max = 0
    for f in output_dir.iterdir():
        if f.is_file() and f.stem.isdigit():
            num = int(f.stem)
            if num > existing_max:
                existing_max = num
    start_index = existing_max + 1
    if existing_max > 0:
        print(i18n.t("e6_resume_seq", n=existing_max, start=start_index))

    # 4. 顺序下载
    downloaded = 0
    skipped = 0
    download_failed = []

    for idx in range(len(downloadable)):
        target_index = start_index + idx        # 绝对序号
        pid, url, ext = downloadable[idx]
        filename = f"{target_index}.{ext}"
        filepath = output_dir / filename

        if filepath.exists():
            print(i18n.t("e6_post_skip_seq", idx=target_index,
                         last=start_index + len(downloadable) - 1,
                         pid=pid, name=filename))
            skipped += 1
            continue

        print(i18n.t("e6_post_download_single", idx=target_index, pid=pid, name=filename))
        try:
            with session.get(url, stream=True) as r:
                r.raise_for_status()
                with open(filepath, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            # 设置文件修改时间（可选）
            os.utime(filepath, None)
            downloaded += 1
        except requests.RequestException as e:
            print(i18n.t("e6_download_failed_indent", e=e))
            download_failed.append(pid)
            # 删除可能未完成的文件
            if filepath.exists():
                filepath.unlink()
            continue

        time.sleep(REQUEST_DELAY)

    # 5. 汇总
    print(i18n.t("e6_done_header"))
    print(i18n.t("e6_pool_id_line", name=pool_name, id=pool_id))
    print(i18n.t("e6_total_posts", n=total_posts))
    print(i18n.t("e6_downloadable_count", n=len(downloadable)))
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