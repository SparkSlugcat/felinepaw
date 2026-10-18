#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Yiffverse (yiffverse.com) 标签图片爬虫
==============================================
仿照 e621 系列脚本编写，按标签下载 yiffverse 上的图片/视频。

用法示例：
    python yiff_scraper.py feline                 # 默认下载前 120 个（实际最多 30）
    python yiff_scraper.py "jack-jackal_(character)" -o ./jack_pics
    python yiff_scraper.py feline --limit 10      # 只下载前 10 个
    python yiff_scraper.py feline --limit inf     # 下载全部（该版本最多 30）

特点：
- 图片按顺序编号 1.jpg, 2.png ...（原图优先，自动探测真实扩展名）
- 支持断点续传（已有数字文件自动跳过）
- 自动跟随 Windows 系统代理（也可手动指定或关闭）
- 请求间隔 1 秒，礼貌访问

⚠️ 已知限制（重要）：
- yiffverse 是 Blazor 单页应用，服务器端渲染（SSR）每个标签页只输出
  最新的约 30 个帖子；翻页是客户端（SignalR）行为，没有公开的 HTTP 分页
  接口，因此本脚本每个标签最多只能下载到最新 30 个帖子。
- 文件命名规律（已逆向确认）：
      原图:   https://furry34com.b-cdn.net/posts/{id//1000}/{id}/{id}.pic.{ext}
      原视频: https://furry34com.b-cdn.net/posts/{id//1000}/{id}/{id}.mov.{ext}
      缩略图: {id}.pic256.jpg / 视频预览 {id}.mov256.mp4
- 原始扩展名不在网页里，需要逐个探测（图片: jpg->png->gif->webp；视频: mp4->webm）
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

# ---- 定位并导入共享模块 common.py（felinepaw 基础库） ----
_here = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.dirname(os.path.dirname(_here)), os.path.dirname(_here), _here):
    if os.path.exists(os.path.join(_p, "common.py")):
        sys.path.insert(0, _p)
        break
import common
import i18n
# 共享函数别名（供本脚本及 yiff_auto_scraper 使用）
create_session = common.create_session
sanitize_filename = common.sanitize_filename
find_existing_max = common.find_existing_max
parse_limit = common.parse_limit

# ---------- 配置 ----------
SITE_BASE = "https://yiffverse.com"
CDN_BASE = "https://furry34com.b-cdn.net"
REQUEST_DELAY = 1.0            # 请求间隔（秒）
MAX_RETRIES = 3
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

# 原文件扩展名探测顺序（按出现概率排序）
IMAGE_EXTS = ("jpg", "png", "gif", "webp")
VIDEO_EXTS = ("mp4", "webm")


# ============================================================
# 解析
# ============================================================

def fetch_tag_page(session: requests.Session, tag: str):
    """抓取 /tag/{tag} 页面，解析出帖子列表。

    返回 [(post_id, kind, chunk), ...]
      kind: "image" / "video"（由缩略图类型判断）
      chunk: 帖子 ID 所在 CDN 目录段（id // 1000）
    """
    url = f"{SITE_BASE}/tag/{quote(tag, safe='')}"
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    html = resp.text

    posts = []          # (id, kind, chunk)
    seen = set()

    # 先扫一遍所有缩略图/预览 URL，记录每个帖子出现过的类型和 CDN 目录段。
    # 注意：视频卡片同时含 pic256（海报）和 mov256（视频源），只要出现 mov256 即视频。
    info = {}           # pid -> (chunk, kinds集合)
    for um in re.finditer(r'furry34com\.b-cdn\.net/posts/(\d+)/(\d+)/(\d+)\.(pic256|mov256)\.[a-z0-9]+',
                          html):
        chunk, pid = um.group(1), um.group(2)
        kind = "video" if um.group(4) == "mov256" else "image"
        entry = info.setdefault(pid, (chunk, set()))
        entry[1].add(kind)

    # 帖子链接: <a ... href="/post/839793?&d=feline"> 或首页格式 /post/839793
    for m in re.finditer(r'href="/post/(\d+)(?:\?[^"]*)?"', html):
        pid = m.group(1)
        if pid in seen:
            continue
        seen.add(pid)
        entry = info.get(pid)
        if not entry:
            continue
        chunk, kinds = entry
        kind = "video" if "video" in kinds else "image"
        posts.append((pid, kind, chunk))
    return posts


def build_original_url(post_id: str, kind: str, chunk: str, ext: str) -> str:
    """根据帖子 ID 构造原文件 URL。"""
    fmt = "mov" if kind == "video" else "pic"
    return f"{CDN_BASE}/posts/{chunk}/{post_id}/{post_id}.{fmt}.{ext}"


