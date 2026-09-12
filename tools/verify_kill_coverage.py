"""复查 EDL 是否满足**排除法**的选取标准（用户换思路后的新标准）。

## 思路变化
- **旧标准（选择）**：从素材里挑窗口 ⇒ 检查"每段 ≥2 杀""开场必见杀"。
- **新标准（排除）**：素材整条拿来，只删掉过长的无击杀段 ⇒
  检查"11 条素材是不是都用上了""过长的无击杀删干净了没有""有没有留下碎段"。

判据完全变了，所以这个脚本重写。

## 五条判据
| # | 用户原话 | 判据 |
|---|---|---|
| 1 | "直接用原始素材" | **11 条素材全部出现在成片里**（一条都不许丢） |
| 2 | "不要把一个素材的击杀切分之后和别的素材混起来" | 每条素材**只出现一个连续块** |
| 3 | "先后顺序" | 块内 `source_in` **严格递增** |
| 4 | "把过长的无击杀的画面删除去除" | 保留下来的任何**无击杀空档都 ≤ GAP** |
| 5 | （裁剪产物不该是碎渣） | 每段 ≥ `MIN_SEG`（含 10% 容差） |

## 用法
    .venv\\Scripts\\python.exe tools/verify_kill_coverage.py [edl.json]
退出码 0 = 全过；1 = 有违反项（逐条指出是哪个镜头、超了多少）。
"""
from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_EDL = ROOT / "projects/game-001/edl/bili-montage.json"
KILLS = ROOT / "projects/game-001/analysis2/kills_mine.json"

GAP = 5.0        # 无击杀超过这么多秒就应被删掉（与 build_by_exclusion.py 一致）
MIN_SEG = 1.35   # 每段最短时长（MIN_SEG=1.5 的 90% 容差）
# 第 6 条：击杀密度下限。用户反馈带来的**决定性指标** ——
#   他满意的三段密度是 0.35 / 0.61 / 0.38，不满意的 #1/#3 只有 0.19 / 0.16。
#   只看"段内 >=2 杀"不够：两杀之间那几秒可能是空的（购买阶段/空房间）。
MIN_DENSITY = 0.25   # 杀/秒


def main() -> int:
    edl_path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_EDL
    if not edl_path.is_absolute():
        edl_path = ROOT / edl_path
    edl = json.loads(edl_path.read_text(encoding="utf-8"))
    km = json.loads(KILLS.read_text(encoding="utf-8"))
    mine = {s: sorted(r["mine"]) for s, r in km.items()}

    clips = edl["clips"]
    total = sum(c["duration"] for c in clips)
    fails: list[str] = []
    print(f"=== 排除法标准复查：{edl_path.name} ===")
    print(f"    {len(clips)} 段 / {total:.2f}s\n")

    # ---- 1. 所有素材都要用上 ----
    used = {pathlib.Path(c["source"]).stem[:8] for c in clips}
    missing = sorted(set(mine) - used)
    print("【1】11 条原始素材全部用上")
    if missing:
        for s in missing:
            print(f"  ✗ {s} 完全没被使用（排除法不该丢掉任何素材）")
            fails.append(f"{s} 未被使用")
    else:
        print(f"  ✓ {len(used)}/{len(mine)} 条全部用上")

    # ---- 2/3. 同素材连续 + 块内递增 ----
    seq, prev, last_in, jump = [], None, None, 0
    for c in clips:
        s = pathlib.Path(c["source"]).stem[:8]
        if not seq or seq[-1] != s:
            seq.append(s)
        if s == prev and c["source_in"] <= last_in:
            print(f"  ✗ {c['id']} ({s}) source_in {c['source_in']:.2f} ≤ 上一段 {last_in:.2f}")
            fails.append(f"{c['id']} 顺序回跳")
            jump += 1
        prev, last_in = s, c["source_in"]
    cnt = Counter(seq)
    split = {s: n for s, n in cnt.items() if n > 1}
    print("\n【2】每条素材只出现一个连续块")
    if split:
        for s, n in split.items():
            print(f"  ✗ {s} 被拆成 {n} 处（中间插了别的素材）")
            fails.append(f"{s} 被拆成 {n} 处")
    else:
        print(f"  ✓ {len(seq)} 个块: {' -> '.join(seq)}")
    print("\n【3】块内 source_in 严格递增")
    print("  ✓ 全部递增" if jump == 0 else f"  ✗ {jump} 处回跳")

    # ---- 4. 保留段内不得有无击杀空档 > GAP ----
    print(f"\n【4】保留段内的无击杀空档 <= {GAP:.1f}s（过长的无击杀画面应已删除）")
    over = 0
    worst = 0.0
    for c in clips:
        short = pathlib.Path(c["source"]).stem[:8]
        a, b = c["source_in"], c["source_in"] + c["duration"]
        ks = [k for k in mine.get(short, []) if a - 0.05 <= k <= b + 0.05]
        if not ks:
            print(f"  ✗ {c['id']} ({short}) 段内 0 杀")
            fails.append(f"{c['id']} 无击杀")
            over += 1
            continue
        inner = [ks[0] - a] + [y - x for x, y in zip(ks, ks[1:])] + [b - ks[-1]]
        m = max(inner)
        worst = max(worst, m)
        if m > GAP + 0.05:
            print(f"  ✗ {c['id']} ({short}) 段内最大空档 {m:.2f}s > {GAP:.1f}s")
            fails.append(f"{c['id']} 空档 {m:.2f}s")
            over += 1
    if over == 0:
        print(f"  ✓ 全部通过（最大空档 {worst:.2f}s）")

    # ---- 5. 不留碎段 ----
    print(f"\n【5】每段 >= {MIN_SEG:.2f}s（裁剪不该留下碎渣）")
    short_segs = [(c["id"], c["duration"]) for c in clips if c["duration"] < MIN_SEG]
    if short_segs:
        for i, d in short_segs:
            print(f"  ✗ {i} 只有 {d:.2f}s")
            fails.append(f"{i} 段过短 {d:.2f}s")
    else:
        print(f"  ✓ 最短段 {min(c['duration'] for c in clips):.2f}s")

    # ---- 6. 击杀密度 ----
    print(f"\n【6】击杀密度 >= {MIN_DENSITY:.2f} 杀/秒（不只有'发生过击杀'，还要够密）")
    low, dens = [], []
    for c in clips:
        short = pathlib.Path(c["source"]).stem[:8]
        a, b = c["source_in"], c["source_in"] + c["duration"]
        k = len([x for x in mine.get(short, []) if a - 0.05 <= x <= b + 0.05])
        d = k / c["duration"]
        dens.append(d)
        if d < MIN_DENSITY:
            low.append((c["id"], d, k, c["duration"]))
    if low:
        for i, d, k, L in low:
            print(f"  x {i} 密度 {d:.2f}（{k} 杀 / {L:.2f}s）")
            fails.append(f"{i} 密度 {d:.2f}")
    else:
        ds = sorted(dens)
        print(f"  ok 全部通过（中位 {ds[len(ds)//2]:.2f}，最低 {ds[0]:.2f}）")

    print()
    if fails:
        print(f"[FAIL] {len(fails)} 项不满足：{fails}")
        return 1
    print("[OK] 六条判据全部通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
