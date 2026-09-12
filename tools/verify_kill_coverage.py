"""复查 EDL 是否满足「**整条不切**」标准。

## 本轮标准（用户推翻了前几轮的"排除法/密度"要求）
> "推翻前面的说法……重新对原始素材进行剪辑，
>  **尽量先不把每一个素材切断，先保证完整的流畅连贯性**。"

判据只有三条：

| # | 用户原话 | 判据 |
|---|---|---|
| 1 | "直接用原始素材" | **11 条素材全部出现** |
| 2 | "**尽量先不把每一个素材切断**" | 每条素材**整条使用**：`source_in==0` 且时长==素材原长（容差 1 帧） |
| 3 | "不要把一个素材的击杀切分之后和别的素材混起来" | 每条素材**只出现一个连续块** |

⚠️ 前几轮的"击杀密度 ≥0.25""段内空档 ≤GAP"等判据**本轮刻意不检查**：
整条不切必然带进买枪/走路画面，那是"先保证连贯性"的既定代价，
是下一步要解决的问题，不该被门禁判为失败。

用法：`.venv\\Scripts\\python.exe tools/verify_kill_coverage.py [edl.json]`
"""
from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter

from pymediainfo import MediaInfo

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_EDL = ROOT / "projects/game-001/edl/bili-montage.json"
KILLS = ROOT / "projects/game-001/analysis2/kills_mine.json"
TOL = 0.05      # 秒，约 1.5 帧


def clip_duration(name: str) -> float:
    for t in MediaInfo.parse(str(ROOT / "原始素材" / name)).tracks:
        if t.track_type == "Video":
            return t.duration / 1000.0
    return 0.0


def main() -> int:
    edl_path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_EDL
    if not edl_path.is_absolute():
        edl_path = ROOT / edl_path
    edl = json.loads(edl_path.read_text(encoding="utf-8"))
    km = json.loads(KILLS.read_text(encoding="utf-8"))

    clips = edl["clips"]
    total = sum(c["duration"] for c in clips)
    fails: list[str] = []
    print(f"=== 整条不切标准复查：{edl_path.name} ===")
    print(f"    {len(clips)} 段 / {total:.2f}s\n")

    # 1. 全部素材都要用上
    used = {pathlib.Path(c["source"]).stem[:8] for c in clips}
    missing = sorted(set(km) - used)
    print("【1】11 条原始素材全部用上")
    if missing:
        for s in missing:
            print(f"  x {s} 完全没被使用")
            fails.append(f"{s} 未被使用")
    else:
        print(f"  ok {len(used)}/{len(km)} 条全部用上")

    # 2. 每条整条使用
    print("\n【2】每条素材整条使用（素材内部零剪切）")
    for c in clips:
        short = pathlib.Path(c["source"]).stem[:8]
        d = clip_duration(km[short]["file"])
        a, b = c["source_in"], c["source_in"] + c["duration"]
        if a > TOL:
            print(f"  x {c['id']} ({short}) 入点 {a:.3f}s != 0（被切掉了片头）")
            fails.append(f"{c['id']} 非整条")
        elif b < d - TOL:
            print(f"  x {c['id']} ({short}) 出点 {b:.3f}s < 素材原长 {d:.3f}s（被切掉了片尾）")
            fails.append(f"{c['id']} 非整条")
    if not any("非整条" in f for f in fails):
        print(f"  ok {len(clips)} 条全部整条使用")

    # 3. 同素材只能一个连续块
    seq = []
    for c in clips:
        s = pathlib.Path(c["source"]).stem[:8]
        if not seq or seq[-1] != s:
            seq.append(s)
    split = {s: n for s, n in Counter(seq).items() if n > 1}
    print("\n【3】每条素材只出现一个连续块")
    if split:
        for s, n in split.items():
            print(f"  x {s} 被拆成 {n} 处")
            fails.append(f"{s} 被拆成 {n} 处")
    else:
        print(f"  ok {len(seq)} 个块: {' -> '.join(seq)}")

    print()
    if fails:
        print(f"[FAIL] {len(fails)} 项不满足：{fails}")
        return 1
    print("[OK] 三条判据全部通过：素材内部零剪切，只有换素材的 10 个切点。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
