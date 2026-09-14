"""打印 EDL 的摘要事实，便于与草稿逐项对照。"""
import json
import sys
from pathlib import Path

for f in sys.argv[1:]:
    p = Path(f)
    j = json.loads(p.read_text(encoding="utf-8"))
    print("=" * 78)
    print(f"EDL: {f}")
    print(f"  project={j.get('project')!r} canvas={j.get('canvas')} "
          f"target_duration_s={j.get('target_duration_s')} style_ref={j.get('style_ref')}")
    n_tr = 0
    for c in j.get("clips") or []:
        tr = c.get("transition")
        if tr:
            n_tr += 1
        print(f"  clip {c['id']:<4} track={c['track']:<8} role={c.get('role'):<8} "
              f"source_in={c.get('source_in')} start={c.get('start')} dur={c.get('duration')} "
              f"vol={c.get('volume')} rule={c.get('rule_id')} transition={tr}")
        print(f"       source={c.get('source')}")
    for t in j.get("texts") or []:
        print(f"  text {t['id']:<4} start={t.get('start')} dur={t.get('duration')} "
              f"content={t.get('content')!r}")
    clips = j.get("clips") or []
    end = max((c.get("start", 0) + c.get("duration", 0)) for c in clips) if clips else 0
    print(f"  clips={len(clips)} texts={len(j.get('texts') or [])} "
          f"declared_transitions={n_tr} timeline_end={end}")
    if clips:
        print(f"  sum(duration)={sum(c['duration'] for c in clips)}")
