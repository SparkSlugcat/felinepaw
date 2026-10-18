#!/usr/bin/env python3
"""
e621/e926 艺术家作品智能分组爬虫（最终版）
- 下载指定艺术家的所有作品，按所属 Pool 分组：
    - 每个 Pool 单独一个文件夹（完整下载池内全部作品）
    - 不属于任何 Pool 的作品放入 others 文件夹
- 可通过 --skip-others 跳过非池作品
- 输出结构：
    艺术家标签/
        Pool名称1/
        Pool名称2/
        ...
        others/          (如果不跳过)
- 支持断点续传、登录认证（环境变量 E621_USER / E621_KEY）、内容不过滤

新功能（v2）——「先看名单，再挑着下」：
    python e6_artist.py --tags artist_name --dry-run          # 只列名单（存 JSON，不下）
    python e6_artist.py --tags artist_name --pick 1,3         # 只下名单第 1、3 项
    python e6_artist.py --from-manifest e6_artist_manifest.json --pick 2-4

名单的每一项 = 一个 Pool 或 others（不是单张图），序号就是 dry-run 打印的 #。
⚠️ 顺序是固定的：Pool 按「名称」排序，others 永远排在最后。
   这样同一个艺术家的名单，两次运行序号一致（否则 --pick 2 会指到不同的池）。
"""

import os
import sys
import json
import time
import argparse
import re
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# ---- 定位并导入共享模块 common.py（felinepaw 基础库） ----
_here = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.dirname(os.path.dirname(_here)), os.path.dirname(_here), _here):
    if os.path.exists(os.path.join(_p, "common.py")):
        sys.path.insert(0, _p)
        break
import common
# i18n 词条表与 common.py 同在项目根，上面的 sys.path 已把它放好
import i18n

# ---------- 配置 ----------
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "DNT": "1",
    "Connection": "keep-alive",
    "Referer": "https://e621.net/",
}
API_BASE = os.environ.get("E621_BASE", "https://e621.net")          # 可改为 https://e926.net
POSTS_PER_REQUEST = 320                # API 单次最大帖子数
REQUEST_DELAY = 1.0                    # API 请求间隔（秒）
MAX_RETRIES = 3
DOWNLOAD_WORKERS = 4                   # 并发下载线程数
MANIFEST_DEFAULT = "e6_artist_manifest.json"   # --dry-run 名单默认文件名

# ===== 登录凭据（环境变量，留空=游客） =====
API_USER = os.environ.get("E621_USER", "")    # e621/e926 用户名
API_KEY = os.environ.get("E621_KEY", "")      # 完整 API Key
# ===================================================

# --------------------------

def create_session(proxy=None):
    """创建带重试和认证的会话"""
    session = common.create_session(proxy, HEADERS)
    if API_USER and API_KEY:
        session.auth = (API_USER, API_KEY)
        print(i18n.t("e6_logged_in"))
    else:
        print(i18n.t("e6_guest_limited"))
    return session


session = create_session()


def sanitize_filename(name: str) -> str:
    """去除非法文件名字符，保证文件夹名合法"""
    name = re.sub(r'[\\/*?:"<>|]', '_', name)      # Windows 非法字符
    name = re.sub(r'[\s.]+$', '', name)            # 去除末尾空格或点
    name = name.strip()
    if not name:
        name = "untitled"
    return name


def fetch_all_post_ids(tags: str) -> list[int]:
    """获取匹配标签的所有帖子 ID（自动翻页）"""
    all_ids = []
    page = 1
    while True:
        params = {
            "tags": tags,
            "limit": POSTS_PER_REQUEST,
            "page": page,
            "filter_id": 0,
        }
        try:
            resp = session.get(f"{API_BASE}/posts.json", params=params)
            resp.raise_for_status()
            data = resp.json()
            posts = data.get("posts", [])
            if not posts:
                break
            all_ids.extend(post["id"] for post in posts)
            print(i18n.t("e6_page_fetched", page=page, got=len(posts), total=len(all_ids)))
            if len(posts) < POSTS_PER_REQUEST:
                break
            page += 1
            time.sleep(REQUEST_DELAY)
        except Exception as e:
            print(i18n.t("e6_list_failed_page", page=page, e=e))
            break
    return all_ids


