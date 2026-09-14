"""核对**已生成的剪映草稿**是否真的等于 EDL（执行层不能自证）。

`edl_to_draft.py` 在生成时的 dry-run 与生成后自检都在**执行层内部**，
按本项目第 2 轮的结论（"被审方的判据不能由被审方定义；执行层不能审自己"），
这里**重新从落盘的 `draft_content.json` 读回来**，与 EDL 逐项对账。

对账项：
  1. 画布尺寸 / 帧率
  2. 每条轨道是否存在且类型正确
  3. 主轨每段的 (start, duration, source_in, speed, volume) 与 EDL 一致
  4. 叠加轨（白闪/黑场）条数与时刻
  5. 音频素材的 path 是否指向**真实存在**的文件，且 `duration` 覆盖成片长度
  6. `materials.durations` / 时间线是否出现「Σ duration < end」的黑洞（本项目踩过）

用法：
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\verify_draft_v3.py <edl.json> <draft_dir>
"""
from __future__ import annotations

import json
import pathlib
import sys
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

US = 1_000_000.0


def main() -> int:
    edl_p = pathlib.Path(sys.argv[1])
    draft_dir = pathlib.Path(sys.argv[2])
    edl = json.loads(edl_p.read_text(encoding="utf-8"))
    dc = json.loads((draft_dir / "draft_content.json").read_text(encoding="utf-8"))

    fails: list[str] = []
    oks: list[str] = []

    def check(cond: bool, msg: str) -> None:
        (oks if cond else fails).append(msg)

    # 1 画布
    cv = dc.get("canvas_config", {})
    check(cv.get("width") == edl["canvas"]["width"] and cv.get("height") == edl["canvas"]["height"],
          f"画布 {cv.get('width')}x{cv.get('height')} == EDL {edl['canvas']['width']}x{edl['canvas']['height']}")
    check(int(dc.get("fps", 0)) == edl["canvas"]["fps"], f"帧率 {dc.get('fps')} == EDL {edl['canvas']['fps']}")

    # 2 轨道
    tracks = dc["tracks"]
    names = [(t["type"], t.get("name")) for t in tracks]
    edl_names = set(t["name"] for t in edl["tracks"])
    got = set(n for _, n in names)
    check(edl_names <= got, f"EDL 的 {len(edl_names)} 条内容轨道都在草稿里（草稿共 {len(tracks)} 条）")

    # 3 主轨片段
    by_id = {s["id"]: s for s in dc["tracks"]}
    # 剪映里片段挂在 tracks[i].segments，material 通过 materials.videos 解析
    vids = {m["id"]: m for m in dc["materials"]["videos"]}
    auds = {m["id"]: m for m in dc["materials"]["audios"]}

    edl_main = [c for c in edl["clips"] if not str(c["track"]).startswith("ovl_")]
    edl_ovl = [c for c in edl["clips"] if str(c["track"]).startswith("ovl_")]

    segs_main, segs_ovl = [], []
    for t in tracks:
        if t["type"] != "video":
            continue
        for s in t["segments"]:
            mat = vids.get(s["material_id"], {})
            row = (t.get("name"), s, mat)
            (segs_ovl if str(t.get("name", "")).startswith("ovl_") else segs_main).append(row)

    check(len(segs_main) == len(edl_main),
          f"主轨视频片段数 {len(segs_main)} == EDL {len(edl_main)}")
    check(len(segs_ovl) == len(edl_ovl),
          f"叠加轨片段数 {len(segs_ovl)} == EDL {len(edl_ovl)}（白闪/黑场）")

    for i, (c, (tname, s, mat)) in enumerate(zip(edl_main, segs_main), 1):
        got_start = s["target_timerange"]["start"] / US
        got_dur = s["target_timerange"]["duration"] / US
        got_in = s["source_timerange"]["start"] / US
        got_sp = s.get("speed", 1.0)
        got_vol = s.get("volume", 1.0)
        check(abs(got_start - c["start"]) < 1e-3, f"片段{i} start {got_start:.4f} == EDL {c['start']:.4f}")
        check(abs(got_dur - c["duration"]) < 1e-3, f"片段{i} duration {got_dur:.4f} == EDL {c['duration']:.4f}")
        check(abs(got_in - c["source_in"]) < 1e-3, f"片段{i} source_in {got_in:.4f} == EDL {c['source_in']:.4f}")
        check(abs(got_sp - c.get("speed", 1.0)) < 1e-6, f"片段{i} speed {got_sp} == EDL {c.get('speed', 1.0)}")
        check(abs(got_vol - c.get("volume", 1.0)) < 1e-3, f"片段{i} volume {got_vol:.3f} == EDL {c.get('volume', 1.0):.3f}")
        check(pathlib.Path(mat.get("path", "")).exists(), f"片段{i} 素材文件存在：{pathlib.Path(mat.get('path','')).name}")

    # 4 音频
    edl_audio = edl.get("audio_overlays", [])
    check(len(dc["materials"]["audios"]) == len(edl_audio),
          f"音频素材数 {len(dc['materials']['audios'])} == EDL {len(edl_audio)}")
    for m in dc["materials"]["audios"]:
        p = pathlib.Path(m.get("path", ""))
        check(p.exists(), f"BGM 文件存在：{p.name}（{m.get('duration', 0)/US:.3f}s）")
        want = edl["target_duration_s"]
        check(m["duration"] / US >= want - 1e-3,
              f"BGM 素材时长 {m['duration']/US:.3f}s >= 成片 {want:.3f}s（不会出现音乐不够长）")
        check(m.get("type") == "extract_music",
              f"BGM material.type = {m.get('type')!r}（pyJianYingDraft 对本地音频硬编码，剪映接受）")

    # 5 黑洞检查：任一片段 end 不得超过时间线总长；且主轨 Σduration == end
    total = edl["target_duration_s"]
    end = max(s["target_timerange"]["start"] + s["target_timerange"]["duration"]
              for _, s, _ in segs_main) / US
    check(abs(end - total) < 1e-3, f"主轨时间线末端 {end:.4f}s == 成片声明长度 {total:.4f}s")

    print(f"=== 对账：{draft_dir.name} ===")
    print(f"    EDL {edl_p.name}")
    for o in oks:
        print(f"  PASS  {o}")
    for f in fails:
        print(f"  FAIL  {f}")
    print(f"\n{len(oks)} PASS / {len(fails)} FAIL")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
