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

def _material_duration(path: str, kind: str = "video") -> tuple[float | None, str]:
    """返回 (可用时长秒, 依据说明)。

    kind='video' 时以**视频流**为准。实测本机素材容器/音频时长比视频流长约 13–46ms
    （如 19.030s vs 18.984s）；沿用容器时长会让贴着容器卡点的片段通过校验，
    但剪映里取不到对应画面，表现为末帧滞留或黑尾。
    """
    try:
        from pymediainfo import MediaInfo
    except ImportError:
        return None, "pymediainfo 不可用"
    try:
        tracks = MediaInfo.parse(path).tracks
    except Exception as exc:  # noqa: BLE001
        return None, f"解析失败: {exc}"

    want = "Video" if kind == "video" else "Audio"
    for t in tracks:
        if t.track_type == want and getattr(t, "duration", None):
            return float(t.duration) / 1000.0, f"{want} 轨 duration"

    durations = [float(t.duration) / 1000.0 for t in tracks if getattr(t, "duration", None)]
    if durations:
        return max(durations), "所有轨道最长者（回退：未找到目标轨道）"
    return None, "无可用时长信息"


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
    kind_of = {t.get("name"): ("audio" if t.get("type") == "audio" else "video")
               for t in tracks}
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

        # 时间码越界校验：source_in + duration 不得超出素材**对应流**的可用时长。
        # 缺失这一步时，越界 EDL 也能通过 dry-run，直到剪映里才发现画面不够。
        # 容差取 1ms（仅吸收浮点噪声）：视频流上界已按真实末帧收紧，不再需要额外余量。
        dur = item.get("duration")
        src_in = item.get("source_in", 0) or 0
        if (src and os.path.exists(resolve(src))
                and isinstance(dur, (int, float)) and dur > 0
                and isinstance(src_in, (int, float))):
            kind = kind_of.get(item.get("track"), "video")
            total, basis = _material_duration(resolve(src), kind)
            if total is None:
                problems.append(
                    f"片段 {tid} 无法读取素材时长（{basis}），时间码越界未校验: {src}")
            elif float(src_in) + float(dur) > total + 0.001:
                problems.append(
                    f"片段 {tid} 时间码越界: source_in={src_in} + duration={dur} "
                    f"= {float(src_in) + float(dur):.4f}s 超出{kind}流可用时长 "
                    f"{total:.4f}s（依据: {basis}, {os.path.basename(src)}）")

        # 转场名校验：名字写错时 _transition() 只会 WARN 然后静默跳过，
        # 草稿表面正常却没有转场。这里在 dry-run 阶段就拦下。
        tname = (item.get("transition") or {}).get("type")
        if tname and getattr(d.TransitionType, str(tname), None) is None:
            problems.append(
                f"片段 {tid} 的转场名 '{tname}' 不存在于 TransitionType 枚举"
                f"（写错会被静默跳过，草稿里不会有转场）")

    for item in list(edl.get("texts") or []):
        tid = item.get("id", "<无 id>")
        if not item.get("content"):
            problems.append(f"文本 {tid} 的 content 为空")
        for key in ("start", "duration"):
            if not isinstance(item.get(key), (int, float)):
                problems.append(f"文本 {tid} 的 {key} 缺失或不是数字")

    # 音频叠加（BGM / 音效）：与片段同一套越界口径。
    # 第 17 轮补：此前只校验 clips，于是「BGM 文件不在」「音效比素材本身还长」
    # 这类错要等剪映里才发现（build 只打 WARN，不拦）。
    for i, ao in enumerate(edl.get("audio_overlays") or [], 1):
        tag = f"音频叠加 #{i}（track={ao.get('track')}）"
        src = ao.get("source")
        if not src:
            problems.append(f"{tag} 缺少 source")
            continue
        exists = os.path.exists(resolve(src))
        if not exists:
            problems.append(f"{tag} 的音频不存在: {src}")
        if ao.get("track") and ao["track"] not in names:
            problems.append(f"{tag} 引用了不存在的轨道 '{ao['track']}'"
                            "（build 会自动建轨，但显式声明才看得出意图）")
        for key in ("start", "duration"):
            if not isinstance(ao.get(key), (int, float)):
                problems.append(f"{tag} 的 {key} 缺失或不是数字")
        dur = ao.get("duration")
        src_in = ao.get("source_in", 0) or 0
        if (exists and isinstance(dur, (int, float)) and dur > 0
                and isinstance(src_in, (int, float))):
            total, basis = _material_duration(resolve(src), "audio")
            if total is None:
                problems.append(f"{tag} 无法读取时长（{basis}），越界未校验: {src}")
            elif float(src_in) + float(dur) > total + 0.001:
                problems.append(
                    f"{tag} 时间码越界: source_in={src_in} + duration={dur} = "
                    f"{float(src_in) + float(dur):.4f}s 超出音频可用时长 {total:.4f}s"
                    f"（依据: {basis}, {os.path.basename(src)}）")

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


