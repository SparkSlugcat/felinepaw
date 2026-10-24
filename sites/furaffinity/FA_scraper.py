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
    python FA_scraper.py https://www.furaffinity.net/view/12345678/ --dry-run

    # 正常下载整个系列（按提示输入账号密码）
    python FA_scraper.py https://www.furaffinity.net/view/12345678/ -o ./out

    # 下一个作者的整个画廊，按作品名分目录
    python FA_scraper.py someartist -o ./out

    # 用环境变量提供凭据，或命令行参数
    set FA_USERNAME=xxx & set FA_PASSWORD=yyy
    python FA_scraper.py URL --user xxx --pass yyy --limit 50 --proxy off

    # 只下载这一张，不找系列
    python FA_scraper.py URL --just-this

依赖: requests + lxml
注意: FA 服务条款禁止自动化批量下载，本工具仅供个人使用，风险自担。
"""

import argparse
import difflib
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
import i18n
import local_creds          # 本机凭据快捷通道（.faenv；不进仓库，见 local_creds.py）
# 共享函数别名
create_session = common.create_session
sanitize_filename = common.sanitize_filename
parse_limit = common.parse_limit


# ============================================================
# 登录
# ============================================================

def stdin_is_interactive() -> bool:
    """能不能安全地向用户要输入。

    ⚠️ 这是 GUI 场景的地雷（2026-10-23 实测）：
       `启动.bat` 用 `start "" pythonw.exe` 起界面，GUI 再起本脚本时**也是 pythonw**，
       子进程的 stdin 一读就 EOF —— `input()` 抛 `EOFError: EOF when reading a line`，
       用户只在日志里看到一坨 traceback，完全不知道要干什么。
       更糟的是 `input_password()` 走 msvcrt.getwch()，那种情况下**不报错、直接卡死**。

    所以任何交互之前都必须先问这一句，答"否"就走非交互分支（打印引导 + 退出）。
    """
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except (ValueError, OSError):        # 句柄被关掉时 isatty() 会抛
        return False


def input_password(prompt: str = i18n.t("fa_prompt_password")) -> str:
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


def cloudflare_challenge(resp) -> bool:
    """这一页是不是 Cloudflare 的人机挑战页。

    实测（2026-10-23，py39 + Clash 7897）：FA 整站在 Cloudflare 后面，出口 IP 一旦被
    判定可疑就下发 Managed Challenge —— HTTP 403、响应头 `cf-mitigated: challenge`、
    标题 `Just a moment...`、正文只有一句 `Enable JavaScript and cookies to continue`。
    连**首页**和**登录页**都会中招，跟作品 ID 存不存在无关。

    这种页面必须由真浏览器执行 JS 才能过，requests 换 cookie / 换 UA 都没用。
    → 所以它既不是"账号密码错"，也不是"作品不存在"，不能让人去查这两件事。
    """
    if resp is None or resp.status_code not in (403, 503):
        return False
    if (resp.headers.get("cf-mitigated") or "").lower() == "challenge":
        return True
    head = (resp.text or "")[:2000].lower()
    return ("just a moment" in head and "cloudflare" in head) or \
           "enable javascript and cookies" in head


class SiteOffline(RuntimeError):
    """整站下线 —— 不是网络错，也不是没权限，等人家修好再来。"""


def site_offline(resp) -> bool:
    """这一页是不是 FA 自己的「全站维护中」占位页。

    实测（2026-10-24）：FA 因 PHP 漏洞（PHP2Shell / CVE-2026-109618）全站下线，
    **任意** URL 都返回 HTTP 403 + 同一张 1917 字节的 `FA is temporarily offline!`
    静态页（`Server: cloudflare`、`Set-Cookie: FA-Cache-Clear=<时间戳>`）。

    关键点：它的状态码也是 403，但**没有** `cf-mitigated` 头 —— 和上面那种人机挑战
    长得像、本质完全不同。不区分的话会被当成"画廊是空的"或"你没有权限"，
    让人白白去换节点、重新导 cookie。
    """
    head = (resp.text or "")[:4000].lower()
    return "temporarily offline" in head or "currently offline" in head


def ensure_site_online(session: requests.Session) -> None:
    """开跑前先戳一下首页：整站下线就直接说清楚并退出。

    放在最前面，是为了让后面所有"抓不到 / 403 / 空画廊"的报错都不会掩盖真正原因。
    网络本身不通时**不在这里报** —— 那属于代理问题，留给真正的请求去抛。
    """
    try:
        resp = session.get(SITE + "/", timeout=20)
    except requests.RequestException:
        return
    if site_offline(resp):
        print(i18n.t("fa_site_offline"))
        print(i18n.t("fa_site_offline_hint"))
        sys.exit(2)


def login(session: requests.Session, username: str, password: str) -> bool:
    """登录 FA，成功返回 True。

    注意：FA 登录页含 JS 验证码（fa-captcha），纯 requests 可能被拦截
    （返回 /login/?msg=3）。遇到验证码时请改用 --cookies 模式：
    先运行 FA_get_cookies.py 导出 fa_cookies.json。
    """
    print(i18n.t("fa_logging_in"))
    try:
        r = session.get(SITE + "/login/", timeout=20)
        if cloudflare_challenge(r):
            print(i18n.t("fa_err_cloudflare"))
            print(i18n.t("fa_err_cloudflare_hint"))
            return False
        r.raise_for_status()
        # 检测验证码
        has_captcha = "fa-captcha" in r.text or "captcha-container" in r.text
        data = {"action": "login", "name": username, "pass": password,
                "login": "Login to Fur Affinity"}
        r2 = session.post(SITE + "/login/", data=data, timeout=20,
                          allow_redirects=False)
        loc = r2.headers.get("Location", "")
        if "msg=" in loc or r2.status_code not in (302, 200):
            print(i18n.t("fa_login_rejected"))
            if has_captcha:
                print(i18n.t("fa_login_captcha"))
                print(i18n.t("fa_login_cookies_hint1"))
                print(i18n.t("fa_login_cookies_hint2"))
            else:
                print(i18n.t("fa_login_bad_credentials"))
            return False
        # 302 且无 msg -> 疑似成功，再做一次主页验证
        home = session.get(SITE + "/", timeout=20).text
        low_home = home.lower()
        if f'href="/user/{username.lower()}/"' in low_home:
            print(i18n.t("fa_login_ok"))
            return True
        if re.search(r"welcome\s+back[^<]{0,20}" + re.escape(username.lower()), low_home):
            print(i18n.t("fa_login_ok"))
            return True
        print(i18n.t("fa_login_unconfirmed"))
        return False
    except requests.RequestException as e:
        print(i18n.t("fa_err_login_request", e=e))
        return False


def load_cookies(session: requests.Session, path: str) -> bool:
    """从 JSON 文件加载 cookies（FA_get_cookies.py 导出的格式）。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(i18n.t("fa_err_cookies_read", e=e))
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
    print(i18n.t("fa_cookies_loaded", count=count, path=path))
    # 浏览器导出的真实 UA 跟着 cookie 一起放在旁边（fa_cookies_ua.txt）。
    # cf_clearance 绑定「出口 IP + 浏览器 UA」，UA 对不上等于没拿到 cookie。
    ua_file = Path(path).with_name(Path(path).stem + "_ua.txt")
    try:
        ua = ua_file.read_text(encoding="utf-8").strip() if ua_file.exists() else ""
    except OSError:
        ua = ""
    if ua:
        session.headers["User-Agent"] = ua
        IMAGE_HEADERS["User-Agent"] = ua
        print(i18n.t("fa_ua_loaded"))
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
    raise ValueError(i18n.t("fa_err_parse_id", id=url_or_id))


