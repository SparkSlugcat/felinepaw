#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
felinepaw_tool.py — 一体化工具 v1（统一 CLI 分发器）
======================================================
把 e621 / yiff / e-hentai / furaffinity / BBooru / wilddream 各站脚本统一到一个入口，
自动映射参数、流式显示输出。

用法：
    python felinepaw_tool.py e621 tags --tags feline -o ./out
    python felinepaw_tool.py e621 pool https://e621.net/pools/12345 -o ./out
    python felinepaw_tool.py yiff feline --limit 50
    python felinepaw_tool.py yiff feline --auto --max-pages 10
    python felinepaw_tool.py ehentai "https://e-hentai.org/g/xxx/yyy/" -o ./out
    python felinepaw_tool.py fa "https://www.furaffinity.net/view/xxx/" --cookies fa_cookies.json -o ./out
    python felinepaw_tool.py bbooru --tags landscape -o ./out          # 按标签
    python felinepaw_tool.py bbooru --pool 33976 --limit 20 -o ./out   # 按合集（show 页 URL 或纯 id）
    python felinepaw_tool.py wilddream "https://www.wilddream.net/art/userpage/gallery?userpagename=...&folderid=485" -o ./out

通用参数（按站点脚本支持度自动透传）：
    -o/--output  --limit  --proxy  -w/--workers  -d/--delay
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# 站点 -> (默认脚本, 支持的通用参数, 需要的位置参数帮助)
E621_SCRIPTS = {
    "tags":     "e6_scraper.py",
    "page":     "e6_taged_page_scraper.py",
    "artist":   "e6_artist.py",
    "pool":     "pool_scraper.py",
    "pool-rev": "e621.py",
}
# 各脚本支持的通用参数白名单（e621 旧脚本只有 -o）
WHITELIST = {
    "e6_scraper.py": ["-o", "--limit"],
    "e6_taged_page_scraper.py": ["-o"],
    "e6_artist.py": ["-o"],
    "pool_scraper.py": ["-o"],
    "e621.py": ["-o"],
    "yiff_scraper.py": ["-o", "--limit", "--proxy"],
    "yiff_auto_scraper.py": ["-o", "--limit", "--proxy", "--max-pages", "--headless"],
    "EH_scraper_v2.py": ["-o", "--limit", "--proxy", "-w", "-d"],
    "FA_scraper.py": ["-o", "--limit", "--proxy", "-w", "-d", "--cookies"],
    "B_scraper.py": ["-o", "--limit", "--proxy", "--adult", "--name", "--retry", "--dry-run"],
    "W_scraper.py": ["-o", "--limit"],
}


