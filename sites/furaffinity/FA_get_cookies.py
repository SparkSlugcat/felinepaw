#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FA cookies 获取器（浏览器模式）
==============================================
FA 登录页含 JS 验证码（fa-captcha），纯 requests 登录会被拦截。
本脚本用 DrissionPage 打开真实浏览器：
  1. 自动填好用户名/密码
  2. 如出现验证码，请你在浏览器窗口里手动完成
  3. 登录成功后自动导出 cookies 到 fa_cookies.json

之后运行 FA_scraper.py 时加 --cookies fa_cookies.json 即可跳过登录。

用法（推荐用 py39 环境）：
    conda activate py39
    python FA_get_cookies.py
    按提示输入用户名/密码（密码以 * 显示）
    -> 浏览器打开 FA 登录页，完成验证码（如有）
    -> 自动导出 fa_cookies.json

依赖：DrissionPage（py39 环境已装）+ Edge/Chrome
"""

import json
import re
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ENV = _HERE.parent / "_dsp_env"          # 备用依赖目录（如存在）

# ---- 定位项目根目录（felinepaw/）并导入 i18n，供下面的提示语使用 ----
for _p in (_HERE.parent.parent, _HERE.parent, _HERE):
    if (_p / "i18n.py").exists():
        sys.path.insert(0, str(_p))
        break
import i18n

try:
    from DrissionPage import ChromiumOptions, ChromiumPage
except ImportError:
    if _ENV.exists():
        sys.path.insert(0, str(_ENV))
        from DrissionPage import ChromiumOptions, ChromiumPage
    else:
        print(i18n.t("fa_err_no_drissionpage"))
        sys.exit(1)


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


def main():
    username = input(i18n.t("fa_prompt_username")).strip()
    password = input_password(i18n.t("fa_prompt_password"))

    co = ChromiumOptions()
    co.set_argument("--no-sandbox")
    edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if Path(edge).exists():
        co.set_browser_path(edge)
    elif Path(chrome).exists():
        co.set_browser_path(chrome)

    print(i18n.t("fa_opening_browser"))
    page = ChromiumPage(co)
    try:
        page.get("https://www.furaffinity.net/login/")
        time.sleep(3)

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
    finally:
        try:
            page.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
