"""测量「击杀 → 切点」的关系：参考成片到底怎么处理击杀帧。

## 为什么需要它

`tools/detect_kills.py` 只回答前半句：**哪一帧是击杀**。
它不回答后半句：**剪辑师在击杀前后怎么切** —— 而这才是"模板"的核心。

本工具把两者接起来：

    击杀时刻  ×  镜头切点  →  每个击杀的「切点上下文」

具体产出（每个击杀一行）：

| 指标 | 含义 |
|---|---|
| `d_prev` | 击杀距**上一个切点**多久（= 这个击杀镜头已经播了多久） |
| `d_next` | 击杀距**下一个切点**多久（= 击杀后画面还停留多久） |
| `offset_in_shot` | 击杀在所属镜头内的相对位置（0=刚切进来，1=镜头末尾） |
| `freeze_near` | 击杀 ±0.5s 内是否有**定格**（连续重复帧） |

## 区域标定怎么来的

基线是 720p 玩家视角（`detect_kills.py` 实际验证过的值），本工具按**画面比例**换算，
所以 1080p 素材不用重新标定：

| 区域 | 720p | 比例 |
|---|---|---|
| 底部击杀特效 | `crop=1280:120:0:600` | x0=0, y0=0.8333, w=1.0, h=0.1667 |
| 右上角播报 | `crop=320:58:950:18` | x0=0.7422, y0=0.025, w=0.25, h=0.0806 |

> ⚠️ **但参考成片不一定能用**：本轮实测发现高水平剪辑常用**观战/回放视角**，
> 或者干脆把 HUD **裁掉/盖住**（竖屏版尤其如此）。这时右上角是选手名牌、不是击杀播报，
> 底部被设计好的边框盖住 —— 默认标定会失效。
> 所以本工具会打印每个区域的**信号强度**，并给出 `hud_suspect` 提示，而不是硬报一个数字。

## 用法

    .venv\\Scripts\\python.exe tools/measure_kill_edit.py <视频> [--shots <json>]
    .venv\\Scripts\\python.exe tools/measure_kill_edit.py <视频> --json out.json
    .venv\\Scripts\\python.exe tools/measure_kill_edit.py --dir 参考视频

`--shots` 传 `analyze_film.py` 产出的 json（里面有镜头切点）；不传就只报击杀与定格。

## 定格检测的局限（**目前不够硬**）

本工具用「相邻帧灰度均差 < 0.05」找静止段。这条判据**分不清两件事**：

- 剪辑师**插入的定格**（真·keyframe 处理）
- 玩家**站着架枪不动**（游戏本身画面静止）

第一版用 64x36 网格 + 阈值 0.35，在一条 29.6s 的成片上报出 **36 个静止段** —— 显然是后者。
现在收紧到 320x180 + 0.05，但**根本问题没解决**：要真正区分，得看
「静止段里有没有游戏本该有的细微动效」（准星呼吸、UI 计时、场景粒子），
或者干脆逐帧目视。**在修好之前，`freeze` 一列只能当线索，不能当结论。**
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

import numpy as np

try:
    import imageio_ffmpeg
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (ImportError, AttributeError, ValueError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[1]

# 720p 基线 → 比例（见模块 docstring 的标定来源）
REGIONS = {
    "bottom":   (0.0000, 0.8333, 1.0000, 0.1667),
    "topright": (0.7422, 0.0250, 0.2500, 0.0806),
}
SIGMA = 2.5          # 上升沿阈值：均值 + SIGMA×标准差
MIN_GAP = 0.55       # 同类沿之间的最小间隔（秒）
MERGE = 0.40         # 合并过近的沿
CO_WINDOW = 0.80     # 底部 ∩ 右上 的共现窗口（秒）
FREEZE_EPS = 0.05    # 相邻帧灰度均差小于它 → 视为同一帧（定格）
FREEZE_MIN = 3       # 连续多少帧才算定格
NEAR_WINDOW = 0.50   # "击杀附近"的窗口（秒）
FREEZE_GRID = (320, 180)   # 定格检测的采样网格
# ⚠️ 局限：见 docstring「定格检测的局限」。这个判据分不清
#    「剪辑师插了定格」和「玩家站着不动」，所以输出里叫「静止段」而不是「定格」。


def _probe(path: pathlib.Path) -> dict:
    from pymediainfo import MediaInfo
    for t in MediaInfo.parse(str(path)).tracks:
        if t.track_type == "Video":
            return {"w": t.width, "h": t.height,
                    "dur": (t.duration or 0) / 1000.0,
                    "fps": float(t.frame_rate) if t.frame_rate else 30.0}
    return {}


def _gray_series(path: pathlib.Path, crop: str, gw: int, gh: int) -> np.ndarray:
    """按区域取逐帧灰度均值。gw/gh 是缩放后的采样网格（只要相对变化，不求分辨率）。"""
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    p = subprocess.run(
        [ff, "-hide_banner", "-loglevel", "error", "-i", str(path),
         "-vf", f"{crop},scale={gw}:{gh},format=gray", "-f", "rawvideo", "-"],
        capture_output=True)
    a = np.frombuffer(p.stdout, dtype=np.uint8)
    n = len(a) // (gw * gh)
    if n < 3:
        return np.zeros(0)
    return a[:n * gw * gh].reshape(n, gh, gw).mean(axis=(1, 2)).astype(np.float64)


def _crop_str(path_w: int, path_h: int, frac: tuple[float, float, float, float]) -> str:
    x0, y0, w, h = frac
    # 取偶数，避免 yuv420 采样报错
    x = int(round(path_w * x0 / 2) * 2)
    y = int(round(path_h * y0 / 2) * 2)
    cw = int(round(path_w * w / 2) * 2)
    ch = int(round(path_h * h / 2) * 2)
    return f"crop={cw}:{ch}:{x}:{y}"


def rising_edges(sig: np.ndarray, fps: float) -> list[float]:
    if sig.size < 3:
        return []
    d = np.diff(sig)
    thr = d.mean() + SIGMA * d.std()
    idx = sorted((int(i) for i in np.where(d > thr)[0]), key=lambda i: -d[i])
    picked: list[int] = []
    for i in idx:
        if all(abs(i - j) / fps >= MIN_GAP for j in picked):
            picked.append(i)
    picked.sort()
    merged: list[float] = []
    for i in picked:
        t = round(i / fps, 3)
        if not merged or t - merged[-1] > MERGE:
            merged.append(t)
    return merged


def freeze_runs(sig: np.ndarray, fps: float) -> list[tuple[float, float]]:
    """连续近似相同的帧 → 定格段（起, 止）。"""
    if sig.size < FREEZE_MIN:
        return []
    d = np.abs(np.diff(sig))
    runs: list[tuple[float, float]] = []
    start = None
    for i, v in enumerate(d):
        if v < FREEZE_EPS:
            if start is None:
                start = i
        else:
            if start is not None and (i - start) >= FREEZE_MIN:
                runs.append((round(start / fps, 3), round(i / fps, 3)))
            start = None
    if start is not None and (len(d) - start) >= FREEZE_MIN:
        runs.append((round(start / fps, 3), round(len(d) / fps, 3)))
    return runs


def load_cuts(shots_json: pathlib.Path) -> tuple[list[float], list[dict]]:
    d = json.loads(shots_json.read_text(encoding="utf-8"))
    shots = d.get("shots") or []
    return [s["start"] for s in shots], shots


def measure(path: pathlib.Path, shots_json: pathlib.Path | None,
            max_seconds: float | None, cut_guard: float = 0.25) -> dict:
    info = _probe(path)
    w, h = info.get("w", 0), info.get("h", 0)
    fps = info.get("fps") or 30.0
    if not w or not h:
        raise SystemExit(f"读不到视频信息: {path}")

    vf_in = ["-t", str(max_seconds)] if max_seconds else []
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    gw, gh = FREEZE_GRID
    p = subprocess.run(
        [ff, "-hide_banner", "-loglevel", "error", *vf_in, "-i", str(path),
         "-vf", f"scale={gw}:{gh},format=gray", "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, dtype=np.uint8)
    n = len(a) // (gw * gh)
    whole = a[:n * gw * gh].reshape(n, gh, gw).mean(axis=(1, 2)).astype(np.float64)

    bottom_sig = _gray_series(path, _crop_str(w, h, REGIONS["bottom"]), 128, 12)
    top_sig = _gray_series(path, _crop_str(w, h, REGIONS["topright"]), 128, 12)

    bo = rising_edges(bottom_sig, fps)
    tr = rising_edges(top_sig, fps)
    raw = [t for t in tr if any(abs(t - b) <= CO_WINDOW for b in bo)]
    freezes = freeze_runs(whole, fps)

    # 信号强度：区域灰度标准差。接近 0 = 这块区域是死画面（标定大概率失效）
    strength = {"bottom": round(float(bottom_sig.std()), 3) if bottom_sig.size else 0.0,
                "topright": round(float(top_sig.std()), 3) if top_sig.size else 0.0}

    cuts: list[float] = []
    shots: list[dict] = []
    if shots_json and shots_json.exists():
        cuts, shots = load_cuts(shots_json)

    # ★★ 关键修正：**硬切本身就会同时点亮两个区域**（整帧都变了），
    #    所以「底部 ∩ 右上」在**有切点的成片**上其实是个切点探测器，不是击杀探测器。
    #    在**未剪辑的原始素材**上它才成立（没有切点，共现只可能来自击杀）。
    #    这里把落在切点附近的候选剔除，并如实报告剔掉了多少。
    rejected: list[float] = []
    if cuts:
        kept = []
        for t in raw:
            nearest = min(abs(t - c) for c in cuts)
            (rejected if nearest < cut_guard else kept).append(t)
        kills = kept
    else:
        kills = raw

    rows = []
    for t in kills:
        prev_cut = max([c for c in cuts if c <= t], default=None)
        next_cut = min([c for c in cuts if c > t], default=None)
        shot = None
        for s in shots:
            if s["start"] <= t < s["end"]:
                shot = s
                break
        rows.append({
            "t": t,
            "d_prev": round(t - prev_cut, 3) if prev_cut is not None else None,
            "d_next": round(next_cut - t, 3) if next_cut is not None else None,
            "offset_in_shot": (round((t - shot["start"]) / shot["duration"], 3)
                               if shot and shot["duration"] else None),
            "shot_index": shot["index"] if shot else None,
            "freeze_near": [f for f in freezes if f[0] - 0.5 <= t <= f[1] + 0.5],
        })

    return {
        "file": path.name,
        "w": w, "h": h, "fps": round(fps, 3), "duration": round(info.get("dur", 0), 2),
        "region_strength": strength,
        "hud_suspect": bool(strength["topright"] < 1.0 or strength["bottom"] < 1.0),
        "cut_guard": cut_guard,
        "n_bottom": len(bo), "n_topright": len(tr),
        "n_raw": len(raw), "n_rejected_at_cuts": len(rejected),
        "rejected": rejected,
        "n_kills": len(kills),
        "kills": rows,
        "freezes": freezes,
        "cuts": cuts,
    }


def summarize(r: dict) -> None:
    print(f"\n=== {r['file']}  {r['w']}x{r['h']} {r['fps']}fps {r['duration']}s ===")
    s = r["region_strength"]
    flag = "  ⚠️ HUD 标定可疑（区域几乎是死画面）" if r["hud_suspect"] else ""
    print(f"  区域信号强度: 底部 {s['bottom']} · 右上 {s['topright']}{flag}")
    print(f"  沿: 底部 {r['n_bottom']} · 右上 {r['n_topright']} → 共现 {r['n_raw']} 个")
    if r.get("n_rejected_at_cuts"):
        print(f"  ⚠️ 其中 {r['n_rejected_at_cuts']} 个落在切点 ±{r.get('cut_guard')}s 内 → **判为切点，不是击杀**："
              + " ".join(f"{t:.2f}" for t in r["rejected"][:10]))
    print(f"  → 可用击杀 {r['n_kills']} 个" +
          ("（无切点信息，未做切点剔除）" if not r.get("cuts") else ""))
    if r["freezes"]:
        print(f"  静止段 {len(r['freezes'])} 个（⚠️ 分不清『剪辑定格』与『玩家站定』）: " +
              " ".join(f"[{a:.2f}~{b:.2f}]" for a, b in r["freezes"][:8]))
    if not r["kills"]:
        print("  （没有击杀可分析）")
        return
    print(f"  {'击杀时刻':>8} {'距上切':>7} {'距下切':>7} {'镜内位置':>8}  定格")
    for k in r["kills"][:25]:
        dp = f"{k['d_prev']:.2f}" if k["d_prev"] is not None else "  -"
        dn = f"{k['d_next']:.2f}" if k["d_next"] is not None else "  -"
        off = f"{k['offset_in_shot']:.2f}" if k["offset_in_shot"] is not None else "  -"
        fz = "有" if k["freeze_near"] else ""
        print(f"  {k['t']:8.2f} {dp:>7} {dn:>7} {off:>8}  {fz}")
    dns = [k["d_next"] for k in r["kills"] if k["d_next"] is not None]
    dps = [k["d_prev"] for k in r["kills"] if k["d_prev"] is not None]
    if dns:
        print(f"  → 击杀后停留: 中位 {np.median(dns):.2f}s · 最短 {min(dns):.2f} · 最长 {max(dns):.2f}")
    if dps:
        print(f"  → 击杀前已播: 中位 {np.median(dps):.2f}s")


def main() -> int:
    ap = argparse.ArgumentParser(description="测量击杀与切点的关系")
    ap.add_argument("video", nargs="?", help="视频路径")
    ap.add_argument("--dir", help="批量处理目录下的 mp4")
    ap.add_argument("--shots", help="analyze_film.py 产出的 json（含镜头切点）")
    ap.add_argument("--json", dest="json_out", help="把结果写到这个 json")
    ap.add_argument("--max-seconds", type=float, default=None, help="只分析前 N 秒")
    args = ap.parse_args()

    targets: list[pathlib.Path] = []
    if args.dir:
        targets = sorted(pathlib.Path(args.dir).glob("*.mp4"))
    elif args.video:
        targets = [pathlib.Path(args.video)]
    else:
        ap.print_help()
        return 2
    if not targets:
        print("[FAIL] 没有找到视频", file=sys.stderr)
        return 2

    shots_path = pathlib.Path(args.shots) if args.shots else None
    # ⚠️ 别静默忽略：--shots 指错文件时，之前会安静地输出一堆 "-"，看起来像"没有切点数据"，
    #    实际是路径写错了。这是本轮实际踩到的坑。
    if shots_path is not None and not shots_path.exists():
        print(f"[FAIL] --shots 指向的文件不存在: {shots_path}", file=sys.stderr)
        print("       提示：analyze_film.py 的输出文件名要和你传的一致。", file=sys.stderr)
        return 2
    results = []
    for t in targets:
        sp = shots_path
        if sp is None:
            cand = ROOT / "projects" / "game-001" / "ref-analysis" / f"ref-{t.stem}.json"
            sp = cand if cand.exists() else None
            print(f"[i] {t.name}: 自动匹配切点 {sp.name if sp else '（无，只报击杀/静止段）'}")
        try:
            r = measure(t, sp, args.max_seconds)
        except SystemExit as e:
            print(f"[skip] {t.name}: {e}", file=sys.stderr)
            continue
        results.append(r)
        summarize(r)

    if args.json_out:
        out = pathlib.Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n[OK] 已写出 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
