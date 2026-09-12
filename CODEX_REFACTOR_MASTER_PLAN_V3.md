# AI-director 重构总方案 V3（Codex Harness + Architecture Implementation Brief）

> 目标仓库：`lilmoon1314-cpu/AI-director`
>
> 本文是后续与 Codex 协作的主任务说明。它同时替代旧版 `CODEX_REFACTOR_MASTER_PLAN_V2.md` 中已经过时的 Harness 设计。
>
> 这不是“一次性全部重写”的命令。Codex 必须按小的、可验证的架构切片推进，禁止大爆炸式重构。

---

## 0. Codex 如何使用本文

本文包含两类内容：

1. **R0 Harness 重构目标**：先让编码代理能以更低上下文成本、更明确的状态、更可靠的反馈工作。
2. **R1 之后的产品/后端架构目标**：Agent 拆分、Artifact、Narrative State、Workflow、Production Pipeline 等。

执行优先级：

```text
用户当前明确任务
    ↓
本文对应阶段的目标与边界
    ↓
仓库中的当前事实（代码 / tests / config / Git）
```

如果本文与仓库实际实现不一致：

- 不要猜测；
- 先确认现状；
- 把差异作为 migration fact 报告；
- 除非用户当前任务明确要求，不要顺手修复无关差异。

R0 期间尤其注意：**不要为了建立 baseline 重新运行历史全量 mutation / full benchmark。** 已有 Git、测试文档、日志与历史记录已经足够证明 Harness 成本问题。

---

# 1. 本轮总目标

项目已经证明若干方向有效：模块化单体、项目隔离、作者/角色/观众三视角、HTML 分段文档、Agent 只读检索工具、propose→confirm 两段式写入、SQLite 本地优先。

本轮不是推翻项目，而是解决四个瓶颈：

1. **Harness 上下文与维护成本过高**：同一事实散落在大量相似 Markdown、脚本常量和历史记录中，Agent 冷启动时需要阅读和比对过多上下文。
2. **模块边界与实现边界不一致**：`backend/app/agent/service.py` 承担过多职责，导致理解范围、测试范围和修改风险膨胀。
3. **数据模型不足以稳定承载长篇连续性**：状态缺少时间、来源、知识视角和可追溯变化链。
4. **产品需要从世界观工作台升级为长漫剧生产系统**：Project → Series → Episode → Scene → Screenplay → Production → Shot → Timeline，并支持局部修改、影响分析、stale 与回滚。

---

# 2. 最高级架构原则

## 2.1 Harness 的目标不是“更多文档”，而是降低 Agent 的恢复成本

Harness 的核心目标：

> 一个新的 Codex session 能用最少的无关上下文，快速恢复到“知道项目是什么、当前该做什么、该读什么、不能做什么、如何证明完成”的状态。

因此所有 Harness 设计遵循：

- **Map, not manual**：常驻指令是地图，不是百科全书。
- **Repository as system of record**：当前事实尽量从代码、配置、测试、结构化状态和 Git 得到，而不是复制成多份叙事文档。
- **Progressive disclosure**：先读小入口，再按任务逐层读取相关知识；仓库中“存在”不等于“当前上下文必须加载”。
- **One fact, one owner**：每类事实只有一个权威 owner。
- **Guidance ≠ enforcement**：Agent 指令负责行为引导；lint、type、architecture checks、DB constraints、tests、CI 才负责机器强制。
- **State must survive sessions**：复杂工作的进度、发现和决策必须有明确的跨会话状态载体。
- **Feedback must be proportional to risk**：验证追求“最小但充分的完成证据”，不是固定仪式化地跑所有检查。

这些原则来自并优先对齐：

- OpenAI, *Harness engineering: leveraging Codex in an agent-first world*
- Anthropic, *Effective harnesses for long-running agents*
- Walking Labs, *Learn Harness Engineering*（Harness = Instructions + Tools + Environment + State + Feedback）

## 2.2 Agent 的自由度只存在于一个明确任务内部

固定：

```text
Workflow Engine → Context Compiler → Atomic Skill → Validator → Artifact/State Update
```

而不是：

```text
Super Agent → 自己决定下一步 → 自己选工具 → 自己修改多个领域
```

Atomic Skill 不允许直接调用“下一个 Skill”；全局工作流和阶段 gate 位于 LLM 外部。

## 2.3 Skill、Agent、Domain、Tool 四者分离

- **Domain**：Project / Series / Episode / Scene / Block / Entity / State / Shot / Artifact
- **Skill**：一个创作动作，例如 `dialogue.humanize`
- **Tool**：一个确定性动作，例如 `read_entity_state`
- **Agent**：交互/协作外壳，不是领域模型，也不拥有任意路由权

## 2.4 写入永远显式

继续保留 propose/confirm 思路，并扩展为：

```text
Atomic Skill output
→ candidate
→ deterministic validation
→ impact preview
→ user accept
→ commit
```

Agent 不直接覆盖用户已批准内容。

---

# 3. 当前 Harness 的核心问题

当前 Harness 的问题不是单纯“文档太多”或“测试太严格”，而是五个子系统彼此缠绕：

```text
Instructions  指令重复、常驻上下文过重
Tools         task/verify 与 Markdown 互相解析、策略分散
Environment   会话开始/结束存在高成本固定仪式
State         PROGRESS / DECISIONS / features / tests 同时保存重叠状态
Feedback      full check / mutation / review 被绑定到几乎所有功能
```

典型冷启动路径可能变成：

