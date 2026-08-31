#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FurAffinity (furaffinity.net) 系列作品爬虫
==============================================
FA 没有"池"概念，官方也没有 API。本脚本借鉴 FA Webcomic Auto Loader 的思路：
  1. 标题归一化识别系列（把 page/part/book/episode、罗马数字剥掉 -> 系列名）
  2. 输入单个作品 URL，自动找出该作者同系列的全部作品并下载

需要登录（FA 游客页面不含图片链接）。凭据绝不写死在代码里：
  优先级: --user/--pass 参数 > 环境变量 FA_USERNAME/FA_PASSWORD > 运行时输入

用法：
    # 登录并识别系列后打印结果，不下载
    python FA_scraper.py https://www.furaffinity.net/view/65703734/ --dry-run

    # 正常下载整个系列（按提示输入账号密码）
    python FA_scraper.py https://www.furaffinity.net/view/65703734/ -o ./study_session

    # 用环境变量提供凭据，或命令行参数
    set FA_USERNAME=xxx & set FA_PASSWORD=yyy
    python FA_scraper.py URL --user xxx --pass yyy --limit 50 --proxy off

    # 只下载这一张，不找系列
    python FA_scraper.py URL --just-this

依赖: requests + lxml
注意: FA 服务条款禁止自动化批量下载，本工具仅供个人使用，风险自担。
"""

import argparse
import getpass
import json
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from lxml import etree

SITE = "https://www.furaffinity.net"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
# FA 对图片下载有防盗链，需要 Referer
IMAGE_HEADERS = {**HEADERS, "Referer": SITE + "/"}

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
# 登录
# ============================================================

def input_password(prompt: str = "FA 密码: ") -> str:
    """输入密码：每个字符显示为 *，便于发现输错后修改；回车确认。

    Windows 下用 msvcrt 逐键读取并回显 *（支持退格修改）；
    其他平台回退到 getpass（无回显）。
    """
    if sys.platform != "win32":
        return getpass.getpass(prompt)
    import msvcrt
    sys.stdout.write(prompt)
    sys.stdout.flush()
    pwd = []
    while True:
        try:
            ch = msvcrt.getwch()
        except KeyboardInterrupt:        # Ctrl+C
            sys.stdout.write("\n")
            raise
        if ch in ("\r", "\n"):           # 回车确认
            break
        if ch in ("\b", "\x7f"):         # 退格删除
            if pwd:
                pwd.pop()
                sys.stdout.write("\b \b")
                sys.stdout.flush()
        else:
            pwd.append(ch)
            sys.stdout.write("*")
            sys.stdout.flush()
    sys.stdout.write("\n")
    return "".join(pwd)


def login(session: requests.Session, username: str, password: str) -> bool:
    """登录 FA，成功返回 True。

    注意：FA 登录页含 JS 验证码（fa-captcha），纯 requests 可能被拦截
    （返回 /login/?msg=3）。遇到验证码时请改用 --cookies 模式：
    先运行 FA_get_cookies.py 导出 fa_cookies.json。
    """
    print("正在登录 furaffinity.net ...")
    try:
        r = session.get(SITE + "/login/", timeout=20)
        r.raise_for_status()
        # 检测验证码
        has_captcha = "fa-captcha" in r.text or "captcha-container" in r.text
        data = {"action": "login", "name": username, "pass": password,
                "login": "Login to Fur Affinity"}
        r2 = session.post(SITE + "/login/", data=data, timeout=20,
                          allow_redirects=False)
        loc = r2.headers.get("Location", "")
        if "msg=" in loc or r2.status_code not in (302, 200):
            print("登录被拒（FA 返回错误码）。")
            if has_captcha:
                print("检测到登录页有验证码：FA 要求真人验证，纯脚本登录无法通过。")
                print("请改用 cookies 模式：先运行  FA_get_cookies.py  导出 cookies，")
                print("再用  --cookies fa_cookies.json  参数运行本脚本。")
            else:
                print("账号或密码可能不正确，请检查后重试。")
            return False
        # 302 且无 msg -> 疑似成功，再做一次主页验证
        home = session.get(SITE + "/", timeout=20).text
        low_home = home.lower()
        if f'href="/user/{username.lower()}/"' in low_home:
            print("登录成功。")
            return True
        if re.search(r"welcome\s+back[^<]{0,20}" + re.escape(username.lower()), low_home):
            print("登录成功。")
            return True
        print("登录状态无法确认（可能仍被验证码拦截），请改用 cookies 模式。")
        return False
    except requests.RequestException as e:
        print(f"登录请求失败: {e}")
        return False


def load_cookies(session: requests.Session, path: str) -> bool:
    """从 JSON 文件加载 cookies（FA_get_cookies.py 导出的格式）。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"读取 cookies 文件失败: {e}")
        return False
    count = 0
    for c in data:
        if not isinstance(c, dict) or "name" not in c or "value" not in c:
            continue
        try:
            session.cookies.set(
                c["name"], c["value"],
                domain=c.get("domain"),
                path=c.get("path", "/"),
                expires=c.get("expires"),
            )
            count += 1
        except Exception:
            continue
    print(f"已加载 {count} 条 cookies（来源: {path}）")
    return count > 0


