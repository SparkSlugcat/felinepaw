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

# ---------- 配置 ----------
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",

    "DNT": "1",                     # Do Not Track
    "Connection": "keep-alive",
    "Referer": "https://e621.net/",
}
API_BASE = "https://e621.net"          # 也可改为 https://e926.net
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
        print("已使用认证信息登录")
    else:
        print("以游客身份访问")
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
            print(f"  第 {page} 页，获取到 {len(posts)} 个帖子（累计 {len(all_ids)}）")

            if limit is not None:          # 指定了 limit，只取一页
                break
            if len(posts) < POSTS_PER_REQUEST:
                break
            page += 1
            time.sleep(REQUEST_DELAY)
        except requests.exceptions.JSONDecodeError:
            print(f"    响应不是 JSON，前200字节: {resp.content[:200]}")
            break
        except requests.RequestException as e:
            print(f"获取帖子列表失败（第 {page} 页）: {e}")
            print("等待 5 秒后重试...")
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
    parser = argparse.ArgumentParser(description="下载 e621/e926 指定 tags 的所有图片")
    parser.add_argument("--tags", required=True, help="搜索标签，例如 aubrey_(iceink)")
    parser.add_argument("--limit", type=int, default=None, help="只下载前 N 个帖子") ;  parser.add_argument("-o", "--output", default=None, help="图片保存目录（默认为 tags 名称）")
    args = parser.parse_args()

    tags = args.tags.strip()
    print(f"搜索标签: {tags}")

    # 1. 获取所有帖子 ID
    print("正在获取帖子 ID 列表（可能多页）...")
    try:
        all_ids = fetch_all_post_ids(tags, limit=args.limit)
    except Exception as e:
        print(f"获取 ID 列表失败: {e}")
        sys.exit(1)

    if not all_ids:
        print("没有找到匹配的帖子。")
        return

    print(f"共找到 {len(all_ids)} 个帖子")

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

    print("正在获取帖子详细信息...")
    for i in range(0, len(all_ids), POSTS_PER_REQUEST):
        batch_ids = all_ids[i:i + POSTS_PER_REQUEST]
        print(f"  批次 {i//POSTS_PER_REQUEST + 1} ({i+1}-{min(i+POSTS_PER_REQUEST, len(all_ids))}/{len(all_ids)})")
        try:
            posts = fetch_posts_batch(batch_ids)
        except requests.RequestException as e:
            print(f"批次请求失败: {e}，等待 5 秒重试...")
            time.sleep(5)
            try:
                posts = fetch_posts_batch(batch_ids)
            except requests.RequestException as e2:
                print(f"重试仍失败: {e2}，跳过该批次")
                continue

        for post in posts:
            pid = post.get("id")
            url, ext = get_download_url(post)
            if url:
                downloadable.append((pid, url, ext or "jpg"))
            else:
                failed_ids.append(pid)
        time.sleep(REQUEST_DELAY)

    print(f"可下载: {len(downloadable)}, 无URL: {len(failed_ids)}")
    if not downloadable:
        print("没有可下载的图片。")
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
        print(f"检测到已有 {existing_max} 个文件，从序号 {start_index} 继续下载")

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
            print(f"[{target_index}] #{pid} -> {filename} 已存在，跳过")
            skipped += 1
            continue

        print(f"[{target_index}/{len(downloadable)}] 下载 #{pid} -> {filename}")
        try:
            with session.get(url, stream=True) as r:
                r.raise_for_status()
                with open(filepath, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            os.utime(filepath, None)
            downloaded += 1
        except requests.RequestException as e:
            print(f"  下载失败: {e}")
            download_failed.append(pid)
            if filepath.exists():
                filepath.unlink()
        time.sleep(REQUEST_DELAY)

    # 5. 汇总
    print("\n===== 下载完成 =====")
    print(f"标签: {tags}")
    print(f"总计帖子: {len(all_ids)}")
    print(f"成功下载: {downloaded}")
    print(f"已存在跳过: {skipped}")
    if download_failed:
        print(f"下载失败: {len(download_failed)} (ID: {', '.join(map(str, download_failed))})")
    if failed_ids:
        print(f"无可用 URL: {len(failed_ids)} (ID: {', '.join(map(str, failed_ids))})")
    print(f"文件保存至: {output_dir.resolve()}")


if __name__ == "__main__":
    main()