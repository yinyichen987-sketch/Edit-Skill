"""解析生成的 draft_content.json，与 EDL 逐项对照（t4 自证）。

关键结构事实（实测，剪映 11.4.2 / pyJianYingDraft 0.3.0 生成）：
  - 转场不写在 segment.transition 上，而是 segment.extra_material_refs 里指向
    materials.transitions[].id（已知陷阱 2 的正确结果形态）。
  - 文字内容不在 segment.content 上，而是在 materials.texts[id].content，
    该字段是**再套一层 JSON 字符串**：{"styles":[...], "text": "..."}。
  - 文本位置在 segment.clip.transform.{x,y}。

用法：.venv\\Scripts\\python.exe projects\\game-001\\tools\\verify_drafts.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
US = 1_000_000.0

PAIRS = [
    ("GAME_EP01_LS", "projects/game-001/edl/ep01.json", 1920, 1080),
    ("GAME_EP01_VT", "projects/game-001/edl/ep01-vertical.json", 1080, 1920),
]

FAIL = []


def check(ok, msg):
    print(("  PASS  " if ok else "  FAIL  ") + msg)
    if not ok:
        FAIL.append(msg)


def sec(us):
    return round(int(us) / US, 6)


for name, edl_rel, cw, ch in PAIRS:
    print(f"\n===== {name} =====")
    edl_path = os.path.join(ROOT, edl_rel)
    draft_dir = os.path.join(ROOT, "projects", "game-001", "draft-out", name)

    with open(os.path.join(draft_dir, "draft_content.json"), encoding="utf-8") as fh:
        draft = json.load(fh)
    with open(edl_path, encoding="utf-8") as fh:
        edl = json.load(fh)

    print("-- 落盘位置（必须都在工作区内）")
    for fn in ("draft_content.json", "draft_meta_info.json"):
        p = os.path.join(draft_dir, fn)
        check(os.path.isfile(p), f"{fn}: {os.path.relpath(p, ROOT)}")
    check(os.path.commonpath([ROOT, os.path.abspath(draft_dir)]) == ROOT,
          f"草稿目录在工作区内: {os.path.relpath(draft_dir, ROOT)}")

    print("-- 画布")
    dc = draft.get("canvas_config") or {}
    check(dc.get("width") == cw and dc.get("height") == ch,
          f"canvas_config = {dc} == {cw}x{ch}")

    print("-- 轨道")
    tracks = draft.get("tracks") or []
    print(f"          tracks = {[(t.get('type'), t.get('name')) for t in tracks]}")
    check(len(tracks) == len(edl["tracks"]), f"轨道数 {len(tracks)} == EDL {len(edl['tracks'])}")
    check([t.get("name") for t in tracks] == [t["name"] for t in edl["tracks"]], "轨道名与顺序一致")

    mats = draft.get("materials") or {}
    vids = {m["id"]: m for m in mats.get("videos", [])}
    txts = {m["id"]: m for m in mats.get("texts", [])}
    trans = {m["id"]: m for m in mats.get("transitions", [])}
    by_name = {t.get("name"): t for t in tracks}
    main_segs = by_name["main"].get("segments") or []
    cap_segs = by_name["caption"].get("segments") or []

    print("-- video 片段（微秒 → 秒）与 EDL 对照")
    check(len(main_segs) == len(edl["clips"]), f"video 片段数 {len(main_segs)} == EDL {len(edl['clips'])}")
    end_max = 0.0
    for i, (seg, clip) in enumerate(zip(main_segs, edl["clips"])):
        st, du = sec(seg["target_timerange"]["start"]), sec(seg["target_timerange"]["duration"])
        si = sec(seg["source_timerange"]["start"])
        fname = os.path.basename(vids.get(seg["material_id"], {}).get("path", "<未找到>"))
        print(f"          clip{i + 1} target[{st:.2f}, {st + du:.2f}] dur={du:.2f} source_in={si:.2f} vol={seg.get('volume')} | {fname}")
        check(abs(st - clip["start"]) < 1e-6, f"clip{i + 1} start {st} == EDL {clip['start']}")
        check(abs(du - clip["duration"]) < 1e-6, f"clip{i + 1} duration {du} == EDL {clip['duration']}")
        check(abs(si - clip["source_in"]) < 1e-6, f"clip{i + 1} source_in {si} == EDL {clip['source_in']}")
        check(fname == os.path.basename(clip["source"]), f"clip{i + 1} 素材文件与 EDL 一致 ({fname})")
        check(abs(seg.get("volume", 1.0) - clip["volume"]) < 1e-6,
              f"clip{i + 1} volume {seg.get('volume')} == EDL {clip['volume']}")
        end_max = max(end_max, st + du)

    print("-- 转场是否真的写入（已知陷阱 2）")
    declared = sum(1 for c in edl["clips"] if c.get("transition"))
    print(f"          materials.transitions 条数 = {len(trans)}；EDL 声明的转场数 = {declared}")
    for m in trans.values():
        print(f"            transition material: id={m['id'][:8]}… name={m.get('name')} duration={sec(m.get('duration', 0))}s")
    check(len(trans) == declared, f"转场素材条数 {len(trans)} == 声明 {declared}")
    check(all(m.get("name") == "闪白" for m in trans.values()), "所有转场名为「闪白」")
    check(all(abs(sec(m.get("duration", 0)) - 0.13) < 1e-6 for m in trans.values()),
          "每个转场 duration 换算回秒 == 0.13")
    # 逐片段核对（实测的出题/答案关系）：
    # EDL 中 clip[n]（n≥2）声明 transition"进入本片段" → 工具把它挂到 clip[n-1] 上。
    # 所以 draft 里 clip[k] 应带 (EDL clip[k+1] 是否声明转场 ? 1 : 0) 条转场引用。
    for k, seg in enumerate(main_segs):
        refs = [r for r in seg.get("extra_material_refs", []) if r in trans]
        declared_next = bool(edl["clips"][k + 1].get("transition")) if k + 1 < len(edl["clips"]) else False
        expect = 1 if declared_next else 0
        print(f"          draft clip{k + 1} 挂载转场引用 {len(refs)} 条"
              f"（EDL clip{k + 2 if k + 1 < len(edl['clips']) else '-'} 声明转场 = {declared_next} → 应为 {expect}）")
        check(len(refs) == expect,
              f"draft clip{k + 1} 转场引用数 {len(refs)} == {expect}（挂载前序语义）")
    # 首片段必须无转场（EDL 首片段未声明 transition）
    first_refs = [r for r in main_segs[0].get("extra_material_refs", []) if r in trans]
    check(not edl["clips"][0].get("transition"), "EDL 首片段未声明 transition（TRN-03）")
    refs_all = sum(len([r for r in s.get("extra_material_refs", []) if r in trans]) for s in main_segs)
    check(refs_all == declared, f"全部转场引用合计 {refs_all} == 声明 {declared}")

    print("-- 转场是否被正确挂到「前序片段」（语义：进入本片段）")
    # clip2/3/4 的转场时间点必须紧邻其 start
    for i in (1, 2, 3):
        prev_end = sec(main_segs[i - 1]["target_timerange"]["start"]) + sec(main_segs[i - 1]["target_timerange"]["duration"])
        cur_start = sec(main_segs[i]["target_timerange"]["start"])
        refs = [r for r in main_segs[i - 1].get("extra_material_refs", []) if r in trans]
        has = bool(refs)
        print(f"          clip{i}→clip{i + 1} 边界: prev_end={prev_end:.2f} cur_start={cur_start:.2f} "
              f"差 {round(cur_start - prev_end, 6)}；转场挂在前序 = {has}")
        check(has, f"clip{i + 1} 的转场挂在前序 clip{i} 上")

    print("-- text 片段（微秒 → 秒、文案、位置）与 EDL 对照")
    check(len(cap_segs) == len(edl["texts"]), f"text 片段数 {len(cap_segs)} == EDL {len(edl['texts'])}")
    for i, (seg, txt) in enumerate(zip(cap_segs, edl["texts"])):
        st, du = sec(seg["target_timerange"]["start"]), sec(seg["target_timerange"]["duration"])
        raw = txts.get(seg["material_id"], {}).get("content", "")
        try:
            content = json.loads(raw).get("text", "")
        except Exception:
            content = "<解析失败>"
        clip = seg.get("clip") or {}
        ty = (clip.get("transform") or {}).get("y")
        print(f"          text{i + 1} content={content!r} target[{st:.2f}, {st + du:.2f}] transform.y={ty}")
        check(abs(st - txt["start"]) < 1e-6, f"text{i + 1} start {st} == EDL {txt['start']}")
        check(abs(du - txt["duration"]) < 1e-6, f"text{i + 1} duration {du} == EDL {txt['duration']}")
        check(content == txt["content"], f"text{i + 1} 文案与 EDL 一致（{content!r}）")
        check(ty is not None and abs(ty - txt["style"]["transform_y"]) < 1e-6,
              f"text{i + 1} transform.y {ty} == EDL {txt['style']['transform_y']}")

    print("-- 总时长")
    print(f"          end = start(last) + duration(last) = {end_max:.3f}s")
    check(14.8 <= end_max <= 15.2, f"总时长 {end_max:.3f} 落在 [14.8, 15.2]")
    check(abs(end_max - 15.0) < 1e-6, f"总时长 {end_max:.3f} == 15.000")

print("\n===== 跨版本一致性（CUT-03） =====")
with open(os.path.join(ROOT, "projects/game-001/edl/ep01.json"), encoding="utf-8") as fh:
    a = json.load(fh)
with open(os.path.join(ROOT, "projects/game-001/edl/ep01-vertical.json"), encoding="utf-8") as fh:
    b = json.load(fh)
check(a["clips"] == b["clips"], "LS 与 VT 的 clips 数组逐字段相等")
check(a["canvas"] != b["canvas"], "LS 与 VT 的 canvas 不同（唯一允许的结构差异）")
check([(t["start"], t["duration"], t["content"]) for t in a["texts"]]
      == [(t["start"], t["duration"], t["content"]) for t in b["texts"]],
      "LS 与 VT 的文本时间码与文案一致（只有位置/字号不同）")

print()
print(f"RESULT: {'ALL PASS' if not FAIL else str(len(FAIL)) + ' FAILURES'}")
for f in FAIL:
    print("  - " + f)
sys.exit(1 if FAIL else 0)
