# -*- coding: utf-8 -*-
import sys, json, io
sys.stdout.reconfigure(encoding="utf-8")
import cn

QUERIES = [
    "剪映 定格 教程",
    "剪映 曲线变速 教程",
    "剪映 闪白 教程",
    "剪映 击杀特效",
    "无畏契约 剪辑 教程",
    "瓦洛兰特 剪辑 教程",
    "剪映 卡点 教程",
    "剪映 音效 击杀",
    "剪映 抖动 震动 教程",
    "游戏高光 剪辑 教学",
    "剪映 高光 剪辑 教程",
    "CSGO 击杀 剪辑 教程",
    "五杀 剪辑 教程",
    "剪映专业版 快捷键 大全",
    "剪映 转场 教程 游戏",
]

allres = {}
for q in QUERIES:
    try:
        rs = cn.bili_search(q, 1)
    except Exception as e:
        print("QFAIL", q, e)
        continue
    allres[q] = rs
    print("=== %s (%d)" % (q, len(rs)))
    for r in rs:
        print("  - %s | %s | play=%s | %s" % (r["title"], r["url"], r["play"], r["author"]))

with io.open("bili_batch1.json", "w", encoding="utf-8") as f:
    json.dump(allres, f, ensure_ascii=False, indent=1)
print("SAVED bili_batch1.json")
