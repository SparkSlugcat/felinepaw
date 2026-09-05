#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
felinepaw_gui.py — 一体化工具 GUI v1（tkinter）
======================================================
e621 / yiff / e-hentai / furaffinity 统一图形界面。
参数映射复用 felinepaw_tool.py（同一套规则），运行于子进程并流式显示日志。

运行：python felinepaw_gui.py （需要 tkinter，Python 自带）
"""

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import felinepaw_tool as tool

SITES = ["e621", "e926", "yiff", "ehentai", "fa", "bbooru", "wilddream"]
E621_MODES = ["tags", "page", "artist", "pool", "pool-rev"]


class FelinepawGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("felinepaw 一体化下载器 v0.1")
        root.geometry("780x620")
        self.queue = queue.Queue()
        self.proc = None
        self._build_ui()
        root.after(100, self._poll)

    def _build_ui(self):
        bar = ttk.LabelFrame(self.root, text=" 任务参数 ")
        bar.pack(fill="x", padx=10, pady=8)

        ttk.Label(bar, text="站点:").grid(row=0, column=0, padx=(8, 2), pady=6, sticky="e")
        self.site_var = tk.StringVar(value=SITES[0])
        site_cb = ttk.Combobox(bar, textvariable=self.site_var, values=SITES,
                               state="readonly", width=12)
        site_cb.grid(row=0, column=1, padx=2, pady=6, sticky="w")
        site_cb.bind("<<ComboboxSelected>>", lambda e: self._on_site())

        ttk.Label(bar, text="模式(e621):").grid(row=0, column=2, padx=(12, 2), pady=6, sticky="e")
        self.mode_var = tk.StringVar(value="tags")
        ttk.Combobox(bar, textvariable=self.mode_var, values=E621_MODES,
                     state="readonly", width=9).grid(row=0, column=3, padx=2, pady=6, sticky="w")

        ttk.Label(bar, text="目标/标签:").grid(row=1, column=0, padx=(8, 2), pady=6, sticky="e")
        self.target_var = tk.StringVar()
        ttk.Entry(bar, textvariable=self.target_var, width=40).grid(row=1, column=1, columnspan=3,
                                                                    sticky="we", pady=6)

        ttk.Label(bar, text="标签(--tags):").grid(row=2, column=0, padx=(8, 2), pady=6, sticky="e")
        self.tags_var = tk.StringVar()
        ttk.Entry(bar, textvariable=self.tags_var, width=40).grid(row=2, column=1, columnspan=3,
                                                                  sticky="we", pady=6)

        ttk.Label(bar, text="输出目录:").grid(row=3, column=0, padx=(8, 2), pady=6, sticky="e")
        self.out_var = tk.StringVar()
        ttk.Entry(bar, textvariable=self.out_var, width=32).grid(row=3, column=1, columnspan=2,
                                                                 sticky="we", pady=6)
        ttk.Button(bar, text="浏览...", command=self._pick_dir).grid(row=3, column=3, padx=4)

        ttk.Label(bar, text="数量限制:").grid(row=4, column=0, padx=(8, 2), pady=6, sticky="e")
        self.limit_var = tk.StringVar()
        ttk.Entry(bar, textvariable=self.limit_var, width=10).grid(row=4, column=1, sticky="w", pady=6)
        ttk.Label(bar, text="代理:").grid(row=4, column=2, padx=(12, 2), pady=6, sticky="e")
        self.proxy_var = tk.StringVar()
        ttk.Entry(bar, textvariable=self.proxy_var, width=24).grid(row=4, column=3, sticky="w", pady=6)
        ttk.Label(bar, text="提示：代理留空=自动，off=直连；--limit 填 inf 表示全部",
                  foreground="gray").grid(row=5, column=0, columnspan=4, padx=8, pady=(0, 4), sticky="w")
        bar.columnconfigure(1, weight=1)

        act = ttk.Frame(self.root)
        act.pack(fill="x", padx=10, pady=4)
        self.start_btn = ttk.Button(act, text="▶ 开始", command=self._start)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(act, text="■ 停止", command=self._stop, state="disabled")
        self.stop_btn.pack(side="left", padx=8)
        self.status_var = tk.StringVar(value="空闲")
        ttk.Label(act, textvariable=self.status_var).pack(side="left", padx=12)

        logf = ttk.LabelFrame(self.root, text=" 运行日志 ")
        logf.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log_text = tk.Text(logf, wrap="word", state="disabled", font=("Microsoft YaHei UI", 9))
        sb = ttk.Scrollbar(logf, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)
        self._on_site()

    def _on_site(self):
        site = self.site_var.get()
        if site == "e926":
            self.status_var.set("e926 暂不可用（Cloudflare 拦截）")
            self.start_btn.config(state="disabled")
            self._log("⚠️ e926 暂不可用：被 Cloudflare 人机挑战拦截，纯 requests 无法访问。")
            self._log("   请改用 e621，或用浏览器访问 e926。")
        else:
            self.start_btn.config(state="normal")
            self.status_var.set("空闲")

    def _pick_dir(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.out_var.set(d)

    def _log(self, msg):
        self.queue.put(str(msg))

    def _poll(self):
        try:
            while True:
                msg = self.queue.get_nowait()
                self.log_text.configure(state="normal")
                self.log_text.insert("end", msg + "\n")
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
        except queue.Empty:
            pass
        if self.proc is not None and self.proc.poll() is not None:
            self._on_done(self.proc.returncode)
            self.proc = None
        self.root.after(100, self._poll)

    def _start(self):
        if self.proc is not None and self.proc.poll() is None:
            messagebox.showinfo("提示", "任务正在运行中")
            return
        site = self.site_var.get()
        # 组装参数（复用 tool 的 build_command 规则）
        ns = {
            "site": site, "mode": self.mode_var.get(), "target": self.target_var.get().strip(),
            "tags": self.tags_var.get().strip(), "page": None, "skip_others": False,
            "pool": None,
            "output": self.out_var.get().strip() or None,
            "limit": self.limit_var.get().strip() or None,
            "proxy": self.proxy_var.get().strip() or None,
            "workers": None, "delay": None, "cookies": None,
            "auto": False, "max_pages": None, "headless": False,
        }
        try:
            args = argparse_fix(site, ns)
        except ValueError as e:
            messagebox.showwarning("参数错误", str(e))
            return
        cmd = args
        self._log(">>> " + " ".join(cmd))
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace", bufsize=1,
                                     cwd=str(HERE))
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_var.set("运行中...")
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        try:
            for line in self.proc.stdout:
                self._log(line.rstrip("\n"))
        except Exception:
            pass

    def _on_done(self, code):
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_var.set(f"完成（退出码 {code}）")
        self._log(f"[进程结束，退出码 {code}]")

    def _stop(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            self.status_var.set("正在停止...")
            self._log("已请求停止")


def argparse_fix(site, ns):
    """把 GUI 表单组装成命令行参数（复用 tool.build_command）。"""
    import argparse
    a = argparse.Namespace(**ns)
    # e621 的 tags 模式用 --tags；其他模式用 target
    if site in ("e621", "e926") and a.mode in ("tags", "page", "artist"):
        if not a.tags:
            raise ValueError("请填写标签(--tags)")
        a.target = None
    if site == "bbooru":
        # 标签框填了 → 按标签；否则目标框当作 pool（show URL 或纯 id）
        if a.tags:
            a.pool = None
            a.target = None
        elif a.target:
            a.pool = a.target
            a.target = None
        else:
            raise ValueError("bbooru 需要填标签(--tags)，或在目标框填 pool URL/id")
    if site == "wilddream":
        if not a.target:
            raise ValueError("wilddream 需要画廊 URL（目标框）")
        a.tags = None
    return tool.build_command(site, a)


def main():
    root = tk.Tk()
    FelinepawGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
