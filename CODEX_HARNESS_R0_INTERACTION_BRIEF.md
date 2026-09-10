# AI-director R0 Harness 重构交互 Brief

> 当前阶段与 Codex 协作的主要入口。只做 **R0 Harness 重构**，不进入 R1+ 业务重构。
>
> 完整长期架构参考：`CODEX_REFACTOR_MASTER_PLAN_V3.md`。R0 冷启动时不要默认全文读取它。

---

## 1. R0 的目标

现有 Harness 的核心问题不是单纯“文档太多”，而是同一事实散落在 `AGENTS / PROGRESS / DECISIONS / ARCHITECTURE / CONSTRAINTS / testing / tests/FXX / architecture_checks / lessons / scripts` 等位置，导致 Agent 冷启动时需要大量阅读、比对和重新推理。

R0 要让新的 Codex session 能够：

- 快速知道项目是什么；
- 快速找到当前任务真正需要的知识；
- 不默认读取历史和无关领域；
- 清楚每类事实的唯一 owner；
- 跨 session 继续复杂工作；
- 获得与风险匹配的验证反馈；
- 不让 Harness 本身成为新的复杂系统。

核心指标：

> **降低 Agent 从冷启动到正确执行任务的恢复成本。**

---

## 2. 设计基线

优先参考：

- OpenAI Harness Engineering：`map, not manual`、repository as system of record、progressive disclosure、ExecPlan；
- Anthropic long-running agent harness：machine-readable feature state、小步工作、跨 session progress、Git 恢复；
- Walking Labs Harness Engineering：Harness = Instructions + Tools + Environment + State + Feedback。

不要因为某个大型仓库恰好存在巨型 Roadmap/CONTEXT，就复制它的历史偶然结构。

---

## 3. Harness 五个子系统

```text
Instructions
  Agent 如何工作、去哪里找信息

Knowledge
  当前架构、设计真相、产品真相、外部参考

State
  长期功能验收状态、当前复杂任务状态、历史

Tools / Environment
  scripts、config、worktree、dev commands

Feedback
  tests、lint、type、architecture checks、E2E、CI
```

文档只是 Harness 的一部分。

---

## 4. 目标职责拓扑