# ============================================================
# 解析
# ============================================================

def parse_view_id(url_or_id: str) -> str:
    """从 URL 或纯数字提取 view id。"""
    s = url_or_id.strip()
    m = re.search(r"/view/(\d+)", s)
    if m:
        return m.group(1)
    if s.isdigit():
        return s
    raise ValueError(f"无法解析作品 ID: {url_or_id}")


def extract_title_from_html(html: str) -> str:
    m = re.search(r'<span[^>]*class="[^"]*submission-title[^"]*"[^>]*title="([^"]+)"', html)
    if m:
        return m.group(1).strip()
    m = re.search(r'<title>([^<]*)-- Fur Affinity', html)
    if m:
        return m.group(1).strip()
    return ""


def extract_artist_from_html(html: str, title: str = "") -> str:
    """从页面提取作品作者用户名。

    登录后页面头部会出现"自己"的用户链接，必须优先用作品区的作者元素：
      1. "by 作者"块（class=c-usernameBlockSimple）
      2. 作品作者头像链接（img.submission-user-icon）
      3. 兜底：任意 /user/ 链接取最后一个（头部自己的链接在前）
      4. 再兜底：从标题 "by X" 解析
    """
    tree = etree.HTML(html)
    # 1) "by 作者"块
    hrefs = tree.xpath('//span[contains(@class,"c-usernameBlockSimple")]'
                       '//a[contains(@href,"/user/")]/@href')
    if hrefs:
        m = re.search(r"/user/([^/]+)", hrefs[0])
        if m:
            return m.group(1)
    # 2) 作者头像链接
    hrefs = tree.xpath('//a[.//img[contains(@class,"submission-user-icon")]]/@href')
    if hrefs:
        m = re.search(r"/user/([^/]+)", hrefs[0])
        if m:
            return m.group(1)
    # 3) 兜底：任意 /user/ 链接取最后一个（头部自己的链接在前）
    links = re.findall(r'/user/([^"/]+)/', html)
    if links:
        return links[-1]
    # 4) 从标题 "by X" 解析
    if title:
        m = re.search(r"by\s+([A-Za-z0-9_\-]+)", title)
        if m:
            return m.group(1)
    return ""


def fetch_view_info(session: requests.Session, view_id: str):
    """获取作品信息: (title, artist, image_url)。

    登录后可拿到 image_url；游客只能拿到 title（从 <title> 解析）。
    """
    resp = session.get(f"{SITE}/view/{view_id}/", timeout=20)
    resp.raise_for_status()
    html = resp.text
    tree = etree.HTML(html)

    # 标题：优先 submission-title 元素，其次 <title>
    title = extract_title_from_html(html)
    # 艺术家：优先 /user/ 链接，其次从 "by X" 解析
    artist = extract_artist_from_html(html, title)

    # 图片 URL（需登录；FA 返回协议相对地址 //host/path，需补 https:）
    image_url = None
    for xpath in ['//img[@id="submissionImg"]/@data-fullsize-src',
                  '//img[@id="submissionImg"]/@src']:
        srcs = tree.xpath(xpath)
        if srcs:
            image_url = srcs[0]
            break
    if image_url and image_url.startswith("//"):
        image_url = "https:" + image_url
    return title, artist, image_url


