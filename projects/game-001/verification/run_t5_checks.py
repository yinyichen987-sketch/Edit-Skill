"""t5 审阅总入口 —— 一条命令跑完全部独立核查。

为什么需要它
------------
t5 的结论必须**可复现**。分散的四五个脚本各自能跑，但没有人会记得全部跑一遍；
而"我跑过了"这种记忆在审阅里是最不可靠的东西。这里把它们串成一个门禁。

包含两类检查：
  A. **工具自身的健康度**：每个 verification 工具的自测必须先绿。
     自测不绿时，其余结论都不可信——先修工具，再谈结论。
  B. **对交付物的独立核查**：不看报告，自己解析产物。

审阅侧的规则实现
----------------
规格里 CUT-05 的「高光前后各留 ≥X s 余量」**没有任何作者侧脚本实现**（见 `../claim-audit/`）。
本入口**自己实现它**——审阅判据不应只存在于被审方自己的工具里，否则被审方改口径就等于同时改了判据。
阈值 X **从规格文本里读出来**，不写死，避免本入口自己变成又一个"过期常量"。

用法
----
    .venv/Scripts/python.exe run_t5_checks.py
    .venv/Scripts/python.exe run_t5_checks.py --json-out t5-report.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
VER = REPO_ROOT / "projects" / "game-001" / "verification"
PY = sys.executable

SPEC = REPO_ROOT / "projects" / "game-001" / "spec" / "format-spec.md"
PLAN = REPO_ROOT / "projects" / "game-001" / "spec" / "episode-plan.md"
EDLS = [("GAME_EP01_LS", REPO_ROOT / "projects/game-001/edl/ep01.json"),
        ("GAME_EP01_VT", REPO_ROOT / "projects/game-001/edl/ep01-vertical.json")]
DRAFT_ROOT = REPO_ROOT / "projects" / "game-001" / "draft-out"
HIGHLIGHTS = REPO_ROOT / "projects" / "game-001" / "analysis" / "material-analysis.json"

SRC_KEY = {
    "4b0460c400bbb5320acb6063b4f59358.mp4": "a",
    "6b2eea343eee7595c3c0ede10d21d028.mp4": "b",
    "dcc871b1791e7796fadac842593f10f7.mp4": "c",
}
# 独立实测的不安全窗口（真实 PTS）。来源：../scene-cuts/scene-cuts-result.json
UNSAFE = {
    "a": [],
    "b": [[10.979688, 11.045378], [12.978711, 13.012044]],
    "c": [[2.07168, 2.105013], [3.37168, 3.405013]],
}


def run(cmd: list[str]) -> tuple[int, str]:
    """以子进程运行并把输出**按 UTF-8 解码**。

    不要用 text=True：子进程已把 stdout 重配置为 UTF-8，而父进程的 text 模式
    会按系统 locale（本机 GBK）解码，导致"阈值 0.3"这类中文变成乱码。
    子进程输出是 UTF-8 字节，就按 UTF-8 解。
    """
    r = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, timeout=900)
    out = (r.stdout or b"") + (r.stderr or b"")
    return r.returncode, out.decode("utf-8", errors="replace")


# ---------------------------------------------------------------- 审阅侧规则

# 审阅侧的基准阈值。
#
# 这里是**审阅判据**，不是被审方可调的参数。设计上有个真实的取舍：
#   - 只硬编码 → 规格改了我不跟，我自己变成"过期常量的持有者"（本项目已踩过 4 次同类）；
#   - 只动态读规格 → **被审方改一句规格，就把我用来判它的那把尺子放宽了**，
#     独立性当场消失（"改口径 = 改判据"）。
# 因此取第三条路：**基准硬编码 + 检测规格是否被改动，一改就报 FAIL 要求人工确认**。
# 这样常量不会过期（改动会被响亮报出），尺子也不会被被审方单方面移动。
REVIEW_MARGIN_BASELINE = 0.30


def measured_margin_threshold() -> tuple[float | None, str]:
    """从规格里读出 CUT-05 的余量阈值声明（仅用于**比对**，不直接用它判）。"""
    for p in (SPEC, PLAN):
        if not p.exists():
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if "余量" in line and "高光" in line:
                m = re.search(r"[≥>]=?\s*(\d+\.\d+)", line)
                if m:
                    return float(m.group(1)), f"{p.name}:{i}"
    return None, "规格里找不到「高光…余量 ≥X」"


def _safe(name: str, detail: str, fn):
    """把任一检查包起来：异常必须变成"该检查 FAIL + 原因"，而不是让总表崩掉。

    实测踩到：审阅期间其他成员正在写文件，`material-analysis.json` 一度不是合法 JSON，
    整个入口直接抛 traceback —— **一份跑不出总表的审阅入口等于没有入口**。
    审阅本来就要在"对方正在改"的状态下进行，工具必须容忍这一点。
    """
    try:
        return fn()
    except Exception as exc:
        return {"name": name, "status": "FAIL",
                "detail": f"{detail}（读取异常，文件可能正被编辑）",
                "findings": [f"{type(exc).__name__}: {exc}"]}


def margin_check() -> dict:
    """审阅侧独立实现：每个片段的素材区间相对其覆盖的高光区间是否留够 ≥X 余量。

    判定基准恒为 `REVIEW_MARGIN_BASELINE`（审阅判据），**不是**规格当前声明的值。
    规格声明值只用来比对：**若被改动，报 FAIL 要求人工确认**——因为放宽验收口径
    等于放宽判它的尺子，这必须由人拍板，不能由被审方静默完成。
    """
    declared, src = measured_margin_threshold()
    thr = REVIEW_MARGIN_BASELINE
    findings = []

    if declared is None:
        findings.append(f"规格里读不到余量阈值声明（{src}）——验收口径不明确")
    elif abs(declared - thr) > 1e-9:
        direction = "放宽" if declared < thr else "收紧"
        findings.append(
            f"**验收口径被改动（{direction}）**：规格声明 {declared}，审阅基准 {thr}"
            f"（读取处 {src}）。判据仍按基准 {thr} 执行；"
            f"若要正式改口径，需人工确认并同步更新审阅基准。")

    H = {}
    if HIGHLIGHTS.exists():
        j = json.loads(HIGHLIGHTS.read_text(encoding="utf-8"))
        for c in j["clips"]:
            for h in c["highlights"]:
                H[h["id"]] = [h["start"], h["start"] + h["duration"]]
    for name, edl_path in EDLS:
        if not edl_path.exists():
            findings.append(f"{name}: EDL 不存在 {edl_path}")
            continue
        e = json.loads(edl_path.read_text(encoding="utf-8"))
        for c in e["clips"]:
            k = SRC_KEY.get(os.path.basename(c["source"]))
            if k is None:
                continue
            r0 = float(c["source_in"])
            r1 = r0 + float(c["duration"])
            for hid, (h0, h1) in H.items():
                if hid[0].lower() != k:
                    continue
                if h0 >= r0 - 1e-6 and h1 <= r1 + 1e-6:
                    if h0 - r0 < thr - 1e-6:
                        findings.append(f"{name}/{c['id']} 覆盖 {hid}：前余量 {h0-r0:.2f}s < {thr}")
                    if r1 - h1 < thr - 1e-6:
                        findings.append(f"{name}/{c['id']} 覆盖 {hid}：后余量 {r1-h1:.2f}s < {thr}")
    return {"name": "CUT-05 高光余量", "status": "FAIL" if findings else "PASS",
            "detail": (f"基准 {thr}（审阅侧固定）；规格声明 {declared} @ {src}"),
            "findings": findings}


def unsafe_window_check() -> dict:
    """切点是否落在不安全窗口内 / 贴边 <0.1s。"""
    findings = []
    for name, edl_path in EDLS:
        if not edl_path.exists():
            continue
        e = json.loads(edl_path.read_text(encoding="utf-8"))
        for c in e["clips"]:
            k = SRC_KEY.get(os.path.basename(c["source"]))
            if k is None:
                continue
            r0 = float(c["source_in"])
            r1 = r0 + float(c["duration"])
            for w0, w1 in UNSAFE.get(k, []):
                if (w0 <= r0 <= w1) or (w0 <= r1 <= w1) or (r0 < w0 and r1 > w1):
                    findings.append(f"{name}/{c['id']} 跨过不安全窗口 [{w0}, {w1}]")
                elif min(abs(r0 - w0), abs(r0 - w1)) < 0.1 or min(abs(r1 - w0), abs(r1 - w1)) < 0.1:
                    findings.append(f"{name}/{c['id']} 贴边不安全窗口 [{w0}, {w1}]（<0.1s）")
    return {"name": "CUT-05 距不安全窗口 ≥0.1s", "status": "FAIL" if findings else "PASS",
            "detail": "窗口见 ../scene-cuts/scene-cuts-result.json（真实 PTS）", "findings": findings}


# ---------------------------------------------------------------- 汇总

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="t5 审阅总入口")
    ap.add_argument("--json-out")
    args = ap.parse_args()

    results = []

    # A. 工具自身健康度
    selftests = [
        ("scene-cuts 自测", [PY, str(VER / "scene-cuts" / "detect_scene_cuts.py"), "--selftest"]),
        ("draft-audit 正例自测", [PY, str(VER / "draft-audit" / "audit_draft.py"), "--selftest"]),
        ("draft-audit 反例自测", [PY, str(VER / "draft-audit" / "audit_draft.py"), "--negtest"]),
        ("frame-probe 自测", [PY, str(VER / "frame-probe" / "measure_sampling_bias.py"), "--selftest"]),
        ("claim-audit 自测", [PY, str(VER / "claim-audit" / "audit_claims.py"), "--selftest"]),
    ]
    for name, cmd in selftests:
        code, out = run(cmd)
        results.append({"name": name, "status": "PASS" if code == 0 else "FAIL",
                        "detail": "自测", "findings": [] if code == 0 else [out[-300:]]})

    # B. 对交付物的独立核查
    for draft, edl in EDLS:
        if not edl.exists():
            results.append({"name": f"draft-audit {draft}", "status": "SKIP",
                            "detail": "EDL 不存在", "findings": []})
            continue
        code, out = run([PY, str(VER / "draft-audit" / "audit_draft.py"),
                         "--edl", str(edl), "--draft-root", str(DRAFT_ROOT), "--draft", draft])
        fails = [l.strip() for l in out.splitlines() if "[FAIL]" in l]
        results.append({"name": f"草稿 == EDL（{draft}）", "status": "PASS" if code == 0 else "FAIL",
                        "detail": "draft-audit", "findings": fails})

    code, out = run([PY, str(VER / "claim-audit" / "audit_claims.py")])
    fails = [l.strip() for l in out.splitlines() if "[FAIL]" in l]
    results.append({"name": "规格声称 ↔ 脚本实现", "status": "PASS" if code == 0 else "FAIL",
                    "detail": "claim-audit", "findings": fails})

    results.append(_safe("CUT-05 高光余量", "审阅侧独立实现",
                         margin_check))
    results.append(_safe("CUT-05 距不安全窗口 ≥0.1s", "真实 PTS 窗口",
                         unsafe_window_check))

    # 输出
    def dwidth(s: str) -> int:
        """显示宽度：CJK 字符占 2 列。用 len() 做对齐会在中文行错位。"""
        import unicodedata
        return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)

    w = max(dwidth(r["name"]) for r in results)
    print("=" * 78)
    print("t5 独立核查总表")
    print("=" * 78)
    for r in results:
        mark = {"PASS": " PASS ", "FAIL": " FAIL ", "SKIP": " SKIP "}[r["status"]]
        pad = " " * max(0, w - dwidth(r["name"]))
        print(f"  [{mark}] {r['name']}{pad}  {r['detail']}")
        for f in r["findings"][:8]:
            print(f"           - {f}")
    blockers = [r for r in results if r["status"] == "FAIL"]
    print("=" * 78)
    print(f"合计 {len(results)} 项，FAIL {len(blockers)} 项，"
          f"verdict={'PASS' if not blockers else 'FAIL(with findings)'}")
    if blockers:
        print("阻塞项：")
        for r in blockers:
            print(f"  - {r['name']}（{len(r['findings'])} 条）")

    rep = {"results": results, "fail_count": len(blockers),
           "verdict": "PASS" if not blockers else "FAIL"}
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(rep, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
        print(f"报告已写入: {args.json_out}")
    return 0 if not blockers else 1


if __name__ == "__main__":
    sys.exit(main())
