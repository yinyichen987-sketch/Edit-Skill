# -*- coding: utf-8 -*-
"""Batch: fetch bilibili video details for VALORANT/montage editing tutorials."""
import sys, io, json
sys.stdout.reconfigure(encoding="utf-8")
import bili_detail

KEY = [
    # VALORANT / 瓦 specific 剪映 tutorials
    "BV1FJeRzZEtY",  # 瓦 击杀瞬间切刀
    "BV11hdSYcENH",  # 曝光击杀特效
    "BV1HVe8zRE5m",  # 击杀卡片效果
    "BV1wyRmYDERv",  # 公式化剪瓦定格特效
    "BV1G1r6BuEsF",  # 瓦区左右闪白
    "BV1g2adz3EvS",  # 瓦回弹万金油转场
    "BV194afzDE6h",  # cs2和无畏契约热门剪辑全学会
    "BV1qx5463Exr",  # 无畏契约音乐击杀卡点
    "BV11AyEBuEo9",  # 超燃击杀效果
    "BV1uWrZB7Ewc",  # 曝光击杀转场
    "BV1ZHKE6aEkb",  # 慢动作结尾
    "BV18CcUz3E86",  # 从0制作完整无畏契约编辑
    "BV1We411m7vg",  # 三步调色
    "BV1mn9uBMEwP",  # 丝滑慢放结尾
    "BV18rrsBdEcD",  # 内吸击杀抖动
    "BV1Yj41197ui",  # 抖动效果 电脑端
    "BV1Q841127YH",  # 黑场突出主体
    "BV1VK421t78N",  # cs2 模糊开场+击杀效果
    "BV1xQf3BWEEz",  # 无畏契约帅气五杀剪辑教学
    "BV17tEqzeEXr",  # 游戏集锦应该这么剪
    "BV1hHGQ6AErb",  # 蒙版闪白卡点
    "BV1xjh7zWEjh",  # 推拉闪白转场
    "BV1Yu4y1v7vg",  # 闪白三种方法
    "BV1TeibBJELh",  # 电脑剪映变速及曲线变速
    "BV1Pq42zZEZj",  # 曲线变数和卡点
    "BV14J4m1P7PN",  # 常规变速和曲线变速
    "BV1QmpnznEZF",  # 定格卡点教程
    "BV1sqtt6fEbR",  # 切刀定格结尾
    "BV1ue8y6XE2M",  # 超有氛围感击杀结尾
    "BV1DAdrY7EyL",  # 快捷键 Ctrl&Alt
    "BV1Y5RRYWEyD",  # 快捷键教程
    "BV1k3LczZEAc",  # 曲线变速这么简单
    "BV12o8nzfE8d",  # 曲线变速教程
    "BV1yK411b72Z",  # 曲线变速卡不准点
    "BV1mZYyemE8B",  # 炸麦全损音质
    "BV1rR4y1c7pc",  # 游戏击杀慢放效果
    "BV1oX4y1U7Sh",  # 击杀秀音乐转动转场
]

res = []
for bv in KEY:
    try:
        r = bili_detail.detail(bv)
    except Exception as e:
        r = {"bv": bv, "err": "%s: %s" % (type(e).__name__, e)}
    res.append(r)
    print("=" * 74)
    print("BV %s | %s" % (r.get("bv"), r.get("title")))
    print("  url=%s" % r.get("url"))
    print("  owner=%s view=%s like=%s danmaku=%s dur=%s tname=%s"
          % (r.get("owner"), r.get("view"), r.get("like"), r.get("danmaku"), r.get("dur"), r.get("tname")))
    if r.get("parts") and len(r["parts"]) > 1:
        print("  PARTS: %s" % r["parts"][:12])
    d = (r.get("desc") or "").strip()
    print("  DESC: %s" % (d[:1200] if d else "(empty)"))
    if r.get("err"):
        print("  ERR:", r["err"])

with io.open("bili_details.json", "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print("\nSAVED bili_details.json")
