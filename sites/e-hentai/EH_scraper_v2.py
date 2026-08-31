#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
e-hentai 画廊下载器 v2（改进版）
==============================================
相比旧版 EH_scraper.py 的改进：
1. 支持代理（自动跟随系统代理，也可手动指定）——旧版没有，国内必需要
2. 修复大画廊漏图 bug：e-hentai 每页只显示 20 个图片链接，
   旧版只抓第一页（>20 页的画廊会漏掉后面的图），v2 自动翻页抓全
3. 使用官方 API (gdata) 获取标题/文件数做目录命名和校验
4. 支持 --limit（默认 120，inf=全部），与 yiff 脚本语义一致
5. 扩展名从真实图片 URL 提取（旧版写死 .webp）

用法：
    python EH_scraper_v2.py https://e-hentai.org/g/3817181/3b0370c5a1/
    python EH_scraper_v2.py "https://e-hentai.org/g/xxx/yyy/" -o ./downloads
    python EH_scraper_v2.py "https://e-hentai.org/g/xxx/yyy/" -w 6 -d 2.0 --limit 50
    python EH_scraper_v2.py "https://e-hentai.org/g/xxx/yyy/" --limit inf

依赖：requests + lxml
"""

import argparse
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from lxml import etree

# ---------- 配置 ----------
SITE = "https://e-hentai.org"
API = "https://api.e-hentai.org/api.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
GALLERY_LINKS_PER_PAGE = 20    # e-hentai 每页显示 20 个图片链接

# ---- 定位并导入共享模块 common.py（felinepaw 基础库） ----
_here = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.dirname(os.path.dirname(_here)), os.path.dirname(_here), _here):
    if os.path.exists(os.path.join(_p, "common.py")):
        sys.path.insert(0, _p)
        break
import common
# 共享函数别名
create_session = common.create_session
sanitize_filename = common.sanitize_filename
parse_limit = common.parse_limit


# ============================================================
# 解析
# ============================================================

def parse_gallery_url(url: str):
    """从画廊 URL 提取 gid 和 token。"""
    path = urlparse(url.strip()).path
    m = re.search(r"/g/(\d+)/([a-f0-9]+)", path)
    if not m:
        raise ValueError(f"无法从 URL 解析 gid/token: {url}")
    return m.group(1), m.group(2)


def fetch_gallery_meta(session: requests.Session, gid: str, token: str):
    """调用官方 gdata API 获取画廊信息；失败返回 None（回退 HTML 解析）。"""
    try:
        payload = {"method": "gdata", "gidlist": [[int(gid), token]], "namespace": 1}
        r = session.post(API, json=payload, timeout=20)
        r.raise_for_status()
        gmeta = r.json().get("gmetadata", [{}])[0]
        if gmeta.get("gid") != int(gid):
            return None
        return gmeta
    except Exception:
        return None


def fetch_gallery_links(session: requests.Session, gid: str, token: str, log=print):
    """翻页抓取画廊全部图片详情页链接，返回有序 [(detail_url, filename), ...]。

    修复旧版只抓第一页（20 张）导致大画廊漏图的 bug。
    filename 取自标题属性 "Page N: xxx.ext"（无则用索引名）。
    """
    links = []
    page = 0
    while True:
        url = f"{SITE}/g/{gid}/{token}/?p={page}"
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        tree = etree.HTML(resp.text)
        # 每个 <a href="/s/..."> 内含 title="Page N: 文件名"
        found = []
        for a in tree.xpath('//div[@id="gdt"]/a'):
            href = a.get("href", "")
            if "/s/" not in href:
                continue
            title = a.get("title", "")
            fname = ""
            m = re.search(r"Page \d+:\s*(.+)$", title)
            if m:
                fname = m.group(1).strip()
            found.append((href, fname))
        if not found:
            break
        links.extend(found)
        log(f"  画廊第 {page + 1} 页: {len(found)} 个链接（累计 {len(links)}）")
        if len(found) < GALLERY_LINKS_PER_PAGE:
            break
        page += 1
        time.sleep(0.5)
    return links


def fetch_image_url(session: requests.Session, detail_url: str):
    """访问详情页，提取原图 URL。"""
    resp = session.get(detail_url, timeout=20)
    resp.raise_for_status()
    tree = etree.HTML(resp.text)
    srcs = tree.xpath('//div[@id="i3"]/a/img/@src')
    if not srcs:
        return None
    return srcs[0]


# ============================================================
# 下载
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="e-hentai 画廊下载器 v2（代理/翻页/限速）")
    parser.add_argument("url", help="画廊 URL，例如 https://e-hentai.org/g/3817181/3b0370c5a1/")
    parser.add_argument("-o", "--output", default=None, help="保存目录（默认用画廊标题命名）")
    parser.add_argument("-w", "--workers", type=int, default=4, help="并发线程数（默认4）")
    parser.add_argument("-d", "--delay", type=float, default=1.0, help="随机延迟上限秒（默认1.0）")
    parser.add_argument("--limit", default=None,
                        help="下载数量: 正整数 或 inf(全部)；不填默认只下载前 120 个")
    parser.add_argument("--proxy", default=None,
                        help="代理: 留空=自动检测, off=直连, 或 http://127.0.0.1:7897")
    args = parser.parse_args()

    # ---------- 1. 解析 URL ----------
    try:
        gid, token = parse_gallery_url(args.url)
    except ValueError as e:
        print(e)
        sys.exit(1)
    print(f"gid={gid} token={token}")

    session = create_session(args.proxy)
    if session.proxies:
        print(f"已启用代理: {list(session.proxies.values())[0]}")
    else:
        print("未使用代理（直连）")

    # ---------- 2. API 元数据（标题用于目录命名） ----------
    meta = fetch_gallery_meta(session, gid, token)
    if meta:
        title = meta.get("title") or f"gallery_{gid}"
        filecount = meta.get("filecount")
        print(f"画廊标题: {title} | 文件数: {filecount} | 分类: {meta.get('category')}")
    else:
        print("gdata API 未返回信息，回退用 URL 命名目录。")
        title = f"gallery_{gid}"

    # ---------- 3. 抓取全部详情页链接（自动翻页） ----------
    print("正在翻页抓取图片详情页链接...")
    try:
        detail_links = fetch_gallery_links(session, gid, token, log=print)
    except requests.RequestException as e:
        print(f"获取画廊页面失败: {e}")
        sys.exit(1)

    if not detail_links:
        print("未找到任何图片链接（画廊可能已被删除或需要登录）。")
        return

    limit = parse_limit(args.limit, len(detail_links))
    if limit is None:
        return
    detail_links = detail_links[:limit]
    print(f"共 {len(detail_links)} 张图片（下载上限 {limit}），"
          f"{args.workers} 线程下载，随机延迟 0~{args.delay}s")

    # ---------- 4. 输出目录 ----------
    out = Path(args.output) if args.output else Path(safe_name(title))
    out.mkdir(parents=True, exist_ok=True)

    # ---------- 5. 并发下载 ----------
    lock = __import__("threading").Lock()
    downloaded = failed = skipped = 0

    def job(idx, detail_url):
        nonlocal downloaded, failed, skipped
        time.sleep(random.uniform(0, args.delay))
        # 断点续传：目录里已有 {idx}.* 则跳过
        if any(out.glob(f"{idx}.*")):
            with lock:
                skipped += 1
            print(f"[{idx}] 已存在，跳过")
            return
        try:
            img_url = fetch_image_url(session, detail_url)
            if not img_url:
                raise RuntimeError("详情页未找到图片 src")
            ext = Path(urlparse(img_url).path).suffix.lstrip(".") or "jpg"
            filepath = out / f"{idx}.{ext}"
            if filepath.exists():
                with lock:
                    skipped += 1
                print(f"[{idx}] {filepath.name} 已存在，跳过")
                return
            with session.get(img_url, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(filepath, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        f.write(chunk)
            if filepath.stat().st_size == 0:
                filepath.unlink()
                raise RuntimeError("下载文件为空")
            with lock:
                downloaded += 1
            print(f"[{idx}/{len(detail_links)}] 完成 -> {filepath.name}")
        except Exception as e:
            with lock:
                failed += 1
            print(f"[{idx}] 失败: {e}")

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(job, idx, url): (idx, url)
                   for idx, (url, _fname) in enumerate(detail_links, 1)}
        for future in as_completed(futures):
            pass    # 异常已在 job 内处理

    # ---------- 6. 汇总 ----------
    print("\n===== 下载完成 =====")
    print(f"画廊: {title} (gid={gid})")
    print(f"成功: {downloaded} | 跳过: {skipped} | 失败: {failed}")
    print(f"文件保存至: {out.resolve()}")


if __name__ == "__main__":
    main()
