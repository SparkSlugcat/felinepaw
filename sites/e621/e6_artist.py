#!/usr/bin/env python3
"""
e621/e926 艺术家作品智能分组爬虫（最终版）
- 下载指定艺术家的所有作品，按所属 Pool 分组：
    - 每个 Pool 单独一个文件夹（完整下载池内全部作品）
    - 不属于任何 Pool 的作品放入 others 文件夹
- 可通过 --skip-others 跳过非池作品
- 输出结构：
    艺术家标签/
        Pool名称1/
        Pool名称2/
        ...
        others/          (如果不跳过)
- 支持断点续传、登录认证（环境变量 E621_USER / E621_KEY）、内容不过滤
"""

import os
import sys
import json
import time
import argparse
import re
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "DNT": "1",
    "Connection": "keep-alive",
    "Referer": "https://e621.net/",
}
API_BASE = "https://e621.net"          # 可改为 https://e926.net
POSTS_PER_REQUEST = 320                # API 单次最大帖子数
REQUEST_DELAY = 1.0                    # API 请求间隔（秒）
MAX_RETRIES = 3
DOWNLOAD_WORKERS = 4                   # 并发下载线程数

# ===== 登录凭据（环境变量，留空=游客） =====
API_USER = os.environ.get("E621_USER", "")    # e621/e926 用户名
API_KEY = os.environ.get("E621_KEY", "")      # 完整 API Key
# ===================================================

# --------------------------

def create_session(proxy=None):
    """创建带重试和认证的会话"""
    session = common.create_session(proxy, HEADERS)
    if API_USER and API_KEY:
        session.auth = (API_USER, API_KEY)
        print("已使用认证信息登录")
    else:
        print("以游客身份访问（部分内容可能受限）")
    return session


session = create_session()


def sanitize_filename(name: str) -> str:
    """去除非法文件名字符，保证文件夹名合法"""
    name = re.sub(r'[\\/*?:"<>|]', '_', name)      # Windows 非法字符
    name = re.sub(r'[\s.]+$', '', name)            # 去除末尾空格或点
    name = name.strip()
    if not name:
        name = "untitled"
    return name


def fetch_all_post_ids(tags: str) -> list[int]:
    """获取匹配标签的所有帖子 ID（自动翻页）"""
    all_ids = []
    page = 1
    while True:
        params = {
            "tags": tags,
            "limit": POSTS_PER_REQUEST,
            "page": page,
            "filter_id": 0,
        }
        try:
            resp = session.get(f"{API_BASE}/posts.json", params=params)
            resp.raise_for_status()
            data = resp.json()
            posts = data.get("posts", [])
            if not posts:
                break
            all_ids.extend(post["id"] for post in posts)
            print(f"  第 {page} 页，获取到 {len(posts)} 个帖子（累计 {len(all_ids)}）")
            if len(posts) < POSTS_PER_REQUEST:
                break
            page += 1
            time.sleep(REQUEST_DELAY)
        except Exception as e:
            print(f"获取帖子列表失败（第 {page} 页）: {e}")
            break
    return all_ids


def fetch_posts_details_batch(post_ids: list[int]) -> list[dict]:
    """批量获取帖子详细信息（包含 pools 字段）"""
    if not post_ids:
        return []
    ids_str = ",".join(str(pid) for pid in post_ids)
    params = {
        "tags": f"id:{ids_str}",
        "limit": POSTS_PER_REQUEST,
        "filter_id": 0,
    }
    resp = session.get(f"{API_BASE}/posts.json", params=params)
    resp.raise_for_status()
    data = resp.json()
    return data.get("posts", [])


def fetch_pool_info(pool_id: int) -> dict:
    """获取单个 Pool 的完整信息（含所有 post_ids）"""
    resp = session.get(f"{API_BASE}/pools/{pool_id}.json")
    resp.raise_for_status()
    data = resp.json()
    if "pool" in data:
        return data["pool"]
    return data