def _enum_of(enum_cls, name, report: dict, ctx: str):
    """按名称取枚举成员；取不到就记警告并返回 None（不静默）。"""
    if not name:
        return None
    obj = getattr(enum_cls, str(name), None)
    if obj is None:
        msg = f"{ctx} 的 '{name}' 不在 {enum_cls.__name__} 中，已跳过"
        report["warnings"].append(msg)
        print(f"  [WARN] {msg}")
    return obj


def _keyframes(seg, item, report: dict, ctx: str) -> None:
    for kf in item.get("keyframes") or []:
        prop = getattr(d.KeyframeProperty, str(kf.get("property")), None)
        if prop is None:
            msg = f"{ctx} 的关键帧属性 '{kf.get('property')}' 不存在，已跳过"
            report["warnings"].append(msg)
            print(f"  [WARN] {msg}")
            continue
        seg.add_keyframe(prop, tsec(kf["time"]), float(kf["value"]))


def band_scale(canvas_w: int, canvas_h: int, src_w: int, src_h: int,
               band_h: float) -> float:
    """求「让素材在画布中显示为 band_h 像素高」所需的 clip.scale。

    依据（**实测得出，不是猜的**）：
      · 剪映里 `clip.scale = 1.0` 表示 **contain（等比缩放到完整装进画布）**。
        实测证据：1280x720 素材放进 1080x1920 画布、scale=1.0 时，剪映自己渲染出的
        草稿封面里画面带正好是 1080x608，上下各 656px 黑边；而 contain 的理论值
        是 1080x607.5。两者一致（±1px 取整）。
      · 因此：装进画布后的基准高度 = canvas_w * src_h / src_w（当素材比画布更宽时，
        以画布宽为基准；否则以画布高为基准）。
      · 想得到 band_h 高 → scale = band_h / 基准高度。

    注意 scale_x/scale_y 必须取同一个值，否则画面会变形。
    """
    src_ar = src_w / src_h
    canvas_ar = canvas_w / canvas_h
    if src_ar >= canvas_ar:          # 素材更宽 → 以画布宽为准
        base_h = canvas_w * src_h / src_w
    else:                            # 素材更高 → 以画布高为准
        base_h = float(canvas_h)
    return band_h / base_h


def _font_of(name, report: dict, sid):
    """把 EDL 里的字体名转成剪映字体对象。

    不指定时会落到剪映默认字体；指定的字体**必须在 pyJianYingDraft 的 `FontType`
    枚举里**（枚举是从剪映本体抽出来的）。注意枚举里既有免费也有 VIP 字体，
    这里会顺带把 `is_vip` 写进报告，避免误用 VIP 字体。
    """
    if not name:
        return None
    if not hasattr(d.FontType, name):
        msg = f"文本 {sid} 指定的字体 '{name}' 不在 FontType 枚举里，已回退默认字体"
        report["warnings"].append(msg)
        print(f"  [WARN] {msg}")
        return None
    font = getattr(d.FontType, name)
    report.setdefault("fonts", {}).setdefault(name, bool(font.value.is_vip))
    return font


