"""规格数字自证脚本 —— 核对 game-001 规格文档里的数字是否与素材事实自洽。

范围：单集（1 集 × LS/VT 两版）。校验项：
  1. 片段 start 递进公式    2. 素材 Video 流硬上界与 ≥1 帧余量
  3. Σ duration + Σ transition = 总时长
  4. 同源区间不二次出现（SEL-02，按 (source, source_in, duration) 三元组）
  5. 素材文件存在性          6. 逐源 volume 系数（AUD-01）
  7. 相邻段对齐后响度残差     8. 用量与 t1 推荐池覆盖率

用法：.venv\\Scripts\\python.exe projects\\game-001\\tools\\verify_spec_numbers.py
"""
import json
import os
import sys
from math import log10

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

BOUND = {
    "a": {"file": "4b0460c400bbb5320acb6063b4f59358.mp4", "video": 18.984},
    "b": {"file": "6b2eea343eee7595c3c0ede10d21d028.mp4", "video": 26.017},
    "c": {"file": "dcc871b1791e7796fadac842593f10f7.mp4", "video": 25.012},
}
VOL = {"a": 0.700, "b": 0.851, "c": 0.912}
LUFS = {"a": -12.9, "b": -14.6, "c": -15.2}
TRANS = 0.13

# 直接以 EDL 为唯一真值来源，避免脚本与 EDL 各写一份而漂移
EDL_REL = os.path.join("projects", "game-001", "edl", "ep01.json")
NAME2KEY = {
    "4b0460c400bbb5320acb6063b4f59358.mp4": "a",
    "6b2eea343eee7595c3c0ede10d21d028.mp4": "b",
    "dcc871b1791e7796fadac842593f10f7.mp4": "c",
}
with open(os.path.join(ROOT, EDL_REL), encoding="utf-8") as fh:
    _edl = json.load(fh)
CLIPS = [(NAME2KEY[os.path.basename(c["source"])], c["source_in"], c["duration"], c["start"],
          (c.get("transition") or {}).get("duration"))
         for c in _edl["clips"]]

TARGET_END = 15.0
END_TOL = (14.8, 15.2)

# t1 明确列为 usable=true 的候选区间（严格 + 中置信战斗 + 情绪节拍）。
# 排除 usable=false 的 A-H4/A-H7、B-H4/B-H6、C-H4/C-H6/C-H9。
POOL = {
    "a": [(0.50, 2.00), (5.00, 6.00), (6.35, 6.95), (11.60, 12.20), (13.40, 14.60), (16.25, 17.45)],
    "b": [(5.40, 7.00), (8.50, 9.10), (9.40, 12.80), (17.00, 19.00), (21.40, 23.90)],
    "c": [(2.90, 3.90), (6.40, 7.40), (8.90, 9.40), (9.90, 11.10), (19.10, 21.70), (23.40, 23.90)],
}

FAIL = []


def check(ok, msg):
    print(("  PASS  " if ok else "  FAIL  ") + msg)
    if not ok:
        FAIL.append(msg)


print("== 1/2/3. 片段递进、上界余量、总时长 ==")
total_dur = 0.0
for i, (k, si, dur, declared_start, trans) in enumerate(CLIPS):
    expect_start = 0.0 if i == 0 else CLIPS[i - 1][3] + CLIPS[i - 1][2]
    check(abs(declared_start - round(expect_start, 6)) < 1e-6,
          f"clip{i + 1} start 递进：声明 {declared_start} == 公式 {round(expect_start, 6)}（转场=重叠，零间隙）")
    check(si + dur <= BOUND[k]["video"] - 0.001,
          f"clip{i + 1} 上界：{si}+{dur}={si + dur:.3f} <= {BOUND[k]['video']} ({k})")
    margin = BOUND[k]["video"] - (si + dur)
    check(margin >= 0.034, f"clip{i + 1} 余量 {margin:.3f}s >= 1 帧")
    print(f"         clip{i + 1} 上界余量 {margin:.3f}s")
    total_dur += dur

end = CLIPS[-1][3] + CLIPS[-1][2]
n_trans = sum(1 for _k, _si, _d, _s, t in CLIPS if t)
check(END_TOL[0] <= end <= END_TOL[1], f"总时长 end={end:.3f} 落在 {END_TOL}")
check(abs(total_dur - end) < 1e-9,
      f"Σ duration {total_dur:.3f} == end {end:.3f}（转场为重叠，不额外占时）")
check(abs(end - TARGET_END) < 1e-9, f"end 精确 == {TARGET_END}（目标值；硬约束是 {END_TOL}）")
check(all(0.5 <= d <= 6.5 for _k, _si, d, _s, _t in CLIPS),
      "每条片段 duration ∈ [0.5, 6.5]（CUT-02）")
