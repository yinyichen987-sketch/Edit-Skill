"""场景跳变检测器（附带阳性/阴性对照自测）。

用途
----
判定 VALORANT 原始素材里**哪些时间点存在真实的瞬时视点跳变**（画面内容在一帧内完全换位），
用于给剪辑决策提供"天然硬断点"候选，并检验"素材是连续长镜头"这类结论是否成立。

为什么不用 scdet / 固定阈值
---------------------------
`references/environment.md` 记录：ffmpeg `scdet` 以亮度差为主，等亮度换色会漏判。
本素材实测 d 的中位数高达 8.3–9.3（满量程 255），运动/枪口焰把基线撑得很高，
任何固定阈值都会把大量运动误判为切点（这正是 `analyze_film.py` 报出 34.6–43.2 cuts/min 的原因）。

判据（孤立跳变）
----------------
记 d[i] = mean|G[i+1] - G[i]|（G 为 8 倍降采样灰度帧）。一个**瞬时视点跳变**满足：

    d[i]      >= MAD_THR                          # 跳变幅度足够大
    max(d[i-1], d[i-2]) < PRE_RATIO  * d[i]       # 之前是静止/连续的
    max(d[i+1], d[i+2]) < POST_RATIO * d[i]       # 之后是静止/连续的

含义：跳变**孤立**——宽约一帧、两侧都没有同等幅度的变化。
枪口焰/特效/快速转视角会让**邻帧同样剧烈变化**，因此被排除。

帧序必须精确（重要）
--------------------
解码一律走 `-fps_mode passthrough`。**默认解码会对 VFR 素材补帧**以凑成恒定帧率：

| 素材 | frame_rate_mode | MediaInfo frame_count | 默认解码 | passthrough |
|---|---|---|---|---|
| 4b0460c4 | CFR | 570 | 570 ✓ | 570 ✓ |
| 6b2eea34 | **VFR** | 780 | **781 ✗** | 780 ✓ |
| dcc871b1 | **VFR** | 750 | **751 ✗** | 750 ✓ |

补进来的那一帧插在文件中段，会让**其后的所有帧号整体偏移 1**，
于是"帧号 → 时间"的换算在偏移点之后全部差一帧。
`detect()` 因此会把解码帧数与 `pymediainfo` 的 `frame_count` 对账，不一致直接报错。

> 推论（踩过的坑）：不要拿其它工具的帧号来给本结果做像素取证。
> `ffmpeg -vf select='between(n,a,b)'` 的 `n` 与"解码序帧号"在 VFR 素材上可能整体差 1，
> 用它对账会得到与前一张完全矛盾的图。**取证图必须来自与检测同一次解码。**

已知局限（必须如实对待）
------------------------
1. **本判据给出的是下界，不是全集。** 它只抓"孤立跳变"；
   发生在高速运动中的硬切，其邻帧本身也在剧烈变化，会被漏掉。
2. 纯色帧（std=0）会让"去均值相关系数"变成 0/0。本脚本的主判据**不使用相关系数**，
   只用绝对差值，因此对纯色夹具同样有效——这正是第一版检测器在对照上 0 命中后修正的点。
3. 只做视觉判断，不做语义判断：不区分"编辑意义的镜头切换"与"观战镜头跳转/死亡回放/回合切换"。

自带对照自测（--selftest）
--------------------------
- 阳性对照 `spike/media/test_film.mp4`：已知 2 处硬切（2.967s / 4.967s），阈值 3.0 时应命中 2 处，
  **且每处宽度必须为 1**（单帧完成）。
- 阴性对照 `spike/media/test_a.mp4`：连续动画、无切点，阈值 3.0 时应 0 误报。
- 两个对照都断言**解码帧数 == MediaInfo frame_count**（抓"默认解码补帧"这类问题）。

自测同时断言**命中数**和**宽度**。只断言命中数是不够的——本脚本第一版宽度阈值只用
`3*median`，在 `median = 0` 的纯色夹具上任何 `d > 0` 都算"仍在跳变"，宽度蔓延至 121 帧；
单看命中数仍是 2，bug 不会被发现。补上宽度断言后，该 bug 会被判 FAIL。

四次实际踩到的坑（都在本文件里修掉，并由自测覆盖）：
1. 用去均值相关系数做判据 → 纯色帧 std=0，0/0，对照 0 命中。
2. 宽度阈值只用 `3*median` → `median=0` 时退化蔓延（实测 121 帧）。
3. 宽度循环先自增后校验 → 每处多计一帧。
4. 默认解码对 VFR 素材补帧 → 帧号中段起整体偏移 1，时间换算错一帧。

用法
----
    .venv/Scripts/python.exe detect_scene_cuts.py --selftest
    .venv/Scripts/python.exe detect_scene_cuts.py --out scene-cuts-result.json
"""
from __future__ import annotations

