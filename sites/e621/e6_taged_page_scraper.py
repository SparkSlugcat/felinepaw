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
        print("已使用认证信息登录")
    else:
        print("以游客身份访问（部分标签或原图可能受限）")
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
            print(f"  第 {current_page} 页，获取到 {len(posts)} 个帖子（累计 {len(all_ids)}）")

            if page_num is not None:
                break   # 指定了页码，只取一页
            if len(posts) < POSTS_PER_REQUEST:
                break   # 最后一页
            current_page += 1
            time.sleep(REQUEST_DELAY)
        except requests.exceptions.JSONDecodeError:
            print(f"    响应不是 JSON，前200字节: {resp.content[:200]}")
            break
        except requests.RequestException as e:
            print(f"获取帖子列表失败（第 {current_page} 页）: {e}")
            print("等待 5 秒后重试...")
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
    parser = argparse.ArgumentParser(description="下载 e621/e926 指定 tags 的图片")
    parser.add_argument("--tags", required=True, help="搜索标签，例如 aubrey_(iceink) 或带排序的 arcanis_(hahaluckyme) order:hot")
    parser.add_argument("--page", type=int, default=None, help="指定下载第几页（不指定则下载全部）")
    parser.add_argument("-o", "--output", default=None, help="图片保存目录（默认以标签命名）")
    args = parser.parse_args()

    tags = args.tags.strip()
    print(f"搜索标签: {tags}")
    if args.page:
        print(f"仅下载第 {args.page} 页")
    else:
        print("下载所有页面")

    # 1. 获取帖子 ID 列表
    print("正在获取帖子 ID 列表...")
    try:
        all_ids = fetch_post_ids(tags, page_num=args.page)
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

    # 2. 批量获取帖子详细信息，构建可下载列表
    downloadable = []   # (post_id, url, ext)
    failed_ids = []     # 没有可用 URL 的帖子 ID

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

    print(f"可下载: {len(downloadable)}, 无可用URL: {len(failed_ids)}")
    if not downloadable:
        print("没有可下载的图片。")
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
        print(f"检测到已有 {existing_max} 个文件，从序号 {start_index} 继续下载")



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
            print(f"[{target_index}/{len(downloadable)}] 帖子 #{pid} -> {filename} 已存在，跳过")
            with lock:
                skipped += 1
            continue

        tasks.append((pid, url, filepath, target_index))

    total_tasks = len(tasks)
    print(f"待下载任务数: {total_tasks}")

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
                print(f"[{idx}/{len(downloadable)}] 下载帖子 #{pid} -> {filepath.name} 完成")
            else:  # 失败
                success, pid, idx, error = result
                with lock:
                    download_failed.append(pid)
                print(f"[{idx}/{len(downloadable)}] 下载帖子 #{pid} 失败: {error}")
                # 删除可能残留的残缺文件
                if filepath.exists():
                    filepath.unlink()

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