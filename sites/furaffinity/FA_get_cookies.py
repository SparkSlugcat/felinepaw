#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FA cookies 获取器（浏览器模式）
==============================================
FA 登录页含 JS 验证码（fa-captcha），而且整站挂在 Cloudflare 后面。
纯 requests 这两关都过不去，所以本脚本用 DrissionPage 打开真实浏览器：
  1. 自动填好用户名/密码
  2. 如出现验证码 / 人机验证，请你在浏览器窗口里手动完成
  3. 登录成功后自动导出 cookies 到 fa_cookies.json

⚠️ 三个「必须一致」—— 只要有一项对不上，导出的 cookie 拿回去照样被 Cloudflare 挡：
  · 出口 IP   浏览器和 FA_scraper.py 必须走同一个代理（本脚本默认 7897）
  · User-Agent 浏览器被强制成 FA_scraper.py 里那个 UA
  · 时效      cf_clearance 这个通行证有有效期，换节点 / 隔久了要重新导出

之后运行 FA_scraper.py 时加 --cookies fa_cookies.json 即可跳过登录。

用法（推荐用 py39 环境）：
    python FA_get_cookies.py                        # 代理走 7897（默认）
    python FA_get_cookies.py --proxy off            # 下载脚本也直连时用这个
    python FA_get_cookies.py --proxy http://127.0.0.1:7890

