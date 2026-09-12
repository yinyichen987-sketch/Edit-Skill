"""复查 EDL 是否满足用户定的**素材选取标准**。

## 用户的四条标准（逐条对应一个检查项）

| # | 用户原话 | 检查项 |
|---|---|---|
| 1 | "每个击杀留的窗口时间更长一点" | 每段 **≥2 次击杀**、段长 ≥2s |
| 2 | "第一个画面没有出现任何一个击杀那么它的意义是什么" | **段起点距首杀 ≤0.5s**（开场必须马上见杀） |
| 3 | "不要把一个素材的击杀切分之后和别的素材混起来……要连在一起" | 每条素材**只能出现一个连续块**，块内**不得被别的素材打断** |
| 4 | "先后顺序不对" | 块内 `source_in` **严格递增**（一杀→多杀的过程） |

## 用法

    .venv\\Scripts\\python.exe tools/verify_kill_coverage.py [edl.json]

退出码 0 = 全部通过；1 = 有不满足项（会逐条列出是哪个镜头、差多少）。
**这四个判据是本项目最容易反复犯的错**，所以做成门禁而不是"看一眼"。
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

MIN_KILLS = 2        # 每段至少几次击杀
MAX_HEAD = 0.5       # 段起点距首杀最多几秒（开场必须见杀）
MIN_SEG_S = 2.0      # 段最短时长
MAX_INNER_GAP = 6.0  # 段内两杀之间允许的最大无击杀空档（秒）


def main() -> int:
    edl_path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_EDL
    if not edl_path.is_absolute():
        edl_path = ROOT / edl_path
    edl = json.loads(edl_path.read_text(encoding="utf-8"))
    km = json.loads(KILLS.read_text(encoding="utf-8"))
    mine = {s: sorted(r["mine"]) for s, r in km.items()}

    clips = edl["clips"]
    fails: list[str] = []

    print(f"=== 素材选取标准复查：{edl_path.name} ===")
    print(f"    {len(clips)} 段 / {sum(c['duration'] for c in clips):.2f}s\n")

    # ---- 检查 1 & 2：每段击杀数与开场延迟 ----
    print("【1+2】每段 ≥%d 杀、开场 ≤%.1fs 必见杀" % (MIN_KILLS, MAX_HEAD))
    for i, c in enumerate(clips, 1):
        short = pathlib.Path(c["source"]).stem[:8]
        a, b = c["source_in"], c["source_in"] + c["duration"]
        ks = [k for k in mine.get(short, []) if a - 0.05 <= k <= b + 0.05]
        head = (ks[0] - a) if ks else None
        tag = ""
        if len(ks) < MIN_KILLS:
            tag = f"✗ 只有 {len(ks)} 杀（要求 ≥{MIN_KILLS}）"
            fails.append(f"{c['id']} 击杀不足")
        elif head is not None and head > MAX_HEAD:
            tag = f"✗ 开场 {head:.2f}s 无击杀（要求 ≤{MAX_HEAD}s）"
            fails.append(f"{c['id']} 开场无击杀")
        elif c["duration"] < MIN_SEG_S:
            tag = f"✗ 段长 {c['duration']:.2f}s 过短"
            fails.append(f"{c['id']} 段过短")
        else:
            tag = "✓"
        print(f"  {i:3} {short:10} {a:6.2f}→{b:6.2f} {c['duration']:6.2f}s "
              f"{len(ks)}杀 首杀+{head:.2f}s {tag}" if head is not None else
              f"  {i:3} {short:10} {a:6.2f}→{b:6.2f} {c['duration']:6.2f}s 0杀  {tag}")

    # ---- 检查 3：每条素材只能有一个连续块 ----
    print("\n【3】同一素材必须连在一起（不得被别的素材打断）")
    seq = []
    for c in clips:
        s = pathlib.Path(c["source"]).stem[:8]
        if not seq or seq[-1] != s:
            seq.append(s)
    cnt = Counter(seq)
    multi = {s: n for s, n in cnt.items() if n > 1}
    if multi:
        for s, n in multi.items():
            print(f"  ✗ {s} 被拆成 {n} 处（中间插了别的素材）")
            fails.append(f"{s} 被拆成 {n} 处")
    else:
        print(f"  ✓ {len(seq)} 个块: {' → '.join(seq)}")

    # ---- 检查 4：块内 source_in 递增 ----
    print("\n【4】块内 source_in 严格递增（一杀 → 多杀 的过程）")
    prev = None
    bad = 0
    for c in clips:
        s = pathlib.Path(c["source"]).stem[:8]
        if s == prev:
            if c["source_in"] <= last_in:
                print(f"  ✗ {c['id']} ({s}) {c['source_in']:.2f} ≤ 上一段 {last_in:.2f}")
                fails.append(f"{c['id']} 顺序回跳")
                bad += 1
        prev, last_in = s, c["source_in"]
    if bad == 0:
        print("  ✓ 全部递增")

    # ---- 检查 5：段内不得有 >MAX_INNER_GAP 的无击杀空档 ----
    # 这条直接对应"很多和击杀无关的画面被剪辑进入" —— 段内两杀之间隔太久，
    # 中间那段就是与击杀无关的画面。合并"单杀组"时最容易把它并进来
    # （实测第一段曾因此变成 27.28s 只有 3 杀）。
    print(f"\n【5】段内无击杀空档 ≤ {MAX_INNER_GAP:.1f}s")
    worst = 0.0
    for c in clips:
        short = pathlib.Path(c["source"]).stem[:8]
        a, b = c["source_in"], c["source_in"] + c["duration"]
        ks = [k for k in mine.get(short, []) if a - 0.05 <= k <= b + 0.05]
        inner = [ks[0] - a] + [y - x for x, y in zip(ks, ks[1:])] + [b - ks[-1]]
        m = max(inner) if inner else 0.0
        worst = max(worst, m)
        if m > MAX_INNER_GAP:
            print(f"  ✗ {c['id']} ({short}) 段内最大无击杀空档 {m:.2f}s "
                  f"（要求 ≤{MAX_INNER_GAP:.1f}s）")
            fails.append(f"{c['id']} 段内空档 {m:.2f}s")
    if not any("段内空档" in f for f in fails):
        print(f"  ✓ 全部通过（最大空档 {worst:.2f}s）")

    print()
    if fails:
        print(f"[FAIL] {len(fails)} 项不满足：{fails}")
        return 1
    print("[OK] 五条标准全部通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