import argparse
import datetime as _dt
import glob
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

try:
    import imageio_ffmpeg
except ImportError:  # pragma: no cover
    print("[FAIL] 需要 imageio-ffmpeg（见 requirements.txt）", file=sys.stderr)
    raise

try:
    from pymediainfo import MediaInfo
except ImportError:  # pragma: no cover
    MediaInfo = None

# ---------------------------------------------------------------- 判据参数（默认值）

MAD_THR = 12.0     # 跳变幅度阈值（8 倍降采样灰度帧的平均绝对差，满量程 255）
PRE_RATIO = 0.2    # 前侧邻帧须小于该比例 × d[i]
POST_RATIO = 0.5   # 后侧邻帧须小于该比例 × d[i]
DOWNSAMPLE = 8     # 降采样倍数：每 8 像素取 1，画面变 160x90
WIDTH_FACTOR = 3.0 # 计算"跳变宽度"时，d > WIDTH_FACTOR × d_median 视为仍在跳变中

FPS = 30.0         # 容器帧率；仅用于把帧号折算成时间戳

# 关键：passthrough 保证解码帧序与容器帧序一一对应，不做 VFR→CFR 补帧
DECODE_PARAMS = ["-fps_mode", "passthrough"]

REPO_ROOT = Path(__file__).resolve().parents[4]


# ---------------------------------------------------------------- 解码

def gray_frames(path: str, step: int = DOWNSAMPLE) -> np.ndarray:
    """解码全部帧并降采样为灰度 float32 数组，形状 (N, H/step, W/step)。

    逐帧立即降采样，避免把整段 720p 全彩帧留在内存里。
    使用 passthrough 解码，确保帧序与容器一致（不做补帧）。
    """
    gen = imageio_ffmpeg.read_frames(path, pix_fmt="rgb24",
                                     output_params=list(DECODE_PARAMS))
    meta = next(gen)
    w, h = meta["size"]
    nbytes = w * h * 3
    frames = []
    for chunk in gen:
        arr = np.frombuffer(chunk[:nbytes], dtype=np.uint8).reshape(h, w, 3)
        frames.append(arr[::step, ::step].mean(axis=2).astype(np.float32))
    if not frames:
        raise RuntimeError(f"解码不到任何帧: {path}")
    return np.stack(frames)


def container_frame_count(path: str) -> int | None:
    """从容器读帧数（MediaInfo）。读不到返回 None。"""
    if MediaInfo is None:
        return None
    try:
        for t in MediaInfo.parse(path).tracks:
            if t.track_type == "Video" and getattr(t, "frame_count", None):
                return int(t.frame_count)
    except Exception:
        return None
    return None


def dump_pts(path: str) -> list[float]:
    """逐帧真实 pts_time（秒），顺序即解码序。

    为什么不能只用「帧号 ÷ 30」当时间：b、c 是 VFR，帧间隔不恒为 1/30，
    且有起始 PTS 偏移（0.016 / 0.013 / 0.005）。
    用名义帧号换算会**系统性偏早**（b 段实测偏早最多约 0.045s）。
    """
    import subprocess
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-nostats", "-i", path,
           "-vf", "showinfo", "-an", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    return [float(b) for _, b in
            re.findall(r"n:\s*(\d+)\s+pts:\s*-?\d+\s+pts_time:(-?[\d.]+)", r.stderr)]


