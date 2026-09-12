# draft-audit —— EDL 与剪映草稿的独立审计器

t5 审阅用。回答两个问题，且**不采信任何报告里的数字**——全部自己解析文件得出。

- 脚本：`audit_draft.py`
- 用法：见下方「运行」
- 已做**双向**自证：正例（已知正确的夹具）判 PASS，反例（故意改坏）判 FAIL

生成日期：2026-09-12 ｜ 作者：creative-reviewer

---

## 1. 为什么需要它

`edl_to_draft.py`（执行层）自己也会做校验，但**执行层不能审自己**：

- 它校验的是「EDL 是否合法」，不校验「生成的草稿是否真的等于 EDL」。
- 报告里写的片段数、时间码、转场数都是**第一方自述**。t5 的价值在于用第二份独立实现去对账。
- 本项目已确认两处**静默失效**点，只有拿草稿实际内容比对才能发现：

| 陷阱 | 现象 | 本审计器的判定 |
|---|---|---|
| `tim()` 裸数字按微秒解释 | 生成出**微秒级**片段（如 3µs），草稿表面正常 | `B5-timeline`：timerange != round(秒×1e6)，或数值 < 1000 时额外标注「疑似 tim() 微秒陷阱」 |
| 转场必须在入轨前挂好 | 先入轨后挂转场 → `materials.transitions` 丢失，剪映里看不到转场 | `B7-transition` + `B8-transition-count`：核对转场数量**与归属** |

---

## 2. 检查项

### A. EDL 自身可执行性

| ID | 检查 |
|---|---|
| `A1-source` | 素材文件存在（相对路径按 EDL 所在目录解析） |
| `A2-duration` | `duration` 为正 |
| `A3-bounds` | `source_in + duration` 不超出素材**视频流**时长 |
| `A3-frames` | （info）素材帧数与按帧推算的内容末点，供人工判断是否贴边 |
| `A4-track` | 片段引用的轨道已定义 |
| `A5-transition-name` | 转场名存在于 `pyJianYingDraft.TransitionType` 枚举（写错会被静默跳过） |
| `A6-first-transition` | 首片段带转场 → 告警（EDL 语义下无效） |
| `A7-overlap` / `A7-gap` | 同轨道片段重叠 / 留缝（留缝在剪映里会黑） |
| `A8-text-track` | 文本引用的轨道已定义 |

### B. 草稿 vs EDL（核心）

| ID | 检查 |
|---|---|
| `B0-draft` | 草稿存在且 `draft_content.json` 是**明文 JSON** |
| `B1-canvas` | `canvas_config` 与 EDL canvas 一致 |
| `B2-fps` | fps 一致 |
| `B3-tracks` | 轨道数、名、类型、**顺序**一致 |
| `B4-count` | 每轨道片段数一致 |
| `B5-timeline` | 每片段 `target_timerange` == `round(start×1e6)` / `round(duration×1e6)`（**微秒**） |
| `B6-source` | 每片段 `source_timerange` == `round(source_in×1e6)` / `round(duration×1e6)` |
| `B7-transition` | **归属**核对：剪映把转场存在**前一个**片段上，故草稿 `segs[j]` 的转场属于 EDL `items[j+1]` |
| `B7b-transition-dur` | 转场时长一致 |
| `B8-transition-count` | 草稿转场素材数 == EDL 非首片段声明的转场数 |
| `B9-texts` | 文本段数一致 |
| `B10-duration` | 草稿 `duration` == 时间线末点 |

---

## 3. 运行

```bash
cd "C:\Users\18930\Desktop\Edit skill"

# 正例自测：用 spike 夹具验证审计器在已知正确的草稿上判 PASS
.venv/Scripts/python.exe projects/game-001/verification/draft-audit/audit_draft.py --selftest

# 反例自测：故意改坏，验证审计器真的会失败
.venv/Scripts/python.exe projects/game-001/verification/draft-audit/audit_draft.py --negtest

# 实际审计（草稿默认在剪映草稿根目录，可用 --draft-root 指向工作区内目录）
.venv/Scripts/python.exe projects/game-001/verification/draft-audit/audit_draft.py \
    --edl projects/game-001/edl/ep01.json --draft GAME_EP01_LS \
    --json-out projects/game-001/verification/draft-audit/ep01-LS.json
```

退出码：`0` = PASS（无 error），`1` = FAIL。告警（warn）不影响退出码。

---

## 4. 自证结果（2026-09-12）

### 正例：`spike/sample-edl.json` → 草稿 `DSH_EDL_TEST`