def _clip_settings_of(item, report: dict, sid) -> "d.ClipSettings | None":
    """把 EDL 片段上的 `clip` 块转成剪映的图像调节设置。

    坐标系实测结论（与 pyJianYingDraft 文档互相印证）：
      transform_x / transform_y 的单位是**半个画布宽 / 半个画布高**，正方向为**上/左**。
      即  y_px = H/2 - (H/2) * transform_y  （y_px 从画面顶部算起）
      交叉验证：LS 画布 1920x1080 时 transform_y=-0.7407 → 940px、-0.79 → 966.6px；
                VT 画布 1080x1920 时 transform_y=+0.6875 → 300px、-0.5104 → 1450px。
                两组四个数全部吻合。
    """
    c = item.get("clip") or {}
    if not c:
        return None
    scale = c.get("scale", 1.0)
    return d.ClipSettings(
        alpha=float(c.get("alpha", 1.0)),
        flip_horizontal=bool(c.get("flip_horizontal", False)),
        flip_vertical=bool(c.get("flip_vertical", False)),
        rotation=float(c.get("rotation", 0.0)),
        scale_x=float(c.get("scale_x", scale)),
        scale_y=float(c.get("scale_y", scale)),
        transform_x=float(c.get("transform_x", 0.0)),
        transform_y=float(c.get("transform_y", 0.0)),
    )


def _apply_video_advanced(seg, item, report: dict) -> None:
    """把 clip 的高级字段落到片段上。**必须在 add_segment 之前调用。**"""
    sid = item.get("id", "?")

    anim = item.get("animation") or {}
    for key, enum_cls in (("intro", d.IntroType), ("outro", d.OutroType), ("group", d.GroupAnimationType)):
        obj = _enum_of(enum_cls, anim.get(key), report, f"片段 {sid} 动画.{key}")
        if obj is None:
            continue
        dur = anim.get(f"{key}_duration")
        seg.add_animation(obj, duration=tsec(dur) if dur else None)

    flt = item.get("filter") or {}
    obj = _enum_of(d.FilterType, flt.get("type"), report, f"片段 {sid} 滤镜")
    if obj is not None:
        seg.add_filter(obj, intensity=float(flt.get("intensity", 100.0)))

    eff = item.get("effect") or {}
    if eff.get("type"):
        obj = (_enum_of(d.VideoSceneEffectType, eff["type"], report, f"片段 {sid} 特效")
               or _enum_of(d.VideoCharacterEffectType, eff["type"], report, f"片段 {sid} 角色特效"))
        if obj is not None:
            seg.add_effect(obj, params=eff.get("params"))

    mk = item.get("mask") or {}
    if mk.get("type"):
        obj = _enum_of(d.MaskType, mk["type"], report, f"片段 {sid} 蒙版")
        if obj is not None:
            seg.add_mask(obj, **{k: v for k, v in mk.items() if k != "type"})

    obj = _enum_of(d.MixModeType, item.get("mix_mode"), report, f"片段 {sid} 混合模式")
    if obj is not None:
        seg.set_mix_mode(obj)

    bf = item.get("background_filling")
    if bf:
        seg.add_background_filling(bf.get("type", "blur"),
                                   blur=float(bf.get("blur", 0.0625)),
                                   color=bf.get("color", "#00000000"))

    fd = item.get("fade")
    if fd:
        seg.add_fade(tsec(fd.get("in", 0)), tsec(fd.get("out", 0)))

    _keyframes(seg, item, report, f"片段 {sid}")


def _apply_audio_advanced(seg, item, report: dict) -> None:
    sid = item.get("id", "?")
    obj = _enum_of(d.AudioSceneEffectType, (item.get("effect") or {}).get("type"),
                   report, f"音频片段 {sid} 音效")
    if obj is not None:
        seg.add_effect(obj)
    fd = item.get("fade")
    if fd:
        seg.add_fade(tsec(fd.get("in", 0)), tsec(fd.get("out", 0)))
    _keyframes(seg, item, report, f"音频片段 {sid}")


