#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
i18n_sites_fa.py — furaffinity + yiff 站点脚本的词条子表
============================================================

由 i18n.py 自动合并，不要直接 import；不要 import i18n。

key 前缀：
    fa_  furaffinity（sites/furaffinity/FA_scraper.py, FA_get_cookies.py）
    yf_  yiff（sites/yiff/yiff_scraper.py, yiff_auto_scraper.py）
"""

# ============================================================
# furaffinity
# ============================================================

ZH_FA = {
    # ---------- 交互提示 ----------
    "fa_prompt_username": "FA 用户名: ",
    "fa_prompt_password": "FA 密码: ",
    "fa_err_no_drissionpage": "未找到 DrissionPage。请先激活装了 DrissionPage 的 conda 环境（示例：conda activate py39）",

    # ---------- 非交互环境（GUI 起的子进程）----------
    # 这些是**给人看**的文案：不提 stdin / EOF / traceback / gitignore 这类实现细节，
    # 只说"缺什么"和"怎么办"。技术原因记在 BUGS.md 的 B10。
    "fa_err_no_tty": "FA（FurAffinity）需要登录才能下载。请先提供账号，方法任选一种：",
    "fa_err_no_tty_hint": "  · 界面里填：站点选 fa → 下方「FA 凭据」填账号和密码 → 再点「开始」\n"
                          "  · 用 cookie：在命令行窗口运行 sites/furaffinity/FA_get_cookies.py 导出"
                          " fa_cookies.json，\n"
                          "    再把导出文件填进「FA 凭据」的 cookie 文件一格\n"
                          "  · 命令行：加 --user 账号 --pass 密码，或 --cookies 指定 cookie 文件\n"
                          "已经填了账号还看到这句？多半是密码不对，或者被 FA 的验证码挡住了。",
    "fa_getcookie_no_tty": "这个脚本只能在命令行窗口里运行：它需要你输入账号密码，"
                           "还会打开浏览器等你完成验证码。",

    # ---------- FA_get_cookies.py：浏览器出口 / 人机验证 ----------
    # 这几条解释「为什么导出的 cookie 拿回去还是用不了」。只讲现象和下一步，不写实现细节。
    "fa_browser_proxy": "浏览器将通过 {proxy} 访问 FA，与下载脚本走同一个出口。",
    "fa_browser_direct": "浏览器直连（没有用代理）。如果下载脚本走代理，导出的文件可能用不上 —— "
                         "两边的出口必须一致。",
    "fa_proxy_dead": "代理 {proxy} 连不上。请先打开 Clash；如果你本来就不想用代理，"
                     "加 --proxy off 重跑，并让下载脚本也加 --proxy off。",
    "fa_challenge_in_browser": "浏览器停在了人机验证页面。请在窗口里点一下通过验证，"
                               "脚本会继续等你 —— 不用关窗口，也不用重开。"
                               "如果反复点都过不去，那多半是这个节点被 Cloudflare 盯上了，"
                               "换一个节点再试。",
    "fa_ua_saved": "已记下浏览器的身份标识，下载脚本会自动使用同一个 —— "
                   "两边报不同身份的话，通行证会被立刻作废。",
    "fa_ua_loaded": "已套用导出时记录的浏览器身份标识。",
    "fa_err_browser_start": "浏览器没能启动。",
    "fa_err_browser_start_hint": "请先关掉所有 Edge / Chrome 窗口再重跑；"
                                 "如果还是不行，删掉 sites\\furaffinity\\.fa_profile 这个文件夹后重试。",
    "fa_cookies_expiry_hint": "这个文件里的通行证和「当前节点 + 浏览器版本」绑定，"
                              "换节点或隔一段时间后要重新导出一次。",

    "fa_site_offline": "FA 整站下线维护中 —— 这不是你的网络、代理或 cookie 的问题，"
                       "换节点、重新导 cookie 都没用。",
    "fa_site_offline_hint": "站点修好会自己恢复；过一阵再跑一次就行。",
    "fa_err_cloudflare": "FA 现在要求浏览器验证（Cloudflare 人机检测），脚本被挡在门外 —— "
                         "这不是账号密码的问题。",
    "fa_err_cloudflare_hint": "请先运行 sites/furaffinity/FA_get_cookies.py：它会打开真浏览器帮你过掉"
                              "验证并导出 fa_cookies.json，再把该文件填进「FA 登录」的 cookie 文件一格"
                              "（命令行用 --cookies）。换个代理节点有时也能绕过。"
                              "刚导出过还是这句？说明通行证过期或中途换过节点，重新导一次就行。",
    "fa_creds_loaded": "使用已保存的账号（无需重新输入）。",
    "fa_cookie_from_creds": "使用 cookie 文件: {path}",
    "fa_cookie_auto": "已找到之前导出的 cookie 文件，自动使用: {path}",

    # ---------- FA_scraper.py：登录 ----------
    "fa_logging_in": "正在登录 furaffinity.net ...",
    "fa_login_rejected": "登录被拒（FA 返回错误码）。",
    "fa_login_captcha": "检测到登录页有验证码：FA 要求真人验证，纯脚本登录无法通过。",
    "fa_login_cookies_hint1": "请改用 cookies 模式：先运行  FA_get_cookies.py  导出 cookies，",
    "fa_login_cookies_hint2": "再用  --cookies fa_cookies.json  参数运行本脚本。",
    "fa_login_bad_credentials": "账号或密码可能不正确，请检查后重试。",
    "fa_login_ok": "登录成功。",
    "fa_login_unconfirmed": "登录状态无法确认（可能仍被验证码拦截），请改用 cookies 模式。",
    "fa_err_login_request": "登录请求失败: {e}",
    "fa_err_cookies_read": "读取 cookies 文件失败: {e}",
    "fa_cookies_loaded": "已加载 {count} 条 cookies（来源: {path}）",

    # ---------- FA_scraper.py：抓取 / 下载 ----------
    "fa_err_parse_id": "「{id}」既不是作品地址，也不是作品编号。"
                       "请填作品页地址（形如 https://www.furaffinity.net/view/12345678/），"
                       "或者直接填那串数字。",
    "fa_err_parse_target": "「{id}」看不出是作品还是作者。可以填：作品的完整地址"
                           "（…/view/12345678/）、作品编号（12345678）、作者名（如 someartist），"
                           "或作者的画廊地址（…/gallery/someartist/）。",
    "fa_gallery_empty": "抓不到 {artist} 的任何作品：画廊是空的，或者这个名字不存在。",
    "fa_artist_target": "作者: {artist}（将下载整个画廊，并按标题分组）",
    "fa_groups_total": "\n共 {total} 张，按标题归成 {n} 组：",
    "fa_group_line": "  [{i:2d}] {name}  —— {n} 张",
    "fa_summary_gallery": "作者: {artist} | 存进 {groups} 个目录",
    "fa_limit_hint": "还有 {rest} 张没下（受数量上限限制）。要全部，把数量上限填 inf。",
    "fa_err_gallery_page": "  抓取 {path} 第 {page} 页失败: {e}",
    "fa_gallery_page": "  {path} 第 {page} 页: {n} 项（累计 {total}）",
    "fa_page_no_new": "  {path} 第 {page} 页没有新内容，停止翻页",
    "fa_skip_exists": "  #{vid} -> {name} 已存在，跳过",
    "fa_err_no_image": "  #{vid} 未取到图片链接（可能未登录或不是图片）",
    "fa_skip_not_image": "  #{vid} 非图片类型(.{ext})，跳过",
    "fa_err_empty_file": "空文件",
    "fa_done": "  #{vid} -> {name} 完成",
    "fa_err_download": "  #{vid} 下载失败: {e}",

    # ---------- FA_scraper.py：命令行 ----------
    "fa_cli_desc": "FurAffinity 系列作品爬虫（登录+系列识别）",
    "fa_help_url": "作品地址、作品编号，或作者名 —— 填作者名会下载他的整个画廊",
    "fa_help_output": "保存目录（默认用作者名 / 系列名）",
    "fa_help_workers": "并发线程数（默认4）",
    "fa_help_delay": "随机延迟上限秒（默认1.0）",
    "fa_help_limit": "下载数量: 正整数 或 inf(全部)；不填默认只下载前 120 个",
    "fa_help_proxy": "代理: 留空=自动检测, off=直连, 或 http://127.0.0.1:7897",
    "fa_help_user": "FA 用户名（或用环境变量 FA_USERNAME）",
    "fa_help_pass": "FA 密码（或用环境变量 FA_PASSWORD；不推荐命令行明文）",
    "fa_help_cookies": "cookies 文件（FA_get_cookies.py 导出），登录被验证码拦截时用这个",
    "fa_help_dry_run": "只列出会下载哪些，不实际下载",
    "fa_help_just_this": "只下载这一张，不找系列",
    "fa_help_all": "输入是作品时，也下载该作者的整个画廊（按标题分组）",

    # ---------- FA_scraper.py：运行期 ----------
    "fa_submission_id": "作品 ID: {id}",
    "fa_proxy_enabled": "已启用代理: {proxy}",
    "fa_proxy_direct": "未使用代理（直连）",
    "fa_err_fetch_page": "获取作品页失败: {e}",
    "fa_err_no_title": "无法解析作品标题，请检查 URL。",
    "fa_submission_title": "作品: {title}",
    "fa_err_no_artist": "无法解析作者，请检查页面结构。",
    "fa_artist": "作者: {artist}",
    "fa_series_key": "系列名（归一化）: {name!r}",
    "fa_crawling_gallery": "正在抓取作者画廊以查找同系列作品...",
    "fa_err_crawl_gallery": "抓取画廊失败: {e}",
    "fa_no_series_match": "画廊里没有找到同系列的其他作品（可能只有这一张）。",
    "fa_series_total": "\n系列共 {n} 张:",
    "fa_series_item": "  {i:3d} #{vid} 序号={num}  {title}",
    "fa_dry_run_done": "\n[dry-run] 识别完成，未下载。",
    "fa_download_plan": "\n下载前 {n} 张（{workers} 线程，延迟 0~{delay}s）",
    "fa_done_title": "\n===== 下载完成 =====",
    "fa_summary_series": "系列: {series} | 作者: {artist}",
    "fa_summary_counts": "成功: {ok} | 失败: {fail}",
    "fa_saved_to": "文件保存至: {path}",

    # ---------- FA_get_cookies.py ----------
    "fa_opening_browser": "正在打开浏览器（请勿关闭窗口）...",
    "fa_autofill_ok": "已自动填写账号密码。",
    "fa_autofill_failed": "自动填写没能生效，请在本窗口手动填一次账号密码再点登录。",
    "fa_already_logged_in": "浏览器里还留着上次的登录态，已跳过登录，直接导出。",
    "fa_err_challenge_stuck": "等了两分钟仍停在人机验证上，先退出。换一个节点再试一次。",
    "fa_captcha_hint": "若出现验证码/人机验证，请在本窗口手动完成；登录后脚本会自动保存 cookies ...",
    "fa_waiting_login": "  等待登录完成... ({sec}s)",
    "fa_login_timeout": "等待超时：未能确认登录成功，cookies 未导出。",
    "fa_cookies_saved": "\ncookies 已保存到: {path}",
    "fa_cookies_next_hint": "共 {n} 条。之后运行: python FA_scraper.py URL --cookies fa_cookies.json",

    # ========================================================
    # yiff
    # ========================================================
    # ---------- yiff_scraper.py：命令行 ----------
    "yf_cli_desc": "下载 yiffverse.com 指定标签的最新图片/视频",
    "yf_help_tag": "标签名，例如 feline 或 jack-jackal_(character)",
    "yf_help_output": "保存目录（默认以标签名命名）",
    "yf_help_limit": "下载数量: 正整数 或 inf(全部)；不填默认只下载前 120 个",
    "yf_help_proxy": "代理设置: 留空=自动检测, off=直连, 或 http://127.0.0.1:7897",

    # ---------- yiff_scraper.py：运行期 ----------
    "yf_err_download": "  下载 {id} 失败: {e}",
    "yf_tag": "标签: {tag}",
    "yf_note1": "注意: yiffverse 服务端每个标签只渲染最新约 30 个帖子（分页在客户端实现），",
    "yf_note2": "      本脚本只能下载到最新约 30 个作品。",
    "yf_proxy_enabled": "已启用代理: {proxy}",
    "yf_proxy_direct": "未使用代理（直连）",
    "yf_fetching_tag_page": "正在获取标签页 {url} ...",
    "yf_err_fetch_tag_page": "获取标签页失败: {e}",
    "yf_no_posts": "没有解析到任何帖子（标签可能不存在或页面结构已变化）。",
    "yf_limit": "下载数量上限: {n}",
    "yf_parsed": "解析到 {n} 个帖子 (图片 {images}，视频 {videos})",
    "yf_resume": "检测到已有 {n} 个文件，从序号 {start} 继续下载",
    "yf_skip_exists": "[{idx}] #{pid} 已存在，跳过",
    "yf_err_no_original": "[{idx}] #{pid} 未找到原文件，跳过",
    "yf_skip_exists_named": "[{idx}] #{pid} -> {name} 已存在，跳过",
    "yf_downloading": "[{idx}/{total}] 下载 #{pid} -> {name}",
    "yf_done_title": "\n===== 下载完成 =====",
    "yf_summary_downloaded": "成功下载: {n}",
    "yf_summary_skipped": "已存在跳过: {n}",
    "yf_summary_failed": "失败: {n}",
    "yf_saved_to": "文件保存至: {path}",

    # ---------- yiff_auto_scraper.py ----------
    "yf_round": "第 {page} 轮: 解析 {n} 个新帖子（累计 {total}）",
    "yf_scroll_done": "滚动后没有新帖子，加载结束。",
    "yf_max_rounds": "已达最大轮数 {n}，停止。",
    "yf_auto_desc": "yiffverse 全量标签爬虫（浏览器翻页版）",
    "yf_auto_help_tag": "标签名，例如 feline",
    "yf_help_max_pages": "最多翻页数（每页约30帖）",
    "yf_help_headless": "无头模式（不弹浏览器窗口）",
    "yf_help_list_only": "只列出帖子，不下载",
    "yf_auto_help_proxy": "代理: 留空=自动, off=直连, 或 http://127.0.0.1:7897",
    "yf_help_browser": "浏览器可执行文件路径（默认自动用 Edge，其次 Chrome）",
    "yf_auto_tag": "标签: {tag}（浏览器滚动加载模式，最多 {n} 轮）",
    "yf_starting_browser": "正在启动浏览器（DrissionPage）...",
    "yf_open_url": "打开 {url}",
    "yf_no_posts_collected": "没有收集到任何帖子（标签可能不存在）。",
    "yf_collected": "\n共收集 {n} 个帖子（图片 {images}，视频 {videos}）",
    "yf_list_item": "  {i:4d} #{pid} [{kind}]",
}


# ============================================================
# English
# ============================================================

EN_FA = {
    # ---------- prompts ----------
    "fa_prompt_username": "FA username: ",
    "fa_prompt_password": "FA password: ",
    "fa_err_no_drissionpage": "DrissionPage not found. Please activate a conda environment that has DrissionPage installed (e.g. conda activate py39)",

    # ---------- non-interactive environment (child process launched by the GUI) ----------
    # User-facing copy: no stdin / EOF / traceback / gitignore jargon - only "what is missing"
    # and "what to do". The technical write-up lives in BUGS.md (B10).
    "fa_err_no_tty": "FA (FurAffinity) requires a login before it will download anything. "
                     "Provide an account in one of these ways:",
    "fa_err_no_tty_hint": "  - In the app: set Site to fa, fill in Username and Password under "
                          "\"FA credentials\", then press Start\n"
                          "  - With cookies: run sites/furaffinity/FA_get_cookies.py in a command prompt "
                          "to export fa_cookies.json,\n"
                          "    then point the \"Cookie file\" field at it\n"
                          "  - On the command line: add --user NAME --pass PASSWORD, or --cookies FILE\n"
                          "Already filled in an account and still seeing this? The password is probably "
                          "wrong, or FA is showing you a captcha.",
    "fa_getcookie_no_tty": "This script only runs in a command prompt: it asks for your credentials "
                           "and opens a browser window so you can solve the captcha.",

    # ---------- FA_get_cookies.py: browser egress / human check ----------
    "fa_browser_proxy": "The browser will reach FA through {proxy} - the same exit as the downloader.",
    "fa_browser_direct": "The browser is going direct (no proxy). If the downloader uses a proxy the "
                         "exported file may not work - both sides must share one exit.",
    "fa_proxy_dead": "Cannot reach the proxy at {proxy}. Start Clash first; if you really want no proxy, "
                     "rerun with --proxy off and give the downloader --proxy off as well.",
    "fa_challenge_in_browser": "The browser is sitting on the human check page. Click through it in the "
                               "window - the script keeps waiting, no need to close or restart it. "
                               "If repeated clicks never get through, this node is likely flagged by "
                               "Cloudflare - try another node.",
    "fa_ua_saved": "Recorded the browser's identity; the downloader will reuse the same one - "
                   "two different identities would void the pass immediately.",
    "fa_ua_loaded": "Using the browser identity recorded at export time.",
    "fa_err_browser_start": "The browser failed to start.",
    "fa_err_browser_start_hint": "Close all Edge / Chrome windows and run it again; if that still fails, "
                                 "delete the sites\\furaffinity\\.fa_profile folder and retry.",
    "fa_cookies_expiry_hint": "The pass inside this file is tied to the current node and browser version, "
                              "so export it again after switching nodes or waiting a while.",

    "fa_site_offline": "Fur Affinity is down for maintenance right now - this is not a network, "
                       "proxy or cookie problem, so switching nodes or re-exporting cookies won't help.",
    "fa_site_offline_hint": "The site comes back on its own; just run it again later.",
    "fa_err_cloudflare": "FA is behind a browser challenge (Cloudflare) and is turning the request "
                         "away - this is not a password problem.",
    "fa_err_cloudflare_hint": "Run sites/furaffinity/FA_get_cookies.py first: it opens a real browser, "
                              "lets you pass the challenge and exports fa_cookies.json - then point the "
                              "\"Cookie file\" field at it (or use --cookies on the command line). "
                              "Switching to another proxy node sometimes gets around it too. "
                              "Exported it just now and still seeing this? The pass expired or the node "
                              "changed - export again.",
    "fa_creds_loaded": "Using the saved account (no prompt).",
    "fa_cookie_from_creds": "Using cookie file: {path}",
    "fa_cookie_auto": "Found a previously exported cookie file, using it automatically: {path}",

    # ---------- FA_scraper.py: login ----------
    "fa_logging_in": "Logging in to furaffinity.net ...",
    "fa_login_rejected": "Login rejected (FA returned an error code).",
    "fa_login_captcha": "A captcha was detected on the login page: FA requires human verification, so a plain script cannot log in.",
    "fa_login_cookies_hint1": "Please use cookies mode instead: run  FA_get_cookies.py  first to export cookies,",
    "fa_login_cookies_hint2": "then run this script with the  --cookies fa_cookies.json  argument.",
    "fa_login_bad_credentials": "The username or password may be incorrect; please check and try again.",
    "fa_login_ok": "Login successful.",
    "fa_login_unconfirmed": "Could not confirm the login state (the captcha may still be blocking); please use cookies mode.",
    "fa_err_login_request": "Login request failed: {e}",
    "fa_err_cookies_read": "Failed to read the cookies file: {e}",
    "fa_cookies_loaded": "Loaded {count} cookies (source: {path})",

    # ---------- FA_scraper.py: fetching / downloading ----------
    "fa_err_parse_id": "\"{id}\" is neither a submission URL nor a submission ID. "
                       "Pass the page URL (e.g. https://www.furaffinity.net/view/12345678/) "
                       "or just the number.",
    "fa_err_parse_target": "\"{id}\" does not look like a submission or an artist. You can pass a full "
                           "submission URL (.../view/12345678/), a submission ID (12345678), an "
                           "artist name (e.g. someartist), or a gallery URL (.../gallery/someartist/).",
    "fa_gallery_empty": "No works found for {artist}: the gallery is empty, or the name does not exist.",
    "fa_artist_target": "Artist: {artist} (will download the whole gallery, grouped by title)",
    "fa_groups_total": "\n{total} item(s) in {n} group(s) by title:",
    "fa_group_line": "  [{i:2d}] {name}  - {n} item(s)",
    "fa_summary_gallery": "Artist: {artist} | saved into {groups} folder(s)",
    "fa_limit_hint": "{rest} item(s) left out by the download cap. Set the limit to inf for everything.",
    "fa_err_gallery_page": "  Failed to fetch page {page} of {path}: {e}",
    "fa_gallery_page": "  {path} page {page}: {n} items ({total} so far)",
    "fa_page_no_new": "  {path} page {page} had nothing new, stopping",
    "fa_skip_exists": "  #{vid} -> {name} already exists, skipped",
    "fa_err_no_image": "  #{vid} no image link found (not logged in, or not an image)",
    "fa_skip_not_image": "  #{vid} not an image (.{ext}), skipped",
    "fa_err_empty_file": "empty file",
    "fa_done": "  #{vid} -> {name} done",
    "fa_err_download": "  #{vid} download failed: {e}",

    # ---------- FA_scraper.py: command line ----------
    "fa_cli_desc": "FurAffinity series scraper (login + series detection)",
    "fa_help_url": "Submission URL / ID, or an artist name - an artist name downloads the whole gallery",
    "fa_help_output": "Output directory (named after the artist / series by default)",
    "fa_help_workers": "Number of worker threads (default 4)",
    "fa_help_delay": "Max random delay in seconds (default 1.0)",
    "fa_help_limit": "How many to download: a positive integer or inf (all); defaults to the first 120",
    "fa_help_proxy": "Proxy: empty = auto-detect, off = direct, or http://127.0.0.1:7897",
    "fa_help_user": "FA username (or the FA_USERNAME environment variable)",
    "fa_help_pass": "FA password (or the FA_PASSWORD environment variable; plain text on the command line is discouraged)",
    "fa_help_cookies": "Cookies file (exported by FA_get_cookies.py); use it when login is blocked by a captcha",
    "fa_help_dry_run": "List what would be downloaded without downloading anything",
    "fa_help_just_this": "Download only this submission, do not look for the series",
    "fa_help_all": "When the input is a submission, download the artist's whole gallery instead (grouped by title)",

    # ---------- FA_scraper.py: runtime ----------
    "fa_submission_id": "Submission ID: {id}",
    "fa_proxy_enabled": "Proxy enabled: {proxy}",
    "fa_proxy_direct": "No proxy (direct connection)",
    "fa_err_fetch_page": "Failed to fetch the submission page: {e}",
    "fa_err_no_title": "Cannot parse the submission title; please check the URL.",
    "fa_submission_title": "Submission: {title}",
    "fa_err_no_artist": "Cannot parse the artist; please check the page structure.",
    "fa_artist": "Artist: {artist}",
    "fa_series_key": "Series name (normalized): {name!r}",
    "fa_crawling_gallery": "Crawling the artist gallery to find other works in the same series...",
    "fa_err_crawl_gallery": "Failed to crawl the gallery: {e}",
    "fa_no_series_match": "No other works in this series were found in the gallery (there may be only this one).",
    "fa_series_total": "\n{n} item(s) in the series:",
    "fa_series_item": "  {i:3d} #{vid} part={num}  {title}",
    "fa_dry_run_done": "\n[dry-run] done, nothing downloaded.",
    "fa_download_plan": "\nDownloading the first {n} item(s) ({workers} threads, delay 0~{delay}s)",
    "fa_done_title": "\n===== Download complete =====",
    "fa_summary_series": "Series: {series} | Artist: {artist}",
    "fa_summary_counts": "Succeeded: {ok} | Failed: {fail}",
    "fa_saved_to": "Files saved to: {path}",

    # ---------- FA_get_cookies.py ----------
    "fa_opening_browser": "Opening the browser (do not close the window)...",
    "fa_autofill_ok": "Username and password filled in automatically.",
    "fa_autofill_failed": "Auto-fill did not take; please type the credentials and click login in the window.",
    "fa_already_logged_in": "The browser still holds a previous login, so login was skipped and cookies exported directly.",
    "fa_err_challenge_stuck": "Still stuck on the human check after two minutes, so it stopped here. Try again with another node.",
    "fa_captcha_hint": "If a captcha / human check appears, complete it manually in this window; the script will save the cookies automatically after login ...",
    "fa_waiting_login": "  Waiting for login... ({sec}s)",
    "fa_login_timeout": "Timed out: could not confirm a successful login; cookies were not exported.",
    "fa_cookies_saved": "\ncookies saved to: {path}",
    "fa_cookies_next_hint": "{n} cookies in total. Then run: python FA_scraper.py URL --cookies fa_cookies.json",

    # ========================================================
    # yiff
    # ========================================================
    # ---------- yiff_scraper.py: command line ----------
    "yf_cli_desc": "Download the latest images/videos of a tag from yiffverse.com",
    "yf_help_tag": "Tag name, e.g. feline or jack-jackal_(character)",
    "yf_help_output": "Output directory (named after the tag by default)",
    "yf_help_limit": "How many to download: a positive integer or inf (all); defaults to the first 120",
    "yf_help_proxy": "Proxy: empty = auto-detect, off = direct, or http://127.0.0.1:7897",

    # ---------- yiff_scraper.py: runtime ----------
    "yf_err_download": "  Failed to download {id}: {e}",
    "yf_tag": "Tag: {tag}",
    "yf_note1": "Note: yiffverse renders only the newest ~30 posts per tag on the server (paging happens on the client),",
    "yf_note2": "      so this script can only download the newest ~30 items.",
    "yf_proxy_enabled": "Proxy enabled: {proxy}",
    "yf_proxy_direct": "No proxy (direct connection)",
    "yf_fetching_tag_page": "Fetching the tag page {url} ...",
    "yf_err_fetch_tag_page": "Failed to fetch the tag page: {e}",
    "yf_no_posts": "No posts were parsed (the tag may not exist or the page structure has changed).",
    "yf_limit": "Download limit: {n}",
    "yf_parsed": "Parsed {n} posts (images {images}, videos {videos})",
    "yf_resume": "Found {n} existing file(s), resuming from index {start}",
    "yf_skip_exists": "[{idx}] #{pid} already exists, skipped",
    "yf_err_no_original": "[{idx}] #{pid} original file not found, skipped",
    "yf_skip_exists_named": "[{idx}] #{pid} -> {name} already exists, skipped",
    "yf_downloading": "[{idx}/{total}] downloading #{pid} -> {name}",
    "yf_done_title": "\n===== Download complete =====",
    "yf_summary_downloaded": "Downloaded: {n}",
    "yf_summary_skipped": "Skipped (already exists): {n}",
    "yf_summary_failed": "Failed: {n}",
    "yf_saved_to": "Files saved to: {path}",

    # ---------- yiff_auto_scraper.py ----------
    "yf_round": "Round {page}: parsed {n} new posts ({total} so far)",
    "yf_scroll_done": "No new posts after scrolling; loading finished.",
    "yf_max_rounds": "Reached the maximum number of rounds ({n}), stopping.",
    "yf_auto_desc": "yiffverse full tag scraper (browser paging)",
    "yf_auto_help_tag": "Tag name, e.g. feline",
    "yf_help_max_pages": "Max number of rounds (about 30 posts per page)",
    "yf_help_headless": "Headless mode (no browser window)",
    "yf_help_list_only": "List the posts only, do not download",
    "yf_auto_help_proxy": "Proxy: empty = auto, off = direct, or http://127.0.0.1:7897",
    "yf_help_browser": "Browser executable path (defaults to Edge, then Chrome)",
    "yf_auto_tag": "Tag: {tag} (browser scroll mode, up to {n} rounds)",
    "yf_starting_browser": "Starting the browser (DrissionPage)...",
    "yf_open_url": "Opening {url}",
    "yf_no_posts_collected": "No posts were collected (the tag may not exist).",
    "yf_collected": "\nCollected {n} posts (images {images}, videos {videos})",
    "yf_list_item": "  {i:4d} #{pid} [{kind}]",
}