def parse_target(url_or_id: str):
    """把用户输入归类，返回 ("view", 作品id) 或 ("artist", 作者名)。

    四种写法都认：
        https://www.furaffinity.net/view/12345678/      -> ("view", "12345678")
        12345678                                        -> ("view", "12345678")
        https://www.furaffinity.net/gallery/someartist/ -> ("artist", "someartist")
        someartist                                      -> ("artist", "someartist")

    为什么要分类：作品页只能一张一张扩展（靠标题找同系列），
    作者页才是一次拿整个画廊的入口。
    """
    s = (url_or_id or "").strip()
    if not s:
        raise ValueError(i18n.t("fa_err_parse_target", id=url_or_id))
    m = re.search(r"/view/(\d+)", s)
    if m:
        return "view", m.group(1)
    if s.isdigit():
        return "view", s
    m = re.search(r"/(?:gallery|user|favorites)/([A-Za-z0-9_.~\-]+)", s)
    if m:
        return "artist", m.group(1)
    # 剩下的当作者名（FA 用户名只由字母数字和 - _ . ~ 组成）
    if re.fullmatch(r"[A-Za-z0-9_.~\-]+", s):
        return "artist", s
    raise ValueError(i18n.t("fa_err_parse_target", id=url_or_id))


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
        # 健康检查过了也可能中途下线 —— 不拦一下就会报成"画廊是空的"
        if site_offline(resp):
            raise SiteOffline(url)
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
                log(i18n.t("fa_err_gallery_page", path=path, page=page + 1, e=e))
                break
            new = [(v, t) for v, t in batch if v not in seen]
            for v, t in new:
                seen.add(v)
                items.append((v, t))
            log(i18n.t("fa_gallery_page", path=path, page=page + 1,
                       n=len(batch), total=len(items)))
            if not batch:
                break
            if not new:
                # 整页都是见过的 —— 到底了，或者这个页面没在真的翻页。
                # 实测：/gallery/<user>/scraps/ 会原样返回 gallery 的内容，
                # 不设这一条就会把整个画廊再抓一遍（几百次无谓请求）。
                log(i18n.t("fa_page_no_new", path=path, page=page + 1))
                break
            if len(batch) < 24:          # FA 每页约 48 项，明显变少说明是末页
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


