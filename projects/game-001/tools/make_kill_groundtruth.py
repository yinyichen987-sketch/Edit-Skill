"""生成 / 校验「击杀帧」的 ground truth（`kills_groundtruth.json`）。

## 本轮的结论（与第 4–6 轮的旧判据对照）

`tools/detect_kills.py` 的判据（底部特效带 ∩ 右上播报，legacy 标定）在**这条素材上失效**：

| 它信号给的东西 | 逐帧实测看到的 |
|---|---|
| 「底部击杀特效」带 `crop=1280:120:0:600` | 装的是**武器皮肤检视动画**与技能图标，不是击杀横幅 |
| 10 个候选「击杀」 | 只有 1 个（6.53s）在顶部真的出现了**洋红击杀横幅**（占比 0.82） |

换了两条不依赖底部带的路（都逐帧实测，可复现）：

1. **顶部 HUD 帧间差**（`y10..80`）：命中 11 个突变帧，覆盖 9/10 个旧候选，**多报 2 个**
   （479 = 15.967s、757 = 25.233s）。
2. **双方头像条饱和度骤降**（`track_portraits.py`，8 个头像逐帧）：框住 11 个突变里的大多数，
   最大落差 **−22 ~ −113**（6.733s / 14.267s / 25.5s 最大）。

### 为什么「帧」只能给到「候选帧」

这条素材是**观战/直播 HUD 的录屏**：顶部计分板的回合计时是**跳变更新**的（实测 6.533s 时从
1:25 直接跳到 1:24；15.967s 处从 1:15 跳到 1:09），不是逐帧计时。
于是「HUD 相对上一帧的突变帧」与「真实击杀帧」之间**无法从画面本身证明是同一帧**。
本项目反复被「信号自证不算验证」咬过（`docs/lessons.md` 第 4 轮、第 6 轮），
所以这里**如实标注**：`kill_frame_candidate` 是候选帧，`anchor` 说明它是怎么来的。

## 用法

    .venv\\Scripts\\python.exe projects/game-001/tools/make_kill_groundtruth.py b61cc53d
    .venv\\Scripts\\python.exe projects/game-001/tools/make_kill_groundtruth.py b61cc53d --check

输出：projects/game-001/analysis2/kills_groundtruth.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

import imageio_ffmpeg
import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = ROOT / "原始素材"
OUT = ROOT / "projects" / "game-001" / "analysis2" / "kills_groundtruth.json"
OLD = ROOT / "projects" / "game-001" / "analysis2" / "kills_mine.json"

W, H = 1280, 720
FPS = 30.0
HUD_BAND = (0, 10, W, 80)          # 顶部 HUD（含计分板与击杀横幅）
BANNER_BAND = (420, 35, 860, 75)   # 洋红横幅带（实测 6.53s 时占比 0.82）
DIFF_SIGMA = 3.0                   # 帧间差突变门限
MAGENTA_MARGIN = 30
MAGENTA_MIN_RB = 70


def _decode(path: pathlib.Path) -> np.ndarray:
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    p = subprocess.run([ff, "-v", "error", "-i", str(path), "-f", "rawvideo",
                        "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
    return np.frombuffer(p.stdout, dtype=np.uint8).reshape(-1, H, W, 3)


def _runs(idx: list[int], max_gap: int = 3) -> list[list[int]]:
    out: list[list[int]] = []
    for i in idx:
        if out and i - out[-1][1] <= max_gap:
            out[-1][1] = i
        else:
            out.append([i, i])
    return out


def build(short: str) -> dict:
    src = next(SRC.glob(f"{short}*.mp4"))
    frames = _decode(src)
    n = frames.shape[0]
    x0, y0, x1, y1 = HUD_BAND
    hud = frames[:, y0:y1, x0:x1, :].astype(np.int16)
    d = np.abs(np.diff(hud, axis=0)).mean(axis=(1, 2, 3))
    thr = float(d.mean() + DIFF_SIGMA * d.std())

    x0, y0, x1, y1 = BANNER_BAND
    band = frames[:, y0:y1, x0:x1, :].astype(np.int16)
    r, g, b = band[..., 0], band[..., 1], band[..., 2]
    mb = np.minimum(r, b)
    mag = ((mb - g > MAGENTA_MARGIN) & (mb > MAGENTA_MIN_RB)).mean(axis=(1, 2))
    banner_runs = _runs([i for i in range(n) if mag[i] > 0.10], max_gap=4)

    # 突变帧（取区间内差值最大的那一帧）
    bursts: list[int] = []
    for rr in _runs([i for i in range(len(d)) if d[i] > thr], max_gap=3):
        local = d[rr[0]:rr[1] + 1]
        bursts.append(rr[0] + int(np.argmax(local)))
    # 合并 6 帧内的重复突变（同一次画面变化）
    merged: list[int] = []
    for bfl in bursts:
        if merged and bfl - merged[-1] <= 6:
            continue
        merged.append(bfl)

    old = json.loads(OLD.read_text(encoding="utf-8")).get(short, {}).get("mine", [])
    events = []
    for i, bfl in enumerate(merged, 1):
        near = None
        if banner_runs:
            near = min(banner_runs, key=lambda rr: abs(0.5 * (rr[0] + rr[1]) - bfl))
        magenta_hit = bool(near and near[0] - 20 <= bfl <= near[1] + 20
                           and mag[near[0]:near[1] + 1].max() > 0.10)
        old_hit = [t for t in old if abs(t - bfl / FPS) < 0.35]
        # ⚠️ 2026-09-14 修正：洋红**不是**击杀横幅。
        # 本轮联网+本机交叉核对（子 agent 独立抽帧，见 research/kill-frame-criteria-web.md）：
        #   ① 本素材 6.53~7.4s 的整屏洋红是**技能/特效**，不是横幅；
        #   ② 仓库原先记的「底部击杀横幅 y522~613」实为**准星命中标记**。
        # 所以「出现洋红」不能把置信度抬到 high —— 全部候选都只有 HUD 突变这一条间接证据。
        confidence = "medium"
        events.append({
            "n": i,
            "kill_frame_candidate": bfl,
            "kill_time_candidate_s": round(bfl / FPS, 4),
            "anchor": "HUD 帧间差突变帧（顶部 y10..80，3σ）",
            "anchor_prev_frame": bfl - 1,
            "anchor_delta": round(float(d[bfl - 1]) if bfl >= 1 else 0.0, 2),
            "confidence": confidence,
            "magenta_fullscreen_effect_frames": near if magenta_hit else None,
            "magenta_ratio_at_burst": round(float(mag[bfl]), 5),
            "magenta_ratio_peak_near": (round(float(mag[near[0]:near[1] + 1].max()), 5)
                                        if magenta_hit else round(float(mag[bfl]), 5)),
            "magenta_is_kill_banner": False,
            "old_detect_kills_mine_s": old_hit,
            "old_detect_matched": bool(old_hit),
        })

    matched = {round(t, 3) for e in events for t in e["old_detect_kills_mine_s"]}
    false_positive_s = [t for t in old if round(t, 3) not in matched]
    missed_s = [round(e["kill_time_candidate_s"], 3) for e in events if not e["old_detect_matched"]]

    return {
        "source": src.name,
        "fps": FPS,
        "n_frames": n,
        "duration_s": round(n / FPS, 4),
        "generated_by": "projects/game-001/tools/make_kill_groundtruth.py",
        "method": {
            "hud_band": HUD_BAND,
            "banner_band": BANNER_BAND,
            "diff_threshold": thr,
            "burst_frames_raw": bursts,
            "burst_frames_merged": merged,
            "banner_runs": banner_runs,
        },
        "caveats": [
            "本素材是**观战/直播 HUD 录屏**：顶部回合计时是跳变更新（实测 6.533s 从 1:25 跳 1:24、"
            "15.967s 从 1:15 跳 1:09），因此 HUD 突变帧与真实击杀帧之间无法从画面本身证明同帧。",
            "候选取自「HUD 帧间差 3σ 突变帧」，全部 confidence=medium —— **没有任何一个候选"
            "拿到了正面证据**。",
            "★ 洋红不是击杀横幅：2026-09-14 联网+本机交叉核对（research/kill-frame-criteria-web.md）"
            "确认本素材 6.53~7.4s 的整屏洋红是技能/特效；仓库原先记的「底部击杀横幅 y522~613」"
            "实为**准星命中标记**。因此洋红信号只用于定位特效，不用于判定击杀。",
            "旧判据 detect_kills.py（底部带∩右上播报，legacy 标定）在本素材上失效："
            "底部带装的是武器皮肤检视动画/技能图标，不是击杀横幅。",
            "洋红特效实测区间 [[197,204],[216,220]]，峰值占比 0.808（帧 198）。",
        ],
        "comparison_with_old_detector": {
            "old_candidates_s": old,
            "old_false_positives_s": false_positive_s,
            "new_events_not_in_old_s": missed_s,
        },
        "events": events,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("short")
    ap.add_argument("--check", action="store_true", help="只校验已有 groundtruth 与当前信号是否一致")
    a = ap.parse_args()

    data = build(a.short)
    if a.check and OUT.exists():
        prev = json.loads(OUT.read_text(encoding="utf-8"))
        pk = [e["kill_frame_candidate"] for e in prev.get("events", [])]
        nk = [e["kill_frame_candidate"] for e in data["events"]]
        same = pk == nk
        print(f"{'[OK]' if same else '[FAIL]'} 已有 groundtruth 候选帧 {pk}")
        print(f"{'[OK]' if same else '[FAIL]'} 当前信号候选帧   {nk}")
        if not same:
            return 1
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"=== 击杀帧 ground truth 候选 · {data['source']} ===")
    print(f"帧间差门限 {data['method']['diff_threshold']:.2f}（3σ）  "
          f"突变区间 {len(data['method']['burst_frames_raw'])} → 合并后 {len(data['events'])}")
    print(f"洋红横幅区间 {data['method']['banner_runs']}")
    cmp_ = data["comparison_with_old_detector"]
    print(f"旧判据候选 {len(cmp_['old_candidates_s'])} 个 → 未被新锚点匹配上的（疑似误报）: "
          f"{cmp_['old_false_positives_s'] or '无'}")
    print(f"新锚点里旧判据没有的（疑似漏报）: {cmp_['new_events_not_in_old_s'] or '无'}")
    print(f"\n{'#':>3} {'候选帧':>7} {'秒':>9} {'锚点Δ':>7} {'洋红峰值':>9} {'置信':>6} {'旧判据命中':>10}")
    for e in data["events"]:
        print(f"{e['n']:3} {e['kill_frame_candidate']:7} {e['kill_time_candidate_s']:9.4f} "
              f"{e['anchor_delta']:7.2f} {e['magenta_ratio_peak_near']:9.5f} "
              f"{e['confidence']:>6} "
              f"{('是 ' + ','.join(f'{t:.3f}' for t in e['old_detect_kills_mine_s'])) if e['old_detect_matched'] else '否':>10}")
    print(f"\n[OK] {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
