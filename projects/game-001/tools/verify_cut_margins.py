"""切点安全性核对（CUT-04 上界余量 / CUT-05 切点容差与高光余量）。

判定口径
--------
**CUT-05 有两半，本脚本两半都实现：**

1. **距不安全窗口 ≥ 0.1 s**。不安全窗口是**区间**（不是点）—— 每处真实画面换位
   对应的是「内容发生变化的那一对相邻帧」的 PTS 区间。用「名义帧号 ÷ 30」换算
   对 VFR 素材**系统性偏早**（b 段最多约 0.045 s），所以不得用点、也不得用帧号算术。
   窗口区间取自 `verification/scene-cuts/scene-cuts-result.json`（passthrough 解码
   + `showinfo` 实测真实 PTS）。b 段的第一个窗口**已把 VFR 丢帧吸收在内**，
   因此不要再把丢帧当成第二个独立危险点。

2. **高光前后各留 ≥ 0.3 s 余量**。口径写死为**相对高光区间**（「不要贴边切」
   约束的是区间边界，不是某个锚点）。高光区间取自
   `analysis/material-analysis.json`，只对**被该片段完整覆盖**的高光做检查。

3. **CUT-04 上界余量 ≥ 1 帧**：片段时间码不得越过素材 Video 流硬上界
   （越过会在剪映里取不到画面 → 黑尾/末帧滞留）。这与 CUT-05 是两件事。

本脚本的声明范围 = 实现范围。历史上本项目出现过「docstring 写了 0.3、代码里只有
0.10 与 0.034，跑出来仍是 ALL PASS」——那正是 `verification/claim-audit/` 要抓的
失败模式。这里把 0.3 真正写进判据。

用法：
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\verify_cut_margins.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# ---- 素材事实 ---------------------------------------------------------------

# CUT-04：素材 Video 流硬上界（= MediaInfo Video 轨 duration，比真实末点保守约一帧）
BOUND = {"a": 18.984, "b": 26.017, "c": 25.012}

# CUT-05 第一半：不安全窗口（真实 PTS 区间，闭区间）。
# 来源：verification/scene-cuts/scene-cuts-result.json
UNSAFE_WINDOWS = {
    "a": [],
    "b": [[10.9797, 11.0454], [12.9787, 13.0120]],
    "c": [[2.0717, 2.1050], [3.3717, 3.4050]],
}

# CUT-05 第二半：高光区间（来自 analysis/material-analysis.json，仅列本集用到的）
HIGHLIGHTS = {
    "A-H3": ("a", 6.35, 6.95),
    "A-H4": ("a", 8.40, 9.00),
    "A-H5": ("a", 11.60, 12.20),
    "B-H1": ("b", 5.40, 7.00),
    "B-H2": ("b", 8.50, 9.10),
    "B-H6": ("b", 23.40, 24.00),
}

NAME2KEY = {
    "4b0460c400bbb5320acb6063b4f59358.mp4": "a",
    "6b2eea343eee7595c3c0ede10d21d028.mp4": "b",
    "dcc871b1791e7796fadac842593f10f7.mp4": "c",
}

# ---- 阈值 -------------------------------------------------------------------

TOL = 0.10        # CUT-05 第一半：切点距不安全窗口边界 >= 0.1 s
MARGIN_HL = 0.3   # CUT-05 第二半：高光前后各留 >= 0.3 s（口径：相对高光区间）
FRAME = 0.034     # CUT-04：距素材硬上界 >= 1 帧

EDLS = ["projects/game-001/edl/ep01.json", "projects/game-001/edl/ep01-vertical.json"]

FAIL = []


def check(ok, msg):
    print(("  PASS  " if ok else "  FAIL  ") + msg)
    if not ok:
        FAIL.append(msg)


def window_clearance(value, windows):
    """value 到任一闭区间 [w0, w1] 的「外部距离」。

    落在区间内 -> 返回负数（越大表示越深入区间内部），并单独标记。
    区间外 -> 返回到最近边界的距离。
    """
    best = float("inf")
    inside = False
    for w0, w1 in windows:
        if w0 <= value <= w1:
            inside = True
            best = min(best, -min(value - w0, w1 - value))
        else:
            best = min(best, min(abs(value - w0), abs(value - w1)))
    return best, inside


for rel in EDLS:
    print(f"\n===== {rel} =====")
    edl = json.load(open(os.path.join(ROOT, rel), encoding="utf-8"))
    for i, c in enumerate(edl["clips"]):
        key = NAME2KEY[os.path.basename(c["source"])]
        s, e = float(c["source_in"]), float(c["source_in"]) + float(c["duration"])
        print(f"-- clip{i + 1}  {key} [{s}, {e}]  转场进入={bool(c.get('transition'))}")

        # ---------- CUT-04：距素材硬上界 >= 1 帧 ----------
        margin = BOUND[key] - e
        check(margin >= FRAME,
              f"clip{i + 1} CUT-04 距硬上界 {margin:.3f}s >= 1 帧（{FRAME}s）")

        # ---------- CUT-05 第一半：距不安全窗口边界 >= 0.1 s ----------
        windows = UNSAFE_WINDOWS[key]
        if not windows:
            print(f"         NOTE  {key} 为 CFR，无不安全窗口")
        for w0, w1 in windows:
            for label, v in (("入点", s), ("出点", e)):
                d, inside = window_clearance(v, [[w0, w1]])
                if inside:
                    check(False, f"clip{i + 1} {label} {v} 落在不安全窗口 [{w0}, {w1}] 内")
                else:
                    check(d >= TOL,
                          f"clip{i + 1} {label} {v} 距窗口 [{w0}, {w1}] = {d:.3f}s >= {TOL}s")

        # ---------- CUT-05 第二半：高光前后 >= 0.3 s（相对区间） ----------
        covered = [(hid, h0, h1) for hid, (hk, h0, h1) in HIGHLIGHTS.items()
                   if hk == key and h0 >= s - 1e-9 and h1 <= e + 1e-9]
        if not covered:
            print(f"         NOTE  clip{i + 1} 未完整覆盖任何已登记高光区间")
        for hid, h0, h1 in covered:
            pre, post = h0 - s, e - h1
            check(pre >= MARGIN_HL - 1e-9,
                  f"clip{i + 1} 高光 {hid} [{h0}, {h1}] 前余量 {pre:.3f}s >= {MARGIN_HL}s")
            check(post >= MARGIN_HL - 1e-9,
                  f"clip{i + 1} 高光 {hid} [{h0}, {h1}] 后余量 {post:.3f}s >= {MARGIN_HL}s")

print("\n===== 时长复核 =====")
edl = json.load(open(os.path.join(ROOT, EDLS[0]), encoding="utf-8"))
clips = edl["clips"]
sd = sum(c["duration"] for c in clips)
end = clips[-1]["start"] + clips[-1]["duration"]
# 转场=重叠模型：相邻片段零间隙 → end = Σduration（转场不额外占用总长）
check(abs(sd - end) < 1e-9, f"Σ duration {sd:.2f} == end {end:.2f}（转场为重叠，不额外占时）")
check(abs(end - 15.0) < 1e-9, f"末片段 end = {end:.3f} == 15.000")
print("-- no-black-frame：相邻片段必须零间隙（转场重叠，不得留黑洞）")
for i in range(1, len(clips)):
    prev_end = clips[i - 1]["start"] + clips[i - 1]["duration"]
    gap = round(clips[i]["start"] - prev_end, 6)
    check(abs(gap) < 1e-9,
          f"clip{i}→clip{i + 1} 间隙 {gap}s（转场重叠模型下必须为 0，否则该处无素材=闪黑）")
print("-- 转场区间必须紧贴切点、且两侧片段在时间线上无缝衔接")
for i, c in enumerate(clips):
    if c.get("transition"):
        tr = c["transition"]["duration"]
        prev = clips[i - 1]
        prev_end = round(prev["start"] + prev["duration"], 6)
        cut = round(c["start"], 6)
        check(abs(prev_end - cut) < 1e-9, f"clip{i + 1} 切点 {cut} == 前一片段末点 {prev_end}（无缝）")
        check(abs(tr - 0.13) < 1e-9, f"clip{i + 1} 转场时长 {tr}s == 0.13s")
        print(f"         clip{i + 1} 转场覆盖切点前后各 {tr / 2:.3f}s（重叠区由两侧素材共同提供）")

print()
print("本脚本检查范围：CUT-04 上界余量 + CUT-05 距不安全窗口 + CUT-05 高光余量"
      " + 零间隙 + 总长 + 转场无缝")
print(f"RESULT: {'ALL PASS' if not FAIL else str(len(FAIL)) + ' FAILURES'}")
for f in FAIL:
    print("  - " + f)
sys.exit(1 if FAIL else 0)
