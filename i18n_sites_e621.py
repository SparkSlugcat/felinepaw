# -*- coding: utf-8 -*-
"""
i18n_sites_e621.py — e621 系站点脚本（tags / page / artist / pool / pool-rev）的中英词条
=========================================================================================

由 i18n.py 自动合并，不要直接 import；不要 import i18n（会循环依赖）。

覆盖 scripts：sites/e621/e621.py、e6_artist.py、e6_scraper.py、
             e6_taged_page_scraper.py、pool_scraper.py
key 前缀统一 e6_，占位符一律 {} + 关键字参数。
"""

# ============================================================
# 中文词条
# ============================================================

ZH_E621 = {
    # ---------- 通用：登录 / 会话 ----------
    "e6_logged_in": "已使用认证信息登录",
    "e6_guest_mode": "以游客身份访问",
    "e6_guest_limited": "以游客身份访问（部分内容可能受限）",
    "e6_guest_limited_tags": "以游客身份访问（部分标签或原图可能受限）",

    # ---------- 通用：帖子列表 ----------
    "e6_page_fetched": "  第 {page} 页，获取到 {got} 个帖子（累计 {total}）",
    "e6_not_json": "    响应不是 JSON，前200字节: {body}",
    "e6_list_failed_page": "获取帖子列表失败（第 {page} 页）: {e}",
    "e6_wait_retry": "等待 5 秒后重试...",
    "e6_id_list_fetching": "正在获取帖子 ID 列表...",
    "e6_id_list_fetching_paged": "正在获取帖子 ID 列表（可能多页）...",
    "e6_id_list_failed": "获取 ID 列表失败: {e}",
    "e6_no_posts_found": "没有找到匹配的帖子。",
    "e6_total_found": "共找到 {n} 个帖子",
    "e6_search_tags": "搜索标签: {tags}",

    # ---------- 通用：帖子详情 / 批次 ----------
    "e6_posts_detail_fetching": "正在获取帖子详细信息...",
    "e6_batch_n": "  批次 {n} ({start}-{end}/{total})",
    "e6_batch_failed_retry": "批次请求失败: {e}，等待 5 秒重试...",
    "e6_batch_failed_retry_indent": "  批次请求失败: {e}，等待 5 秒后重试...",
    "e6_batch_retry_failed": "重试仍失败: {e}，跳过该批次",
    "e6_batch_retry_failed_indent": "  重试仍失败: {e}，跳过该批次",

    # ---------- 通用：下载 / 汇总 ----------
    "e6_downloadable_and_missing": "可下载: {ok}, 无可用URL: {bad}",
    "e6_downloadable_and_missing_short": "可下载: {ok}, 无URL: {bad}",
    "e6_no_images": "没有可下载的图片。",
    "e6_resume_from": "检测到已有 {n} 个文件，从序号 {start} 继续下载",
    "e6_post_skip_tagged": "[{idx}/{total}] 帖子 #{pid} -> {name} 已存在，跳过",
    "e6_post_skip_plain": "[{idx}] #{pid} -> {name} 已存在，跳过",
    "e6_task_count": "待下载任务数: {n}",
    "e6_post_done": "[{idx}/{total}] 下载帖子 #{pid} -> {name} 完成",
    "e6_post_failed": "[{idx}/{total}] 下载帖子 #{pid} 失败: {err}",
    "e6_done_header": "\n===== 下载完成 =====",
    "e6_tags_line": "标签: {tags}",
    "e6_total_posts_tags": "总计帖子: {n}",
    "e6_downloaded_count": "成功下载: {n}",
    "e6_skipped_count": "已存在跳过: {n}",
    "e6_failed_with_ids": "下载失败: {n} (ID: {ids})",
    "e6_no_url_with_ids": "无可用 URL: {n} (ID: {ids})",
    "e6_saved_to": "文件保存至: {path}",

    # ---------- Pool 类（e621.py / pool_scraper.py） ----------
    "e6_err_pool_id": "无法从 URL 中提取 Pool ID: {url}",
    "e6_err_prefix": "错误: {e}",
    "e6_pool_url_help": "Pool 页面完整 URL，例如 https://e621.net/pools/12345",
    "e6_output_help_pool": "图片保存目录（默认以 Pool 名称命名）",
    "e6_pool_id_parsed": "解析到 Pool ID: {id}",
    "e6_pool_info_fetching": "正在获取 Pool 信息...",
    "e6_pool_info_failed": "获取 Pool 信息失败: {e}",
    "e6_pool_empty": "该 Pool 中没有作品。",
    "e6_pool_name": "Pool 名称: {name}",
    "e6_post_count": "作品数量: {n}",
    "e6_batch_progress_indent": "  获取批次 ({start}-{end}/{total})",
    "e6_downloadable_count": "可下载作品: {n}",
    "e6_no_url_posts": "无文件 URL 的作品: {n} (ID: {ids})",
    "e6_nothing_to_download": "没有可下载的作品，退出。",
    "e6_download_failed_indent": "  下载失败: {e}",
    "e6_pool_id_line": "Pool: {name} (ID: {id})",
    "e6_total_posts": "总计作品: {n}",
    "e6_rev_desc": "下载 e621/e926 指定 Pool 中的所有图片（反转编号）",
    "e6_seq_desc": "下载 e621/e926 指定 Pool 中的所有图片（顺序命名）",
    "e6_err_mkdir": "错误：无法创建输出目录 {path}",
    "e6_mkdir_fallback": "可能包含系统不支持的字符，尝试使用 Pool ID 作为备用目录名...",
    "e6_resume_reverse": "检测到已有 {n} 个文件，从序号 {start} 开始续传（反转顺序）",
    "e6_start_reverse": "开始下载，图片将按 Pool 反转顺序编号：最后一张 → 1.jpg, 倒数第二张 → 2.png ...",
    "e6_post_skip": "[{idx}/{total}] 作品 #{pid} -> {name} 已存在，跳过",
    "e6_post_download": "[{idx}/{total}] 下载作品 #{pid} -> {name}",
    "e6_post_download_plain": "[{idx}/{total}] 下载 #{pid} -> {name}",
    "e6_resume_seq": "检测到已有 {n} 个文件，将从序号 {start} 开始下载",
    "e6_post_skip_seq": "[{idx}/{last}] 作品 #{pid} -> {name} 已存在，跳过",
    "e6_post_download_single": "[{idx}] 下载作品 #{pid} -> {name}",
    "e6_reverse_resume_tip": "提示：反转编号续传时，已保证序号连续。若手动删除中间文件可能导致重复，建议清空目录后重试。",

    # ---------- Tags 类（e6_scraper.py / e6_taged_page_scraper.py） ----------
    "e6_tags_desc": "下载 e621/e926 指定 tags 的所有图片",
    "e6_tags_help": "搜索标签，例如 aubrey_(iceink)",
    "e6_limit_help": "只下载前 N 个帖子",
    "e6_output_help_tags": "图片保存目录（默认为 tags 名称）",
    "e6_page_desc": "下载 e621/e926 指定 tags 的图片",
    "e6_page_tags_help": "搜索标签，例如 aubrey_(iceink) 或带排序的 arcanis_(hahaluckyme) order:hot",
    "e6_page_help": "指定下载第几页（不指定则下载全部）",
    "e6_only_page": "仅下载第 {page} 页",
    "e6_all_pages": "下载所有页面",

    # ---------- 艺术家类（e6_artist.py） ----------
    "e6_post_no_url_skip_indent": "  帖子 #{pid} 无可用 URL，跳过",
    "e6_post_download_failed_indent": "  下载帖子 #{pid} 失败: {err}",
    "e6_batch_info_failed": "批量获取帖子信息失败: {e}",
    "e6_no_post_info_indent": "  没有找到帖子信息",
    "e6_dir_download_summary_indent": "  下载完成：成功 {ok}，失败/跳过 {bad}",
    "e6_manifest_write_failed": "名单写入失败：{e}",
    "e6_manifest_not_found": "找不到名单文件：{path}",
    "e6_manifest_unreadable": "名单文件读不了（{kind}）：{e}",
    "e6_artist_suffix": "（艺术家: {tag}）",
    "e6_artist_unrecorded": "(未记录)",
    "e6_manifest_title": "\n===== 下载名单{suffix} =====",
    "e6_manifest_pool_line": "  {idx:>3}. [pool]   {name}{tag}   （{count} 个作品）",
    "e6_manifest_others_line": "  {idx:>3}. [others] 不属于任何池   （{count} 个作品）",
    "e6_manifest_footer": "  共 {n} 项。用 --pick 1,3 挑着下，编号就是上面的 #",
    "e6_artist_ids_fetching": "正在获取艺术家所有帖子 ID...",
    "e6_posts_detail_for_pools": "正在获取帖子详细信息以提取 Pool 信息...",
    "e6_pools_found": "发现 {pools} 个相关 Pool，{others} 个帖子不属于任何池",
    "e6_pool_info_failed_indent": "  获取 Pool {id} 信息失败: {e}",
    "e6_artist_desc": "下载艺术家作品并按 Pool 分组（含 dry-run 名单 / --pick 挑着下）",
    "e6_artist_epilog": (
        "示例:\n"
        "  {prog} --tags artist_name                    # 全部下载\n"
        "  {prog} --tags artist_name --dry-run          # 只看名单（存 JSON，不下载）\n"
        "  {prog} --tags artist_name --pick 1,3         # 只下名单里的第 1、3 项\n"
        "  {prog} --from-manifest e6_artist_manifest.json --pick 2-4   # 从已存名单挑着下\n"
        "\n"
        "--pick 的编号 = dry-run 打印的 #（Pool 按名称排序，others 固定最后）。\n"
    ),
    "e6_artist_tags_help": "艺术家标签，例如 artist_name",
    "e6_artist_output_help": "输出根目录（默认为艺术家标签名）",
    "e6_skip_others_help": "跳过不属于任何 Pool 的帖子（用 --pick 显式选中 others 时以 --pick 为准）",
    "e6_dry_run_help": "只列名单不下载（同时把名单写进 --manifest 指的文件）",
    "e6_pick_help": "按名单序号挑着下，如 2-4,7 / 3- / all（编号 = dry-run 看到的 #）",
    "e6_manifest_help": "--dry-run 保存名单的文件名（默认 {name}）",
    "e6_from_manifest_help": "从这个名单文件读结果，跳过检索（配合 --pick 精确复现）",
    "e6_need_tags_or_manifest": "请给出 --tags <艺术家标签> 或 --from-manifest <名单文件>（二选一）。",
    "e6_example_dry_run": "  例：python e6_artist.py --tags artist_name --dry-run",
    "e6_example_manifest": "  例：python e6_artist.py --from-manifest {name} --pick 2-4,7",
    "e6_manifest_empty": "名单里没有可下载的项。",
    "e6_manifest_read": "从名单读回 {n} 项（原艺术家: {tag}）",
    "e6_artist_tag": "艺术家标签: {tag}",
    "e6_no_posts_at_all": "没有找到任何帖子。",
    "e6_manifest_saved": "\n名单已保存: {path}",
    "e6_manifest_next_hint": "下次可用: python {prog} --from-manifest {manifest} --pick 1,3",
    "e6_pick_selected": "\n--pick 挑出 {n} 项: {idx}",
    "e6_skip_others_applied": "\n--skip-others 生效：跳过 others（{n} 项）",
    "e6_output_root": "输出根目录: {path}",
    "e6_pool_header": "\n[{seq}/{total}] Pool #{id} {name}",
    "e6_pool_fetch_failed_indent": "  获取 Pool {id} 失败: {e}",
    "e6_others_header": "\n[{seq}/{total}] others",
    "e6_item_no_posts_indent": "  该项没有作品，跳过。",
    "e6_all_done": "\n全部完成！文件保存在:",
}


