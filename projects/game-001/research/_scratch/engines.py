# -*- coding: utf-8 -*-
"""Sogou + Baidu search with cookie jar, delays and retries."""
import sys, re, html, time, random, urllib.parse, http.cookiejar, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
import net

_CJ = http.cookiejar.CookieJar()
_OP = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(_CJ),
    urllib.request.HTTPSHandler(context=net.CTX),
)
_OP.addheaders = [
    ("User-Agent", net.UA),
    ("Accept-Language", "zh-CN,zh;q=0.9"),
    ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
]


def fetch(url, referer=None, timeout=30):
    h = {}
    if referer:
        h["Referer"] = referer
    req = urllib.request.Request(url, headers=h)
    r = _OP.open(req, timeout=timeout)
    d = r.read()
    if "gzip" in r.headers.get("Content-Encoding", ""):
        import gzip
        try:
            d = gzip.decompress(d)
        except Exception:
            pass
    return d.decode("utf-8", "replace")


def sogou(q, page=1):
    u = "https://www.sogou.com/web?query=%s&page=%d" % (urllib.parse.quote(q), page)
    b = fetch(u, referer="https://www.sogou.com/")
    out = []
    for m in re.finditer(r'(?s)<h3[^>]*class="vr-title"[^>]*>(.*?)</h3>', b):
        blk = m.group(1)
        a = re.search(r'href="([^"]+)"', blk)
        title = net.text_of(blk)
        url = html.unescape(a.group(1)) if a else ""
        if url.startswith("/link"):
            url = "https://www.sogou.com" + url
        out.append((title, url, ""))
    if not out:
        for m in re.finditer(r'(?s)<h3[^>]*>(.*?)</h3>\s*(?:<div[^>]*class="[^"]*text-layout[^"]*"[^>]*>)?(.*?)(?=<h3|</body>)', b):
            title = net.text_of(m.group(1))
            url = ""
            a = re.search(r'href="([^"]+)"', m.group(1))
            if a:
                url = html.unescape(a.group(1))
            snip = net.text_of(m.group(2))[:300]
            if title:
                out.append((title, url, snip))
    return out


def baidu(q, page=0, tries=4):
    last = ""
    for i in range(tries):
        try:
            u = "https://www.baidu.com/s?wd=%s&pn=%d&ie=utf-8" % (urllib.parse.quote(q), page * 10)
            b = fetch(u, referer="https://www.baidu.com/")
            rows = []
            for blk in re.split(r'<div[^>]*class="result', b)[1:]:
                mu = re.search(r'mu="([^"]+)"', blk)
                real = html.unescape(mu.group(1)) if mu else ""
                t = re.search(r"(?s)<h3[^>]*>(.*?)</h3>", blk)
                title = net.text_of(t.group(1)) if t else ""
                if not real:
                    m2 = re.search(r'"url":"(http[^"]+)"', blk)
                    real = m2.group(1).replace("\\/", "/") if m2 else ""
                if title:
                    rows.append((title, real, net.text_of(blk)[:400]))
            if rows:
                return rows
            last = "empty(len=%d)" % len(b)
        except Exception as e:
            last = "%s: %s" % (type(e).__name__, e)
        time.sleep(4 + random.random() * 4)
    print("   [baidu gave up: %s]" % last, file=sys.stderr)
    return []


if __name__ == "__main__":
    eng = sys.argv[1]
    q = sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    fn = {"s": sogou, "b": baidu}[eng]
    for i, (t, u, sn) in enumerate(fn(q)[:n], 1):
        print("%d. %s" % (i, t))
        print("   %s" % u)
        if sn:
            print("   %s" % sn[:280].replace("\n", " "))
