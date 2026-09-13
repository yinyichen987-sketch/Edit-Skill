# -*- coding: utf-8 -*-
"""Multi-query search runner with delays (Sogou + Baidu)."""
import sys, io, json, time, random
sys.stdout.reconfigure(encoding="utf-8")
import engines

QUERIES = [
    ("s", "剪映专业版 定格 时长 几秒"),
    ("s", "剪映 定格 默认 时长 3秒"),
    ("s", "剪映专业版 闪白 0.1秒 教程"),
    ("s", "剪映 击杀音效 搜索关键词"),
    ("s", "剪映专业版 音效 重低音 搜索"),
    ("s", "无畏契约 剪辑 击杀 卡点 手法"),
    ("s", "剪映 曲线变速 英雄时刻 怎么用"),
    ("s", "剪映 震动 抖动 特效 怎么做"),
    ("s", "剪映 黑场 转场 游戏 击杀"),
    ("s", "剪映 五杀 剪辑 特殊 效果"),
    ("s", "游戏集锦 击杀 卡点 剪辑 教学 剪映"),
    ("s", "剪映 快捷键 方案 自定义 切换"),
]
if len(sys.argv) > 1:
    QUERIES = [(sys.argv[1], sys.argv[2])]

res = []
for eng, q in QUERIES:
    print("\n" + "=" * 74)
    print("### [%s] %s" % (eng, q))
    try:
        rows = (engines.sogou if eng == "s" else engines.baidu)(q)
    except Exception as e:
        print("FAIL", type(e).__name__, e)
        rows = []
    for i, (t, u, sn) in enumerate(rows[:8], 1):
        print("%d. %s" % (i, t))
        print("   %s" % u)
        if sn:
            print("   %s" % sn[:300].replace("\n", " "))
        res.append({"eng": eng, "q": q, "title": t, "url": u, "snip": sn})
    time.sleep(3 + random.random() * 3)

with io.open("search_batch2.json", "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print("\nSAVED search_batch2.json")