```
[ ok ] B1-canvas              画布一致: 1080x1920
[ ok ] B2-fps                 fps 一致: 30
[ ok ] B3-tracks              轨道名/类型/顺序一致
[ ok ] B5-timeline            c1: target 0.0s/3.0s 与 EDL 精确一致
[ ok ] B6-source              c2: source_in 1.0s → 1000000µs 正确
[ ok ] B7-transition          EDL c2 的转场 '信号故障' 正确挂在草稿 seg[0]（c1）上，
                              转场素材 name='信号故障' duration=500000µs
[ ok ] B9-texts               文本段数一致: 1
=> PASS
```

### 反例：故意改坏，5/5 被拦下

| 反例 | 期望命中 | 实际报出 |
|---|---|---|
| `us-trap`（duration 改成 3µs） | `B5-timeline` | `dur=3 vs 期望 dur=3000000 ← 疑似 tim() 微秒陷阱` |
| `transition-dropped`（删 seg[0] 的转场引用） | `B7-transition` | `EDL c2 声明了转场，但草稿 seg[0]（c1）上没有转场素材` |
| `canvas-mismatch`（高度改 1080） | `B1-canvas` | `草稿 1080x1080 vs EDL 1080x1920` |
| `timeline-shift`（seg[1] 起点 +0.5s） | `B5-timeline` | `start=3500000 vs 期望 start=3000000` |
| `edl-out-of-bounds`（source_in 16.0 + dur 3.0） | `A3-bounds` | `19.000s > 视频流时长 18.984s` |

> 最后一条同时独立复现了 `A3-bounds` 的保守口径：硬上界取**视频流时长**（18.984s），
> 比容器/音频时长（19.030s）短约一帧，因此 `source_in=16.0 + duration=3.0` 会被拒绝。

---

## 5. 审计器自身被正例抓到的一个 bug（留档）

第一版 `B7-transition` 用**同下标**比对（查草稿 `segs[i]` 是否带转场，对照 EDL `items[i].transition`），
结果在**已知正确**的夹具上报出两条互相矛盾的错误：

```
[FAIL] B7-transition  c1 是首片段，草稿里却挂了转场（EDL 语义下应被忽略）
[FAIL] B7-transition  c2 的转场 '信号故障' 未落到草稿的前一个片段上
```

真相是**我的映射错了**：剪映把转场存在前一个片段上，所以 `segs[j]` 的转场属于 `items[j+1]`。
改成 `j → j+1` 的映射后全部通过。

**教训**：审计器自己也会犯它要抓的那个错。正例自测不是形式——如果当时只跑反例，
两个错误会正好互相掩盖（一边多报、一边少报），看起来"反例都能抓"。

---

## 6. 已知局限（诚实声明）

1. **只读明文草稿。** 剪映 11.x 原生草稿是加密的，本项目不接入解密（见 `references/environment.md`）。
   本审计器只适用于 pyJianYingDraft 生成的**明文**草稿；遇到加密草稿会在 `B0-draft` 明确报错并说明原因，不会猜。
2. **不验证「剪映能否打开」。** 那只能人工完成（剪映 7+ 也无自动导出）。
3. **不验证画面内容。** 它比的是**数字与结构**，不判断画面是否黑帧、构图是否对、字幕是否压到关键信息。
   这类必须看证据帧或人工预览。
4. **`A3-bounds` 取视频流时长作硬上界**，比真实内容末点保守约一帧（`4b0460c4`：18.984 vs 约 19.000）。
   这是**有意的保守偏置**：宁可误拦贴边片段，也不放过真正越界的。命中该错误时应人工确认差值是否小于一帧。
5. **不校验 `speed != 1.0` 时的时长语义。** EDL 约定 `duration` 为变速后时长，本审计器按此直接比对，
   不额外推算源取用区间。
6. **文本校验覆盖段数、逐条时间码与文案**（`B9-texts` / `B9b-text-time` / `B9c-text-content`），
   但**不校验字号/颜色/位置**是否与规格的落点或禁止区一致——那需要读规格并叠加构图判断，属人工项。
7. **不校验 EDL 的数值是否满足它自己引用的规则。** 本审计器只比对「EDL 写的」与「草稿生成的」是否一致。
   若 EDL 的 `reason` 声称满足某条规则（如距跳变点 ≥0.1s）而数值并不满足，本工具**不会发现**——
   那属于依据链核查，由 t5 人工完成（或由 `projects/game-001/tools/verify_cut_margins.py` 这类专门脚本覆盖）。

---

## 7. 与 scene-cuts 检测器的分工

| 目录 | 回答的问题 |
|---|---|
| `../scene-cuts/` | 素材里**哪里**有真实的瞬时视点跳变（可作天然切点） |
| `./draft-audit/` | 生成的草稿**是否真的等于** EDL，有没有踩微秒/转场登记两个陷阱 |

两者都遵循同一套纪律：**做对照**（正例 + 反例）、**标注下界与偏置**、**把检测器自身的 bug 留档**。
