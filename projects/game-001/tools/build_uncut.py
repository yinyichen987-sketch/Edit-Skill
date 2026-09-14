"""生成**整条不切**的取段表：每条原始素材从 0 到片尾完整使用。

## 用户最新指示（推翻了上一轮的"排除法"）
> "推翻前面的说法……重新对原始素材进行剪辑，
>  **尽量先不把每一个素材切断，先保证完整的流畅连贯性**。"

⇒ 本轮**不做任何裁剪**：11 条素材**整条**依次串起来。
- 切点只有 10 个（每换一条素材一个），**素材内部零剪切**；
- 总长 = 11 条素材原长之和 = **336.1s**（5分36秒）；
- 顺序：**击倒数递增**，收尾固定为含「获胜」横幅的那条，让情绪有个落点。

## 为什么这是"先保证连贯性"的正确做法
前几版无论怎么调参数，本质都是"**在素材内部切刀**"，
而用户的耐受度集中在"**同一素材被切开**"这件事上。
整条不切之后，"割裂感"从结构上不可能出现 —— 代价是会出现买枪/走路等画面，
这正好是**下一步**才需要解决的问题（用户也说了"**先**保证完整连贯性"）。

## BGM
成片 336.1s > 单段可用音乐（《STYLE》约 176s）⇒ **把 168s 的高能量段循环两次**拼成
336s。循环点落在**小节边界**上，听感上是一个自然的段落重复。
⚠️ 循环是可听见的；若要避免，应换一首更长的曲子或让成片短于单段音乐。
"""
import json
import pathlib

from pymediainfo import MediaInfo

ROOT = pathlib.Path(__file__).resolve().parents[3]
KM = ROOT / "projects/game-001/analysis2/kills_mine.json"
OUT = ROOT / "projects/game-001/analysis2/source_blocks.json"

CLOSER = "6b2eea34"     # 含「获胜」横幅，固定收尾


def dur(p: pathlib.Path) -> float:
    for t in MediaInfo.parse(str(p)).tracks:
        if t.track_type == "Video":
            return t.duration / 1000.0
    return 0.0


km = json.loads(KM.read_text(encoding="utf-8"))
rows = [(s, dur(ROOT / "原始素材" / r["file"]), len(r["mine"])) for s, r in km.items()]
# 击倒数递增；收尾固定
rows.sort(key=lambda x: (x[0] == CLOSER, x[2], x[0]))

blocks = []
for short, d, n in rows:
    blocks.append({
        "short": short,
        "segs": [[0.0, round(d, 3)]],       # ★ 整条，一刀不切
        "n_kills": n,
        "kills_per_seg": [n],
        "removed_s": 0.0,
        "whole": True,
    })

OUT.write_text(json.dumps(blocks, ensure_ascii=False, indent=1), encoding="utf-8")
tot = sum(b - a for blk in blocks for a, b in blk["segs"])
print(f"=== 整条不切（{len(blocks)} 条素材）===")
for blk in blocks:
    a, b = blk["segs"][0]
    print(f"  {blk['short']:10} 原长 {b-a:6.2f}s  自身击杀 {blk['n_kills']:2}  "
          f"击杀密度 {blk['n_kills']/(b-a):.2f}/秒")
print(f"\n  总长 {tot:.2f}s = {tot/60:.2f} 分钟")
print(f"  切点 {len(blocks)-1} 个（只在换素材处）→ 素材内部 **零剪切**")
