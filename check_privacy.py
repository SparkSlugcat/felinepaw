#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_privacy.py — 扫产物里有没有本机路径 / 用户名 / 上级目录名
================================================================

打包完、以及**任何对外发布之前**跑一次。纯离线，不联网。

用法（在 felinepaw 目录下）：

    python check_privacy.py                       # 自动扫所有 dist\\*.exe
    python check_privacy.py 路径\\BBoorupaw.exe
    python check_privacy.py 路径\\xxx.exe --extra 敏感词1,敏感词2

为什么比 e-hentai-paw 那份多一层
--------------------------------
仓库可以放在任何不含用户名的目录里（典型情形：把整个工作区搬到了非系统盘，
路径里压根没有 `Users\\<name>` 这一段）。这时单靠「用户名路径形态」一条都扫不到，
真正泄露的是项目根上面那几级目录名。所以除了用户名形态，这里还把项目根
每一级上级目录名（带分隔符）和其中的中文串一起算作强模式。

两档判据（关键设计）
--------------------
- **强命中** = 路径形态 / 完整项目路径 / 上级目录名（含中文）→ 判失败，退出码 1
- **弱命中** = 裸用户名 → 只告警。几个字母在几十 MB 压缩数据里几乎必然出现几次
  （e621 的 icon.ico 里就出现过，周围全是高熵二进制）→ 只打印上下文，不判失败

一刀切「命中即失败」的检查会被训练成「反正都会红」，比没有还糟。

输出全 ASCII：Windows 控制台是 GBK，中文夹在批处理输出里会变乱码。
"""

import os
import re
import sys
from pathlib import Path

ENCODINGS = ("utf-8", "utf-16-le", "gbk")
MIN_NAME_LEN = 4          # 短于这个的目录名不当强模式（"src" / "tmp" 满屏都是）
NON_ASCII = re.compile(r"[^\x00-\x7f]")
DRIVE_ONLY = re.compile(r"^[A-Za-z]:$")


def _variants(text: str):
    """同一个字符串在三种编码下的字节形态（去重）。"""
    out = []
    for enc in ENCODINGS:
        try:
            b = text.encode(enc)
        except UnicodeEncodeError:
            continue
        if b and b not in out:
            out.append(b)
    return out


def _project_root():
    return Path(__file__).resolve().parent


def ancestor_names(root: Path):
    """项目根自己 + 每一级上级目录的**目录名**（不含盘符、不含空名）。"""
    names = []
    for p in [root] + list(root.parents):
        if DRIVE_ONLY.match(p.drive or "") and p.name == "":
            continue                      # 盘符根 D:\ 没有 name
        n = (p.name or "").strip()
        if n:
            names.append(n)
    return names


def strong_patterns(username, project_dir, extra=()):
    """路径形态 / 完整路径 / 上级目录名 —— 出现就是真的泄露。"""
    pats = []

    if username and len(username) >= 3:
        for form in ("\\%s\\" % username,        # ...\<user>\...
                     "Users\\%s" % username,     # C:\Users\<user>
                     "Users/%s" % username,      # .../Users/<name>
                     "/%s/" % username):         # /home/<user>
            pats.extend(_variants(form))

    root = Path(project_dir).resolve() if project_dir else _project_root()
    p = str(root).rstrip("\\/")
    if len(p) >= 6:
        for form in (p, p.replace("\\", "/")):
            pats.extend(_variants(form))

    # 上级目录名：带分隔符的形态（`\some-dir\` 这种），外加纯中文名本身。
    # 中文串在 ASCII 二进制里几乎不可能是巧合，所以直接当强模式。
    for name in ancestor_names(root):
        if len(name) < MIN_NAME_LEN:
            continue
        for form in ("\\%s\\" % name, "/%s/" % name):
            pats.extend(_variants(form))
        if NON_ASCII.search(name):
            pats.extend(_variants(name))

    for word in extra:
        w = (word or "").strip()
        if w:
            pats.extend(_variants(w))

    return pats


def weak_patterns(username):
    if username and len(username) >= 3:
        return _variants(username)
    return []


def scan(data: bytes, patterns, limit=5):
    """返回 [(offset, pattern_bytes)]，最多 limit 条。"""
    hits = []
    for pat in patterns:
        start = 0
        while True:
            i = data.find(pat, start)
            if i < 0:
                break
            hits.append((i, pat))
            if len(hits) >= limit:
                return hits
            start = i + len(pat)
    return hits


def context(data: bytes, off: int, span: int = 40) -> str:
    lo, hi = max(0, off - span), min(len(data), off + span)
    return "".join(chr(b) if 32 <= b < 127 else "." for b in data[lo:hi])


def find_targets(root: Path):
    """没给文件名时，把 dist 下的 exe 全找出来（跳过 _pyi_env / build）。"""
    seen, out = set(), []
    for pat in ("dist/*.exe", "sites/*/dist/*.exe", "sites/*/gui/dist/*.exe"):
        for f in sorted(root.glob(pat)):
            if "_pyi_env" in f.parts or "build" in f.parts:
                continue
            if f not in seen:
                seen.add(f)
                out.append(f)
    return out


def check_one(target: Path, username, project_dir, extra) -> int:
    """扫单个文件。返回 0 = 干净 / 1 = 强命中 / 2 = 无法检查。"""
    if not target.is_file():
        print("[privacy] file not found: %s" % target)
        return 2

    data = target.read_bytes()
    print("[privacy] file     : %s (%.1f MB)" % (target, len(data) / 1048576))
    print("[privacy] username : %s" % (username or "(none)"))
    print("[privacy] project  : %s" % project_dir)

    strong = scan(data, strong_patterns(username, project_dir, extra))
    weak = scan(data, weak_patterns(username))

    if strong:
        print("[privacy] FAIL - %d path-like hit(s):" % len(strong))
        for off, pat in strong:
            shown = pat.decode("utf-8", "replace").encode("ascii", "replace").decode("ascii")
            print("  0x%08X  %-24s  %s" % (off, shown, context(data, off)))
        print("[privacy] -> this artifact carries a local path. Do NOT ship it.")
        return 1

    if weak:
        print("[privacy] WARN - %d bare-username hit(s), likely compressed-data noise:"
              % len(weak))
        for off, _pat in weak:
            print("  0x%08X  %s" % (off, context(data, off)))
        print("[privacy] -> judge by context: a real leak has readable paths around it.")

    print("[privacy] OK  - no local path patterns found")
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    username = os.environ.get("USERNAME", "")
    project_dir = str(_project_root())
    extra = []

    targets = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--extra":
            i += 1
            if i < len(argv):
                extra = [x for x in re.split(r"[,;]", argv[i]) if x.strip()]
        elif a in ("-h", "--help"):
            print("usage: python check_privacy.py [file ...] [--extra word1,word2]")
            return 0
        else:
            # 批处理里 `"%~dp0"` 末尾的反斜杠会转义掉结束引号，传进来可能带尾引号
            targets.append(Path(a.strip().strip('"').strip()))
        i += 1

    if not targets:
        targets = find_targets(_project_root())
        if not targets:
            print("[privacy] no dist/*.exe found under %s" % _project_root())
            print("[privacy] build one first, or pass a file path explicitly.")
            return 2

    worst = 0
    for idx, t in enumerate(targets, 1):
        if len(targets) > 1:
            print("")
            print("[privacy] === %d/%d ===" % (idx, len(targets)))
        rc = check_one(t, username, project_dir, extra)
        worst = max(worst, rc)
    return worst


if __name__ == "__main__":
    sys.exit(main())
