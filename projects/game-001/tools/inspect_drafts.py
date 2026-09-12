"""独立解析剪映 draft_content.json，输出结构事实（不依赖生成脚本的输出）。

用法：
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\inspect_drafts.py <draft_content.json> [...]
"""
import json
import sys
from pathlib import Path


def us(v):
    """微秒 -> 秒"""
    if v is None:
        return None
    return round(v / 1_000_000.0, 6)


def analyze(path: Path):
    raw = path.read_bytes()
    # 剪映草稿里中文字段可能是 UTF-8；用 utf-8 读，失败再退 latin-1 只为了不崩
    try:
        text = raw.decode("utf-8")
        enc = "utf-8"
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
        enc = "utf-8(replace)"
    j = json.loads(text)

    print("=" * 78)
    print(f"FILE   : {path}")
    print(f"encoding: {enc}  bytes: {len(raw)}")

    # 画布：不同版本 key 不一样，全部探测
    canvas = None
    for k in ("canvas_config", "canvas"):
        if isinstance(j.get(k), dict):
            canvas = j[k]
            print(f"canvas[{k}]: {canvas}")
            break
    if canvas is None:
        print("canvas: <not found>")

    for k in ("duration", "fps", "version", "new_version"):
        if k in j:
            print(f"top.{k} = {j[k]}")

    tracks = j.get("tracks") or []
    print(f"tracks: {len(tracks)}")

    mats = j.get("materials") or {}
    trans = mats.get("transitions") or []
    print(f"materials.transitions: {len(trans)}")
    tr_by_id = {}
    for t in trans:
        tr_by_id[t.get("id")] = t
        print(
            f"  - id={t.get('id')} name={t.get('name')!r} "
            f"duration_us={t.get('duration')} -> {us(t.get('duration'))}s "
            f"is_overlap={t.get('is_overlap')} effect_id={t.get('effect_id')}"
        )

    grand_total = 0
    for ti, tr in enumerate(tracks):
        segs = tr.get("segments") or []
        grand_total += len(segs)
        print("-" * 78)
        print(f"track[{ti}] name={tr.get('name')!r} type={tr.get('type')!r} segments={len(segs)}")
        for si, s in enumerate(segs):
            tgt = s.get("target_timerange") or {}
            src = s.get("source_timerange") or {}
            refs = s.get("extra_material_refs") or []
            my_tr = [r for r in refs if r in tr_by_id]
            trans_desc = "none"
            if my_tr:
                t0 = tr_by_id[my_tr[0]]
                trans_desc = f"{t0.get('name')!r} dur={us(t0.get('duration'))}s"
            print(
                f"  seg[{si}] id={s.get('id')}\n"
                f"        target  start={us(tgt.get('start'))}s  dur={us(tgt.get('duration'))}s"
                f"  (us {tgt.get('start')}/{tgt.get('duration')})\n"
                f"        source  start={us(src.get('start'))}s  dur={us(src.get('duration'))}s\n"
                f"        material_id={s.get('material_id')}  volume={s.get('volume')}\n"
                f"        transition(refs)={trans_desc}"
            )
    print("-" * 78)
    print(f"TOTAL segments across tracks: {grand_total}")
    return {
        "file": str(path),
        "tracks": len(tracks),
        "segments": grand_total,
        "transitions": len(trans),
        "canvas": canvas,
        "json": j,
    }


if __name__ == "__main__":
    for p in sys.argv[1:]:
        analyze(Path(p))