density = (len(CLIPS) - 1) / end * 60
check(10 <= density <= 16, f"切点密度 {density:.1f} 切/分 ∈ [10, 16]（CUT-02）")
print("-- no-black-frame：相邻片段零间隙（转场用重叠实现，不得留无素材黑洞）")
for i in range(1, len(CLIPS)):
    prev_end = CLIPS[i - 1][3] + CLIPS[i - 1][2]
    gap = round(CLIPS[i][3] - prev_end, 6)
    check(abs(gap) < 1e-9, f"clip{i}→clip{i + 1} 间隙 {gap}s == 0")

print("== 4. 同源区间不二次出现（SEL-02，按三元组） ==")
triples = [(k, round(si, 3), round(si + dur, 3)) for k, si, dur, _s, _t in CLIPS]
check(len(set(triples)) == len(triples), f"4 个三元组互不相同：{triples}")
for k in "abc":
    iv = sorted((si, si + dur) for kk, si, dur, _s, _t in CLIPS if kk == k)
    for x in range(len(iv) - 1):
        check(iv[x][1] <= iv[x + 1][0] + 1e-9, f"{k} 同源区间不交叠 {iv[x]} | {iv[x + 1]}")
    if not iv:
        print(f"  NOTE  {k} 整段未使用")

print("== 5. 素材文件存在性 ==")
for k, v in BOUND.items():
    p = os.path.join(ROOT, "原始素材", v["file"])
    check(os.path.exists(p), f"{k} 素材存在 {v['file']}")

print("== 6. 逐源 volume 系数（AUD-01） ==")
for k in "abc":
    gain_db = -16.0 - LUFS[k]
    coef = 10 ** (gain_db / 20)
    check(abs(coef - VOL[k]) < 0.002, f"{k}: 10^({gain_db:.1f}/20) = {coef:.3f} ~ 文档写 {VOL[k]}")
    print(f"         {k}: {LUFS[k]} LUFS → -16.0 LUFS, 增益 {gain_db:+.1f} dB, volume {coef:.3f}")

print("== 7. 相邻段对齐后响度残差 ==")
vals = [round(LUFS[k] + 20 * log10(VOL[k]), 3) for k, _si, _d, _s, _t in CLIPS]
worst = max((abs(vals[i] - vals[i + 1]) for i in range(len(vals) - 1)), default=0.0)
check(worst <= 0.4, f"相邻段最大残差 {worst:.3f} LU <= 0.4")
print(f"         各段对齐后响度 {vals}")

print("== 8. 用量与推荐池覆盖率 ==")
used = {k: 0.0 for k in "abc"}
for k, _si, dur, _s, _t in CLIPS:
    used[k] += dur
total_src = sum(v["video"] for v in BOUND.values())
for k in "abc":
    print(f"         {k}: 用 {used[k]:.2f}s / {BOUND[k]['video']}  未用 {BOUND[k]['video'] - used[k]:.2f}s")
print(f"         视频流总长 {total_src:.3f}s，Σ duration {sum(used.values()):.2f}s")

pool_total = sum(b - a for iv in POOL.values() for a, b in iv)
print(f"         t1 明确高光区间总长 {pool_total:.2f}s（t1 口径 19.5s，口径差异见 episode-plan §6）")
grand = 0.0
for k, si, dur, _s, _t in CLIPS:
    ov = sum(max(0.0, min(si + dur, b) - max(si, a)) for a, b in POOL[k])
    print(f"         {k} [{si},{si + dur}]: 落在明确高光区间内 {ov:.2f}s")
    grand += ov
print(f"         全集：Σ duration {sum(used.values()):.2f}s 中 {grand:.2f}s（{grand / sum(used.values()) * 100:.1f}%）"
      f" 落在 t1 明确高光区间内")
EXPECTED_POOL_COVERAGE = 7.10   # Plan B 前后实测均为 7.10s（见 episode-plan §6.2 的说明）
check(abs(grand - EXPECTED_POOL_COVERAGE) < 0.02,
      f"明确高光覆盖 {grand:.2f}s ≈ 文档记的 {EXPECTED_POOL_COVERAGE}s（episode-plan §6.2）")
check(abs(sum(used.values()) - 15.0) < 1e-9, f"Σ duration {sum(used.values()):.2f}s == 15.00s（转场为重叠）")

print()
print("== 9. 规则 ID 必须存在于风格规则集 ==")
style = os.path.join(ROOT, ".dsh", "skills", "jianying-edit", "references", "styles", "game-valorant.md")
style_text = open(style, encoding="utf-8").read()
for c in _edl["clips"]:
    rid = c.get("rule_id")
    check(f"### {rid} " in style_text, f"clip {c['id']} 的 rule_id {rid} 存在于 game-valorant.md")
    check(bool(c.get("reason")), f"clip {c['id']} 有非空 reason")

print()
print(f"RESULT: {'ALL PASS' if not FAIL else str(len(FAIL)) + ' FAILURES'}")
for f in FAIL:
    print("  - " + f)
sys.exit(1 if FAIL else 0)