def download_post(post, output_dir: Path, lock: threading.Lock) -> bool:
    """下载单个帖子，返回是否成功"""
    pid = post["id"]
    file_url = post.get("file", {}).get("url")
    ext = post.get("file", {}).get("ext", "jpg")
    if not file_url:
        # 降级到 sample
        file_url = post.get("sample", {}).get("url")
        ext = post.get("sample", {}).get("ext", ext or "jpg")
    if not file_url:
        print(f"  帖子 #{pid} 无可用 URL，跳过")
        return False

    filename = f"{pid}.{ext}"
    filepath = output_dir / filename
    if filepath.exists():
        return True   # 已存在视为成功

    try:
        with session.get(file_url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(filepath, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        os.utime(filepath, None)
        return True
    except Exception as e:
        print(f"  下载帖子 #{pid} 失败: {e}")
        if filepath.exists():
            filepath.unlink()
        return False


def download_posts_to_dir(post_ids: list[int], output_dir: Path):
    """批量下载帖子到指定目录（并发下载）"""
    output_dir.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()

    # 获取所有帖子的详细信息
    posts_details = []
    for i in range(0, len(post_ids), POSTS_PER_REQUEST):
        batch_ids = post_ids[i:i+POSTS_PER_REQUEST]
        try:
            posts_details.extend(fetch_posts_details_batch(batch_ids))
        except Exception as e:
            print(f"批量获取帖子信息失败: {e}")
        time.sleep(REQUEST_DELAY)

    if not posts_details:
        print("  没有找到帖子信息")
        return

    # 并发下载
    success_count = 0
    fail_count = 0
    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as executor:
        futures = [executor.submit(download_post, post, output_dir, lock) for post in posts_details]
        for future in as_completed(futures):
            if future.result():
                success_count += 1
            else:
                fail_count += 1

    print(f"  下载完成：成功 {success_count}，失败/跳过 {fail_count}")


def main():
    parser = argparse.ArgumentParser(description="下载艺术家作品并按 Pool 分组")
    parser.add_argument("--tags", required=True, help="艺术家标签，例如 artist_name")
    parser.add_argument("-o", "--output", default=None, help="输出根目录（默认为艺术家标签名）")
    parser.add_argument(
        "--skip-others",
        action="store_true",
        help="跳过下载不属于任何 Pool 的帖子（只下载池中的图片）"
    )
    args = parser.parse_args()

    artist_tag = args.tags.strip()
    print(f"艺术家标签: {artist_tag}")

    # 确定根输出目录
    if args.output:
        root_dir = Path(args.output)
    else:
        root_dir = Path(sanitize_filename(artist_tag))
    root_dir.mkdir(parents=True, exist_ok=True)

    # 1. 获取艺术家所有帖子 ID
    print("正在获取艺术家所有帖子 ID...")
    all_artist_post_ids = fetch_all_post_ids(artist_tag)
    if not all_artist_post_ids:
        print("没有找到任何帖子。")
        return
    print(f"共找到 {len(all_artist_post_ids)} 个帖子")

    # 2. 获取这些帖子的详细信息（包括 pools 字段）
    print("正在获取帖子详细信息以提取 Pool 信息...")
    artist_posts_with_pools = []
    for i in range(0, len(all_artist_post_ids), POSTS_PER_REQUEST):
        batch_ids = all_artist_post_ids[i:i+POSTS_PER_REQUEST]
        try:
            batch_posts = fetch_posts_details_batch(batch_ids)
            artist_posts_with_pools.extend(batch_posts)
        except Exception as e:
            print(f"批量获取帖子信息失败: {e}")
        time.sleep(REQUEST_DELAY)

    # 提取所有涉及的 pool IDs 和没有 pool 的帖子 ID
    pool_ids_set = set()
    posts_without_pool = []

    for post in artist_posts_with_pools:
        pools = post.get("pools", [])
        if pools:
            for pool_id in pools:          # pool_id 直接是整数
                pool_ids_set.add(pool_id)
        else:
            posts_without_pool.append(post["id"])

    print(f"发现 {len(pool_ids_set)} 个相关 Pool，{len(posts_without_pool)} 个帖子不属于任何池")

    # 3. 下载每个 Pool 的全部作品
    for pool_id in pool_ids_set:
        print(f"\n正在处理 Pool ID: {pool_id}")
        try:
            pool_info = fetch_pool_info(pool_id)
            pool_name = sanitize_filename(pool_info.get("name", f"pool_{pool_id}"))
            pool_post_ids = pool_info.get("post_ids", [])
            print(f"  Pool 名称: {pool_name}, 作品数: {len(pool_post_ids)}")
            pool_dir = root_dir / pool_name
            download_posts_to_dir(pool_post_ids, pool_dir)
        except Exception as e:
            print(f"  获取 Pool {pool_id} 失败: {e}")

    # 4. 下载不属于任何池的帖子到 others 目录
    if posts_without_pool and not args.skip_others:
        print(f"\n下载 {len(posts_without_pool)} 个无 Pool 帖子到 others 文件夹")
        others_dir = root_dir / "others"
        download_posts_to_dir(posts_without_pool, others_dir)
    elif args.skip_others:
        print(f"\n已跳过 {len(posts_without_pool)} 个无 Pool 帖子（--skip-others 生效）")

    print("\n全部完成！文件保存在:", root_dir.resolve())


if __name__ == "__main__":
    main()