```text
AGENTS.md
→ PROGRESS.md
→ DECISIONS.md
→ root CONSTRAINTS.md
→ root ARCHITECTURE.md
→ backend/ARCHITECTURE.md
→ backend/CONSTRAINTS.md
→ module/ARCHITECTURE.md
→ module/CONSTRAINTS.md
→ docs/testing.md
→ docs/tests/FXX_*.md
→ docs/architecture_checks.md
→ docs/lessons.md / error.jsonl
→ docs/features.md
→ scripts/task.py / verify_feature.py
```

这会带来三类失败：

1. **发现成本**：Agent 花大量 token 判断“该读哪个、哪个更新”。
2. **同步成本**：一次设计变化传播到多份文档，产生 fan-out。
3. **权威性下降**：代码、文档、脚本配置互相重复后，任何一个都可能 stale。

历史 Harness 证据已经足够：F04 说明 mutation 对小型纯规则模块有价值；F08/F10/F13/F14 则证明将 mutation 绑定到大型 orchestration 模块会诱发实现钉死、超长运行、人工复判和测试工具反向塑造代码。R0 不再重新 benchmark 这些历史事实。

---

# 4. Harness V3 目标架构

## 4.1 先按五个 Harness 子系统分责

```text
Instructions
  AGENTS.md

Knowledge
  ARCHITECTURE.md
  docs/design-docs/
  docs/product-specs/
  docs/references/
  docs/generated/

State
  feature_list.json
  docs/exec-plans/active/
  docs/exec-plans/completed/
  Git

Tools / Environment
  existing scripts, package/pyproject config, dev commands, worktree

Feedback
  targeted tests, structural checks, E2E when behavior requires, CI
```

**文档只是 Harness 的一部分。** 不要把 Harness 重构再次变成“创造更多 Markdown”。

## 4.2 `AGENTS.md`：唯一的 always-on Agent 入口

职责：

- 项目极短说明；
- 极少数所有任务都需要的全局约束；
- 工作范围纪律；
- 知识路由；
- 基本开发/验证入口；
- 完成时必须做的最小检查。

它回答：

```text
How should I work here?
Where should I look next?
```

它不保存：当前任务、历史进度、详细架构、模块 API、测试理论、mutation 历史、完整产品功能列表。

目标是保持短、小、稳定；参考 OpenAI 的“约 100 行入口地图”思路，而不是继续发展成大型手册。

Claude/Cursor 等其他编码代理需要兼容时，应尽量复用同一语义来源，不维护一套平行复制的规则正文。

## 4.3 `ARCHITECTURE.md`：当前系统的短地图

职责：

- 当前主要 bounded contexts；
- 关键 ownership；
- 依赖方向；
- 主要数据/控制流；
- 关键入口在哪里。

它回答：

```text
Where is X?
Who owns X?
What may depend on what?
```

它不保存：历史决策、未来 roadmap、逐函数 API、DB 全字段、当前任务、实施步骤、测试历史。

原则：**bird's-eye codemap，不是 atlas。** 如果细节不断增长，应下沉到 design docs，而不是让根地图膨胀。

## 4.4 `docs/design-docs/`：长期、当前有效的设计知识

职责：保存**代码本身无法完整表达，但会影响 Agent 架构判断**的 durable design truth。

建议组织：

```text
docs/design-docs/
  index.md
  core-beliefs.md
  <bounded-design-topic>.md
```

其中：

- `index.md` 只做路由，不复制正文；
- `core-beliefs.md` 保存长期设计原则及理由；
- 领域文档保存当前 canonical design，例如 artifact revision、narrative state、workflow、agent ownership。

禁止把所有复杂模块都塞进一个巨型 `CONTEXT.md`。当一个 topic 变得难以检索时，按 bounded concern 拆分并通过 index 发现。

设计文档描述“现在应该怎样设计”，不是历史日志。

## 4.5 `docs/product-specs/`：产品行为真相

职责：回答：

```text
What should the product do?
What behavior must the user observe?
```

它不规定 Repository 类名、SQL 表名、React hook、FastAPI router 等实现细节。

产品目标和架构机制必须分离：

```text
Product Spec = WHAT
Design Doc   = HOW / WHY
Architecture = WHERE / OWNERSHIP
```

## 4.6 `feature_list.json`：机器可读的长期验收状态

借鉴 Anthropic long-running agent harness：长期项目状态不要靠一个不断增长的叙事型 Roadmap/PROGRESS 表达。

`feature_list.json` 只保存可验证能力的：

```text
id / category
behavior / acceptance intent
status (例如 passing / failing / not_started)
必要的验证引用
```

重要规则：

- feature 状态只有在实际验证后才能切换为 passing；
- Agent 不得把“代码看起来存在”当成 passing；
- 该文件是机器状态，不是每次 session 全量注入的 prompt；
- 应通过脚本或筛选只查询当前相关 category / incomplete items。

`product-specs` 与 `feature_list` 不重复：前者定义产品行为，后者记录是否已被客观验收。

## 4.7 `docs/exec-plans/`：复杂任务的跨会话状态

采用 OpenAI ExecPlan 思路：**只有复杂、多步骤、可能跨 session 的任务才创建 ExecPlan。** 普通小修复直接由用户请求/Issue + Git 承载。

结构：

```text
docs/exec-plans/
  active/
  completed/
```

每个 active ExecPlan 可以同时拥有该任务的：

- purpose / big picture；
- progress；
- surprises & discoveries；
- task-local decision log；
- plan of work；
- validation & acceptance；
- recovery / handoff notes。

因此不再需要一个全局 `CURRENT_TASK.md + PROGRESS.md + DECISIONS.md` 三件套。

任务完成后：

1. durable design truth 提炼回对应 design doc；
2. durable product truth 提炼回 product spec；
3. feature 验收状态更新到 feature list；
4. ExecPlan 移入 `completed/`；
5. Git 保留实现历史。

