#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
common.py - 多站点爬虫共享模块（felinepaw 基础库）
==============================================
统一提供：
- 代理检测与应用（Windows 系统代理、环境变量）
- 带重试与代理的 requests 会话
- 文件名清理、断点续传扫描、--limit 解析

供 sites/ 下各站点脚本复用，避免每个脚本复制一份相同代码。
用法：脚本内先定位本文件再 import：
    import os, sys
    _here = os.path.dirname(os.path.abspath(__file__))
    for _p in (os.path.dirname(_here), _here):
        if os.path.exists(os.path.join(_p, "common.py")):
            sys.path.insert(0, _p); break
    import common
"""

import os
import re
from pathlib import Path
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


# ============================================================
# 代理支持
# ============================================================

def _fix_proxy_scheme(url: str) -> str:
    """Windows 注册表里的 https 代理前缀对本地 Clash 类代理是错的，回环地址改成 http。"""
    low = url.strip().lower()
    if low.startswith("https://"):
        try:
            from urllib.parse import urlparse
            host = (urlparse(url).hostname or "").lower()
        except Exception:
            host = ""
        if host in ("127.0.0.1", "localhost", "::1") or host.startswith("127."):
            return "http://" + url[len("https://"):]
    return url


def detect_proxy() -> str:
    """自动检测代理：环境变量 -> Windows 系统代理设置；找不到返回空串。"""
    for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        v = os.environ.get(key, "").strip()
        if v:
            return _fix_proxy_scheme(v)
    try:
        import urllib.request
        proxies = urllib.request.getproxies()
        for key in ("https", "http"):
            v = (proxies.get(key) or "").strip()
            if v and "://" in v:
                return _fix_proxy_scheme(v)
    except Exception:
        pass
    return ""


def normalize_proxy(proxy: Optional[str]) -> str:
    """把用户填的代理整理成标准 URL；'off'/'auto' 等关键字分别处理。"""
    p = (proxy or "").strip()
    if not p:
        return ""
    low = p.lower()
    if low in ("off", "direct", "none", "不使用代理", "关闭"):
        return ""
    if low in ("auto", "自动", "跟随系统", "系统"):
        return detect_proxy()
    if "://" not in p:
        p = "http://" + p
    return _fix_proxy_scheme(p)


def apply_proxy(session: requests.Session, proxy: Optional[str] = None) -> None:
    """给会话应用代理。

    proxy: None/"" = 自动检测；"off" = 直连；其他 = 代理 URL。
    注意：requests 2.27 下仅设置 session.proxies 不生效，
    必须同时关闭 trust_env 才会使用显式代理。
    """
    if proxy is None or str(proxy).strip() == "":
        detected = detect_proxy()
        if detected:
            session.proxies = {"http": detected, "https": detected}
            session.trust_env = False
    else:
        p = normalize_proxy(proxy)
        if p:
            session.proxies = {"http": p, "https": p}
            session.trust_env = False


def create_session(proxy: Optional[str] = None,
                   headers: Optional[dict] = None) -> requests.Session:
    """创建带重试和代理的会话。"""
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1,
                  status_forcelist=[500, 502, 503, 504], allowed_methods=["GET"])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    if headers:
        session.headers.update(headers)
    apply_proxy(session, proxy)
    return session


# ============================================================
# 通用工具
# ============================================================

def sanitize_filename(name: str) -> str:
    """去除文件名/文件夹名中的非法字符。"""
    name = re.sub(r'[\\/*?:"<>|]', "_", name or "")
    name = re.sub(r"[\s.]+$", "", name).strip()
    return name or "untitled"


def find_existing_max(out_dir: Path) -> int:
    """扫描目录中已有的数字文件名，返回最大序号（断点续传用）。"""
    max_num = 0
    try:
        for f in out_dir.iterdir():
            if f.is_file() and f.stem.isdigit():
                try:
                    n = int(f.stem)
                except ValueError:
                    continue
                if n > max_num:
                    max_num = n
    except OSError:
        pass
    return max_num


def parse_limit(limit_str, total: int):
    """--limit 语义（各站点统一）：默认 120；inf=全部；正整数=前 N 个。

    参数非法时打印提示并返回 None（调用方应中止）。
    """
    if limit_str is None:
        return 120
    s = str(limit_str).strip().lower()
    if s == "inf":
        return total
    try:
        n = int(s)
    except ValueError:
        print("--limit 需要是正整数或 inf。")
        return None
    if n <= 0:
        print("--limit 需要是正整数或 inf。")
        return None
    return n