# ---------------------------------------------------------------- 检测

def detect(path: str, mad_thr: float = MAD_THR,
           pre_ratio: float = PRE_RATIO, post_ratio: float = POST_RATIO,
           step: int = DOWNSAMPLE) -> dict:
    """返回该素材的检测结果 dict（含逐事件明细与帧数对账）。"""
    G = gray_frames(path, step)
    n = len(G)
    if n < 6:
        raise RuntimeError(f"帧数过少，无法检测: {path} ({n} 帧)")

    expected = container_frame_count(path)
    if expected is not None and expected != n:
        raise RuntimeError(
            f"解码帧数与容器不一致，帧号→时间换算不可信: {path} "
            f"解码={n} 容器={expected}（差 {n - expected}）。"
            f"检查是否漏了 -fps_mode passthrough。")

    d = np.array([np.abs(G[i + 1] - G[i]).mean() for i in range(n - 1)])
    med = float(np.median(d))

    # 真实 PTS：用于给出「不安全窗口」，而不是只报名义帧号
    try:
        pts = dump_pts(path)
        if len(pts) != n:
            pts = []
    except Exception:
        pts = []

    events = []
    for i in range(2, n - 3):
        if d[i] < mad_thr:
            continue
        prev_neighbor = float(max(d[i - 1], d[i - 2]))
        next_neighbor = float(max(d[i + 1], d[i + 2]))
        if prev_neighbor >= pre_ratio * d[i]:
            continue
        if next_neighbor >= post_ratio * d[i]:
            continue

        # 跳变宽度：包含 i 在内、连续处于"跳变中"的帧数。
        #
        # 阈值取三重下限的最大值，避免两个已踩过的退化情况：
        #   - 只用 WIDTH_FACTOR*med：med 可能为 0（纯色夹具），此时任何 d>0 都算"仍在跳变"，
        #     宽度会一路蔓延到整段。
        #   - 只用绝对下限：高运动素材里整段都在变化，宽度同样会蔓延。
        # 加入 0.25*d[i] 后，宽度只在"与本次跳变同量级"时延伸，语义为：
        # 宽度 1 = 单帧完成（硬切/瞬移）；宽度大 = 有渐变（溶解、淡入淡出、快速摇镜）。
        width_thr = max(WIDTH_FACTOR * med, 0.25 * d[i], 1.0)
        width = 1
        j = i - 1
        while j >= 1 and d[j] > width_thr:
            j -= 1
            width += 1
        j = i + 1
        while j <= n - 2 and d[j] > width_thr:
            j += 1
            width += 1

        events.append({
            "t_sec": round(i / FPS, 3),
            "frame_index": i,
            # 真实 PTS：不安全窗口 = 内容发生变化的那一对相邻帧的 PTS 区间。
            # 任何落在窗口内的切点都可能取到跳变帧；名义帧号换算只作参考。
            "t_pts_before_s": round(pts[i], 6) if pts else None,
            "t_pts_after_s": round(pts[i + 1], 6) if pts else None,
            "unsafe_window_s": [round(pts[i], 6), round(pts[i + 1], 6)] if pts else None,
            "window_width_ms": round((pts[i + 1] - pts[i]) * 1000, 1) if pts else None,
            "d": round(float(d[i]), 3),
            "prev_neighbor_max": round(prev_neighbor, 3),
            "next_neighbor_max": round(next_neighbor, 3),
            "ratio_prev": round(float(d[i]) / max(prev_neighbor, 1e-6), 2),
            "ratio_next": round(float(d[i]) / max(next_neighbor, 1e-6), 2),
            "width_frames": width,
            "instant": width <= 2,   # 宽 <= 2 帧 => 无渐变，不是溶解/淡入
        })

    return {
        "source": str(path),
        "frames": n,
        "container_frame_count": expected,
        "frame_count_ok": expected is None or expected == n,
        "d_median": round(med, 3),
        "d_max": round(float(d.max()), 3),
        "event_count": len(events),
        "events": events,
    }