```text
AI-director/
├─ AGENTS.md
├─ ARCHITECTURE.md
├─ README.md
├─ feature_list.json
│
├─ docs/
│  ├─ design-docs/
│  ├─ product-specs/
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

这只是职责拓扑。只有存在真实知识/状态需要承载时才创建 artifact，禁止批量生成空模板。

---

## 5. One Fact, One Owner

| 信息 | 唯一 Owner |
|---|---|
| Agent 如何工作、如何找知识 | `AGENTS.md` |
| 当前系统高层结构 / ownership | `ARCHITECTURE.md` |
| durable architecture/design truth | `docs/design-docs/` |
| 产品应表现出的行为 | `docs/product-specs/` |
| 产品能力是否经过客观验收 | `feature_list.json` |
| 当前复杂任务 progress / decisions / discoveries | 对应 active ExecPlan |
| 已完成复杂工作的历史 | completed ExecPlan + Git |
| 当前真实 schema/code/config | code/config/schema；必要时 generated projection |
| 第三方/framework/provider 知识 | `docs/references/` |
| lint/type/import/DB 等机器约束 | 对应 machine config/check |

其他位置只能链接/路由到 owner，不复制正文。

---

## 6. 核心文档职责

### `AGENTS.md`

唯一 always-on Agent 入口。只保存：极短项目说明、少量全局规则、scope discipline、知识路由、基本命令、最小完成要求。

回答：

```text
How should I work here?
Where should I look next?
```

不保存当前任务、历史进度、详细架构、测试理论、mutation 历史、完整 roadmap。目标是短、稳定、像地图。

### `ARCHITECTURE.md`

只做当前系统 bird's-eye map：主要 bounded contexts、truth ownership、依赖方向、主要数据/控制流、关键入口。

回答：

```text
Where is X?
Who owns X?
What may depend on what?
```

不保存未来 roadmap、历史决策、逐函数 API、完整 DB schema、当前任务和测试历史。细节增长时下沉到 bounded design docs。

### `docs/design-docs/`

保存代码本身无法完整表达、但会影响架构判断的 **durable design truth**。使用 index 路由，一个 topic 太大时按 bounded concern 拆分。不要重新制造巨型 `CONTEXT.md`。

### `docs/product-specs/`

只定义用户/产品应观察到的行为，不绑定 SQL 表、Repository、React hook、router 等实现。

```text
Product Spec = WHAT
Design Doc   = HOW / WHY
Architecture = WHERE / OWNERSHIP
```

### `README.md`

主要面向人类 onboarding；避免与 AGENTS 重复 Agent 规则。

---

## 7. 长线状态与跨 session 状态

### `feature_list.json`

用于 machine-readable acceptance state：feature/behavior ID、category、acceptance intent、当前状态、必要验证引用。

只有真实验证后才能标 passing。它是机器状态，不是每次 session 全量注入的 prompt；应按 category/status 查询。

### ExecPlan

只有复杂、多步骤、可能跨 session 的任务才创建 active ExecPlan。它可以同时拥有该任务的：purpose、progress、discoveries、task-local decisions、plan、validation/acceptance、recovery/handoff。

因此不再需要：

```text
CURRENT_TASK.md
+ global PROGRESS.md
+ global DECISIONS.md
```

简单 bug / 小功能不要制造 ExecPlan 仪式。

完成时：durable design → design doc；durable product behavior → product spec；acceptance state → feature list；plan → completed；实现历史 → Git。

Completed plans 默认不加载。

### `docs/PLANS.md`

只定义 ExecPlan 协议与何时使用，不保存所有任务汇总。

---

## 8. Generated / References

### `docs/generated/`

只在能显著降低 discovery cost 时生成机器事实的 Agent-readable projection，例如 DB schema/API schema。必须能从真实 code/config/schema 重建，禁止手工成为第二事实源。

### `docs/references/`

保存第三方框架/provider/API 参考。它们不能覆盖本项目自己的 design/product truth。

---

## 9. 默认不引入的新体系

第一版 R0 不要默认创建：

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

未来只有真实失败证明需要时再引入。

---

## 10. Machine Enforcement

机器能保证的事情优先交给已有机制：

```text
pyproject / ruff / mypy
package.json / eslint / tsconfig
import-linter / architecture tests
DB constraints
scripts
CI
```

Prose guidance 和 machine enforcement 必须分开。不要为了“统一”立即新增 `harness.yaml`。

---

## 11. Feedback / Verification

新原则：**最小但充分的完成证据。**

- 小任务运行最接近改动的 targeted checks/tests；
- complex task 在 ExecPlan 中声明 `Validation and Acceptance`；
- 真实跨层/用户行为必须有 integration/E2E 证据；
- full repository check 只在变更范围、CI、release 确实需要时运行；
- mutation 不再 per-feature mandatory，只用于适合 mutation 的高价值纯领域逻辑；
- 普通 TDD red 不再自动进入 error/lessons；
- session start/end 不再仪式化 full `make check`；
- independent review 只在风险/里程碑真正需要时触发。

禁止为了 R0 重新运行历史全量 mutation / benchmark。F04/F08/F10/F13/F14 的历史证据已经足够证明成本/收益差异。

---

## 12. Progressive Context Loading

小任务：

```text
AGENTS.md
→ target code
→ nearest tests/config
```

复杂架构任务：

```text
AGENTS.md
→ ARCHITECTURE.md
→ relevant index
→ only relevant design/product docs
→ active ExecPlan（如果存在）
→ target code/tests
```

默认不要读取 completed plans、全部 design docs、全部 product specs、历史 PROGRESS/DECISIONS、无关 module docs、历史 mutation/test reports。

不要再创建 Context Manifest DSL；使用简单路由和任务本身决定所需上下文。

---

## 13. 旧 Harness 迁移规则

对每条旧信息执行：

```text
仍然有效？
  ├─ 否 → 删除，让 Git 保留历史
  └─ 是 → 找唯一 Owner
             ↓
           迁移
             ↓
      删除旧副本或改为链接