def crawl_gallery(session: requests.Session, artist: str,
                  include_scraps: bool = True, log=print) -> list:
    """分页抓取作者画廊，返回 [(view_id, title), ...]（去重保序）。"""
    items = []
    seen = set()

    def grab(url):
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        tree = etree.HTML(resp.text)
        found = []
        for fig in tree.xpath('//figure[starts-with(@id,"sid-")]'):
            a = fig.xpath('.//a[contains(@href,"/view/")]')
            if not a:
                continue
            a = a[0]
            m = re.search(r"/view/(\d+)", a.get("href", ""))
            if not m:
                continue
            vid = m.group(1)
            # 标题在 figcaption 的 a/@title 里（图片链接上通常没有）
            title = ""
            cap = fig.xpath('.//figcaption//a/@title')
            if cap:
                title = (cap[0] or "").strip()
            if not title:
                title = (a.get("title") or "").strip()
            if not title:
                for img in a.xpath('.//img'):
                    title = (img.get("title") or img.get("alt") or "").strip()
                    if title:
                        break
            found.append((vid, title))
        return found

    for path in ([f"/gallery/{artist}/"] +
                 ([f"/gallery/{artist}/scraps/"] if include_scraps else [])):
        page = 0
        while True:
            url = f"{SITE}{path}" + (f"?page={page + 1}" if page else "")
            try:
                batch = grab(url)
            except requests.RequestException as e:
                log(f"  抓取 {path} 第 {page + 1} 页失败: {e}")
                break
            new = [(v, t) for v, t in batch if v not in seen]
            for v, t in new:
                seen.add(v)
                items.append((v, t))
            log(f"  {path} 第 {page + 1} 页: {len(batch)} 项（累计 {len(items)}）")
            if len(batch) < 24:          # FA 每页约 24 项
                break
            page += 1
            time.sleep(0.5)
    return items


# ============================================================
# 系列识别（标题归一化）
# ============================================================

ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6,
         "vii": 7, "viii": 8, "ix": 9, "x": 10}


def normalize_title(title: str, artist: str = "") -> str:
    """标题归一化 -> 系列名。

    借鉴 FA Webcomic Auto Loader：去掉 page/part/book/episode/chapter 等
    常见词、方括号内容（如 [Conrie]）、"by 作者"、罗马数字、末尾序号、
    标点 -> 得到系列名。
    """
    t = (title or "").lower().strip()
    if artist:
        t = re.sub(r"\s+by\s+" + re.escape(artist.lower()) + r"\s*$", " ", t)
    t = re.sub(r"\[[^\]]*\]", " ", t)             # 去掉 [xxx]
    t = re.sub(r"\b(page|part|book|episode|chapter|vol|volume|ch|p)\b", " ", t)
    t = re.sub(r"[\s_\-.:,()\[\]{}]+", " ", t)
    t = re.sub(r"^(?:the|a|an)\s+", "", t)
    # 去掉末尾罗马数字
    t = re.sub(r"(?i)\s+(iv|ix|v|vi{0,3}|i{1,3}|x|xi{0,3}|x{1,3})\s*$", "", t)
    # 去掉末尾阿拉伯数字
    t = re.sub(r"\s+\d+\s*$", "", t)
    # 去掉开头序号（如 "Part 3: The Story" 去掉 part 后残留的 "3:"）
    t = re.sub(r"^\s*\d+[\s:.\-]*", " ", t)
    # 去掉开头罗马数字（如 "Chapter VII of the Epic"）
    t = re.sub(r"^\s*(?:iv|ix|vi{0,3}|v|xi{0,3}|x{1,3}|i{1,3})\b[\s:.\-]*", " ", t, flags=re.I)
    # 去掉开头冠词/介词（the/a/an/of，循环处理）
    for _ in range(3):
        t = re.sub(r"^\s*(?:the|a|an|of)\s+", " ", t)
    return t.strip()


