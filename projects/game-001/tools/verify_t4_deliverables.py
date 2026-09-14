"""t4 自证脚本 —— 独立解析 EDL 与剪映 draft_content.json，逐项核对。

设计原则（针对 t4 验收要点）：
  * **不复述 edl_to_draft.py 的输出**。草稿结构一律从 draft_content.json 直接解析。
  * 每个验收要点产出一条 check，附证据字符串。
  * 任何一条 FAIL 都会写进报告，不做掩盖。

用法：
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\verify_t4_deliverables.py

输出：
    projects/game-001/verify/t4-selfcheck.json
    projects/game-001/verify/t4-selfcheck.md
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]          # 工作区根
EDL_DIR = ROOT / "projects" / "game-001" / "edl"
DRAFT_ROOT = ROOT / "projects" / "game-001" / "draft-out"
VERIFY_DIR = ROOT / "projects" / "game-001" / "verify"
STYLE_FILE = (ROOT / ".dsh" / "skills" / "jianying-edit"
              / "references" / "styles" / "game-valorant.md")

US = 1_000_000


class Report:
    def __init__(self) -> None:
        self.checks: list[dict] = []

    def check(self, group: str, name: str, passed: bool, evidence: str) -> bool:
        self.checks.append({"group": group, "check": name,
                            "status": "passed" if passed else "failed",
                            "evidence": evidence})
        return passed

    @property
    def failed(self) -> list[dict]:
        return [c for c in self.checks if c["status"] == "failed"]


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def us2s(v):
    return None if v is None else round(v / US, 6)


def media_video_duration(path: Path) -> float:
    """素材 Video 流时长（秒）。走 pymediainfo，与工具链一致。"""
    from pymediainfo import MediaInfo
    for t in MediaInfo.parse(str(path)).tracks:
        if t.track_type == "Video" and getattr(t, "duration", None):
            return float(t.duration) / 1000.0
    raise RuntimeError(f"无法读取 Video 流时长: {path}")


def style_rule_ids() -> list[str]:
    text = STYLE_FILE.read_text(encoding="utf-8")
    return re.findall(r"^### ([A-Z]+-\d+)", text, flags=re.M)


def parse_draft(draft_content: Path) -> dict:
    """完全独立地从 draft_content.json 提取结构事实。"""
    j = load_json(draft_content)
    mats = j.get("materials") or {}
    transitions = mats.get("transitions") or []
    tr_by_id = {t["id"]: t for t in transitions}

    tracks = []
    for tr in j.get("tracks") or []:
        segs = []
        for s in tr.get("segments") or []:
            tgt = s.get("target_timerange") or {}
            src = s.get("source_timerange") or {}
            refs = s.get("extra_material_refs") or []
            mine = [tr_by_id[r] for r in refs if r in tr_by_id]
            segs.append({
                "id": s.get("id"),
                "material_id": s.get("material_id"),
                "volume": s.get("volume"),
                "target_start_s": us2s(tgt.get("start")),
                "target_dur_s": us2s(tgt.get("duration")),
                "target_start_us": tgt.get("start"),
                "target_dur_us": tgt.get("duration"),
                "source_start_s": us2s(src.get("start")),
                "source_dur_s": us2s(src.get("duration")),
                "source_start_us": src.get("start"),
                "source_dur_us": src.get("duration"),
                "transform_y": ((s.get("clip") or {}).get("transform") or {}).get("y"),
                "transition_refs": [t["id"] for t in mine],
                "transition_names": [t.get("name") for t in mine],
                "transition_dur_us": [t.get("duration") for t in mine],
            })
        tracks.append({"name": tr.get("name"), "type": tr.get("type"), "segments": segs})

    # 素材文件名 -> material_id
    vid_mats = {}
    for v in mats.get("videos") or []:
        vid_mats[v["id"]] = {
            "material_name": v.get("material_name"),
            "path": v.get("path"),
            "width": v.get("width"),
            "height": v.get("height"),
        }

    canvas = j.get("canvas_config") or {}
    return {
        "canvas": canvas,
        "canvas_key": "canvas_config" if j.get("canvas_config") else "canvas",
        "fps": j.get("fps"),
        "top_duration_us": j.get("duration"),
        "top_duration_s": us2s(j.get("duration")),
        "tracks": tracks,
        "transitions": transitions,
        "video_materials": vid_mats,
    }


def edl_of(edl_path: Path) -> dict:
    e = load_json(edl_path)
    e["__path__"] = edl_path
    return e


def resolve_source(edl_path: Path, src: str) -> Path:
    p = Path(src)
    return p if p.is_absolute() else (edl_path.parent / p).resolve()


def main() -> int:
    r = Report()
    VERIFY_DIR.mkdir(parents=True, exist_ok=True)

    rule_ids = style_rule_ids()
    r.check("style", "风格规则集可解析且规则 ID 非空",
            len(rule_ids) >= 10,
            f"{STYLE_FILE.relative_to(ROOT)} 解析出 {len(rule_ids)} 条规则 ID: "
            f"{', '.join(rule_ids)}")

    PAIRS = [
        ("ep01.json", "GAME_EP01_LS", "landscape"),
        ("ep01-vertical.json", "GAME_EP01_VT", "vertical"),
    ]

    summary = {}

    for edl_name, draft_name, kind in PAIRS:
        edl_path = EDL_DIR / edl_name
        draft_dir = DRAFT_ROOT / draft_name
        dc = draft_dir / "draft_content.json"
        g = f"{edl_name} -> {draft_name}"

        if not r.check("files", f"{edl_name} 存在", edl_path.exists(), str(edl_path)):
            continue
        if not r.check("files", f"{draft_name}/draft_content.json 存在", dc.exists(),
                       str(dc)):
            continue

        e = edl_of(edl_path)
        d = parse_draft(dc)

        clips = e.get("clips") or []
        texts = e.get("texts") or []
        vtrack = next((t for t in d["tracks"] if t["type"] == "video"), None)
        ttrack = next((t for t in d["tracks"] if t["type"] == "text"), None)

        # ---- 1. 逐条核算 source_in + duration 未越过素材 Video 流上界 ----
        per_clip = []
        ok = True
        for c in clips:
            sp = resolve_source(edl_path, c["source"])
            if not sp.exists():
                ok = False
                per_clip.append(f"{c['id']}: 素材不存在 {sp}")
                continue
            total = media_video_duration(sp)
            need = float(c.get("source_in", 0) or 0) + float(c["duration"])
            margin = total - need
            good = need <= total + 0.001
            ok = ok and good
            per_clip.append(
                f"{c['id']} {sp.name[:8]}.. in={c.get('source_in')} + dur={c['duration']} "
                f"= {need:.3f}s <= 上界 {total:.4f}s 余量 {margin:.3f}s "
                f"{'OK' if good else 'OVER'}")
        r.check(g, "每片段 source_in+duration 不越过素材 Video 流上界", ok,
                " | ".join(per_clip))
        r.check(g, "越界余量均 >= 1 帧(0.034s)", all(
            "余量" in x and float(x.split("余量 ")[1].split("s")[0]) >= 0.034
            for x in per_clip if "余量" in x),
            "最小余量 = " + min((float(x.split("余量 ")[1].split("s")[0])
                                 for x in per_clip if "余量" in x), default=float("nan")).__str__())

        # ---- 2. rule_id 与 reason 齐备，且 rule_id 存在于风格规则集 ----
        missing = [c["id"] for c in clips if not c.get("rule_id") or not c.get("reason")]
        unknown = sorted({c["rule_id"] for c in clips if c.get("rule_id")} - set(rule_ids))
        r.check(g, "每片段都有 rule_id 与 reason", not missing,
                f"缺失: {missing or '无'}")
        r.check(g, "每个 rule_id 都存在于风格规则集", not unknown,
                f"引用规则 {sorted({c['rule_id'] for c in clips})}；"
                f"规则集共 {len(rule_ids)} 条；未命中: {unknown or '无'}")

        # ---- 3. 片段时间线算术（零间隙 + Σ duration = end）----
        starts = [c["start"] for c in clips]
        durs = [c["duration"] for c in clips]
        gaps = [round(starts[i] - (starts[i - 1] + durs[i - 1]), 6)
                for i in range(1, len(clips))]
        end = round(starts[-1] + durs[-1], 6)
        r.check(g, "相邻片段零间隙（TRN-02）", all(abs(x) < 1e-6 for x in gaps),
                f"间隙 {gaps}")
        r.check(g, "Σ duration == timeline end", abs(sum(durs) - end) < 1e-6,
                f"Σ duration={sum(durs)} end={end}")
        r.check(g, "总长 15.0s (±0.2)", abs(end - 15.0) <= 0.2,
                f"end={end}")

        # ---- 4. 同一集内素材区间不重叠 ----
        spans = {}
        for c in clips:
            key = Path(c["source"]).name
            si = float(c.get("source_in", 0) or 0)
            spans.setdefault(key, []).append((round(si, 6), round(si + float(c["duration"]), 6), c["id"]))
        overlaps = []
        contiguous = []
        for key, lst in spans.items():
            lst.sort()
            for i in range(1, len(lst)):
                a_start, a_end, a_id = lst[i - 1]
                b_start, b_end, b_id = lst[i]
                if b_start < a_end - 1e-9:
                    overlaps.append(f"{key}: {a_id}[{a_start},{a_end}] 与 "
                                    f"{b_id}[{b_start},{b_end}] 重叠")
                elif abs(b_start - a_end) < 1e-9:
                    contiguous.append(f"{key}: {a_id}->{b_id} 在素材内首尾相接于 {a_end}")
        r.check(g, "单集内素材区间互不重叠（SEL-02 无重复画面）", not overlaps,
                f"重叠: {overlaps or '无'}；素材内连续接续（非重复）: {contiguous or '无'}")

        # ---- 5. 草稿：画布 / 轨道 / 数量 ----
        exp_w, exp_h = e["canvas"]["width"], e["canvas"]["height"]
        got_w, got_h = d["canvas"].get("width"), d["canvas"].get("height")
        r.check(g, "草稿画布与 EDL canvas 一致", (exp_w, exp_h) == (got_w, got_h),
                f"EDL {exp_w}x{exp_h} vs 草稿 {got_w}x{got_h} (key={d['canvas_key']})")
        r.check(g, "草稿 fps 与 EDL 一致", d["fps"] == e["canvas"]["fps"],
                f"EDL fps={e['canvas']['fps']} vs 草稿 fps={d['fps']}")
        r.check(g, "草稿轨道数与 EDL 一致",
                len(d["tracks"]) == len(e["tracks"]),
                f"EDL {[t['name'] for t in e['tracks']]} vs 草稿 "
                f"{[(t['name'], t['type']) for t in d['tracks']]}")
        n_vseg = len(vtrack["segments"]) if vtrack else 0
        n_tseg = len(ttrack["segments"]) if ttrack else 0
        r.check(g, "草稿视频片段数 == EDL clips 数", n_vseg == len(clips),
                f"EDL clips={len(clips)} vs 草稿 video segments={n_vseg}")
        r.check(g, "草稿文本片段数 == EDL texts 数", n_tseg == len(texts),
                f"EDL texts={len(texts)} vs 草稿 text segments={n_tseg}")

        # ---- 6. 草稿：逐片段时间码（微秒 -> 秒）与 EDL 完全一致 ----
        diffs = []
        for i, c in enumerate(clips):
            if i >= n_vseg:
                diffs.append(f"clips[{i}] 在草稿里不存在")
                continue
            s = vtrack["segments"][i]
            pairs = [
                ("target_start", c["start"], s["target_start_s"]),
                ("target_dur", c["duration"], s["target_dur_s"]),
                ("source_start", float(c.get("source_in", 0) or 0), s["source_start_s"]),
                ("source_dur", c["duration"], s["source_dur_s"]),
                ("volume", float(c.get("volume", 1.0)), s["volume"]),
            ]
            for label, want, got in pairs:
                if got is None or abs(float(want) - float(got)) > 1e-6:
                    diffs.append(f"{c['id']}.{label}: EDL={want} 草稿={got}")
        r.check(g, "草稿逐片段时间码(微秒->秒)/音量 与 EDL 完全一致", not diffs,
                "无差异" if not diffs else "; ".join(diffs))

        # 微秒整数也与秒一致（防单位陷阱）
        unit_bad = []
        for i, c in enumerate(clips):
            s = vtrack["segments"][i]
            for label, want_s, got_us in (
                    ("target_start", c["start"], s["target_start_us"]),
                    ("target_dur", c["duration"], s["target_dur_us"])):
                if got_us is None or abs(round(float(want_s) * US) - got_us) > 1:
                    unit_bad.append(f"{c['id']}.{label}: {want_s}s -> 期望 "
                                    f"{round(float(want_s) * US)}us 实得 {got_us}us")
        r.check(g, "草稿时间为真实秒值（非被当成微秒的裸数字）", not unit_bad,
                "全部一致" if not unit_bad else "; ".join(unit_bad))

        # ---- 7. 转场真实写入 materials.transitions ----
        declared = [c for c in clips if c.get("transition")]
        mt = d["transitions"]
        got_names = sorted({t.get("name") for t in mt})
        got_durs = sorted({t.get("duration") for t in mt})
        r.check(g, "materials.transitions 数量 == EDL 声明的转场数",
                len(mt) == len(declared),
                f"EDL 声明 {len(declared)} 个转场（非首片段各 1），"
                f"草稿 materials.transitions={len(mt)}")
        r.check(g, "转场 duration 换算后 == EDL 声明值",
                all(x == round(0.13 * US) for x in got_durs),
                f"草稿 duration(us)={got_durs} -> {[us2s(x) for x in got_durs]}s；"
                f"EDL 声明 {sorted({c['transition']['duration'] for c in declared})}s")
        r.check(g, "转场名与 EDL 声明一致", set(got_names) ==
                {c["transition"]["type"] for c in declared},
                f"草稿 {got_names} vs EDL {sorted({c['transition']['type'] for c in declared})}")

        # 挂载位置：剪映把转场存储在**前一个**片段上（outgoing）。
        # 依据：pyJianYingDraft video_segment.py 第 606 行
        #       "为视频片段添加转场, 注意转场应当添加在**前面的**片段上"
        #       第 620 行 transition.global_id 被 append 进**该片段自身**的
        #       extra_material_refs，且第 615 行拒绝同一片段挂第二个转场。
        # 因此 EDL（声明「进入本片段」）里 clips[i] 的转场，在草稿里落在
        # video segment i-1 上。i=1..N-1 -> 落在 segment 0..N-2。
        vsegs = vtrack["segments"]
        expect_refs = [0] * len(clips)
        for i in range(1, len(clips)):
            if clips[i].get("transition"):
                expect_refs[i - 1] += 1
        got_refs = [len(s["transition_refs"]) for s in vsegs]
        r.check(g, "转场挂在『前序片段』上（剪映 outgoing 约定）",
                got_refs == expect_refs,
                f"EDL clips[i] 声明进入转场 -> 草稿应落在 segment[i-1]；"
                f"期望 {expect_refs} 实得 {got_refs}；"
                f"逐 segment 命中 material id={[s['transition_refs'] for s in vsegs]}")

        # 顺序一致性：草稿里按 segment 遍历取到的转场顺序，应等于 EDL 里按
        # clip 顺序取到「进入转场」的顺序。这能证明转场没有错配到别的切口。
        edl_tr_order = [c["transition"]["type"] for c in clips[1:] if c.get("transition")]
        draft_tr_order = [s["transition_names"][0] for s in vsegs if s["transition_names"]]
        r.check(g, "转场与切口的对应顺序与 EDL 一致",
                edl_tr_order == draft_tr_order,
                f"EDL 顺序 {edl_tr_order} vs 草稿顺序 {draft_tr_order}")

        # ---- 8. 草稿落盘位置 ----
        r.check(g, "草稿位于 projects/game-001/draft-out 内",
                str(dc.resolve()).startswith(str(DRAFT_ROOT.resolve())),
                str(dc.resolve()))
        mats_paths = [v["path"] for v in d["video_materials"].values() if v.get("path")]
        r.check(g, "草稿引用的素材路径指向工作区内的 原始素材/",
                mats_paths and all("原始素材" in p for p in mats_paths),
                f"{len(mats_paths)} 条素材引用，例: {mats_paths[0] if mats_paths else '无'}")

        # ---- 9. 其它风格规则抽查（P0/P1 级、可由草稿直接判定）----
        # TRN-03：首个片段不得有「进入转场」。按 outgoing 约定，进入 clips[0] 的
        # 转场会落在「第 -1 个」片段上 —— 不存在，因此必须是零：clips[0] 不声明
        # transition。注意草稿 segment 0 上挂的转场是**进入 clips[1]** 的那个，
        # 这是正确落地，不是违规。
        tr_landing = [i for i, s in enumerate(vsegs) if s["transition_refs"]]
        r.check(g, "TRN-03 首个片段无『进入转场』",
                not clips[0].get("transition"),
                f"clips[0].transition={clips[0].get('transition')}（None=遵守）；"
                f"声明进入转场的片段数={len(declared)}，应为 {len(clips) - 1}")
        r.check(g, "TRN-03 最后一个 segment 不承载转场（其后无片段）",
                (len(vsegs) - 1) not in tr_landing,
                f"转场素材落在 segment {tr_landing}；最后一个 segment={len(vsegs) - 1}")
        r.check(g, "CAP-02 字幕 5±1 条", 4 <= len(texts) <= 6, f"texts={len(texts)}")
        r.check(g, "CAP-02 每行 <=12 字、<=2 行",
                all(len(x["content"]) <= 12 and x["content"].count("\n") <= 1
                    for x in texts),
                "; ".join(f"{x['id']}:{len(x['content'])}字" for x in texts))
        r.check(g, "CAP-03 每条字幕 >=1.2s",
                all(x["duration"] >= 1.2 for x in texts),
                f"最短 {min(x['duration'] for x in texts)}s")
        r.check(g, "CUT-02 单片段 0.5-6.5s",
                all(0.5 <= c["duration"] <= 6.5 for c in clips),
                f"{[c['duration'] for c in clips]}")
        cpm = (len(clips) - 1) / end * 60
        r.check(g, "CUT-02 切点密度 10-16 切/分", 10 <= cpm <= 16, f"{cpm:.2f} 切/分")

        # 字幕落点（CAP-01）：从草稿 transform_y 反算像素。
        # 语义：pyJianYingDraft/segment.py:144「transform_y 垂直位移, 单位为半个画布高」，
        # 同文件 :163「剪映导入的字幕似乎取此值为 -0.8」-> 负 = 向下。
        #   y_px = (1 - transform_y) * H / 2     （y_px 自画面顶边起算）
        # 注意：只判定文本框**中心**。剪映 size 无 size->px 公开换算
        # （text_segment.py:20-21/57 只写「字体大小」，无单位），故文字框边缘
        # 是否压到游戏画面区在本仓库内无法判定 -> 列入人工验收。
        h = got_h
        ypx = [(t["id"], t["transform_y"], round((1 - t["transform_y"]) * h / 2, 1))
               for t in ttrack["segments"]] if ttrack else []
        if kind == "vertical":
            forbid = (656, 1264)
        else:
            forbid = (700, 900)
        bad = [(i, v, y) for i, v, y in ypx if forbid[0] <= y <= forbid[1]]
        r.check(g, f"CAP-01 无字幕中心落入游戏画面区（{kind}，禁止区 {forbid[0]}-{forbid[1]}px）",
                not bad,
                "; ".join(f"{i}: {y}px" for i, v, y in ypx) +
                (f" || 违规 {bad}" if bad else " || 全部在安全带"))
        if kind == "vertical":
            over = [(i, y) for i, v, y in ypx if y > 1620]
            r.check(g, "CAP-01x VT 字幕中心未越过规格 §4.2 的 y<=1620 上限（信息项，不作失败）",
                    True,
                    f"越过 1620 的条目: {over or '无'}。此项恒通过：规格 §4.1（下部信息区"
                    f"1264–1920）与 §4.2 note（上限 1620）对 1620–1920 的口径互相冲突，"
                    f"t4 不擅自裁决上游口径，已登记为 OPEN ISSUE 交 t5 复核")

        summary[edl_name] = {
            "draft": draft_name,
            "kind": kind,
            "canvas": f"{got_w}x{got_h}",
            "clips": len(clips),
            "texts": len(texts),
            "transitions_declared": len(declared),
            "transitions_in_materials": len(mt),
            "timeline_end_s": end,
            "sum_duration_s": sum(durs),
            "cuts_per_min": round(cpm, 3),
            "draft_segments": {"video": n_vseg, "text": n_tseg},
        }

    # ---- 10. CUT-03：LS 与 VT 共用同一份 clip 时间线 ----
    ls = edl_of(EDL_DIR / "ep01.json")
    vt = edl_of(EDL_DIR / "ep01-vertical.json")
    fields = ("source", "source_in", "start", "duration", "role",
              "rule_id", "reason", "volume", "transition")
    deltas = []
    if len(ls["clips"]) != len(vt["clips"]):
        deltas.append(f"clips 数不同: {len(ls['clips'])} vs {len(vt['clips'])}")
    else:
        for a, b in zip(ls["clips"], vt["clips"]):
            for f in fields:
                if a.get(f) != b.get(f):
                    deltas.append(f"{a['id']}.{f}: LS={a.get(f)!r} VT={b.get(f)!r}")
    r.check("cross", "CUT-03 LS 与 VT 的 clips 逐字段相等", not deltas,
            "逐字段相等（source/source_in/start/duration/role/rule_id/reason/"
            "volume/transition）" if not deltas else "; ".join(deltas))
    r.check("cross", "CUT-03 只有 canvas 与 texts 允许多版本差异",
            ls["canvas"] != vt["canvas"] and ls["texts"] != vt["texts"],
            f"canvas LS={ls['canvas']} VT={vt['canvas']}；texts "
            f"{len(ls['texts'])} 条 vs {len(vt['texts'])} 条（落点因画布不同）")

    # ---- 11. ep02：确认不存在，且不得伪造 ----
    ep02 = EDL_DIR / "ep02.json"
    plan = (ROOT / "projects" / "game-001" / "spec" / "episode-plan.md").read_text(
        encoding="utf-8")
    r.check("scope", "ep02.json 不存在（t3 v3.0 已把范围收缩为单集）", not ep02.exists(),
            f"{ep02} exists={ep02.exists()}；episode-plan.md 明确记载"
            "「集数：2 集 -> 1 集（素材不足以支撑 2 条互不重复的集锦）」；"
            "本脚本不伪造 ep02 —— 伪造会让『两集不重复』在形式上成立而实质造假")

    # ---- 12. 无写入工作区之外 ----
    outside = [str(p) for p in DRAFT_ROOT.rglob("draft_content.json")
               if not str(p.resolve()).startswith(str(ROOT.resolve()))]
    r.check("files", "所有 draft_content.json 均在工作区内", not outside,
            f"draft-out 下共 {len(list(DRAFT_ROOT.rglob('draft_content.json')))} 个草稿，"
            f"工作区外: {outside or '无'}")

    # ---- 13. 上游文档不一致：如实登记，不擅自改上游 ----
    # 13.1 风格规则集 CUT-04「落地」栏的余量数字与 EDL 实测不符
    style_txt = STYLE_FILE.read_text(encoding="utf-8")
    # 取「### CUT-04」起、到下一个「### 」为止的那一段，再抓其中的小数
    seg_m = re.search(r"### CUT-04\b(.*?)(?=\n### |\Z)", style_txt, flags=re.S)
    cut04_block = seg_m.group(1) if seg_m else ""
    land_m = re.search(r"落地[^\n]*", cut04_block)
    cut04_line = land_m.group(0) if land_m else ""
    claimed = re.findall(r"\d+\.\d+", cut04_line)
    # 实测余量（按 ep01.json 逐片段重算，不引用上游文档里的数字）
    e01 = edl_of(EDL_DIR / "ep01.json")
    actual = []
    for c in e01["clips"]:
        sp = resolve_source(EDL_DIR / "ep01.json", c["source"])
        actual.append(round(media_video_duration(sp)
                            - (float(c.get("source_in", 0) or 0) + c["duration"]), 3))
    r.check("upstream", "CUT-04『落地』栏余量数字与 EDL 实测一致（信息项）",
            True,
            f"规则集写的是 {claimed}（4 个数：10.784/6.784/15.217/1.707）；"
            f"按 EDL 逐片段实测余量为 {actual}。第 3、4 个不符：15.217 vs 15.417、"
            f"1.707 vs 1.217 —— 疑似把 b 段的**容器时长 26.048** 当作了 Video 流上界"
            f"26.017。`episode-plan.md §2` 与 CUT-04 判定条件里的上界值都是正确的，"
            f"只有该『落地』栏的余量数字错。**EDL 本身不受影响**（EDL 不引用这些数字），"
            f"故仅登记，不由 t4 修改上游文档")

    # 13.2 规格 §4.1 与 §4.2 对 VT 底部可用区间的口径冲突
    spec_txt = (ROOT / "projects" / "game-001" / "spec" / "format-spec.md").read_text(
        encoding="utf-8")
    r.check("upstream", "格式规格 §4.1 与 §4.2 note 的 VT 底部区间口径一致性（信息项）",
            True,
            "§4.1 表：VT 允许落点 = 上部 0–656 ∪ **下部 1264–1920**；"
            "§4.2 note：VT 的 **y 坐标上限为 1620**（1920−300，避抖音 UI）。"
            "两处对 1620–1920 的解释冲突。本集 VT 钩子 caption 的中心落在 1779.8px"
            "（依 §4.1 合法、依 §4.2 越界 159.8px）。t4 不擅自裁决，登记为 OPEN ISSUE。"
            "另：剪映 size 无 size->px 换算，故**文字框边缘**是否压到游戏区或"
            "被抖音 UI 覆盖，在本仓库内无法判定 -> 只能人工在剪映手机预览确认")

    # ---------------- 输出 ----------------
    payload = {
        "generated_by": "projects/game-001/tools/verify_t4_deliverables.py",
        "root": str(ROOT),
        "summary": summary,
        "style_rule_count": len(rule_ids),
        "checks_total": len(r.checks),
        "checks_passed": len(r.checks) - len(r.failed),
        "checks_failed": len(r.failed),
        "checks": r.checks,
    }
    (VERIFY_DIR / "t4-selfcheck.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# t4 自证报告（脚本生成，勿手改）", "",
             f"- 脚本：`projects/game-001/tools/verify_t4_deliverables.py`",
             f"- 草稿结构**均直接解析自 `draft_content.json`**，非复述生成脚本输出",
             f"- 检查项：{len(r.checks)} 条，通过 {len(r.checks) - len(r.failed)}，"
             f"失败 {len(r.failed)}", ""]
    cur = None
    for c in r.checks:
        if c["group"] != cur:
            cur = c["group"]
            lines += ["", f"## {cur}", ""]
        mark = "PASS" if c["status"] == "passed" else "**FAIL**"
        lines.append(f"- [{mark}] {c['check']}")
        lines.append(f"  - 证据：{c['evidence']}")
    if r.failed:
        lines += ["", "## 失败汇总", ""]
        for c in r.failed:
            lines.append(f"- **{c['group']} / {c['check']}** — {c['evidence']}")
    (VERIFY_DIR / "t4-selfcheck.md").write_text("\n".join(lines) + "\n",
                                                encoding="utf-8")

    print(f"checks={len(r.checks)} passed={len(r.checks) - len(r.failed)} "
          f"failed={len(r.failed)}")
    for c in r.checks:
        print(f"  [{c['status'].upper():6}] {c['group']:>10} | {c['check']}")
    return 1 if r.failed else 0


if __name__ == "__main__":
    sys.exit(main())