Completed ExecPlans 是**冷历史**，默认不加载，仅在追溯“为什么当时这么做”时搜索。

## 4.8 `docs/PLANS.md`：ExecPlan 协议，而不是当前计划

仅定义：

- 什么工作需要 ExecPlan；
- ExecPlan 最小结构；
- 执行过程中何时更新 progress / decisions / discoveries；
- 完成后如何归档与提炼 durable truth。

不要让 `PLANS.md` 自己变成所有任务的汇总表。

## 4.9 `docs/generated/`：机器事实的 Agent-readable 投影

用于降低 discovery cost，例如：

```text
db-schema.md
api-schema.md
dependency-graph.md
```

原则：

- generated 文件禁止手工成为第二事实源；
- 必须可由真实 schema/code/config 重新生成；
- 只生成确实能显著降低 Agent 重建成本的内容。

## 4.10 `docs/references/`：外部参考，不是项目设计真相

保存第三方框架/provider/API 的必要参考材料。

它们只能回答“外部系统怎么工作”，不能覆盖本项目自己的 product/design truth。

## 4.11 `README.md`：主要面向人类 onboarding

Root README 负责安装、启动、产品介绍、基本目录、贡献入口等。

Agent 不因为存在 README 就必须和 AGENTS 同时全文读取；避免两者复制同一段架构规则。

## 4.12 默认不引入的文件/机制

R0 第一版**不要默认创建**以下新体系：

```text
ROADMAP.md
CURRENT_TASK.md
全局 PROGRESS.md
全局 DECISIONS.md
CONSTRAINTS.md 层级树
MODULE.md
backend/GUIDE.md / frontend/GUIDE.md
巨型 CONTEXT.md
ADR 框架
QUALITY.md
harness.yaml
复杂 policy DSL
文档依赖图/同步机器人
```

如果未来确实出现这些文件才能解决的问题，再用真实失败证据引入；不要预先搭框架。

## 4.13 Machine enforcement 的 owner

机器可强制的规则优先放到现有机制：

```text
pyproject / ruff / mypy
package.json / eslint / TypeScript config
import-linter / architecture tests
DB constraints / schema
scripts
CI
```

不要为了“单一策略源”立即新增 `harness.yaml`。如果已有工具配置可以直接成为事实源，就使用已有配置。

## 4.14 Verification / Feedback：从固定等级制改为任务验收

旧 V2 的 V0/V1/V2/V3 是有用的思考模型，但不再作为新的正式 Harness DSL。

新规则：

1. 全局只保留少数稳定、快速、机器化的 structural checks。
2. 小任务运行最接近改动的 targeted tests/checks。
3. 复杂任务在其 ExecPlan 的 `Validation and Acceptance` 中声明完成证据。
4. 涉及真实用户交互或跨层行为时，必须有合适的 integration/E2E 证据；不能仅凭单元测试宣称完成。
5. full repository checks 只在变更范围/CI/release 确实需要时运行，不作为每次 session 的仪式。
6. mutation test 不再按 feature 强制；只用于高价值纯领域规则/状态机/权限等适合 mutation 的关键逻辑。
7. 不再因为普通 TDD 红灯自动写 `error.jsonl` / lessons；只提升重复性 Harness 问题、数据损坏风险、权限泄漏、系统性 AI 误区等长期知识。
8. 不再强制每次会话开始/结束运行 full `make check`。

核心目标：

> Feedback 要足以证明行为，而不是尽可能多。

## 4.15 Context Loading：不要再用“必须阅读十几个文件”做保险

典型小任务：

```text
AGENTS.md
→ target code
→ nearest tests/config
```

典型复杂架构任务：

```text
AGENTS.md
→ ARCHITECTURE.md
→ relevant design/product index
→ only relevant design/product docs
→ active ExecPlan（若该任务需要）
→ target code/tests
```

默认禁止为了“保险”加载：

- completed ExecPlans；
- 全部 design docs；
- 全部 product specs；
- 历史 PROGRESS/DECISIONS；
- 无关模块文档；
- 历史 mutation/test 报告。

是否读取某个知识源由**当前任务与路由关系**决定，不需要另造一个 `CURRENT_TASK Context Manifest`。

## 4.16 One Fact, One Owner

最终 owner 关系：

| 信息 | 唯一 Owner |
|---|---|
| Agent 如何在仓库工作 | `AGENTS.md` |
| 当前系统高层结构/ownership | `ARCHITECTURE.md` |
| durable architecture/design truth | `docs/design-docs/` |
| 产品行为要求 | `docs/product-specs/` |
| 产品能力是否已客观验收 | `feature_list.json` |
| 当前复杂工作的 progress/decisions/discoveries | 对应 active ExecPlan |
| 已完成复杂工作的历史 | completed ExecPlan + Git |
| 真实 schema/code facts | code/config/schema；必要时 generated projection |
| 第三方知识 | `docs/references/` |
| lint/type/import/DB 强约束 | 对应 machine config/check |

同一事实禁止为了“方便 Agent”复制到第二个长期文档。应该通过 index/link/route 引导 Agent 找 owner。

## 4.17 R0 目标态（概念结构）

R0 完成后，Harness 大致应呈现：

```text
AI-director/
├─ AGENTS.md
├─ ARCHITECTURE.md
├─ README.md
├─ feature_list.json
│
├─ docs/
│  ├─ design-docs/
│  │  └─ index + bounded design knowledge
│  ├─ product-specs/
│  │  └─ index + bounded product behavior specs
│  ├─ exec-plans/
│  │  ├─ active/
│  │  └─ completed/
│  ├─ generated/
│  ├─ references/
│  └─ PLANS.md
│
├─ backend/
├─ frontend/
├─ scripts/
├─ pyproject.toml
└─ package.json
```