def extract_part_number(title: str, artist: str = "") -> int:
    """从标题提取序号（末尾或开头的数字/罗马数字），没有则返回 0。"""
    t = (title or "").lower().strip()
    if artist:
        t = re.sub(r"\s+by\s+" + re.escape(artist.lower()) + r"\s*$", " ", t)
    t = re.sub(r"\[[^\]]*\]", " ", t)
    # 1) 末尾数字: "Study Session 1"
    m = re.search(r"(\d+)\s*$", t)
    if m:
        return int(m.group(1))
    # 2) 末尾罗马数字: "Study Session II"
    m = re.search(r"\s(iv|ix|v|vi{0,3}|i{1,3}|x|xi{0,3}|x{1,3})\s*$", t)
    if m:
        return ROMAN.get(m.group(1), 0)
    # 3) 开头数字/罗马数字（去掉 page/part 等词后）: "Part 3: The Story" / "Chapter VII of the Epic"
    t2 = re.sub(r"\b(page|part|book|episode|chapter|vol|volume|ch|p)\b", " ", t)
    m = re.search(r"^\s*(\d+)\b", t2)
    if m:
        return int(m.group(1))
    m = re.search(r"^\s*(iv|ix|vi{0,3}|v|xi{0,3}|x{1,3}|i{1,3})\b", t2)
    if m:
        return ROMAN.get(m.group(1), 0)
    return 0


# ============================================================
# 下载
# ============================================================