依赖：DrissionPage（py39 环境已装）+ Edge/Chrome
"""

import argparse
import json
import socket
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

_HERE = Path(__file__).resolve().parent
_ENV = _HERE.parent / "_dsp_env"          # 备用依赖目录（如存在）

# ---- 定位项目根目录（felinepaw/）并导入 i18n，供下面的提示语使用 ----
for _p in (_HERE.parent.parent, _HERE.parent, _HERE):
    if (_p / "i18n.py").exists():
        sys.path.insert(0, str(_p))
        break
import i18n
import local_creds        # 本机凭据快捷通道（.faenv；不进仓库）

try:
    from DrissionPage import ChromiumOptions, ChromiumPage
except ImportError:
    if _ENV.exists():
        sys.path.insert(0, str(_ENV))
        from DrissionPage import ChromiumOptions, ChromiumPage
    else:
        print(i18n.t("fa_err_no_drissionpage"))
        sys.exit(1)

SITE_LOGIN = "https://www.furaffinity.net/login/"

#: 本机 Clash 的混合端口。--proxy 不给就用它；给了 off/none 才直连。
DEFAULT_PROXY = "http://127.0.0.1:7897"

#: 兜底 UA —— 正常情况下从 FA_scraper.py 取，保证两边报同一个版本号。
_FALLBACK_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


def scraper_ua() -> str:
    """取 FA_scraper.py 用的那个 User-Agent。

    Cloudflare 发的 `cf_clearance` 绑定「出口 IP + User-Agent」。
    浏览器报一个版本号、requests 报另一个，cookie 立刻作废并重新下发挑战，
    所以这里直接把下载端的 UA 借过来，让浏览器也用同一个。
    """
    try:
        from FA_scraper import HEADERS as _H
        return _H.get("User-Agent") or _FALLBACK_UA
    except Exception:
        # 导入失败（路径/依赖问题）不该挡住取 cookie —— 退回同一份字面量
        return _FALLBACK_UA


def proxy_reachable(proxy: str, timeout: float = 1.5) -> bool:
    """代理端口有没有在监听。纯 TCP，不发 HTTP 请求。"""
    try:
        u = urlparse(proxy if "://" in proxy else "http://" + proxy)
        host, port = u.hostname, u.port or 7897
        if not host:
            return False
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def looks_challenged(page) -> bool:
    """浏览器这一页是不是停在 Cloudflare 人机验证上。"""
    try:
        title = (page.title or "").lower()
        if "just a moment" in title:
            return True
        body = (page.html or "")[:3000].lower()
        return ("enable javascript and cookies" in body) or ("cf-mitigated" in body)
    except Exception:
        return False


def input_password(prompt: str = i18n.t("fa_prompt_password")) -> str:
    """密码输入：每键显示一个 *，退格可修改（Windows 用 msvcrt）。"""
    if sys.platform != "win32":
        import getpass
        return getpass.getpass(prompt)
    import msvcrt
    sys.stdout.write(prompt)
    sys.stdout.flush()
    pwd = []
    while True:
        try:
            ch = msvcrt.getwch()
        except KeyboardInterrupt:
            sys.stdout.write("\n")
            raise
        if ch in ("\r", "\n"):
            break
        if ch in ("\b", "\x7f"):
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


def stdin_is_interactive() -> bool:
    """能不能安全地问用户要输入。

    本脚本是**终端专用**的：它既问账号密码，又会弹一个真实浏览器等用户手过验证码。
    被当成 GUI 子进程起来（pythonw、stdin 已 EOF）时必须立刻说清楚，
    而不是抛 `EOFError` 让用户对着一坨 traceback 发呆 —— 更糟的是
    `input_password()` 走 msvcrt.getwch()，那种环境下**不报错、直接卡死**。
    """
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except (ValueError, OSError):
        return False


def build_browser(proxy: str) -> ChromiumOptions:
    """把浏览器配置成「和下载脚本同一个出口、同一个 UA」。"""
    co = ChromiumOptions()
    co.set_argument("--no-sandbox")
    # Cloudflare 会看 navigator.webdriver；这一条让自动化特征没那么刺眼
    co.set_argument("--disable-blink-features=AutomationControlled")

    if proxy:
        if proxy_reachable(proxy):
            co.set_argument("--proxy-server", proxy)
            print(i18n.t("fa_browser_proxy", proxy=proxy))
        else:
            # 代理没开就别硬设 —— 设了浏览器连首页都打不开，报错会莫名其妙
            print(i18n.t("fa_proxy_dead", proxy=proxy))
    else:
        print(i18n.t("fa_browser_direct"))

    co.set_user_agent(scraper_ua())
    return co


def main():
    parser = argparse.ArgumentParser(
        description="用真实浏览器过 Cloudflare 验证并导出 FA cookies")
    parser.add_argument("--proxy", default=DEFAULT_PROXY,
                        help="浏览器走的代理，默认 %s；写 off 表示直连" % DEFAULT_PROXY)
    args = parser.parse_args()
    raw = (args.proxy or "").strip()
    proxy = "" if raw.lower() in ("off", "none", "") else raw

    # 本机快捷通道优先：.faenv 里已有账号密码就不用再打一遍
    creds = local_creds.load_fa_creds()
    username = creds.get("username") or ""
    password = creds.get("password") or ""
    if username and password:
        print(i18n.t("fa_creds_loaded"))
    else:
        if not stdin_is_interactive():
            print(i18n.t("fa_getcookie_no_tty"))
            sys.exit(2)
        if not username:
            username = input(i18n.t("fa_prompt_username")).strip()
        if not password:
            password = input_password(i18n.t("fa_prompt_password"))

    co = build_browser(proxy)
    edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if Path(edge).exists():
        co.set_browser_path(edge)
    elif Path(chrome).exists():
        co.set_browser_path(chrome)

    print(i18n.t("fa_opening_browser"))
    page = ChromiumPage(co)
    try:
        page.get(SITE_LOGIN)
        time.sleep(3)

        # Cloudflare 挑战是「等你动手」的页面，得先告诉用户点一下，
        # 否则他会看着一个白屏发呆，以为脚本卡死了。
        if looks_challenged(page):
            print(i18n.t("fa_challenge_in_browser"))

        # 自动填写用户名/密码
        try:
            name_box = page.ele('xpath://input[@name="name"]', timeout=10)
            name_box.input(username)
            pass_box = page.ele('xpath://input[@name="pass"]', timeout=5)
            pass_box.input(password)
            print(i18n.t("fa_autofill_ok"))
        except Exception as e:
            print(i18n.t("fa_autofill_failed", e=e))

        print(i18n.t("fa_captcha_hint"))
        # 点击登录按钮（若可点击）
        try:
            btn = page.ele('xpath://input[@name="login"]', timeout=3)
            btn.click()
        except Exception:
            pass

        # 等待登录成功：出现用户链接或跳离登录页
        logged_in = False
        for i in range(90):                 # 最多等 3 分钟
            time.sleep(2)
            try:
                url = page.url.lower()
                if "/login" not in url:
                    # 已跳离登录页
                    if page.ele(f'xpath://a[contains(@href,"/user/{username.lower()}/")]', timeout=1):
                        logged_in = True
                        break
                    logged_in = True        # 保守：跳离登录页即认为成功
                    break
                if page.ele(f'xpath://a[contains(@href,"/user/{username.lower()}/")]', timeout=1):
                    logged_in = True
                    break
            except Exception:
                continue
            if i % 15 == 0:
                print(i18n.t("fa_waiting_login", sec=i * 2))

        if not logged_in:
            print(i18n.t("fa_login_timeout"))
            sys.exit(1)

        # 导出 cookies（DrissionPage -> JSON）
        cookies = json.loads(page.cookies().as_json())
        out = _HERE / "fa_cookies.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        print(i18n.t("fa_cookies_saved", path=out))
        print(i18n.t("fa_cookies_next_hint", n=len(cookies)))
        # 通行证有时效，且和「节点 + 浏览器版本」绑定 —— 不说清他下次会以为是脚本坏了
        print(i18n.t("fa_cookies_expiry_hint"))
    finally:
        try:
            page.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
