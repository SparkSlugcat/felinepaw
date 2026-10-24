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
import local_creds  # noqa: E402  （本机凭据快捷通道 .faenv；该数据文件不进仓库）
import felinepaw_tool as tool

SITES = ["e621", "e926", "yiff", "ehentai", "fa", "bbooru", "wilddream", "hypnohub", "rule34us"]
E621_MODES = ["tags", "page", "artist", "pool", "pool-rev"]
BBOORU_MODES = ["auto", "api", "html", "artist"]
#: FA_get_cookies.py 的默认产物 —— FA_scraper.py 没收到 --cookies 时也会自动用它
FA_COOKIE = HERE / "sites" / "furaffinity" / "fa_cookies.json"

#: 界面上可被「用不上就灰掉」的输入口。键名对应 input_spec() 返回的字典。
_INPUT_KEYS = ("target", "tags", "page", "pick", "pages", "limit", "proxy",
               "skip_others", "force_pool", "pool_rev", "force", "dry_run")


def input_spec(site: str, mode: str = "") -> dict:
    """这个站（这个模式）下，哪些输入口真的会被用到。

    分工只有一条 —— **目标网址 = 网址或编号，标签 = 标签**。
    e621 的 tags/page/artist 只吃标签，pool/pool-rev 只吃网址；
    yiff 是例外：它的位置参数就是标签（`yiff_scraper.py feline`），所以归标签框。
    """
    def spec(**on):
        base = dict.fromkeys(_INPUT_KEYS, False)
        base.update(limit=True, proxy=True)   # 大多数站都吃这两个
        base.update(on)
        return base

    if site in ("e621", "e926"):
        # e621 那批旧脚本没有 --proxy，proxy 一律不给
        if mode == "tags":
            return spec(tags=True, proxy=False)
        if mode == "page":
            return spec(tags=True, page=True, limit=False, proxy=False)
        if mode == "artist":
            return spec(tags=True, pick=True, dry_run=True, limit=False, proxy=False)
        return spec(target=True, limit=False, proxy=False)      # pool / pool-rev

    if site == "yiff":
        return spec(tags=True)                                  # 入口是标签，不是网址
    if site == "ehentai":
        return spec(target=True, tags=True, pick=True, pages=True, force=True, dry_run=True)
    if site == "fa":
        return spec(target=True, dry_run=True)
    if site == "bbooru":
        return spec(target=True, tags=True, skip_others=True, force_pool=True,
                    pool_rev=True, force=True, dry_run=True)
    if site == "wilddream":
        return spec(target=True, proxy=False)
    if site in ("hypnohub", "rule34us"):
        return spec(tags=True, page=True, force=True, dry_run=True)
    return spec()


def example_key(site: str, mode: str = "") -> str:
    """切到这个站时该显示哪句示例（词条 key，切语言能一起重译）。"""
    if site in ("e621", "e926"):
        return {"tags": "gui_ex_e621_tags", "page": "gui_ex_e621_page",
                "artist": "gui_ex_e621_artist", "pool": "gui_ex_e621_pool",
                "pool-rev": "gui_ex_e621_poolrev"}.get(mode, "gui_ex_e621_tags")
    return {"yiff": "gui_ex_yiff", "ehentai": "gui_ex_ehentai", "fa": "gui_ex_fa",
            "bbooru": "gui_ex_bbooru", "wilddream": "gui_ex_wilddream",
            "hypnohub": "gui_ex_tags_only", "rule34us": "gui_ex_tags_only"}.get(site, "")


class FelinepawGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.geometry("780x740")   # 参数区多了一行示例，日志区留住原来的高度
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

        # ---- FA 凭据（只在 site == fa 时露出来）----
        # 本机有 .faenv 就先填好 —— 这就是"本地快捷通道"：
        # 上传版没有这个文件，面板永远是空的，行为完全一样。
        creds = local_creds.load_fa_creds()
        self.fa_user_var = tk.StringVar(value=creds.get("username", ""))
        self.fa_pass_var = tk.StringVar(value=creds.get("password", ""))
        self.fa_cookie_var = tk.StringVar(value=creds.get("cookie_file", ""))
        self._fa_prefilled = bool(creds.get("username") or creds.get("password")
                                  or creds.get("cookie_file"))
        self._fa_visible = False          # 面板当前是否已 pack（切站/切语言都要靠它判断）

    def _build_lang_bar(self):
        """顶部语言小横条（靠右）：只建一次，重建参数区时不受 pack 顺序影响。

        pack(side="right") 是从右往左排的：先 pack 的占最右侧。
        所以先放下拉框、后放标签，屏幕上才是「标签 下拉框」的读法；
        `padx=(0, 14)` 是给窗口右边缘留的呼吸空间（原先标签直接贴边，太挤）。
        """
        self._lang_bar = ttk.Frame(self.root)
        self._lang_bar.pack(fill="x", padx=10, pady=(8, 0))
        self.lang_cb = ttk.Combobox(self._lang_bar, textvariable=self.lang_var, width=9,
                                    state="readonly", values=list(i18n.LANG_NAMES))
        self.lang_cb.pack(side="right", padx=(0, 14))
        self.lang_label = ttk.Label(self._lang_bar, text=i18n.t("gui_lang_label"))
        self.lang_label.pack(side="right", padx=(0, 6))
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
        for name in ("_fa_frame", "_bar_frame", "_act_frame", "_log_frame"):
            w = getattr(self, name, None)
            if w is not None:
                w.destroy()
        self._fa_visible = False          # 面板刚被销毁重建，肯定没 pack 出来

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
        # e621 换模式会换输入口（tags 吃标签、pool 吃网址），所以模式一变就重算
        self.mode_cb.bind("<<ComboboxSelected>>", lambda e: self._apply_inputs())

        # 第 1 行只放网址/编号，第 2 行只放标签 —— 别让人在两个框之间猜
        ttk.Label(bar, text=i18n.t("gui_target_url")).grid(row=1, column=0, padx=(8, 2), pady=6,
                                                           sticky="e")
        self.target_entry = ttk.Entry(bar, textvariable=self.target_var, width=40)
        self.target_entry.grid(row=1, column=1, columnspan=3, sticky="we", pady=6)

        ttk.Label(bar, text=i18n.t("gui_tags")).grid(row=2, column=0, padx=(8, 2), pady=6, sticky="e")
        self.tags_entry = ttk.Entry(bar, textvariable=self.tags_var, width=40)
        self.tags_entry.grid(row=2, column=1, columnspan=3, sticky="we", pady=6)

        ttk.Label(bar, text=i18n.t("gui_output")).grid(row=3, column=0, padx=(8, 2), pady=6, sticky="e")
        # 输入框和「浏览」放进同一个 Frame：按钮才会紧跟输入框右边。
        # 直接摆成两列的话，最右列带 weight 变宽后按钮会甩到中间去留一片空白。
        out_row = ttk.Frame(bar)
        out_row.grid(row=3, column=1, columnspan=3, sticky="we", pady=6)
        out_row.columnconfigure(0, weight=1)
        ttk.Entry(out_row, textvariable=self.out_var).grid(row=0, column=0, sticky="we")
        ttk.Button(out_row, text=i18n.t("gui_browse"), command=self._pick_dir).grid(
            row=0, column=1, padx=(6, 0))

        ttk.Label(bar, text=i18n.t("gui_limit")).grid(row=4, column=0, padx=(8, 2), pady=6, sticky="e")
        self.limit_entry = ttk.Entry(bar, textvariable=self.limit_var, width=10)
        self.limit_entry.grid(row=4, column=1, sticky="w", pady=6)
        ttk.Label(bar, text=i18n.t("gui_proxy")).grid(row=4, column=2, padx=(12, 2), pady=6, sticky="e")
        self.proxy_entry = ttk.Entry(bar, textvariable=self.proxy_var, width=24)
        self.proxy_entry.grid(row=4, column=3, sticky="w", pady=6)

        # 第 5 行：页码 + 高级选项（e621 page 模式 / bbooru --page / hypnohub --page）
        ttk.Label(bar, text=i18n.t("gui_page")).grid(row=5, column=0, padx=(8, 2), pady=6, sticky="e")
        self.page_entry = ttk.Entry(bar, textvariable=self.page_var, width=10)
        self.page_entry.grid(row=5, column=1, sticky="w", pady=6)
        opts = ttk.Frame(bar)
        opts.grid(row=5, column=2, columnspan=2, sticky="w", padx=(12, 2))
        # 勾选框也归类到输入口：用不上的站一并灰掉，不然勾了也白勾
        self._checks = {}
        for name, var, key in (
                ("skip_others", self.skip_others_var, "gui_skip_others"),
                ("force_pool", self.force_pool_var, "gui_force_pool"),
                ("pool_rev", self.pool_rev_var, "gui_pool_rev"),
                ("force", self.force_var, "gui_force")):
            chk = ttk.Checkbutton(opts, text=i18n.t(key), variable=var)
            chk.pack(side="left", padx=(0, 8))
            self._checks[name] = chk

        # 第 6 行：挑序号 / 每画廊限张 / 只列名单（e-hentai、e621 artist 用得上）
        ttk.Label(bar, text=i18n.t("gui_pick")).grid(row=6, column=0, padx=(8, 2), pady=6, sticky="e")
        self.pick_entry = ttk.Entry(bar, textvariable=self.pick_var, width=14)
        self.pick_entry.grid(row=6, column=1, sticky="w", pady=6)
        opts2 = ttk.Frame(bar)
        opts2.grid(row=6, column=2, columnspan=2, sticky="w", padx=(12, 2))
        ttk.Label(opts2, text=i18n.t("gui_pages")).pack(side="left")
        self.pages_entry = ttk.Entry(opts2, textvariable=self.pages_var, width=6)
        self.pages_entry.pack(side="left", padx=(2, 10))
        dry = ttk.Checkbutton(opts2, text=i18n.t("gui_dry_run"), variable=self.dry_var)
        dry.pack(side="left")
        self._checks["dry_run"] = dry

        # 第 7 行：这个站的示例（随站点/模式变，切语言一起重译）
        self.hint_label = ttk.Label(bar, text="", foreground="#0a58ca",
                                    wraplength=740, justify="left")
        self.hint_label.grid(row=7, column=0, columnspan=4, padx=8, pady=(0, 2), sticky="w")

        # 第 8 行：通用提示（跟站点无关的那些约定）
        ttk.Label(bar, text=i18n.t("gui_hint"),
                  foreground="gray", wraplength=740, justify="left"
                  ).grid(row=8, column=0, columnspan=4, padx=8, pady=(0, 4), sticky="w")
        # 多出来的宽度给最右一列，别给第 1 列。
        # 第 1 列装的是站点下拉框、数量限制、页码、挑序号 —— 让它当唯一带 weight 的列时，
        # 窗口只要比内容窄一点点，全部压缩都落在这一列上，这四个控件会被压成 1px 宽。
        # 英文文案比中文长（需求宽度差 100 多像素），所以英文界面必现。
        bar.columnconfigure(1, weight=0, minsize=110)
        bar.columnconfigure(3, weight=1)

        # ===== FA 凭据面板 =====
        # 单独一个 LabelFrame，而不是往 bar 里加行：只有 site == fa 时才 pack 出来，
        # 其它站点整块不占地方 —— 也不会让人以为"用 e621 也要填账号"。
        fa = ttk.LabelFrame(self.root, text=i18n.t("gui_fa_frame"))
        self._fa_frame = fa

        ttk.Label(fa, text=i18n.t("gui_fa_user")).grid(
            row=0, column=0, padx=(8, 2), pady=6, sticky="e")
        ttk.Entry(fa, textvariable=self.fa_user_var, width=22).grid(
            row=0, column=1, sticky="w", pady=6)
        ttk.Label(fa, text=i18n.t("gui_fa_pass")).grid(
            row=0, column=2, padx=(14, 2), pady=6, sticky="e")
        # show="*"：密码不以明文留在屏幕上（虽然它是 StringVar，只在内存里）
        ttk.Entry(fa, textvariable=self.fa_pass_var, width=22, show="*").grid(
            row=0, column=3, sticky="w", pady=6)

        ttk.Label(fa, text=i18n.t("gui_fa_cookie")).grid(
            row=1, column=0, padx=(8, 2), pady=6, sticky="e")
        ttk.Entry(fa, textvariable=self.fa_cookie_var, width=32).grid(
            row=1, column=1, columnspan=2, sticky="we", pady=6)
        fa_btns = ttk.Frame(fa)
        fa_btns.grid(row=1, column=3, sticky="w", padx=4, pady=6)
        ttk.Button(fa_btns, text=i18n.t("gui_browse"),
                   command=self._pick_cookie_file).pack(side="left")
        ttk.Button(fa_btns, text=i18n.t("gui_fa_save"),
                   command=self._save_fa_creds).pack(side="left", padx=(6, 0))

        ttk.Label(fa, text=i18n.t("gui_fa_hint"), foreground="gray",
                  wraplength=740, justify="left").grid(
            row=2, column=0, columnspan=4, padx=8, pady=(0, 6), sticky="w")
        fa.columnconfigure(1, weight=1)

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
        # height=8 是"最低要这么多行"，不是实际高度：日志区 expand=True 会吃掉剩余空间。
        # 默认的 24 行会让窗口的最小需求虚高 250px，窗口尺寸一自适应就顶到屏幕上沿。
        self.log_text = tk.Text(logf, wrap="word", state="disabled", height=8,
                                font=("Microsoft YaHei UI", 9))
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
        self._sync_fa_panel()      # 切语言重建后，按当前站点决定 FA 面板要不要露出来
        self._apply_inputs()       # 灰掉这个站用不上的输入口 + 填上示例
        self._fit_window()         # 英文文案更长：装不下就把窗口撑大，别让控件被压扁

    def _fit_window(self):
        """内容比窗口大时把窗口撑大（只增不减，且不超出屏幕）。

        切换语言会整体重建控件，文案长度变了需要的尺寸也跟着变 ——
        Tk 遇到装不下不会提示：宽度上会把列压扁（输入框变成一条竖线），
        高度上会把日志区压到只剩几行。这里量一次真实需求，不够就补。
        """
        self.root.update_idletasks()
        need_w = self.root.winfo_reqwidth() + 8
        need_h = self.root.winfo_reqheight() + 8
        cur_w, cur_h = self.root.winfo_width(), self.root.winfo_height()
        if cur_w <= 1:                     # 还没映射到屏幕，用初始几何值
            cur_w, cur_h = 780, 740
        room_w = self.root.winfo_screenwidth() - 80
        room_h = self.root.winfo_screenheight() - 120
        new_w = min(max(cur_w, need_w), room_w)
        new_h = min(max(cur_h, need_h), room_h)
        if (new_w, new_h) != (cur_w, cur_h):
            self.root.geometry("%dx%d" % (new_w, new_h))
        self.root.minsize(min(need_w, room_w), 540)

    def _set_status(self, key, **kw):
        """状态栏文案记成 (key, 参数)，切语言重建时能原样重译。"""
        self._status_key, self._status_kw = key, kw
        self.status_var.set(i18n.t(key, **kw))

    def _refresh_mode_options(self):
        """按站点切换模式下拉（只改标签与候选值）。"""
        site = self.site_var.get()
        if site in ("e621", "e926"):
            self.mode_label.config(text=i18n.t("gui_mode_e621"))
            values = E621_MODES
        elif site == "bbooru":
            self.mode_label.config(text=i18n.t("gui_mode_bbooru"))
            values = BBOORU_MODES
        else:
            self.mode_label.config(text=i18n.t("gui_mode"))
            values = []
        # 不按模式走的站（e-hentai / fa / yiff / 那几个 booru）根本没有模式可选，
        # 与其留一个空下拉框让人点，不如一起灰掉 —— 和别的输入口一个规矩。
        self.mode_cb.config(values=values, state="readonly" if values else "disabled")
        # 换了站点，原来的模式值可能不在新候选里（tags 之于 bbooru）——
        # 留着会让 input_spec() 走错分支，所以归位到第一个候选
        if values and self.mode_var.get() not in values:
            self.mode_var.set(values[0])

    def _apply_inputs(self):
        """按站点（和 e621/bbooru 的模式）把用不上的输入口灰掉，并显示该站示例。

        ⚠️ 灰掉只是提示，拦不住人 —— `StringVar.get()` 照样能读出旧文本。
        真正的把关在 `argparse_fix()`：那里会按同样的 input_spec() 把无效项置空。
        """
        site, mode = self.site_var.get(), self.mode_var.get()
        spec = input_spec(site, mode)
        entries = {
            "target": getattr(self, "target_entry", None),
            "tags": getattr(self, "tags_entry", None),
            "page": getattr(self, "page_entry", None),
            "pick": getattr(self, "pick_entry", None),
            "pages": getattr(self, "pages_entry", None),
            "limit": getattr(self, "limit_entry", None),
            "proxy": getattr(self, "proxy_entry", None),
        }
        for name, w in entries.items():
            if w is not None and w.winfo_exists():
                w.config(state="normal" if spec.get(name) else "disabled")
        for name, w in getattr(self, "_checks", {}).items():
            if w.winfo_exists():
                w.config(state="normal" if spec.get(name) else "disabled")

        key = example_key(site, mode)
        text = i18n.t(key) if key else ""
        if text and not all(spec.values()):
            text = text + "  " + i18n.t("gui_ex_disabled")
        if getattr(self, "hint_label", None) is not None and self.hint_label.winfo_exists():
            self.hint_label.config(text=text)

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
        # FA 需要登录态：把凭据面板露出来，并在日志里说清「要填什么、不填会怎样」。
        # 已经能自动用上导出好的 cookie 时就别吓唬人 —— 那种情况直接开始就行。
        if site == "fa":
            has_login = bool(self.fa_user_var.get().strip() and self.fa_pass_var.get().strip())
            has_cookie = bool(self.fa_cookie_var.get().strip()) or FA_COOKIE.exists()
            if has_login or has_cookie:
                self._log(i18n.t("gui_fa_ready"))
            else:
                self._log(i18n.t("gui_fa_guide1"))
                self._log(i18n.t("gui_fa_guide2"))
            if self._fa_prefilled:
                self._log(i18n.t("gui_fa_loaded"))
        self._refresh_mode_options()
        self._sync_fa_panel()
        self._apply_inputs()
        # 切站就把这个站怎么填打在日志里 —— 单功能站（fa/wilddream）尤其需要
        key = example_key(site, self.mode_var.get())
        if key:
            self._log(i18n.t(key))
        self._fit_window()      # FA 面板展开会多占一块高度，窗口不够就把日志区压扁了

    def _sync_fa_panel(self):
        """按当前站点显示/收起「FA 凭据」面板。

        用 pack / pack_forget 而不是把控件设成 disabled：不该看到的东西就别占地方。
        `before=self._act_frame` 是必须的 —— 后 pack 的控件默认排到最后，
        不收这个参数的话面板会跑到「开始/停止」按钮下面去。
        """
        frame = getattr(self, "_fa_frame", None)
        if frame is None or not frame.winfo_exists():
            return
        need = self.site_var.get() == "fa"
        if need and not self._fa_visible:
            frame.pack(fill="x", padx=10, pady=(0, 8), before=self._act_frame)
            self._fa_visible = True
        elif not need and self._fa_visible:
            frame.pack_forget()
            self._fa_visible = False

    def _pick_dir(self):
        d = filedialog.askdirectory(title=i18n.t("gui_choose_output_dir"))
        if d:
            self.out_var.set(d)

    def _pick_cookie_file(self):
        f = filedialog.askopenfilename(
            title=i18n.t("gui_dlg_cookie_file"),
            filetypes=[("JSON / cookie", "*.json *.txt"), ("*", "*.*")])
        if f:
            self.fa_cookie_var.set(f)

    def _save_fa_creds(self):
        """把当前三项写进本机 `.faenv`。

        这是**本机专属**动作：只写磁盘上那份 gitignore 过的文件，不碰任何仓库内容。
        """
        u = self.fa_user_var.get().strip()
        p = self.fa_pass_var.get().strip()
        c = self.fa_cookie_var.get().strip()
        if not (u or p or c):
            messagebox.showwarning(i18n.t("gui_tip_title"), i18n.t("gui_fa_save_empty"))
            return
        try:
            path = local_creds.save_fa_creds(username=u, password=p, cookie_file=c)
        except OSError as e:
            messagebox.showerror(i18n.t("gui_param_error"), str(e))
            return
        self._fa_prefilled = True
        messagebox.showinfo(i18n.t("gui_tip_title"), i18n.t("gui_fa_saved", path=path))
        self._log(i18n.t("gui_fa_saved", path=path))

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
            "workers": None, "delay": None,
            # FA 的 cookie 文件可以走命令行（路径不算敏感），账号密码走环境变量，见下面
            "cookies": self.fa_cookie_var.get().strip() or None,
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
        # ⚠️ 子进程的输出编码必须钉死成 utf-8。
        #    py39 在管道里默认按系统代码页（GBK）写，而下面 Popen 按 utf-8 读 ——
        #    只要不定这个变量，中文就全变乱码，用户看到的报错等于没看到。
        env["PYTHONIOENCODING"] = "utf-8"
        # ⚠️ FA 的账号密码**不走命令行**，走环境变量。两个原因：
        #   ① 下面这行 `self._log(">>> " + " ".join(cmd))` 会把整条命令打进日志框，
        #      密码以 --pass 传就会被明文展示在界面上（还可能被用户截图/贴出去）；
        #   ② 命令行参数在任务管理器/进程列表里是可见的。
        # FA_scraper.py 本来就读 FA_USERNAME/FA_PASSWORD，这里直接塞进去即可。
        if site == "fa":
            if self.fa_user_var.get().strip():
                env["FA_USERNAME"] = self.fa_user_var.get().strip()
            if self.fa_pass_var.get().strip():
                env["FA_PASSWORD"] = self.fa_pass_var.get().strip()
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
    """把 GUI 表单组装成命令行参数（复用 tool.build_command）。

    ⚠️ 这里是「界面灰掉」的兑现处：被禁用的输入框里可能还留着上一个站点输入的文本，
    StringVar 照样读得出来。所以先按 input_spec() 把用不上的项**置空**，
    再走各站的专属规则。
    """
    import argparse
    a = argparse.Namespace(**ns)
    spec = input_spec(site, a.mode or "")
    # ⚠️ 界面灰掉 = 这里作废。控件禁用拦不住 StringVar：切站后旧文本照样读得出来，
    #    漏给命令行会变成「明明没填却带了 --limit」这种怪事（build_command 只会打警告）。
    for name in ("target", "tags", "page", "pick", "pages", "limit", "proxy"):
        if not spec.get(name):
            setattr(a, name, None)
    for name, attr in (("skip_others", "skip_others"), ("force_pool", "force_pool_check"),
                       ("pool_rev", "pool_rev"), ("force", "force"), ("dry_run", "dry_run")):
        if not spec.get(name):
            setattr(a, attr, False)
    if site != "fa":
        a.cookies = None        # FA 面板藏起来了，但它的路径还留在变量里

    if site in ("e621", "e926"):
        # e621 的 tags/page/artist 用 --tags；pool/pool-rev 用位置参数
        if a.mode in ("tags", "page", "artist") and not a.tags:
            raise ValueError(i18n.t("gui_err_need_tags"))
    if site == "yiff":
        # yiff 的位置参数是标签：界面上的标签框 → 命令行位置参数
        if not a.tags:
            raise ValueError(i18n.t("tool_err_yiff_need"))
        a.target, a.tags = a.tags, None
    if site == "bbooru":
        if a.tags and a.target:
            raise ValueError(i18n.t("tool_err_bbooru_exclusive"))
        if a.tags:
            a.pool, a.target = None, None
        elif a.target:
            a.pool, a.target = a.target, None
        else:
            raise ValueError(i18n.t("gui_err_bbooru_input"))
    if site == "wilddream":
        if not a.target:
            raise ValueError(i18n.t("gui_err_wilddream_gallery"))
        a.tags = None
    if site in ("hypnohub", "rule34us"):
        if not a.tags:
            raise ValueError(i18n.t("gui_err_site_need_tags", site=site))
    if site == "ehentai":
        # 两个框都填了不报错，但只会用标签那个 —— 与其静默丢掉一半，不如说清楚
        if a.tags and a.target:
            raise ValueError(i18n.t("gui_err_ehentai_both"))
        if not (a.tags or a.target or getattr(a, "from_manifest", None)):
            raise ValueError(i18n.t("gui_err_ehentai_input"))
    return tool.build_command(site, a)


def main():
    root = tk.Tk()
    FelinepawGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
