"""按新标准重建 `source_blocks.json`。

## 用户指出的两个具体问题（我复查后确认）
> "比如说你这一版本里**第一个画面没有出现任何一个击杀**那么它的意义是什么，
>  而且现在仍然有**先后顺序不对或者剪辑穿插到别的集锦后面**的。"

复查 `edl/bili-montage.json` 的 28 个镜头：

- **27 个镜头开场 1.5 秒内没有任何击杀** —— 因为我给每段统一加了 `LEAD=1.5s` 前摇。
  第一个镜头尤其糟：全片第一帧起 1.5 秒什么都没发生。
- **很多段只含 1 次击杀** —— 因为"单杀组"也会套上一个 `1.5+2.5=4.0s` 的窗口。

## 新标准
1. **每段至少 2 次你自己的击杀**；含 1 杀的组**并入相邻组**（直到 ≥2 杀）。
2. **前摇压到 0.4s** —— 只够看到开枪那一下，**开场几乎立刻见杀**。
3. 收尾 2.5s（击杀后要有交代）。
4. 段与段之间仍是"长时间无击杀"的空档（>4.5s 才剔除）。
5. 一条素材 = 一个块，块内按素材时间顺序，**不与其他素材交错**。

判据由 `tools/verify_kill_coverage.py` 机器复查（退出码 0 = 全过）。
"""
import json
import pathlib

from pymediainfo import MediaInfo

ROOT = pathlib.Path(__file__).resolve().parents[3]
KM = ROOT / "projects/game-001/analysis2/kills_mine.json"
OUT = ROOT / "projects/game-001/analysis2/source_blocks.json"

LEAD, TAIL, GAP, MERGE = 0.4, 2.5, 4.5, 0.6
# ★ 合并上限：单杀组为了凑到 MIN_KILLS 可以跨越的**最大间隔**。
#   不设上限时，无条件合并会把"21.6 秒无击杀"的空档也并进来 ——
#   实测第一段就成了 27.28s 只有 3 杀，正是用户说的"和击杀无关的画面"。
#   超过 MERGE_GAP 仍凑不到 MIN_KILLS 的单杀组，**直接丢弃**。
MERGE_GAP = 6.0
MIN_KILLS = 2


def dur(p: pathlib.Path) -> float:
    for t in MediaInfo.parse(str(p)).tracks:
        if t.track_type == "Video":
            return t.duration / 1000.0
    return 0.0


km = json.loads(KM.read_text(encoding="utf-8"))
D = {s: dur(ROOT / "原始素材" / r["file"]) for s, r in km.items()}

blocks = []
for short, r in sorted(km.items()):
    ks = r["mine"]
    if not ks:
        continue
    # 1) 按 GAP 分组
    groups = [[ks[0]]]
    for a, b in zip(ks, ks[1:]):
        groups[-1].append(b) if b - a <= GAP else groups.append([b])
    # 2) 把只有 1 杀的组并进相邻组（直到每组 >= MIN_KILLS，或只剩一组）
    changed = True
    while changed and len(groups) > 1:
        changed = False
        for i, g in enumerate(groups):
            if len(g) >= MIN_KILLS:
                continue
            # 并进"间隔更小"的那一侧
            left = (g[0] - groups[i - 1][-1]) if i > 0 else None
            right = (groups[i + 1][0] - g[-1]) if i + 1 < len(groups) else None
            # 只能并进 MERGE_GAP 以内的邻居
            left_ok = left is not None and left <= MERGE_GAP
            right_ok = right is not None and right <= MERGE_GAP
            if not left_ok and not right_ok:
                groups.pop(i)          # 两侧都太远 ⇒ 这个单杀组不要了
                changed = True
                break
            if right is None or (left_ok and (not right_ok or left <= right)):
                groups[i - 1].extend(g)
                groups.pop(i)
            else:
                groups[i + 1][:0] = g
                groups.pop(i)
            changed = True
            break
    # 3) 生成段窗口
    segs = []
    for g in groups:
        if len(g) < MIN_KILLS:
            continue
        segs.append([max(0.0, g[0] - LEAD), min(D[short], g[-1] + TAIL)])
    if not segs:
        continue
    # 4) 合并重叠/贴太近
    merged = [segs[0]]
    for a, b in segs[1:]:
        if a <= merged[-1][1] + MERGE:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    blocks.append({"short": short, "segs": [[round(a, 3), round(b, 3)] for a, b in merged],
                   "n_kills": len(ks),
                   "kills_per_seg": [len([k for k in ks if a <= k <= b]) for a, b in merged]})

OUT.write_text(json.dumps(blocks, ensure_ascii=False, indent=1), encoding="utf-8")
tot = sum(b - a for blk in blocks for a, b in blk["segs"])
nseg = sum(len(blk["segs"]) for blk in blocks)
print(f"  {len(blocks)} 块 / {nseg} 段 / {tot:.2f}s")
print(f"  切点 {nseg}（含块内空档接缝）→ {nseg/tot*60:.1f} 切每分")
for blk in blocks:
    print(f"  {blk['short']:10} 自身击杀{blk['n_kills']:3}  " +
          " + ".join(f"{a:.1f}→{b:.1f}({n}杀)" for (a, b), n in
                     zip(blk["segs"], blk["kills_per_seg"])))