这只是**职责拓扑**，不是要求 Codex 一次性创建所有空目录/空文档。只有有实际知识需要承载时才创建对应 artifact。

---

# 5. Agent 后端重构

当前 `app.agent.service` 不是一个 service，而是多个 application service 的集合。

目标结构：

```text
backend/app/
  agent/
    facade.py
    schemas.py

    chat/
      service.py
      stream.py
      orchestration.py

    context/
      compiler.py
      budget.py
      permissions.py

    memory/
      conversation_window.py
      summary.py

    documents/
      service.py
      templates.py
      rendering.py

    tools/
      registry.py
      read_tools.py
      write_intents.py

    writes/
      pending_service.py
      validators.py

    providers/
      llm.py

    repository/
      conversations.py
      messages.py
      documents.py
```

注意：
这里仍可处于 `agent` bounded context 内，不需要微服务。

## 5.1 facade.py

只暴露稳定 application API。

其他模块禁止 import 内部实现。

## 5.2 chat/orchestration.py

只负责一次对话 turn：

```text
compile context
→ call LLM
→ execute allowed read tools
→ collect execution trace
→ return answer + candidates
```

不负责：
- memory doc CRUD
- entity 写库
- HTML rendering
- project cascade

## 5.3 context/compiler.py

成为系统核心基础设施。

输入：

```json
{
  "project_id": "...",
  "series_id": "...",
  "episode_id": "...",
  "scene_id": "...",
  "artifact_id": "...",
  "block_ids": [],
  "perspective": "...",
  "skill_id": "...",
  "budget": {}
}
```

输出：

```json
{
  "system_contract": {},
  "project_constraints": [],
  "canon_refs": [],
  "state_snapshot": {},
  "artifact_fragments": [],
  "recent_conversation": [],
  "excluded_sources": [],
  "token_estimate": 0
}
```

Context Compiler 不让 LLM 自己决定“去搜什么全部资料”。

Skill contract 提供 `required_context` 与 `optional_context`。

---

# 6. 创作工作流重新定义

上一版中“场次在剧本前”容易造成混淆。

必须把两种“分场”分开。

## 6.1 Scene Plan（剧本前）

这是写剧本之前的**叙事规划卡**，不是制作分解。

字段：

```text
scene_id
episode_id
order
location_ref
time_context
characters
scene_goal
character_goal
conflict
turn
reveal
exit_change
target_duration
required_setup
required_payoff
```

用途：
让 `screenplay.scene_write` 一次只写一场。

---

## 6.2 Screenplay（剧本）

面向故事与表演阅读：

```text
Scene Heading
Action
Dialogue
Parenthetical（少量）
Transition（必要时）
```

不要把大量摄像参数写进剧本。

---

## 6.3 Production Breakdown（剧本制作分解）

发生在剧本已经足够稳定之后。

从 screenplay 派生，一场一张制作分解单：

```text
scene_id
cast
extras
location
set_requirements
props
wardrobe
makeup
character_continuity
item_continuity
environment
vfx_requirements
sfx_requirements
music_requirements
special_constraints
estimated_complexity
asset_refs
```

这里回答“这一场要准备什么”。

---

## 6.4 Performance Script / 演出台本

本项目对“台本”做明确产品定义，避免行业语义混乱。

一场内部按 beat 分解：

```text
beat_id
source_block_refs
duration_target
speaker
dialogue
action
emotion
subtext
pause
blocking
interaction
prop_action
audio_cue
continuity_notes
```

这里回答：

“演员/角色在这一小段具体怎么演、怎么动、节奏多少。”

对于 AI 漫剧尤其重要，因为它是 screenplay 到 shot planning 的中间语义层。

---

## 6.5 Shot Plan / Storyboard（分镜）

镜头层：

```text
shot_id
scene_id
beat_refs
duration
framing
shot_size
camera_angle
camera_position
lens_intent
camera_movement
subject_action
blocking_ref
composition
lighting_intent
focus
transition
dialogue_audio_ref
asset_refs
continuity_refs
generation_intent
```

### 机位/运镜放哪里？

- “角色从门口走到桌边” → Performance Script.blocking
- “桌上必须有铜镜” → Production Breakdown.props
- “先大全景建立空间” → Shot Plan
- “35mm 感、低机位” → Shot Plan
- “缓慢 dolly in” → Shot Plan
- “这一镜使用哪个生成模型” → Provider Adapter，不进入 Shot Plan domain truth

---

## 6.6 Timeline

Timeline 不是世界观 SSOT。

它只做 playable production SSOT：

```text
shot track
dialogue track
audio track
state marker track
review marker track
generation status track
```

---

# 7. 新的主链路

```text
Project Requirement Spec
↓
Story Bible
↓
Series / Arc Plan
↓
Episode Outline
↓
Scene Plan
↓
Screenplay
↓
Script Review
↓
Production Breakdown
↓
Performance Script（演出台本）
↓
Shot Plan
↓
Storyboard
↓
Timeline
↓
Generation Adapter
```

30s Trailer：

```text
Approved Story + Approved Shots + Approved Assets
↓
Trailer Brief
↓
Trailer Beat Select
↓
Trailer Shot Plan
↓
Trailer Timeline
```

预告片是派生分支，不污染正剧工作流。

---

# 8. 状态模型：删除“静态/动态二分”

当前数据模型最大的问题之一：

```text
Entity.properties 同时混放静态与动态
relationship 同时保存身份关系和即时情绪数值
known_by/audience_known 在 entity/relation/fact/clue/audience_model 多处重复
current state 没有完整时间原因链
```

