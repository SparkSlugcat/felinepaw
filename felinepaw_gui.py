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
import common  # noqa: E402  （读本机默认输出目录 .pawout）
import i18n  # noqa: E402
import felinepaw_tool as tool

SITES = ["e621", "e926", "yiff", "ehentai", "fa", "bbooru", "wilddream", "hypnohub", "rule34us"]
E621_MODES = ["tags", "page", "artist", "pool", "pool-rev"]
BBOORU_MODES = ["auto", "api", "html", "artist"]


class FelinepawGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.geometry("780x620")
        self.queue = queue.Queue()
        self.proc = None
        self._status_key = "gui_idle"
        self._status_kw = {}
        self._init_vars()
        self._build_lang_bar()
        self._build_ui()
        root.after(100, self._poll)

    def _init_vars(self):
        """所有变量只建一次：切换语言整体重建控件时复用，用户已填的值自动保留。"""
        self.site_var = tk.StringVar(value=SITES[0])
        self.mode_var = tk.StringVar(value="tags")
        self.target_var = tk.StringVar()
        self.tags_var = tk.StringVar()
        self.out_var = tk.StringVar(value=str(common.local_out_root()))
        self.limit_var = tk.StringVar()
        self.proxy_var = tk.StringVar()
        self.page_var = tk.StringVar()
        self.skip_others_var = tk.BooleanVar(value=False)
        self.force_pool_var = tk.BooleanVar(value=False)
        self.pool_rev_var = tk.BooleanVar(value=False)
        self.force_var = tk.BooleanVar(value=False)
        self.pick_var = tk.StringVar()
        self.pages_var = tk.StringVar()
        self.dry_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value=i18n.t("gui_idle"))
        self.lang_var = tk.StringVar(value=i18n.LANG_NAMES[0 if i18n.get_lang() == "zh" else 1])

    def _build_lang_bar(self):
        """顶部语言小横条（靠右）：只建一次，重建参数区时不受 pack 顺序影响。"""
        self._lang_bar = ttk.Frame(self.root)
        self._lang_bar.pack(fill="x", padx=10, pady=(8, 0))
        self.lang_label = ttk.Label(self._lang_bar, text=i18n.t("gui_lang_label"))
        self.lang_label.pack(side="right", padx=(0, 6))
        self.lang_cb = ttk.Combobox(self._lang_bar, textvariable=self.lang_var, width=9,
                                    state="readonly", values=list(i18n.LANG_NAMES))
        self.lang_cb.pack(side="right")
        self.lang_cb.bind("<<ComboboxSelected>>", self._on_lang_change)

    def _on_lang_change(self, event=None):
        new = "zh" if self.lang_var.get() == i18n.LANG_NAMES[0] else "en"
        if new == i18n.get_lang():
            return
        i18n.set_lang(new)          # 同时写偏好
        self._build_ui()            # 重建
        self._log(i18n.t("gui_lang_switched", lang=i18n.LANG_NAMES[0 if new == "zh" else 1]))

    def _build_ui(self):
        # 先取出运行时状态：日志文本、按钮可用性 —— 切语言不打断任务、不丢日志
        log_text = ""
        start_state, stop_state = "normal", "disabled"
        if getattr(self, "_log_frame", None) is not None:
            log_text = self.log_text.get("1.0", "end-1c")
            start_state = str(self.start_btn.cget("state"))
            stop_state = str(self.stop_btn.cget("state"))
        for name in ("_bar_frame", "_act_frame", "_log_frame"):
            w = getattr(self, name, None)
            if w is not None:
                w.destroy()

        self.root.title(i18n.t("gui_app_title"))
        self.lang_label.config(text=i18n.t("gui_lang_label"))
        self.lang_var.set(i18n.LANG_NAMES[0 if i18n.get_lang() == "zh" else 1])

        bar = ttk.LabelFrame(self.root, text=i18n.t("gui_params_frame"))
        self._bar_frame = bar
        bar.pack(fill="x", padx=10, pady=8)

        ttk.Label(bar, text=i18n.t("gui_site")).grid(row=0, column=0, padx=(8, 2), pady=6, sticky="e")
        site_cb = ttk.Combobox(bar, textvariable=self.site_var, values=SITES,
                               state="readonly", width=12)
        site_cb.grid(row=0, column=1, padx=2, pady=6, sticky="w")
        site_cb.bind("<<ComboboxSelected>>", lambda e: self._on_site())

        self.mode_label = ttk.Label(bar, text=i18n.t("gui_mode_e621"))
        self.mode_label.grid(row=0, column=2, padx=(12, 2), pady=6, sticky="e")
        self.mode_cb = ttk.Combobox(bar, textvariable=self.mode_var, values=E621_MODES,
                                     state="readonly", width=9)
        self.mode_cb.grid(row=0, column=3, padx=2, pady=6, sticky="w")

        ttk.Label(bar, text=i18n.t("gui_target_tags")).grid(row=1, column=0, padx=(8, 2), pady=6, sticky="e")
        ttk.Entry(bar, textvariable=self.target_var, width=40).grid(row=1, column=1, columnspan=3,
                                                                    sticky="we", pady=6)

        ttk.Label(bar, text=i18n.t("gui_tags")).grid(row=2, column=0, padx=(8, 2), pady=6, sticky="e")
        ttk.Entry(bar, textvariable=self.tags_var, width=40).grid(row=2, column=1, columnspan=3,
                                                                  sticky="we", pady=6)

        ttk.Label(bar, text=i18n.t("gui_output")).grid(row=3, column=0, padx=(8, 2), pady=6, sticky="e")
        ttk.Entry(bar, textvariable=self.out_var, width=32).grid(row=3, column=1, columnspan=2,
                                                                 sticky="we", pady=6)
        ttk.Button(bar, text=i18n.t("gui_browse"), command=self._pick_dir).grid(row=3, column=3, padx=4)

        ttk.Label(bar, text=i18n.t("gui_limit")).grid(row=4, column=0, padx=(8, 2), pady=6, sticky="e")
        ttk.Entry(bar, textvariable=self.limit_var, width=10).grid(row=4, column=1, sticky="w", pady=6)
        ttk.Label(bar, text=i18n.t("gui_proxy")).grid(row=4, column=2, padx=(12, 2), pady=6, sticky="e")
        ttk.Entry(bar, textvariable=self.proxy_var, width=24).grid(row=4, column=3, sticky="w", pady=6)

        # 第 5 行：页码 + 高级选项（e621 page 模式 / bbooru --page / hypnohub --page）
        ttk.Label(bar, text=i18n.t("gui_page")).grid(row=5, column=0, padx=(8, 2), pady=6, sticky="e")
        ttk.Entry(bar, textvariable=self.page_var, width=10).grid(row=5, column=1, sticky="w", pady=6)
        opts = ttk.Frame(bar)
        opts.grid(row=5, column=2, columnspan=2, sticky="w", padx=(12, 2))
        ttk.Checkbutton(opts, text=i18n.t("gui_skip_others"),
                        variable=self.skip_others_var).pack(side="left")
        ttk.Checkbutton(opts, text=i18n.t("gui_force_pool"),
                        variable=self.force_pool_var).pack(side="left", padx=(8, 0))
        ttk.Checkbutton(opts, text=i18n.t("gui_pool_rev"),
                        variable=self.pool_rev_var).pack(side="left", padx=(8, 0))
        ttk.Checkbutton(opts, text=i18n.t("gui_force"),
                        variable=self.force_var).pack(side="left", padx=(8, 0))

        # 第 6 行：e-hentai 专用（挑序号 / 每画廊限张 / 只列名单）
        ttk.Label(bar, text=i18n.t("gui_pick")).grid(row=6, column=0, padx=(8, 2), pady=6, sticky="e")
        ttk.Entry(bar, textvariable=self.pick_var, width=14).grid(row=6, column=1, sticky="w", pady=6)
        opts2 = ttk.Frame(bar)
        opts2.grid(row=6, column=2, columnspan=2, sticky="w", padx=(12, 2))
        ttk.Label(opts2, text=i18n.t("gui_pages")).pack(side="left")
        ttk.Entry(opts2, textvariable=self.pages_var, width=6).pack(side="left", padx=(2, 10))
        ttk.Checkbutton(opts2, text=i18n.t("gui_dry_run"),
                        variable=self.dry_var).pack(side="left")

        ttk.Label(bar, text=i18n.t("gui_hint"),
                  foreground="gray", wraplength=740, justify="left"
                  ).grid(row=7, column=0, columnspan=4, padx=8, pady=(0, 4), sticky="w")
        bar.columnconfigure(1, weight=1)

        act = ttk.Frame(self.root)
        self._act_frame = act
        act.pack(fill="x", padx=10, pady=4)
        self.start_btn = ttk.Button(act, text=i18n.t("gui_start"), command=self._start)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(act, text=i18n.t("gui_stop"), command=self._stop, state="disabled")
        self.stop_btn.pack(side="left", padx=8)
        ttk.Label(act, textvariable=self.status_var).pack(side="left", padx=12)

        logf = ttk.LabelFrame(self.root, text=i18n.t("gui_log_frame"))
        self._log_frame = logf
        logf.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log_text = tk.Text(logf, wrap="word", state="disabled", font=("Microsoft YaHei UI", 9))
        sb = ttk.Scrollbar(logf, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

        # 回填日志、恢复按钮状态与状态栏文案
        if log_text:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", log_text)
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.start_btn.config(state=start_state)
        self.stop_btn.config(state=stop_state)
        self.status_var.set(i18n.t(self._status_key, **self._status_kw))
        self._refresh_mode_options()

    def _set_status(self, key, **kw):
        """状态栏文案记成 (key, 参数)，切语言重建时能原样重译。"""
        self._status_key, self._status_kw = key, kw
        self.status_var.set(i18n.t(key, **kw))

    def _refresh_mode_options(self):
        """按站点切换模式下拉（只改标签与候选值）。"""
        site = self.site_var.get()
        if site in ("e621", "e926"):
            self.mode_label.config(text=i18n.t("gui_mode_e621"))
            self.mode_cb.config(values=E621_MODES)
        elif site == "bbooru":
            self.mode_label.config(text=i18n.t("gui_mode_bbooru"))
            self.mode_cb.config(values=BBOORU_MODES)
        else:
            self.mode_label.config(text=i18n.t("gui_mode"))
            self.mode_cb.config(values=[])

    def _on_site(self):
        site = self.site_var.get()
        if site == "e926":
            self._set_status("gui_e926_status")
            self.start_btn.config(state="disabled")
            self._log(i18n.t("gui_e926_log1"))
            self._log(i18n.t("gui_e926_log2"))
        else:
            self.start_btn.config(state="normal")
            self._set_status("gui_idle")
        self._refresh_mode_options()

    def _pick_dir(self):
        d = filedialog.askdirectory(title=i18n.t("gui_choose_output_dir"))
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
            messagebox.showinfo(i18n.t("gui_tip_title"), i18n.t("gui_task_running"))
            return
        site = self.site_var.get()
        # 页码：留空 = None
        page_txt = self.page_var.get().strip()
        try:
            page_val = int(page_txt) if page_txt else None
        except ValueError:
            messagebox.showwarning(i18n.t("gui_param_error"), i18n.t("gui_page_must_be_number"))
            return
        # 组装参数（复用 tool 的 build_command 规则）
        ns = {
            "site": site, "mode": self.mode_var.get(), "target": self.target_var.get().strip(),
            "tags": self.tags_var.get().strip(), "page": page_val,
            "skip_others": self.skip_others_var.get(),
            "force_pool_check": self.force_pool_var.get(),
            "pool": None, "pool_rev": self.pool_rev_var.get(),
            "output": self.out_var.get().strip() or None,
            "limit": self.limit_var.get().strip() or None,
            "proxy": self.proxy_var.get().strip() or None,
            "workers": None, "delay": None, "cookies": None,
            "jitter": None, "cooldown": None, "force": self.force_var.get(),
            "no_preflight": False,
            "dry_run": self.dry_var.get(),
            "pick": self.pick_var.get().strip() or None,
            "pages": self.pages_var.get().strip() or None,
            "from_manifest": None, "manifest": None,
            "auto": False, "max_pages": None, "headless": False,
        }
        try:
            args = argparse_fix(site, ns)
        except ValueError as e:
            messagebox.showwarning(i18n.t("gui_param_error"), str(e))
            return
        cmd = args
        self._log(">>> " + " ".join(cmd))
        env = dict(os.environ)
        env[i18n.LANG_ENV] = i18n.get_lang()
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace", bufsize=1,
                                     cwd=str(HERE), env=env)
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self._set_status("gui_running")
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
        self._set_status("gui_done_status", code=code)
        self._log(i18n.t("gui_process_exit", code=code))

    def _stop(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            self._set_status("gui_stopping")
            self._log(i18n.t("gui_stop_requested"))


def argparse_fix(site, ns):
    """把 GUI 表单组装成命令行参数（复用 tool.build_command）。"""
    import argparse
    a = argparse.Namespace(**ns)
    # e621 的 tags 模式用 --tags；其他模式用 target
    if site in ("e621", "e926") and a.mode in ("tags", "page", "artist"):
        if not a.tags:
            raise ValueError(i18n.t("gui_err_need_tags"))
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
            raise ValueError(i18n.t("gui_err_bbooru_input"))
    if site == "wilddream":
        if not a.target:
            raise ValueError(i18n.t("gui_err_wilddream_gallery"))
        a.tags = None
    if site in ("hypnohub", "rule34us"):
        if not a.tags:
            raise ValueError(i18n.t("gui_err_site_need_tags", site=site))
        a.target = None
    if site == "ehentai":
        # 画廊 URL 走目标框，标签搜索走标签框；两者都没有就报错
        if not (a.tags or a.target or getattr(a, "from_manifest", None)):
            raise ValueError(i18n.t("gui_err_ehentai_input"))
    return tool.build_command(site, a)


def main():
    root = tk.Tk()
    FelinepawGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