# ---------------------------------------------------------------- 对照自测

CONTROLS = [
    # (路径, 阈值, 期望命中数, 期望每处宽度, 说明)
    # 期望宽度必须一起断言：只断言命中数时，"宽度计算退化蔓延至整段"这类 bug 不会被发现。
    # test_film 的两处硬切都是单帧完成（前侧纯色静止、后侧即刻恢复），宽度应为 1。
    ("spike/media/test_film.mp4", 3.0, 2, 1, "阳性对照：已知 2 处硬切，均为单帧完成"),
    ("spike/media/test_a.mp4",    3.0, 0, None, "阴性对照：连续动画、无切点"),
]


def selftest(repo_root: Path) -> tuple[bool, list[dict]]:
    """跑阳性/阴性对照，返回 (是否全部通过, 明细)。"""
    results = []
    ok = True
    for rel, thr, expect, expect_width, desc in CONTROLS:
        p = repo_root / rel
        if not p.exists():
            results.append({"control": rel, "desc": desc, "status": "SKIP",
                            "reason": "夹具不存在"})
            print(f"  [SKIP] {rel} 不存在")
            continue
        try:
            r = detect(str(p), mad_thr=thr)
        except Exception as exc:
            ok = False
            results.append({"control": rel, "desc": desc, "status": "FAIL",
                            "detail": f"检测抛异常: {exc}"})
            print(f"  [FAIL] {rel} 抛异常: {exc}")
            continue

        times = [e["t_sec"] for e in r["events"]]
        widths = [e["width_frames"] for e in r["events"]]

        count_ok = r["event_count"] == expect
        width_ok = (expect_width is None) or all(w == expect_width for w in widths)
        frames_ok = bool(r["frame_count_ok"])
        passed = count_ok and width_ok and frames_ok
        ok = ok and passed

        detail = []
        if not count_ok:
            detail.append(f"命中数 {r['event_count']} != 期望 {expect}")
        if not width_ok:
            detail.append(f"宽度 {widths} != 期望全为 {expect_width}")
        if not frames_ok:
            detail.append(f"解码帧数 {r['frames']} != 容器 {r['container_frame_count']}")
        results.append({
            "control": rel, "desc": desc, "mad_thr": thr,
            "expected_events": expect, "actual_events": r["event_count"],
            "event_times": times, "event_widths": widths,
            "expected_width": expect_width,
            "frames": r["frames"], "container_frame_count": r["container_frame_count"],
            "status": "PASS" if passed else "FAIL",
            "detail": "; ".join(detail) or None,
        })
        flag = "PASS" if passed else "FAIL"
        msg = (f"  [{flag}] {rel} 期望 {expect} 命中，实际 {r['event_count']}，"
               f"宽度={widths}，帧数 {r['frames']}/{r['container_frame_count']}")
        if detail:
            msg += "  <- " + "; ".join(detail)
        print(msg)
    return ok, results