新的核心概念：

## 8.1 Canonical Attribute

稳定事实。

例如：

```text
character.birth_name
character.origin
item.base_appearance
location.parent
```

存 entities / relationships canonical data。

---

## 8.2 Stateful Attribute

可变化属性不再直接覆盖“过去”。

属性注册表：

```text
attribute_key
owner_type
value_schema
temporality_class
merge_policy
default_value
indexed
```

temporality_class：

```text
identity
slow_mutable
scene_state
belief_state
creative_constraint
derived
```

---

# 9. 推荐数据库实现（SQLite 可直接做）

## 9.1 narrative_timepoints

```sql
id
project_id
series_id
episode_id
scene_id
beat_id NULL
sequence_no
world_time NULL
```

提供统一的“故事时间坐标”。

---

## 9.2 state_events（append-only）

```sql
id
project_id
subject_type
subject_id
attribute_key
operation          -- set/add/remove/transition
before_json
after_json
timepoint_id
cause_type         -- screenplay/event/user_edit/system
cause_ref
source_artifact_id
source_revision_id
created_at
```

这是状态变化的审计日志。

禁止更新历史 event；纠错使用 compensation event。

---

## 9.3 state_current（物化当前值）

```sql
project_id
subject_type
subject_id
attribute_key
value_json
last_event_id
timepoint_id
version
```

这是性能层。

写入逻辑：

```text
StateEvent
↓ reducer
StateCurrent
```

业务逻辑以 event 可追溯、current 快速读取。

---

## 9.4 state_snapshots

```sql
id
scope_type       -- scene_entry / scene_exit / episode_entry / episode_exit
scope_id
timepoint_id
snapshot_json
source_event_cursor
created_at
```

用于：

- E12 exit → E13 entry
- Scene 5 entry → screenplay writer
- storyboard continuity check

---

# 10. Knowledge / Audience 不再使用多个 boolean

建立统一 `knowledge_states`：

```sql
id
project_id
knower_type       -- character | audience
knower_id NULL    -- audience 为 NULL
claim_id
status            -- unknown / suspects / believes / knows / misled
confidence NULL
acquired_timepoint_id
source_ref
superseded_by NULL
```

再建立 `claims`：

```sql
id
project_id
subject_ref
predicate
object_json
truth_status       -- true / false / uncertain
author_note
```

于是：

- 作者真相 = claims
- 角色认知 = knowledge_states
- 观众认知 = knowledge_states(knower_type=audience)

删除大部分散落的：

```text
audience_known
known_by
seen_by
knowledge_summary
audience_model.author_truth
```

`knowledge_summary` 变成 derived view，不持久化为真相。

---

# 11. Relationship 的重构

关系本体和关系状态拆开。

Canonical Relationship：

```text
A -- parent_of --> B
A -- member_of --> faction
A -- mentor_of --> B
```

动态：

```text
trust
intimacy
resentment
current_public_identity
promise
leverage
```

进入 state_events/state_current。

不要继续把所有动态关系字段固定成 relationships 的大宽表。

---

# 12. Artifact / HTML / 局部生成

HTML 继续作为前端呈现层，但底层新增结构化 artifact/block。

## 12.1 artifacts

```sql
id
project_id
series_id NULL
episode_id NULL
type
title
status        -- draft/review/approved/stale/archived
current_revision_id
created_at
updated_at
```

type：

```text
project_spec
story_bible
arc_plan
episode_outline
scene_plan
screenplay
production_breakdown
performance_script
shot_plan
storyboard
timeline
```

## 12.2 artifact_blocks

```sql
id
artifact_id
parent_block_id NULL
block_type
order_key
semantic_json
current_revision_id
```

## 12.3 block_revisions

```sql
id
block_id
revision_no
content_html
semantic_json
created_by
created_at
```

HTML 是 revision 的一个渲染结果/可编辑内容，不是唯一领域数据。

---

# 13. Dependency Graph 与 stale

新增：

```sql
artifact_dependencies
- upstream_ref
- upstream_revision
- downstream_ref
- dependency_type
- invalidation_policy
```

修改 B42：

```text
B42 rev5 → rev6
↓
dependency evaluator
↓
只标记真正依赖 B42@rev5 的：
Performance Beat PB12 stale
Shot SH18 stale
Timeline clip TC18 stale
```

禁止自动删除下游。

UI 提供：

```text
[仍然有效]
[查看差异]
[重新生成]
```

---

# 14. 前端真实迁移方向

当前真实代码仍以：

```text
ProjectPicker
Workbench
GraphView
AssetLibrary
agent-panel
```

为中心。

不要一次删除。

## Phase UI-1：Shell 重构

保留现有 Graph/Assets 页面，新增 ProductionRail。

```text
Project
└─ Series
   ├─ Overview
   ├─ Story
   ├─ Episodes
   ├─ Production
   └─ Resources
       ├─ Graph
       └─ Assets
```

Agent 不再作为唯一一级“目的地”，改为：
- Context Inspector 右侧协作区
- 独立会话页仍可保留为高级入口

## Phase UI-2：Episode Workspace

```text
Episode
[Overview] [Scenes] [Screenplay] [Breakdown] [Performance] [Storyboard] [Timeline] [Review]
```

用户一次工作集中在一个 Episode。

## Phase UI-3：Block Editor

Script/台本使用 block editor：
- hover actions
- selection → atomic skill
- candidate diff
- impact preview
- accept/reject
- lock span
- version history

## Phase UI-4：Timeline

播放器 + 轨道：
- Shots
- Dialogue
- Audio
- State
- Review

---

# 15. Execution Trace 替代 Raw Reasoning UI

