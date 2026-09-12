"""**排除法**取段：把 11 条原始素材整条拿来，只删掉「过长的无击杀画面」。

## 用户的原话（这是一次思路换向）
> "**我说过了直接用原始素材不要用你迭代的素材了**，重新评判重新剪辑。
>  我们要不换个思路，**我们不做选择，我们做排除**，
>  把原始素材里**是否有过长的无击杀的画面删除去除**。"

我此前一直在做「**选择**」——从素材里挑出我要的窗口，其余全部丢掉。
**排除**是反过来的：**素材全都留着，只把"过长的无击杀段"剪掉**。

两者的实际差别很大：
- 选择 ⇒ 每条素材只留几个窗口，**首尾和中间的大量素材被丢弃**；
- 排除 ⇒ 只有**超过阈值**的无击杀段被剪掉，其余（含较短的空档、开场、收尾）**全部保留**。

## 规则
对每条素材：
1. 从 0 到片尾**整条保留**；
2. 找出**无击杀持续 > `GAP` 秒**的区间 —— 只有这种"过长的无击杀画面"才删；
3. 删除时两侧各留 `POST` / `PRE` 秒（让上一杀有收尾、下一杀有前摇）；
4. 若片头（第一次击杀之前）或片尾（最后一次击杀之后）超过 `GAP`，按同规则裁剪；
   未超阈值的**一律保留**。
5. **一条素材的所有保留片断按时间顺序连在一起**，不与其他素材交错。

## 顺带修正一处判据（来自 Rocklan 的 After Effects 教程）
> "不要对齐到**击杀播报**出现的那一刻……**击杀播报比实际开枪晚几帧**，
>  你要对齐的是**橙色枪口火焰**那一刻。"

⇒ 我们的 `kills_mine.json` 记的是**播报/底部特效**的时刻，比真正开枪晚约 0.2–0.5s。
所以 `PRE` 不能太小，否则保留段会从"已经打死了"开始。这里 `PRE=0.6s` 专门补这个差。
"""
import json
import pathlib

from pymediainfo import MediaInfo

ROOT = pathlib.Path(__file__).resolve().parents[3]
KM = ROOT / "projects/game-001/analysis2/kills_mine.json"
OUT = ROOT / "projects/game-001/analysis2/source_blocks.json"

GAP = 3.0     # 无击杀超过这么多秒 = "过长"，删。
              # ⚠️ 由 5.0 收紧到 3.0：用户指出后者留下了"太多没用的镜头"。
              #    实测 3.0 是"没有任何一段击杀密度 < 0.25/秒"的临界点
              #    （5.0 时最低 0.16，即有约 6 秒画面里只有 1 次击杀）。
PRE = 0.6     # 删除区间的右端留出（给下一杀前摇）
POST = 1.5    # 删除区间的左端留出（给上一杀收尾）
MIN_CUT = 1.5  # 真正能删掉的部分不足这么多秒 ⇒ 不值得切这一刀，保留
MIN_SEG = 1.5  # 保留段短于此值 ⇒ 与相邻段合并（把中间空档放回去）


def dur(p: pathlib.Path) -> float:
    for t in MediaInfo.parse(str(p)).tracks:
        if t.track_type == "Video":
            return t.duration / 1000.0
    return 0.0


km = json.loads(KM.read_text(encoding="utf-8"))
D = {s: dur(ROOT / "原始素材" / r["file"]) for s, r in km.items()}

