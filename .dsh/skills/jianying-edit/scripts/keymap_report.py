#!/usr/bin/env python3
"""报告本机剪映（JianYingPro）当前生效的键位方案。

为什么需要这个脚本：剪映内置多套键位方案，同一功能在不同方案下是**不同的键**
（例如「分割」在 Premiere 风格方案里是 Ctrl+K，在 Final Cut Pro X 方案里是 Ctrl+B）。
所以任何「剪映快捷键」的说法都必须同时给出方案名，否则就是错的。
详见 references/operations.md §2。

用法::

    python keymap_report.py                     # 当前方案 + 各方案概览
    python keymap_report.py --compare           # 只列各方案之间**不一致**的命令
    python keymap_report.py --keymap "Premiere Pro"   # 打印某一方案的完整键位
    python keymap_report.py --command cutoff    # 追一个命令在各方案下的键
    python keymap_report.py --json              # 机器可读输出

退出码：0 = 正常；1 = 没找到键位文件；2 = 用法错误。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# 约定：所有 CLI 脚本都显式 UTF-8 输出，避免 Windows GBK 控制台把正常输出变成
# UnicodeEncodeError，从而与「检查未通过」的退出码混淆。见 docs/lessons.md 第 14 条。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover - 老解释器/被重定向
        pass

# 命令 ID → 中文含义。只列操作层会真正用到的，其余保持原样输出。
COMMAND_LABELS = {
    "cutoff": "分割",
    "batchCut": "批量分割",
    "cutLeft": "向左裁剪",
    "cutRight": "向右裁剪",
    "del": "删除片段",
    "undo": "撤销",
    "redo": "重做",
    "exportVideo": "导出",
    "importMedia": "导入媒体",
    "newProject": "新建草稿",
    "speedPlayBackward": "反向播放",
    "speedPlayPause": "暂停",
    "speedPlayForward": "正向播放",
    "togglePlay": "播放/暂停",
    "prevFrame": "上一帧",
    "nextFrame": "下一帧",
    "largePreFrame": "大步后退",
    "largeNextFrame": "大步前进",
    "prevCutPoint": "上一分割点",
    "nextCutPoint": "下一分割点",
    "locateFirstFrame": "跳到首帧",
    "locateLastFrame": "跳到末帧",
    "scrollTrackScale": "时间线缩放",
    "scrollTrackH": "时间线横向滚动",
    "scrollTrackV": "时间线纵向滚动",
    "zoomIn": "轨道放大",
    "zoomOut": "轨道缩小",
    "adsorb": "自动吸附",
    "mainTrackAdsorb": "主轨磁吸",
    "linkage": "联动",
    "preview": "预览轴",
    "segmentTrimGap": "修剪间隙",
    "segmentMakeGroup": "创建组合",
    "segmentRemoveGroup": "解除组合",
    "segmentCombination": "新建复合片段",
    "segmentRemoveCombination": "解除复合片段",
    "activeSpeedControl": "变速面板",
    "divideSpeedSegment": "曲线变速切分",
    "addKeyframe": "添加关键帧",
    "addBasicKeyframe": "添加基础关键帧",
    "expandKeyframePanel": "关键帧面板",
    "storeSingelFrame": "定格",
    "mark": "添加标记",
    "markWithAnotherColor": "标记(另一颜色)",
    "markBeat": "手动踩点",
    "smartExtend": "智能扩展",
    "roughCutHead": "粗剪头",
    "roughCutTail": "粗剪尾",
    "selectRangeStart": "选区起点",
    "selectRangeEnd": "选区终点",
    "selectRangeBySegment": "以片段定选区",
    "cancelRangeSelect": "取消选区",
    "switchToSelect": "鼠标选择模式",
    "switchToCut": "鼠标分割模式",
    "toggleSegmentVisibe": "启用/停用片段",
    "toggleVideoAudio": "分离/还原音频",
    "showFullscreen": "全屏(编辑区)",
    "toggleFullscreen": "全屏预览",
    "subtitleSplit": "字幕拆分",
    "subtitleNewLine": "字幕折行",
    "switchTab": "切换素材面板",
    "voiceUp": "音量+",
    "voiceDown": "音量-",
    "tracksHeightUp": "轨道变高",
    "tracksHeightDown": "轨道变矮",
    "agentToggleInput": "唤起 AI 输入",
    "disableAlignment": "临时取消对齐(按住)",
    "autoWrap": "自动换行(Alt+左键)",
}

# 键位方案的展示顺序：先内置方案，再自定义槽位。
PRESET_ORDER = ["Final Cut Pro X", "Premiere Pro", "Custom1", "Custom2", "Custom3"]


def default_config_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / "JianyingPro" / "User Data" / "Config"


def load_keymaps(shortcut_dir: Path) -> dict[str, dict[str, list[str]]]:
    maps: dict[str, dict[str, list[str]]] = {}
    for path in sorted(shortcut_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"!! 跳过 {path.name}: {exc}", file=sys.stderr)
            continue
        name = data.get("name") or path.stem
        maps[name] = data.get("sequence") or {}
    return maps


def read_current_index(config_dir: Path) -> int | None:
    """keymapSettings 是个 ini，形如 ``currentKeymapIndex=0``。"""
    path = config_dir / "keymapSettings"
    if not path.exists():
        return None
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if line.lower().startswith("currentkeymapindex"):
            _, _, value = line.partition("=")
            try:
                return int(value.strip())
            except ValueError:
                return None
    return None


def ordered_names(maps: dict[str, dict[str, list[str]]]) -> list[str]:
    known = [n for n in PRESET_ORDER if n in maps]
    return known + [n for n in maps if n not in known]


def fmt_keys(keys: list[str]) -> str:
    visible = [k for k in keys if k]
    return " / ".join(visible) if visible else "(无默认快捷键)"


def cmd_overview(maps: dict[str, dict[str, list[str]]], index: int | None) -> None:
    names = ordered_names(maps)

    print("剪映键位方案报告")
    print("=" * 62)
    print(f"当前索引     : {index if index is not None else '(读不到 keymapSettings)'}")
    print("当前方案     : **无法从索引直接映射** —— 剪映没有把『索引→方案名』写进任何可读文件。")
    print(f"               已知方案顺序（来自 VECreator.dll 字符串表，仅供参考）：{' → '.join(names)}")
    print()
    print("⚠ 所以本脚本**不会**替你断言当前是哪套方案。要确定它，只能在剪映里打开")
    print("  快捷键设置面板看方案名。在那之前，引用快捷键必须同时给出方案名。")
    print()
    print("各方案在此功能上的取值（★ = 各方案不一致，引用时必须带上方案名）")
    print("-" * 62)
    for cmd in ("cutoff", "exportVideo", "cutLeft", "cutRight", "adsorb",
                "mainTrackAdsorb", "linkage", "zoomIn"):
        values = {name: fmt_keys(maps[name].get(cmd, [])) for name in names}
        differs = len(set(values.values())) > 1
        mark = "★" if differs else " "
        label = COMMAND_LABELS.get(cmd, "")
        print(f"{mark} {cmd:<18}{label:<14}", end="")
        for name in names:
            print(f" | {name}={values[name]}", end="")
        print()


def cmd_compare(maps: dict[str, dict[str, list[str]]]) -> None:
    names = ordered_names(maps)
    if len(names) < 2:
        print("少于两套方案，无法比较。")
        return
    base = names[0]
    all_cmds = sorted({c for m in maps.values() for c in m})
    rows = []
    for cmd in all_cmds:
        values = [fmt_keys(maps[n].get(cmd, [])) for n in names]
        if len(set(values)) > 1:
            rows.append((cmd, values))

    print(f"各方案差异（基准 = {base}，共 {len(rows)} 个命令不一致 / 总 {len(all_cmds)} 个）")
    print("-" * 62)
    header = f"{'命令':<22}{'含义':<16}" + "".join(f"{n:<18}" for n in names)
    print(header)
    for cmd, values in rows:
        label = COMMAND_LABELS.get(cmd, "")
        print(f"{cmd:<22}{label:<16}" + "".join(f"{v:<18}" for v in values))


def cmd_dump(maps: dict[str, dict[str, list[str]]], name: str) -> int:
    if name not in maps:
        print(f"没有名为 {name!r} 的方案。可用：{', '.join(ordered_names(maps))}", file=sys.stderr)
        return 2
    print(f"# {name}")
    for cmd in sorted(maps[name]):
        label = COMMAND_LABELS.get(cmd, "")
        print(f"{cmd:<24}{label:<16}{fmt_keys(maps[name][cmd])}")
    return 0


def cmd_command(maps: dict[str, dict[str, list[str]]], cmd: str) -> int:
    hit = False
    label = COMMAND_LABELS.get(cmd, "")
    print(f"{cmd}  {label}")
    for name in ordered_names(maps):
        if cmd in maps[name]:
            hit = True
            print(f"  {name:<20}{fmt_keys(maps[name][cmd])}")
    if not hit:
        print(f"  没有任何方案包含命令 {cmd!r}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="报告本机剪映当前生效的键位方案（同一功能在不同方案下键位不同）")
    parser.add_argument("--dir", type=Path, default=None,
                        help="Config 目录（默认 %%LOCALAPPDATA%%\\JianyingPro\\User Data\\Config）")
    parser.add_argument("--compare", action="store_true", help="只列各方案不一致的命令")
    parser.add_argument("--keymap", metavar="NAME", help="打印某个方案的完整键位")
    parser.add_argument("--command", metavar="CMD", help="追一个命令在各方案下的键")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = parser.parse_args()

    config_dir = args.dir or default_config_dir()
    shortcut_dir = config_dir / "Shortcut"
    if not shortcut_dir.is_dir():
        print(f"找不到键位目录：{shortcut_dir}", file=sys.stderr)
        print("提示：用 --dir 指定剪映的 Config 目录，或确认本机装的是剪映专业版。", file=sys.stderr)
        return 1

    maps = load_keymaps(shortcut_dir)
    if not maps:
        print(f"{shortcut_dir} 下没有可解析的键位 json。", file=sys.stderr)
        return 1

    index = read_current_index(config_dir)

    if args.json:
        payload = {
            "config_dir": str(config_dir),
            "current_keymap_index": index,
            "keymaps": maps,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"# 键位目录: {shortcut_dir}")
    print()
    if args.keymap:
        return cmd_dump(maps, args.keymap)
    if args.command:
        return cmd_command(maps, args.command)
    if args.compare:
        cmd_compare(maps)
        return 0
    cmd_overview(maps, index)
    print()
    print("用 --compare 看全部差异，--keymap <名字> 看完整键位，--command <命令ID> 追单个命令。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