```

典型映射：

- PROGRESS：当前复杂任务 → active ExecPlan；历史 → Git/completed plan；
- DECISIONS：durable design → design doc；task-local rationale → plan/Git；
- CONSTRAINTS：机器可强制 → check/config；真正全局 agent invariant → AGENTS；设计 invariant → design doc；
- 多层 ARCHITECTURE：根短地图 + bounded design docs；
- docs/tests/FXX：测试细节让 tests 表达；真正 acceptance intent 留 product/feature/plan；
- architecture_checks：让机器 check 成为事实源；
- lessons/error：普通开发噪声删除，只保留重复、系统性、长期有价值的 Harness failure knowledge。

---

## 14. R0 执行顺序

### Step A — Inventory（只读）

建立：

```text
information_type
current_sources
consumers
machine_enforced?
duplicates/staleness
target_owner
migration_action
```

### Step B — Ownership Proposal

把现有信息映射到目标 owner；没有长期价值的信息直接删除，不强行找新家。

### Step C — Minimal Foundation

只建立迁移真实需要的入口、index、state/plan 机制；禁止批量创建空文档。

### Step D — Migrate One Slice

先选择 `agent` 相关 Harness 内容做试点，完成：

```text
inventory
→ owner migration
→ route update
→ old duplicate retirement
→ cold-start verification
```

成功后再扩展。

### Step E — Retire Rituals

渐进删除 global historical PROGRESS/DECISIONS、重复 Constraints/Architecture、重复测试 prose、普通 error logging-as-knowledge、session full-check ritual、per-feature mutation ritual。

### Step F — Cold-start Acceptance

至少验证：小型局部修复、单领域复杂重构、跨层产品行为变更。发现问题时修 owner/router，不增加新的 always-on 文件。

---

## 15. R0 完成标准

- `AGENTS.md` 是唯一 always-on Agent 入口；
- Architecture 是短地图，不是百科/历史；
- 不存在无限增长的全局 Roadmap/Progress/Decisions；
- complex work 用 active ExecPlan 跨 session；
- feature acceptance state 可机器查询；
- completed/history 默认不污染 context；
- 同一事实只有一个 owner；
- machine-enforced rule 不在多个 Markdown 重复；
- ordinary task 不默认 full check / mutation / independent review；
- 一次设计变化不再要求同步十余份文档；
- 没有为 Harness v3 引入新的大型 DSL/同步系统；
- 新 Codex session 能显著更快进入正确工作状态。

---

## 16. Codex 执行边界

Codex 必须：

1. 当前只执行 R0，除非用户明确进入 R1+；
2. 每次只做一个最小 coherent slice；
3. 不顺便重构业务；
4. 先探索现状再修改 Harness；
5. 不创建没有真实内容的模板；
6. 不保留两个 authoritative source；
7. 不默认全文读取历史；
8. 简单任务不制造 ExecPlan；
9. durable truth 与 task-local truth 分开；
10. 机器能保证的规则优先机器保证；
11. 不重新跑历史全量 mutation / benchmark；
12. 完成后报告：迁移了什么 owner、删除了哪些副本、如何验证新的 context path。

出现以下情况立即停止并报告：R0 开始改变业务行为；同一事实再次被复制；新 Roadmap/Context/Progress 开始无限膨胀；需要新复杂 DSL/知识图谱；简单任务也被要求创建大量 Harness artifacts；feature 被标 passing 但没有真实验证证据。

---

## 17. 与 Codex 的第一条交互

直接给 Codex：

> 阅读 `CODEX_HARNESS_R0_INTERACTION_BRIEF.md`。现在只执行 **R0 / Step A — Harness Inventory**。先不要修改业务代码，也不要重新运行历史 mutation 或 full benchmark。请检查仓库当前 Harness 文档、脚本和默认启动规则，建立 `information_type / current_sources / consumers / machine_enforced / duplicates / target_owner / migration_action` 矩阵。重点识别同一事实的重复 owner、默认上下文 fan-out，以及哪些 prose 已经能由现有机器检查替代。完成 inventory 后先向我汇报，不要自动继续 Step B。

第一轮只读诊断，用来确认 Codex 是否正确理解新的 Harness 目标。

---

## 18. 长期参考

R0 验收后，R1+ 业务重构按需查阅：

`CODEX_REFACTOR_MASTER_PLAN_V3.md`

其中保留 Agent backend split、Context Compiler、Production Pipeline、Artifact、Narrative State、Workflow Gate、Atomic Skill 等长期架构。R0 冷启动时不要默认全文读取。