# ---------------------------------------------------------------- main

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="场景跳变检测器（含对照自测）")
    ap.add_argument("--repo-root", default=str(REPO_ROOT))
    ap.add_argument("--clips", nargs="*", default=None,
                    help="待检测素材（默认 原始素材/*.mp4）")
    ap.add_argument("--out", default=None, help="结果 JSON 输出路径")
    ap.add_argument("--mad-thr", type=float, default=MAD_THR)
    ap.add_argument("--pre-ratio", type=float, default=PRE_RATIO)
    ap.add_argument("--post-ratio", type=float, default=POST_RATIO)
    ap.add_argument("--selftest", action="store_true", help="只跑对照自测")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()

    print("=" * 72)
    print("对照自测（验证检测器本身是否正常：补帧、纯色 0/0、宽度退化靠它暴露）")
    print("=" * 72)
    ctrl_ok, ctrl_results = selftest(repo_root)
    print(f"对照自测结果: {'全部通过' if ctrl_ok else '存在失败'}")

    if args.selftest:
        return 0 if ctrl_ok else 1

    clips = args.clips or sorted(glob.glob(str(repo_root / "原始素材" / "*.mp4")))
    print()
    print("=" * 72)
    print(f"检测素材（判据: d[i] >= {args.mad_thr}, "
          f"前邻 < {args.pre_ratio}*d[i], 后邻 < {args.post_ratio}*d[i]）")
    print("=" * 72)

    results = []
    total = 0
    for c in clips:
        r = detect(c, mad_thr=args.mad_thr,
                   pre_ratio=args.pre_ratio, post_ratio=args.post_ratio)
        results.append(r)
        total += r["event_count"]
        print(f"  {os.path.basename(c):42s} frames={r['frames']:4d}"
              f"/{r['container_frame_count']} d_median={r['d_median']:6.2f}"
              f" 跳变={r['event_count']}")
        for e in r["events"]:
            win = e.get("unsafe_window_s")
            wins = (f" 不安全窗口=[{win[0]:.4f}, {win[1]:.4f}] ({e['window_width_ms']}ms)"
                    if win else "")
            print(f"        frame={e['frame_index']:4d} 名义={e['t_sec']:7.3f}s "
                  f"d={e['d']:6.2f} 前={e['prev_neighbor_max']:5.2f} "
                  f"后={e['next_neighbor_max']:5.2f} "
                  f"ratio=({e['ratio_prev']},{e['ratio_next']}) "
                  f"width={e['width_frames']}{wins}")

    print()
    print(f"合计跳变 {total} 处 —— 这是【下界】，不是全集。")
    print("判据只抓孤立跳变；发生在高速运动中的硬切，邻帧同样剧烈变化，会被漏掉。")

    payload = {
        "generated_by": "detect_scene_cuts.py",
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "decode": {
            "output_params": DECODE_PARAMS,
            "note": ("必须 passthrough。默认解码会对 VFR 素材补帧（6b2eea34 780→781、"
                     "dcc871b1 750→751），补入帧插在文件中段，导致其后帧号整体偏移 1，"
                     "帧号→时间换算错一帧。"),
            "downsample": DOWNSAMPLE,
        },
        "criterion": {
            "d": "mean|G[i+1]-G[i]|，G 为 8 倍降采样灰度帧",
            "mad_thr": args.mad_thr,
            "pre_ratio": args.pre_ratio,
            "post_ratio": args.post_ratio,
            "downsample": DOWNSAMPLE,
            "width_factor": WIDTH_FACTOR,
            "fps_for_timestamps": FPS,
            "timestamps": ("每个事件同时给出 `t_sec`（名义帧号 ÷ 30，仅作参考）与 "
                           "`unsafe_window_s`（内容发生变化的那一对相邻帧的真实 PTS 区间）。"
                           "b、c 为 VFR 且有起始 PTS 偏移，**应以 unsafe_window_s 为准**；"
                           "名义帧号换算会系统性偏早（b 段实测最多约 0.045s）。"),
            "formula": ("d[i] >= mad_thr AND max(d[i-1],d[i-2]) < pre_ratio*d[i] "
                        "AND max(d[i+1],d[i+2]) < post_ratio*d[i]"),
            "width_thr": "max(width_factor*median(d), 0.25*d[i], 1.0)",
        },
        "self_test": {"all_passed": ctrl_ok, "controls": ctrl_results},
        "clips": results,
        "total_events": total,
        "result_kind": "lower_bound",
        "limitation": ("下界：只抓孤立跳变。运动中发生的硬切邻帧同样剧烈变化，会被漏判；"
                       "枪口焰/特效/快速转视角因邻帧同样变化而被正确排除。"
                       "本检测只判视觉跳变，不区分编辑镜头切换与观战跳转/死亡回放/回合切换。"),
    }

    if args.out:
        outp = Path(args.out)
        if not outp.is_absolute():
            outp = repo_root / outp
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        print(f"\n结果已写入: {outp}")

    return 0 if ctrl_ok else 1


if __name__ == "__main__":
    sys.exit(main())
