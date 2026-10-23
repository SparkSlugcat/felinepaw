#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
local_creds.py — 本机凭据快捷通道（只服务「这台电脑」）
========================================================

各站点默认都要手输凭据或走命令行参数，本机用起来嫌啰嗦。所以这里提供一个
**只在本机存在**的文本文件，让 GUI / CLI 自动把凭据填好：

    <项目根>/.faenv            一行一条 `key=value`：
        username=
        password=
        cookie_file=fa_cookies.json

优先级（高 → 低）：命令行参数 > 环境变量 > `.faenv`

⚠️ 上传版 / 本地版的差别（重要）
--------------------------------
| 文件              | 性质     | 进仓库？ |
|-------------------|----------|----------|
| `local_creds.py`  | 通用代码 | ✅ 要     |
| `.faenv`          | 本机数据 | ❌ 绝不   |

`.faenv` 里是**明文密码**，等同于账号本身，已写进 `.gitignore`。
别人克隆这个仓库拿到的是本文件（能读但读不到东西），`fa` 面板会是空的 —— 这是对的。

不做成 `common.py` 的一部分，是因为 `common.py` 与 `e-hentai-paw/common.py`
必须逐字节同步，往里面塞 felinepaw 专属逻辑会立刻破坏那条约定。
"""

import os
from pathlib import Path
from typing import Dict

#: 本机凭据文件名（点开头是故意的：跟 .pawout / .ehcookie 一样，一眼看出是本机私有）
CRED_FILE = ".faenv"

#: `.faenv` 认识的键（顺序 = 保存时写出的顺序）
FA_KEYS = ("username", "password", "cookie_file")


def candidates():
    """`.faenv` 可能在哪：当前工作目录 → 本文件所在目录。

    当前目录优先：GUI 启动器会先 `cd /d "%~dp0"`，源码态和打包态都指向项目根。
    第二个位置是兜底 —— 万一用户在别的目录起 CLI，也还能找到项目根那份。
    """
    seen, out = set(), []
    for base in (Path.cwd(), Path(__file__).resolve().parent):
        f = base / CRED_FILE
        if str(f) not in seen:
            seen.add(str(f))
            out.append(f)
    return out


def find_file():
    """返回实际存在的 `.faenv`；都不存在返回 None。"""
    for f in candidates():
        if f.is_file():
            return f
    return None


def save_target():
    """保存时写到哪：已有文件就覆盖它，否则写当前目录那份。

    覆盖优先是为了「本机已经有一份就不要再多生一份」——
    文件散成两个位置时，用户改了 A 却生效 B，是最难查的那类问题。
    """
    existing = find_file()
    return existing if existing is not None else candidates()[0]


def read(path=None) -> Dict[str, str]:
    """读 `.faenv`，返回 `{key: value}`。文件不存在 / 读不了返回 {}。

    容错三件事：BOM（记事本另存会带）、GBK（老写入方式）、
    值里含 `=`（密码里很常见）—— 所以按**第一个** `=` 切。
    """
    p = Path(path) if path else find_file()
    if p is None:
        return {}
    text = None
    for enc in ("utf-8-sig", "gbk"):
        try:
            text = Path(p).read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue
        except OSError:
            return {}
    if text is None:
        return {}

    data = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().lower()
        if key:
            data[key] = value.strip()
    return data


def load_fa_creds() -> Dict[str, str]:
    """FA 凭据：环境变量优先，其次 `.faenv`。缺的键返回空串而不是不返回。

    环境变量优先是有意的 —— `set FA_USERNAME=...` 是**本次会话临时覆盖**，
    比改文件更轻，应该盖住磁盘上的旧值。
    """
    file_data = read()
    env_map = {
        "username": os.environ.get("FA_USERNAME", ""),
        "password": os.environ.get("FA_PASSWORD", ""),
        "cookie_file": os.environ.get("FA_COOKIES", ""),
    }
    out = {}
    for key in FA_KEYS:
        val = (env_map.get(key) or "").strip() or (file_data.get(key) or "").strip()
        out[key] = val
    return out


def save_fa_creds(username="", password="", cookie_file=""):
    """把三项写进 `.faenv`（空值不写）。返回写入路径。

    只给 GUI 的「保存到 .faenv」按钮用 —— 这是**本机专属**动作，
    上传版永远走不到这里（没有文件也没有按钮的默认值）。
    """
    values = {
        "username": (username or "").strip(),
        "password": (password or "").strip(),
        "cookie_file": (cookie_file or "").strip(),
    }
    path = save_target()
    lines = [
        "# felinepaw 本机凭据 —— 明文密码，已 gitignore，绝不提交",
        "# 由 GUI 的「保存到 .faenv」写入；也可以手改。",
    ]
    for key in FA_KEYS:
        if values[key]:
            lines.append("%s=%s" % (key, values[key]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
