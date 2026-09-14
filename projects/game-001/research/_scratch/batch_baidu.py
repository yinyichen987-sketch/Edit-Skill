# -*- coding: utf-8 -*-
import sys, io, json
sys.stdout.reconfigure(encoding="utf-8")
import cn

QUERIES = [
    "剪映专业版 曲线变速 在哪里 设置",
    "剪映 闪白 效果 教程",
    "剪映专业版 画面 基础 定格 菜单位置",
    "剪映 击杀音效 搜索 关键词",
    "剪映 震动 抖动 特效 教程",
    "剪映 五杀 剪辑 教程",
    "剪映专业版 快捷键 大全 默认",
    "剪映 变声 重低音 音效",
    "无畏契约 集锦 剪辑 手法 教学",
    "剪映 黑场 黑帧 教程",
]

out = []
for q in QUERIES:
    print("\n" + "=" * 72)
    print("### QUERY:", q)
    try:
        rs = cn.baidu(q)
    except Exception as e:
        print("FAIL", type(e).__name__, e)
        continue
    for i, (t, u, b) in enumerate(rs[:8], 1):
        print("%d. %s" % (i, t))
        print("   %s" % u)
        print("   %s" % b[:260].replace("\n", " "))
        out.append({"q": q, "title": t, "url": u, "snippet": b[:400]})

with io.open("baidu_batch1.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("\nSAVED baidu_batch1.json")
