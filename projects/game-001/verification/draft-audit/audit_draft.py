"""EDL → 剪映草稿 独立审计器（t5 审阅用）。

它回答两个问题，且**不采信任何报告里的数字**：

A. EDL 本身可执行吗？
   - 素材文件存在、时长够用（`source_in + duration` 不越界）
   - 轨道引用合法、duration 为正、转场名在枚举里
   - 同轨道是否重叠/留缝

B. 草稿真的按 EDL 生成了吗？
   - canvas / fps / 轨道（名、类型、顺序）
   - 每个片段的 target_timerange / source_timerange（**微秒**）
   - 转场数量与**归属**（EDL 中 clip[i] 的转场应挂在草稿 segment[i-1] 上）
   - 文本内容与时间码
   - 素材路径

专门针对本项目已踩过的两个陷阱做显式判定：
  1. **`tim()` 微秒陷阱**：裸数字被当微秒 → 生成出微秒级片段。
     判定：timerange 数值 != round(秒 × 1e6)，或数值 < 1000（几乎必然是陷阱）。
  2. **转场登记时机**：先入轨后挂转场 → `materials.transitions` 为空。
     判定：草稿里 transition 素材数量与归属是否与 EDL 一致。

用法
----
    .venv/Scripts/python.exe audit_draft.py --edl <edl.json> --draft <草稿名>
    .venv/Scripts/python.exe audit_draft.py --selftest        # 用 spike 夹具验证审计器自身
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]

DEFAULT_DRAFT_ROOT = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "JianyingPro", "User Data", "Projects", "com.lveditor.draft",
)

US = 1_000_000  # 1 秒 = 1e6 微秒


# ---------------------------------------------------------------- 工具

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def media_info(path: Path) -> dict:
    """读素材事实：视频流时长、音频流时长、帧数、帧率。读不到返回空 dict。"""
    out: dict = {}
    try:
        from pymediainfo import MediaInfo
        mi = MediaInfo.parse(str(path))
        for t in mi.tracks:
            if t.track_type == "Video":
                out["video_duration_s"] = (t.duration or 0) / 1000.0
                out["frame_count"] = int(t.frame_count) if t.frame_count else None
                out["fps"] = float(t.frame_rate) if t.frame_rate else None
            elif t.track_type == "Audio":
                out.setdefault("audio_duration_s", (t.duration or 0) / 1000.0)
    except Exception as exc:
        out["error"] = str(exc)
    return out


def load_draft(draft_root: str, name: str) -> tuple[dict | None, str | None]:
    """返回 (草稿 JSON, 错误说明)。"""
    d = Path(draft_root) / name
    f = d / "draft_content.json"
    if not f.exists():
        return None, f"草稿不存在: {f}"
    raw = f.read_bytes()
    try:
        return json.loads(raw.decode("utf-8")), None
    except Exception:
        head = raw[:24]
        return None, (f"draft_content.json 不是明文 JSON（剪映 11.x 原生草稿是加密的；"
                      f"本项目不接入解密）。前 24 字节: {head!r}")


def to_us(seconds: float) -> int:
    return int(round(float(seconds) * US))


def us_to_s(value) -> float:
    return float(value) / US if isinstance(value, (int, float)) else float("nan")


# ---------------------------------------------------------------- 审计

class Audit:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, check: str, level: str, msg: str, **extra):
        self.items.append({"check": check, "level": level, "msg": msg, **extra})

    def ok(self, check: str, msg: str, **e):
        self.add(check, "ok", msg, **e)

    def warn(self, check: str, msg: str, **e):
        self.add(check, "warn", msg, **e)

    def error(self, check: str, msg: str, **e):
        self.add(check, "error", msg, **e)

    @property
    def errors(self) -> list[dict]:
        return [i for i in self.items if i["level"] == "error"]

    @property
    def warnings(self) -> list[dict]:
        return [i for i in self.items if i["level"] == "warn"]


def audit(edl_path: Path, draft_root: str, draft_name: str | None = None) -> dict:
    a = Audit()
    edl = load_json(edl_path)
    base = edl_path.parent
    canvas = edl.get("canvas") or {}
    tracks_def = edl.get("tracks") or []
    clips = edl.get("clips") or []
    texts = edl.get("texts") or []
    track_names = [t.get("name") for t in tracks_def]
    track_type = {t.get("name"): t.get("type") for t in tracks_def}

    # ---------------- A. EDL 可执行性
    src_facts: dict[str, dict] = {}
    for c in clips:
        cid = c.get("id", "?")
        src = c.get("source")
        if not src:
            a.error("A1-source", f"片段 {cid} 缺少 source")
            continue
        p = Path(src) if os.path.isabs(src) else (base / src)
        p = Path(os.path.normpath(str(p)))
        if not p.exists():
            a.error("A1-source", f"片段 {cid} 素材不存在: {src}")
            continue
        facts = src_facts.setdefault(str(p), media_info(p))
        if "error" in facts:
            a.warn("A3-bounds", f"片段 {cid} 读不到素材时长，越界未校验: {p.name}")
            continue

        if c.get("track") not in track_names:
            a.error("A4-track", f"片段 {cid} 引用不存在的轨道 {c.get('track')!r}")

        dur = c.get("duration")
        if not isinstance(dur, (int, float)) or dur <= 0:
            a.error("A2-duration", f"片段 {cid} duration 非法: {dur!r}")
            continue

        s_in = float(c.get("source_in") or 0.0)
        # 用视频流时长作硬上界（比容器/音频短，最保守）
        limit = facts.get("video_duration_s")
        label = "视频流"
        if limit is None:
            limit = facts.get("audio_duration_s")
            label = "音频流"
        if limit is not None:
            end = s_in + float(dur)
            if end > limit + 1e-6:
                a.error("A3-bounds",
                        f"片段 {cid} 越界: source_in {s_in} + duration {dur} = "
                        f"{end:.3f}s > {label}时长 {limit:.3f}s ({p.name})")
            else:
                a.ok("A3-bounds",
                     f"片段 {cid} 时间码在界内: {end:.3f}s <= {limit:.3f}s ({p.name}, {label})")
            fc = facts.get("frame_count")
            if fc:
                a.add("A3-frames", "info",
                      f"片段 {cid} 素材 {p.name}: {fc} 帧, "
                      f"按帧推算内容末点 ≈ {fc / (facts.get('fps') or 30):.3f}s")

        # 转场名
        tname = (c.get("transition") or {}).get("type")
        if tname:
            try:
                import pyJianYingDraft as d
                if getattr(d.TransitionType, str(tname), None) is None:
                    a.error("A5-transition-name",
                            f"片段 {cid} 转场名 {tname!r} 不在 TransitionType 枚举中（会被静默跳过）")
                else:
                    a.ok("A5-transition-name", f"片段 {cid} 转场名 {tname!r} 合法")
            except ImportError:
                a.warn("A5-transition-name", "无法导入 pyJianYingDraft，转场名未校验")

    # 同轨道排序 / 重叠 / 缝隙
    by_track: dict[str, list] = {}
    for c in clips:
        by_track.setdefault(c.get("track"), []).append(c)
    for trk, items in by_track.items():
        items = sorted(items, key=lambda x: float(x.get("start") or 0))
        for i in range(1, len(items)):
            prev_end = float(items[i - 1]["start"]) + float(items[i - 1]["duration"])
            cur_start = float(items[i]["start"])
            if cur_start < prev_end - 1e-6:
                a.warn("A7-overlap",
                       f"轨道 {trk}: {items[i-1]['id']} 与 {items[i]['id']} 重叠 "
                       f"{prev_end - cur_start:.3f}s")
            elif cur_start > prev_end + 1e-6:
                a.warn("A7-gap",
                       f"轨道 {trk}: {items[i-1]['id']} → {items[i]['id']} 之间有 "
                       f"{cur_start - prev_end:.3f}s 空隙（剪映里会留黑）")

    # 首片段带转场 → 执行层会忽略
    for trk, items in by_track.items():
        items = sorted(items, key=lambda x: float(x.get("start") or 0))
        if items and (items[0].get("transition") or {}).get("type"):
            a.warn("A6-first-transition",
                   f"轨道 {trk} 首个片段 {items[0]['id']} 带了转场，EDL 语义下会被忽略")

    # 文本轨道存在性
    for t in texts:
        if t.get("track") not in track_names:
            a.error("A8-text-track", f"文本 {t.get('id')} 引用不存在的轨道 {t.get('track')!r}")

    # ---------------- B. 草稿 vs EDL
    name = draft_name or edl.get("project") or "dsh_edit"
    draft, err = load_draft(draft_root, name)
    if draft is None:
        a.error("B0-draft", err or "草稿读取失败")
        return _report(a, edl_path, name, None)

    cc = draft.get("canvas_config") or {}
    if int(cc.get("width", -1)) == int(canvas.get("width", -2)) and \
       int(cc.get("height", -1)) == int(canvas.get("height", -2)):
        a.ok("B1-canvas", f"画布一致: {cc.get('width')}x{cc.get('height')}")
    else:
        a.error("B1-canvas",
                f"画布不一致: 草稿 {cc.get('width')}x{cc.get('height')} vs "
                f"EDL {canvas.get('width')}x{canvas.get('height')}")

    if int(draft.get("fps", -1)) == int(canvas.get("fps", -2)):
        a.ok("B2-fps", f"fps 一致: {draft.get('fps')}")
    else:
        a.error("B2-fps", f"fps 不一致: 草稿 {draft.get('fps')} vs EDL {canvas.get('fps')}")

    d_tracks = draft.get("tracks") or []
    a.add("B3-tracks", "info",
          "草稿轨道: " + ", ".join(f"{t.get('name')}({t.get('type')})" for t in d_tracks))
    if len(d_tracks) != len(tracks_def):
        a.error("B3-tracks", f"轨道数不一致: 草稿 {len(d_tracks)} vs EDL {len(tracks_def)}")
    else:
        mismatch = []
        for dt, et in zip(d_tracks, tracks_def):
            if dt.get("name") != et.get("name") or dt.get("type") != et.get("type"):
                mismatch.append(f"草稿 {dt.get('name')}({dt.get('type')}) vs "
                                f"EDL {et.get('name')}({et.get('type')})")
        if mismatch:
            for m in mismatch:
                a.error("B3-tracks", f"轨道不一致: {m}")
        else:
            a.ok("B3-tracks", "轨道名/类型/顺序一致")

    # material_id -> material
    mats: dict[str, dict] = {}
    for kind, lst in (draft.get("materials") or {}).items():
        if isinstance(lst, list):
            for m in lst:
                if isinstance(m, dict) and m.get("id"):
                    mats[m["id"]] = {**m, "_kind": kind}
    transition_ids = {m["id"] for m in draft.get("materials", {}).get("transitions", [])
                      if isinstance(m, dict) and m.get("id")}

    # 按轨道逐片段比对
    edl_by_track: dict[str, list] = {}
    for c in clips:
        edl_by_track.setdefault(c.get("track"), []).append(c)
    for trk, items in edl_by_track.items():
        items = sorted(items, key=lambda x: float(x.get("start") or 0))
        dt = next((t for t in d_tracks if t.get("name") == trk), None)
        if dt is None:
            continue
        segs = sorted(dt.get("segments") or [],
                      key=lambda s: (s.get("target_timerange") or {}).get("start", 0))
        if len(segs) != len(items):
            a.error("B4-count", f"轨道 {trk} 片段数不一致: 草稿 {len(segs)} vs EDL {len(items)}")
            continue
        a.ok("B4-count", f"轨道 {trk} 片段数一致: {len(segs)}")

        for i, (c, s) in enumerate(zip(items, segs)):
            cid = c.get("id", i)
            ttr = s.get("target_timerange") or {}
            str_ = s.get("source_timerange") or {}

            exp_ts, exp_td = to_us(c["start"]), to_us(c["duration"])
            if ttr.get("start") == exp_ts and ttr.get("duration") == exp_td:
                a.ok("B5-timeline", f"{cid}: target {us_to_s(ttr['start'])}s/"
                                    f"{us_to_s(ttr['duration'])}s 与 EDL 精确一致")
            else:
                hint = ""
                if isinstance(ttr.get("duration"), (int, float)) and 0 < ttr["duration"] < 1000:
                    hint = " ← 疑似 tim() 微秒陷阱（裸数字被当微秒）"
                a.error("B5-timeline",
                        f"{cid}: target 草稿 start={ttr.get('start')} dur={ttr.get('duration')} "
                        f"vs 期望 start={exp_ts} dur={exp_td}{hint}")

            s_in = c.get("source_in")
            if s_in is not None:
                exp_ss, exp_sd = to_us(s_in), to_us(c["duration"])
                if str_.get("start") == exp_ss and str_.get("duration") == exp_sd:
                    a.ok("B6-source", f"{cid}: source_in {s_in}s → {str_.get('start')}µs 正确")
                else:
                    a.error("B6-source",
                            f"{cid}: source 草稿 start={str_.get('start')} dur={str_.get('duration')} "
                            f"vs 期望 start={exp_ss} dur={exp_sd}")

            # 转场的归属检查放在下面单独一轮（见 B7），因为剪映把转场
            # 存在**前一个**片段上，映射关系不是同下标。

    # 转场归属核对（独立一轮）：
    # 剪映把转场存在**前一个**片段上，所以草稿 segs[j] 上的转场属于 EDL items[j+1]。
    # 用同下标去比对会得到完全相反的结论（首片段"凭空有转场"、后续片段"转场丢失"）。
    for trk, items in edl_by_track.items():
        items = sorted(items, key=lambda x: float(x.get("start") or 0))
        dt = next((t for t in d_tracks if t.get("name") == trk), None)
        if dt is None:
            continue
        segs = sorted(dt.get("segments") or [],
                      key=lambda s: (s.get("target_timerange") or {}).get("start", 0))
        if len(segs) != len(items):
            continue
        for j, s in enumerate(segs):
            has = bool(set(s.get("extra_material_refs") or []) & transition_ids)
            owner = items[j + 1].get("id") if j + 1 < len(items) else None
            want = (items[j + 1].get("transition") or {}).get("type") if owner else None
            seg_of = items[j].get("id", j)
            if want and has:
                tid = next(iter(set(s.get("extra_material_refs") or []) & transition_ids))
                tm = mats.get(tid, {})
                a.ok("B7-transition",
                     f"EDL {owner} 的转场 {want!r} 正确挂在草稿 seg[{j}]（{seg_of}）上，"
                     f"转场素材 name={tm.get('name')!r} duration={tm.get('duration')}µs")
                exp_tdur = to_us((items[j + 1].get("transition") or {}).get("duration") or 0)
                if exp_tdur and tm.get("duration") != exp_tdur:
                    a.error("B7b-transition-dur",
                            f"转场时长不一致: 草稿 {tm.get('duration')}µs vs EDL {exp_tdur}µs")
            elif want and not has:
                a.error("B7-transition",
                        f"EDL {owner} 声明了转场 {want!r}，但草稿 seg[{j}]（{seg_of}）上没有"
                        f"转场素材（剪映把转场存在前一片段；缺失意味着登记时机出错）")
            elif not want and has:
                a.error("B7-transition",
                        f"草稿 seg[{j}]（{seg_of}）上挂了转场，但 EDL "
                        f"{owner or '（无后续片段）'} 并未声明转场")
        if items and (items[0].get("transition") or {}).get("type"):
            a.warn("B7c-first-transition",
                   f"轨道 {trk} 首片段 {items[0].get('id')} 声明了转场，"
                   f"EDL 语义下无效（执行层应忽略且不写入草稿）")

    n_exp_trans = 0
    for trk, items in edl_by_track.items():
        ordered = sorted(items, key=lambda x: float(x.get("start") or 0))
        for i, c in enumerate(ordered):
            if i > 0 and (c.get("transition") or {}).get("type"):
                n_exp_trans += 1
    if len(transition_ids) == n_exp_trans:
        a.ok("B8-transition-count",
             f"转场素材数一致: 草稿 {len(transition_ids)} == EDL 非首片段转场 {n_exp_trans}")
    else:
        a.error("B8-transition-count",
                f"转场素材数不一致: 草稿 {len(transition_ids)} vs EDL 期望 {n_exp_trans}"
                f"（少了通常意味着先入轨后挂转场，转场被静默丢弃）")

    # 文本：段数 + 逐条时间码 + 文案
    d_text_tracks = [t for t in d_tracks if t.get("type") == "text"]
    n_seg_text = sum(len(t.get("segments") or []) for t in d_text_tracks)
    if n_seg_text != len(texts):
        a.error("B9-texts", f"文本段数不一致: 草稿 {n_seg_text} vs EDL {len(texts)}")
    else:
        a.ok("B9-texts", f"文本段数一致: {n_seg_text}")
        tsegs = []
        for t in d_text_tracks:
            tsegs.extend(sorted(t.get("segments") or [],
                                key=lambda s: (s.get("target_timerange") or {}).get("start", 0)))
        for i, (s, txt) in enumerate(zip(tsegs, texts)):
            tid = txt.get("id", i)
            ttr = s.get("target_timerange") or {}
            exp_s, exp_d = to_us(txt["start"]), to_us(txt["duration"])
            if ttr.get("start") != exp_s or ttr.get("duration") != exp_d:
                hint = ""
                if isinstance(ttr.get("duration"), (int, float)) and 0 < ttr["duration"] < 1000:
                    hint = " ← 疑似 tim() 微秒陷阱"
                a.error("B9b-text-time",
                        f"文本 {tid}: 草稿 start={ttr.get('start')} dur={ttr.get('duration')} "
                        f"vs 期望 start={exp_s} dur={exp_d}{hint}")
            # 文案：materials.texts[id].content 是再套一层 JSON 字符串
            mat = mats.get(s.get("material_id"), {})
            raw = mat.get("content")
            got = None
            if isinstance(raw, str):
                try:
                    got = json.loads(raw).get("text")
                except Exception:
                    got = None
            if got is not None and got != txt.get("content"):
                a.error("B9c-text-content",
                        f"文本 {tid} 文案不一致: 草稿 {got!r} vs EDL {txt.get('content')!r}")

    # 时间线总长
    max_end = 0
    for t in d_tracks:
        for s in t.get("segments") or []:
            tr_ = s.get("target_timerange") or {}
            max_end = max(max_end, (tr_.get("start") or 0) + (tr_.get("duration") or 0))
    if abs(max_end - (draft.get("duration") or 0)) <= 1:
        a.ok("B10-duration", f"草稿总时长 {us_to_s(draft['duration'])}s == 时间线末点")
    else:
        a.warn("B10-duration",
               f"草稿 duration {us_to_s(draft.get('duration'))}s != 时间线末点 {us_to_s(max_end)}s")

    return _report(a, edl_path, name, draft)


def _report(a: Audit, edl_path, name, draft) -> dict:
    return {
        "edl": str(edl_path),
        "draft_name": name,
        "draft_loaded": draft is not None,
        "error_count": len(a.errors),
        "warning_count": len(a.warnings),
        "verdict": "PASS" if not a.errors else "FAIL",
        "items": a.items,
    }


# ---------------------------------------------------------------- 自测

def selftest(repo_root: Path, draft_root: str) -> bool:
    """用 spike 夹具（sample-edl.json + DSH_EDL_TEST）验证审计器自身。"""
    edl = repo_root / "spike" / "sample-edl.json"
    print("=" * 72)
    print("审计器自测：spike/sample-edl.json  →  DSH_EDL_TEST")
    print("=" * 72)
    if not edl.exists():
        print("  [SKIP] 夹具不存在")
        return False
    rep = audit(edl, draft_root, "DSH_EDL_TEST")
    for it in rep["items"]:
        mark = {"ok": " ok ", "warn": "WARN", "error": "FAIL", "info": "info"}[it["level"]]
        print(f"  [{mark}] {it['check']:22s} {it['msg']}")

    # 断言：这个夹具是已知正确生成的，审计器必须判 PASS
    checks = {}
    for it in rep["items"]:
        checks.setdefault((it["level"], it["check"]), []).append(it["msg"])
    expect_ok = [
        ("ok", "B1-canvas"), ("ok", "B2-fps"), ("ok", "B3-tracks"),
        ("ok", "B5-timeline"), ("ok", "B6-source"), ("ok", "B7-transition"),
        ("ok", "B9-texts"),
    ]
    ok = True
    for key in expect_ok:
        if key not in checks:
            print(f"  [FAIL] 缺少期望的通过项: {key}")
            ok = False
    if rep["error_count"]:
        print(f"  [FAIL] 已知正确的夹具上出现了 {rep['error_count']} 个错误判定")
        ok = False
    if ok:
        print(f"\n  [PASS] 审计器在已知正确的夹具上判定 PASS（"
              f"{len(checks.get(('ok','B5-timeline'), []))} 个片段时间码精确一致）")
    return ok


# ---------------------------------------------------------------- 反例自测

def _mut_us_trap(draft):
    """把第一个视频片段的 target duration 改成 3（微秒）——模拟 tim() 裸数字陷阱。"""
    for t in draft.get("tracks", []):
        if t.get("type") == "video" and t.get("segments"):
            t["segments"][0]["target_timerange"]["duration"] = 3
            return True
    return False


def _mut_transition_dropped(draft):
    """删掉 seg[0] 上的转场引用——模拟"先入轨后挂转场"导致转场丢失。"""
    ids = {m["id"] for m in draft.get("materials", {}).get("transitions", []) if m.get("id")}
    for t in draft.get("tracks", []):
        for s in t.get("segments", []):
            refs = s.get("extra_material_refs") or []
            if set(refs) & ids:
                s["extra_material_refs"] = [r for r in refs if r not in ids]
                return True
    return False


def _mut_canvas(draft):
    draft.setdefault("canvas_config", {})["height"] = 1080
    return True


def _mut_timeline_shift(draft):
    """把 seg[1] 的 target start 偏移 0.5s——模拟时间线起点算错。"""
    for t in draft.get("tracks", []):
        segs = t.get("segments") or []
        if t.get("type") == "video" and len(segs) > 1:
            segs[1]["target_timerange"]["start"] = int(segs[1]["target_timerange"]["start"]) + 500000
            return True
    return False


NEG_CASES = [
    ("us-trap", _mut_us_trap, "B5-timeline"),
    ("transition-dropped", _mut_transition_dropped, "B7-transition"),
    ("canvas-mismatch", _mut_canvas, "B1-canvas"),
    ("timeline-shift", _mut_timeline_shift, "B5-timeline"),
]


def negtest(repo_root: Path, draft_root: str) -> bool:
    """在**故意改坏**的草稿上跑审计，确认它真的会失败（否则自测没有价值）。"""
    import copy
    import shutil

    src = Path(draft_root) / "DSH_EDL_TEST" / "draft_content.json"
    print("=" * 72)
    print("反例自测：故意改坏草稿，审计器必须报出对应错误")
    print("=" * 72)
    if not src.exists():
        print(f"  [SKIP] 缺少基准草稿: {src}")
        return False

    # 放在工作区内：沙箱可能禁止写系统临时目录
    tmp_root = Path(__file__).resolve().parent / "_negtest"
    if tmp_root.exists():
        shutil.rmtree(tmp_root, ignore_errors=True)
    tmp_root.mkdir(parents=True, exist_ok=True)
    base = json.loads(src.read_text(encoding="utf-8"))
    edl = repo_root / "spike" / "sample-edl.json"
    ok = True

    for name, mutate, expect_check in NEG_CASES:
        d = copy.deepcopy(base)
        applied = mutate(d)
        case_dir = tmp_root / ("NEG_" + name)
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "draft_content.json").write_text(
            json.dumps(d, ensure_ascii=False), encoding="utf-8")
        rep = audit(edl, str(tmp_root), "NEG_" + name)
        hit = [i for i in rep["items"]
               if i["level"] == "error" and i["check"] == expect_check]
        passed = bool(applied) and bool(hit) and rep["verdict"] == "FAIL"
        ok = ok and passed
        flag = "PASS" if passed else "FAIL"
        detail = hit[0]["msg"][:88] if hit else "未报出期望的错误"
        print(f"  [{flag}] {name:22s} 期望 {expect_check:16s} -> {detail}")

    # EDL 侧反例：时间码越界
    bad_edl = tmp_root / "bad-edl.json"
    bad_edl.write_text(json.dumps({
        "project": "NEG_EDL",
        "canvas": {"width": 1080, "height": 1920, "fps": 30},
        "tracks": [{"type": "video", "name": "main"}],
        "clips": [{"id": "x1", "track": "main",
                   "source": str((repo_root / "原始素材" /
                                  "4b0460c400bbb5320acb6063b4f59358.mp4").resolve()),
                   "source_in": 16.0, "start": 0.0, "duration": 3.0}],
        "texts": [],
    }, ensure_ascii=False), encoding="utf-8")
    rep = audit(bad_edl, str(tmp_root), "NEG_EDL")
    hit = [i for i in rep["items"] if i["level"] == "error" and i["check"] == "A3-bounds"]
    passed = bool(hit)
    ok = ok and passed
    print(f"  [{'PASS' if passed else 'FAIL'}] {'edl-out-of-bounds':22s} "
          f"期望 A3-bounds          -> {hit[0]['msg'][:88] if hit else '未报出'}")

    shutil.rmtree(tmp_root, ignore_errors=True)
    print()
    print("  [PASS] 反例全部被拦下，说明审计器的通过/失败都是可判定的" if ok
          else "  [FAIL] 有反例未被拦下，审计器不可信")
    return ok


# ---------------------------------------------------------------- main

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="EDL → 剪映草稿 独立审计器")
    ap.add_argument("--edl", help="EDL JSON 路径")
    ap.add_argument("--draft", help="草稿名（默认取 EDL 的 project）")
    ap.add_argument("--draft-root", default=DEFAULT_DRAFT_ROOT)
    ap.add_argument("--json-out", help="报告输出路径")
    ap.add_argument("--selftest", action="store_true", help="用 spike 夹具验证审计器自身")
    ap.add_argument("--negtest", action="store_true", help="用故意改坏的输入验证审计器会失败")
    args = ap.parse_args()

    if args.selftest:
        return 0 if selftest(REPO_ROOT, args.draft_root) else 1

    if args.negtest:
        return 0 if negtest(REPO_ROOT, args.draft_root) else 1

    if not args.edl:
        ap.error("需要 --edl（或用 --selftest）")
    edl_path = Path(args.edl)
    if not edl_path.is_absolute():
        edl_path = (Path.cwd() / edl_path).resolve()
    if not edl_path.exists():
        print(f"[FAIL] EDL 不存在: {edl_path}", file=sys.stderr)
        return 1

    rep = audit(edl_path, args.draft_root, args.draft)
    for it in rep["items"]:
        mark = {"ok": " ok ", "warn": "WARN", "error": "FAIL", "info": "info"}[it["level"]]
        print(f"  [{mark}] {it['check']:22s} {it['msg']}")
    print("=" * 72)
    print(f"verdict={rep['verdict']}  errors={rep['error_count']} warnings={rep['warning_count']}")

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"报告已写入: {args.json_out}")
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
