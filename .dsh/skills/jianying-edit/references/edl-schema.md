# EDL —— 剪辑决策对象规范

EDL（Edit Decision List）是这个 skill 的**核心协议**。它是 Skill、工具、评测、剪映草稿之间的
唯一稳定接口：模型负责产出 EDL，工具负责把 EDL 执行成草稿，评测负责判断 EDL 是否合规。

设计原则：**EDL 里不出现任何剪映专有概念**。换剪辑工具时，只换执行层，EDL 不动。

---

## 时间单位

**EDL 中所有时间一律用「秒」，浮点数。** 例如 `3.5` 表示 3.5 秒。

> ⚠️ 这是刻意的约定。执行层必须做单位转换，见下方「已知陷阱」。

---

## 顶层结构

```jsonc
{
  "version": "1.0",
  "project": "sample-001",              // 草稿名
  "canvas": {
    "width": 1080,
    "height": 1920,
    "fps": 30
  },
  "style_ref": "default",               // 引用 references/ 中的风格规则集
  "target_duration_s": 45,
  "tracks": [ ... ],                    // 轨道定义，顺序即层级
  "clips":  [ ... ],                    // 音视频片段
  "texts":  [ ... ],                    // 字幕/文字
  "audio":  { ... },                    // 全局音频意图
  "qa":     { ... }                     // 验收要求
}
```

## tracks —— 轨道

```jsonc
{ "type": "video", "name": "main" }
```

- `type`：`video` / `audio` / `text` / `sticker` / `effect` / `filter`
- `name`：轨道名，`clips` / `texts` 通过它引用轨道
- **顺序即层级**：数组靠后的轨道在上层（前景）。所以通常 `video` 在前、`text` 在后。

## clips —— 音视频片段

```jsonc
{
  "id": "c2",
  "track": "main",
  "source": "raw/cam_a.mp4",     // 相对 EDL 文件所在目录，或绝对路径
  "source_in": 1.0,              // 取素材内部起点（秒），默认 0
  "start": 3.0,                  // 落在时间线上的起点（秒）
  "duration": 3.0,               // 持续时长（秒）
  "role": "body",                // hook / body / reaction / broll / ending
  "rule_id": "BODY-01",          // 依据哪条规则做的决定
  "reason": "切入过程展示",       // 人话解释，供审阅和复盘
  "confidence": 0.81,
  "volume": 1.0,
  "speed": 1.0,
  "transition": { "type": "信号故障", "duration": 0.5 }
}
```

### 转场语义（重要）

`transition` 写在片段上，含义是 **「进入本片段的转场」**，也就是本片段与前一个片段之间的过渡。

> 剪映内部把转场**存储在前一个片段**上。执行层负责这个映射，EDL 层不需要关心。
> 第一个片段带 `transition` 是无效的，执行层会忽略并告警。

### 字段必填性

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 片段唯一标识，便于审阅时定位 |
| `track` | 是 | 必须是 `tracks` 中已定义的 name |
| `source` | 是 | 素材路径，执行层会校验存在性 |
| `start` / `duration` | 是 | 秒，`duration` 必须为正 |
| `rule_id` / `reason` | **强烈建议** | 缺失会导致决策无法复盘，评测扣分 |
| `source_in` | 否 | 默认 0 |
| `speed` | 否 | 非 1.0 时注意 `duration` 应为变速后的时长 |

## texts —— 字幕/文字

```jsonc
{
  "id": "t1",
  "track": "caption",
  "content": "关键词上屏",
  "start": 0.5,
  "duration": 2.5,
  "style": {
    "size": 10.0,
    "bold": true,
    "color": [1.0, 0.9, 0.2],
    "transform_x": 0.0,
    "transform_y": -0.8
  }
}
```

- `color` 是归一化 RGB，取值 `0.0–1.0`
- `transform_x` / `transform_y` 是画面归一化坐标，`-0.8` 约在画面下方

## audio / qa

```jsonc
"audio": { "voice_priority": "high", "bgm_volume": 0.25 },
"qa": { "required": ["duration-valid", "no-black-frame", "audio-present"] }
```

---

## 验证

任何 EDL 在生成草稿前都应该先跑校验：

```bash
python scripts/edl_to_draft.py <edl.json> --dry-run
```

校验内容：轨道引用是否存在、素材文件是否存在、时间字段类型与取值、文本内容是否为空。

---

## 已知陷阱（都是实际踩过的）

这两条如果不注意，会生成**表面正常但内容全错**的草稿，剪映打开后才会发现。

### 1. 时间必须带单位后缀

`pyJianYingDraft.time_util.tim()` 对**裸 int/float 按微秒解释**，只有字符串才按秒解析：

```python
tim(0.5)      # -> 0        ← 0.5 微秒取整为 0，亚秒精度丢失
tim("0.5s")   # -> 500000   ← 正确
```

所以执行层一律用 `f"{seconds}s"` 形式。曾因此生成出时长 3 微秒的片段。

### 2. 转场必须在入轨前挂好

`ScriptFile.add_segment()` **只在入轨那一刻**把 `segment.transition` 登记进
`materials.transitions`。如果先入轨、之后再给前序片段补转场，转场素材不会写入草稿。

正确顺序：**构造全部片段 → 挂转场 → 统一入轨**。
