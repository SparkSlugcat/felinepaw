# -*- coding: utf-8 -*-
"""
BBooru 下载器 GUI（tkinter）— 配合 B_scraper.py 打包成独立 exe
================================================================
- 界面选模式（标签 / 合集 / 艺术家）、填参数，点开始即可
- 直接在当前进程内调用 B_scraper.main(argv)，把 print 输出重定向到窗口日志
- 支持「停止」（调用 B_scraper.request_cancel()）
- 支持 --selftest（打包后自检：不开窗口，验证 frozen 环境能 import requests/common/B_scraper）

开发运行：python app.py
打包：见同目录 build_exe.bat / BBoorupaw.spec
"""

import io
import os
import queue
import sys
import threading
import tkinter as tk
import traceback
from tkinter import filedialog, messagebox, ttk

# ---------------------------------------------------------------
# 路径处理：源码运行 vs PyInstaller 冻结
# ---------------------------------------------------------------
if getattr(sys, "frozen", False):
    BASE = sys._MEIPASS                      # 打包后资源/模块根目录
    SITE_DIR = BASE
else:
    GUI_DIR = os.path.dirname(os.path.abspath(__file__))
    SITE_DIR = os.path.dirname(GUI_DIR)      # .../sites/BBooru
    BASE = os.path.dirname(os.path.dirname(SITE_DIR))   # .../felinepaw
for _p in (SITE_DIR, BASE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import B_scraper            # noqa: E402
import common               # noqa: E402
import i18n                 # noqa: E402


def resource_path(rel):
    """图标等资源路径（兼容冻结）"""
    root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, rel)


# ---------------------------------------------------------------
# 把 B_scraper 的 print 输出接进窗口（线程安全）
# ---------------------------------------------------------------
class QueueWriter(io.TextIOBase):
    # io.TextIOBase.encoding 是只读描述符，实例上赋值会抛 AttributeError；
    # 用类属性给出同样的值（print 不依赖它，但部分库会读）。
    encoding = "utf-8"

    def __init__(self, q):
        self.q = q
        self._buf = ""

    def write(self, s):
        if not s:
            return 0
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self.q.put(line)
        return len(s)

    def flush(self):
        if self._buf:
            self.q.put(self._buf)
            self._buf = ""


#: 模式内部名（界面上显示的是 bb_mode_<key> 的词条）
MODE_KEYS = ("tags", "pool", "artist")
ENGINES = ["auto", "api", "html"]