def safe_name(text: str, limit: int = 60) -> str:
    """把标题/系列名变成安全的文件（夹）名。

    比 common.sanitize_filename 多做一件事：把 `.` 换成 `_`。
    因为 download_submission 是用 with_suffix(".jpg") 补扩展名的，
    文件名里但凡有个点（"Vol.2 完"），那个点会被当成扩展名分隔符，
    后半截标题整个丢掉。
    """
    s = sanitize_filename(text or "")
    s = s.replace(".", "_")
    s = re.sub(r"\s+", " ", s).strip(" _")
    s = s[:limit].strip(" _")
    # 标题只有符号（"----"）时给个中性名，否则会造出叫 "----" 的文件
    if not re.search(r"[A-Za-z0-9\u4e00-\u9fff]", s):
        return "untitled"
    return s


def _same_series(a: str, b: str) -> bool:
    """两个归一化标题算不算同一部作品。

    先看前缀（"study session" / "study session extra"），
    再用字符相似度兜住拼写差异。阈值偏低是有意的：
    这一层的用途是"把相近的放一起"，多并一组最多是目录名不精确，
    漏并一组则是同一部漫画被拆散 —— 后者更烦人。
    """
    if a == b:
        return True
    if not a or not b:
        return False
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    if len(short) >= 8 and long_.startswith(short):
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.86


def group_by_series(items, artist: str = ""):
    """把 [(view_id, title)] 按系列归堆。

    两步：① 用 normalize_title 精确分组；② 把名字相近的组并到一起。
    返回 [(系列名, [(vid, title, 序号), ...]), ...]
      组内按序号排（同序号保持画廊顺序），组之间按张数从多到少。
    """
    #: 标题里连一个有意义的字符都没有时用的独立前缀
    SOLO = "\x00solo\x00"

    buckets = {}
    for vid, title in items:
        key = normalize_title(title, artist)
        if not re.search(r"[A-Za-z0-9\u4e00-\u9fff]", key or ""):
            # 画师常拿 "----" 当分隔线：归一化后只剩空/符号。
            # 这种不能当系列名 —— 否则几百张互不相干的作品会被并成一组。
            buckets.setdefault(SOLO + str(vid), []).append(
                (vid, title, extract_part_number(title, artist)))
            continue
        key = re.sub(r"\s+", " ", key).strip()
        buckets.setdefault(key, []).append(
            (vid, title, extract_part_number(title, artist)))

    merged = {}
    reps = []
    # 大组先落地，小组再往上并 —— 否则一个只有 1 张的组会抢走代表名
    for key in sorted(buckets, key=lambda k: (-len(buckets[k]), k)):
        if key.startswith(SOLO):
            target = key                     # 无标题作品各自独立，不参与合并
        else:
            target = next((r for r in reps if _same_series(key, r)), None)
            if target is None:
                target = key
                reps.append(key)
        merged.setdefault(target, []).extend(buckets[key])

    groups = []
    for name, members in merged.items():
        seen, uniq = set(), []
        for m in members:
            if m[0] in seen:
                continue
            seen.add(m[0])
            uniq.append(m)
        numbered = sorted([m for m in uniq if m[2] > 0], key=lambda m: m[2])
        members = numbered + [m for m in uniq if m[2] == 0]
        # 独立作品用原始标题当显示名（"----" 之类），反正不会拿它建目录
        raw = (uniq[0][1].strip() if name.startswith(SOLO) else name) or ""
        shown = raw if re.search(r"[A-Za-z0-9\u4e00-\u9fff]", raw) else "untitled"
        groups.append((shown, members))
    groups.sort(key=lambda g: (-len(g[1]), g[0]))
    return groups


