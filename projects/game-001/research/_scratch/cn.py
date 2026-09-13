#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Baidu SERP parser + Bilibili search (cookie bootstrap)."""
import sys, re, html, json, urllib.parse
import net

sys.stdout.reconfigure(encoding="utf-8")


def baidu(q, page=0):
    url = "https://www.baidu.com/s?wd=%s&pn=%d" % (urllib.parse.quote(q), page * 10)
    body = net.raw(url)
    out = []
    # result containers carry mu="realurl"
    for blk in re.split(r'<div[^>]*class="result', body)[1:]:
        m = re.search(r'mu="([^"]+)"', blk)
        real = html.unescape(m.group(1)) if m else ""
        t = re.search(r"(?s)<h3[^>]*>(.*?)</h3>", blk)
        title = net.text_of(t.group(1)) if t else ""
        # fallback: data-tools json
        if not real:
            m2 = re.search(r'"url":"(http[^"]+)"', blk)
            real = m2.group(1).replace("\\/", "/") if m2 else ""
        body_txt = net.text_of(blk)[:400]
        if title:
            out.append((title, real, body_txt))
    return out


def bili_search(kw, pages=1):
    import http.cookiejar
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        urllib.request.HTTPSHandler(context=net.CTX),
    )
    hdr = {
        "User-Agent": net.UA,
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://www.bilibili.com/",
    }
    try:
        op.open(urllib.request.Request("https://www.bilibili.com/", headers=hdr), timeout=25).read()
    except Exception as e:
        print("  [cookie bootstrap warn]", e)
    ck = "; ".join("%s=%s" % (c.name, c.value) for c in cj)
    hdr["Cookie"] = ck
    res = []
    for p in range(1, pages + 1):
        u = (
            "https://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword=%s&page=%d"
            % (urllib.parse.quote(kw), p)
        )
        try:
            r = op.open(urllib.request.Request(u, headers=hdr), timeout=30)
            j = json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            print("  [api fail]", type(e).__name__, e)
            return res
        if j.get("code") != 0:
            print("  [api code]", j.get("code"), j.get("message"))
            return res
        for it in (j.get("data") or {}).get("result") or []:
            res.append(
                {
                    "title": net.text_of(it.get("title", "")),
                    "bvid": it.get("bvid"),
                    "url": "https://www.bilibili.com/video/" + (it.get("bvid") or ""),
                    "play": it.get("play"),
                    "author": it.get("author"),
                    "desc": net.text_of(it.get("description", ""))[:300],
                    "dur": it.get("duration"),
                    "pubdate": it.get("pubdate"),
                }
            )
    return res


if __name__ == "__main__":
    mode = sys.argv[1]
    arg = sys.argv[2]
    if mode == "b":
        for i, r in enumerate(baidu(arg), 1):
            print("%d. %s" % (i, r[0]))
            print("   URL: %s" % r[1])
            print("   %s" % r[2][:300].replace("\n", " "))
            print()
    elif mode == "v":
        rs = bili_search(arg, int(sys.argv[3]) if len(sys.argv) > 3 else 1)
        print("### %s -> %d results" % (arg, len(rs)))
        for r in rs:
            print("- %s" % r["title"])
            print("  %s  play=%s dur=%s author=%s" % (r["url"], r["play"], r["dur"], r["author"]))
            if r["desc"]:
                print("  desc: %s" % r["desc"].replace("\n", " "))
