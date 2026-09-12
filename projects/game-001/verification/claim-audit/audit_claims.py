"""规格声称 ↔ 脚本实现 的一致性审计器（t5 用）。

要防的失败模式
--------------
项目里出现过这样一种组合，三个脚本全绿而规格是假的：

  1. **规则存在**   规格写了「高光前后各留 ≥0.3s 余量」
  2. **声称存在**   规格写了「8 个切点全部达标」，还引用了脚本名
  3. **实现不存在** 被引用的脚本**文件根本不存在**；另一个脚本 docstring 里写了 0.3，
                   正文只实现 0.10 与 0.034，跑出来仍是 `ALL PASS`

即：**校验器的声明范围大于它的实现范围，于是"全绿"被当成"已满足"。**

判据（三条，全部可自动检查）
--------------------------
1. 规格里每个「全部达标 / 已满足 / 无违规 / ALL PASS」类字样，所在**同一行或紧邻行**
   若引用了脚本，该脚本必须**真实存在**。
2. 该脚本必须能被**运行到退出**（不崩、有明确退出码）。
3. 声称里出现的**数值阈值**必须在该脚本源码里出现——否则脚本没有实现它。
   （关键前提：宣称"达标"必须指向一个**真正实现了该判据**的脚本，而不只是存在一个脚本。）

已知局限
--------
- 第 3 条是**字面量搜索**，只能证明"阈值出现过"，不能证明判据逻辑正确；
  它专抓"声称里有 0.3、脚本里根本没有 0.3"这类**完全没有实现**的情况。
- 第 2 条默认**不运行**脚本（有些脚本会写文件），需要显式 `--run` 才执行。
  `--run` 会在仓库根目录下以子进程执行被引用的脚本，**只应对可信脚本使用**。

用法
----
    .venv/Scripts/python.exe audit_claims.py --selftest
    .venv/Scripts/python.exe audit_claims.py            # 静态检查（不运行脚本）
    .venv/Scripts/python.exe audit_claims.py --run      # 同时执行被引用的脚本
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]

DOCS = [
    "projects/game-001/spec/format-spec.md",
    "projects/game-001/spec/episode-plan.md",
]

CLAIM_WORDS = ["全部达标", "全部通过", "均达标", "已满足", "无违规", "0 违规",
               "ALL PASS", "全部一致", "全部合格", "均已验证"]

PY_REF = re.compile(r"([\w./\\-]*\.py)")
NUM_REF = re.compile(r"(\d+\.\d+)")
# 只把**比较符/量词旁边**的数字当作"验收阈值"。
# 第一版只要同一行出现"余量/容差"就收走该行所有小数，结果把 15.00、
# 21.40、48.96 这类**描述性数据**也当成阈值，一口气报出 40+ 条——全是假阳性。
# 一个"什么都要报"的检查等于没有检查。
THRESH_PATTERNS = [
    re.compile(r"[≥>]=?\s*(\d+\.\d+)"),                       # ≥0.3 / >=0.1
    re.compile(r"(\d+\.\d+)\s*s?[^\w]{0,6}(?:余量|容差)"),      # 0.3 s 余量 / 0.034s）余量
    re.compile(r"(?:留|至少|不少于)\s*(\d+\.\d+)"),             # 留 0.034
]


def thresholds_in(line: str) -> list[str]:
    """从一行里提取"被声明为判据"的阈值，只认比较符/量词旁边的数字。"""
    out = []
    for pat in THRESH_PATTERNS:
        for m in pat.finditer(line):
            if m.group(1) not in out:
                out.append(m.group(1))
    return out


def code_numbers(path: Path) -> set[float]:
    """脚本**可执行代码**里出现过的数值字面量（tokenize 的 NUMBER token）。

    这是本审计器最关键的一步。第一版直接在整个源文件里做**子串搜索**，
    结果漏判了真实缺陷：`verify_cut_margins.py` 的 **docstring 里写了 `>= 0.3`**，
    子串搜索因此通过——但代码里根本没有 0.3 的判据。
    **"文档里提到"不等于"代码里实现"。**

    用 NUMBER token 而不是子串，还顺手解决了另一类假阳性：
    `0.1` 不会因为代码里有 `0.10` 而被判为"已实现"（虽然数值相等也应算实现，
    这里用浮点比较而非子串比较来表达这个语义）。
    """
    import tokenize
    nums: set[float] = set()
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for tok in tokenize.generate_tokens(fh.readline):
                if tok.type == tokenize.NUMBER:
                    try:
                        nums.add(float(tok.string))
                    except ValueError:
                        pass
    except Exception:
        return set()
    return nums


def prose_only(path: Path, num: str) -> bool:
    """该数值是否（仅）出现在注释/字符串里，而不在代码里。"""
    full = path.read_text(encoding="utf-8", errors="replace")
    if num not in full:
        return False
    try:
        target = float(num)
    except ValueError:
        return False
    return not any(abs(v - target) < 1e-9 for v in code_numbers(path))


def find_scripts(text: str) -> list[str]:
    out = []
    for m in PY_REF.finditer(text):
        s = m.group(1).strip("`.,;()[]")
        if s and s not in out:
            out.append(s)
    return out


def resolve_ref(ref: str, root: Path = REPO_ROOT) -> Path | None:
    """把文档里的脚本引用解析成真实路径。"""
    cands = [root / ref,
             root / "projects" / "game-001" / ref,
             root / ref.replace("\\", "/"),
             root / "projects" / "game-001" / Path(ref).name]
    for c in cands:
        if c.exists():
            return c.resolve()
    for p in root.rglob(Path(ref).name):
        if p.is_file() and ".venv" not in str(p):
            return p.resolve()
    return None


def repo_code_index(root: Path) -> dict[float, list[str]]:
    """全仓（排除 .venv / .git）每个数值字面量 → 出现过它的脚本列表。

    为什么要全仓而不是只看文档引用的脚本：实现可能落在文档**没引用**的脚本里。
    第一版只查"本文档引用的脚本"，把 CAP-03 的 `1.2` 也报了违规——
    而它其实由 `verify_t4_deliverables.py` 实现，只是该文档没引用它。
    **那种误报和分析漏洞一样糟。**
    """
    idx: dict[float, list[str]] = {}
    for p in root.rglob("*.py"):
        s = str(p)
        if ".venv" in s or ".git" in s or "__pycache__" in s:
            continue
        for v in code_numbers(p):
            idx.setdefault(v, []).append(str(p.relative_to(root)))
    return idx


def audit(docs: list[str], do_run: bool, root: Path = REPO_ROOT) -> dict:
    findings = []
    all_refs: dict[str, list[str]] = {}

    for rel in docs:
        p = root / rel
        if not p.exists():
            findings.append({"doc": rel, "level": "warn", "msg": "文档不存在"})
            continue
        lines = p.read_text(encoding="utf-8").splitlines()

        # 全文脚本引用（用于"引用了不存在的脚本"这一类）
        for i, line in enumerate(lines, 1):
            for ref in find_scripts(line):
                all_refs.setdefault(ref, []).append(f"{rel}:{i}")

        # 逐条声称
        for i, line in enumerate(lines, 1):
            if not any(w in line for w in CLAIM_WORDS):
                continue
            window = " ".join(lines[max(0, i - 2):i + 1])
            refs = find_scripts(window)
            nums = []
            for ln in lines[max(0, i - 2):i + 1]:
                for n in thresholds_in(ln):
                    if n not in nums:
                        nums.append(n)
            findings.append({
                "doc": rel, "line": i, "level": "info", "kind": "claim",
                "msg": line.strip()[:160], "cited_scripts": refs,
                "claimed_numbers": sorted(set(nums)),
            })

    # 引用脚本的存在性
    #
    # 关键区分：**"引用一个不存在的脚本" 与 "在更正说明里提到一个曾经不存在的脚本" 不是一回事。**
    # 实测踩到：t4 修好后，`format-spec.md:440` 写「旧文…引用了**不存在**的脚本
    # `tools/_check_cutmargins.py`…已删去该引用」——文档**在记录自己已修的错误**，
    # 而第一版把它当成失效引用报 FAIL。**文档诚实地记录错误，不该被检查器惩罚。**
    # 判据：某一引用的**所有**出现处都带"历史/更正"语义词时，降级为 info。
    HISTORICAL_MARKERS = ("不存在", "已删", "已更正", "失实", "旧文", "此前", "曾经", "已修复")
    missing = []
    historical = []
    for ref, places in sorted(all_refs.items()):
        rp = resolve_ref(ref, root)
        if rp is not None:
            continue
        ctx_lines = []
        for place in places:
            doc_rel, lineno = place.rsplit(":", 1)
            try:
                ctx_lines.append((root / doc_rel).read_text(
                    encoding="utf-8").splitlines()[int(lineno) - 1])
            except Exception:
                ctx_lines.append("")
        if ctx_lines and all(any(m in ln for m in HISTORICAL_MARKERS) for ln in ctx_lines):
            historical.append({"ref": ref, "cited_at": places,
                               "note": "所有出现处都带历史/更正语义词 → 视为'记录已修的错误'，不计为失效引用"})
        else:
            missing.append({"ref": ref, "cited_at": places})
    # ---- 检查 B：文档里作为阈值出现的数值，是否有**任何**脚本在代码里实现
    unimplemented = []
    thresholds_seen: dict[str, list[str]] = {}
    code_idx = repo_code_index(root)
    for rel in docs:
        p = root / rel
        if not p.exists():
            continue
        lines = p.read_text(encoding="utf-8").splitlines()
        doc_scripts = []
        for line in lines:
            for ref in find_scripts(line):
                rp = resolve_ref(ref)
                if rp is not None and rp not in doc_scripts:
                    doc_scripts.append(rp)
        for i, line in enumerate(lines, 1):
            for n in thresholds_in(line):
                thresholds_seen.setdefault(rel, [])
                if n not in thresholds_seen[rel]:
                    thresholds_seen[rel].append(n)
                target = float(n)
                implementers = code_idx.get(target, [])
                if not implementers:
                    prose = [s for s in doc_scripts if prose_only(s, n)]
                    unimplemented.append({
                        "doc": rel, "line": i, "number": n,
                        "declared_as": line.strip()[:120],
                        "implemented_by": [],
                        "number_only_in_prose_of": [str(s.relative_to(root)) for s in prose],
                        "msg": (f"阈值 {n} 在文档里被声明为判据，但**全仓任何脚本的可执行代码里"
                                f"都找不到它**"
                                + (f"（仅出现在 {[str(x.relative_to(root)) for x in prose]} 的注释/字符串里）"
                                   if prose else "")),
                    })

    runs = []
    if do_run:
        # 只把**被"声称"引用的脚本**当作门禁：一行若声称了结果并引用了脚本，
        # 该脚本的运行退出码必须为 0。
        # 不这么做会引入假阳性——`analyze_film.py` / `edl_to_draft.py` 是被文档
        # 当作**命令行工具**提到的，裸跑必然以 usage 错误退出（exit=2），
        # 把它们计入 verdict 等于因为"没给它参数"而判交付物失败。
        # **误报和分析漏洞一样糟**，所以门禁范围要精确等于"被声称支撑的脚本"。
        gated: set[str] = set()
        for f in findings:
            if f.get("kind") != "claim":
                continue
            for ref in f.get("cited_scripts", []):
                rp = resolve_ref(ref)
                if rp is not None:
                    gated.add(str(rp))
        for ref in sorted(all_refs):
            rp = resolve_ref(ref)
            if rp is None:
                continue
            try:
                r = subprocess.run([sys.executable, str(rp)], cwd=str(root),
                                   capture_output=True, timeout=600)
                tail = ((r.stdout or b"") + (r.stderr or b"")).decode("utf-8", "replace")[-300:]
                runs.append({"script": str(rp.relative_to(root)),
                             "exit": r.returncode,
                             "gated": str(rp) in gated,
                             "tail": tail})
            except Exception as exc:
                runs.append({"script": str(rp.relative_to(root)), "exit": None,
                             "gated": str(rp) in gated, "tail": f"运行异常: {exc}"})

    # 运行失败也必须进 verdict（仅限门禁脚本）。
    # 否则门禁存在一个洞：**只要"实现了"这条判据，哪怕实现的脚本一跑就失败，
    # 门禁也会转绿**——"有脚本"被当成"判据被满足"。这正是本工具要防的那类错误，
    # 不能自己在自己身上再犯一次。
    run_failures = [r for r in runs if r.get("gated") and r.get("exit") not in (0, None)]
    non_gated_nonzero = [r for r in runs
                         if not r.get("gated") and r.get("exit") not in (0, None)]

    return {
        "docs": docs,
        "claim_count": sum(1 for f in findings if f.get("kind") == "claim"),
        "claims": [f for f in findings if f.get("kind") == "claim"],
        "all_script_refs": {k: v for k, v in sorted(all_refs.items())},
        "missing_scripts": missing,
        "historical_mentions": historical,
        "unimplemented_claims": unimplemented,
        "runs": runs,
        "run_failures": run_failures,
        "non_gated_nonzero_runs": non_gated_nonzero,
        "verdict": ("PASS" if (not missing and not unimplemented and not run_failures)
                    else "FAIL"),
    }


def selftest() -> bool:
    """自测：用**合成夹具**验证判据 A 与 B 都能触发。

    ⚠️ 这里刻意**不**断言"本项目当前有哪两个缺陷"。第一版就是这么写的，结果
    当 t4 真的把 `0.3` 实现进脚本后，本自测立刻转为 FAIL——**它把"检测器能工作"
    和"被检对象有缺陷"绑在了一起**。
    那样的自测有两个害处：① 项目一改善它就变红，看起来像工具坏了；
    ② 更糟的是，它诱使人为了让自测变绿去**保留缺陷**。

    **正确的做法：检测器对"已知坏的输入"必须报错，而不是对"当前的输入"必须报错。**
    所以下面当场合成一个最小仓库：一个只有 docstring 提到 0.3 的脚本 + 一个
    引用了不存在脚本的文档，断言两条都被抓出。
    """
    import shutil
    import tempfile

    print("=" * 74)
    print("审计器自测：用合成夹具验证判据 A / B 能触发（不依赖项目当前状态）")
    print("=" * 74)
    base = Path(__file__).resolve().parent / "_selftest"
    if base.exists():
        shutil.rmtree(base, ignore_errors=True)
    (base / "tools").mkdir(parents=True, exist_ok=True)

    # 夹具 1：0.3 只出现在 docstring 里，代码中完全没有
    (base / "tools" / "prose_only.py").write_text(
        '"""声称实现了 0.3s 余量判据（其实只在注释里）。\n\n'
        'CUT-05: 高光前后各留 >= 0.3 s 余量。\n"""\n'
        "TOL = 0.10\n"
        "FRAME = 0.034\n"
        "def check(margin):\n"
        "    return margin >= TOL\n",
        encoding="utf-8")

    # 夹具 2：引用了不存在的脚本
    (base / "doc.md").write_text(
        "# 合成规格\n\n"
        "- 高光前后各留 **≥0.3 s** 余量（CUT-05）。\n\n"
        "本集 4 个片段 8 个切点**全部达标**"
        "（脚本 `tools/prose_only.py`、`tools/does_not_exist.py`）。\n",
        encoding="utf-8")

    rep = audit(["doc.md"], do_run=False, root=base)
    ok = True

    miss = [m["ref"] for m in rep["missing_scripts"]]
    hit1 = any("does_not_exist" in m for m in miss)
    print(f"  [{'PASS' if hit1 else 'FAIL'}] 判据A 抓出「被引用但不存在的脚本」: {miss}")
    ok = ok and hit1

    un = [(u["number"], u["number_only_in_prose_of"]) for u in rep["unimplemented_claims"]]
    hit2 = any(n == "0.3" and prose for n, prose in un)
    print(f"  [{'PASS' if hit2 else 'FAIL'}] 判据B 抓出「阈值只在注释/字符串里」: {un}")
    ok = ok and hit2

    # 判据 B 的**反例**：把 0.3 真正写进代码后，就不应再报
    (base / "tools" / "prose_only.py").write_text(
        '"""CUT-05: 高光前后各留 >= 0.3 s 余量。"""\n'
        "MARGIN = 0.3\n"
        "def check(margin):\n"
        "    return margin >= MARGIN\n",
        encoding="utf-8")
    rep2 = audit(["doc.md"], do_run=False, root=base)
    hit3 = not any(u["number"] == "0.3" for u in rep2["unimplemented_claims"])
    print(f"  [{'PASS' if hit3 else 'FAIL'}] 判据B 反例：阈值进了代码后不再报 0.3")
    ok = ok and hit3

    shutil.rmtree(base, ignore_errors=True)
    print(f"\n  verdict={rep['verdict']}")
    print("  [PASS] 判据 A/B 在合成夹具上按预期触发与收敛" if ok
          else "  [FAIL] 审计器漏判或误报，不可信")
    return ok


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="规格声称 ↔ 脚本实现 一致性审计器")
    ap.add_argument("--docs", nargs="*", default=DOCS)
    ap.add_argument("--run", action="store_true", help="执行被引用的脚本（有副作用风险）")
    ap.add_argument("--json-out")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return 0 if selftest() else 1

    rep = audit(args.docs, args.run)
    print("=" * 74)
    print(f"规格声称 ↔ 脚本实现   (claim 行 {rep['claim_count']} 条，引用脚本 {len(rep['all_script_refs'])} 个)")
    print("=" * 74)
    print("\n-- 包含「达标/已满足」类字样的行")
    for c in rep["claims"]:
        print(f"  {c['doc']}:{c['line']}  cited={c['cited_scripts']}  numbers={c['claimed_numbers']}")
        print(f"      {c['msg']}")
    print("\n-- 被引用但不存在的脚本（引用处）")
    for m in rep["missing_scripts"]:
        print(f"  [FAIL] {m['ref']}  <- {m['cited_at']}")
    if not rep["missing_scripts"]:
        print("  无")
    if rep.get("historical_mentions"):
        print("\n-- 仅在更正说明里提到的历史脚本（**不计为失效引用**）")
        for m in rep["historical_mentions"]:
            print(f"  [info] {m['ref']}  <- {m['cited_at']}")
    print("\n-- 文档声明为判据、但**全仓任何脚本的可执行代码**里都未实现的阈值")
    for u in rep["unimplemented_claims"]:
        print(f"  [FAIL] {u['doc']}:{u['line']}  阈值 {u['number']}")
        print(f"      声明原文: {u['declared_as']}")
        if u["number_only_in_prose_of"]:
            print(f"      **仅出现在注释/字符串里**: {u['number_only_in_prose_of']}")
    if not rep["unimplemented_claims"]:
        print("  无")
    if rep["runs"]:
        print("\n-- 被引用脚本的运行结果")
        for r in rep["runs"]:
            tag = "门禁" if r.get("gated") else "仅信息"
            print(f"  exit={r['exit']}  [{tag}]  {r['script']}")
    if rep["run_failures"]:
        print(f"\n-- [FAIL] 门禁脚本运行未通过（{len(rep['run_failures'])} 个）")
        print("   注：'实现了这条判据'与'这条判据被满足'是两件事——")
        print("       只要不把运行退出码计入 verdict，门禁就会被一个'存在但失败'的脚本骗过。")
        for r in rep["run_failures"]:
            print(f"  [FAIL] {r['script']}  exit={r['exit']}")
            print(f"      tail: {r['tail'][-160:]!r}")
    if rep["non_gated_nonzero_runs"]:
        print(f"\n-- 非门禁脚本的非零退出（{len(rep['non_gated_nonzero_runs'])} 个，"
              f"**不计入 verdict**）")
        print("   这些是被文档当作命令行工具提到的脚本，裸跑会以 usage 错误退出；")
        print("   把它们计入 verdict 等于因为'没给它参数'而判交付物失败。")
        for r in rep["non_gated_nonzero_runs"]:
            print(f"  exit={r['exit']}  {r['script']}")
    print("\n" + "=" * 74)
    print(f"verdict={rep['verdict']}")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(rep, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
        print(f"报告已写入: {args.json_out}")
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
