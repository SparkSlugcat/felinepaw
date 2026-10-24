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
    python felinepaw_tool.py bbooru --pool 123456 --limit 20 -o ./out   # 按合集（show 页 URL 或纯 id）
    python felinepaw_tool.py wilddream "https://www.wilddream.net/art/userpage/gallery?userpagename=...&folderid=123" -o ./out

通用参数（按站点脚本支持度自动透传）：
    -o/--output  --limit  --proxy  -w/--workers  -d/--delay  --jitter  --cooldown
    --force  --no-preflight
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# 借同级的 common.py 读本机默认输出目录（.pawout）
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import common  # noqa: E402
import i18n  # noqa: E402

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
    "e6_artist.py": ["-o", "--dry-run", "--pick", "--manifest", "--from-manifest"],
    "pool_scraper.py": ["-o"],
    "e621.py": ["-o"],
    "yiff_scraper.py": ["-o", "--limit", "--proxy"],
    "yiff_auto_scraper.py": ["-o", "--limit", "--proxy", "--max-pages", "--headless"],
    "EH_scraper_v2.py": ["-o", "--limit", "--proxy", "-w", "-d", "--cooldown", "--force",
                         "--no-preflight", "--dry-run", "--pick", "--pages",
                         "--from-manifest", "--manifest"],
    # --dry-run：FA_scraper.py 本身支持，之前漏在白名单外，GUI 勾了也被丢掉
    "FA_scraper.py": ["-o", "--limit", "--proxy", "-w", "-d", "--cookies", "--dry-run"],
    "B_scraper.py": ["-o", "--limit", "--proxy", "--adult", "--name", "--retry", "--dry-run",
                     "--mode", "--page", "--skip-others", "--pool-rev", "--force-pool-check",
                     "--delay", "--jitter", "--cooldown", "--force", "--no-preflight"],
    "W_scraper.py": ["-o", "--limit"],
    "H_scraper.py": ["-o", "--limit", "--proxy", "--adult", "--name", "--dry-run", "--page",
                     "--delay", "--jitter", "--cooldown", "--force", "--no-preflight"],
    "R_scraper.py": ["-o", "--limit", "--proxy", "--dry-run", "--page",
                     "--delay", "--jitter", "--cooldown", "--force", "--no-preflight"],
}


