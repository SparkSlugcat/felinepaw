'''
下载 WildDream 用户的某个漫画文件夹（等价于一个 pool）
用法：
    python W_scraper.py "https://www.wilddream.net/art/userpage/gallery?userpagename=xxx&folderid=485" [--limit 80|inf] [-o 输出根目录]
特性：多线程收集前 limit 即停 / -o 建 <漫画名>/ 子文件夹 / 断点续传(.part+原子改名) / 礼貌请求(间隔+超时+重试)
'''

import time, requests, os, re, sys, random
from lxml import etree
from urllib.parse import urljoin, urlparse
import argparse

# Windows GBK 控制台可能编不了个别字符（emoji 等）→ 打印时替换为 '?'，避免 UnicodeEncodeError 崩溃
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")


main_site = 'https://www.wilddream.net/'
headers = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 Edg/152.0.0.0"}

# ============ 礼貌请求层：复用连接 + 全局间隔 + 超时 + 轻量重试 ============
_session = requests.Session()
_session.headers.update(headers)
_last_req_ts = 0.0
MIN_GAP = 0.5                 # 两次请求的最小间隔（秒）


def throttle():
    """保证两次请求之间至少隔 MIN_GAP(+随机抖动) 秒，避免被站点限流"""
    global _last_req_ts
    gap = MIN_GAP + random.uniform(0, 0.3)
    wait = gap - (time.time() - _last_req_ts)
    if wait > 0:
        time.sleep(wait)
    _last_req_ts = time.time()


def polite_get(url, timeout=20, stream=False, retries=2):
    """带礼貌间隔/超时/重试的 GET。流式下载请用 with polite_get(...) as r:"""
    for attempt in range(1 + retries):
        throttle()
        try:
            r = _session.get(url, timeout=timeout, stream=stream)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if attempt >= retries:
                raise
            print(f"  [WARN] 请求失败({e})，{attempt + 1} 秒后重试…")
            time.sleep(attempt + 1)
# =======================================================================


def sanitize_filename(name: str) -> str:
    """去除非法文件名字符，保证文件夹名合法"""
    name = re.sub(r'[\\/*?:"<>|]', '_', name)      # Windows 非法字符
    name = re.sub(r'[\s.]+$', '', name)            # 去除末尾空格或点
    name = name.strip()
    if not name:
        name = "untitled"
    return name


def get_post_url(url, limit=10 ** 9):
    """分页收集帖子链接；收集满 limit 即停（不浪费请求）"""
    post_url_lis = []
    n = 0
    while True:
        n += 1
        p_url = f"{url}&sort=dateline&page={n}"
        html = polite_get(p_url).text
        links = etree.HTML(html).xpath(
            '//div[contains(@class, "artwork_thumb")]/a/@href')
        if not links:                       # 空页 = 到底了
            break
        post_url_lis.extend(urljoin(main_site, t) for t in links)
        if len(post_url_lis) >= limit:      # 够了立刻停
            post_url_lis = post_url_lis[:limit]
            break
    print(f"共收集到 {len(post_url_lis)} 个帖子")
    return post_url_lis


def get_single_post(post_url):
    """进帖子页拿主图 URL 和文件名；页面异常时返回 (None, None)"""
    post_tree = etree.HTML(polite_get(post_url).text)
    src = post_tree.xpath('//img[@id="artwork_img"]/@src')
    if not src:                             # 该帖可能已删除/无图
        print(f"  [WARN] 无主图，跳过: {post_url}")
        return None, None
    img_url = urljoin(main_site, src[0])

    title = (post_tree.xpath('//title/text()') or [''])[0]
    ext = os.path.splitext(urlparse(img_url).path)[1]
    name = re.sub(r'[\\/*?:"<>|]', '_', title.split(' by ')[0].strip())
    return img_url, f"{name}{ext}"


def download_single(img_url, img_name, download_dir):
    """下载单图：已存在则跳过；写 .part 临时文件、完成后再原子改名。
    中断只留 .part，不会留下半截的"正式文件" → 重跑即可续传。"""
    path = os.path.join(download_dir, img_name)

    if os.path.exists(path) and os.path.getsize(path) > 0:
        print(f"已存在，跳过: {img_name}")
        return "skip"

    tmp = path + ".part"
    try:
        with polite_get(img_url, timeout=60, stream=True) as r:
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1024 * 64):
                    f.write(chunk)
        os.replace(tmp, path)               # 原子改名：要么没有，要么完整
        print(f"已保存: {img_name}")
        return "ok"
    except Exception as e:
        if os.path.exists(tmp):
            os.remove(tmp)                  # 失败清掉残留的 .part
        print(f"下载失败: {img_name} ({e})")
        return "fail"


def get_comic_name(tree):
    """返回漫画名；找不到给默认值，绝不抛 IndexError"""
    els = tree.xpath('//h4[contains(., "Comic")]')
    if not els:
        return "untitled"
    raw = els[0].text                       # 'Comic\t\t...：『诺瓦』'
    return raw.split('：')[-1].strip('『』 \t\r\n')   # → '诺瓦'


def parse_args():
    parser = argparse.ArgumentParser(description="下载 WildDream 用户的某个漫画文件夹")
    parser.add_argument("url", help="画廊 URL，例如 https://www.wilddream.net/art/userpage/gallery?userpagename=...&folderid=485")
    parser.add_argument("--limit", default="80",
                        help="最多下载张数：数字 或 inf(全部)；默认 80")
    parser.add_argument("-o", "--output", dest="output", default=".",
                        help="输出根目录（默认当前目录），会在其下建 <漫画名>/ 子文件夹")
    return parser.parse_args()


def parse_limit(s):
    """'inf' → 超大数(全部)；数字字符串 → int；非法返回 None"""
    s = str(s).strip().lower()
    if s == "inf":
        return 10 ** 9
    try:
        n = int(s)
        return n if n > 0 else None
    except ValueError:
        return None


def ensure_query(url):
    """URL 已带 ? 原样返回；路径式 URL 补一个 ?，让后续 &page= 拼接成立"""
    return url if "?" in url else url + "?"


def main():
    args = parse_args()
    base_url = ensure_query(args.url)

    limit_num = parse_limit(args.limit)
    if limit_num is None:
        print("--limit 需要是正整数或 inf，已按默认 80 处理")
        limit_num = 80
    elif limit_num >= 10 ** 9:
        print("下载全部 post")
    else:
        print(f"下载前 {limit_num} 个 post")

    # 抓首页取漫画名
    tree = etree.HTML(polite_get(base_url).text)
    file_name = get_comic_name(tree)
    print(f"漫画：{file_name}")

    post_url_lis = get_post_url(base_url, limit_num)
    if not post_url_lis:
        print("没有收集到任何帖子，退出。")
        return

    download_dir = os.path.join(os.path.abspath(args.output), file_name)
    os.makedirs(download_dir, exist_ok=True)
    print(f"下载目录：{download_dir}")

    ok = skip = fail = 0
    for post_url in post_url_lis:
        img_url, img_name = get_single_post(post_url)
        if not img_url:
            fail += 1
            continue
        st = download_single(img_url, img_name, download_dir)
        ok += st == "ok"
        skip += st == "skip"
        fail += st == "fail"

    print("=" * 40)
    print(f"完成：成功 {ok}，已存在跳过 {skip}，失败 {fail}")


if __name__ == '__main__':
    main()