blocks = []
for short, r in sorted(km.items()):
    ks = sorted(r["mine"])
    d = D[short]
    if not ks:
        blocks.append({"short": short, "segs": [[0.0, round(d, 3)]], "n_kills": 0,
                       "kills_per_seg": [0], "removed_s": 0.0})
        continue

    keep, pos = [], 0.0
    # 片头：首杀之前若超过 GAP，才裁
    if ks[0] - 0.0 > GAP:
        pos = max(0.0, ks[0] - PRE)
    # 内部：相邻击杀间隔 > GAP 才裁
    for a, b in zip(ks, ks[1:]):
        # 只有当"真正能删掉的净长度"够大时才切
        if (b - a) > GAP and (b - a) - PRE - POST >= MIN_CUT:
            keep.append([pos, a + POST])
            pos = max(0.0, b - PRE)
    # 片尾：末杀之后若超过 GAP，才裁
    if d - ks[-1] > GAP:
        keep.append([pos, ks[-1] + POST])
    else:
        keep.append([pos, d])

    keep = [[max(0.0, a), min(d, b)] for a, b in keep if b - a > 0.2]
    # 合并因裁剪而贴太近的段
    merged = [keep[0]]
    for a, b in keep[1:]:
        if a <= merged[-1][1] + 0.3:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])

    # 规则 2：短于 MIN_SEG 的段 —— **只在合并后仍不违反 GAP 时才合并**，
    # 否则直接丢弃该碎段。
    # ⚠️ 一开始写成"无条件与相邻段合并"，结果把刚刚删掉的长空档又接了回来：
    #    9526869d 变成 27.48s 里塞着 **21.6 秒无击杀**，正是用户要删掉的东西。
    #    **"删掉过长无击杀"这条硬规则优先于"少留碎段"这条软规则。**
    def max_inner_gap(a: float, b: float) -> float:
        ks = [k for k in mine_times if a - 0.05 <= k <= b + 0.05]
        if len(ks) < 2:
            return float("inf")          # 段内不足 2 杀，视为不合格
        return max(y - x for x, y in zip(ks, ks[1:]))

    mine_times = ks
    merged = [m for m in merged if m[1] - m[0] >= MIN_SEG or True]  # 占位，下面统一处理
    changed = True
    while changed and len(merged) > 1:
        changed = False
        for i, (a, b) in enumerate(merged):
            if b - a >= MIN_SEG:
                continue
            merged.pop(i)                # 先移除碎段
            if i < len(merged):          # 试与右邻合并
                nb = merged[i][1]
                if max_inner_gap(a, nb) <= GAP:
                    merged[i] = [a, nb]
            elif i > 0:                  # 试与左邻合并
                na = merged[i - 1][0]
                if max_inner_gap(na, b) <= GAP:
                    merged[i - 1] = [na, b]
            changed = True
            break

    removed = d - sum(b - a for a, b in merged)
    blocks.append({
        "short": short, "segs": [[round(a, 3), round(b, 3)] for a, b in merged],
        "n_kills": len(ks),
        "kills_per_seg": [len([k for k in ks if a <= k <= b]) for a, b in merged],
        "removed_s": round(removed, 2),
    })

OUT.write_text(json.dumps(blocks, ensure_ascii=False, indent=1), encoding="utf-8")

tot = sum(b - a for blk in blocks for a, b in blk["segs"])
nseg = sum(len(blk["segs"]) for blk in blocks)
raw = sum(D.values())
print(f"=== 排除法结果（GAP={GAP}s / PRE={PRE}s / POST={POST}s）===")
for blk in blocks:
    print(f"  {blk['short']:10} 原长 {D[blk['short']]:5.2f}s  保留 "
          f"{sum(b-a for a,b in blk['segs']):5.2f}s  删掉 {blk['removed_s']:5.2f}s  "
          f"{len(blk['segs'])} 段  " +
          " + ".join(f"{a:.1f}→{b:.1f}({n}杀)" for (a, b), n in
                     zip(blk["segs"], blk["kills_per_seg"])))
print(f"\n  {len(blocks)} 块 / {nseg} 段")
print(f"  原始总长 {raw:.1f}s → 保留 {tot:.1f}s（删掉 {raw-tot:.1f}s = {(raw-tot)/raw*100:.0f}%）")
print(f"  切点 {nseg - 1} → {(nseg-1)/tot*60:.1f} 切每分")
