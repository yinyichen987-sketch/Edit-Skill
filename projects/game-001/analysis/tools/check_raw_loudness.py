"""raw/ 产物自查：扫出响度相关字段的异常残留。

判定规则（不靠肉眼）：
  * integrated_loudness_lufs == -70.0  → 残留 bug（ebur128 进度行地板值）
  * loudness_range_lu == 0.0           → 残留 bug
  * integrated_loudness_lufs 为 None   → 缺测
  * 出现「高 true peak（>0 dBFS）却极低响度」的矛盾组合 → 重点标记
退出码：有残留=1，干净=0
"""
import glob
import json
import os
import sys

# Windows 默认控制台为 GBK，本脚本打印 ✓ / ✅ / ⚠️ 等符号会在中途抛 UnicodeEncodeError；
# 且崩溃退出码(1)与「发现残留」的失败码(1)相同，会被误读为「检查未通过」。统一改为 UTF-8。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

BAD_LOUDNESS = -70.0
EXPECTED = {"a": (-12.9, 4.4), "b": (-14.6, 12.8), "c": (-15.2, 12.2)}

problems = []
checked = 0

for f in sorted(glob.glob("projects/game-001/analysis/raw/*.json")):
    base = os.path.basename(f)
    try:
        d = json.load(open(f, encoding="utf-8"))
    except Exception as e:
        problems.append((base, "-", f"无法解析: {e}"))
        continue

    if not isinstance(d, dict):
        continue  # fps_probe.json 等非音频产物是数组，跳过
    aud = d.get("audio")
    if not isinstance(aud, dict) or not aud.get("has_audio"):
        continue
    checked += 1

    lufs = aud.get("integrated_loudness_lufs")
    lra = aud.get("loudness_range_lu")
    tp = aud.get("true_peak_dbfs")

    if lufs == BAD_LOUDNESS:
        problems.append((base, "integrated_loudness_lufs", f"= {lufs}（ebur128 进度行残留）"))
    if lra == 0.0:
        problems.append((base, "loudness_range_lu", f"= {lra}（残留）"))
    if lufs is None:
        problems.append((base, "integrated_loudness_lufs", "缺失"))
    if tp is not None and lufs is not None and tp > 0 and lufs < -40:
        problems.append((base, "矛盾", f"峰值 {tp} dBFS 偏高却响度仅 {lufs} LUFS"))

    key = base[0]
    exp = EXPECTED.get(key)
    note = ""
    if exp and lufs is not None and lra is not None:
        ok = abs(lufs - exp[0]) < 0.05 and abs(lra - exp[1]) < 0.05
        note = "✅ 与实测真值一致" if ok else f"⚠️ 期望 {exp}，实得 ({lufs}, {lra})"
        if not ok:
            problems.append((base, "真值不符", note))
    print(f"{base:22} I={lufs:>8}  LRA={lra:>6}  TP={tp:>5}  {note}")

print(f"\n检查了 {checked} 个含音频的产物文件")
if problems:
    print("!! 发现残留/异常：")
    for p in problems:
        print("   ", p)
    sys.exit(1)
print("✅ 干净：无 -70.0 / 无 LRA=0.0 / 无峰值-响度矛盾 / 全部与真值一致")
sys.exit(0)