# ============================================================
# 英文词条（key 必须与 ZH_E621 一一对应）
# ============================================================

EN_E621 = {
    # ---------- 通用：登录 / 会话 ----------
    "e6_logged_in": "Signed in with the configured credentials",
    "e6_guest_mode": "Browsing as a guest",
    "e6_guest_limited": "Browsing as a guest (some content may be restricted)",
    "e6_guest_limited_tags": "Browsing as a guest (some tags or originals may be restricted)",

    # ---------- 通用：帖子列表 ----------
    "e6_page_fetched": "  Page {page}: {got} posts ({total} in total)",
    "e6_not_json": "    Response is not JSON; first 200 bytes: {body}",
    "e6_list_failed_page": "Failed to fetch the post list (page {page}): {e}",
    "e6_wait_retry": "Waiting 5 seconds before retrying...",
    "e6_id_list_fetching": "Fetching the post ID list...",
    "e6_id_list_fetching_paged": "Fetching the post ID list (may span several pages)...",
    "e6_id_list_failed": "Failed to fetch the ID list: {e}",
    "e6_no_posts_found": "No matching posts found.",
    "e6_total_found": "Found {n} posts in total",
    "e6_search_tags": "Search tags: {tags}",

    # ---------- 通用：帖子详情 / 批次 ----------
    "e6_posts_detail_fetching": "Fetching post details...",
    "e6_batch_n": "  Batch {n} ({start}-{end}/{total})",
    "e6_batch_failed_retry": "Batch request failed: {e}; retrying in 5 seconds...",
    "e6_batch_failed_retry_indent": "  Batch request failed: {e}; retrying in 5 seconds...",
    "e6_batch_retry_failed": "Retry failed again: {e}; skipping this batch",
    "e6_batch_retry_failed_indent": "  Retry failed again: {e}; skipping this batch",

    # ---------- 通用：下载 / 汇总 ----------
    "e6_downloadable_and_missing": "Downloadable: {ok}, no usable URL: {bad}",
    "e6_downloadable_and_missing_short": "Downloadable: {ok}, no URL: {bad}",
    "e6_no_images": "No downloadable images.",
    "e6_resume_from": "Found {n} existing files; continuing from index {start}",
    "e6_post_skip_tagged": "[{idx}/{total}] post #{pid} -> {name} already exists, skipped",
    "e6_post_skip_plain": "[{idx}] #{pid} -> {name} already exists, skipped",
    "e6_task_count": "Pending download tasks: {n}",
    "e6_post_done": "[{idx}/{total}] post #{pid} -> {name} done",
    "e6_post_failed": "[{idx}/{total}] post #{pid} failed: {err}",
    "e6_done_header": "\n===== Download complete =====",
    "e6_tags_line": "Tags: {tags}",
    "e6_total_posts_tags": "Total posts: {n}",
    "e6_downloaded_count": "Downloaded: {n}",
    "e6_skipped_count": "Skipped (already existed): {n}",
    "e6_failed_with_ids": "Failed: {n} (ID: {ids})",
    "e6_no_url_with_ids": "No usable URL: {n} (ID: {ids})",
    "e6_saved_to": "Files saved to: {path}",

    # ---------- Pool 类 ----------
    "e6_err_pool_id": "Cannot extract a Pool ID from the URL: {url}",
    "e6_err_prefix": "Error: {e}",
    "e6_pool_url_help": "Full pool page URL, e.g. https://e621.net/pools/12345",
    "e6_output_help_pool": "Image output directory (defaults to the pool name)",
    "e6_pool_id_parsed": "Parsed Pool ID: {id}",
    "e6_pool_info_fetching": "Fetching pool info...",
    "e6_pool_info_failed": "Failed to fetch pool info: {e}",
    "e6_pool_empty": "This pool has no posts.",
    "e6_pool_name": "Pool name: {name}",
    "e6_post_count": "Post count: {n}",
    "e6_batch_progress_indent": "  Fetching batch ({start}-{end}/{total})",
    "e6_downloadable_count": "Downloadable posts: {n}",
    "e6_no_url_posts": "Posts without a file URL: {n} (ID: {ids})",
    "e6_nothing_to_download": "Nothing to download, exiting.",
    "e6_download_failed_indent": "  Download failed: {e}",
    "e6_pool_id_line": "Pool: {name} (ID: {id})",
    "e6_total_posts": "Total posts: {n}",
    "e6_rev_desc": "Download every image of an e621/e926 pool (reverse numbering)",
    "e6_seq_desc": "Download every image of an e621/e926 pool (sequential numbering)",
    "e6_err_mkdir": "Error: cannot create the output directory {path}",
    "e6_mkdir_fallback": "The name may contain characters unsupported by the system; trying the Pool ID as a fallback name...",
    "e6_resume_reverse": "Found {n} existing files; resuming from index {start} (reverse order)",
    "e6_start_reverse": "Starting download; images are numbered in reverse pool order: last one → 1.jpg, second to last → 2.png ...",
    "e6_post_skip": "[{idx}/{total}] post #{pid} -> {name} already exists, skipped",
    "e6_post_download": "[{idx}/{total}] downloading post #{pid} -> {name}",
    "e6_post_download_plain": "[{idx}/{total}] downloading #{pid} -> {name}",
    "e6_resume_seq": "Found {n} existing files; starting from index {start}",
    "e6_post_skip_seq": "[{idx}/{last}] post #{pid} -> {name} already exists, skipped",
    "e6_post_download_single": "[{idx}] downloading post #{pid} -> {name}",
    "e6_reverse_resume_tip": "Note: reverse-numbered resume keeps the indices contiguous. Deleting files in the middle may cause duplicates; clearing the directory and retrying is recommended.",

    # ---------- Tags 类 ----------
    "e6_tags_desc": "Download all images matching the given tags on e621/e926",
    "e6_tags_help": "Search tags, e.g. aubrey_(iceink)",
    "e6_limit_help": "Download only the first N posts",
    "e6_output_help_tags": "Image output directory (defaults to the tag name)",
    "e6_page_desc": "Download images matching the given tags on e621/e926",
    "e6_page_tags_help": "Search tags, e.g. aubrey_(iceink) or with sorting arcanis_(hahaluckyme) order:hot",
    "e6_page_help": "Download only this page (all pages when omitted)",
    "e6_only_page": "Downloading page {page} only",
    "e6_all_pages": "Downloading all pages",

    # ---------- 艺术家类 ----------
    "e6_post_no_url_skip_indent": "  Post #{pid} has no usable URL, skipped",
    "e6_post_download_failed_indent": "  Failed to download post #{pid}: {err}",
    "e6_batch_info_failed": "Failed to fetch post details in batch: {e}",
    "e6_no_post_info_indent": "  No post details found",
    "e6_dir_download_summary_indent": "  Download done: {ok} succeeded, {bad} failed/skipped",
    "e6_manifest_write_failed": "Failed to write the manifest: {e}",
    "e6_manifest_not_found": "Manifest file not found: {path}",
    "e6_manifest_unreadable": "Cannot read the manifest file ({kind}): {e}",
    "e6_artist_suffix": " (artist: {tag})",
    "e6_artist_unrecorded": "(not recorded)",
    "e6_manifest_title": "\n===== Download list{suffix} =====",
    "e6_manifest_pool_line": "  {idx:>3}. [pool]   {name}{tag}   ({count} posts)",
    "e6_manifest_others_line": "  {idx:>3}. [others] in no pool   ({count} posts)",
    "e6_manifest_footer": "  {n} items in total. Use --pick 1,3 to pick; the indices are the # above",
    "e6_artist_ids_fetching": "Fetching all post IDs of the artist...",
    "e6_posts_detail_for_pools": "Fetching post details to extract pool information...",
    "e6_pools_found": "Found {pools} related pools; {others} posts belong to no pool",
    "e6_pool_info_failed_indent": "  Failed to fetch info for pool {id}: {e}",
    "e6_artist_desc": "Download an artist's posts grouped by pool (with a dry-run list and --pick)",
    "e6_artist_epilog": (
        "Examples:\n"
        "  {prog} --tags artist_name                    # download everything\n"
        "  {prog} --tags artist_name --dry-run          # list only (saves JSON, no download)\n"
        "  {prog} --tags artist_name --pick 1,3         # download only items 1 and 3 of the list\n"
        "  {prog} --from-manifest e6_artist_manifest.json --pick 2-4   # pick from a saved manifest\n"
        "\n"
        "--pick indices = the # printed by dry-run (pools sorted by name, others always last).\n"
    ),
    "e6_artist_tags_help": "Artist tag, e.g. artist_name",
    "e6_artist_output_help": "Output root directory (defaults to the artist tag)",
    "e6_skip_others_help": "Skip posts that belong to no pool (an explicit --pick of others still wins)",
    "e6_dry_run_help": "List the manifest without downloading (also writes it to the --manifest file)",
    "e6_pick_help": "Pick items by manifest index, e.g. 2-4,7 / 3- / all (indices = the # shown by dry-run)",
    "e6_manifest_help": "File name used by --dry-run to save the manifest (default {name})",
    "e6_from_manifest_help": "Read results from this manifest file and skip searching (use with --pick to reproduce exactly)",
    "e6_need_tags_or_manifest": "Please provide --tags <artist tag> or --from-manifest <file> (exactly one of them).",
    "e6_example_dry_run": "  e.g. python e6_artist.py --tags artist_name --dry-run",
    "e6_example_manifest": "  e.g. python e6_artist.py --from-manifest {name} --pick 2-4,7",
    "e6_manifest_empty": "The manifest contains no downloadable items.",
    "e6_manifest_read": "Read {n} items from the manifest (original artist: {tag})",
    "e6_artist_tag": "Artist tag: {tag}",
    "e6_no_posts_at_all": "No posts found at all.",
    "e6_manifest_saved": "\nManifest saved: {path}",
    "e6_manifest_next_hint": "Next time use: python {prog} --from-manifest {manifest} --pick 1,3",
    "e6_pick_selected": "\n--pick selected {n} items: {idx}",
    "e6_skip_others_applied": "\n--skip-others applied: skipped others ({n} items)",
    "e6_output_root": "Output root: {path}",
    "e6_pool_header": "\n[{seq}/{total}] Pool #{id} {name}",
    "e6_pool_fetch_failed_indent": "  Failed to fetch pool {id}: {e}",
    "e6_others_header": "\n[{seq}/{total}] others",
    "e6_item_no_posts_indent": "  This item has no posts, skipped.",
    "e6_all_done": "\nAll done! Files saved to:",
}
