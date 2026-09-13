#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fetch / search helper for web research (sandbox: schannel blocked, OpenSSL ok)."""
import sys, re, html, json, gzip, io, urllib.request, urllib.parse, ssl

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def raw(url, timeout=30, headers=None):
    h = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
    }
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    r = urllib.request.urlopen(req, timeout=timeout, context=CTX)
    data = r.read()
    enc = r.headers.get("Content-Encoding", "")
    if "gzip" in enc:
        try:
            data = gzip.decompress(data)
        except Exception:
            pass
    ctype = r.headers.get("Content-Type", "")
    m = re.search(r"charset=([\w-]+)", ctype, re.I)
    charset = m.group(1) if m else "utf-8"
    try:
        return data.decode(charset, "replace")
    except LookupError:
        return data.decode("utf-8", "replace")


def text_of(h):
    h = re.sub(r"(?is)<(script|style|noscript|svg|head)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"(?is)<br\s*/?>", "\n", h)
    h = re.sub(r"(?is)</(p|div|li|h[1-6]|tr|section)>", "\n", h)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    h = html.unescape(h)
    h = re.sub(r"[ \t\u00a0]+", " ", h)
    h = re.sub(r"\n\s*\n+", "\n", h)
    return h.strip()


def main():
    mode = sys.argv[1]
    arg = sys.argv[2]
    if mode == "get":
        try:
            body = raw(arg)
        except Exception as e:
            print("FETCH_FAIL", type(e).__name__, e)
            return
        if "--html" in sys.argv:
            print(body)
        else:
            t = text_of(body)
            lim = 6000
            for a in sys.argv:
                if a.startswith("--lim="):
                    lim = int(a.split("=")[1])
            print(t[:lim])
    elif mode == "search":
        q = urllib.parse.quote(arg)
        url = "https://www.bing.com/search?q=%s&format=rss&count=30" % q
        try:
            body = raw(url)
        except Exception as e:
            print("SEARCH_FAIL", type(e).__name__, e)
            return
        items = re.findall(r"(?s)<item>(.*?)</item>", body)
        if not items:
            print("NO_RSS_ITEMS len=%d" % len(body))
            print(text_of(body)[:1500])
        for it in items:
            t = re.search(r"(?s)<title>(.*?)</title>", it)
            l = re.search(r"(?s)<link>(.*?)</link>", it)
            d = re.search(r"(?s)<description>(.*?)</description>", it)
            print("- " + html.unescape(t.group(1)) if t else "- ?")
            print("  " + (html.unescape(l.group(1)) if l else ""))
            if d:
                print("  " + text_of(html.unescape(d.group(1)))[:260])
            print()
    elif mode == "ddg":
        q = urllib.parse.quote(arg)
        try:
            body = raw("https://html.duckduckgo.com/html/?q=" + q)
        except Exception as e:
            print("DDG_FAIL", type(e).__name__, e)
            return
        for m in re.finditer(r'(?s)result__a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', body):
            print("-", text_of(m.group(2))[:120])
            print("  ", html.unescape(m.group(1))[:220])
    elif mode == "json":
        try:
            body = raw(arg)
        except Exception as e:
            print("FETCH_FAIL", type(e).__name__, e)
            return
        print(body[:20000])


if __name__ == "__main__":
    main()
