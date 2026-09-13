# -*- coding: utf-8 -*-
"""Download key 剪映 VALORANT/montage tutorial videos at <=720p (video-only, small)."""
import subprocess, sys, os, glob
sys.stdout.reconfigure(encoding="utf-8")

PY = r"C:\Users\18930\Desktop\Edit skill\.venv\Scripts\python.exe"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vids")
os.makedirs(OUT, exist_ok=True)

BVS = [
    "BV1FJeRzZEtY",  # 瓦 击杀瞬间切刀效果
    "BV11hdSYcENH",  # 曝光击杀特效
    "BV1G1r6BuEsF",  # 瓦区卡点左右闪白
    "BV1wyRmYDERv",  # 公式化剪瓦定格特效
    "BV1HVe8zRE5m",  # 击杀卡片效果
    "BV18rrsBdEcD",  # 内吸击杀抖动
    "BV1QmpnznEZF",  # 定格卡点教程
    "BV1g2adz3EvS",  # 瓦回弹万金油转场
    "BV1qx5463Exr",  # 无畏契约音乐击杀卡点
    "BV1xjh7zWEjh",  # 推拉闪白转场
    "BV1hHGQ6AErb",  # 蒙版闪白卡点
]

env = dict(os.environ, PYTHONIOENCODING="utf-8")
for bv in BVS:
    dest = os.path.join(OUT, bv + ".mp4")
    if os.path.exists(dest) and os.path.getsize(dest) > 50000:
        print("SKIP", bv, os.path.getsize(dest))
        continue
    cmd = [
        PY, "-m", "yt_dlp",
        "-f", "bv*[height<=720][ext=mp4]/bv*[height<=720]/bv*/b",
        "--no-playlist", "--no-warnings", "-q",
        "-o", dest,
        "https://www.bilibili.com/video/%s/" % bv,
    ]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    ok = os.path.exists(dest)
    print("DL", bv, "ok" if ok else "FAIL", (os.path.getsize(dest) if ok else 0))
    if not ok:
        print("   ", (r.stderr or "")[:400].replace("\n", " "))
print("ALL DONE")
