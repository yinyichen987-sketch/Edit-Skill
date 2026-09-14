"""verify/ 目录与 material-analysis.json 的一致性审计。

设计要点：**不用阈值判据**。
    阈值（"越界个数 <= N"）需要人拍一个任意数，而且它管不住真正的问题。
    真正的问题是「**有异常却没写出来**」，不是「有异常」。

    因此判据是**双向断言**：
        扫描出的每一个异常，都必须在 disclosed_anomalies 清单里；
        清单里的每一条，也必须能在实际数据里找到。
    前者防「漏披露」，后者防「幽灵披露」（写了但不存在 —— 会让人以为已经审过）。

检查项：
    1. s / m 帧时间是否与 JSON 的 start / start+duration/2 吻合
    2. pk 帧是否落在其所属高光区间内
    3. 是否有帧被多个高光共用（同一张图对应两个高光）
    4. 同段内是否有高光区间包含关系
    5. 清单计数自洽

用法：
    python audit_verify_dir.py              # 审计，有未披露/幽灵异常则退出码 1
    python audit_verify_dir.py --selftest   # 自检：注入假异常，验证两个方向的断言都真的会失败
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict

ROOT = "projects/game-001/analysis"
VERIFY = os.path.join(ROOT, "verify")
FRAME_RE = re.compile(r"^([abc])_(A-H\d+|B-H\d+|C-H\d+)_(s|m|pk)_([\d.]+)s\.jpg$")
GAP_RE = re.compile(r"^_gapcheck_([abc])_([\d.]+)s\.jpg$")

# ---------------------------------------------------------------------------
# 已披露异常清单（**这里是唯一允许出现异常的地方**；README.md 的「已知限制」须与之对应）
# ---------------------------------------------------------------------------
DISCLOSED_ANOMALIES = {
    # pk 落在其所属高光区间之外。机制：音频能量爆发先于我确认到的状态帧。
    "pk_outside_interval": [
        {"id": "A-H3", "interval": [6.35, 6.95], "pk": 4.75, "offset": -1.60},
        {"id": "C-H4", "interval": [4.40, 5.00], "pk": 3.25, "offset": -1.15},
        {"id": "A-H5", "interval": [11.60, 12.20], "pk": 11.25, "offset": -0.35},
        {"id": "A-H2", "interval": [5.00, 6.00], "pk": 4.75, "offset": -0.25},
        {"id": "A-H4", "interval": [8.40, 9.00], "pk": 8.25, "offset": -0.15},
        {"id": "B-H6", "interval": [23.40, 24.00], "pk": 23.25, "offset": -0.15},
    ],
    # 同一张图被多个高光引用。
    "shared_frames": [
        {"kind": "m", "clip": "b", "t": 23.70, "ids": ["B-H6", "B-H7"],
         "severity": "high", "why": "两区间中点同值 ⇒ 同一画面；当两个独立高光选材会用两次"},
        {"kind": "pk", "clip": "a", "t": 4.75, "ids": ["A-H2", "A-H3"],
         "severity": "medium", "why": "能量证据跨区间共享"},
        {"kind": "pk", "clip": "c", "t": 3.25, "ids": ["C-H3", "C-H4"],
         "severity": "medium", "why": "同一能量段的相邻切片"},
    ],
    # 同段内高光区间包含关系。
    "interval_containment": [
        {"inner": "B-H6", "outer": "B-H7", "note": "B-H6 [23.40,24.00] ⊂ B-H7 [21.40,26.00]"},
    ],
}

EXPECTED_NO_PK = ["B-H4"]
TOL = 0.02


def keyof_pk(d: dict) -> tuple:
    return (d["id"], round(float(d["pk"]), 2))


def main() -> int:
    # Windows 默认控制台为 GBK，中文/符号（⊂ ✓ ✅ → 等）会在打印中途抛
    # UnicodeEncodeError 而退出；崩溃退出码可能与脚本自身的失败码相同，
    # 导致「崩溃」被误读为「检查未通过」。统一改为 UTF-8。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    selftest = "--selftest" in sys.argv
    data = json.load(open(os.path.join(ROOT, "material-analysis.json"), encoding="utf-8"))
    files = [f for f in os.listdir(VERIFY) if f.endswith(".jpg")]

    frames, gapchecks, unparsed = [], [], []
    for f in files:
        m = FRAME_RE.match(f)
        if m:
            frames.append({"clip": m.group(1), "id": m.group(2), "kind": m.group(3),
                           "t": float(m.group(4)), "file": f})
        elif GAP_RE.match(f):
            gapchecks.append(f)
        else:
            unparsed.append(f)

    hl = {}
    for c in data["clips"]:
        for h in c["highlights"]:
            hl[h["id"]] = {"clip": c["key"], "start": h["start"],
                           "end": h["start"] + h["duration"]}

    print("=" * 78)
    print("A) s / m 帧时间与 JSON 是否吻合")
    print("=" * 78)
    mismatches = []
    for fr in frames:
        if fr["kind"] not in ("s", "m"):
            continue
        h = hl.get(fr["id"])
        if not h:
            mismatches.append((fr["file"], "JSON 无此高光 id", None, None))
            continue
        expect = h["start"] if fr["kind"] == "s" else h["start"] + (h["end"] - h["start"]) / 2
        if abs(fr["t"] - expect) > TOL:
            mismatches.append((fr["file"], expect, fr["t"], fr["t"] - expect))
    n_sm = sum(1 for f in frames if f["kind"] in ("s", "m"))
    print(f"   共 {n_sm} 张；不符 {len(mismatches)} 张")
    for row in mismatches:
        print(f"     !! {row}")

    print()
    print("=" * 78)
    print("B) pk 落在区间外的情况")
    print("=" * 78)
    outside = []
    for fr in frames:
        if fr["kind"] != "pk":
            continue
        h = hl.get(fr["id"])
        if h and not (h["start"] <= fr["t"] <= h["end"]):
            outside.append({"id": fr["id"], "interval": [round(h["start"], 2), round(h["end"], 2)],
                            "pk": fr["t"], "offset": round(fr["t"] - h["start"], 2)})
    outside.sort(key=lambda x: x["offset"])
    print(f"   落在区间外 {len(outside)} 个（已披露 {len(DISCLOSED_ANOMALIES['pk_outside_interval'])} 个）")
    for o in outside:
        print(f"     {o['id']:6} 区间{o['interval']} pk={o['pk']:.2f} 偏移 {o['offset']:+.2f}s")

    print()
    print("=" * 78)
    print("C) 被共用的帧")
    print("=" * 78)
    shared_map = defaultdict(list)
    for fr in frames:
        shared_map[(fr["kind"], fr["clip"], fr["t"])].append(fr["id"])
    shared = []
    for (kind, clip, t), ids in shared_map.items():
        if len(ids) > 1:
            shared.append({"kind": kind, "clip": clip, "t": t, "ids": sorted(ids)})
    shared.sort(key=lambda x: (x["kind"], x["clip"], x["t"]))
    print(f"   共 {len(shared)} 处（已披露 {len(DISCLOSED_ANOMALIES['shared_frames'])} 处）")
    for s in shared:
        print(f"     {s['kind']} {s['clip']}@{s['t']:.2f}s <- {s['ids']}")

    print()
    print("=" * 78)
    print("D) 区间包含关系")
    print("=" * 78)
    per_clip = defaultdict(list)
    for hid, h in hl.items():
        per_clip[h["clip"]].append((hid, h["start"], h["end"]))
    contained = []
    for clip, items in per_clip.items():
        for hid, lo, hi in items:
            for ohid, olo, ohi in items:
                if hid != ohid and olo <= lo and hi <= ohi and (ohi - olo) > (hi - lo):
                    contained.append({"inner": hid, "outer": ohid,
                                      "note": f"{hid} [{lo:.2f},{hi:.2f}] ⊂ {ohid} [{olo:.2f},{ohi:.2f}]"})
    print(f"   共 {len(contained)} 处（已披露 {len(DISCLOSED_ANOMALIES['interval_containment'])} 处）")
    for c in contained:
        print(f"     {c['note']}")

    print()
    print("=" * 78)
    print("E) 清单计数")
    print("=" * 78)
    kinds = defaultdict(int)
    for fr in frames:
        kinds[fr["kind"]] += 1
    total = sum(kinds.values()) + len(gapchecks)
    print(f"   s={kinds['s']}  m={kinds['m']}  pk={kinds['pk']}  gapcheck={len(gapchecks)}  "
          f"合计={total}（实际 jpg {len(files)}）")
    no_pk = sorted(set(hl) - {f["id"] for f in frames if f["kind"] == "pk"})
    print(f"   高光总数 {len(hl)}；无 pk 的高光 {no_pk}（期望 {EXPECTED_NO_PK}）")
    if unparsed:
        print(f"   !! 无法解析的文件名 {len(unparsed)} 个：{unparsed}")

    # ------------------------------------------------------------------ 自检注入
    if selftest:
        print()
        print("=" * 78)
        print("SELFTEST：注入假异常，验证双向断言都会失败")
        print("=" * 78)
        injected_outside = outside + [{"id": "ZZ-H99", "interval": [1.0, 2.0], "pk": 0.5, "offset": -0.5}]
        injected_shared = shared + [{"kind": "pk", "clip": "a", "t": 99.99, "ids": ["A-H1", "A-H2"]}]
        r1 = reconcile("pk_outside_interval", injected_outside, DISCLOSED_ANOMALIES["pk_outside_interval"])
        r2 = reconcile("shared_frames", injected_shared, DISCLOSED_ANOMALIES["shared_frames"])
        print(f"   注入未披露 pk 异常 -> 检出 missing={len(r1['missing'])} "
              f"ghost={len(r1['ghost'])}  {'✅ 断言触发' if r1['missing'] else '❌ 未触发'}")
        print(f"   注入未披露共用帧   -> 检出 missing={len(r2['missing'])} "
              f"ghost={len(r2['ghost'])}  {'✅ 断言触发' if r2['missing'] else '❌ 未触发'}")

        # 幽灵披露方向：清单里塞一条不存在的内容
        ghost_list = DISCLOSED_ANOMALIES["pk_outside_interval"] + [
            {"id": "GH-H00", "interval": [9.0, 9.5], "pk": 8.0, "offset": -1.0}]
        r3 = reconcile("pk_outside_interval", outside, ghost_list)
        print(f"   清单塞入不存在项   -> 检出 ghost={len(r3['ghost'])}  "
              f"{'✅ 断言触发' if r3['ghost'] else '❌ 未触发'}")
        ok = bool(r1["missing"]) and bool(r2["missing"]) and bool(r3["ghost"])
        print(f"\n   SELFTEST {'PASS' if ok else 'FAIL'}：双向断言均有效")
        return 0 if ok else 1

    # ------------------------------------------------------------------ 双向断言
    print()
    print("=" * 78)
    print("F) 双向断言：扫出的异常必须已披露，披露的必须真实存在")
    print("=" * 78)
    problems = 0
    for name, actual, disclosed in (
        ("pk_outside_interval", outside, DISCLOSED_ANOMALIES["pk_outside_interval"]),
        ("shared_frames", shared, DISCLOSED_ANOMALIES["shared_frames"]),
        ("interval_containment", contained, DISCLOSED_ANOMALIES["interval_containment"]),
    ):
        r = reconcile(name, actual, disclosed)
        status = "OK" if not r["missing"] and not r["ghost"] else "FAIL"
        print(f"   {name:22} 实际 {len(actual):2} / 披露 {len(disclosed):2}  -> {status}")
        for m in r["missing"]:
            print(f"      !! 漏披露：{m}")
            problems += 1
        for g in r["ghost"]:
            print(f"      !! 幽灵披露（清单有此条但实际不存在）：{g}")
            problems += 1
    if mismatches:
        print(f"   s/m 时间不符 {len(mismatches)} 张 -> 计入问题")
        problems += len(mismatches)
    if unparsed:
        problems += len(unparsed)
    if no_pk != EXPECTED_NO_PK:
        print(f"   !! 无 pk 的高光集合与期望不符：{no_pk} != {EXPECTED_NO_PK}")
        problems += 1

    print()
    if problems:
        print(f"结论：发现 {problems} 处问题（漏披露 / 幽灵披露 / 时间不符）")
        return 1
    print("结论：全部异常均已披露，且披露清单无幽灵条目 ✅")
    return 0


def reconcile(name: str, actual: list, disclosed: list) -> dict:
    """双向比对。返回 {missing:[...], ghost:[...]}。"""
    if name == "pk_outside_interval":
        ka = {keyof_pk(a) for a in actual}
        kd = {keyof_pk(d) for d in disclosed}
        fmt = lambda k: f"{k[0]} pk@{k[1]}"
    elif name == "shared_frames":
        ka = {(a["kind"], a["clip"], round(a["t"], 2)) for a in actual}
        kd = {(d["kind"], d["clip"], round(d["t"], 2)) for d in disclosed}
        fmt = lambda k: f"{k[0]} {k[1]}@{k[2]}"
    else:
        ka = {(a["inner"], a["outer"]) for a in actual}
        kd = {(d["inner"], d["outer"]) for d in disclosed}
        fmt = lambda k: f"{k[0]} ⊂ {k[1]}"
    return {"missing": [fmt(k) for k in sorted(ka - kd)],
            "ghost": [fmt(k) for k in sorted(kd - ka)]}


if __name__ == "__main__":
    raise SystemExit(main())