def build_command(site: str, args) -> list:
    """根据站点与参数构造子进程命令。"""
    script = None
    pos_args = []

    if site in ("e621", "e926"):
        if not args.mode:
            raise ValueError(i18n.t("tool_err_need_mode", site=site))
        script = E621_SCRIPTS[args.mode]
        if args.mode in ("tags", "page", "artist"):
            if args.mode == "artist":
                # 艺术家模式支持 --from-manifest（从名单挑着下），此时可不给 --tags
                if not (args.tags or args.from_manifest):
                    raise ValueError(i18n.t("tool_err_artist_need"))
                if args.tags:
                    pos_args += ["--tags", args.tags]
                if args.skip_others:
                    pos_args += ["--skip-others"]
            else:
                if not args.tags:
                    raise ValueError(i18n.t("tool_err_mode_need_tags"))
                pos_args += ["--tags", args.tags]
                if args.mode == "page" and args.page:
                    pos_args += ["--page", str(args.page)]
        else:
            if not args.target:
                raise ValueError(i18n.t("tool_err_need_pool_url"))
            pos_args += [args.target]

    elif site == "yiff":
        if not args.target:
            raise ValueError(i18n.t("tool_err_yiff_need"))
        if args.auto:
            script = "yiff_auto_scraper.py"
            pos_args += [args.target]
        else:
            script = "yiff_scraper.py"
            pos_args += [args.target]

    elif site == "ehentai":
        script = "EH_scraper_v2.py"
        if args.tags:
            pos_args += ["--tags", args.tags]          # 标签搜索
        elif args.target:
            pos_args += [args.target]                  # 单画廊
        # --from-manifest / --manifest / --pick / --pages 由下面的白名单透传处理
        if not (args.tags or args.target or args.from_manifest):
            raise ValueError(i18n.t("tool_err_ehentai_need"))

    elif site == "fa":
        if not args.target:
            raise ValueError(i18n.t("tool_err_fa_need"))
        script = "FA_scraper.py"
        pos_args += [args.target]

    elif site == "bbooru":
        script = "B_scraper.py"
        if args.tags and args.pool:
            raise ValueError(i18n.t("tool_err_bbooru_exclusive"))
        if args.pool:
            pos_args += ["--pool", args.pool]          # 合集：show 页 URL 或纯 id
            if args.pool_rev:
                pos_args += ["--pool-rev"]
        elif args.tags:
            pos_args += ["--tags", args.tags]
            if args.mode and args.mode != "tags":
                pos_args += ["--mode", args.mode]          # artist 模式
            if args.page is not None:
                pos_args += ["--page", str(args.page)]
            if args.skip_others:
                pos_args += ["--skip-others"]
            if args.force_pool_check:
                pos_args += ["--force-pool-check"]
        else:
            raise ValueError(i18n.t("tool_err_bbooru_need"))
        # bbooru 的并发参数是 --threads，把通用 -w 映射过去
        if args.workers:
            pos_args += ["--threads", str(args.workers)]

    elif site == "wilddream":
        if not args.target:
            raise ValueError(i18n.t("tool_err_wilddream_need"))
        script = "W_scraper.py"
        pos_args += [args.target]
        # wilddream 的并发参数是 --threads，把通用 -w 映射过去
        if args.workers:
            pos_args += ["--threads", str(args.workers)]

    elif site == "hypnohub":
        if not args.tags:
            raise ValueError(i18n.t("tool_err_hypnohub_need"))
        script = "H_scraper.py"
        pos_args += ["--tags", args.tags]
        if args.page is not None:
            pos_args += ["--page", str(args.page)]
        # H_scraper 的并发参数是 --threads，把通用 -w 映射过去
        if args.workers:
            pos_args += ["--threads", str(args.workers)]

    elif site == "rule34us":
        if not args.tags:
            raise ValueError(i18n.t("tool_err_rule34us_need"))
        script = "R_scraper.py"
        pos_args += ["--tags", args.tags]
        if args.page is not None:
            pos_args += ["--page", str(args.page)]
        # R_scraper 的并发参数是 --threads，把通用 -w 映射过去
        if args.workers:
            pos_args += ["--threads", str(args.workers)]

    else:
        raise ValueError(i18n.t("tool_err_unknown_site", site=site))

    # ⚠️ 站点名 -> 目录名。不要想当然：目录用的是**带连字符/全称**的写法
    #    （sites/e-hentai/、sites/furaffinity/），漏掉的会拼出不存在的路径。
    site_dir = {"bbooru": "BBooru", "hypnohub": "hypnohub", "rule34us": "rule34us",
                "ehentai": "e-hentai", "fa": "furaffinity"}.get(site, site)
    if site in ("e621", "e926"):
        site_dir = "e621"
    cmd = [sys.executable, str(HERE / "sites" / site_dir / script)] + pos_args

    # 按白名单透传通用参数；不支持的参数给出警告（防止"以为限制了其实全下"）
    allowed = set(WHITELIST.get(script, []))
    def _add(flag, value):
        if value is not None and value is not False:
            if flag in allowed:
                if flag in ("--headless", "--force", "--no-preflight", "--dry-run"):
                    cmd.extend([flag])
                else:
                    cmd.extend([flag, str(value)])
            else:
                print(i18n.t("tool_warn_unsupported", script=script, flag=flag), file=sys.stderr)
    _add("-o", args.output or str(common.local_out_root()))
    _add("--limit", args.limit)
    _add("--proxy", args.proxy)
    if site not in ("bbooru", "wilddream", "hypnohub", "rule34us"):   # 这些站的 -w 已在上面映射为 --threads
        _add("-w", args.workers)
    # 延时参数的名字不统一：EH/FA 用 -d（随机延迟上限），
    # bbooru/hypnohub/rule34us 用 --delay（基准）+ --jitter（抖动）。
    # 换算关系：EH/FA 的 `-d N` ≡ bbooru 系的 `--delay 0 --jitter N`。
    if script in ("EH_scraper_v2.py", "FA_scraper.py"):
        _add("-d", args.delay)
    else:
        _add("--delay", args.delay)
    _add("--jitter", getattr(args, "jitter", None))
    _add("--cooldown", getattr(args, "cooldown", None))
    _add("--force", getattr(args, "force", False))
    _add("--no-preflight", getattr(args, "no_preflight", False))
    _add("--dry-run", getattr(args, "dry_run", False))
    _add("--pick", getattr(args, "pick", None))
    _add("--pages", getattr(args, "pages", None))
    _add("--from-manifest", getattr(args, "from_manifest", None))
    _add("--manifest", getattr(args, "manifest", None))
    _add("--cookies", args.cookies)
    _add("--max-pages", args.max_pages)
    _add("--headless", args.headless)
    return cmd


