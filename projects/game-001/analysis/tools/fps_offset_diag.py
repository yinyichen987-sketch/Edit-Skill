"""诊断 fps_offset_check 的索引错位。

假设（由 creative-reviewer 提出，我认可其机制）：
    帧数组与 PTS 列表来自**不同解码路径**。若任一侧对 VFR 素材补了帧
    （b 780→781、c 750→751），则在丢帧点之后所有下标整体偏移 1，
    用 PTS 去查这个偏移过的下标就会系统性「晚一帧」，**且只在有丢帧的素材上发作**。

三条可自证检查（任一条不过即索引错位）：
    1. len(pts) 与 len(frames) 都等于容器帧数（pymediainfo.frame_count）570/780/750
    2. 匹配到的源帧号步长只能出现 7 和 8
    3. 偏差取值集合应是 2-4 个离散值；连续分布说明匹配退化
"""
from __future__ import annotations

import os
import subprocess
import sys

import imageio_ffmpeg

try:
    from pymediainfo import MediaInfo
except ImportError:
    MediaInfo = None

FF = imageio_ffmpeg.get_ffmpeg_exe()
SRC = {
    "a": "原始素材/4b0460c400bbb5320acb6063b4f59358.mp4",
    "b": "原始素材/6b2eea343eee7595c3c0ede10d21d028.mp4",
    "c": "原始素材/dcc871b1791e7796fadac842593f10f7.mp4",
}
W, H = 160, 90
SIZE = W * H * 3
TMP = "projects/game-001/analysis/raw/_diag"


def container_frame_count(path: str) -> int | None:
    if MediaInfo is None:
        return None
    mi = MediaInfo.parse(path)
    for t in mi.tracks:
        if t.track_type == "Video" and t.frame_count:
            return int(t.frame_count)
    return None


def decode_raw(path: str, vf: str, out: str) -> int:
    """解码到 raw 文件，返回帧数。"""
    if os.path.exists(out):
        os.remove(out)
    r = subprocess.run([FF, "-hide_banner", "-nostats", "-v", "error", "-y", "-i", path,
                        "-vf", vf, "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", out],
                       capture_output=True)
    if r.returncode != 0:
        print("   decode err:", r.stderr.decode("utf-8", "replace")[:200])
    return os.path.getsize(out) // SIZE if os.path.exists(out) else 0


def dump_pts(path: str, vf: str, meta: str) -> list[float]:
    if os.path.exists(meta):
        os.remove(meta)
    with open(meta, "wb") as fh:
        subprocess.run([FF, "-hide_banner", "-nostats", "-v", "info", "-y", "-i", path,
                        "-vf", f"{vf},showinfo", "-an", "-f", "null", os.devnull],
                       stdout=subprocess.DEVNULL, stderr=fh)
    out = []
    for line in open(meta, encoding="utf-8", errors="replace"):
        if "pts_time:" in line:
            try:
                out.append(float(line.split("pts_time:")[1].split()[0]))
            except (IndexError, ValueError):
                pass
    return out


def frames_of(raw: str) -> list[bytes]:
    data = open(raw, "rb").read()
    n = len(data) // SIZE
    return [data[i * SIZE:(i + 1) * SIZE] for i in range(n)]


def mad(a: bytes, b: bytes) -> float:
    return sum(abs(a[i] - b[i]) for i in range(len(a))) / len(a) if len(a) == len(b) else 1e9


