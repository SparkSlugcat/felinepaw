#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
i18n.py — 中英双语词库 + 语言偏好持久化
=========================================

用法：
    import i18n
    i18n.t("key")               # 当前语言的字符串
    i18n.t("key", n=3)          # 支持 {n} 占位符（str.format 语法）
    i18n.set_lang("en")         # 切语言并记住（写 ~/.paw/felinepaw.lang）

默认语言从哪来（优先级从高到低）：
    1. 环境变量 PAW_LANG —— GUI 起子进程时塞进去的，保证界面和日志同一个语言
    2. ~/.paw/felinepaw.lang —— 用户上次在 GUI 里选的语言
    3. "zh"

词条按用途分段（界面 / 命令行工具 / 公共库 / BBooru 站点），
新增文案时加在自己那段里，别打散。
"""

import os
from pathlib import Path

#: 决定偏好文件路径：~/.paw/<APP_ID>.lang
APP_ID = "felinepaw"
#: GUI 传给子进程的语言通道（环境变量）
LANG_ENV = "PAW_LANG"

LANGS = ("zh", "en")
LANG_NAMES = ("中文", "English")


# ============================================================
# 中文词条
# ============================================================

ZH = {
    # ---------- 界面（felinepaw_gui.py） ----------
    "gui_app_title": "felinepaw 一体化下载器 v0.1",
    # 语言标签故意「反着写」：中文界面显示 Language，英文界面显示 语言。
    # 因为要找切换开关的人，恰恰是看不懂当前界面语言的人。
    "gui_lang_label": "Language:",
    "gui_lang_switched": "已切换界面语言：{lang}",
    "gui_params_frame": " 任务参数 ",
    "gui_site": "站点:",
    "gui_mode_e621": "模式(e621):",
    "gui_mode_bbooru": "模式(bbooru):",
    "gui_mode": "模式:",
    "gui_target_url": "目标网址:",
    # ---- 各站的填写示例（切站时打在日志里 + 常驻在参数区第 7 行）----
    "gui_ex_disabled": "（灰掉的行在这个站用不上）",
    "gui_ex_e621_tags": "示例：标签框填 feline solo，目标网址留空。",
    "gui_ex_e621_page": "示例：标签框填 feline，页码填 2。",
    "gui_ex_e621_artist": "示例：标签框填作者名，如 tom_fischbach。",
    "gui_ex_e621_pool": "示例：目标网址填 https://e621.net/pools/12345 或 12345，标签留空。",
    "gui_ex_e621_poolrev": "示例：同 pool，只是编号倒序。",
    "gui_ex_yiff": "示例：只填标签，如 feline —— yiff 的入口是标签，不是网址。",
    "gui_ex_ehentai": "示例：目标网址填 https://e-hentai.org/g/123456/abcdef1234/；"
                      "或标签框填 language:chinese（两个只填一个）。",
    "gui_ex_fa": "示例：目标网址填作者名（如 someartist，下他的整个画廊，按作品名分目录）；"
                 "或者填作品地址 …/view/12345678/ 或编号 12345678（只下这一个系列）。",
    "gui_ex_bbooru": "示例：标签框填 landscape；或目标网址填合集 123456（两个只填一个）。",
    "gui_ex_wilddream": "示例：目标网址填画廊地址 "
                        "https://www.wilddream.net/art/userpage/gallery?userpagename=xxx&folderid=123",
    "gui_ex_tags_only": "示例：只填标签，如 fox 或 cute dog。",
    "gui_tags": "标签(--tags):",
    "gui_output": "输出目录:",
    "gui_browse": "浏览...",
    "gui_limit": "数量限制:",
    "gui_proxy": "代理:",
    "gui_page": "页码(--page):",
    "gui_skip_others": "artist 跳过非池帖",
    "gui_force_pool": "全量查池",
    "gui_pool_rev": "pool 反转编号",
    "gui_force": "重新下载(--force)",
    "gui_pick": "挑序号(--pick):",
    "gui_pages": "每画廊限张(--pages):",
    "gui_dry_run": "只列名单(--dry-run)",
    "gui_hint": ("提示：代理留空=自动，off=直连；--limit 填 inf 表示全部；"
                 "页码留空=全部；'重新下载' 对 bbooru/hypnohub/rule34us/e-hentai 生效；"
                 "「挑序号」「只列名单」用于 e-hentai（如 2-4,7；"
                 "搜索模式下标作用于画廊，单画廊模式作用于图片）"),

    # ---------- 界面：FA 凭据面板（仅 site == fa 时出现） ----------
    "gui_fa_frame": " FA 登录（仅 fa 站需要） ",
    "gui_fa_user": "账号:",
    "gui_fa_pass": "密码:",
    "gui_fa_cookie": "cookie 文件:",
    "gui_fa_save": "保存账号",
    "gui_fa_saved": "已保存到：{path}\n（明文保存，只在本机生效，不会上传）",
    "gui_fa_save_empty": "账号、密码、cookie 都还是空的，没什么可保存。",
    "gui_fa_loaded": "已载入上次保存的账号",
    "gui_fa_hint": ("账号和密码可以保存下来，下次打开自动填好 —— 明文存在本机，不会上传。"
                    "遇到验证码时，先用 sites/furaffinity/FA_get_cookies.py 导出 cookie，再填进上面一格。"),
    "gui_fa_guide1": "fa 站需要登录：在下方「FA 登录」填账号和密码，或指定 cookie 文件。",
    "gui_fa_guide2": "不填就点「开始」，FA 会拒绝下载。",
    "gui_fa_ready": "已找到可用的登录凭据（账号或 cookie），直接点「开始」就行。"
                    "目标框可以填作者名（下一个人的整个画廊）、作品地址或编号，"
                    "例如 someartist、12345678 或 https://www.furaffinity.net/view/12345678/。",
    "gui_dlg_cookie_file": "选择 cookie 文件",
    "gui_start": "▶ 开始",
    "gui_stop": "■ 停止",
    "gui_idle": "空闲",
    "gui_running": "运行中...",
    "gui_stopping": "正在停止...",
    "gui_stop_requested": "已请求停止",
    "gui_done_status": "完成（退出码 {code}）",
    "gui_process_exit": "[进程结束，退出码 {code}]",
    "gui_log_frame": " 运行日志 ",
    "gui_choose_output_dir": "选择输出目录",
    "gui_tip_title": "提示",
    "gui_task_running": "任务正在运行中",
    "gui_param_error": "参数错误",
    "gui_page_must_be_number": "页码必须填数字（留空表示不限制）",
    "gui_e926_status": "e926 暂不可用（Cloudflare 拦截）",
    "gui_e926_log1": "⚠️ e926 暂不可用：被 Cloudflare 人机挑战拦截，纯 requests 无法访问。",
    "gui_e926_log2": "   请改用 e621，或用浏览器访问 e926。",
    "gui_err_need_tags": "请填写标签栏",
    "gui_err_bbooru_input": "bbooru 需要标签框填标签，或目标网址填合集 URL/编号",
    "gui_err_wilddream_gallery": "wilddream 需要目标网址填画廊地址",
    "gui_err_site_need_tags": "{site} 只吃标签：请填标签框",
    "gui_err_ehentai_input": "ehentai 需要目标网址填画廊地址，或标签框填标签",
    "gui_err_ehentai_both": "标签框和目标网址只能填一个：标签=搜索，网址=单个画廊",

    # ---------- 命令行工具（felinepaw_tool.py） ----------
    "tool_desc": "felinepaw 一体化工具：统一调度 e621/yiff/e-hentai/furaffinity/bbooru/wilddream 脚本",
    "tool_help_site": "站点（e926 为 e621 安全版；bbooru 用 --tags/--pool；wilddream 用画廊 URL；hypnohub/rule34us 用 --tags）",
    "tool_help_mode": "e621/bbooru 下载模式（bbooru: auto/api/html/artist）",
    "tool_help_tags": "标签（e621/bbooru 用）",
    "tool_help_pool": "bbooru 合集：pool show 页 URL 或纯 id（与 --tags 二选一）",
    "tool_help_page": "页码（e621 page 模式 / bbooru / hypnohub / rule34us）",
    "tool_help_skip_others": "艺术家模式跳过非池作品（e621 / bbooru）",
    "tool_help_pool_rev": "pool 反转编号（bbooru）",
    "tool_help_force_pool_check": "bbooru artist 模式：全量查询每个帖子的 pool 归属（默认只查前 10 个）",
    "tool_help_target": "目标：yiff=标签；pool/ehentai/fa=URL；wilddream=画廊 URL",
    "tool_help_output": "保存目录",
    "tool_help_limit": "下载数量: 数字或 inf",
    "tool_help_proxy": "代理: 留空自动/off/URL",
    "tool_help_workers": "并发线程数",
    "tool_help_delay": "请求间隔秒：EH/FA 为随机延时上限；bbooru/hypnohub/rule34us 为基准延时",
    "tool_help_jitter": "在 --delay 基础上叠加的随机抖动秒数（bbooru/hypnohub/rule34us）",
    "tool_help_cooldown": "被限流(429/503)时全部线程一起安静多少秒，默认 20（bbooru/hypnohub/rule34us）",
    "tool_help_force": "重新下载已存在的图片（bbooru/hypnohub/rule34us/ehentai；默认跳过）",
    "tool_help_no_preflight": "跳过发包前的代理预检（bbooru/hypnohub/rule34us/ehentai）",
    "tool_help_dry_run": "只拉名单不下载（e621 artist/bbooru/hypnohub/rule34us/ehentai）",
    "tool_help_pick": "按名单序号挑着下，如 2-4,7（e621 artist/ehentai；编号 = dry-run 看到的 #）",
    "tool_help_pages": "ehentai 搜索模式：每个画廊最多下 N 张图（默认全部）",
    "tool_help_from_manifest": "e621 artist/ehentai：读 dry-run 存的名单文件，跳过搜索（配合 --pick 精确复现）",
    "tool_help_manifest": "e621 artist/ehentai：dry-run 保存名单的文件名（e621 默认 e6_artist_manifest.json，ehentai 默认 eh_manifest.json）",
    "tool_help_cookies": "FA cookies 文件",
    "tool_help_auto": "yiff 用浏览器滚动版",
    "tool_help_max_pages": "yiff 自动版最大滚动轮数",
    "tool_help_headless": "yiff 自动版无头模式",
    "tool_e926_unavailable": "e926 暂不可用：该站被 Cloudflare 人机挑战拦截，纯 requests 无法访问。",
    "tool_e926_hint": "请改用 e621，或用浏览器访问 e926。后续若实现浏览器模式再恢复支持。",
    "tool_param_error": "参数错误: {e}",
    "tool_interrupted": "\n已终止。",
    "tool_warn_unsupported": "⚠️ 警告: 目标脚本 {script} 不支持 {flag}，该参数已忽略",
    "tool_err_need_mode": "{site} 需要 --mode: tags/page/artist/pool/pool-rev",
    "tool_err_artist_need": "艺术家模式需要 --tags <标签> 或 --from-manifest <名单>",
    "tool_err_mode_need_tags": "该模式需要 --tags",
    "tool_err_need_pool_url": "该模式需要 Pool URL，例如: e621 pool https://e621.net/pools/123",
    "tool_err_yiff_need": "yiff 需要标签，例如: yiff feline",
    "tool_err_ehentai_need": "ehentai 需要画廊 URL、--tags <标签> 或 --from-manifest <名单>",
    "tool_err_fa_need": "fa 需要作品 URL",
    "tool_err_bbooru_exclusive": "bbooru 的 --tags 与 --pool 只能二选一",
    "tool_err_bbooru_need": "bbooru 需要 --tags <标签> 或 --pool <show页URL/id>",
    "tool_err_wilddream_need": "wilddream 需要画廊 URL（目标框）",
    "tool_err_hypnohub_need": "hypnohub 需要 --tags <标签>",
    "tool_err_rule34us_need": "rule34us 需要 --tags <标签>",
    "tool_err_unknown_site": "未知站点: {site}（可用: e621/e926/yiff/ehentai/fa/bbooru/wilddream/hypnohub/rule34us）",

    # ---------- 公共库（common.py） ----------
    "common_limit_invalid": "--limit 需要是正整数或 inf。",
    "common_pick_empty": "--pick 是空的。写成 2-4,7 这样的序号（或 all）。",
    "common_pick_none_left": "--pick 挑完之后一个都不剩。",
    "common_help_delay": "每次请求前的基准延时秒数，默认 0（不限速）。被站点限流时试试 --delay 1.0",
    "common_help_jitter": "在基准延时上叠加的随机抖动秒数，默认 0。配合 --delay 用（如 --delay 1 --jitter 1.5）让节奏不像机器",
    "common_help_cooldown": "吃到 429/503 时让所有线程一起安静多少秒，默认 20",
    "common_help_no_preflight": "跳过发包前的代理预检（默认会先花约 1 秒确认链路，失败时能立刻说清是代理没开还是节点问题）",
    "common_pick_dash": "--pick 里的 '-' 两边至少要有一个数字：{part!r}",
    "common_pick_reversed": "--pick 的区间写反了（{start} > {end}）：{part!r}",
    "common_pick_bad": "--pick 看不懂这一段：{part!r}（支持 2-4,7 / 3- / -3 / all）",
    "common_pick_oob_n": "--pick 里有超出范围的序号已忽略：{n} 个（{first}~{last} 等，当前名单只有 {total} 个）",
    "common_pick_oob_list": "--pick 里有超出范围的序号已忽略：{ids}（当前名单只有 {total} 个）",

    # ---------- BBooru 站点（sites/BBooru/**） ----------
    # GUI 通用
    "bb_app_title": "BBooru 下载器",
    "bb_lang_label": "语言:",
    "bb_lang_switched": "已切换界面语言：{lang}",
    # GUI 参数区
    "bb_params_frame": " 下载参数 ",
    "bb_mode_label": "模式:",
    "bb_mode_tags": "标签 (Tags)",
    "bb_mode_pool": "合集 (Pool)",
    "bb_mode_artist": "艺术家 (Artist)",
    "bb_engine_label": "引擎(tags):",
    "bb_tags_label": "标签 --tags:",
    "bb_pool_label": "合集 --pool:",
    "bb_output_label": "输出目录:",
    "bb_browse": "浏览...",
    "bb_limit_label": "数量 limit:",
    "bb_page_label": "页 --page:",
    "bb_threads_label": "线程:",
    "bb_retry_label": "重试:",
    "bb_adult_label": "成人:",
    "bb_proxy_label": "代理:",
    "bb_pool_rev": "反转 pool 编号(--pool-rev)",
    "bb_skip_others": "跳过非池帖子(--skip-others)",
    "bb_dry_run": "仅收集(--dry-run)",
    "bb_hint": "提示：limit 留空=默认120，填 inf=全部；代理留空=自动检测，off=直连",
    # GUI 按钮 / 状态
    "bb_start": "▶ 开始下载",
    "bb_pick_button": "☑ 挑着下载",
    "bb_stop": "■ 停止",
    "bb_open_output": "打开输出目录",
    "bb_status_ready": "就绪",
    "bb_status_running": "运行中...",
    "bb_status_collecting": "正在收集名单...",
    "bb_status_pick": "挑着下载：勾选后点「下载选中」",
    "bb_status_collect_failed": "收集失败",
    "bb_status_done": "完成",
    "bb_status_stopping": "正在停止（已下载的会保留，可重跑续传）...",
    # GUI 日志 / 对话框
    "bb_log_frame": " 运行日志 ",
    "bb_choose_output_dir": "选择输出目录",
    "bb_tip_title": "提示",
    "bb_dir_is": "目录：{p}",
    "bb_task_running": "任务正在运行中",
    "bb_param_error": "参数错误",
    "bb_err_tags_need": "标签模式请在『标签 --tags』里填写标签",
    "bb_err_pool_need": "合集模式请在『合集 --pool』里填 pool 的 URL 或 id",
    "bb_err_artist_need": "艺术家模式请在『标签 --tags』里填写艺术家标签",
    "bb_exit_code": "[退出码 {code}]",
    "bb_collect_echo": ">>> 先收集名单: ",
    "bb_pick_ignore_dryrun": "[挑着下载] 已忽略「仅收集(--dry-run)」勾选",
    "bb_collect_failed_log": "[收集失败或名单为空，无法挑着下]",
    "bb_collected_log": "[收集到 {n} 项，请在弹窗里勾选]",
    "bb_pick_none": "[没勾任何项，已取消]",
    "bb_pick_start": "[已选 {n} 项，开始下载]",
    "bb_task_end": "[任务结束]",
    "bb_stop_requested": "[已请求停止]",
    # 挑着下载弹窗
    "bb_pick_title": "挑着下载 — 勾选要下载的条目（共 {n} 项）",
    "bb_pick_hint": "把要下载的条目前面勾上，点「下载选中」即可。序号与命令行 --pick 一致。",
    "bb_col_check": "勾",
    "bb_col_folder": "目录",
    "bb_col_url": "地址",
    "bb_pick_all": "全选",
    "bb_pick_clear": "取消全选",
    "bb_pick_invert": "反选",
    "bb_pick_cancel": "取消",
    "bb_pick_confirm": "下载选中",
    "bb_pick_count": "已选 {sel} / {total} 项",
    # 命令行（B_scraper.py --help）
    "bb_cli_desc": "从 bbooru.com 下载原图：--tags 按标签（JSON API 优先），或 --pool 按合集（HTML）",
    "bb_cli_tags": "标签，多个用空格分开，如 'cute fox' 或 landscape（与 --pool 二选一）",
    "bb_cli_pool": "pool 的 show 页 URL 或纯 id，如 https://bbooru.com/index.php?page=pool&s=show&id=123456 或 123456",
    "bb_cli_mode": "下载引擎: auto=API优先失败自动回退HTML(默认), api=强制API, html=强制HTML, artist=Artist模式(需配合--tags)",
    "bb_cli_limit": "下载数量: 正整数 或 inf(全部)；不填默认只下载前 120 个",
    "bb_cli_adult": "是否包含成人内容（y=是，n=否），默认 y。n 时原图会被站点隐藏",
    "bb_cli_name": "自定义下载文件夹名称，默认与 --tags 相同",
    "bb_cli_output": "输出根目录，默认为当前目录",
    "bb_cli_threads": "并发线程数（翻页+下载），默认 8",
    "bb_cli_retry": "单个任务失败重试次数，默认 2",
    "bb_cli_force": "重新下载已存在的图片（默认跳过；用于修复下到一半的坏文件）",
    "bb_cli_proxy": "代理: 留空=自动检测, off=直连, 或 http://127.0.0.1:7897",
    "bb_cli_dry_run": "只列出收集到的条目（带序号），不下载",
    "bb_cli_pick": "只下载挑中的序号，如 2-4,7 / 3- / -3 / all；序号来自 --dry-run 或 GUI「挑着下载」列表",
    "bb_cli_skip_others": "Artist 模式：跳过不属于任何 pool 的帖子（不放入 others/ 文件夹）",
    "bb_cli_page": "配合 --tags 指定只下载 API 翻页的某一页（从 1 开始）",
    # 日志（B_scraper.py 运行期）
    "bb_api_request_failed": "API 请求失败: {e}",
    "bb_api_empty": "API 返回空响应",
    "bb_api_not_json": "API 返回非 JSON（可能被限流/abuse）: {body}",
    "bb_api_bad_json": "API 返回非法 JSON: {e}",
    "bb_api_unknown_struct": "未知 API 结构: {keys}",
    "bb_api_unknown_not_list": "未知 API 结构，不是数组: {data}",
    "bb_err_pool_id": "无法从 {arg!r} 解析 pool id（请给 show 页 URL 或纯数字）",
    "bb_err_no_original": "未找到 '{text}' 链接{hint}",
    "bb_err_adult_hint": "；可能成人内容被隐藏，试试 --adult y",
    "bb_cooldown": "[COOLDOWN] {item}: HTTP 限流，全部线程安静 {sec:.0f}s",
}


# ============================================================
# 英文词条（key 必须与 ZH 一一对应）
# ============================================================

EN = {
    # ---------- 界面 ----------
    "gui_app_title": "felinepaw All-in-One Downloader v0.1",
    # Deliberately flipped: English UI shows 语言, Chinese UI shows Language.
    # Whoever needs this switch is the person who cannot read the current UI language.
    "gui_lang_label": "语言:",
    "gui_lang_switched": "Interface language switched to: {lang}",
    "gui_params_frame": " Task Parameters ",
    "gui_site": "Site:",
    "gui_mode_e621": "Mode (e621):",
    "gui_mode_bbooru": "Mode (bbooru):",
    "gui_mode": "Mode:",
    "gui_target_url": "Target URL:",
    # ---- per-site examples (logged on site switch + shown under the params) ----
    "gui_ex_disabled": "(greyed rows are unused for this site)",
    "gui_ex_e621_tags": "Example: tags = feline solo, leave Target URL empty.",
    "gui_ex_e621_page": "Example: tags = feline, page = 2.",
    "gui_ex_e621_artist": "Example: tags = the artist name, e.g. tom_fischbach.",
    "gui_ex_e621_pool": "Example: Target URL = https://e621.net/pools/12345 or 12345, tags empty.",
    "gui_ex_e621_poolrev": "Example: same as pool, just numbered in reverse.",
    "gui_ex_yiff": "Example: tags only, e.g. feline - yiff takes tags, not a URL.",
    "gui_ex_ehentai": "Example: Target URL = https://e-hentai.org/g/123456/abcdef1234/ ; "
                      "or tags = language:chinese (fill only one).",
    "gui_ex_fa": "Example: Target URL = artist name (e.g. someartist - whole gallery, one folder "
                 "per series); or a submission URL .../view/12345678/ or id 12345678 (that series only).",
    "gui_ex_bbooru": "Example: tags = landscape; or Target URL = pool id 123456 (fill only one).",
    "gui_ex_wilddream": "Example: Target URL = the gallery address "
                        "https://www.wilddream.net/art/userpage/gallery?userpagename=xxx&folderid=123",
    "gui_ex_tags_only": "Example: tags only, e.g. fox or cute dog.",
    "gui_tags": "Tags (--tags):",
    "gui_output": "Output dir:",
    "gui_browse": "Browse...",
    "gui_limit": "Limit:",
    "gui_proxy": "Proxy:",
    "gui_page": "Page (--page):",
    # 英文比中文长一截：同一行四个勾选框全用全称，会把整行撑到 600px 宽，
    # 窗口装不下就把旁边的输入框压扁。这里一律用短称，全称在 --help 里。
    "gui_skip_others": "Skip non-pool posts",
    "gui_force_pool": "All pools",
    "gui_pool_rev": "Reverse order",
    "gui_force": "Re-download",
    "gui_pick": "Pick (--pick):",
    "gui_pages": "Per gallery (--pages):",
    "gui_dry_run": "List only (--dry-run)",
    "gui_hint": ("Tips: empty proxy = auto, off = direct; --limit inf means everything; "
                 "empty page = all pages; 'Re-download' applies to bbooru/hypnohub/rule34us/e-hentai; "
                 "'Pick' and 'List only' are for e-hentai (e.g. 2-4,7; "
                 "in search mode the index picks galleries, in single-gallery mode it picks images)"),

    # ---------- GUI: FA credentials panel (only shown for site == fa) ----------
    "gui_fa_frame": " FA login (site fa only) ",
    "gui_fa_user": "Username:",
    "gui_fa_pass": "Password:",
    "gui_fa_cookie": "Cookie file:",
    "gui_fa_save": "Save account",
    "gui_fa_saved": "Saved to: {path}\n(stored in plain text, this machine only, never uploaded)",
    "gui_fa_save_empty": "Username, password and cookie file are all empty - nothing to save.",
    "gui_fa_loaded": "Loaded the saved account",
    "gui_fa_hint": ("You can save the username and password and they will be filled in next time - "
                    "stored in plain text on this machine only, never uploaded. If you hit a captcha, "
                    "run sites/furaffinity/FA_get_cookies.py to export cookies and put that file in the "
                    "field above."),
    "gui_fa_guide1": "site fa needs a login: fill in the username and password below, or point at a "
                     "cookie file.",
    "gui_fa_guide2": "Starting without either will be rejected by FA.",
    "gui_fa_ready": "A usable login is already in place (account or cookie) - just hit Start. "
                    "The target box takes an artist name (whole gallery), a submission URL or an ID - "
                    "e.g. someartist, 12345678 or https://www.furaffinity.net/view/12345678/.",
    "gui_dlg_cookie_file": "Select cookie file",
    "gui_start": "▶ Start",
    "gui_stop": "■ Stop",
    "gui_idle": "Idle",
    "gui_running": "Running...",
    "gui_stopping": "Stopping...",
    "gui_stop_requested": "Stop requested",
    "gui_done_status": "Done (exit code {code})",
    "gui_process_exit": "[Process exited, code {code}]",
    "gui_log_frame": " Run Log ",
    "gui_choose_output_dir": "Choose output directory",
    "gui_tip_title": "Notice",
    "gui_task_running": "A task is already running",
    "gui_param_error": "Invalid argument",
    "gui_page_must_be_number": "Page must be a number (leave it empty for no limit)",
    "gui_e926_status": "e926 unavailable (blocked by Cloudflare)",
    "gui_e926_log1": "⚠️ e926 unavailable: blocked by a Cloudflare human challenge, plain requests cannot access it.",
    "gui_e926_log2": "   Please use e621 instead, or open e926 in a browser.",
    "gui_err_need_tags": "Fill in the tags box",
    "gui_err_bbooru_input": "bbooru needs tags in the tags box, or a pool URL/id in Target URL",
    "gui_err_wilddream_gallery": "wilddream needs a gallery address in Target URL",
    "gui_err_site_need_tags": "{site} takes tags only: fill the tags box",
    "gui_err_ehentai_input": "ehentai needs a gallery URL in Target URL, or tags in the tags box",
    "gui_err_ehentai_both": "Fill only one: tags = search, Target URL = a single gallery",

    # ---------- 命令行工具 ----------
    "tool_desc": "felinepaw all-in-one tool: one entry point for the e621/yiff/e-hentai/furaffinity/bbooru/wilddream scripts",
    "tool_help_site": "Site (e926 is the safe variant of e621; bbooru uses --tags/--pool; wilddream takes a gallery URL; hypnohub/rule34us use --tags)",
    "tool_help_mode": "Download mode for e621/bbooru (bbooru: auto/api/html/artist)",
    "tool_help_tags": "Tags (used by e621/bbooru)",
    "tool_help_pool": "bbooru pool: pool show page URL or plain id (mutually exclusive with --tags)",
    "tool_help_page": "Page number (e621 page mode / bbooru / hypnohub / rule34us)",
    "tool_help_skip_others": "Artist mode: skip non-pool posts (e621 / bbooru)",
    "tool_help_pool_rev": "Reverse pool numbering (bbooru)",
    "tool_help_force_pool_check": "bbooru artist mode: check the pool membership of every post (by default only the first 10)",
    "tool_help_target": "Target: yiff=tags; pool/ehentai/fa=URL; wilddream=gallery URL",
    "tool_help_output": "Output directory",
    "tool_help_limit": "How many to download: a number or inf",
    "tool_help_proxy": "Proxy: empty = auto / off / URL",
    "tool_help_workers": "Number of worker threads",
    "tool_help_delay": "Seconds between requests: random delay cap for EH/FA; base delay for bbooru/hypnohub/rule34us",
    "tool_help_jitter": "Random jitter in seconds added on top of --delay (bbooru/hypnohub/rule34us)",
    "tool_help_cooldown": "Seconds all threads stay quiet when rate-limited (429/503), default 20 (bbooru/hypnohub/rule34us)",
    "tool_help_force": "Re-download images that already exist (bbooru/hypnohub/rule34us/ehentai; skipped by default)",
    "tool_help_no_preflight": "Skip the proxy preflight before sending requests (bbooru/hypnohub/rule34us/ehentai)",
    "tool_help_dry_run": "Fetch the list only, do not download (e621 artist/bbooru/hypnohub/rule34us/ehentai)",
    "tool_help_pick": "Pick items by list index, e.g. 2-4,7 (e621 artist/ehentai; the # shown by dry-run)",
    "tool_help_pages": "ehentai search mode: max images per gallery (all by default)",
    "tool_help_from_manifest": "e621 artist/ehentai: read the manifest saved by dry-run and skip searching (use with --pick to reproduce exactly)",
    "tool_help_manifest": "e621 artist/ehentai: file name used to save the dry-run manifest (e621 defaults to e6_artist_manifest.json, ehentai to eh_manifest.json)",
    "tool_help_cookies": "FA cookies file",
    "tool_help_auto": "Use the browser-scrolling variant for yiff",
    "tool_help_max_pages": "Max scroll rounds for the yiff auto variant",
    "tool_help_headless": "Headless mode for the yiff auto variant",
    "tool_e926_unavailable": "e926 unavailable: this site is blocked by a Cloudflare human challenge, plain requests cannot access it.",
    "tool_e926_hint": "Please use e621 instead, or open e926 in a browser. Support will resume once a browser mode is implemented.",
    "tool_param_error": "Argument error: {e}",
    "tool_interrupted": "\nTerminated.",
    "tool_warn_unsupported": "⚠️ Warning: target script {script} does not support {flag}; the argument was ignored",
    "tool_err_need_mode": "{site} requires --mode: tags/page/artist/pool/pool-rev",
    "tool_err_artist_need": "Artist mode requires --tags <tags> or --from-manifest <file>",
    "tool_err_mode_need_tags": "This mode requires --tags",
    "tool_err_need_pool_url": "This mode requires a pool URL, e.g.: e621 pool https://e621.net/pools/123",
    "tool_err_yiff_need": "yiff requires tags, e.g.: yiff feline",
    "tool_err_ehentai_need": "ehentai requires a gallery URL, --tags <tags> or --from-manifest <file>",
    "tool_err_fa_need": "fa requires a submission URL",
    "tool_err_bbooru_exclusive": "bbooru: --tags and --pool are mutually exclusive",
    "tool_err_bbooru_need": "bbooru requires --tags <tags> or --pool <show page URL/id>",
    "tool_err_wilddream_need": "wilddream requires a gallery URL (target field)",
    "tool_err_hypnohub_need": "hypnohub requires --tags <tags>",
    "tool_err_rule34us_need": "rule34us requires --tags <tags>",
    "tool_err_unknown_site": "Unknown site: {site} (available: e621/e926/yiff/ehentai/fa/bbooru/wilddream/hypnohub/rule34us)",

    # ---------- 公共库 ----------
    "common_limit_invalid": "--limit must be a positive integer or inf.",
    "common_pick_empty": "--pick is empty. Use an index expression such as 2-4,7 (or all).",
    "common_pick_none_left": "--pick left nothing to download.",
    "common_help_delay": "Base delay in seconds before each request, default 0 (no throttling). Try --delay 1.0 if the site rate-limits you",
    "common_help_jitter": "Random jitter in seconds added to the base delay, default 0. Use it with --delay (e.g. --delay 1 --jitter 1.5) so the pace does not look robotic",
    "common_help_cooldown": "Seconds all threads stay quiet after a 429/503, default 20",
    "common_help_no_preflight": "Skip the proxy preflight before sending requests (by default about 1 second is spent confirming the link, so failures say clearly whether the proxy is not running or the node is bad)",
    "common_pick_dash": "In --pick, '-' needs at least one number on either side: {part!r}",
    "common_pick_reversed": "--pick range is reversed ({start} > {end}): {part!r}",
    "common_pick_bad": "Cannot parse this part of --pick: {part!r} (supported: 2-4,7 / 3- / -3 / all)",
    "common_pick_oob_n": "Ignored {n} out-of-range index(es) in --pick ({first}~{last} etc.; the list has only {total})",
    "common_pick_oob_list": "Ignored out-of-range index(es) in --pick: {ids} (the list has only {total})",

    # ---------- BBooru 站点 ----------
    # GUI 通用
    "bb_app_title": "BBooru Downloader",
    "bb_lang_label": "Language:",
    "bb_lang_switched": "Interface language switched to: {lang}",
    # GUI 参数区
    "bb_params_frame": " Download Parameters ",
    "bb_mode_label": "Mode:",
    "bb_mode_tags": "Tags",
    "bb_mode_pool": "Pool",
    "bb_mode_artist": "Artist",
    "bb_engine_label": "Engine (tags):",
    "bb_tags_label": "Tags --tags:",
    "bb_pool_label": "Pool --pool:",
    "bb_output_label": "Output dir:",
    "bb_browse": "Browse...",
    "bb_limit_label": "Limit:",
    "bb_page_label": "Page --page:",
    "bb_threads_label": "Threads:",
    "bb_retry_label": "Retries:",
    "bb_adult_label": "Adult:",
    "bb_proxy_label": "Proxy:",
    "bb_pool_rev": "Reverse pool order (--pool-rev)",
    "bb_skip_others": "Skip non-pool posts (--skip-others)",
    "bb_dry_run": "Collect only (--dry-run)",
    "bb_hint": "Tips: empty limit = 120 by default, inf = everything; empty proxy = auto-detect, off = direct",
    # GUI 按钮 / 状态
    "bb_start": "▶ Start",
    "bb_pick_button": "☑ Pick & download",
    "bb_stop": "■ Stop",
    "bb_open_output": "Open output folder",
    "bb_status_ready": "Ready",
    "bb_status_running": "Running...",
    "bb_status_collecting": "Collecting list...",
    "bb_status_pick": "Pick & download: tick the items, then click \"Download selected\"",
    "bb_status_collect_failed": "Collection failed",
    "bb_status_done": "Done",
    "bb_status_stopping": "Stopping (downloaded files are kept; rerun to resume)...",
    # GUI 日志 / 对话框
    "bb_log_frame": " Run Log ",
    "bb_choose_output_dir": "Choose output directory",
    "bb_tip_title": "Notice",
    "bb_dir_is": "Directory: {p}",
    "bb_task_running": "A task is already running",
    "bb_param_error": "Invalid argument",
    "bb_err_tags_need": "Tags mode: please fill in the Tags field (--tags)",
    "bb_err_pool_need": "Pool mode: please fill in a pool URL or id in the Pool field (--pool)",
    "bb_err_artist_need": "Artist mode: please fill in an artist tag in the Tags field (--tags)",
    "bb_exit_code": "[Exit code {code}]",
    "bb_collect_echo": ">>> collecting list first: ",
    "bb_pick_ignore_dryrun": "[Pick] ignored the 'Collect only (--dry-run)' checkbox",
    "bb_collect_failed_log": "[Collection failed or the list is empty; cannot pick]",
    "bb_collected_log": "[Collected {n} items; tick them in the dialog]",
    "bb_pick_none": "[Nothing selected, cancelled]",
    "bb_pick_start": "[{n} items selected, starting download]",
    "bb_task_end": "[Task finished]",
    "bb_stop_requested": "[Stop requested]",
    # 挑着下载弹窗
    "bb_pick_title": "Pick & download — tick the items to download ({n} in total)",
    "bb_pick_hint": "Tick the items you want, then click \"Download selected\". The indices match the --pick command line.",
    "bb_col_check": "✓",
    "bb_col_folder": "Folder",
    "bb_col_url": "URL",
    "bb_pick_all": "Select all",
    "bb_pick_clear": "Clear all",
    "bb_pick_invert": "Invert",
    "bb_pick_cancel": "Cancel",
    "bb_pick_confirm": "Download selected",
    "bb_pick_count": "{sel} / {total} selected",
    # 命令行（B_scraper.py --help）
    "bb_cli_desc": "Download original images from bbooru.com: --tags by tag (JSON API preferred), or --pool by pool (HTML)",
    "bb_cli_tags": "Tags, separated by spaces, e.g. 'cute fox' or landscape (mutually exclusive with --pool)",
    "bb_cli_pool": "Pool show-page URL or plain id, e.g. https://bbooru.com/index.php?page=pool&s=show&id=123456 or 123456",
    "bb_cli_mode": "Download engine: auto=API first, fall back to HTML (default), api=force API, html=force HTML, artist=Artist mode (needs --tags)",
    "bb_cli_limit": "How many to download: a positive integer or inf (all); default is the first 120",
    "bb_cli_adult": "Include adult content (y=yes, n=no), default y. With n the originals are hidden by the site",
    "bb_cli_name": "Custom download folder name, defaults to --tags",
    "bb_cli_output": "Output root directory, defaults to the current directory",
    "bb_cli_threads": "Number of worker threads (paging + downloading), default 8",
    "bb_cli_retry": "Retries per failed task, default 2",
    "bb_cli_force": "Re-download existing images (skipped by default; useful for repairing partial files)",
    "bb_cli_proxy": "Proxy: empty = auto-detect, off = direct, or http://127.0.0.1:7897",
    "bb_cli_dry_run": "List the collected items (with indices) without downloading",
    "bb_cli_pick": "Download only the picked indices, e.g. 2-4,7 / 3- / -3 / all; indices come from --dry-run or the GUI pick list",
    "bb_cli_skip_others": "Artist mode: skip posts that belong to no pool (not placed in others/)",
    "bb_cli_page": "With --tags, download only one page of API results (1-based)",
    # 日志（B_scraper.py 运行期）
    "bb_api_request_failed": "API request failed: {e}",
    "bb_api_empty": "API returned an empty response",
    "bb_api_not_json": "API returned non-JSON (possibly rate-limited/abuse): {body}",
    "bb_api_bad_json": "API returned invalid JSON: {e}",
    "bb_api_unknown_struct": "Unknown API structure: {keys}",
    "bb_api_unknown_not_list": "Unknown API structure, not an array: {data}",
    "bb_err_pool_id": "Cannot parse a pool id from {arg!r} (pass a show-page URL or a plain number)",
    "bb_err_no_original": "Could not find the '{text}' link{hint}",
    "bb_err_adult_hint": "; adult content may be hidden, try --adult y",
    "bb_cooldown": "[COOLDOWN] {item}: HTTP rate limit, all threads backing off {sec:.0f}s",
}


# ============================================================
# 合并站点脚本的子表
# ============================================================
# 各站点脚本（sites/**）的日志文案按模块拆成子表，避免几个人同时改本文件。
# 子表缺失不报错（自动跳过），所以少一个不致命。
#   i18n_sites_e621.py → ZH_E621 / EN_E621   e621 及 e621 系（tags/page/artist/pool）
#   i18n_sites_fa.py   → ZH_FA   / EN_FA     furaffinity + yiff
#   i18n_sites_misc.py → ZH_MISC / EN_MISC   其余站点（e-hentai / wilddream / hypnohub / rule34us）

for _mod, _zh_name, _en_name in (
        ("i18n_sites_e621", "ZH_E621", "EN_E621"),
        ("i18n_sites_fa", "ZH_FA", "EN_FA"),
        ("i18n_sites_misc", "ZH_MISC", "EN_MISC")):
    try:
        _m = __import__(_mod)
    except ImportError:
        continue
    ZH.update(getattr(_m, _zh_name, {}) or {})
    EN.update(getattr(_m, _en_name, {}) or {})

try:
    del _mod, _zh_name, _en_name, _m
except NameError:
    pass


# ============================================================
# 语言偏好（跨进程、跨会话）
# ============================================================

def pref_path() -> Path:
    return Path.home() / ".paw" / ("%s.lang" % APP_ID)


def read_pref() -> str:
    """读上次选的语言；没有或不认识就返回空串。"""
    try:
        s = pref_path().read_text(encoding="utf-8").strip().lower()
    except OSError:
        return ""
    return s if s in LANGS else ""


def save_pref(lang: str) -> None:
    """记住选择。写不进去就算了 —— 只读目录（exe 装进 Program Files）不值得报错。"""
    try:
        p = pref_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(lang, encoding="utf-8")
    except OSError:
        pass


def _initial() -> str:
    env = os.environ.get(LANG_ENV, "").strip().lower()
    if env in LANGS:
        return env
    return read_pref() or "zh"


_CURRENT = _initial()


def set_lang(lang: str, persist: bool = True) -> None:
    """切当前语言。

    persist=True（默认）= 同时写偏好文件。GUI 里点下拉框就走这条；
    子进程从不调它（靠 PAW_LANG 环境变量），所以日志不会被"顺手改掉"偏好。
    """
    global _CURRENT
    _CURRENT = lang if lang in LANGS else "zh"
    if persist:
        save_pref(_CURRENT)


def get_lang() -> str:
    return _CURRENT


def t(key: str, **kw) -> str:
    """取当前语言的文案；缺 key 时退化到中文，再退化到 key 本身（便于发现漏翻）。"""
    table = EN if _CURRENT == "en" else ZH
    s = table.get(key)
    if s is None:
        s = ZH.get(key, key)
    if kw:
        try:
            return s.format(**kw)
        except (KeyError, IndexError, ValueError):
            return s
    return s