class PickDialog(tk.Toplevel):
    """「挑着下载」弹窗：Treeview + 勾选 + 全选/反选 + 下载选中。

    与 pixivpaw 的清单弹窗同一套交互（spark 已经用熟）：
    - 勾选状态存在 set 里，不塞进 Treeview（重建控件不丢勾）
    - 点任意一列都能切勾选（`<Button-1>` + `identify_row`，不依赖 selectmode）
    - 默认全选（最常见是「我全要」）
    - 确认时回调 on_pick([1-based 序号...])，序号直接喂 `--pick`
    - 关闭（确认或取消）都调 on_done，让父窗口恢复按钮状态
    """

    COLS = [
        ("check",  "bb_col_check",  4,  "center"),
        ("no",     "#",             6,  "e"),
        ("id",     "ID",            12, "w"),
        ("folder", "bb_col_folder", 18, "w"),
        ("url",    "bb_col_url",    64, "w"),
    ]
    _ASCII_W = 8

    def __init__(self, parent, items, on_pick, on_done=None):
        super().__init__(parent)
        self.items = items
        self.on_pick = on_pick
        self.on_done = on_done
        self.checked = set()          # 0-based 列表下标
        self.title(i18n.t("bb_pick_title", n=len(items)))
        self.geometry("980x620")
        self.transient(parent)
        self._build()
        self.checked = set(range(len(items)))     # 默认全选
        self._fill()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    # ---------------- 界面 ----------------
    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(top, text=i18n.t("bb_pick_hint")).pack(side="left")

        mid = ttk.Frame(self)
        mid.pack(fill="both", expand=True, padx=10, pady=4)
        cols = [c[0] for c in self.COLS]
        self.tree = ttk.Treeview(mid, columns=cols, show="headings", height=18)
        for cid, header, w, anchor in self.COLS:
            self.tree.heading(cid, text=i18n.t(header) if header.startswith("bb_") else header)
            self.tree.column(cid, width=w * self._ASCII_W, anchor=anchor,
                             stretch=(cid == "url"))
        self.tree.tag_configure("on", background="#e8f5e9")
        self.tree.tag_configure("off", foreground="#999")
        sb = ttk.Scrollbar(mid, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Button-1>", self._on_click_row)

        ops = ttk.Frame(self)
        ops.pack(fill="x", padx=10, pady=4)
        ttk.Button(ops, text=i18n.t("bb_pick_all"),
                   command=lambda: self._set_all(True)).pack(side="left")
        ttk.Button(ops, text=i18n.t("bb_pick_clear"),
                   command=lambda: self._set_all(False)).pack(side="left", padx=(6, 0))
        ttk.Button(ops, text=i18n.t("bb_pick_invert"),
                   command=self._invert).pack(side="left", padx=(6, 0))
        self.count_lbl = ttk.Label(ops, text="", foreground="gray")
        self.count_lbl.pack(side="left", padx=12)

        bot = ttk.Frame(self)
        bot.pack(fill="x", padx=10, pady=(4, 10))
        ttk.Button(bot, text=i18n.t("bb_pick_cancel"),
                   command=self._cancel).pack(side="right")
        self.ok_btn = ttk.Button(bot, text=i18n.t("bb_pick_confirm"), command=self._confirm)
        self.ok_btn.pack(side="right", padx=(0, 6))

    def _row_values(self, idx, checked):
        it = self.items[idx]
        return (
            "☑" if checked else "☐",
            str(it.get("index") or (idx + 1)),
            str(it.get("id") or ""),
            (it.get("folder") or "—"),
            (it.get("url") or ""),
        )

    def _fill(self):
        rows = []
        for i in range(len(self.items)):
            rows.append((str(i), self._row_values(i, True), ("on",)))
        if rows:
            for iid, vals, tags in rows:
                self.tree.insert("", "end", iid=iid, values=vals, tags=tags)
        self._refresh_count()

    # ---------------- 交互 ----------------
    def _on_click_row(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        try:
            idx = int(iid)
        except ValueError:
            return
        on = idx not in self.checked
        if on:
            self.checked.add(idx)
        else:
            self.checked.discard(idx)
        self.tree.item(iid, values=self._row_values(idx, on),
                       tags=("on" if on else "off",))
        self._refresh_count()

    def _set_all(self, on):
        self.checked = set(range(len(self.items))) if on else set()
        for i in range(len(self.items)):
            self.tree.item(str(i), values=self._row_values(i, on),
                           tags=("on" if on else "off",))
        self._refresh_count()

    def _invert(self):
        new = set(range(len(self.items))) - self.checked
        for i in range(len(self.items)):
            on = i in new
            self.tree.item(str(i), values=self._row_values(i, on),
                           tags=("on" if on else "off",))
        self.checked = new
        self._refresh_count()

    def _refresh_count(self):
        self.count_lbl.config(text=i18n.t("bb_pick_count",
                                          sel=len(self.checked), total=len(self.items)))
        self.ok_btn.config(state="normal" if self.checked else "disabled")

    def _confirm(self):
        idx_1b = sorted(self.items[i].get("index") or (i + 1) for i in self.checked)
        picked, done = self.on_pick, self.on_done
        self.destroy()
        if done:
            done()
        if picked:
            picked(idx_1b)

    def _cancel(self):
        done = self.on_done
        self.destroy()
        if done:
            done()


class BBooruGUI:
    def __init__(self, root):
        self.root = root
        root.geometry("860x640")
        # 队列 / 线程句柄常驻 self：切换语言重建界面时复用，不打断正在跑的任务
        self.queue = queue.Queue()
        self.evt_q = queue.Queue()      # 线程 → 主线程的事件（收集完成等）
        self.worker = None
        self._collecting = False        # 「挑着下载」的收集线程在跑（重建界面用）
        self._init_vars()
        self._build_ui()
        self._apply_icon()
        root.after(100, self._poll)

    # ---------------- 变量（跨界面重建保留用户输入，只建一次） ----------------
    def _init_vars(self):
        self._mode_key = "tags"                     # 模式内部名，界面上显示译名
        self._mode_idx = MODE_KEYS.index(self._mode_key)   # 下拉框身份用「下标」，不认译文
        self.mode_var = tk.StringVar(value=i18n.t("bb_mode_" + self._mode_key))
        self.engine_var = tk.StringVar(value="auto")
        self.tags_var = tk.StringVar()
        self.pool_var = tk.StringVar()
        self.out_var = tk.StringVar(value=".")
        self.limit_var = tk.StringVar()
        self.page_var = tk.StringVar()
        self.threads_var = tk.StringVar(value="8")
        self.retry_var = tk.StringVar(value="2")
        self.adult_var = tk.StringVar(value="y")
        self.proxy_var = tk.StringVar()
        self.rev_var = tk.BooleanVar(value=False)
        self.skip_var = tk.BooleanVar(value=False)
        self.dry_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value=i18n.t("bb_status_ready"))
        self.lang_var = tk.StringVar(value=i18n.LANG_NAMES[0 if i18n.get_lang() == "zh" else 1])

    # ---------------- UI ----------------
    def _apply_icon(self):
        try:
            ico = resource_path(os.path.join("assets", "icon.ico"))
            if os.path.exists(ico):
                self.root.iconbitmap(ico)
        except Exception:
            pass

    def _build_ui(self):
        """整体重建界面（语言切换）；日志框里的历史行原样保留、不重译。"""
        log_text = ""
        try:
            if hasattr(self, "log_text"):
                log_text = self.log_text.get("1.0", "end-1c")
        except Exception:
            log_text = ""

        for attr in ("_topbar_frame", "_params_frame", "_action_frame", "_log_frame"):
            w = getattr(self, attr, None)
            if w is not None:
                w.destroy()
                setattr(self, attr, None)

        self.root.title(i18n.t("bb_app_title"))
        self._build_langbar()
        self._build_params()
        self._build_action()
        self._build_log()

        if log_text:
            self.log_text.configure(state="normal")
            self.log_text.insert("1.0", log_text)
            self.log_text.configure(state="disabled")

        self._restore_state()

    def _build_langbar(self):
        # 顶部小横条：语言下拉框靠右，不动参数区的 grid 编号
        top = ttk.Frame(self.root)
        top.pack(fill="x", padx=10, pady=(8, 0))
        self._topbar_frame = top
        self.lang_var.set(i18n.LANG_NAMES[0 if i18n.get_lang() == "zh" else 1])
        lang_cb = ttk.Combobox(top, textvariable=self.lang_var, width=9, state="readonly",
                               values=list(i18n.LANG_NAMES))
        lang_cb.pack(side="right")
        lang_cb.bind("<<ComboboxSelected>>", self._on_lang_change)
        ttk.Label(top, text=i18n.t("bb_lang_label")).pack(side="right", padx=(0, 4))

    def _build_params(self):
        bar = ttk.LabelFrame(self.root, text=i18n.t("bb_params_frame"))
        bar.pack(fill="x", padx=10, pady=8)
        self._params_frame = bar

        # 模式
        ttk.Label(bar, text=i18n.t("bb_mode_label")).grid(row=0, column=0, padx=(8, 2), pady=6, sticky="e")
        self.mode_cb = cb = ttk.Combobox(bar, textvariable=self.mode_var, state="readonly", width=16,
                                         values=[i18n.t("bb_mode_" + k) for k in MODE_KEYS])
        cb.grid(row=0, column=1, padx=2, pady=6, sticky="w")
        cb.current(self._mode_idx)      # 按「下标」回填：译文变了也不会错位
        cb.bind("<<ComboboxSelected>>", self._on_mode_selected)

        ttk.Label(bar, text=i18n.t("bb_engine_label")).grid(row=0, column=2, padx=(12, 2), pady=6, sticky="e")
        self.engine_cb = ttk.Combobox(bar, textvariable=self.engine_var, state="readonly",
                                      width=8, values=ENGINES)
        self.engine_cb.grid(row=0, column=3, padx=2, pady=6, sticky="w")

        # 标签
        ttk.Label(bar, text=i18n.t("bb_tags_label")).grid(row=1, column=0, padx=(8, 2), pady=6, sticky="e")
        self.tags_entry = ttk.Entry(bar, textvariable=self.tags_var, width=46)
        self.tags_entry.grid(row=1, column=1, columnspan=3, sticky="we", pady=6)

        # 池子
        ttk.Label(bar, text=i18n.t("bb_pool_label")).grid(row=2, column=0, padx=(8, 2), pady=6, sticky="e")
        self.pool_entry = ttk.Entry(bar, textvariable=self.pool_var, width=46)
        self.pool_entry.grid(row=2, column=1, columnspan=3, sticky="we", pady=6)

        # 输出目录
        ttk.Label(bar, text=i18n.t("bb_output_label")).grid(row=3, column=0, padx=(8, 2), pady=6, sticky="e")
        ttk.Entry(bar, textvariable=self.out_var, width=40).grid(row=3, column=1, columnspan=2,
                                                                 sticky="we", pady=6)
        ttk.Button(bar, text=i18n.t("bb_browse"),
                   command=self._pick_dir).grid(row=3, column=3, padx=4)

        # 数量 / 线程 / 重试
        row = ttk.Frame(bar)
        row.grid(row=4, column=0, columnspan=4, sticky="we", padx=8, pady=2)
        ttk.Label(row, text=i18n.t("bb_limit_label")).pack(side="left")
        ttk.Entry(row, textvariable=self.limit_var, width=10).pack(side="left", padx=(2, 10))
        ttk.Label(row, text=i18n.t("bb_page_label")).pack(side="left")
        ttk.Entry(row, textvariable=self.page_var, width=6).pack(side="left", padx=(2, 10))
        ttk.Label(row, text=i18n.t("bb_threads_label")).pack(side="left")
        ttk.Entry(row, textvariable=self.threads_var, width=5).pack(side="left", padx=(2, 10))
        ttk.Label(row, text=i18n.t("bb_retry_label")).pack(side="left")
        ttk.Entry(row, textvariable=self.retry_var, width=5).pack(side="left", padx=(2, 10))
        ttk.Label(row, text=i18n.t("bb_adult_label")).pack(side="left")
        ttk.Combobox(row, textvariable=self.adult_var, values=["y", "n"], width=3,
                     state="readonly").pack(side="left", padx=(2, 0))

        # 代理 + 选项
        row2 = ttk.Frame(bar)
        row2.grid(row=5, column=0, columnspan=4, sticky="we", padx=8, pady=2)
        ttk.Label(row2, text=i18n.t("bb_proxy_label")).pack(side="left")
        ttk.Entry(row2, textvariable=self.proxy_var, width=26).pack(side="left", padx=(2, 10))
        ttk.Checkbutton(row2, text=i18n.t("bb_pool_rev"),
                        variable=self.rev_var).pack(side="left")
        ttk.Checkbutton(row2, text=i18n.t("bb_skip_others"),
                        variable=self.skip_var).pack(side="left", padx=6)
        ttk.Checkbutton(row2, text=i18n.t("bb_dry_run"),
                        variable=self.dry_var).pack(side="left", padx=6)

        ttk.Label(bar, text=i18n.t("bb_hint"),
                  foreground="gray").grid(row=6, column=0, columnspan=4, padx=8, pady=(0, 6),
                                          sticky="w")
        bar.columnconfigure(1, weight=1)

    def _build_action(self):
        act = ttk.Frame(self.root)
        act.pack(fill="x", padx=10, pady=4)
        self._action_frame = act
        self.start_btn = ttk.Button(act, text=i18n.t("bb_start"), command=self._start)
        self.start_btn.pack(side="left")
        self.pick_btn = ttk.Button(act, text=i18n.t("bb_pick_button"), command=self._pick_download)
        self.pick_btn.pack(side="left", padx=8)
        self.stop_btn = ttk.Button(act, text=i18n.t("bb_stop"), command=self._stop, state="disabled")
        self.stop_btn.pack(side="left", padx=8)
        ttk.Button(act, text=i18n.t("bb_open_output"),
                   command=self._open_out).pack(side="left", padx=8)
        ttk.Label(act, textvariable=self.status_var).pack(side="left", padx=12)

    def _build_log(self):
        logf = ttk.LabelFrame(self.root, text=i18n.t("bb_log_frame"))
        logf.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._log_frame = logf
        self.log_text = tk.Text(logf, wrap="word", state="disabled",
                                font=("Microsoft YaHei UI", 9))
        sb = ttk.Scrollbar(logf, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

    def _restore_state(self):
        """重建后按当前真实状态恢复按钮与状态栏（不重跑任何任务）。"""
        running = self.worker is not None and self.worker.is_alive()
        busy = running or self._collecting
        self.start_btn.config(state="disabled" if busy else "normal")
        self.pick_btn.config(state="disabled" if busy else "normal")
        self.stop_btn.config(state="normal" if running else "disabled")
        if running:
            self.status_var.set(i18n.t("bb_status_running"))
        elif self._collecting:
            self.status_var.set(i18n.t("bb_status_collecting"))
        else:
            self.status_var.set(i18n.t("bb_status_ready"))
        self._on_mode()

    def _on_lang_change(self, event=None):
        new = "zh" if self.lang_var.get() == i18n.LANG_NAMES[0] else "en"
        if new == i18n.get_lang():
            return
        i18n.set_lang(new)          # 同时写偏好
        self._build_ui()            # 重建（同进程：日志立刻变新语言）
        self._log(i18n.t("bb_lang_switched",
                         lang=i18n.LANG_NAMES[0 if new == "zh" else 1]))

    def _mode_key_from_display(self):
        """按下拉框**下标**取模式名。不拿译文反查 —— 两个模式译文一旦相同就会静默回退成 tags。"""
        try:
            idx = self.mode_cb.current()
        except (AttributeError, tk.TclError):
            return self._mode_key
        if 0 <= idx < len(MODE_KEYS):
            return MODE_KEYS[idx]
        return self._mode_key

    def _on_mode_selected(self, event=None):
        self._mode_key = self._mode_key_from_display()
        self._mode_idx = MODE_KEYS.index(self._mode_key)
        self._on_mode()

    def _on_mode(self):
        mode = self._mode_key
        # 艺术家模式也用 tags；pool 模式才用 pool 输入
        use_pool = mode == "pool"
        self.pool_entry.configure(state="normal" if use_pool else "disabled")
        self.tags_entry.configure(state="disabled" if use_pool else "normal")
        self.engine_cb.configure(state="readonly" if mode == "tags" else "disabled")
        self.rev_var.set(self.rev_var.get() and use_pool)

    # ---------------- 交互 ----------------
    def _pick_dir(self):
        d = filedialog.askdirectory(title=i18n.t("bb_choose_output_dir"))
        if d:
            self.out_var.set(d)

    def _open_out(self):
        p = os.path.abspath(self.out_var.get() or ".")
        try:
            os.startfile(p)
        except Exception:
            messagebox.showinfo(i18n.t("bb_tip_title"), i18n.t("bb_dir_is", p=p))

    def _log(self, msg):
        self.queue.put(str(msg))

    def _poll(self):
        try:
            while True:
                line = self.queue.get_nowait()
                self.log_text.configure(state="normal")
                self.log_text.insert("end", line + "\n")
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
        except queue.Empty:
            pass
        # 线程 → 主线程事件（收集完成后弹勾选框）
        while True:
            try:
                kind, payload, argv = self.evt_q.get_nowait()
            except queue.Empty:
                break
            if kind == "collected":
                self._on_collected(payload, argv)
        if self.worker is not None and not self.worker.is_alive():
            self._on_done()
        self.root.after(100, self._poll)

    # ---------------- 运行 ----------------
    def _build_argv(self):
        mode = self._mode_key
        tags = self.tags_var.get().strip()
        pool = self.pool_var.get().strip()
        argv = []

        if mode == "tags":
            if not tags:
                raise ValueError(i18n.t("bb_err_tags_need"))
            argv += ["--tags", tags, "--mode", self.engine_var.get()]
            if self.page_var.get().strip():
                argv += ["--page", self.page_var.get().strip()]
        elif mode == "pool":
            if not pool:
                raise ValueError(i18n.t("bb_err_pool_need"))
            argv += ["--pool", pool]
            if self.rev_var.get():
                argv += ["--pool-rev"]
        else:  # artist
            if not tags:
                raise ValueError(i18n.t("bb_err_artist_need"))
            argv += ["--tags", tags, "--mode", "artist"]
            if self.skip_var.get():
                argv += ["--skip-others"]

        if self.limit_var.get().strip():
            argv += ["--limit", self.limit_var.get().strip()]
        argv += ["--adult", self.adult_var.get()]
        if self.threads_var.get().strip():
            argv += ["--threads", self.threads_var.get().strip()]
        if self.retry_var.get().strip():
            argv += ["--retry", self.retry_var.get().strip()]
        argv += ["-o", self.out_var.get().strip() or "."]
        if self.proxy_var.get().strip():
            argv += ["--proxy", self.proxy_var.get().strip()]
        if self.dry_var.get():
            argv += ["--dry-run"]
        return argv

    def _start(self, argv=None):
        if self.worker is not None and self.worker.is_alive():
            messagebox.showinfo(i18n.t("bb_tip_title"), i18n.t("bb_task_running"))
            return
        if argv is None:
            try:
                argv = self._build_argv()
            except ValueError as e:
                messagebox.showwarning(i18n.t("bb_param_error"), str(e))
                return

        self._log(">>> " + " ".join(argv))
        self.start_btn.config(state="disabled")
        self.pick_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_var.set(i18n.t("bb_status_running"))
        self.worker = threading.Thread(target=self._run_worker, args=(argv,), daemon=True)
        self.worker.start()

    # ---------------- 挑着下载 ----------------
    def _pick_download(self):
        """先只收集列表 → 弹勾选框 → 用 --pick 只下勾中的。"""
        if self.worker is not None and self.worker.is_alive():
            messagebox.showinfo(i18n.t("bb_tip_title"), i18n.t("bb_task_running"))
            return
        try:
            argv = self._build_argv()
        except ValueError as e:
            messagebox.showwarning(i18n.t("bb_param_error"), str(e))
            return
        # 挑着下载的语义就是「收集完立刻挑着下」，所以去掉 --dry-run
        if "--dry-run" in argv:
            argv = [a for a in argv if a != "--dry-run"]
            self._log(i18n.t("bb_pick_ignore_dryrun"))

        self._log(i18n.t("bb_collect_echo") + " ".join(argv))
        self.start_btn.config(state="disabled")
        self.pick_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")
        self.status_var.set(i18n.t("bb_status_collecting"))
        self._collecting = True
        threading.Thread(target=self._collect_worker, args=(argv,), daemon=True).start()

    def _collect_worker(self, argv):
        writer = QueueWriter(self.queue)
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = writer
        ctx = None
        try:
            ctx = B_scraper.collect_only(argv)
        except SystemExit as e:
            self._log(i18n.t("bb_exit_code", code=e.code))
        except Exception:
            self._log("[ERROR] " + traceback.format_exc())
        finally:
            try:
                writer.flush()
            except Exception:
                pass
            sys.stdout, sys.stderr = old_out, old_err
        self.evt_q.put(("collected", ctx, argv))

    def _on_collected(self, ctx, argv):
        self._collecting = False
        items = (ctx or {}).get("items") or []
        if not items:
            self._log(i18n.t("bb_collect_failed_log"))
            self.status_var.set(i18n.t("bb_status_collect_failed"))
            self._reset_buttons()
            return
        self._log(i18n.t("bb_collected_log", n=len(items)))
        self.status_var.set(i18n.t("bb_status_pick"))

        def on_pick(idx):
            if not idx:
                self._log(i18n.t("bb_pick_none"))
                return
            self._log(i18n.t("bb_pick_start", n=len(idx)))
            self._start(argv + ["--pick", ",".join(str(i) for i in idx)])

        PickDialog(self.root, items, on_pick=on_pick, on_done=self._reset_buttons)

    def _reset_buttons(self):
        running = self.worker is not None and self.worker.is_alive()
        busy = running or self._collecting
        self.start_btn.config(state="disabled" if busy else "normal")
        self.pick_btn.config(state="disabled" if busy else "normal")
        self.stop_btn.config(state="normal" if running else "disabled")
        if not busy:
            self.status_var.set(i18n.t("bb_status_ready"))

    def _run_worker(self, argv):
        writer = QueueWriter(self.queue)
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = writer
        try:
            B_scraper.main(argv)
        except SystemExit as e:                 # argparse 退出等
            self._log(i18n.t("bb_exit_code", code=e.code))
        except Exception:
            self._log("[ERROR] " + traceback.format_exc())
        finally:
            try:
                writer.flush()
            except Exception:
                pass
            sys.stdout, sys.stderr = old_out, old_err

    def _on_done(self):
        self.worker = None
        self.start_btn.config(state="normal")
        self.pick_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_var.set(i18n.t("bb_status_done"))
        self._log(i18n.t("bb_task_end"))

    def _stop(self):
        B_scraper.request_cancel()
        self.status_var.set(i18n.t("bb_status_stopping"))
        self._log(i18n.t("bb_stop_requested"))


def _selftest():
    """打包后自检：验证 frozen 环境下依赖与模块可用（不开窗口）"""
    import tempfile
    lines = [
        f"frozen={getattr(sys, 'frozen', False)}",
        f"python={sys.version.split()[0]}",
        f"_MEIPASS={getattr(sys, '_MEIPASS', None)}",
        f"B_scraper={B_scraper.__file__}",
        f"common={common.__file__}",
    ]
    ns = B_scraper.parse_args(["--tags", "_selftest_", "--limit", "1", "--dry-run"])
    lines.append(f"parse_args OK: tags={ns.tags} limit={ns.limit} dry_run={ns.dry_run}")
    # 节流/预检参数（v1.1 起）：缺任何一个都说明打包时用了旧的 B_scraper.py
    lines.append(f"pacing/preflight args: delay={ns.delay} jitter={ns.jitter} "
                 f"cooldown={ns.cooldown} force={ns.force} no_preflight={ns.no_preflight}")
    lines.append(f"cancel API: reset={callable(B_scraper.reset_cancel)} "
                 f"request={callable(B_scraper.request_cancel)}")
    # 挑着下载（v1.2 起）：缺任何一个都说明打包时用了旧的 B_scraper.py
    lines.append(f"pick API: parse_pick={callable(getattr(B_scraper, 'parse_pick', None))} "
                 f"collect_only={callable(getattr(B_scraper, 'collect_only', None))}")
    lines.append(f"icon={resource_path(os.path.join('assets', 'icon.ico'))} "
                 f"exists={os.path.exists(resource_path(os.path.join('assets', 'icon.ico')))}")
    out = os.path.join(tempfile.gettempdir(), "bbooru_selftest.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out


def main():
    if "--selftest" in sys.argv:
        path = _selftest()
        print("selftest written:", path)
        return
    root = tk.Tk()
    BBooruGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
