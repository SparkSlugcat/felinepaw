# -*- coding: utf-8 -*-
"""
BBooru 下载器 GUI（tkinter）— 配合 B_scraper.py 打包成独立 exe
================================================================
- 界面选模式（标签 / 合集 / 艺术家）、填参数，点开始即可
- 直接在当前进程内调用 B_scraper.main(argv)，把 print 输出重定向到窗口日志
- 支持「停止」（调用 B_scraper.request_cancel()）
- 支持 --selftest（打包后自检：不开窗口，验证 frozen 环境能 import requests/common/B_scraper）

开发运行：python app.py
打包：见同目录 build_exe.bat / BBooruDownloader.spec
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


def resource_path(rel):
    """图标等资源路径（兼容冻结）"""
    root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, rel)


# ---------------------------------------------------------------
# 把 B_scraper 的 print 输出接进窗口（线程安全）
# ---------------------------------------------------------------
class QueueWriter(io.TextIOBase):
    def __init__(self, q):
        self.q = q
        self.encoding = "utf-8"
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


MODES = {
    "标签 (Tags)": "tags",
    "合集 (Pool)": "pool",
    "艺术家 (Artist)": "artist",
}
ENGINES = ["auto", "api", "html"]


class BBooruGUI:
    def __init__(self, root):
        self.root = root
        root.title("BBooru 下载器")
        root.geometry("860x640")
        self.queue = queue.Queue()
        self.worker = None
        self._build_ui()
        self._apply_icon()
        root.after(100, self._poll)

    # ---------------- UI ----------------
    def _apply_icon(self):
        try:
            ico = resource_path(os.path.join("assets", "icon.ico"))
            if os.path.exists(ico):
                self.root.iconbitmap(ico)
        except Exception:
            pass

    def _build_ui(self):
        bar = ttk.LabelFrame(self.root, text=" 下载参数 ")
        bar.pack(fill="x", padx=10, pady=8)

        # 模式
        ttk.Label(bar, text="模式:").grid(row=0, column=0, padx=(8, 2), pady=6, sticky="e")
        self.mode_var = tk.StringVar(value=list(MODES.keys())[0])
        cb = ttk.Combobox(bar, textvariable=self.mode_var, state="readonly", width=16,
                          values=list(MODES.keys()))
        cb.grid(row=0, column=1, padx=2, pady=6, sticky="w")
        cb.bind("<<ComboboxSelected>>", lambda e: self._on_mode())

        ttk.Label(bar, text="引擎(tags):").grid(row=0, column=2, padx=(12, 2), pady=6, sticky="e")
        self.engine_var = tk.StringVar(value="auto")
        self.engine_cb = ttk.Combobox(bar, textvariable=self.engine_var, state="readonly",
                                      width=8, values=ENGINES)
        self.engine_cb.grid(row=0, column=3, padx=2, pady=6, sticky="w")

        # 标签
        ttk.Label(bar, text="标签 --tags:").grid(row=1, column=0, padx=(8, 2), pady=6, sticky="e")
        self.tags_var = tk.StringVar()
        self.tags_entry = ttk.Entry(bar, textvariable=self.tags_var, width=46)
        self.tags_entry.grid(row=1, column=1, columnspan=3, sticky="we", pady=6)

        # 池子
        ttk.Label(bar, text="合集 --pool:").grid(row=2, column=0, padx=(8, 2), pady=6, sticky="e")
        self.pool_var = tk.StringVar()
        self.pool_entry = ttk.Entry(bar, textvariable=self.pool_var, width=46)
        self.pool_entry.grid(row=2, column=1, columnspan=3, sticky="we", pady=6)

        # 输出目录
        ttk.Label(bar, text="输出目录:").grid(row=3, column=0, padx=(8, 2), pady=6, sticky="e")
        self.out_var = tk.StringVar(value=".")
        ttk.Entry(bar, textvariable=self.out_var, width=40).grid(row=3, column=1, columnspan=2,
                                                                 sticky="we", pady=6)
        ttk.Button(bar, text="浏览...", command=self._pick_dir).grid(row=3, column=3, padx=4)

        # 数量 / 线程 / 重试
        row = ttk.Frame(bar)
        row.grid(row=4, column=0, columnspan=4, sticky="we", padx=8, pady=2)
        ttk.Label(row, text="数量 limit:").pack(side="left")
        self.limit_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.limit_var, width=10).pack(side="left", padx=(2, 10))
        ttk.Label(row, text="页 --page:").pack(side="left")
        self.page_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.page_var, width=6).pack(side="left", padx=(2, 10))
        ttk.Label(row, text="线程:").pack(side="left")
        self.threads_var = tk.StringVar(value="8")
        ttk.Entry(row, textvariable=self.threads_var, width=5).pack(side="left", padx=(2, 10))
        ttk.Label(row, text="重试:").pack(side="left")
        self.retry_var = tk.StringVar(value="2")
        ttk.Entry(row, textvariable=self.retry_var, width=5).pack(side="left", padx=(2, 10))
        ttk.Label(row, text="成人:").pack(side="left")
        self.adult_var = tk.StringVar(value="y")
        ttk.Combobox(row, textvariable=self.adult_var, values=["y", "n"], width=3,
                     state="readonly").pack(side="left", padx=(2, 0))

        # 代理 + 选项
        row2 = ttk.Frame(bar)
        row2.grid(row=5, column=0, columnspan=4, sticky="we", padx=8, pady=2)
        ttk.Label(row2, text="代理:").pack(side="left")
        self.proxy_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.proxy_var, width=26).pack(side="left", padx=(2, 10))
        self.rev_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row2, text="反转 pool 编号(--pool-rev)",
                        variable=self.rev_var).pack(side="left")
        self.skip_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row2, text="跳过非池帖子(--skip-others)",
                        variable=self.skip_var).pack(side="left", padx=6)
        self.dry_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row2, text="仅收集(--dry-run)", variable=self.dry_var).pack(side="left", padx=6)

        ttk.Label(bar, text="提示：limit 留空=默认120，填 inf=全部；代理留空=自动检测，off=直连",
                  foreground="gray").grid(row=6, column=0, columnspan=4, padx=8, pady=(0, 6),
                                          sticky="w")
        bar.columnconfigure(1, weight=1)

        # 按钮
        act = ttk.Frame(self.root)
        act.pack(fill="x", padx=10, pady=4)
        self.start_btn = ttk.Button(act, text="▶ 开始下载", command=self._start)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(act, text="■ 停止", command=self._stop, state="disabled")
        self.stop_btn.pack(side="left", padx=8)
        ttk.Button(act, text="打开输出目录", command=self._open_out).pack(side="left", padx=8)
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(act, textvariable=self.status_var).pack(side="left", padx=12)

        # 日志
        logf = ttk.LabelFrame(self.root, text=" 运行日志 ")
        logf.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log_text = tk.Text(logf, wrap="word", state="disabled",
                                font=("Microsoft YaHei UI", 9))
        sb = ttk.Scrollbar(logf, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

        self._on_mode()

    def _on_mode(self):
        mode = MODES.get(self.mode_var.get(), "tags")
        # 艺术家模式也用 tags；pool 模式才用 pool 输入
        use_pool = mode == "pool"
        self.pool_entry.configure(state="normal" if use_pool else "disabled")
        self.tags_entry.configure(state="disabled" if use_pool else "normal")
        self.engine_cb.configure(state="readonly" if mode == "tags" else "disabled")
        self.rev_var.set(self.rev_var.get() and use_pool)

    # ---------------- 交互 ----------------
    def _pick_dir(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.out_var.set(d)

    def _open_out(self):
        p = os.path.abspath(self.out_var.get() or ".")
        try:
            os.startfile(p)
        except Exception:
            messagebox.showinfo("提示", f"目录：{p}")

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
        if self.worker is not None and not self.worker.is_alive():
            self._on_done()
        self.root.after(100, self._poll)

    # ---------------- 运行 ----------------
    def _build_argv(self):
        mode = MODES.get(self.mode_var.get(), "tags")
        tags = self.tags_var.get().strip()
        pool = self.pool_var.get().strip()
        argv = []

        if mode == "tags":
            if not tags:
                raise ValueError("标签模式请在『标签 --tags』里填写标签")
            argv += ["--tags", tags, "--mode", self.engine_var.get()]
            if self.page_var.get().strip():
                argv += ["--page", self.page_var.get().strip()]
        elif mode == "pool":
            if not pool:
                raise ValueError("合集模式请在『合集 --pool』里填 pool 的 URL 或 id")
            argv += ["--pool", pool]
            if self.rev_var.get():
                argv += ["--pool-rev"]
        else:  # artist
            if not tags:
                raise ValueError("艺术家模式请在『标签 --tags』里填写艺术家标签")
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

    def _start(self):
        if self.worker is not None and self.worker.is_alive():
            messagebox.showinfo("提示", "任务正在运行中")
            return
        try:
            argv = self._build_argv()
        except ValueError as e:
            messagebox.showwarning("参数错误", str(e))
            return

        self._log(">>> " + " ".join(argv))
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_var.set("运行中...")
        self.worker = threading.Thread(target=self._run_worker, args=(argv,), daemon=True)
        self.worker.start()

    def _run_worker(self, argv):
        writer = QueueWriter(self.queue)
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = writer
        try:
            B_scraper.main(argv)
        except SystemExit as e:                 # argparse 退出等
            self._log(f"[退出码 {e.code}]")
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
        self.stop_btn.config(state="disabled")
        self.status_var.set("完成")
        self._log("[任务结束]")

    def _stop(self):
        B_scraper.request_cancel()
        self.status_var.set("正在停止（已下载的会保留，可重跑续传）...")
        self._log("[已请求停止]")


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
    lines.append(f"cancel API: reset={callable(B_scraper.reset_cancel)} "
                 f"request={callable(B_scraper.request_cancel)}")
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
