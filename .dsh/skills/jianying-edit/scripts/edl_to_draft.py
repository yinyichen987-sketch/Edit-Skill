"""EDL -> 剪映草稿 转换器。

把与工具无关的剪辑决策对象（EDL，见 references/edl-schema.md）落成剪映
能直接打开的草稿工程。

用法：
    python edl_to_draft.py <edl.json> [--draft-root 草稿目录] [--name 草稿名] [--dry-run]

说明：
    - 剪映 7+ 不支持自动导出，导出必须由人在剪映里完成。
    - 生成的草稿由剪映在首次保存时自行加密；本工具只写明文草稿。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback

import pyJianYingDraft as d

DEFAULT_DRAFT_ROOT = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "JianyingPro", "User Data", "Projects", "com.lveditor.draft",
)

# 允许出现在 EDL 中的轨道类型 -> pyJianYingDraft 的 TrackType
TRACK_TYPES = {
    "video": d.TrackType.video,
    "audio": d.TrackType.audio,
    "text": d.TrackType.text,
    "sticker": d.TrackType.sticker,
    "effect": d.TrackType.effect,
    "filter": d.TrackType.filter,
}


class EdlError(Exception):
    pass


def tsec(value) -> str:
    """把 EDL 里的秒数转成 pyJianYingDraft 能正确解析的时间串。

    坑：time_util.tim() 对裸 int/float 按【微秒】解释（int(round(inp))），
    只有带单位后缀的字符串才按秒解析。传 0.5 会被当成 0.5 微秒取整成 0，
    导致亚秒级的时间全部丢失。因此这里一律转成 "3.5s" 形式。
    """
    return f"{float(value)}s"


# ---------------------------------------------------------------- 校验

def validate(edl: dict, base_dir: str) -> list[str]:
    """返回问题列表（空列表表示通过）。"""
    problems: list[str] = []

    canvas = edl.get("canvas") or {}
    for key in ("width", "height"):
        if not isinstance(canvas.get(key), int):
            problems.append(f"canvas.{key} 缺失或不是整数")

    tracks = edl.get("tracks") or []
    if not tracks:
        problems.append("tracks 为空，至少要定义一条轨道")
    names = [t.get("name") for t in tracks]
    for t in tracks:
        if t.get("type") not in TRACK_TYPES:
            problems.append(f"轨道 '{t.get('name')}' 的类型 '{t.get('type')}' 不支持")
        if not t.get("name"):
            problems.append("存在没有 name 的轨道")

    def resolve(p: str) -> str:
        return p if os.path.isabs(p) else os.path.normpath(os.path.join(base_dir, p))

    for item in list(edl.get("clips") or []):
        tid = item.get("id", "<无 id>")
        if item.get("track") not in names:
            problems.append(f"片段 {tid} 引用了不存在的轨道 '{item.get('track')}'")
        src = item.get("source")
        if not src:
            problems.append(f"片段 {tid} 缺少 source")
        elif not os.path.exists(resolve(src)):
            problems.append(f"片段 {tid} 的素材不存在: {src}")
        for key in ("start", "duration"):
            if not isinstance(item.get(key), (int, float)):
                problems.append(f"片段 {tid} 的 {key} 缺失或不是数字")
        if isinstance(item.get("duration"), (int, float)) and item["duration"] <= 0:
            problems.append(f"片段 {tid} 的 duration 必须为正数")

    for item in list(edl.get("texts") or []):
        tid = item.get("id", "<无 id>")
        if not item.get("content"):
            problems.append(f"文本 {tid} 的 content 为空")
        for key in ("start", "duration"):
            if not isinstance(item.get(key), (int, float)):
                problems.append(f"文本 {tid} 的 {key} 缺失或不是数字")

    return problems


# ---------------------------------------------------------------- 转换

def _transition(name: str):
    """按名称解析转场枚举；找不到时返回 None 并给出警告。"""
    if not name:
        return None
    tt = getattr(d.TransitionType, str(name), None)
    if tt is None:
        print(f"  [WARN] 未知转场 '{name}'，已跳过")
    return tt


def build(edl: dict, draft_root: str, name: str | None, dry_run: bool) -> dict:
    base_dir = os.path.dirname(os.path.abspath(edl.get("__path__", ".")))
    canvas = edl.get("canvas") or {}
    width = int(canvas.get("width", 1080))
    height = int(canvas.get("height", 1920))
    fps = int(canvas.get("fps", 30))
    draft_name = name or edl.get("project") or "dsh_edit"

    report = {"draft_name": draft_name, "tracks": [], "clips": 0, "texts": 0, "warnings": []}

    if dry_run:
        report["dry_run"] = True
        report["tracks"] = [{"name": t["name"], "type": t["type"]}
                            for t in (edl.get("tracks") or [])]
        report["clips"] = len(edl.get("clips") or [])
        report["texts"] = len(edl.get("texts") or [])
        return report

    folder = d.DraftFolder(draft_root)
    script = folder.create_draft(draft_name, width, height, fps=fps, allow_replace=True)

    # 轨道按 EDL 中给出的顺序创建：靠后的轨道在上层（前景）
    specs = []
    for t in edl.get("tracks") or []:
        specs.append(d.TrackSpec(TRACK_TYPES[t["type"]], t["name"]))
        report["tracks"].append({"name": t["name"], "type": t["type"]})
    script.append_tracks(specs)

    def resolve(p: str) -> str:
        return p if os.path.isabs(p) else os.path.normpath(os.path.join(base_dir, p))

    track_type_of = {t["name"]: t["type"] for t in (edl.get("tracks") or [])}

    # 分两步：先构造全部片段并挂好转场，再统一入轨。
    # 原因：ScriptFile.add_segment() 只在入轨那一刻把 segment.transition 登记进
    # materials.transitions（见 _script_file_segments.py 第 89 行）。若先入轨、
    # 之后才给前序片段补转场，转场素材不会被写入草稿，剪映里看不到任何转场。
    built: list = []
    by_track: dict = {}

    for item in edl.get("clips") or []:
        src = resolve(item["source"])
        start = float(item["start"])
        duration = float(item["duration"])
        kwargs: dict = {"volume": float(item.get("volume", 1.0))}
        if item.get("source_in") is not None:
            kwargs["source_timerange"] = d.trange(tsec(item["source_in"]), tsec(duration))
        if item.get("speed") is not None:
            kwargs["speed"] = float(item["speed"])

        if track_type_of.get(item["track"]) == "audio":
            seg = d.AudioSegment(src, d.trange(tsec(start), tsec(duration)), **kwargs)
        else:
            seg = d.VideoSegment(src, d.trange(tsec(start), tsec(duration)), **kwargs)

        built.append((item["track"], seg))
        by_track.setdefault(item["track"], []).append((item, seg))

    # 转场语义：EDL 中片段上的 transition 表示「进入本片段的转场」。
    # 剪映把转场存储在前一个片段上，因此挂到同轨道的前序片段。
    for _track, entries in by_track.items():
        for idx, (item, _seg) in enumerate(entries):
            trans_spec = item.get("transition") or {}
            trans = _transition(trans_spec.get("type"))
            if trans is None:
                continue
            if idx == 0:
                msg = f"片段 {item.get('id')} 指定了转场但没有同轨道前序片段，已忽略"
                report["warnings"].append(msg)
                print(f"  [WARN] {msg}")
                continue
            dur = trans_spec.get("duration")
            entries[idx - 1][1].add_transition(trans, duration=tsec(dur) if dur else None)

    for track, seg in built:
        script.add_segment(seg, track)
        report["clips"] += 1

    for item in edl.get("texts") or []:
        style = item.get("style") or {}
        color = style.get("color")
        text_style = d.TextStyle(
            size=float(style.get("size", 8.0)),
            bold=bool(style.get("bold", False)),
            color=tuple(color) if color else (1.0, 1.0, 1.0),
        )
        clip = d.ClipSettings(
            transform_x=float(style.get("transform_x", 0.0)),
            transform_y=float(style.get("transform_y", 0.0)),
        )
        seg = d.TextSegment(
            item["content"],
            d.trange(tsec(item["start"]), tsec(item["duration"])),
            style=text_style,
            clip_settings=clip,
        )
        script.add_segment(seg, item.get("track", "caption"))
        report["texts"] += 1

    script.save()
    report["draft_dir"] = os.path.join(draft_root, draft_name)
    return report


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description="把 EDL 决策对象转换为剪映草稿")
    ap.add_argument("edl", help="EDL JSON 路径")
    ap.add_argument("--draft-root", default=DEFAULT_DRAFT_ROOT, help="剪映草稿根目录")
    ap.add_argument("--name", help="草稿名（默认取 EDL 的 project 字段）")
    ap.add_argument("--dry-run", action="store_true", help="只校验，不生成草稿")
    ap.add_argument("--force", action="store_true", help="校验失败也继续")
    args = ap.parse_args()

    if not os.path.exists(args.edl):
        print(f"[FAIL] EDL 文件不存在: {args.edl}", file=sys.stderr)
        return 1

    with open(args.edl, encoding="utf-8") as fh:
        edl = json.load(fh)
    edl["__path__"] = os.path.abspath(args.edl)

    problems = validate(edl, os.path.dirname(os.path.abspath(args.edl)))
    if problems:
        print("=" * 60)
        print(f"校验发现 {len(problems)} 个问题：")
        for p in problems:
            print(f"  - {p}")
        print("=" * 60)
        if not args.force:
            print("已中止。修复后重试，或用 --force 强制继续。")
            return 1

    if not args.dry_run and not os.path.isdir(args.draft_root):
        print(f"[FAIL] 草稿根目录不存在: {args.draft_root}", file=sys.stderr)
        return 1

    try:
        report = build(edl, args.draft_root, args.name, args.dry_run)
    except Exception:
        print("[EXCEPTION] 生成草稿时抛出异常：", file=sys.stderr)
        traceback.print_exc()
        return 2

    print("=" * 60)
    if report.get("dry_run"):
        print("[DRY-RUN] 校验通过，未生成草稿")
    else:
        print(f"[OK] 草稿已生成: {report['draft_name']}")
        print(f"     位置: {report.get('draft_dir')}")
    print(f"     轨道 {len(report['tracks'])} 条: "
          + ", ".join(f"{t['name']}({t['type']})" for t in report["tracks"]))
    print(f"     视频片段 {report['clips']} 个 | 文本 {report['texts']} 条")
    print("     下一步：在剪映中打开该草稿，检查后手动导出（剪映 7+ 不支持自动导出）")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
