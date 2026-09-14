"""打印一份 EDL 的可读摘要（给人和 agent 复核用，不改任何文件）。

用法：
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\show_edl_v3.py projects\\game-001\\edl\\single-4c58efb4-jy.json
"""
from __future__ import annotations

import json
import pathlib
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[3]
p = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else \
    ROOT / "projects/game-001/edl/single-4c58efb4-jy.json"
d = json.loads(p.read_text(encoding="utf-8"))

print(f"== {d['project']}  {d['canvas']['width']}x{d['canvas']['height']}@{d['canvas']['fps']}  "
      f"{d['target_duration_s']:.3f}s ==")
print("\n-- clips --")
for c in d["clips"]:
    sp = c.get("speed", 1.0)
    print(f"  {c['id']:>3} {c['track']:<9} src_in={c.get('source_in', 0):7.3f} "
          f"start={c['start']:7.3f} dur={c['duration']:7.4f} speed={sp:<4} role={c['role']}")

print("\n-- effect_tracks --")
for t in d["effect_tracks"]:
    times = ", ".join(f"{e['start']:.3f}" for e in t["effects"])
    print(f"  {t['name']:<10} {len(t['effects'])} 个 @ {times}")

print("\n-- audio_overlays --")
for a in d.get("audio_overlays", []):
    print(f"  {a['source']}  start={a['start']} dur={a['duration']:.3f} vol={a['volume']} fade={a.get('fade')}")

print("\n-- _beat_alignment --")
print(json.dumps(d["_beat_alignment"], ensure_ascii=False, indent=1))

print("\n-- _bgm --")
print(json.dumps(d["_bgm"], ensure_ascii=False, indent=1))

print("\n-- _manual（必须人工做，别假装做了）--")
for m in d["_manual"]:
    print(f"  · {m}")