前端不依赖 `reasoning_content` 作为可信流程说明。

显示：

```text
读取：Scene 5
加载：B41-B43
加载：角色声纹
加载：Scene Entry Snapshot
执行：dialogue.humanize
校验：continuity.check PASS
候选：3
Token：3.2k
```

这是可审计行为。

Raw provider reasoning 不作为产品架构依赖。

后端新增：

```text
execution_runs
execution_steps
```

而不是继续把 reasoning 当成流程日志。

---

# 16. Context Permission

现有三视角从 Graph filter 升级为 Context Compiler policy。

Audience Auditor：

ALLOW：
```text
revealed claims <= current timepoint
approved screenplay before current scene
audience knowledge state
```

DENY：
```text
future episode plan
hidden truth
unrevealed character goal
writer notes
other agent scratch context
```

角色视角同理。

作者视角不是默认把整个数据库塞进 prompt；只表示“权限最大”，仍按 Skill contract 做最小检索。

---

# 17. Atomic Skill Contract

每个 Skill 一个目录：

```text
skills/dialogue/humanize/
  skill.yaml
  prompt.md
  input.schema.json
  output.schema.json
  validators.py
  examples/
```

`skill.yaml`：

```yaml
id: dialogue.humanize
scope: block
requires:
  artifact_types: [screenplay]
context:
  required:
    - selected_blocks
    - adjacent_blocks
    - speaker_voice_profile
    - scene_objective
    - scene_entry_state
  optional:
    - audience_knowledge
writes:
  - candidate_block_revision
forbidden:
  - canonical_entity_write
  - workflow_transition
validators:
  - screenplay_facts_preserved
  - character_knowledge_valid
  - protected_spans_unchanged
```

---

# 18. Workflow Gate

Gate 是代码，不是 Prompt。

例如 Storyboard Gate：

```text
episode_outline approved
screenplay approved
production_breakdown complete
performance_script approved
continuity hard errors == 0
```

UI：
未来阶段可浏览，但执行按钮 blocked 并显示缺失条件。

---

# 19. 后端模块目标态

```text
app/
  projects/
  series/
  entities/
  relations/
  perspectives/

  narrative_state/
    events/
    reducer/
    snapshots/
    knowledge/

  artifacts/
    blocks/
    revisions/
    dependencies/

  workflow/
    definitions/
    gates/
    runs/

  context/
    compiler/
    permissions/
    budgets/

  skills/
    registry/
    executor/
    validation/

  agent/
    chat/
    memory/
    tools/
    providers/

  production/
    breakdown/
    performance/
    shots/

  timeline/

  assets/
```

仍然是 Modular Monolith。

---

---

# 20. 迁移计划

本节是这次有限 V3 initiative 的唯一阶段 owner。它只拥有阶段顺序、bounded purpose、前置条件、
in/out scope、下一阶段边界、子 ExecPlan 链接和阶段状态；当前阶段的细粒度进度、测试记录、
task-local 决策仍由对应 active ExecPlan 拥有。durable architecture、产品行为与验收状态仍分别属于
design docs、product specs 与 `feature_list.json`。

| 阶段 | 状态 | 前置条件 | bounded purpose / in scope | 明确 out scope 与下一边界 | 子 ExecPlan |
|---|---|---|---|---|---|
| R0 Harness | completed | repository baseline | 去重 Harness、建立 owner/routing/feedback 基线 | 不改业务行为；完成后停在 R1 前 | [`r0-harness-refactor.md`](docs/exec-plans/completed/r0-harness-refactor.md) |
| R1 Agent split | completed | R0 | 行为不变地拆分 Agent service owners | 不新增产品能力或 R2 内容；完成后停在 R2 前 | [`r1-agent-service-split.md`](docs/exec-plans/completed/r1-agent-service-split.md) |
| R2 Artifact Core | completed | R1 | 单一 `screenplay` 的 blocks/revisions/diff/localized stale | 不做 Narrative State、workflow 或 regeneration；完成后停在 R3 前 | [`r2-artifact-core.md`](docs/exec-plans/completed/r2-artifact-core.md) |
| R3 Narrative State | completed | R2 | timepoints、state events/current/snapshots、claims、knowledge states；只迁移少量高价值属性 | 不一次迁移全部 entity properties；完成后停在 R4 前 | [`r3-narrative-state-core.md`](docs/exec-plans/completed/r3-narrative-state-core.md) |
| R4 Workflow Core | not started | R3 | requirement、episode、scene plan、gate、execution run；Skill 可 mock | 不进入 production-document 扩展；完成后停在 R5 前 | 启动 R4 时创建 |
| R5 Production Documents | not started | R4 | 按本节既定顺序建立 production artifacts | 不接入完整 Atomic Skills；完成后停在 R6 前 | 启动 R5 时创建 |
| R6 Atomic Skills | not started | R5 | 接入 bounded creative skills | 不自动扩展到本文未定义的新阶段 | 启动 R6 时创建 |

阶段只能由明确用户请求启动。启动时为该阶段创建 child ExecPlan；完成验收后更新本表状态并停止，
不得自动进入下一阶段。不要在本表复制阶段内 milestones、日志或 implementation decisions。

## R0 — Harness 重构（优先级最高，不改业务行为）

R0 不按“新文件清单”实施，而按 **去重 → 建 owner → 迁移 → 改路由 → 删除副本 → 验证冷启动** 的顺序实施。

### R0-A：现状与冲突清点

只读仓库现状，建立 Harness 信息清单：

```text
information_type
current_sources
current_consumers
machine_enforced?
stale/duplicate risk
target_owner
migration_action
```

必须覆盖现有：

