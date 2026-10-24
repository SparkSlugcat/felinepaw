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
  · 浏览器身份 只能用浏览器**自己的**真实身份；它的 UA 会随 cookie 一起导出，
              下载脚本照着用（反过来硬改浏览器的 UA 会被判定为机器人）
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
#: 浏览器用户目录（固定，不随手删）。已经过掉的验证、登录态都存在这里。
PROFILE_DIR = _HERE / ".fa_profile"

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

def browser_ua(page) -> str:
    """读浏览器**自己**报的 User-Agent。

    方向很关键：不是把浏览器的 UA 改成下载脚本的，而是把浏览器的 UA 记下来交给下载脚本。

    Cloudflare 同时看两个头：`User-Agent` 和 `Sec-CH-UA`（后者由浏览器内核按真实
    版本号自动生成）。用 `--user-agent` 只改得动前一半，两个头对不上就是典型机器人
    特征 —— 验证会一直循环，点多少次都过不去。所以浏览器必须保持原样。
    """
    try:
        return (page.run_js("return navigator.userAgent") or "").strip()
    except Exception:
        return ""


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


def wait_login_form(page, timeout: int = 90):
    """等页面「定型」，返回用户名输入框。

    返回 None 表示页面上压根没有登录表单 —— 要么已经登录（FA 会跳离登录页），
    要么还卡在人机验证上（调用方自己用 looks_challenged() 区分）。

    为什么要等而不是 sleep 三秒：Cloudflare 挑战过掉之后浏览器会**重载一次页面**，
    这个时刻填进去的东西会被冲掉。固定 sleep 就是在赌这一下。
    """
    end = time.time() + timeout
    while time.time() < end:
        try:
            if not looks_challenged(page):
                box = page.ele('xpath://input[@name="name"]', timeout=2)
                if box:
                    return box
                if "/login" not in page.url.lower():
                    return None          # 已经登录、被跳走了
        except Exception:
            pass
        time.sleep(1)
    return None


def fill_login(page, username: str, password: str, tries: int = 3) -> bool:
    """填账号密码，并**回读核对**真的填进去了。

    `input()` 不抛异常 ≠ 填上了。所以每个字段填完都读一遍 `value`，
    对不上就重来（重载刚发生的那一两秒最容易碰上）。
    """
    fields = (('input[@name="name"]', username), ('input[@name="pass"]', password))
    for _ in range(tries):
        try:
            for xpath, value in fields:
                box = page.ele("xpath://" + xpath, timeout=5)
                box.clear()
                box.input(value)
            if all((page.ele("xpath://" + x, timeout=2).value or "") == v
                   for x, v in fields):
                return True
        except Exception:
            pass
        time.sleep(1)
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

    # ⚠️ 这里**不要**再调 set_user_agent()：见 browser_ua() 的说明。
    # 浏览器必须用它自己的真实身份，改了就过不了人机验证。

    # 固定用户目录：过掉的通行证、登录态、浏览记录都留到下次。
    # 每次都用全新临时目录 = 每次都是「零历史的新面孔」，更容易被反复挑战。
    co.set_user_data_path(str(PROFILE_DIR))
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
    try:
        page = ChromiumPage(co)
    except Exception as e:
        # 固定用户目录后最常见的原因是「上次的浏览器窗口还开着」，占着同一个目录
        print(i18n.t("fa_err_browser_start"))
        print(i18n.t("fa_err_browser_start_hint"))
        sys.exit(1)
    try:
        page.get(SITE_LOGIN)

        # Cloudflare 挑战是「等你动手」的页面，得先告诉用户点一下，
        # 否则他会看着一个白屏发呆，以为脚本卡死了。
        if looks_challenged(page):
            print(i18n.t("fa_challenge_in_browser"))

        # 等页面定型再动手填 —— 挑战过后浏览器会自己重载一次，
        # 重载会把刚输进去的内容清空（「提示填好了、实际是空的」就是这么来的）。
        form = wait_login_form(page)
        if form is None:
            if looks_challenged(page):
                print(i18n.t("fa_err_challenge_stuck"))
                sys.exit(1)
            # 固定用户目录里还留着上次的登录态，FA 已经跳离登录页
            print(i18n.t("fa_already_logged_in"))
        elif fill_login(page, username, password):
            print(i18n.t("fa_autofill_ok"))
            print(i18n.t("fa_captcha_hint"))
            try:
                page.ele('xpath://input[@name="login"]', timeout=3).click()
            except Exception:
                pass
        else:
            # 填不进去就别自动提交，交给用户手动来，别让他以为脚本已经搞定了
            print(i18n.t("fa_autofill_failed"))
            print(i18n.t("fa_captcha_hint"))

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
        # 通行证和「节点 IP + 浏览器 UA」绑定：把浏览器真实 UA 一并存下来，
        # 下载脚本读到它就会照用，两边报同一个身份。
        ua = browser_ua(page)
        if ua:
            out.with_name(out.stem + "_ua.txt").write_text(ua, encoding="utf-8")
            print(i18n.t("fa_ua_saved"))
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