def main():
    parser = argparse.ArgumentParser(description=i18n.t("tool_desc"))
    parser.add_argument("site",
                        choices=["e621", "e926", "yiff", "ehentai", "fa", "bbooru", "wilddream", "hypnohub", "rule34us"],
                        help=i18n.t("tool_help_site"))
    # e621 模式（也是 bbooru 模式选择）
    parser.add_argument("--mode", choices=["tags", "page", "artist", "pool", "pool-rev", "auto", "api", "html"],
                        help=i18n.t("tool_help_mode"))
    parser.add_argument("--tags", help=i18n.t("tool_help_tags"))
    parser.add_argument("--pool", default=None,
                        help=i18n.t("tool_help_pool"))
    parser.add_argument("--page", type=int,
                        help=i18n.t("tool_help_page"))
    parser.add_argument("--skip-others", action="store_true",
                        help=i18n.t("tool_help_skip_others"))
    parser.add_argument("--pool-rev", action="store_true", help=i18n.t("tool_help_pool_rev"))
    parser.add_argument("--force-pool-check", action="store_true",
                        help=i18n.t("tool_help_force_pool_check"))
    parser.add_argument("target", nargs="?",
                        help=i18n.t("tool_help_target"))
    # 通用
    parser.add_argument("-o", "--output", default=None, help=i18n.t("tool_help_output"))
    parser.add_argument("--limit", default=None, help=i18n.t("tool_help_limit"))
    parser.add_argument("--proxy", default=None, help=i18n.t("tool_help_proxy"))
    parser.add_argument("-w", "--workers", type=int, default=None, help=i18n.t("tool_help_workers"))
    parser.add_argument("-d", "--delay", type=float, default=None,
                        help=i18n.t("tool_help_delay"))
    parser.add_argument("--jitter", type=float, default=None,
                        help=i18n.t("tool_help_jitter"))
    parser.add_argument("--cooldown", type=float, default=None,
                        help=i18n.t("tool_help_cooldown"))
    parser.add_argument("--force", action="store_true",
                        help=i18n.t("tool_help_force"))
    parser.add_argument("--no-preflight", action="store_true",
                        help=i18n.t("tool_help_no_preflight"))
    parser.add_argument("--dry-run", action="store_true",
                        help=i18n.t("tool_help_dry_run"))
    parser.add_argument("--pick", default=None,
                        help=i18n.t("tool_help_pick"))
    parser.add_argument("--pages", default=None,
                        help=i18n.t("tool_help_pages"))
    parser.add_argument("--from-manifest", default=None, metavar="FILE",
                        help=i18n.t("tool_help_from_manifest"))
    parser.add_argument("--manifest", default=None,
                        help=i18n.t("tool_help_manifest"))
    parser.add_argument("--cookies", default=None, help=i18n.t("tool_help_cookies"))
    # yiff 自动版
    parser.add_argument("--auto", action="store_true", help=i18n.t("tool_help_auto"))
    parser.add_argument("--max-pages", type=int, default=None, help=i18n.t("tool_help_max_pages"))
    parser.add_argument("--headless", action="store_true", help=i18n.t("tool_help_headless"))
    args = parser.parse_args()

    if args.site == "e926":
        print(i18n.t("tool_e926_unavailable"))
        print(i18n.t("tool_e926_hint"))
        sys.exit(1)

    try:
        cmd = build_command(args.site, args)
    except ValueError as e:
        print(i18n.t("tool_param_error", e=e))
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
        print(i18n.t("tool_interrupted"))
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
