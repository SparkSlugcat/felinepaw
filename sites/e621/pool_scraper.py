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

# ---------- 配置 ----------
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}
API_BASE = "https://e621.net"          # 可根据需要改为 https://e926.net
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
    raise ValueError(f"无法从 URL 中提取 Pool ID: {pool_url}")


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
    parser = argparse.ArgumentParser(description="下载 e621/e926 指定 Pool 中的所有图片（顺序命名）")
    parser.add_argument("pool_url", help="Pool 页面完整 URL，例如 https://e621.net/pools/12345")
    parser.add_argument("-o", "--output", default=None, help="图片保存目录（默认以 Pool 名称命名）")
    args = parser.parse_args()

    pool_url = args.pool_url.strip()
    try:
        pool_id = extract_pool_id(pool_url)
    except ValueError as e:
        print(f"错误: {e}")
        sys.exit(1)

    print(f"解析到 Pool ID: {pool_id}")

    # 1. 获取 Pool 信息
    print("正在获取 Pool 信息...")
    try:
        pool_info = get_pool_info(pool_id)
    except requests.RequestException as e:
        print(f"获取 Pool 信息失败: {e}")
        sys.exit(1)

    pool_name = pool_info.get("name", f"pool_{pool_id}")
    post_ids = pool_info.get("post_ids", [])
    if not post_ids:
        print("该 Pool 中没有作品。")
        return

    print(f"Pool 名称: {pool_name}")
    print(f"作品数量: {len(post_ids)}")

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

    print("正在获取作品详细信息...")
    total_posts = len(post_ids)
    for i in range(0, total_posts, POSTS_PER_REQUEST):
        batch_ids = post_ids[i: i + POSTS_PER_REQUEST]
        print(f"  获取批次 ({i + 1}-{min(i + POSTS_PER_REQUEST, total_posts)}/{total_posts})")
        try:
            posts = fetch_posts_batch(batch_ids)
        except requests.RequestException as e:
            print(f"  批次请求失败: {e}，等待 5 秒后重试...")
            time.sleep(5)
            try:
                posts = fetch_posts_batch(batch_ids)
            except requests.RequestException as e2:
                print(f"  重试仍失败: {e2}，跳过该批次")
                continue

        for post in posts:
            pid = post.get("id")
            url, ext = get_download_url(post)
            if url:
                downloadable.append((pid, url, ext or "jpg"))
            else:
                failed_ids.append(pid)
        time.sleep(REQUEST_DELAY)

    print(f"可下载作品: {len(downloadable)}")
    if failed_ids:
        print(f"无文件 URL 的作品: {len(failed_ids)} (ID: {', '.join(map(str, failed_ids))})")

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
        print(f"检测到已有 {existing_max} 个文件，将从序号 {start_index} 开始下载")

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
            print(f"[{target_index}/{start_index + len(downloadable) - 1}] 作品 #{pid} -> {filename} 已存在，跳过")
            skipped += 1
            continue

        print(f"[{target_index}] 下载作品 #{pid} -> {filename}")
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
            print(f"  下载失败: {e}")
            download_failed.append(pid)
            # 删除可能未完成的文件
            if filepath.exists():
                filepath.unlink()
            continue

        time.sleep(REQUEST_DELAY)

    # 5. 汇总
    print("\n===== 下载完成 =====")
    print(f"Pool: {pool_name} (ID: {pool_id})")
    print(f"总计作品: {total_posts}")
    print(f"可下载作品: {len(downloadable)}")
    print(f"成功下载: {downloaded}")
    print(f"已存在跳过: {skipped}")
    if download_failed:
        print(f"下载失败: {len(download_failed)} (ID: {', '.join(map(str, download_failed))})")
    if failed_ids:
        print(f"无可用 URL: {len(failed_ids)} (ID: {', '.join(map(str, failed_ids))})")
    print(f"文件保存至: {output_dir.resolve()}")


if __name__ == "__main__":
    main()