def _apply_text_advanced(seg, item, report: dict) -> None:
    sid = item.get("id", "?")
    anim = item.get("animation") or {}
    for key, enum_cls in (("intro", d.TextIntro), ("outro", d.TextOutro), ("loop", d.TextLoopAnim)):
        obj = _enum_of(enum_cls, anim.get(key), report, f"文本 {sid} 动画.{key}")
        if obj is None:
            continue
        dur = anim.get(f"{key}_duration")
        seg.add_animation(obj, duration=tsec(dur) if dur else None)
    _keyframes(seg, item, report, f"文本 {sid}")



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
        # 干跑也要**如实**数出音频叠加与特效：否则汇总行里的「音效叠加 0 个」
        # 会让人以为音频层没生效（第 17 轮加了 audio_overlays 之后才暴露）。
        report["effects"] = sum(len(t.get("effects") or [])
                                for t in (edl.get("effect_tracks") or []))
        report["audio_overlays"] = len(edl.get("audio_overlays") or [])
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
        speed = float(item.get("speed", 1.0)) or 1.0
        kwargs: dict = {"volume": float(item.get("volume", 1.0))}
        if item.get("source_in") is not None:
            # ⚠️ 变速时**素材窗口 ≠ 时间线长度**：剪映里 target_duration = source_duration / speed，
            # 所以 source_duration = target_duration × speed。
            # （旧代码一律按 `duration` 取素材窗口，速度≠1 时会取错；
            #   这条只在 speed≠1 时才显形，所以长期没暴露。）
            #
            # ⚠️⚠️ **只传 source_timerange，绝不同时传 speed。**
            # 库在 `VideoSegment.__init__` 里是这么写的：
            #     if source_timerange is not None and speed is not None:
            #         target_timerange = Timerange(start, round(source_timerange.duration / speed))
            # 即**它会用 source/speed 反算并覆盖我给的 target 时长**；
            # 而 source 会被四舍五入到微秒，再除回去可能多出 1µs ——
            # 于是本段比 EDL 时长长 1µs，与下一段**重叠 1 微秒**，
            # `add_segment` 的重叠校验直接抛 SegmentOverlap（实测就是这么炸的：
            # `SegmentOverlap [start: 16406250, end: 18750000]`）。
            # 只传 source_timerange 时走的是另一分支：库自己 `speed = source/target`，
            # **target 保持我给的精确值**，相邻片段严丝合缝。
            kwargs["source_timerange"] = d.trange(tsec(item["source_in"]),
                                                  tsec(duration * speed))
        elif item.get("speed") is not None:
            # 没给 source_in 时只能直接给 speed（此时由库自己算素材窗口）
            kwargs["speed"] = speed

        if track_type_of.get(item["track"]) == "audio":
            seg = d.AudioSegment(src, d.trange(tsec(start), tsec(duration)), **kwargs)
            _apply_audio_advanced(seg, item, report)
        else:
            seg = d.VideoSegment(src, d.trange(tsec(start), tsec(duration)),
                                 clip_settings=_clip_settings_of(item, report, item.get("id", "?")),
                                 **kwargs)
            _apply_video_advanced(seg, item, report)

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

    # ---- 独立特效轨 ----
    # 注意：**片段特效会作用于整个片段**，所以 0.1–0.3s 的打击特效必须走独立特效轨，
    # 否则会把整段都加上特效。
    for et in edl.get("effect_tracks") or []:
        name = et.get("name") or "fx"
        script.append_track(d.TrackSpec(d.TrackType.effect, name))
        report.setdefault("effect_tracks", []).append(name)
        report["tracks"].append({"name": name, "type": "effect"})
        for e in et.get("effects") or []:
            obj = (_enum_of(d.VideoSceneEffectType, e.get("type"), report, f"特效轨 {name}")
                   or _enum_of(d.VideoCharacterEffectType, e.get("type"), report, f"特效轨 {name}"))
            if obj is None:
                continue
            script.add_effect(obj, d.trange(tsec(e["start"]), tsec(e["duration"])),
                              track_name=name, params=e.get("params"))
            report["effects"] = report.get("effects", 0) + 1

    # ---- 音效叠加 ----
    # 剪映音效库无法程序化引用（AudioSegment 只接受本地文件路径），
    # 因此音效需先用 ffmpeg 从原素材裁成文件（枪声/播报音都能这样取）。
    declared = {t["name"] for t in (edl.get("tracks") or [])}
    for ao in edl.get("audio_overlays") or []:
        name = ao.get("track") or "sfx"
        if name not in declared:
            script.append_track(d.TrackSpec(d.TrackType.audio, name))
            declared.add(name)
            report.setdefault("effect_tracks", []).append(name)
            report["tracks"].append({"name": name, "type": "audio"})
        src = resolve(ao["source"])
        if not os.path.exists(src):
            msg = f"音效文件不存在: {ao['source']}"
            report["warnings"].append(msg)
            print(f"  [WARN] {msg}")
            continue
        kwargs = {"volume": float(ao.get("volume", 1.0))}
        if ao.get("source_in") is not None:
            kwargs["source_timerange"] = d.trange(tsec(ao["source_in"]), tsec(ao["duration"]))
        seg = d.AudioSegment(src, d.trange(tsec(ao["start"]), tsec(ao["duration"])), **kwargs)
        if ao.get("fade"):
            seg.add_fade(tsec(ao["fade"].get("in", 0)), tsec(ao["fade"].get("out", 0)))
        script.add_segment(seg, name)
        report["audio_overlays"] = report.get("audio_overlays", 0) + 1

    for item in edl.get("texts") or []:
        style = item.get("style") or {}
        color = style.get("color")
        text_style = d.TextStyle(
            size=float(style.get("size", 8.0)),
            bold=bool(style.get("bold", False)),
            italic=bool(style.get("italic", False)),
            color=tuple(color) if color else (1.0, 1.0, 1.0),
            align=int(style.get("align", 0)),
            letter_spacing=int(style.get("letter_spacing", 0)),
            line_spacing=int(style.get("line_spacing", 0)),
        )
        clip = d.ClipSettings(
            transform_x=float(style.get("transform_x", 0.0)),
            transform_y=float(style.get("transform_y", 0.0)),
        )
        # 描边 / 阴影 / 背景：EDL 里给就带上（"高级感"很大一部分来自这三项）
        border = None
        if item.get("border"):
            b = item["border"]
            border = d.TextBorder(color=tuple(b.get("color", (0.0, 0.0, 0.0))),
                                  width=float(b.get("width", 40.0)))
        shadow = None
        if item.get("shadow"):
            s = item["shadow"]
            shadow = d.TextShadow(color=tuple(s.get("color", (0.0, 0.0, 0.0))),
                                  diffuse=float(s.get("diffuse", 15.0)),
                                  distance=float(s.get("distance", 5.0)),
                                  angle=float(s.get("angle", -45.0)))
        background = None
        if item.get("background"):
            g = item["background"]
            background = d.TextBackground(color=g.get("color", "#00000080"),
                                          style=int(g.get("style", 1)),
                                          round_radius=float(g.get("round_radius", 0.0)))

        seg = d.TextSegment(
            item["content"],
            d.trange(tsec(item["start"]), tsec(item["duration"])),
            font=_font_of(style.get("font"), report, item.get("id", "?")),
            style=text_style,
            clip_settings=clip,
            border=border,
            shadow=shadow,
            background=background,
        )
        # 文本动画与关键帧也必须在入轨前挂好（与转场同一机制：入轨时才登记素材）
        _apply_text_advanced(seg, item, report)
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
    print(f"     视频片段 {report['clips']} 个 | 文本 {report['texts']} 条"
          f" | 特效 {report.get('effects', 0)} 个 | 音效叠加 {report.get('audio_overlays', 0)} 个")
    print("     下一步：在剪映中打开该草稿，检查后手动导出（剪映 7+ 不支持自动导出）")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
