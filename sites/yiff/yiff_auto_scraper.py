#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Yiffverse 全量标签爬虫（浏览器自动化版）
==============================================
用 DrissionPage 驱动本机 Chrome，模拟点击"下一页"翻页，
突破 SSR 每标签只渲染 30 帖的限制（靠页面底部无限滚动加载），收集标签下的全部帖子，
再复用 yiff_scraper.py 的原文件探测/下载逻辑保存。

用法示例（推荐用你的 py39 环境，已装好 DrissionPage）：
    conda activate py39
    python yiff_auto_scraper.py feline                  # 默认下载前 120 个
    python yiff_auto_scraper.py feline --limit 50      # 只下载前 50 个
    python yiff_auto_scraper.py feline --limit inf     # 下载全部（滚到没有为止）
    python yiff_auto_scraper.py feline -o ./feline_full --max-pages 10
    python yiff_auto_scraper.py feline --headless --max-pages 3 --list-only

依赖：
- Chrome（或 Edge/Chromium 系浏览器）已安装
- DrissionPage（你的 py39 conda 环境已装；若当前环境没有，
  会回退使用本文件上一级 _dsp_env 目录里的预装副本）

注意：
- 首次运行会弹出一个 Chrome 窗口（可加 --headless 隐藏），请勿手动关闭
- 下载仍走 requests + 代理（自动跟随系统代理）
"""

import argparse
import re
import sys
import time
from pathlib import Path

# ---- 环境准备：优先用当前环境的 DrissionPage；没有则回退到 ../_dsp_env ----
_HERE = Path(__file__).resolve().parent
_ENV = _HERE.parent / "_dsp_env"
try:
    from DrissionPage import ChromiumOptions, ChromiumPage
except ImportError:
    if _ENV.exists():
        sys.path.insert(0, str(_ENV))
        from DrissionPage import ChromiumOptions, ChromiumPage
    else:
        print("未找到 DrissionPage。请先激活 py39 环境：conda activate py39")
        sys.exit(1)

sys.path.insert(0, str(_HERE))
import yiff_scraper as ys          # 复用原文件探测与下载逻辑


def parse_tag_html(html: str):
    """从标签页 DOM 中提取帖子列表 [(pid, kind, chunk), ...]（顺序去重）。"""
    posts = []
    seen = set()
    info = {}   # pid -> (chunk, kinds)
    for um in re.finditer(r'furry34com\.b-cdn\.net/posts/(\d+)/(\d+)/(\d+)\.(pic256|mov256)\.[a-z0-9]+',
                          html):
        chunk, pid = um.group(1), um.group(2)
        kind = "video" if um.group(4) == "mov256" else "image"
        entry = info.setdefault(pid, (chunk, set()))
        entry[1].add(kind)
    for m in re.finditer(r'href="/post/(\d+)(?:\?[^"]*)?"', html):
        pid = m.group(1)
        if pid in seen:
            continue
        seen.add(pid)
        entry = info.get(pid)
        if not entry:
            continue
        chunk, kinds = entry
        posts.append((pid, "video" if "video" in kinds else "image", chunk))
    return posts


def collect_all_posts(page, max_pages: int, log=print) -> list:
    """循环滚动到底部，利用无限滚动收集全部帖子 [(pid, kind, chunk), ...]。

    该标签页是"滚动加载"（页面底部有隐藏的分页按钮，实际靠滚动触发加载），
    因此每轮：收集当前 DOM 里的帖子 -> 滚动到底部 -> 等待加载 -> 重复，
    直到滚动后没有新帖子为止。
    """
    all_posts = []
    seen = set()
    last_count = 0
    for page_no in range(1, max_pages + 1):
        current = parse_tag_html(page.html)
        new = [p for p in current if p[0] not in seen]
        for p in new:
            seen.add(p[0])
            all_posts.append(p)
        log(f"第 {page_no} 轮: 解析 {len(new)} 个新帖子（累计 {len(all_posts)}）")

        if len(all_posts) == last_count:
            log("滚动后没有新帖子，加载结束。")
            break
        last_count = len(all_posts)

        if page_no >= max_pages:
            log(f"已达最大轮数 {max_pages}，停止。")
            break

        page.scroll.to_bottom()          # 触发无限滚动加载
        time.sleep(2)
        if len(parse_tag_html(page.html)) == last_count:
            # 主页面滚动无效时，尝试内部滚动容器
            page.run_js("document.querySelector('.grid') "
                        "? document.querySelector('.grid').parentElement.scrollTop = 99999 : 0")
            time.sleep(2)
    return all_posts


def main():
    parser = argparse.ArgumentParser(description="yiffverse 全量标签爬虫（浏览器翻页版）")
    parser.add_argument("tag", help="标签名，例如 feline")
    parser.add_argument("-o", "--output", default=None, help="保存目录（默认以标签名命名）")
    parser.add_argument("--max-pages", type=int, default=30, help="最多翻页数（每页约30帖）")
    parser.add_argument("--headless", action="store_true", help="无头模式（不弹浏览器窗口）")
    parser.add_argument("--list-only", action="store_true", help="只列出帖子，不下载")
    parser.add_argument("--limit", default=None,
                        help="下载数量: 正整数 或 inf(全部)；不填默认只下载前 120 个")
    parser.add_argument("--proxy", default=None, help="代理: 留空=自动, off=直连, 或 http://127.0.0.1:7897")
    parser.add_argument("--browser", default=None,
                        help="浏览器可执行文件路径（默认自动用 Edge，其次 Chrome）")
    args = parser.parse_args()

    tag = args.tag.strip()
    print(f"标签: {tag}（浏览器滚动加载模式，最多 {args.max_pages} 轮）")

    # 1. 启动浏览器（与你平时自动化环境一致，优先 Edge）
    co = ChromiumOptions()
    if args.headless:
        co.headless(True)
    co.set_argument("--no-sandbox")
    co.set_argument("--disable-gpu")
    edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if args.browser:
        co.set_browser_path(args.browser)
    elif Path(edge).exists():
        co.set_browser_path(edge)
    elif Path(chrome).exists():
        co.set_browser_path(chrome)
    print("正在启动浏览器（DrissionPage）...")
    page = ChromiumPage(co)
    try:
        # 2. 打开标签页并翻页收集
        url = f"https://yiffverse.com/tag/{ys.quote(tag, safe='')}"
        print(f"打开 {url}")
        page.get(url)
        time.sleep(3)          # 等待首屏 SSR + Blazor 渲染
        posts = collect_all_posts(page, args.max_pages)
    finally:
        try:
            page.quit()
        except Exception:
            pass

    if not posts:
        print("没有收集到任何帖子（标签可能不存在）。")
        return
    print(f"\n共收集 {len(posts)} 个帖子"
          f"（图片 {sum(1 for p in posts if p[1]=='image')}，视频 {sum(1 for p in posts if p[1]=='video')}）")

    if args.list_only:
        for i, (pid, kind, _) in enumerate(posts, 1):
            print(f"  {i:4d} #{pid} [{kind}]")
        return

    limit = ys.parse_limit(args.limit, len(posts))
    if limit is None:
        return
    posts = posts[:limit]
    print(f"下载数量上限: {limit}")

    # 3. 下载（复用 yiff_scraper 的逻辑）
    session = ys.create_session(args.proxy)
    if session.proxies:
        print(f"已启用代理: {list(session.proxies.values())[0]}")
    else:
        print("未使用代理（直连）")

    out = Path(args.output) if args.output else Path(ys.sanitize_filename(tag))
    out.mkdir(parents=True, exist_ok=True)
    existing_max = ys.find_existing_max(out)
    start_index = existing_max + 1
    if existing_max > 0:
        print(f"检测到已有 {existing_max} 个文件，从序号 {start_index} 继续下载")

    downloaded = failed = skipped = 0
    for idx, (pid, kind, chunk) in enumerate(posts):
        if idx < existing_max:
            continue
        target_index = start_index + (idx - existing_max)

        exts = ys.VIDEO_EXTS if kind == "video" else ys.IMAGE_EXTS
        real_ext = None
        for ext in exts:
            url = ys.build_original_url(pid, kind, chunk, ext)
            try:
                r = session.head(url, timeout=20, allow_redirects=True)
            except requests.RequestException:
                continue
            if r.status_code == 200:
                real_ext = ext
                break
            time.sleep(0.3)
        if not real_ext:
            print(f"[{target_index}] #{pid} 未找到原文件，跳过")
            failed += 1
            continue

        final_path = out / f"{target_index}.{real_ext}"
        if final_path.exists():
            print(f"[{target_index}] #{pid} -> {final_path.name} 已存在，跳过")
            skipped += 1
            continue

        print(f"[{target_index}/{len(posts)}] 下载 #{pid} -> {final_path.name}")
        if ys.probe_and_download(session, pid, kind, chunk, final_path, log=print):
            downloaded += 1
        else:
            failed += 1
        time.sleep(ys.REQUEST_DELAY)

    print("\n===== 下载完成 =====")
    print(f"标签: {tag}")
    print(f"成功下载: {downloaded}")
    print(f"已存在跳过: {skipped}")
    print(f"失败: {failed}")
    print(f"文件保存至: {out.resolve()}")


if __name__ == "__main__":
    main()