- AGENTS；
- ARCHITECTURE / CONSTRAINTS 各层级；
- PROGRESS / DECISIONS / features；
- testing / tests/FXX / architecture_checks；
- lessons / error.jsonl；
- task.py / verify_feature.py；
- 其他 Codex 被要求默认读取的文档。

此阶段不重新跑历史 mutation/full benchmark。

### R0-B：建立最小 owner 骨架

优先建立/整理：

1. 短 `AGENTS.md`；
2. 短 `ARCHITECTURE.md`；
3. design/product 两类知识的 index；
4. ExecPlan 协议与 active/completed 机制；
5. machine-readable feature acceptance state（如现有 features 可渐进迁移，不要求一次重写）。

不要先批量生成空的 domain docs。

### R0-C：迁移真实知识，不复制

对每条旧信息判断：

```text
仍然有效？
  ├─ 否 → 删除/留 Git 历史
  └─ 是 → 属于哪个唯一 owner？
             ↓
          搬过去
             ↓
       删除旧副本/改为链接
```

典型迁移：

- PROGRESS 当前复杂任务内容 → 对应 active ExecPlan；历史 → Git/completed plan；
- DECISIONS 中仍然有效的系统设计 → 相关 design doc；task-local 决策 → completed plan/Git；
- CONSTRAINTS → 能机器强制的进入 machine checks，纯设计 invariant 进入 AGENTS 或 design doc；
- 多层 ARCHITECTURE → 根短地图 + 必要的 bounded design docs；
- docs/tests/FXX 的重复测试用例说明 → 可执行 tests；只有真实 acceptance intent 留到 product/feature/ExecPlan；
- architecture_checks 文档映射 → 机器配置/测试本身，避免人工双写；
- lessons/error 普通开发噪声 → 删除，不继续作为默认知识源。

### R0-D：重写 Context Routing

更新 Agent 指令和脚本，使典型任务不再要求启动时读取历史文件树。

目标：

```text
small task:
AGENTS → code/tests

complex task:
AGENTS → ARCHITECTURE → relevant index/doc → active ExecPlan → code/tests
```

不要建立另一个 Context Manifest DSL。

### R0-E：重构 Feedback 规则

- 删除 session start/end 强制 full check；
- 删除 per-feature mandatory mutation；
- 删除普通 test failure 强制 error/lessons 记录；
- targeted verification 成为默认；
- complex task 由 ExecPlan 定义 Validation and Acceptance；
- 真实 UI/跨层行为需要 integration/E2E 证据；
- full check / mutation / independent review 只在风险或 CI/release 明确需要时触发。

### R0-F：Cold-start 验证

R0 完成前，用至少三类真实任务验证 Harness，而不是只检查目录：

1. **小型局部修复**：新 Agent 应只需 AGENTS + 代码/测试即可开始。
2. **单领域复杂重构**：新 Agent 应能通过 Architecture → index → relevant design → active ExecPlan 恢复状态。
3. **跨层产品行为变更**：Agent 能区分 product truth、design truth、implementation 和 acceptance state。

记录发现的路由问题，但不要因此重新增加默认必读文件。

### R0 完成标准

- `AGENTS.md` 是唯一 always-on 指令入口，且保持短小稳定；
- 根架构文档是地图而非历史/百科；
- 全局不再维护无限增长的 PROGRESS / DECISIONS / ROADMAP；
- 一个复杂任务的状态只存在于其 active ExecPlan；
- 长期能力状态可机器查询，不依赖阅读数千行 Markdown；
- completed plans / historical reports 不进入默认上下文；
- 同一事实只有一个 owner；
- 机器可强制规则不再在多个 Markdown 重复；
- 普通小改动不再默认触发 full check / mutation / independent review；
- 不再需要一次设计变更同步十余份文档；
- 没有为了“Harness v3”引入新的大型 DSL/同步系统。

---

## R1 — Agent Service Split（行为不变重构）

不得增加新功能。

目标：

- `service.py` 不再承担会话、上下文、文档、memory、writes、provider 等多种 owner；
- chat/context/documents/writes 等职责分离；
- 现有外部 API contract 保持；
- 现有测试按真实行为迁移，而不是为了某个 mutation tool 钉死实现。

先做 characterization，再拆分。

---

## R2 — Artifact Core

新增 artifacts / blocks / revisions / dependencies；先支持 `screenplay`，证明：

```text
段级编辑 → revision → diff → localized stale
```

---

## R3 — Narrative State Core

新增：

- narrative_timepoints
- state_events
- state_current
- state_snapshots
- claims
- knowledge_states

先迁移少数高价值属性，不一次迁移所有 entity properties。

---

## R4 — Workflow Core

实现：

- Project Requirement Spec
- Episode
- Scene Plan
- Gate engine
- execution run

Skill 初期可以 mock。

---

## R5 — Production Documents

按顺序：

1. Screenplay
2. Production Breakdown
3. Performance Script
4. Shot Plan
5. Storyboard
6. Timeline

---

## R6 — Atomic Skills

最后接入 bounded skills，例如 requirement/story/scene/screenplay/dialogue/production/performance/shot/continuity/audience。

---

# 21. Codex 执行规则

Codex 必须：

