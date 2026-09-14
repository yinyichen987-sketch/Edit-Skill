# -*- coding: utf-8 -*-
"""Fetch Bilibili video pages, extract title/desc/stat/owner from __INITIAL_STATE__."""
import sys, re, json, html
sys.stdout.reconfigure(encoding="utf-8")
import net

BVS = sys.argv[1:]


def detail(bv):
    u = "https://www.bilibili.com/video/%s/" % bv
    b = net.raw(u)
    out = {"bv": bv, "url": u}
    m = re.search(r"(?s)window\.__INITIAL_STATE__\s*=\s*(\{.*?\});\s*\(function", b)
    if not m:
        m = re.search(r"(?s)window\.__INITIAL_STATE__\s*=\s*(\{.*?\});", b)
    if m:
        js = m.group(1)
        js = js.replace("undefined", "null")
        try:
            d = json.loads(js)
        except Exception as e:
            out["parse_err"] = str(e)
            d = None
        if d:
            vd = d.get("videoData") or {}
            out["title"] = vd.get("title")
            out["desc"] = vd.get("desc")
            out["dur"] = vd.get("duration")
            out["pubdate"] = vd.get("pubdate")
            st = vd.get("stat") or {}
            out["view"] = st.get("view")
            out["like"] = st.get("like")
            out["danmaku"] = st.get("danmaku")
            out["owner"] = (vd.get("owner") or {}).get("name")
            out["tname"] = vd.get("tname")
            # pages / parts
            out["parts"] = [p.get("part") for p in (vd.get("pages") or [])]
    # fallback meta
    if not out.get("title"):
        t = re.search(r"(?s)<title[^>]*>(.*?)</title>", b)
        if t:
            out["title"] = net.text_of(t.group(1))
        dm = re.search(r'name="description"\s+content="([^"]*)"', b)
        if dm:
            out["desc"] = html.unescape(dm.group(1))
    return out


for bv in BVS:
    r = detail(bv)
    print("=" * 72)
    print("BV:", r.get("bv"))
    print("TITLE:", r.get("title"))
    print("URL:", r.get("url"))
    print("OWNER:", r.get("owner"), "| tname:", r.get("tname"))
    print("VIEW:", r.get("view"), "LIKE:", r.get("like"), "DANMAKU:", r.get("danmaku"))
    print("DUR(s):", r.get("dur"), "PUBDATE:", r.get("pubdate"))
    print("PARTS:", r.get("parts"))
    print("DESC:")
    print((r.get("desc") or "").strip())
    if r.get("parse_err"):
        print("PARSE_ERR:", r["parse_err"])