# ============================================================
# 下载
# ============================================================

def download_submission(session: requests.Session, view_id: str, filepath: Path,
                        log=print) -> bool:
    """下载单个作品（登录态）。"""
    if filepath.exists():
        log(i18n.t("fa_skip_exists", vid=view_id, name=filepath.name))
        return True
    try:
        title, artist, image_url = fetch_view_info(session, view_id)
        if not image_url:
            log(i18n.t("fa_err_no_image", vid=view_id))
            return False
        if image_url.startswith("//"):
            image_url = "https:" + image_url
        ext = Path(urlparse(image_url).path).suffix.lstrip(".") or "jpg"
        if ext.lower() not in ("jpg", "jpeg", "png", "gif", "webp"):
            log(i18n.t("fa_skip_not_image", vid=view_id, ext=ext))
            return False
        final = filepath.with_suffix("." + ext)
        if final.exists():
            log(i18n.t("fa_skip_exists", vid=view_id, name=final.name))
            return True
        with session.get(image_url, stream=True, timeout=30,
                         headers=IMAGE_HEADERS) as r:
            r.raise_for_status()
            with open(final, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
        if final.stat().st_size == 0:
            final.unlink()
            raise RuntimeError(i18n.t("fa_err_empty_file"))
        log(i18n.t("fa_done", vid=view_id, name=final.name))
        return True
    except Exception as e:
        log(i18n.t("fa_err_download", vid=view_id, e=e))
        if filepath.exists():
            try:
                filepath.unlink()
            except OSError:
                pass
        return False


def main():
    parser = argparse.ArgumentParser(description=i18n.t("fa_cli_desc"))
    parser.add_argument("url", help=i18n.t("fa_help_url"))
    parser.add_argument("-o", "--output", default=None, help=i18n.t("fa_help_output"))
    parser.add_argument("-w", "--workers", type=int, default=4, help=i18n.t("fa_help_workers"))
    parser.add_argument("-d", "--delay", type=float, default=1.0, help=i18n.t("fa_help_delay"))
    parser.add_argument("--limit", default=None,
                        help=i18n.t("fa_help_limit"))
    parser.add_argument("--proxy", default=None,
                        help=i18n.t("fa_help_proxy"))
    parser.add_argument("--user", default=None, help=i18n.t("fa_help_user"))
    parser.add_argument("--pass", dest="password", default=None,
                        help=i18n.t("fa_help_pass"))
    parser.add_argument("--cookies", default=None,
                        help=i18n.t("fa_help_cookies"))
    parser.add_argument("--dry-run", action="store_true",
                        help=i18n.t("fa_help_dry_run"))
    parser.add_argument("--just-this", action="store_true", help=i18n.t("fa_help_just_this"))
    parser.add_argument("--all", dest="all_gallery", action="store_true",
                        help=i18n.t("fa_help_all"))
    args = parser.parse_args()

    try:
        kind, target = parse_target(args.url)
    except ValueError as e:
        print(e)
        sys.exit(1)

    session = create_session(args.proxy)
    if session.proxies:
        print(i18n.t("fa_proxy_enabled", proxy=list(session.proxies.values())[0]))
    else:
        print(i18n.t("fa_proxy_direct"))
    ensure_site_online(session)

    # ---------- 1. 作品信息（游客也能拿到标题） ----------
    title = artist = ""
    if kind == "view":
        print(i18n.t("fa_submission_id", id=target))
        try:
            title, artist, _ = fetch_view_info(session, target)
        except requests.HTTPError as e:
            # Cloudflare 挑战要单独说 —— 否则用户会照着 403 去查"作品是不是被删了"
            if cloudflare_challenge(getattr(e, "response", None)):
                print(i18n.t("fa_err_cloudflare"))
                print(i18n.t("fa_err_cloudflare_hint"))
                sys.exit(2)
            print(i18n.t("fa_err_fetch_page", e=e))
            sys.exit(1)
        except requests.RequestException as e:
            print(i18n.t("fa_err_fetch_page", e=e))
            sys.exit(1)
        if not title:
            print(i18n.t("fa_err_no_title"))
            sys.exit(1)
        print(i18n.t("fa_submission_title", title=title))
    else:
        artist = target
        print(i18n.t("fa_artist_target", artist=artist))

    # ---------- 2. 登录（画廊项标题和图片都需要登录态） ----------
    # 凭据优先级：命令行参数 > 环境变量 > 本机 .faenv（见 local_creds.py）
    creds = local_creds.load_fa_creds()
    if creds.get("username") or creds.get("password"):
        print(i18n.t("fa_creds_loaded"))

    cookie_path = args.cookies or creds.get("cookie_file") or ""
    from_default = False
    if not cookie_path:
        # 兜底：导出脚本（FA_get_cookies.py）就写在它自己旁边，也就是这里。
        # 有就用，省得用户去 sites\furaffinity\ 子目录里翻路径 —— 找到了还容易填错。
        _auto = Path(__file__).resolve().parent / "fa_cookies.json"
        if _auto.exists():
            cookie_path = str(_auto)
            from_default = True
    if cookie_path:
        if from_default:
            print(i18n.t("fa_cookie_auto", path=cookie_path))
        elif not args.cookies:
            print(i18n.t("fa_cookie_from_creds", path=cookie_path))
        if not load_cookies(session, cookie_path):
            sys.exit(1)
    else:
        username = args.user or creds.get("username") or ""
        password = args.password or creds.get("password") or ""
        if not (username and password):
            if not stdin_is_interactive():
                # 非交互环境（GUI 子进程）—— 别抛 traceback，直接说清楚怎么办
                print(i18n.t("fa_err_no_tty"))
                print(i18n.t("fa_err_no_tty_hint"))
                sys.exit(2)
            if not username:
                username = input(i18n.t("fa_prompt_username")).strip()
            if not password:
                password = input_password(i18n.t("fa_prompt_password"))
        if not login(session, username, password):
            sys.exit(1)

    # 登录后重新获取作品信息（作者链接/图片 URL 更准确）
    if kind == "view":
        try:
            title, artist, _ = fetch_view_info(session, target)
        except requests.RequestException:
            pass
        if not artist:
            print(i18n.t("fa_err_no_artist"))
            sys.exit(1)
        print(i18n.t("fa_artist", artist=artist))

    # 输入是作者名，或者给了作品但加了 --all —— 都走"整个画廊"这条路
    artist_mode = (kind == "artist") or args.all_gallery

    # ---------- 3. 决定下哪些 ----------
    if artist_mode:
        print(i18n.t("fa_crawling_gallery"))
        try:
            items = crawl_gallery(session, artist, include_scraps=True, log=print)
        except SiteOffline:
            print(i18n.t("fa_site_offline"))
            print(i18n.t("fa_site_offline_hint"))
            sys.exit(2)
        except requests.RequestException as e:
            print(i18n.t("fa_err_crawl_gallery", e=e))
            sys.exit(1)
        if not items:
            print(i18n.t("fa_gallery_empty", artist=artist))
            sys.exit(1)
        plan = group_by_series(items, artist)
    elif args.just_this:
        plan = [(normalize_title(title, artist) or title,
                 [(target, title, extract_part_number(title, artist))])]
    else:
        series_key = normalize_title(title, artist)
        print(i18n.t("fa_series_key", name=series_key))
        print(i18n.t("fa_crawling_gallery"))
        try:
            items = crawl_gallery(session, artist, include_scraps=True, log=print)
        except SiteOffline:
            print(i18n.t("fa_site_offline"))
            print(i18n.t("fa_site_offline_hint"))
            sys.exit(2)
        except requests.RequestException as e:
            print(i18n.t("fa_err_crawl_gallery", e=e))
            sys.exit(1)
        matched = [(v, t, extract_part_number(t, artist)) for v, t in items
                   if normalize_title(t, artist) == series_key]
        if not matched:
            print(i18n.t("fa_no_series_match"))
            matched = [(target, title, extract_part_number(title, artist))]
        # 排序：有编号的按编号，无编号的保持画廊顺序
        with_num = sorted([m for m in matched if m[2] > 0], key=lambda m: m[2])
        without_num = [m for m in matched if m[2] == 0]
        seen_ids = set()
        series = []
        for m in with_num + without_num:
            if m[0] not in seen_ids:
                seen_ids.add(m[0])
                series.append(m)
        plan = [(series_key or title, series)]

    total = sum(len(g[1]) for g in plan)
    if artist_mode:
        # 作者可能有上百张，逐条列出来会刷屏 —— 只报"分成几组、每组几张"
        print(i18n.t("fa_groups_total", n=len(plan), total=total))
        for gi, (name, members) in enumerate(plan, 1):
            print(i18n.t("fa_group_line", i=gi, name=name, n=len(members)))
    else:
        print(i18n.t("fa_series_total", n=total))
        for i, (vid, t, num) in enumerate(plan[0][1], 1):
            print(i18n.t("fa_series_item", i=i, vid=vid, num=num or "-", title=t))

    if args.dry_run:
        print(i18n.t("fa_dry_run_done"))
        return

    # ---------- 4. 下载 ----------
    # 作者模式默认全下 —— 输入作者名本身就是"我要这个人全部作品"的意思；
    # 单作品模式仍按各站点统一语义，不填就只取前 120 个。
    limit_arg = "inf" if (artist_mode and args.limit is None) else args.limit
    limit = parse_limit(limit_arg, total)
    if limit is None:
        return

    # 按组的顺序、组内的顺序摊平，再截断 —— 这样 --limit 截出来的总是完整的头部几组
    flat = []
    for ui, (_name, members) in enumerate(plan):
        for idx, (vid, t, _num) in enumerate(members, 1):
            flat.append((ui, vid, t, idx))
    flat = flat[:limit]
    print(i18n.t("fa_download_plan", n=len(flat), workers=args.workers,
                 delay=args.delay))
    if len(flat) < total:
        print(i18n.t("fa_limit_hint", rest=total - len(flat)))

    # 作者模式再多套一层作者名：-o 往往是公共下载根目录（GUI 默认就是），
    # 直接在里面铺几十个系列目录会把它彻底搞乱。
    if artist_mode:
        root = (Path(args.output) if args.output else Path(".")) / safe_name(artist)
    else:
        root = Path(args.output) if args.output else Path(safe_name(plan[0][0] or title))
    root.mkdir(parents=True, exist_ok=True)

    # 目录规则：
    #   作者模式 —— 真系列（>=2 张）各占一个编号目录，单张作品统一收进 _singles，
    #               免得根目录被几百张互不相干的图淹掉，也不会和专业目录混在一起；
    #   单作品模式 —— 平铺，不套壳（用户 -o 指的就是这个系列自己的目录）。
    used = {f[0] for f in flat}
    dir_of = {}
    gi = 0
    for ui, (_name, members) in enumerate(plan):
        if ui not in used:
            continue                      # 一张都不下就别建空目录
        if not artist_mode:
            d = root
        elif len(members) >= 2:
            gi += 1
            d = root / ("%02d %s" % (gi, safe_name(_name)))
        else:
            d = root / "_singles"
        d.mkdir(parents=True, exist_ok=True)
        dir_of[ui] = d

    lock = threading.Lock()
    downloaded = failed = 0

    def job(ui, vid, t, idx):
        nonlocal downloaded, failed
        time.sleep(random.uniform(0, args.delay))
        if artist_mode and len(plan[ui][1]) < 2:
            # 单张作品没有"组内序号"可讲，用作品号防重名
            fname = "%s [%s].jpg" % (safe_name(t, 50), vid)
        else:
            fname = "%03d %s.jpg" % (idx, safe_name(t, 50))
        ok = download_submission(session, vid, dir_of[ui] / fname, log=print)
        with lock:
            if ok:
                downloaded += 1
            else:
                failed += 1

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(job, u, v, t, i) for u, v, t, i in flat]
        for _ in as_completed(futures):
            pass

    print(i18n.t("fa_done_title"))
    if artist_mode:
        print(i18n.t("fa_summary_gallery", groups=len(set(dir_of.values())),
                     artist=artist))
    else:
        print(i18n.t("fa_summary_series", series=plan[0][0], artist=artist))
    print(i18n.t("fa_summary_counts", ok=downloaded, fail=failed))
    print(i18n.t("fa_saved_to", path=root.resolve()))


if __name__ == "__main__":
    main()
