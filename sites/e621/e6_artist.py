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
        print("已使用认证信息登录")
    else:
        print("以游客身份访问（部分内容可能受限）")
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
            print(f"  第 {page} 页，获取到 {len(posts)} 个帖子（累计 {len(all_ids)}）")
            if len(posts) < POSTS_PER_REQUEST:
                break
            page += 1
            time.sleep(REQUEST_DELAY)
        except Exception as e:
            print(f"获取帖子列表失败（第 {page} 页）: {e}")
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
        print(f"  帖子 #{pid} 无可用 URL，跳过")
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
        print(f"  下载帖子 #{pid} 失败: {e}")
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
            print(f"批量获取帖子信息失败: {e}")
        time.sleep(REQUEST_DELAY)

    if not posts_details:
        print("  没有找到帖子信息")
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

    print(f"  下载完成：成功 {success_count}，失败/跳过 {fail_count}")


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
        print(f"名单写入失败：{e}")
        return False


def load_manifest(path):
    """读回名单。返回 payload dict；失败返回 None。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"找不到名单文件：{path}")
    except (OSError, ValueError) as e:
        print(f"名单文件读不了（{type(e).__name__}）：{e}")
    return None


def show_manifest_list(items, artist_tag=""):
    """打印带序号的下载名单。这里的序号就是 --pick 要写的号。

    用逐行列表而不是表格：GBK 终端里中文占 2 个显示宽度，
    表格列（尤其含中文表头）会对不齐，逐行反而一眼能读。
    名单里出现同名 Pool 时，额外标出 pool id 以便区分。
    """
    suffix = f"（艺术家: {artist_tag}）" if artist_tag else ""
    pool_names = [it["name"] for it in items if it["kind"] == "pool"]
    dup = {n for n in pool_names if pool_names.count(n) > 1}
    print(f"\n===== 下载名单{suffix} =====")
    for i, it in enumerate(items, 1):
        if it["kind"] == "pool":
            tag = f"  [pool id {it['pool_id']}]" if it["name"] in dup else ""
            print(f"  {i:>3}. [pool]   {it['name']}{tag}   （{it.get('count', 0)} 个作品）")
        else:
            print(f"  {i:>3}. [others] 不属于任何池   （{it.get('count', 0)} 个作品）")
    print(f"  共 {len(items)} 项。用 --pick 1,3 挑着下，编号就是上面的 #")


def collect_manifest_items(artist_tag):
    """检索艺术家所有帖子 → 汇总成**有序**的下载单元列表。

    返回 (items, total_posts)。

    顺序规则（必须稳定，否则 dry-run 的序号会跟下载时的序号对不上）：
        - 所有 Pool 按 (名称, pool_id) 排序
        - others 固定放在最后

    items 里 pool 项只存 pool_id（下载时现拉 post_ids，清单小且能容忍池内容变化）；
    others 项直接存 post_ids（否则 --from-manifest 跳过检索后就无法复现这批帖子）。
    """
    print("正在获取艺术家所有帖子 ID...")
    all_ids = fetch_all_post_ids(artist_tag)
    if not all_ids:
        return [], 0
    print(f"共找到 {len(all_ids)} 个帖子")

    print("正在获取帖子详细信息以提取 Pool 信息...")
    posts = []
    for i in range(0, len(all_ids), POSTS_PER_REQUEST):
        batch_ids = all_ids[i:i + POSTS_PER_REQUEST]
        try:
            posts.extend(fetch_posts_details_batch(batch_ids))
        except Exception as e:
            print(f"批量获取帖子信息失败: {e}")
        time.sleep(REQUEST_DELAY)

    pool_ids = set()
    others_ids = []
    for post in posts:
        pools = post.get("pools") or []
        if pools:
            pool_ids.update(pools)          # pool_id 直接是整数
        else:
            others_ids.append(post["id"])

    print(f"发现 {len(pool_ids)} 个相关 Pool，{len(others_ids)} 个帖子不属于任何池")

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
            print(f"  获取 Pool {pid} 信息失败: {e}")
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
        description="下载艺术家作品并按 Pool 分组（含 dry-run 名单 / --pick 挑着下）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  %(prog)s --tags artist_name                    # 全部下载
  %(prog)s --tags artist_name --dry-run          # 只看名单（存 JSON，不下载）
  %(prog)s --tags artist_name --pick 1,3         # 只下名单里的第 1、3 项
  %(prog)s --from-manifest e6_artist_manifest.json --pick 2-4   # 从已存名单挑着下

--pick 的编号 = dry-run 打印的 #（Pool 按名称排序，others 固定最后）。
""" % {"prog": os.path.basename(sys.argv[0])})
    parser.add_argument("--tags", default=None, help="艺术家标签，例如 artist_name")
    parser.add_argument("-o", "--output", default=None, help="输出根目录（默认为艺术家标签名）")
    parser.add_argument(
        "--skip-others",
        action="store_true",
        help="跳过不属于任何 Pool 的帖子（用 --pick 显式选中 others 时以 --pick 为准）"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="只列名单不下载（同时把名单写进 --manifest 指的文件）")
    parser.add_argument("--pick", default=None,
                        help="按名单序号挑着下，如 2-4,7 / 3- / all（编号 = dry-run 看到的 #）")
    parser.add_argument("--manifest", default=MANIFEST_DEFAULT,
                        help=f"--dry-run 保存名单的文件名（默认 {MANIFEST_DEFAULT}）")
    parser.add_argument("--from-manifest", default=None, metavar="FILE",
                        help="从这个名单文件读结果，跳过检索（配合 --pick 精确复现）")
    args = parser.parse_args()

    # ---------- 0. 参数检查：--tags 与 --from-manifest 二选一 ----------
    if bool(args.tags) == bool(args.from_manifest):
        print("请给出 --tags <艺术家标签> 或 --from-manifest <名单文件>（二选一）。")
        print(f"  例：python e6_artist.py --tags artist_name --dry-run")
        print(f"  例：python e6_artist.py --from-manifest {MANIFEST_DEFAULT} --pick 2-4,7")
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
            print("名单里没有可下载的项。")
            return 1
        print(f"从名单读回 {len(items)} 项（原艺术家: {artist_tag or '(未记录)'}）")
    else:
        artist_tag = args.tags.strip()
        print(f"艺术家标签: {artist_tag}")
        items, total_posts = collect_manifest_items(artist_tag)
        if not items:
            print("没有找到任何帖子。")
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
            print(f"\n名单已保存: {os.path.abspath(args.manifest)}")
            print(f"下次可用: python {os.path.basename(sys.argv[0])} "
                  f"--from-manifest {args.manifest} --pick 1,3")
        return 0

    # ---------- 4. 挑序号 ----------
    if args.pick:
        idx = common.parse_pick(args.pick, len(items))
        if idx is None:
            return 1
        picked = [(i, items[i - 1]) for i in idx]
        print(f"\n--pick 挑出 {len(picked)} 项: {', '.join(str(i) for i in idx)}")
    else:
        picked = list(enumerate(items, 1))
        if args.skip_others:
            before = len(picked)
            picked = [(n, it) for n, it in picked if it["kind"] != "others"]
            if len(picked) < before:
                print(f"\n--skip-others 生效：跳过 others（{before - len(picked)} 项）")

    # ---------- 5. 输出目录 ----------
    if args.output:
        root_dir = Path(args.output)
    else:
        root_dir = Path(sanitize_filename(artist_tag or "artist"))
    print(f"输出根目录: {root_dir.resolve()}")

    # ---------- 6. 逐项下载 ----------
    for seq, (no, item) in enumerate(picked, 1):
        if item["kind"] == "pool":
            print(f"\n[{seq}/{len(picked)}] Pool #{item.get('pool_id')} {item['name']}")
            try:
                post_ids = fetch_pool_info(item["pool_id"]).get("post_ids") or []
            except Exception as e:
                print(f"  获取 Pool {item.get('pool_id')} 失败: {e}")
                continue
            # 目录名用名单里算好的 dir（同名 Pool 已带 _<id> 消歧）；
            # 旧名单没有 dir 字段时退回按名称。
            sub = item.get("dir") or sanitize_filename(item["name"])
        else:
            print(f"\n[{seq}/{len(picked)}] others")
            post_ids = item.get("post_ids") or []
            sub = item.get("dir") or "others"

        if not post_ids:
            print("  该项没有作品，跳过。")
            continue
        download_posts_to_dir(post_ids, root_dir / sub)

    print("\n全部完成！文件保存在:", root_dir.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())