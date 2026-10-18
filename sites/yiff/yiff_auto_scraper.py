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

# ---- 定位项目根目录（felinepaw/）并导入 i18n，供下面的提示语使用 ----
for _p in (_HERE.parent.parent, _HERE.parent, _HERE):
    if (_p / "i18n.py").exists():
        sys.path.insert(0, str(_p))
        break
import i18n

try:
    from DrissionPage import ChromiumOptions, ChromiumPage
except ImportError:
    if _ENV.exists():
        sys.path.insert(0, str(_ENV))
        from DrissionPage import ChromiumOptions, ChromiumPage
    else:
        print(i18n.t("fa_err_no_drissionpage"))
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
        log(i18n.t("yf_round", page=page_no, n=len(new), total=len(all_posts)))

        if len(all_posts) == last_count:
            log(i18n.t("yf_scroll_done"))
            break
        last_count = len(all_posts)

        if page_no >= max_pages:
            log(i18n.t("yf_max_rounds", n=max_pages))
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
    parser = argparse.ArgumentParser(description=i18n.t("yf_auto_desc"))
    parser.add_argument("tag", help=i18n.t("yf_auto_help_tag"))
    parser.add_argument("-o", "--output", default=None, help=i18n.t("yf_help_output"))
    parser.add_argument("--max-pages", type=int, default=30, help=i18n.t("yf_help_max_pages"))
    parser.add_argument("--headless", action="store_true", help=i18n.t("yf_help_headless"))
    parser.add_argument("--list-only", action="store_true", help=i18n.t("yf_help_list_only"))
    parser.add_argument("--limit", default=None,
                        help=i18n.t("yf_help_limit"))
    parser.add_argument("--proxy", default=None, help=i18n.t("yf_auto_help_proxy"))
    parser.add_argument("--browser", default=None,
                        help=i18n.t("yf_help_browser"))
    args = parser.parse_args()

    tag = args.tag.strip()
    print(i18n.t("yf_auto_tag", tag=tag, n=args.max_pages))

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
    print(i18n.t("yf_starting_browser"))
    page = ChromiumPage(co)
    try:
        # 2. 打开标签页并翻页收集
        url = f"https://yiffverse.com/tag/{ys.quote(tag, safe='')}"
        print(i18n.t("yf_open_url", url=url))
        page.get(url)
        time.sleep(3)          # 等待首屏 SSR + Blazor 渲染
        posts = collect_all_posts(page, args.max_pages)
    finally:
        try:
            page.quit()
        except Exception:
            pass

    if not posts:
        print(i18n.t("yf_no_posts_collected"))
        return
    print(i18n.t("yf_collected", n=len(posts),
                 images=sum(1 for p in posts if p[1] == 'image'),
                 videos=sum(1 for p in posts if p[1] == 'video')))

    if args.list_only:
        for i, (pid, kind, _) in enumerate(posts, 1):
            print(i18n.t("yf_list_item", i=i, pid=pid, kind=kind))
        return

    limit = ys.parse_limit(args.limit, len(posts))
    if limit is None:
        return
    posts = posts[:limit]
    print(i18n.t("yf_limit", n=limit))

    # 3. 下载（复用 yiff_scraper 的逻辑）
    session = ys.create_session(args.proxy)
    if session.proxies:
        print(i18n.t("yf_proxy_enabled", proxy=list(session.proxies.values())[0]))
    else:
        print(i18n.t("yf_proxy_direct"))

    out = Path(args.output) if args.output else Path(ys.sanitize_filename(tag))
    out.mkdir(parents=True, exist_ok=True)
    existing_max = ys.find_existing_max(out)
    start_index = existing_max + 1
    if existing_max > 0:
        print(i18n.t("yf_resume", n=existing_max, start=start_index))

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
        if ys.probe_and_download(session, pid, kind, chunk, final_path, log=print):
            downloaded += 1
        else:
            failed += 1
        time.sleep(ys.REQUEST_DELAY)

    print(i18n.t("yf_done_title"))
    print(i18n.t("yf_tag", tag=tag))
    print(i18n.t("yf_summary_downloaded", n=downloaded))
    print(i18n.t("yf_summary_skipped", n=skipped))
    print(i18n.t("yf_summary_failed", n=failed))
    print(i18n.t("yf_saved_to", path=out.resolve()))


if __name__ == "__main__":
    main()