def build_command(site: str, args) -> list:
    """根据站点与参数构造子进程命令。"""
    script = None
    pos_args = []

    if site in ("e621", "e926"):
        if not args.mode:
            raise ValueError(f"{site} 需要 --mode: tags/page/artist/pool/pool-rev")
        script = E621_SCRIPTS[args.mode]
        if args.mode in ("tags", "page", "artist"):
            if not args.tags:
                raise ValueError("该模式需要 --tags")
            pos_args += ["--tags", args.tags]
            if args.mode == "page" and args.page:
                pos_args += ["--page", str(args.page)]
            if args.mode == "artist" and args.skip_others:
                pos_args += ["--skip-others"]
        else:
            if not args.target:
                raise ValueError("该模式需要 Pool URL，例如: e621 pool https://e621.net/pools/123")
            pos_args += [args.target]

    elif site == "yiff":
        if not args.target:
            raise ValueError("yiff 需要标签，例如: yiff feline")
        if args.auto:
            script = "yiff_auto_scraper.py"
            pos_args += [args.target]
        else:
            script = "yiff_scraper.py"
            pos_args += [args.target]

    elif site == "ehentai":
        if not args.target:
            raise ValueError("ehentai 需要画廊 URL")
        script = "EH_scraper_v2.py"
        pos_args += [args.target]

    elif site == "fa":
        if not args.target:
            raise ValueError("fa 需要作品 URL")
        script = "FA_scraper.py"
        pos_args += [args.target]

    elif site == "bbooru":
        script = "B_scraper.py"
        if args.tags and args.pool:
            raise ValueError("bbooru 的 --tags 与 --pool 只能二选一")
        if args.pool:
            pos_args += ["--pool", args.pool]          # 合集：show 页 URL 或纯 id
        elif args.tags:
            pos_args += ["--tags", args.tags]
        else:
            raise ValueError("bbooru 需要 --tags <标签> 或 --pool <show页URL/id>")
        # bbooru 的并发参数是 --threads，把通用 -w 映射过去
        if args.workers:
            pos_args += ["--threads", str(args.workers)]

    elif site == "wilddream":
        if not args.target:
            raise ValueError("wilddream 需要画廊 URL（目标框）")
        script = "W_scraper.py"
        pos_args += [args.target]

    else:
        raise ValueError(f"未知站点: {site}（可用: e621/e926/yiff/ehentai/fa/bbooru/wilddream）")

    site_dir = {"bbooru": "BBooru"}.get(site, site)
    if site in ("e621", "e926"):
        site_dir = "e621"
    cmd = [sys.executable, str(HERE / "sites" / site_dir / script)] + pos_args

    # 按白名单透传通用参数；不支持的参数给出警告（防止"以为限制了其实全下"）
    allowed = set(WHITELIST.get(script, []))
    def _add(flag, value):
        if value is not None and value is not False:
            if flag in allowed:
                if flag == "--headless":
                    cmd.extend([flag])
                else:
                    cmd.extend([flag, str(value)])
            else:
                print(f"⚠️ 警告: 目标脚本 {script} 不支持 {flag}，该参数已忽略", file=sys.stderr)
    _add("-o", args.output)
    _add("--limit", args.limit)
    _add("--proxy", args.proxy)
    if site != "bbooru":           # bbooru 的 -w 已在上面映射为 --threads
        _add("-w", args.workers)
    _add("-d", args.delay)
    _add("--cookies", args.cookies)
    _add("--max-pages", args.max_pages)
    _add("--headless", args.headless)
    return cmd


def main():
    parser = argparse.ArgumentParser(
        description="felinepaw 一体化工具：统一调度 e621/yiff/e-hentai/furaffinity/bbooru/wilddream 脚本")
    parser.add_argument("site",
                        choices=["e621", "e926", "yiff", "ehentai", "fa", "bbooru", "wilddream"],
                        help="站点（e926 为 e621 安全版；bbooru 用 --tags/--pool；wilddream 用画廊 URL）")
    # e621 模式
    parser.add_argument("--mode", choices=["tags", "page", "artist", "pool", "pool-rev"],
                        help="e621 下载模式")
    parser.add_argument("--tags", help="标签（e621/bbooru 用）")
    parser.add_argument("--pool", default=None,
                        help="bbooru 合集：pool show 页 URL 或纯 id（与 --tags 二选一）")
    parser.add_argument("--page", type=int, help="页码（e621 page 模式）")
    parser.add_argument("--skip-others", action="store_true", help="艺术家模式跳过非池作品")
    parser.add_argument("target", nargs="?",
                        help="目标：yiff=标签；pool/ehentai/fa=URL；wilddream=画廊 URL")
    # 通用
    parser.add_argument("-o", "--output", default=None, help="保存目录")
    parser.add_argument("--limit", default=None, help="下载数量: 数字或 inf")
    parser.add_argument("--proxy", default=None, help="代理: 留空自动/off/URL")
    parser.add_argument("-w", "--workers", type=int, default=None, help="并发线程数")
    parser.add_argument("-d", "--delay", type=float, default=None, help="随机延迟上限秒")
    parser.add_argument("--cookies", default=None, help="FA cookies 文件")
    # yiff 自动版
    parser.add_argument("--auto", action="store_true", help="yiff 用浏览器滚动版")
    parser.add_argument("--max-pages", type=int, default=None, help="yiff 自动版最大滚动轮数")
    parser.add_argument("--headless", action="store_true", help="yiff 自动版无头模式")
    args = parser.parse_args()

    if args.site == "e926":
        print("e926 暂不可用：该站被 Cloudflare 人机挑战拦截，纯 requests 无法访问。")
        print("请改用 e621，或用浏览器访问 e926。后续若实现浏览器模式再恢复支持。")
        sys.exit(1)

    try:
        cmd = build_command(args.site, args)
    except ValueError as e:
        print(f"参数错误: {e}")
        parser.print_help()
        sys.exit(2)

    print(">>> " + " ".join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace",
                            bufsize=1)
    try:
        for line in proc.stdout:
            print(line, end="", flush=True)
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        print("\n已终止。")
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