def probe_and_download(session: requests.Session, post_id: str, kind: str,
                       chunk: str, filepath: Path, log=print) -> bool:
    """按探测顺序尝试下载原文件；成功返回 True。"""
    exts = VIDEO_EXTS if kind == "video" else IMAGE_EXTS
    for ext in exts:
        url = build_original_url(post_id, kind, chunk, ext)
        try:
            with session.get(url, stream=True, timeout=60) as r:
                if r.status_code != 200:
                    continue            # 该扩展名不存在，试下一个
                with open(filepath, "wb") as f:
                    for chunk_data in r.iter_content(chunk_size=8192):
                        f.write(chunk_data)
            os.utime(filepath, None)
            return True
        except requests.RequestException as e:
            log(i18n.t("yf_err_download", id=post_id, e=e))
            if filepath.exists():
                try:
                    filepath.unlink()
                except OSError:
                    pass
            return False
    return False


# ============================================================
# 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(description=i18n.t("yf_cli_desc"))
    parser.add_argument("tag", help=i18n.t("yf_help_tag"))
    parser.add_argument("-o", "--output", default=None, help=i18n.t("yf_help_output"))
    parser.add_argument("--limit", default=None,
                        help=i18n.t("yf_help_limit"))
    parser.add_argument("--proxy", default=None,
                        help=i18n.t("yf_help_proxy"))
    args = parser.parse_args()

    tag = args.tag.strip()
    print(i18n.t("yf_tag", tag=tag))
    print(i18n.t("yf_note1"))
    print(i18n.t("yf_note2"))

    session = create_session(args.proxy)
    if session.proxies:
        print(i18n.t("yf_proxy_enabled", proxy=list(session.proxies.values())[0]))
    else:
        print(i18n.t("yf_proxy_direct"))

    # 1. 解析标签页
    print(i18n.t("yf_fetching_tag_page", url=f"{SITE_BASE}/tag/{quote(tag, safe='')}"))
    try:
        posts = fetch_tag_page(session, tag)
    except requests.RequestException as e:
        print(i18n.t("yf_err_fetch_tag_page", e=e))
        sys.exit(1)

    if not posts:
        print(i18n.t("yf_no_posts"))
        return

    limit = parse_limit(args.limit, len(posts))
    if limit is None:
        return
    posts = posts[:limit]
    print(i18n.t("yf_limit", n=limit))
    print(i18n.t("yf_parsed", n=len(posts),
                 images=sum(1 for p in posts if p[1] == 'image'),
                 videos=sum(1 for p in posts if p[1] == 'video')))

    # 2. 输出目录 + 断点续传
    out = Path(args.output) if args.output else Path(sanitize_filename(tag))
    out.mkdir(parents=True, exist_ok=True)
    existing_max = find_existing_max(out)
    start_index = existing_max + 1
    if existing_max > 0:
        print(i18n.t("yf_resume", n=existing_max, start=start_index))

    # 3. 下载（顺序编号，与列表顺序一致）
    downloaded = failed = skipped = 0
    for idx, (pid, kind, chunk) in enumerate(posts):
        if idx < existing_max:           # 续传跳过已完成的
            continue
        target_index = start_index + (idx - existing_max)
        filename = f"{target_index}.jpg"
        filepath = out / filename        # 扩展名探测后如不同，会重命名
        if filepath.exists():
            print(i18n.t("yf_skip_exists", idx=target_index, pid=pid))
            skipped += 1
            continue

        # 先探测真实扩展名再确定文件名（避免写死 .jpg）
        exts = VIDEO_EXTS if kind == "video" else IMAGE_EXTS
        real_ext = None
        for ext in exts:
            url = build_original_url(pid, kind, chunk, ext)
            try:
                r = session.head(url, timeout=20, allow_redirects=True)
            except requests.RequestException:
                continue
            if r.status_code == 200:
                real_ext = ext
                break
            time.sleep(0.3)
        if not real_ext:
            print(i18n.t("yf_err_no_original", idx=target_index, pid=pid))
            failed += 1
            continue

        final_path = out / f"{target_index}.{real_ext}"
        if final_path.exists():
            print(i18n.t("yf_skip_exists_named", idx=target_index, pid=pid,
                         name=final_path.name))
            skipped += 1
            continue

        print(i18n.t("yf_downloading", idx=target_index, total=len(posts),
                     pid=pid, name=final_path.name))
        if probe_and_download(session, pid, kind, chunk, final_path, log=print):
            downloaded += 1
        else:
            failed += 1
        time.sleep(REQUEST_DELAY)

    # 4. 汇总
    print(i18n.t("yf_done_title"))
    print(i18n.t("yf_tag", tag=tag))
    print(i18n.t("yf_summary_downloaded", n=downloaded))
    print(i18n.t("yf_summary_skipped", n=skipped))
    print(i18n.t("yf_summary_failed", n=failed))
    print(i18n.t("yf_saved_to", path=out.resolve()))


if __name__ == "__main__":
    main()
