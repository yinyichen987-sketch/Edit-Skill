"""把「击杀帧 ground truth」落成一份**剪映标记草稿**：每个击杀帧处一条短标记。

## 为什么用文字片段当标记（而不是剪映的「标记」）

剪映**没有可自动生成的标记（marker）素材** —— 实测：`pyJianYingDraft` 0.3.0 里没有任何
marker 相关类，本项目既有的 `draft_content.json`（`projects/game-001/draft-out/`）里
grep 不到 `markers` / `marker_infos` 字段（见 `references/operations.md` §3）。

所以这里用**剪映里能做出来、且最接近「标记」的东西**：一条**短文字片段**，
压在击杀帧上、只显示几帧。它在剪映时间线上是一段可以选择/拖动/删除的独立素材，
落在画面里是一个带底色框的编号，打开草稿就能逐帧核对。

## 对齐规则（这一步决定了「标在哪一帧」）

本工具的锚点是 **HUD 帧间差突变帧 `b`**（见 `make_kill_groundtruth.py`）。
实测：突变发生在 **b**，而击杀横幅在 **b+1** 开始出现、**b+2** 达到峰值（6.533s 那一例：
帧 196 无横幅 / 197 = 15.6% / 198 = 80.8%洋红）。因此

    标记起点 = b - 1 帧（突变前一帧），时长 = 6 帧（0.2s）

这样标记**恰好罩住「横幅出现的那两帧」**，而不是慢一帧。

## 用法

    .venv\\Scripts\\python.exe projects/game-001/tools/make_killmark_draft.py b61cc53d
    .venv\\Scripts\\python.exe projects/game-001/tools/make_killmark_draft.py b61cc53d --dry-run

产出：
    projects/game-001/edl/killmark-<short>.json          可复核的 EDL（决策记录）
    projects/game-001/draft-out/<草稿名>/                明文剪映草稿母本
    projects/game-001/spec/killmark-<short>.json         标记台账（帧号 ↔ 标记序号）
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = ROOT / "原始素材"
GT = ROOT / "projects" / "game-001" / "analysis2" / "kills_groundtruth.json"
EDL_OUT = ROOT / "projects" / "game-001" / "edl"
DRAFT_ROOT = ROOT / "projects" / "game-001" / "draft-out"
LEDGER_OUT = ROOT / "projects" / "game-001" / "spec"
CONVERTER = ROOT / ".dsh" / "skills" / "jianying-edit" / "scripts" / "edl_to_draft.py"

W, H, FPS = 1280, 720, 30.0
LEAD_FRAMES = 1        # 标记比突变帧早 1 帧起（实测横幅在 b+1 出现）
SPAN_FRAMES = 6        # 标记持续 6 帧 = 0.2s
LABEL_Y0 = 0.63        # 第一个标记的 transform_y（下方）
LABEL_DY = 0.092       # 标记之间的纵向步进（约 33px @720）
LABEL_X = 0.30         # 标记的 transform_x（左移，避开顶部计分板与中部横幅）


def _load_converter():
    spec = importlib.util.spec_from_file_location("edl_to_draft", CONVERTER)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def t_of_frame(f: int) -> float:
    """帧号 → 秒。用 帧/30 精确表达，避免 30fps 下的浮点漂移。"""
    return f / FPS


def us_of_frame(f: int) -> int:
    """帧号 → 微秒（**四舍五入到微秒**，与 pyJianYingDraft 的写入口径一致）。

    30fps 下 1 帧 = 33333.33µs，**不是整数微秒**：F350 = 11666666.67µs。
    剪映/pyJianYingDraft 存的是整数微秒，所以草稿里必然是 11666700µs。
    如果让生成器算「理想值」、让写入端各自取整，就会出现 ±33µs 的系统性错位
    —— 本工具的独立校验器第一次跑就是这么报的 12 个问题。
    因此：**EDL 的秒值、台账、校验口径全部由这里的微秒整数反推**，只有一份真值。
    """
    return int(round(f * 1_000_000 / FPS))


def sec_of_frame(f: int) -> float:
    """帧号 → 秒，但**经过微秒整数**，与写进草稿的值逐位一致。"""
    return us_of_frame(f) / 1_000_000


def build_edl(short: str, gt: dict, src_name: str, draft_name: str) -> tuple[dict, list[dict]]:
    events = gt["events"]
    clips = [{
        "id": "main-1",
        "track": "main",
        "source": f"../../../原始素材/{src_name}",
        "source_in": 0.0,
        "start": 0.0,
        "duration": round(gt["n_frames"] / FPS, 4),
        "role": "body",
        "rule_id": "KILLMARK-BASE",
        "reason": "整条原素材铺底：标记的意义是「在原时间轴的哪一帧」，所以不做任何剪辑",
    }]
    texts: list[dict] = []
    ledger: list[dict] = []
    for k, e in enumerate(events):
        b = int(e["kill_frame_candidate"])
        start_f = max(0, b - LEAD_FRAMES)
        end_f = min(gt["n_frames"], start_f + SPAN_FRAMES)
        mark_frame = b + 1          # 实测横幅首现帧
        label = f"K{k + 1:02d} F{b} {t_of_frame(b):.3f}s"
        texts.append({
            "id": f"mark-{k + 1:02d}",
            "track": "mark",
            "content": label,
            "start": sec_of_frame(start_f),
            "duration": sec_of_frame(end_f) - sec_of_frame(start_f),
            "style": {
                "size": 6.0,
                "bold": True,
                "color": [1.0, 1.0, 1.0],
                "align": 1,
                "transform_x": LABEL_X,
                "transform_y": round(LABEL_Y0 - k * LABEL_DY, 4),
            },
            "background": {"color": "#D9000000", "style": 1, "round_radius": 0.06},
            "rule_id": "KILLMARK-01",
            "reason": (f"第 {k + 1} 个击杀候选：HUD 帧间差突变帧 F{b}（{t_of_frame(b):.3f}s），"
                       f"标记从 F{start_f} 起持续 {end_f - start_f} 帧，"
                       f"罩住实测横幅首现帧 F{mark_frame}；置信 {e['confidence']}"),
        })
        ledger.append({
            "n": k + 1,
            "text_id": f"mark-{k + 1:02d}",
            "label": label,
            "burst_frame": b,
            "burst_s": round(t_of_frame(b), 4),
            "mark_start_frame": start_f,
            "mark_end_frame": end_f - 1,
            "mark_start_us": us_of_frame(start_f),
            "mark_start_s": sec_of_frame(start_f),
            "mark_end_us": us_of_frame(end_f),
            "mark_duration_us": us_of_frame(end_f) - us_of_frame(start_f),
            "mark_duration_s": sec_of_frame(end_f) - sec_of_frame(start_f),
            "banner_first_frame_measured": mark_frame,
            "confidence": e["confidence"],
            "transform_y": round(LABEL_Y0 - k * LABEL_DY, 4),
        })
    edl = {
        "version": "1.0",
        "project": draft_name,
        "canvas": {"width": W, "height": H, "fps": int(FPS)},
        "style_ref": "killmark",
        "target_duration_s": round(gt["n_frames"] / FPS, 4),
        "tracks": [
            {"type": "video", "name": "main"},
            {"type": "text", "name": "mark"},
        ],
        "clips": clips,
        "texts": texts,
        "qa": {"required": ["duration-valid", "mark-frames-match-groundtruth"]},
    }
    return edl, ledger


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("short")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--draft-root", default=str(DRAFT_ROOT))
    a = ap.parse_args()

    if not GT.exists():
        print(f"[FAIL] 先跑 make_kill_groundtruth.py：{GT} 不存在", file=sys.stderr)
        return 2
    gt = json.loads(GT.read_text(encoding="utf-8"))
    src = next(SRC.glob(f"{a.short}*.mp4"), None)
    if src is None or gt["source"] != src.name:
        print(f"[FAIL] groundtruth 的 source={gt.get('source')} 与 原始素材/{a.short}*.mp4 不一致，"
              f"拒绝生成（防止张冠李戴）", file=sys.stderr)
        return 2

    draft_name = f"击杀帧标记_{a.short}"
    edl, ledger = build_edl(a.short, gt, src.name, draft_name)

    EDL_OUT.mkdir(parents=True, exist_ok=True)
    LEDGER_OUT.mkdir(parents=True, exist_ok=True)
    edl_path = EDL_OUT / f"killmark-{a.short}.json"
    edl_path.write_text(json.dumps(edl, ensure_ascii=False, indent=1), encoding="utf-8")
    ledger_path = LEDGER_OUT / f"killmark-{a.short}.json"
    ledger_path.write_text(json.dumps({
        "draft_name": draft_name,
        "edl": str(edl_path.relative_to(ROOT)).replace("\\", "/"),
        "source": src.name,
        "fps": FPS, "canvas": f"{W}x{H}",
        "alignment_rule": f"标记起点 = 突变帧 − {LEAD_FRAMES} 帧；持续 {SPAN_FRAMES} 帧",
        "groundtruth": str(GT.relative_to(ROOT)).replace("\\", "/"),
        "marks": ledger,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"=== 击杀帧标记草稿 · {draft_name} ===")
    print(f"素材 {src.name}（{gt['n_frames']} 帧 / {gt['n_frames'] / FPS:.3f}s）")
    print(f"EDL   {edl_path.relative_to(ROOT)}")
    print(f"台账  {ledger_path.relative_to(ROOT)}")
    print(f"\n{'#':>3} {'标记':>9} {'突变帧':>6} {'标记起止帧':>11} {'起点(µs)':>10} {'时长(µs)':>9} "
          f"{'transform_y':>11} {'置信':>6}")
    for m in ledger:
        print(f"{m['n']:3} {m['label']:>9} {m['burst_frame']:6} "
              f"{m['mark_start_frame']:5}..{m['mark_end_frame']:<5} {m['mark_start_us']:10} "
              f"{m['mark_duration_us']:9} {m['transform_y']:11.4f} {m['confidence']:>6}")

    conv = _load_converter()
    edl["__path__"] = str(edl_path)
    problems = conv.validate(edl, str(EDL_OUT))
    print(f"\n[校验] edl_to_draft.validate：{'通过' if not problems else str(len(problems)) + ' 个问题'}")
    for p in problems:
        print(f"  - {p}")
    if problems:
        return 1
    if a.dry_run:
        print("[DRY-RUN] 未生成草稿")
        return 0

    if not pathlib.Path(a.draft_root).is_dir():
        print(f"[FAIL] 草稿根目录不存在：{a.draft_root}", file=sys.stderr)
        return 2
    report = conv.build(edl, a.draft_root, draft_name, False)
    print(f"\n[OK] 草稿已生成：{report['draft_dir']}")
    print(f"     轨道 {len(report['tracks'])} 条 | 文本 {report['texts']} 条 | "
          f"警告 {len(report['warnings'])}")
    for w in report["warnings"]:
        print(f"     [WARN] {w}")
    print("     下一步见 projects/game-001/spec/killmark-<short>.md 的交付说明")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
