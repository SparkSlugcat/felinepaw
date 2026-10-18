#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""i18n 子表：其余站点脚本（e-hentai / wilddream / hypnohub / rule34us）。

由 i18n.py 自动合并，不要直接 import；不要 import i18n。
key 前缀：eh_ = e-hentai，wd_ = wilddream，hy_ = hypnohub。
"""

# ============================================================
# 中文词条
# ============================================================

ZH_MISC = {
    # ---------- 抓取器（sites/e-hentai/EH_scraper_v2.py） ----------
    "eh_err_parse_url": "无法从 URL 解析 gid/token: {url}",
    "eh_proxy_auto": "自动选中本地代理 {url}（--proxy 可覆盖）",
    "eh_search_page": "  搜索第 {page} 页: 解析 {got} 条（新增 {fresh}，累计 {total}{cap}）",
    "eh_gallery_links_page": "  画廊第 {page} 页: {n} 个链接（累计 {total}）",
    "eh_gallery_links_enough": "  已够 {n} 张，停止翻页",
    "eh_manifest_write_failed": "名单写入失败：{err}",
    "eh_manifest_not_found": "找不到名单文件：{path}",
    "eh_manifest_unreadable": "名单文件读不了（{kind}）：{err}",
    "eh_results_title": "\n===== 搜索结果{summary} =====",
    "eh_results_summary": "（共 {total} 个{note}）",
    "eh_col_pages": "页数",
    "eh_col_category": "分类",
    "eh_col_title": "标题",
    "eh_results_footer": "  （共 {n} 个。用 --pick 2-4,7 挑着下，编号就是上面的 #）",
    "eh_image_list_title": "\n===== 图片名单（共 {n} 张）=====",
    "eh_desc": "e-hentai 画廊下载器 v3（单画廊 / 标签搜索 / dry-run / 挑着下）",
    "eh_epilog_examples": "示例:",
    "eh_epilog_note": "--limit / --pick 作用于「当次名单」:\n"
                      "  搜索模式 = 搜出来的画廊;  单画廊模式 = 画廊里的图片\n",
    "eh_help_url": "画廊 URL，例如 https://e-hentai.org/g/3817181/3b0370c5a1/",
    "eh_help_tags": "标签搜索（与 URL 二选一）。语法: language:chinese$ / female:feline / "
                    "-male:feline / ~feline，空格分隔多个",
    "eh_help_output": "保存目录。留空 = 读项目根 .pawout（无则当前目录）; "
                      "搜索模式作为根目录，单画廊作为该画廊目录",
    "eh_help_output_nopawout": "保存目录（搜索模式: 根目录; 单画廊: 该画廊目录）",
    "eh_help_limit": "搜索模式: 取前 N 个画廊（默认 {n}，inf=全部）; "
                     "单画廊模式: 下前 N 张图（默认 120）",
    "eh_help_pick": "按名单序号挑着下，如 2-4,7 / 3- / all（编号 = dry-run 看到的 #）",
    "eh_help_pages": "搜索模式专用: 每个画廊最多下 N 张图（默认 inf=全部）",
    "eh_help_dry_run": "只拉名单不下载（同时把名单写进 --manifest 指的文件）",
    "eh_help_manifest": "--dry-run 保存名单的文件名（默认 eh_manifest.json）",
    "eh_help_from_manifest": "从这个名单文件读结果，跳过搜索请求（配合 --pick 精确复现）",
    "eh_help_workers": "并发线程数（默认4）",
    "eh_help_delay": "每次请求前的随机延迟上限秒（默认1.0）。e-hentai 风控较紧，别调太小",
    "eh_help_cooldown": "吃到 429/503 时全体线程一起安静的秒数，默认 20",
    "eh_help_force": "重新下载已存在的图（默认：存在就跳过）",
    "eh_help_proxy": "代理: 留空=自动检测, off=直连, 或 http://127.0.0.1:7897",
    "eh_help_no_preflight": "跳过发包前的代理预检",
    "eh_err_fetch_gallery_indent": "  获取画廊页面失败：{err}",
    "eh_err_fetch_gallery": "获取画廊页面失败: {err}",
    "eh_err_no_links_indent": "  未找到任何图片链接（画廊可能已被删除或需要登录）。",
    "eh_err_no_links": "未找到任何图片链接（画廊可能已被删除或需要登录）。",
    "eh_pages_limited": "  --pages {pages}：本画廊只取下前 {n} 张",
    "eh_output_dir_indent": "  输出目录: {path}",
    "eh_output_dir": "输出目录: {path}",
    "eh_err_pages_invalid": "--pages 需要是正整数或 inf。",
    "eh_skip_exists": "  [{idx}] 已存在，跳过",
    "eh_err_no_img_src": "详情页未找到图片 src",
    "eh_err_empty_file": "下载文件为空",
    "eh_done_progress": "  #{idx} 完成 -> {name}（进度 {done}/{total}）",
    "eh_job_failed": "  [{idx}] 失败: {err}",
    "eh_need_url_or_tags": "请给出画廊 URL 或 --tags 标签（二选一）。",
    "eh_example_url": '  例：python EH_scraper_v2.py "https://e-hentai.org/g/xxx/yyy/"',
    "eh_example_tags": '  例：python EH_scraper_v2.py --tags "language:chinese$" '
                       "--limit 30 --dry-run",
    "eh_example_manifest": "  例：python EH_scraper_v2.py --from-manifest "
                           "eh_manifest.json --pick 2-4,7",
    "eh_proxy_enabled": "已启用代理: {proxy}",
    "eh_proxy_direct": "未使用代理（直连）—— e-hentai 境内通常直连不通，不通就加 "
                       "--proxy http://127.0.0.1:7897",
    "eh_manifest_no_images": "名单里没有图片。",
    "eh_manifest_read_images": "从名单读回 {n} 张图：{title}",
    "eh_pick_images": "--pick 挑出 {n} 张（文件名用原始序号）",
    "eh_download_done": "\n===== 下载完成 =====",
    "eh_summary_counts": "成功: {ok} | 跳过: {skip} | 失败: {fail}",
    "eh_saved_to": "文件保存至: {path}",
    "eh_manifest_read_galleries": "从名单读回 {n} 个画廊（原搜索: {query}）",
    "eh_query_unrecorded": "(未记录)",
    "eh_manifest_no_galleries": "名单里没有画廊。",
    "eh_limit_capped": "--limit 太大，搜到 {n} 个就够了（硬上限 {cap}）。",
    "eh_search_start": "\n搜索: {query}",
    "eh_search_target": "目标: 收前 {n} 个画廊",
    "eh_search_failed": "搜索请求失败：{err}",
    "eh_search_empty": "没搜到任何画廊。检查一下标签写法（如 language:chinese$）。",
    "eh_manifest_saved": "\n名单已保存: {path}",
    "eh_manifest_next_hint": "下次可用: python {prog} --from-manifest {manifest} --pick 2-4,7",
    "eh_pick_galleries": "\n--pick 挑出 {n} 个画廊: {idx}",
    "eh_output_root": "\n输出根目录: {path}",
    "eh_all_done": "\n===== 全部完成 =====",
    "eh_galleries_selected": "画廊: 选中 {n} 个",
    "eh_images_summary": "图片: 成功 {ok} | 跳过 {skip} | 失败 {fail}",
    "eh_saved_root": "保存至: {path}",
    "eh_gallery_meta": "画廊标题: {title} | 文件数: {count} | 分类: {category}",
    "eh_gallery_tags": "标签: {tags}",
    "eh_gallery_meta_missing": "gdata API 未返回信息，回退用 URL 命名目录。",
    "eh_fetching_links": "正在翻页抓取图片详情页链接...",
    "eh_pick_images_in_limit": "--pick 挑出 {n} 张（在名单前 {limit} 张里挑；"
                               "文件名用原始序号 {idx}）",
    "eh_download_plan": "共 {n} 张图片（下载上限 {limit}），{workers} 线程，"
                        "随机延迟 0~{delay}s",
    "eh_gallery_summary": "画廊: {title} (gid={gid})",

    # ---------- WildDream（sites/wilddream/W_scraper.py） ----------
    "wd_retry_warn": "  [WARN] 请求失败({e})，{n} 秒后重试…",
    "wd_collected_posts": "共收集到 {n} 个帖子",
    "wd_warn_no_image": "  [WARN] 无主图，跳过: {url}",
    "wd_skip_exists": "已存在，跳过: {name}",
    "wd_saved": "已保存: {name}",
    "wd_download_failed": "下载失败: {name} ({err})",
    "wd_desc": "下载 WildDream 用户的某个漫画文件夹",
    "wd_help_url": "画廊 URL，例如 https://www.wilddream.net/art/userpage/gallery?userpagename=...&folderid=485",
    "wd_help_limit": "最多下载张数：数字 或 inf(全部)；默认 80",
    "wd_help_output": "输出根目录（默认当前目录），会在其下建 <漫画名>/ 子文件夹",
    "wd_help_threads": "下载并发线程数，默认 8",
    "wd_limit_invalid": "--limit 需要是正整数或 inf，已按默认 80 处理",
    "wd_all_posts": "下载全部 post",
    "wd_first_posts": "下载前 {n} 个 post",
    "wd_comic_name": "漫画：{name}",
    "wd_no_posts": "没有收集到任何帖子，退出。",
    "wd_download_dir": "下载目录：{path}",
    "wd_task_error": "  [FAIL] {url} 处理异常：{err}",
    "wd_summary": "完成：成功 {ok}，已存在跳过 {skip}，失败 {fail}",

    # ---------- HypnoHub（sites/hypnohub/H_scraper.py） ----------
    "hy_desc": "从 hypnohub.net 按标签批量下载原图（HTML only，不支持 JSON API）",
    "hy_help_tags": "标签，多个用空格分开，如 'cute fox' 或 landscape",
    "hy_help_limit": "下载数量: 正整数 或 inf(全部)；不填默认只下载前 120 个",
    "hy_help_adult": "是否包含成人内容（y=是，n=否），默认 y。n 时原图会被站点隐藏",
    "hy_help_name": "自定义下载文件夹名称，默认与 --tags 相同",
    "hy_help_output": "输出根目录，默认为当前目录",
    "hy_help_threads": "并发线程数（翻页+下载），默认 8",
    "hy_help_retry": "单个任务失败重试次数，默认 2",
    "hy_help_force": "重新下载已存在的图片（默认跳过；用于修复下到一半的坏文件）",
    "hy_help_proxy": "代理: 留空=自动检测, off=直连, 或 http://127.0.0.1:7897",
    "hy_help_dry_run": "只收集列表，不下载（用于测试翻页）",
    "hy_help_page": "指定只下载某一页（从 1 开始）",
}


# ============================================================
# 英文词条（key 必须与 ZH_MISC 一一对应）
# ============================================================

EN_MISC = {
    # ---------- 抓取器 ----------
    "eh_err_parse_url": "Cannot parse gid/token from URL: {url}",
    "eh_proxy_auto": "Auto-selected local proxy {url} (override with --proxy)",
    "eh_search_page": "  Search page {page}: parsed {got} (new {fresh}, total {total}{cap})",
    "eh_gallery_links_page": "  Gallery page {page}: {n} links (total {total})",
    "eh_gallery_links_enough": "  Reached {n} images, stop paging",
    "eh_manifest_write_failed": "Failed to write manifest: {err}",
    "eh_manifest_not_found": "Manifest file not found: {path}",
    "eh_manifest_unreadable": "Cannot read manifest ({kind}): {err}",
    "eh_results_title": "\n===== Search results{summary} =====",
    "eh_results_summary": " ({total} total{note})",
    "eh_col_pages": "Pages",
    "eh_col_category": "Category",
    "eh_col_title": "Title",
    "eh_results_footer": "  ({n} total. Use --pick 2-4,7 to pick some; "
                         "the number is the # above)",
    "eh_image_list_title": "\n===== Image list ({n} images) =====",
    "eh_desc": "e-hentai gallery downloader v3 (single gallery / tag search / dry-run / pick)",
    "eh_epilog_examples": "Examples:",
    "eh_epilog_note": "--limit / --pick apply to the current list:\n"
                      "  search mode = galleries found;  single gallery mode = images "
                      "in the gallery\n",
    "eh_help_url": "Gallery URL, e.g. https://e-hentai.org/g/3817181/3b0370c5a1/",
    "eh_help_tags": "Tag search (either this or URL). Syntax: language:chinese$ / "
                    "female:feline / -male:feline / ~feline, space-separated",
    "eh_help_output": "Save directory. Blank = read .pawout in the project root "
                      "(else current dir); in search mode it is the root, in single "
                      "gallery mode it is that gallery's folder",
    "eh_help_output_nopawout": "Save folder (search mode: root dir; single gallery: "
                               "that gallery's dir)",
    "eh_help_limit": "Search mode: take the first N galleries (default {n}, inf=all); "
                     "single gallery mode: download the first N images (default 120)",
    "eh_help_pick": "Pick by list index, e.g. 2-4,7 / 3- / all "
                    "(index = the # shown by dry-run)",
    "eh_help_pages": "Search mode only: at most N images per gallery (default inf=all)",
    "eh_help_dry_run": "Only fetch the list, do not download (also writes the list to "
                       "the file given by --manifest)",
    "eh_help_manifest": "File name used by --dry-run to save the list "
                        "(default eh_manifest.json)",
    "eh_help_from_manifest": "Read the result from this manifest, skipping the search "
                             "request (use with --pick for exact reproduction)",
    "eh_help_workers": "Number of concurrent threads (default 4)",
    "eh_help_delay": "Max random delay in seconds before each request (default 1.0). "
                     "e-hentai rate-limits aggressively, do not set it too low",
    "eh_help_cooldown": "Seconds all threads stay quiet after a 429/503, default 20",
    "eh_help_force": "Re-download images that already exist (default: skip if present)",
    "eh_help_proxy": "Proxy: blank=auto detect, off=direct, or http://127.0.0.1:7897",
    "eh_help_no_preflight": "Skip the proxy preflight check before sending requests",
    "eh_err_fetch_gallery_indent": "  Failed to fetch gallery page: {err}",
    "eh_err_fetch_gallery": "Failed to fetch gallery page: {err}",
    "eh_err_no_links_indent": "  No image links found (the gallery may be deleted or "
                              "require login).",
    "eh_err_no_links": "No image links found (the gallery may be deleted or "
                       "require login).",
    "eh_pages_limited": "  --pages {pages}: only the first {n} images of this gallery",
    "eh_output_dir_indent": "  Output dir: {path}",
    "eh_output_dir": "Output dir: {path}",
    "eh_err_pages_invalid": "--pages must be a positive integer or inf.",
    "eh_skip_exists": "  [{idx}] already exists, skipped",
    "eh_err_no_img_src": "No image src found on the detail page",
    "eh_err_empty_file": "Downloaded file is empty",
    "eh_done_progress": "  #{idx} done -> {name} (progress {done}/{total})",
    "eh_job_failed": "  [{idx}] failed: {err}",
    "eh_need_url_or_tags": "Please give a gallery URL or --tags (one of the two).",
    "eh_example_url": '  e.g.: python EH_scraper_v2.py "https://e-hentai.org/g/xxx/yyy/"',
    "eh_example_tags": '  e.g.: python EH_scraper_v2.py --tags "language:chinese$" '
                       "--limit 30 --dry-run",
    "eh_example_manifest": "  e.g.: python EH_scraper_v2.py --from-manifest "
                           "eh_manifest.json --pick 2-4,7",
    "eh_proxy_enabled": "Proxy enabled: {proxy}",
    "eh_proxy_direct": "No proxy (direct connection) - e-hentai usually cannot be "
                       "reached directly from within China; if it fails, add "
                       "--proxy http://127.0.0.1:7897",
    "eh_manifest_no_images": "No images in the manifest.",
    "eh_manifest_read_images": "Read {n} images from manifest: {title}",
    "eh_pick_images": "--pick selected {n} images (original index used as filename)",
    "eh_download_done": "\n===== Download complete =====",
    "eh_summary_counts": "OK: {ok} | skipped: {skip} | failed: {fail}",
    "eh_saved_to": "Files saved to: {path}",
    "eh_manifest_read_galleries": "Read {n} galleries from manifest "
                                  "(original search: {query})",
    "eh_query_unrecorded": "(not recorded)",
    "eh_manifest_no_galleries": "No galleries in the manifest.",
    "eh_limit_capped": "--limit too large, {n} is enough (hard cap {cap}).",
    "eh_search_start": "\nSearch: {query}",
    "eh_search_target": "Target: collect the first {n} galleries",
    "eh_search_failed": "Search request failed: {err}",
    "eh_search_empty": "No galleries found. Check the tag syntax "
                       "(e.g. language:chinese$).",
    "eh_manifest_saved": "\nManifest saved: {path}",
    "eh_manifest_next_hint": "Next time: python {prog} --from-manifest {manifest} "
                             "--pick 2-4,7",
    "eh_pick_galleries": "\n--pick selected {n} galleries: {idx}",
    "eh_output_root": "\nOutput root: {path}",
    "eh_all_done": "\n===== All done =====",
    "eh_galleries_selected": "Galleries: {n} selected",
    "eh_images_summary": "Images: OK {ok} | skipped {skip} | failed {fail}",
    "eh_saved_root": "Saved to: {path}",
    "eh_gallery_meta": "Gallery title: {title} | files: {count} | category: {category}",
    "eh_gallery_tags": "Tags: {tags}",
    "eh_gallery_meta_missing": "gdata API returned nothing; falling back to naming "
                               "the folder from the URL.",
    "eh_fetching_links": "Paging through the gallery to collect image detail links...",
    "eh_pick_images_in_limit": "--pick selected {n} images (out of the first {limit}; "
                               "original index {idx} used as filename)",
    "eh_download_plan": "{n} images in total (download limit {limit}), {workers} "
                        "threads, random delay 0~{delay}s",
    "eh_gallery_summary": "Gallery: {title} (gid={gid})",

    # ---------- WildDream ----------
    "wd_retry_warn": "  [WARN] request failed ({e}), retrying in {n}s...",
    "wd_collected_posts": "Collected {n} posts in total",
    "wd_warn_no_image": "  [WARN] no main image, skipped: {url}",
    "wd_skip_exists": "Already exists, skipped: {name}",
    "wd_saved": "Saved: {name}",
    "wd_download_failed": "Download failed: {name} ({err})",
    "wd_desc": "Download one comic folder of a WildDream user",
    "wd_help_url": "Gallery URL, e.g. https://www.wilddream.net/art/userpage/gallery?userpagename=...&folderid=485",
    "wd_help_limit": "Max images to download: a number or inf (all); default 80",
    "wd_help_output": "Output root directory (default: current directory); a "
                      "<comic name>/ subfolder is created under it",
    "wd_help_threads": "Number of concurrent download threads, default 8",
    "wd_limit_invalid": "--limit must be a positive integer or inf; falling back to "
                        "the default 80",
    "wd_all_posts": "Downloading all posts",
    "wd_first_posts": "Downloading the first {n} posts",
    "wd_comic_name": "Comic: {name}",
    "wd_no_posts": "No posts collected, exiting.",
    "wd_download_dir": "Download directory: {path}",
    "wd_task_error": "  [FAIL] {url} failed: {err}",
    "wd_summary": "Done: {ok} ok, {skip} skipped (already exist), {fail} failed",

    # ---------- HypnoHub ----------
    "hy_desc": "Download original images from hypnohub.net by tag (HTML only, no JSON API)",
    "hy_help_tags": "Tags, separated by spaces, e.g. 'cute fox' or landscape",
    "hy_help_limit": "How many to download: a positive integer or inf (all); default "
                     "is the first 120",
    "hy_help_adult": "Include adult content (y=yes, n=no), default y. With n the "
                     "originals are hidden by the site",
    "hy_help_name": "Custom download folder name, defaults to --tags",
    "hy_help_output": "Output root directory, defaults to the current directory",
    "hy_help_threads": "Number of worker threads (paging + downloading), default 8",
    "hy_help_retry": "Retries per failed task, default 2",
    "hy_help_force": "Re-download existing images (skipped by default; useful for "
                     "repairing partial files)",
    "hy_help_proxy": "Proxy: empty = auto-detect, off = direct, or http://127.0.0.1:7897",
    "hy_help_dry_run": "Collect the list only, do not download (for testing pagination)",
    "hy_help_page": "Download only one page (1-based)",
}
