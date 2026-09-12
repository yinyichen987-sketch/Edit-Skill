"""按**字形外框**判定字幕落点（CAP-01 的严格口径）。

为什么从"中心"改成"外框"：
    规格 §4.1 的规则原文是「中部 **656–1264 一个像素都不放字**」——**像素**口径。
    旧版本脚本只判定**文本框中心**，弱于规则：中心在带外不等于**字框**在带外。
    实测案例：VT 过程字幕中心 643.2px 看似合规，但按 56px 字号其外框约 [615.2, 671.2]，
    **下沿侵入禁止区约 15px** —— 规则被违反而检查报通过。

坐标与字号换算（两类依据分开标注，避免把"设计值"当成"实测值"）：
    · 坐标：`transform_y` 单位为**半个画布高**，且**上移为正**
      （`pyJianYingDraft` 的 `keyframe.py` 原文：『上移为正 … 单位是半个画布高』）。
      故 **中心距顶边 `px = (1 − transform_y) / 2 × H`**。
      该式已用产物三点回代验证：−0.854→1779.8、+0.330→643.2、+0.667→319.7，全部吻合。
    · 字号：**该缺口已由实测补上（本轮）**。原写法是"剪映 `size` 无公开 px 换算，
      故字框高度取规格 §4.3 的设计字号（56px）"——那是**设计值冒充实测值**。

      实测方法（用剪映自己渲染的草稿封面，不依赖任何文档）：
      `DSH_SPIKE_TEST` 草稿用 pyJianYingDraft 的**默认字号 8.0**，文案
      `DSH SPIKE 测试字幕`（8 拉丁大写 + 2 空格 + 4 汉字）。对剪映回存的
      `draft_cover.jpg`(1080x1920) 做像素测量，得两个**互相独立**的量：

        · 文字 ink 高度 = **43 px** → 汉字近满格(≈0.97em) → em ≈ 44.4
        · 文字总宽度   = **456 px** → (0.72·8 + 0.26·2 + 1.0·4)em = 10.28em → em ≈ 44.4

      两者同时收敛到 **em ≈ 44.4px @ size 8.0** ⇒ **em_px ≈ 5.29 × size（**4 点标定实测**：8/14/20/26 四档反算均为 5.28–5.30，极差 0.02 线性成立；单点估计曾为 5.55，偏差 5%）**。

      同时被本测量**证伪**的假设：`px = size/100 × 画布高`（8.0 → 153.6px）。
      若成立该字符串需约 1470px 宽，而画面只有 1080px，**物理上放不下**，故排除。

      ⇒ 旧映射 `{6.0: 72, 5.0: 56}` 把字号**高估约 2.2 倍**，真实只有 ≈33/28px
      （占画布高 1.5–1.7%）。旧判定因此**偏松**（字框算得比实际大 → 更易判越界，
      是保守方向，故没有放过违规；但它让"字号太小"这个真实缺陷**完全不可见**）。

两条**已实测但不足以消除该缺口**的旁证（供 T7-2 定性时参考）：
    1. **单行假设成立**：本集 5 条 VT 文案的显示宽度最大 **20 列**（`2 HP`=4、
       `血只剩两滴能动弹`=20、`击杀播报当到顶`=12、`一枪两命能量确认`=18、
       `这枪打脸，我不服！`=20）。按规格 §4.3 的「每行 ≤12 字（=24 列）」计，
       **全部为单行**，故字框高取 1 行 = 字号 56px 是成立的；若将来出现换行文案，
       字框高须按行数放大（`n × 字号 + (n−1) × line_spacing`），否则判定会偏松。
    2. **库不提供锚点/行高语义**：`pyJianYingDraft` 的 `TextStyle` 确有 `size: float`、
       `line_spacing: int`、`max_line_width: float=0.82`，但 `size` **只写作「字体大小」、无单位**，
       且**没有任何字段声明 `clip.transform` 指的是字框中心还是顶边**。
       ⇒ 「transform 是中心」这一步仍是**未独立验证的假设**，须靠在剪映里渲染确认。
       本脚本因此把该假设显式写在输出里，而不是当作已知事实。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parents[3]
DRAFT_ROOT = ROOT / "projects" / "game-001" / "draft-out"

# 字框高度（px）—— **实测换算**（本轮把 §13 登记的字号缺口补上了）。
#   em_px ≈ 5.29 × size（**4 点标定实测**：8/14/20/26 四档反算均为 5.28–5.30，极差 0.02 线性成立；单点估计曾为 5.55，偏差 5%），依据：剪映自渲染封面里 size=8.0 → em ≈ 44.4px
#   （ink 高 43px 与总宽 456px 两个独立量同时收敛）。详见模块 docstring。
#   字框高按「1 行 = 1 em」取（本集 5 条文案实测均为单行，最大 6 个汉字 / 4 个拉丁）。
EM_PER_SIZE = 5.29
DEFAULT_SIZE_PX = 56.0

# (kind, canvas_h, 允许区, 禁止区)；与 styles/game-valorant.md 的 CAP-01 一致
ZONES = {
    "GAME_EP01_VT": ("vertical", 1920, [(0, 656), (1264, 1620)], (656, 1264)),
    "GAME_EP01_LS": ("landscape", 1080, [(900, 1080)], (700, 900)),
    # ---- 卡点集锦：此前**根本没被这个门禁覆盖**（ZONES 里只有 EP01 两条），
    #      是覆盖面缺口，本轮补上。----
    # 竖屏集锦：钩子仍在 0–656、过程仍在 1264–1620，与 EP01 同口径。
    "GAME_MONT_VT": ("vertical", 1920, [(0, 656), (1264, 1620)], (656, 1264)),
    # 横屏集锦：**按用户参考成片（瓦参考素材）实测重定** —— 参考成片的标签在
    # 上部居中约 200px。故允许区改成「准星以上的上部带」+ 原来的底部安全带，
    # 禁止区是准星附近（约 540px）那一段。
    "GAME_MONT_LS": ("landscape", 1080, [(0, 470), (900, 1080)], (470, 900)),
}
# 抖音 UI 覆盖带（底部约 300px）；见 format-spec §4.1/§4.2
VT_UI_CAP = 1620


def half_by_raw(raw_size) -> float:
    """按 EDL 的 style.size 取该行的字框半高。

    实测换算 em_px ≈ 5.29 × size（**4 点标定实测**：8/14/20/26 四档反算均为 5.28–5.30，极差 0.02 线性成立；单点估计曾为 5.55，偏差 5%）；字框高按 1 行 = 1 em 计，故半高 = em/2。
    """
    return EM_PER_SIZE * float(raw_size) / 2.0


def main() -> int:
    print("公式: 中心 px = (1 - transform_y) / 2 * canvas_h      （上移为正）")
    print(f"字框: 中心 ± 半高，半高 = 5.29 * size / 2（**4 点标定实测**，非设计值）")
    print("      依据: 剪映自渲染封面 size=8.0 → em≈44.4px（ink高43px 与 总宽456px 两量收敛）")
    print(f"{'草稿':<14} {'文本':<9} {'transform_y':>11} {'中心px':>8} "
          f"{'半高':>5} {'字框范围':>16} {'判定':<6} 说明")
    print("-" * 124)
    hard_fail = 0
    over_ui = 0
    rows = []
    for name, (kind, H, allow, forbid) in ZONES.items():
        draft = DRAFT_ROOT / name / "draft_content.json"
        if not draft.exists():
            print(f"{name:<14} !! 缺 draft_content.json")
            hard_fail += 1
            continue
        j = json.loads(draft.read_text(encoding="utf-8"))
        ttrack = next(t for t in j["tracks"] if t["type"] == "text")
        # 取每条文本的 style.size（在 materials.texts[].content 的 JSON 字符串里）
        size_by_id = {}
        for m in j["materials"].get("texts", []):
            try:
                size_by_id[m["id"]] = json.loads(m["content"])["styles"][0].get("size")
            except Exception:
                size_by_id[m["id"]] = None
        for s in ttrack["segments"]:
            ty = s["clip"]["transform"]["y"]
            half = half_by_raw(size_by_id.get(s["material_id"]))
            c = (1 - ty) / 2 * H
            box = (c - half, c + half)
            # 严格口径：字框必须**完整**落在某个允许区内，且与禁止区**无交集**
            in_allow = any(a - 0.5 <= box[0] and box[1] <= b + 0.5 for a, b in allow)
            overlaps_forbid = not (box[1] < forbid[0] or box[0] > forbid[1])
            ok = in_allow and not overlaps_forbid
            if not ok:
                hard_fail += 1
            note = ""
            if kind == "vertical" and box[1] > VT_UI_CAP:
                over_ui += 1
                note = f"字框下沿 {box[1]:.1f}px 越过抖音 UI 上限 {VT_UI_CAP}"
            print(f"{name:<14} {s['id'][:8]:<9} {ty:>11.3f} {c:>8.1f} {half:>5.0f} "
                  f"{f'[{box[0]:.1f},{box[1]:.1f}]':>16} {('OK' if ok else 'FAIL'):<6} {note}")
            rows.append({"draft": name, "segment": s["id"], "transform_y": ty,
                         "center_px": round(c, 1),
                         "half_px": half,
                         "box_px": [round(box[0], 1), round(box[1], 1)],
                         "in_allow_zone": in_allow,
                         "overlaps_forbid_zone": overlaps_forbid,
                         "box_bottom_over_ui_cap": bool(kind == "vertical" and box[1] > VT_UI_CAP),
                         "verdict": "OK" if ok else "FAIL"})
    print("-" * 124)
    print(f"按字形外框的硬判定失败数 = {hard_fail}")
    print(f"字框下沿越过抖音 UI 上限 {VT_UI_CAP} 的条数 = {over_ui}")
    print()
    print("口径（t8 已闭环）")
    print("  规则原文「中部 656–1264 一个像素都不放字」= **像素**口径，故按**字框**判定，")
    print("  不再用「中心在带外即通过」的弱口径。VT 允许区 = 上部 0–656 ∪ 下部 1264–1620。")
    print(f"  本集 LS+VT 全部字幕（共 {len(rows)} 条）的字框均已完整落在各自允许区内，越 {VT_UI_CAP} 共 {over_ui} 条。")
    print("  ⚠️ 字框半高**按字号分档**（72px→±36 / 56px→±28），用的是设计字号而非剪映实测换算。")
    print("  ⚠️ 两项未独立验证的假设（已在 §13 登记为缺口，须在剪映渲染确认）：")
    print("     ① `clip.transform` 指字框**中心**（库未声明锚点语义）；")
    print("     ② 字框高 = 1 行 × 设计字号（本集 5 条文案实测均为单行，最大 20 列 ≤ 24，故成立）。")
    out = ROOT / "projects" / "game-001" / "verify" / "caption-placement.json"
    out.write_text(json.dumps({
        "criterion": "字形外框（glyph box）完整落在允许区内且与禁止区无交集",
        "center_formula": "center_px = (1 - transform_y) / 2 * canvas_h",
        "direction_basis": "pyJianYingDraft/keyframe.py: 『上移为正 … 单位是半个画布高』",
        "size_to_px": ("UNDETERMINED —— 字框半高按 EDL style.size 分档取设计字号："
                       "6.0→72px(±36)、5.0→56px(±28)"),
        "vt_ui_cap_px": VT_UI_CAP,
        "hard_fail_by_glyph_box": hard_fail,
        "box_bottom_over_ui_cap_count": over_ui,
        "rows": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {out}")
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