def download_submission(session: requests.Session, view_id: str, filepath: Path,
                        log=print) -> bool:
    """下载单个作品（登录态）。"""
    if filepath.exists():
        log(f"  #{view_id} -> {filepath.name} 已存在，跳过")
        return True
    try:
        title, artist, image_url = fetch_view_info(session, view_id)
        if not image_url:
            log(f"  #{view_id} 未取到图片链接（可能未登录或不是图片）")
            return False
        if image_url.startswith("//"):
            image_url = "https:" + image_url
        ext = Path(urlparse(image_url).path).suffix.lstrip(".") or "jpg"
        if ext.lower() not in ("jpg", "jpeg", "png", "gif", "webp"):
            log(f"  #{view_id} 非图片类型(.{ext})，跳过")
            return False
        final = filepath.with_suffix("." + ext)
        if final.exists():
            log(f"  #{view_id} -> {final.name} 已存在，跳过")
            return True
        with session.get(image_url, stream=True, timeout=30,
                         headers=IMAGE_HEADERS) as r:
            r.raise_for_status()
            with open(final, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
        if final.stat().st_size == 0:
            final.unlink()
            raise RuntimeError("空文件")
        log(f"  #{view_id} -> {final.name} 完成")
        return True
    except Exception as e:
        log(f"  #{view_id} 下载失败: {e}")
        if filepath.exists():
            try:
                filepath.unlink()
            except OSError:
                pass
        return False


def main():
    parser = argparse.ArgumentParser(description="FurAffinity 系列作品爬虫（登录+系列识别）")
    parser.add_argument("url", help="作品 URL，例如 https://www.furaffinity.net/view/65703734/")
    parser.add_argument("-o", "--output", default=None, help="保存目录（默认用系列名命名）")
    parser.add_argument("-w", "--workers", type=int, default=4, help="并发线程数（默认4）")
    parser.add_argument("-d", "--delay", type=float, default=1.0, help="随机延迟上限秒（默认1.0）")
    parser.add_argument("--limit", default=None,
                        help="下载数量: 正整数 或 inf(全部)；不填默认只下载前 120 个")
    parser.add_argument("--proxy", default=None,
                        help="代理: 留空=自动检测, off=直连, 或 http://127.0.0.1:7897")
    parser.add_argument("--user", default=None, help="FA 用户名（或用环境变量 FA_USERNAME）")
    parser.add_argument("--pass", dest="password", default=None,
                        help="FA 密码（或用环境变量 FA_PASSWORD；不推荐命令行明文）")
    parser.add_argument("--cookies", default=None,
                        help="cookies 文件（FA_get_cookies.py 导出），登录被验证码拦截时用这个")
    parser.add_argument("--dry-run", action="store_true",
                        help="登录并识别系列后打印结果，不下载")
    parser.add_argument("--just-this", action="store_true", help="只下载这一张，不找系列")
    args = parser.parse_args()

    try:
        view_id = parse_view_id(args.url)
    except ValueError as e:
        print(e)
        sys.exit(1)
    print(f"作品 ID: {view_id}")

    session = create_session(args.proxy)
    if session.proxies:
        print(f"已启用代理: {list(session.proxies.values())[0]}")
    else:
        print("未使用代理（直连）")

    # ---------- 1. 作品信息（游客也能拿到标题） ----------
    try:
        title, artist, _ = fetch_view_info(session, view_id)
    except requests.RequestException as e:
        print(f"获取作品页失败: {e}")
        sys.exit(1)
    if not title:
        print("无法解析作品标题，请检查 URL。")
        sys.exit(1)
    print(f"作品: {title}")

    # ---------- 2. 登录（画廊项标题和图片都需要登录态） ----------
    if args.cookies:
        if not load_cookies(session, args.cookies):
            sys.exit(1)
    else:
        username = args.user or os.environ.get("FA_USERNAME", "")
        password = args.password or os.environ.get("FA_PASSWORD", "")
        if not username:
            username = input("FA 用户名: ").strip()
        if not password:
            password = input_password("FA 密码: ")
        if not login(session, username, password):
            sys.exit(1)

    # 登录后重新获取作品信息（作者链接/图片 URL 更准确）
    try:
        title, artist, _ = fetch_view_info(session, view_id)
    except requests.RequestException:
        pass
    if not artist:
        print("无法解析作者，请检查页面结构。")
        sys.exit(1)
    print(f"作者: {artist}")

    # ---------- 3. 系列识别 ----------
    series_key = normalize_title(title, artist)
    if args.just_this:
        series = [(view_id, title, extract_part_number(title))]
    else:
        print(f"系列名（归一化）: {series_key!r}")
        print("正在抓取作者画廊以查找同系列作品...")
        try:
            items = crawl_gallery(session, artist, include_scraps=True, log=print)
        except requests.RequestException as e:
            print(f"抓取画廊失败: {e}")
            sys.exit(1)
        matched = [(v, t, extract_part_number(t)) for v, t in items
                   if normalize_title(t, artist) == series_key]
        if not matched:
            print("画廊里没有找到同系列的其他作品（可能只有这一张）。")
            matched = [(view_id, title, extract_part_number(title))]
        # 排序：有编号的按编号，无编号的保持画廊顺序
        with_num = sorted([m for m in matched if m[2] > 0], key=lambda m: m[2])
        without_num = [m for m in matched if m[2] == 0]
        seen_ids = set()
        series = []
        for m in with_num + without_num:
            if m[0] not in seen_ids:
                seen_ids.add(m[0])
                series.append(m)

    print(f"\n系列共 {len(series)} 张:")
    for i, (vid, t, num) in enumerate(series, 1):
        print(f"  {i:3d} #{vid} 序号={num or '-'}  {t}")

    if args.dry_run:
        print("\n[dry-run] 系列识别完成，未下载。")
        return

    # ---------- 4. 下载 ----------
    limit = parse_limit(args.limit, len(series))
    if limit is None:
        return
    series = series[:limit]
    print(f"\n下载前 {len(series)} 张（{args.workers} 线程，延迟 0~{args.delay}s）")

    out = Path(args.output) if args.output else Path(safe_name(series_key or title))
    out.mkdir(parents=True, exist_ok=True)

    lock = threading.Lock()
    downloaded = failed = skipped = 0

    def job(idx, vid, t):
        nonlocal downloaded, failed, skipped
        time.sleep(random.uniform(0, args.delay))
        ok = download_submission(session, vid, out / f"{idx}.jpg", log=print)
        with lock:
            if ok:
                downloaded += 1
            else:
                failed += 1

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(job, i, v, t)
                   for i, (v, t, _n) in enumerate(series, 1)]
        for _ in as_completed(futures):
            pass

    print("\n===== 下载完成 =====")
    print(f"系列: {series_key} | 作者: {artist}")
    print(f"成功: {downloaded} | 失败: {failed}")
    print(f"文件保存至: {out.resolve()}")


if __name__ == "__main__":
    main()