def main() -> int:
    # Windows 默认控制台为 GBK，中文/符号（⊂ ✓ ✅ → 等）会在打印中途抛
    # UnicodeEncodeError 而退出；崩溃退出码可能与脚本自身的失败码相同，
    # 导致「崩溃」被误读为「检查未通过」。统一改为 UTF-8。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    os.makedirs(TMP, exist_ok=True)
    print("=" * 78)
    print("检查 1：帧数对账（raw 解码帧数 / PTS 列表长度 / 容器帧数）")
    print("=" * 78)
    print(f"{'素材':5}{'raw-gray帧数':>13}{'raw-rgb帧数':>13}{'PTS列表':>10}{'容器帧数':>10}  判定")
    recon = {}
    for k, src in SRC.items():
        n_gray = decode_raw(src, f"scale={W}:{H},format=gray", f"{TMP}/{k}.gray") if False else 0
        # gray 与 rgb 只是像素格式差异，帧数应相同；这里统一用 rgb 便于后续匹配
        n_rgb = decode_raw(src, f"scale={W}:{H}", f"{TMP}/{k}.rgb")
        pts = dump_pts(src, f"scale={W}:{H}", f"{TMP}/{k}.txt")
        cc = container_frame_count(src)
        ok = (n_rgb == len(pts)) and (cc is None or n_rgb == cc)
        recon[k] = {"raw_frames": n_rgb, "pts": len(pts), "container": cc}
        print(f"{k:5}{'-':>13}{n_rgb:>13}{len(pts):>10}{str(cc):>10}  "
              f"{'OK' if ok else '!! 不一致'}")
    print()
    print("  说明：我原先的 fps_offset_check.py 用 min(len(frames), len(pts)) 截断。")
    print("        若一侧多 1 帧，截断本身就会造成**整段下标错位**，且只在补帧的素材上发作。")

    print()
    print("=" * 78)
    print("检查 2：匹配源帧号的步长分布（应只出现 7 / 8）")
    print("=" * 78)
    print("检查 3：偏差取值集合（应为 2-4 个离散值）")
    print("=" * 78)
    print(f"{'素材':5}{'样本':>6}{'步长分布':>22}{'偏差取值':>34}")
    detail = {}
    for k, src in SRC.items():
        n_rgb = recon[k]["raw_frames"]
        pts = dump_pts(src, f"scale={W}:{H}", f"{TMP}/{k}.txt")
        src_fr = frames_of(f"{TMP}/{k}.rgb")
        # 重采样帧
        n_rs = decode_raw(src, f"fps=4,scale={W}:{H}", f"{TMP}/{k}.fps4")
        rs = frames_of(f"{TMP}/{k}.fps4")

        n = min(len(src_fr), len(pts))
        idxs, offs = [], []
        for j, rf in enumerate(rs):
            nominal = j / 4.0
            lo = max(0, int(nominal * 30) - 16)
            hi = min(n, int(nominal * 30) + 16)
            best_i, best_v = None, 1e9
            for i in range(lo, hi):
                v = mad(rf, src_fr[i])
                if v < best_v:
                    best_v, best_i = v, i
            if best_i is None or best_v > 0.5:
                continue
            idxs.append(best_i)
            offs.append(round(pts[best_i] - nominal, 4))

        steps = {}
        for i in range(1, len(idxs)):
            d = idxs[i] - idxs[i - 1]
            steps[d] = steps.get(d, 0) + 1
        vals = {}
        for o in offs:
            vals[o] = vals.get(o, 0) + 1
        detail[k] = {"steps": steps, "offsets": vals,
                     "mean": round(sum(offs) / len(offs), 4) if offs else None}
        bad_steps = {d: c for d, c in steps.items() if d not in (7, 8)}
        print(f"{k:5}{len(offs):>6}{str(steps):>22}   取值 {sorted(vals)[:6]}")
        if bad_steps:
            print(f"      !! 出现非 7/8 步长：{bad_steps}  → 索引错位")
        if len(vals) > 4:
            print(f"      !! 偏差取值 {len(vals)} 个（>4）→ 匹配退化")

    print()
    print("=" * 78)
    print("均值对比")
    print("=" * 78)
    for k in SRC:
        m = detail[k]["mean"]
        print(f"   {k}: 我的新均值 {m}")

    import json
    json.dump({"recon": recon, "detail": detail},
              open("projects/game-001/analysis/raw/fps_offset_diag.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n[OK] projects/game-001/analysis/raw/fps_offset_diag.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