def fetch_posts_details_batch(post_ids: list[int]) -> list[dict]:
    """批量获取帖子详细信息（包含 pools 字段）"""
    if not post_ids:
        return []
    ids_str = ",".join(str(pid) for pid in post_ids)
    params = {
        "tags": f"id:{ids_str}",
        "limit": POSTS_PER_REQUEST,
        "filter_id": 0,
    }
    resp = session.get(f"{API_BASE}/posts.json", params=params)
    resp.raise_for_status()
    data = resp.json()
    return data.get("posts", [])


def fetch_pool_info(pool_id: int) -> dict:
    """获取单个 Pool 的完整信息（含所有 post_ids）"""
    resp = session.get(f"{API_BASE}/pools/{pool_id}.json")
    resp.raise_for_status()
    data = resp.json()
    if "pool" in data:
        return data["pool"]
    return data


def download_post(post, output_dir: Path, lock: threading.Lock) -> bool:
    """下载单个帖子，返回是否成功"""
    pid = post["id"]
    file_url = post.get("file", {}).get("url")
    ext = post.get("file", {}).get("ext", "jpg")
    if not file_url:
        # 降级到 sample
        file_url = post.get("sample", {}).get("url")
        ext = post.get("sample", {}).get("ext", ext or "jpg")
    if not file_url:
        print(i18n.t("e6_post_no_url_skip_indent", pid=pid))
        return False

    filename = f"{pid}.{ext}"
    filepath = output_dir / filename
    if filepath.exists():
        return True   # 已存在视为成功

    try:
        with session.get(file_url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(filepath, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        os.utime(filepath, None)
        return True
    except Exception as e:
        print(i18n.t("e6_post_download_failed_indent", pid=pid, err=e))
        if filepath.exists():
            filepath.unlink()
        return False


def download_posts_to_dir(post_ids: list[int], output_dir: Path):
    """批量下载帖子到指定目录（并发下载）"""
    output_dir.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()

    # 获取所有帖子的详细信息
    posts_details = []
    for i in range(0, len(post_ids), POSTS_PER_REQUEST):
        batch_ids = post_ids[i:i+POSTS_PER_REQUEST]
        try:
            posts_details.extend(fetch_posts_details_batch(batch_ids))
        except Exception as e:
            print(i18n.t("e6_batch_info_failed", e=e))
        time.sleep(REQUEST_DELAY)

    if not posts_details:
        print(i18n.t("e6_no_post_info_indent"))
        return

    # 并发下载
    success_count = 0
    fail_count = 0
    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as executor:
        futures = [executor.submit(download_post, post, output_dir, lock) for post in posts_details]
        for future in as_completed(futures):
            if future.result():
                success_count += 1
            else:
                fail_count += 1

    print(i18n.t("e6_dir_download_summary_indent", ok=success_count, bad=fail_count))


# ============================================================
# 名单（--dry-run 的产出；--pick / --from-manifest 的输入）
# ============================================================


def save_manifest(path, payload):
    """把名单写成 JSON。用「临时文件 + 原子替换」，中途中断不会留下半截文件。"""
    tmp = str(path) + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, str(path))
        return True
    except OSError as e:
        print(i18n.t("e6_manifest_write_failed", e=e))
        return False


def load_manifest(path):
    """读回名单。返回 payload dict；失败返回 None。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(i18n.t("e6_manifest_not_found", path=path))
    except (OSError, ValueError) as e:
        print(i18n.t("e6_manifest_unreadable", kind=type(e).__name__, e=e))
    return None


def show_manifest_list(items, artist_tag=""):
    """打印带序号的下载名单。这里的序号就是 --pick 要写的号。

    用逐行列表而不是表格：GBK 终端里中文占 2 个显示宽度，
    表格列（尤其含中文表头）会对不齐，逐行反而一眼能读。
    名单里出现同名 Pool 时，额外标出 pool id 以便区分。
    """
    suffix = i18n.t("e6_artist_suffix", tag=artist_tag) if artist_tag else ""
    pool_names = [it["name"] for it in items if it["kind"] == "pool"]
    dup = {n for n in pool_names if pool_names.count(n) > 1}
    print(i18n.t("e6_manifest_title", suffix=suffix))
    for i, it in enumerate(items, 1):
        if it["kind"] == "pool":
            tag = f"  [pool id {it['pool_id']}]" if it["name"] in dup else ""
            print(i18n.t("e6_manifest_pool_line", idx=i, name=it["name"], tag=tag,
                         count=it.get('count', 0)))
        else:
            print(i18n.t("e6_manifest_others_line", idx=i, count=it.get('count', 0)))
    print(i18n.t("e6_manifest_footer", n=len(items)))


def collect_manifest_items(artist_tag):
    """检索艺术家所有帖子 → 汇总成**有序**的下载单元列表。

    返回 (items, total_posts)。

    顺序规则（必须稳定，否则 dry-run 的序号会跟下载时的序号对不上）：
        - 所有 Pool 按 (名称, pool_id) 排序
        - others 固定放在最后

    items 里 pool 项只存 pool_id（下载时现拉 post_ids，清单小且能容忍池内容变化）；
    others 项直接存 post_ids（否则 --from-manifest 跳过检索后就无法复现这批帖子）。
    """
    print(i18n.t("e6_artist_ids_fetching"))
    all_ids = fetch_all_post_ids(artist_tag)
    if not all_ids:
        return [], 0
    print(i18n.t("e6_total_found", n=len(all_ids)))

    print(i18n.t("e6_posts_detail_for_pools"))
    posts = []
    for i in range(0, len(all_ids), POSTS_PER_REQUEST):
        batch_ids = all_ids[i:i + POSTS_PER_REQUEST]
        try:
            posts.extend(fetch_posts_details_batch(batch_ids))
        except Exception as e:
            print(i18n.t("e6_batch_info_failed", e=e))
        time.sleep(REQUEST_DELAY)

    pool_ids = set()
    others_ids = []
    for post in posts:
        pools = post.get("pools") or []
        if pools:
            pool_ids.update(pools)          # pool_id 直接是整数
        else:
            others_ids.append(post["id"])

    print(i18n.t("e6_pools_found", pools=len(pool_ids), others=len(others_ids)))

    # 拉每个 Pool 的名称与作品数（dry-run 要显示，排序也需要名字）
    pool_items = []
    for pid in sorted(pool_ids):
        try:
            info = fetch_pool_info(pid)
            name = info.get("name") or f"pool_{pid}"
            count = len(info.get("post_ids") or [])
            pool_items.append({"kind": "pool", "pool_id": pid,
                               "name": name, "count": count})
        except Exception as e:
            print(i18n.t("e6_pool_info_failed_indent", id=pid, e=e))
        time.sleep(REQUEST_DELAY)

    # ⚠️ 稳定排序：set 的迭代顺序不定，不排序会让"dry-run 看到的 #2"
    #    和"下载时的 #2"指向不同的池。
    pool_items.sort(key=lambda x: (x["name"].lower(), x["pool_id"]))

    # 目录名消歧：**同名 Pool 追加 _<pool_id>**。
    # 不处理的话，两个同名池会被下进同一个文件夹，断点续传把它们混在一起，
    # 分不清哪些图属于哪个池；追加 id 后各自独立。
    # 判重基于 sanitize 之后的名字 —— 不同原名也可能被 sanitize 成同一个。
    base_dirs = [sanitize_filename(it["name"]) for it in pool_items]
    dup = {}
    for d in base_dirs:
        dup[d] = dup.get(d, 0) + 1
    for it, d in zip(pool_items, base_dirs):
        it["dir"] = f"{d}_{it['pool_id']}" if dup[d] > 1 else d

    items = list(pool_items)
    if others_ids:
        items.append({"kind": "others", "pool_id": None, "name": "others",
                      "dir": "others", "count": len(others_ids),
                      "post_ids": others_ids})
    return items, len(all_ids)


def main():
    parser = argparse.ArgumentParser(
        description=i18n.t("e6_artist_desc"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=i18n.t("e6_artist_epilog", prog=os.path.basename(sys.argv[0])))
    parser.add_argument("--tags", default=None, help=i18n.t("e6_artist_tags_help"))
    parser.add_argument("-o", "--output", default=None, help=i18n.t("e6_artist_output_help"))
    parser.add_argument(
        "--skip-others",
        action="store_true",
        help=i18n.t("e6_skip_others_help")
    )
    parser.add_argument("--dry-run", action="store_true",
                        help=i18n.t("e6_dry_run_help"))
    parser.add_argument("--pick", default=None,
                        help=i18n.t("e6_pick_help"))
    parser.add_argument("--manifest", default=MANIFEST_DEFAULT,
                        help=i18n.t("e6_manifest_help", name=MANIFEST_DEFAULT))
    parser.add_argument("--from-manifest", default=None, metavar="FILE",
                        help=i18n.t("e6_from_manifest_help"))
    args = parser.parse_args()

    # ---------- 0. 参数检查：--tags 与 --from-manifest 二选一 ----------
    if bool(args.tags) == bool(args.from_manifest):
        print(i18n.t("e6_need_tags_or_manifest"))
        print(i18n.t("e6_example_dry_run"))
        print(i18n.t("e6_example_manifest", name=MANIFEST_DEFAULT))
        return 1

    # ---------- 1. 拿名单 ----------
    total_posts = None
    if args.from_manifest:
        payload = load_manifest(args.from_manifest)
        if not payload:
            return 1
        items = payload.get("items") or []
        artist_tag = payload.get("query") or ""
        if not items:
            print(i18n.t("e6_manifest_empty"))
            return 1
        print(i18n.t("e6_manifest_read", n=len(items),
                     tag=artist_tag or i18n.t("e6_artist_unrecorded")))
    else:
        artist_tag = args.tags.strip()
        print(i18n.t("e6_artist_tag", tag=artist_tag))
        items, total_posts = collect_manifest_items(artist_tag)
        if not items:
            print(i18n.t("e6_no_posts_at_all"))
            return 1

    # ---------- 2. 展示名单 ----------
    show_manifest_list(items, artist_tag)

    # ---------- 3. dry-run：存名单，不下载 ----------
    if args.dry_run:
        payload = {
            "mode": "artist",
            "tool": "e6_artist",
            "query": artist_tag,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total": len(items),
            "items": items,
        }
        if save_manifest(args.manifest, payload):
            print(i18n.t("e6_manifest_saved", path=os.path.abspath(args.manifest)))
            print(i18n.t("e6_manifest_next_hint", prog=os.path.basename(sys.argv[0]),
                         manifest=args.manifest))
        return 0

    # ---------- 4. 挑序号 ----------
    if args.pick:
        idx = common.parse_pick(args.pick, len(items))
        if idx is None:
            return 1
        picked = [(i, items[i - 1]) for i in idx]
        print(i18n.t("e6_pick_selected", n=len(picked),
                     idx=', '.join(str(i) for i in idx)))
    else:
        picked = list(enumerate(items, 1))
        if args.skip_others:
            before = len(picked)
            picked = [(n, it) for n, it in picked if it["kind"] != "others"]
            if len(picked) < before:
                print(i18n.t("e6_skip_others_applied", n=before - len(picked)))

    # ---------- 5. 输出目录 ----------
    if args.output:
        root_dir = Path(args.output)
    else:
        root_dir = Path(sanitize_filename(artist_tag or "artist"))
    print(i18n.t("e6_output_root", path=root_dir.resolve()))

    # ---------- 6. 逐项下载 ----------
    for seq, (no, item) in enumerate(picked, 1):
        if item["kind"] == "pool":
            print(i18n.t("e6_pool_header", seq=seq, total=len(picked),
                         id=item.get('pool_id'), name=item['name']))
            try:
                post_ids = fetch_pool_info(item["pool_id"]).get("post_ids") or []
            except Exception as e:
                print(i18n.t("e6_pool_fetch_failed_indent", id=item.get('pool_id'), e=e))
                continue
            # 目录名用名单里算好的 dir（同名 Pool 已带 _<id> 消歧）；
            # 旧名单没有 dir 字段时退回按名称。
            sub = item.get("dir") or sanitize_filename(item["name"])
        else:
            print(i18n.t("e6_others_header", seq=seq, total=len(picked)))
            post_ids = item.get("post_ids") or []
            sub = item.get("dir") or "others"

        if not post_ids:
            print(i18n.t("e6_item_no_posts_indent"))
            continue
        download_posts_to_dir(post_ids, root_dir / sub)

    print(i18n.t("e6_all_done"), root_dir.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())