1. **先确认当前用户要求属于哪个阶段，不自动执行整份 master plan。**
2. 每次只解决一个最小 coherent architecture slice。
3. 不以“顺便清理”为理由扩大 scope。
4. R0 只改 Harness/开发系统，不改变业务行为。
5. 不为了“更标准”创建没有真实内容的模板文档。
6. 不新增平行事实源；迁移一个 owner 后，应删除/归档旧副本或改成明确链接。
7. 不默认全文读取历史 Progress、Decisions、completed plans、全部 design docs。
8. 先探索仓库事实，再做需要长期维护的文档决定。
9. 复杂任务需要跨 session 时使用 ExecPlan；简单任务不要制造 ExecPlan 仪式。
10. durable truth 与 task-local truth 分离：长期事实进入 design/product，工作过程留在 ExecPlan/Git。
11. 能由 lint/type/test/schema 强制的规则优先由机器强制，不复制成长篇 Agent 指令。
12. 测试数量与范围由风险和行为决定，不由 feature 编号或固定等级仪式决定。
13. Harness 改造不得重新触发历史全量 mutation/benchmark。
14. R1 之后仍遵守本文其余领域架构原则，不因 Harness 简化而扩大 Agent 自主路由权。

---

# 22. Codex 第一阶段任务顺序

当用户说“开始 Harness 重构 / 开始 R0”时，按以下顺序推进；每一步都应可单独审查和提交。

## Task A — Harness Inventory（只读）

读取现有 Harness 文档、脚本和 Git 状态，输出 source-of-truth / duplicate / consumer / target-owner 矩阵。

禁止重新跑全量 mutation 或历史 benchmark。

## Task B — Target Ownership Proposal（只读或极小文档变更）

基于实际仓库内容，把旧信息映射到：

```text
AGENTS
ARCHITECTURE
design-docs
product-specs
feature state
active/completed ExecPlans
machine checks
Git/archive
```

如果某类信息无需长期保留，直接标记删除，不要强行找新家。

## Task C — Minimal Harness Foundation

只建立当前迁移真正需要的最小入口/索引/状态结构，并保持旧流程暂时可用。

不要批量建立空模块文档，不要创建 harness DSL。

## Task D — Migrate One Slice First

优先选择 `agent` 相关 Harness 内容作为试点：

- 移走重复 architecture/constraints/progress/decision/test prose；
- 建立真正需要的 design/product/ExecPlan owner；
- 更新 AGENTS 路由；
- 验证新 Agent 冷启动路径。

试点成功后再扩展到其他领域。

## Task E — Retire Duplicates and Rituals

渐进删除/归档：

- 全局历史型 PROGRESS/DECISIONS；
- 重复 CONSTRAINTS/ARCHITECTURE 副本；
- 纯重复测试文档；
- 普通错误日志知识化规则；
- session start/end full check；
- per-feature mandatory mutation；
- 已被机器 check 完整取代的 prose 规则。

## Task F — Cold-start Acceptance

用三类真实任务证明新的 progressive disclosure 路径有效，并把发现的问题修到 owner/router，而不是增加新的 always-on 文件。

R0 验收后才进入 R1 Agent Service Split。

---

# 23. Codex 停止条件

出现以下情况时停止扩展并报告：

- R0 开始改变业务 API/产品行为；
- 一个 PR/commit 同时跨多个无关 bounded contexts；
- 为“理解任务”开始默认读取全部历史文档；
- 同一事实正在被复制进第二个长期文档；
- 新的单个 Roadmap/Context/Progress 文档开始承担多个生命周期并持续膨胀；
- Harness v3 又引入复杂 DSL、知识图谱、文档同步机器人或大规模自动生成空文档；
- 为建立成本 baseline 重新执行历史全量 mutation；
- 简单任务也被强制建立 ExecPlan/Acceptance 文档；
- 机器已经能强制的规则又被重复写入多个 prose 文档；
- feature 被标记 passing 但没有对应真实验证证据；
- 为拆 `service.py` 改变外部 API 行为；
- 新状态模型要求一次性迁移所有 entity properties；
- Agent 获得跨工作流自动跳阶段能力；
- HTML 被作为唯一 canonical store；
- 状态变化无法追溯 source artifact/revision/timepoint；
- 用户局部修改会自动覆盖已批准下游。

---

# 24. Harness 成功判断标准

Harness 重构成功不是“文件更漂亮”或“规则更少”，而是：

- 新 Codex session 能快速找到正确信息，而不需要读取十几个相似文档；
- 小任务的上下文路径非常短；
- 复杂任务能通过 active ExecPlan + Git 无损跨 session 继续；
- 产品真相、设计真相、当前架构、执行状态、机器事实彼此不混写；
- 一个事实只有一个 owner；
- 历史信息仍可追溯，但默认不污染模型上下文；
- Agent 不会因为文档过长而反复重建项目模型；
- 验证反馈与风险相匹配，真实行为必须被证明，但不再进行无意义的全量 ritual；
- Harness 自身没有演化成新的复杂产品。

产品重构最终仍需满足：

- 用户知道当前创作阶段；
- Agent 能解释读取了什么、执行了什么、写了什么候选；
- Scene/Block 修改只影响真正依赖的下游；
- 状态能回答“现在是什么、何时改变、为什么改变、由哪段内容造成”；
- Audience Agent 看不到不该知道的信息；
- 核心领域规则保持高可信验证；
- 代码职责边界足够让人类和 Agent共同维护。

---

# 25. 参考基线

R0 Harness 设计优先参考以下公开材料，而不是仅模仿某个大型仓库偶然形成的文档布局：

1. OpenAI — Harness engineering: leveraging Codex in an agent-first world
   `https://openai.com/zh-Hans-CN/index/harness-engineering/`
2. Anthropic — Effective harnesses for long-running agents
   `https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents`
3. Walking Labs — Learn Harness Engineering, Lecture 02: What a harness actually is
   `https://walkinglabs.github.io/learn-harness-engineering/zh/lectures/lecture-02-what-a-harness-actually-is/`

核心采用原则：

```text
map, not manual
progressive disclosure
repository as system of record
machine-readable long-running state
small bounded work
explicit feedback / acceptance
cross-session recoverability
```
