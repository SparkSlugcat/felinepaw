#!/usr/bin/env python3
"""
e621 / e926 Pool 爬虫（反转编号版）
- 图片按作品顺序反着命名：Pool 中最后一张作品 → 1.jpg，倒数第二张 → 2.png ……
- 原图不可用时自动下载 sample
- 支持断点续传（反转模式）
- 需要登录时，请设置环境变量 E621_USER / E621_KEY（或修改下方占位符）
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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
"Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
    "Referer": "https://e621.net/",
}
API_BASE = "https://e621.net"          # 可改为 https://e926.net
REQUEST_DELAY = 1.0                    # 请求间隔（秒）
POSTS_PER_REQUEST = 320                # 单次最多获取作品数
MAX_RETRIES = 3

# ===== 登录凭据（从环境变量读取，未设置则为空=游客） =====
API_USER = os.environ.get("E621_USER", "")            # e621/e926 登录用户名
API_KEY = os.environ.get("E621_KEY", "")              # 在账户设置中生成的 API Key
# ===================================================
# --------------------------


def create_session(proxy=None):
    """创建一个带重试和认证的 requests 会话"""
    session = common.create_session(proxy, HEADERS)
    if API_USER and API_KEY:
        session.auth = (API_USER, API_KEY)
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
    从作品数据中提取可下载的 URL 和扩展名。
    优先返回 (file.url, file.ext)，若不存在则返回 (sample.url, sample.ext)。
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
    """去除所有非法文件名字符，并避免以空格或点结尾"""
    # 保留字母、数字、空格、下划线、连字符、点（中文等非ASCII也会保留）
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _.-")
    # 过滤非法字符，并将连续空格/点压缩为单个
    clean = []
    for ch in name:
        if ch in allowed_chars:
            clean.append(ch)
        else:
            clean.append('_')  # 其他字符替换为下划线
    clean_str = ''.join(clean)
    # 压缩连续的下划线或空格
    import re
    clean_str = re.sub(r'[_\s]+', '_', clean_str).strip('_ .')
    if not clean_str:
        clean_str = "pool_download"  # 空白兜底
    return clean_str


def main():
    parser = argparse.ArgumentParser(description="下载 e621/e926 指定 Pool 中的所有图片（反转编号）")
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
    if not output_dir.exists():
        print(f"错误：无法创建输出目录 {output_dir}")
        print("可能包含系统不支持的字符，尝试使用 Pool ID 作为备用目录名...")
        output_dir = Path(f"pool_{pool_id}")
        output_dir.mkdir(parents=True, exist_ok=True)

    # 2. 获取所有作品的可下载 URL（按原始顺序）
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

    if not downloadable:
        print("没有可下载的作品，退出。")
        return

    # 3. 断点续传准备（反转模式）
    # 扫描目录中已有的数字文件名，找出最大序号
    existing_max = 0
    for f in output_dir.iterdir():
        if f.is_file() and f.stem.isdigit():
            num = int(f.stem)
            if num > existing_max:
                existing_max = num

    start_index = existing_max + 1
    total_to_download = len(downloadable)

    if existing_max > 0:
        print(f"检测到已有 {existing_max} 个文件，从序号 {start_index} 开始续传（反转顺序）")
    else:
        print(f"开始下载，图片将按 Pool 反转顺序编号：最后一张 → 1.jpg, 倒数第二张 → 2.png ...")

    # 4. 反向遍历下载
    downloaded = 0
    skipped = 0
    download_failed = []
    # 已处理（含跳过）的作品计数器，用于序号计算和续传跳过
    processed_count = 0

    # 反转列表：从最后一个可下载作品开始
    for pid, url, ext in reversed(downloadable):
        # 续传时，跳过已经完成的作品
        if processed_count < existing_max:
            processed_count += 1
            continue

        # 计算当前作品的文件名序号
        # processed_count 已经是已处理数量（包括之前跳过的），现有最大序号是 existing_max
        # 当前作品是第 (processed_count + 1) 个，对应序号从 start_index 开始
        target_index = start_index + (processed_count - existing_max)

        filename = f"{target_index}.{ext}"
        filepath = output_dir / filename

        if filepath.exists():
            print(f"[{target_index}/{total_to_download}] 作品 #{pid} -> {filename} 已存在，跳过")
            skipped += 1
            processed_count += 1
            continue

        print(f"[{target_index}/{total_to_download}] 下载作品 #{pid} -> {filename}")
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
            # 即使失败，也占用一个序号（保证后续序号正确）
            processed_count += 1
            continue

        processed_count += 1
        time.sleep(REQUEST_DELAY)

    # 5. 汇总
    print("\n===== 下载完成 =====")
    print(f"Pool: {pool_name} (ID: {pool_id})")
    print(f"总计作品: {total_posts}")
    print(f"可下载作品: {total_to_download}")
    print(f"成功下载: {downloaded}")
    print(f"已存在跳过: {skipped}")
    if download_failed:
        print(f"下载失败: {len(download_failed)} (ID: {', '.join(map(str, download_failed))})")
    if failed_ids:
        print(f"无可用 URL: {len(failed_ids)} (ID: {', '.join(map(str, failed_ids))})")
    print(f"文件保存至: {output_dir.resolve()}")
    if existing_max > 0:
        print("提示：反转编号续传时，已保证序号连续。若手动删除中间文件可能导致重复，建议清空目录后重试。")


if __name__ == "__main__":
    main()