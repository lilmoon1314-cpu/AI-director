# Agent 改善任务分析报告：C 阶段

日期：2026-09-14  
范围：确认写入原子性、真实读取版本、重复请求幂等、并发决定、Artifact/Skill 版本保护。

**C 阶段已经完成并通过定向验收，执行边界停在 D 阶段之前。**

A 阶段发现的最后两个真实故障已经修复：批准状态保存失败时不会留下已经创建的实体；
模型读取文档后，用户若先保存新版，模型基于旧版生成的申请不能再覆盖用户内容。

## 目录

1. [结果概览](#1-结果概览)
2. [模块一：为什么一次批准必须是一个整体](#2-模块一为什么一次批准必须是一个整体)
3. [模块二：pending 的原子决定与重复请求](#3-模块二pending-的原子决定与重复请求)
4. [模块三：真实读取版本与数据库 CAS](#4-模块三真实读取版本与数据库-cas)
5. [模块四：实体、文档和 Artifact 的版本体系](#5-模块四实体文档和-artifact-的版本体系)
6. [模块五：跨领域服务如何加入同一事务](#6-模块五跨领域服务如何加入同一事务)
7. [模块六：Atomic Skill 候选保护](#7-模块六atomic-skill-候选保护)
8. [模块七：指导文档唯一性](#8-模块七指导文档唯一性)
9. [数据库迁移与真实数据保护](#9-数据库迁移与真实数据保护)
10. [必要测试与验收证据](#10-必要测试与验收证据)
11. [异常情况下的稳定程度](#11-异常情况下的稳定程度)
12. [使用变化与排错建议](#12-使用变化与排错建议)
13. [尚未解决的边界](#13-尚未解决的边界)
14. [主要文件与复查入口](#14-主要文件与复查入口)

## 1. 结果概览

| 场景 | 改善前 | C 阶段完成后 |
|---|---|---|
| 创建实体成功，随后 pending 状态保存失败 | 实体可能已经存在，但界面显示批准失败 | 整项事务回滚，实体和状态都不变 |
| 用户在 Agent 读取后修改同一文档段 | Agent 登记时拿到新版版本号，旧草案可能覆盖新版 | 写入绑定 Agent 真正读到的旧版本，批准时明确冲突 |
| 用户连续点击两次“批准” | 第二次只能看到“不是 pending”，且未来扩展容易重复执行 | 返回第一次保存的同一结果，不重复创建 |
| 批准与拒绝同时到达 | 都先读取 pending，存在竞争窗口 | 数据库条件更新决定唯一赢家 |
| 两个编辑者基于同一实体版本保存 | 后保存者可能静默覆盖 | 第一个推进版本，第二个收到 409 冲突 |
| Skill 候选生成后作品已经修改 | 候选可能继续写到新作品上 | 候选保存 base revision，过期接受被拒绝 |
| Skill 效果成功而候选状态保存失败 | Artifact/Production 可能已提交 | 效果和候选决定同事务回滚 |
| 两个请求并发创建同类指导文档 | 应用层“先查再建”仍有竞态 | SQLite 部分唯一索引作为最终防线 |

C 没有改变“作者必须批准才能写入”的产品规则，也没有增加第三方依赖或真实模型调用。

## 2. 模块一：为什么一次批准必须是一个整体

### 2.1 原理讲解

数据库事务可以理解为银行转账的一个密封信封。扣款和加款必须一起生效；只完成其中一半，
账目就失真。Agent 批准也有两部分：

1. 真正的业务效果，例如创建实体、修改文档或生成 Artifact revision；
2. 把 pending/candidate 标为已经批准，并保存这次批准的结果。

过去领域服务会在第一步内部执行 `commit`。外层随后保存批准状态；若第二步异常，外层的
`rollback` 已无法撤回第一步，所以出现“界面说失败，实体却已经创建”的半成功状态。

### 2.2 现在如何工作

参与 Agent/Skill 确认的领域服务支持 `commit=False`。它们仍负责全部业务校验和数据装配，
但只把变化放进调用方事务。最外层在业务效果、稳定响应和决定状态都准备好后只提交一次。
任何一步抛出异常，统一回滚全部变化。

### 2.3 为什么仍通过 service，而不是直接改表

实体、关系、Artifact、Production 各自的 service 持有项目归属、属性类型、引用关系、
revision 和依赖失效等规则。Agent 若直接访问这些领域的 repository，短期看代码更少，
长期会绕过业务规则。C 保留了模块化单体的服务边界，只扩展了事务参与方式。

### 2.4 重难点

- 原子性要求所有参与者使用同一个 SQLite 会话；其中任何服务偷偷提交都会打破保证。
- Production 创建会继续创建 Artifact 和依赖，内部多层调用都必须保持不提交。
- 每个批准项仍独立提交，因此一项失败不会撤销同批中此前已成功的其他项。

## 3. 模块二：pending 的原子决定与重复请求

### 3.1 条件更新是“取号锁”

批准开始时执行类似下面的条件：

```text
只有 status 仍为 pending，才把它变为事务内的 approving
```

数据库返回受影响行数。等于 1 表示当前请求获得决定权；等于 0 表示另一请求已经批准或
拒绝。检查状态和占有决定权是同一条 SQL，不存在“两个请求都先读到 pending”的空隙。

`approving` 只存在于未提交事务内部。成功时直接提交为 `approved`，失败时回滚回
`pending`，外部 API 仍只显示 pending/approved/rejected 三种稳定状态。

### 3.2 幂等是什么意思

幂等表示同一操作重复执行，最终效果与执行一次相同。浏览器双击、网络超时重发、前端重试
都可能重复发送批准请求。C 在 pending 行保存第一次成功的 `result_json`。再次批准同一个
pending ID 时，服务直接返回这份结果，目标 ID 与名称保持一致，不再次调用领域写入。

pending ID 本身就是操作幂等键。批准和拒绝也通过条件状态转换竞争，因此只有一个方向能赢。

### 3.3 值得关注的限制

这里解决的是“确认操作”的重复执行。聊天轮本身的持久 run ID、断线重连和请求级幂等属于
D 阶段，当前不能把确认幂等误解为整条 SSE 对话已经具备崩溃恢复。

## 4. 模块三：真实读取版本与数据库 CAS

### 4.1 原故障为什么隐蔽

旧流程在 `write_doc_section` 登记时读取当前版本。假设 Agent 读到 v1，用户随后保存 v2，
Agent 再登记写入；旧代码会把登记瞬间的 v2 当成基线。批准时 v2 与当前版本相同，于是
把基于 v1 写成的内容覆盖到 v2 上。表面存在 `expected_version`，实际绑定了错误时间点。

### 4.2 本轮读取账本

`ToolContext.read_versions` 只记录本轮真正返回给模型的实体/文档段版本：

```text
read_doc_section → 记录 (section_id, version)
get_entity_detail/search_entities → 记录 (entity_id, version)
write_doc_section/update_entity → 必须使用上述记录
```

如果模型没有先读，就没有可以证明的生成基线，写工具会拒绝登记并要求先读取。它不会用
登记时看到的最新版冒充模型读过的版本。

### 4.3 CAS 原理

CAS 是 Compare And Swap，中文可理解为“版本相同才替换”。关键 SQL 语义是：

```text
UPDATE ... SET content=?, version=v+1
WHERE id=? AND version=模型读取的版本
```

受影响行数为 1 才成功；为 0 说明版本已经改变。传统的“先 SELECT 检查，再 UPDATE”包含
两个数据库动作，两者之间可能插入另一个写入。CAS 把检查与修改合成一个不可分割的动作。

## 5. 模块四：实体、文档和 Artifact 的版本体系

不同数据结构使用适合自己的版本方式：

| 对象 | 版本形式 | 成功后变化 | 冲突行为 |
|---|---|---|---|
| Entity | 整数 `version` | `v → v+1` | 条件更新为 0，返回 409 |
| MemoryDocSection | 整数 `version` | 段和父文档版本同事务 +1 | 保留当前段，返回 409 |
| Artifact | 不可变 revision ID | 新建完整 revision，并条件推进 current | base revision 不是 current 时返回 409 |

实体编辑面板现在把正在显示的 `entity.version` 随 PATCH 发回。后端接口类型和前端生成类型
已经同步。旧调用方仍可暂时不传版本以保持兼容，但 Agent 主路径和当前编辑界面会传版本；
后续若移除兼容分支，应作为明确的 API 破坏性变更处理。

Artifact 使用 revision 而不是简单数字，是因为一个 revision 还关联完整的 block 快照。
推进 current revision 也采用数据库条件更新，两个并发编辑不能都从同一 revision 成功。

## 6. 模块五：跨领域服务如何加入同一事务

C 涉及的参与式服务包括：

- Entity create/update；
- Relation create；
- Memory document create/section update；
- Artifact create/edit/dependency；
- Production document create；
- Skill candidate decide。

这些接口默认仍自行提交，现有路由行为不变。只有明确传入 `commit=False` 的上层组合流程
才接管提交。这样可以保持普通 CRUD 简单，同时让 Agent/Skill 的复合写入具备一个事务边界。

跨域调用始终经过目标领域 service。Import Linter 的 16 条架构规则全部通过，说明 C 没有为了
事务方便而从 Agent 或 Skill 直接导入别的领域 repository/ORM。

## 7. 模块六：Atomic Skill 候选保护

### 7.1 base revision

Skill 执行产生候选时，服务端读取目标 Artifact 或 Production 上游 Artifact 的 current
revision，并把 ID 保存到 `skill_candidates.base_revision_id`。接受候选时重新检查：

- 对话润色等 block 编辑要求目标 current revision 仍等于 base revision；
- Production 候选要求其直接来源 Artifact 仍是生成时的 revision。

如果作者在等待确认期间已经修改作品，旧候选返回 409，不覆盖新作品。

### 7.2 接受/拒绝的单赢家和回滚

Skill candidate 也使用数据库条件更新取得决定权。Artifact/Production 效果以
`commit=False` 加入 candidate 决定事务。测试在 Artifact 新 revision 已准备好、candidate
状态尚未保存的位置注入异常，结果 revision 与 candidate 都回滚；恢复后可重新批准一次。

重复接受已经成功的 candidate 返回同一 `committed_ref`，Artifact revision 不会再次增长。

## 8. 模块七：指导文档唯一性

应用层原本会先查询同项目是否已有 positioning/style 文档，但两个并发请求可能同时查到
“没有”，随后各建一份。C 增加 SQLite 部分唯一索引，只约束：

```text
(project_id, kind)，且 kind 属于 positioning/style
```

这样未来若增加允许多份的作品类文档，不会被错误限制。迁移前先清查真实数据库，重复项为
0；没有删除、合并或改写任何用户文档。并发触发唯一约束时转换为可读的冲突提示。

## 9. 数据库迁移与真实数据保护

迁移 `c184d5e6f7a8` 仅做增量操作：

- `entities.version`，存量默认 v1；
- `agent_pending_writes.result_json`，旧记录默认为空；
- `skill_candidates.base_revision_id`，旧候选默认为空；
- 指导文档部分唯一索引。

真实库升级前版本为 `b071c2d3e4f5`，升级后为 `c184d5e6f7a8`。执行顺序为只读清查、
SQLite 在线备份、副本演练、旧列逐表哈希比对、确认真实库期间未变化、实际升级、再次比对。

验收结果：

- 29 张既有业务表、435 行旧数据全部旧列 SHA-256 一致；
- 194 个实体、208 条关系、7 个会话、17 条消息、1 份记忆文档和 4 个段保持；
- `PRAGMA integrity_check = ok`；
- `PRAGMA foreign_key_check` 为 0 项；
- 升级前定位/风格指导文档重复项为 0；
- 没有执行自动 downgrade，也没有修改 `.env`。

恢复与证明文件：

- 升级前备份：`backend/data/backups/agent-c-20260914-122119-328323-before.db`
- 演练副本：`backend/data/backups/agent-c-20260914-122119-328323-rehearsal.db`
- 逐表证据：`backend/data/backups/agent-c-20260914-122119-328323-verification.json`

这些文件位于已被 Git 忽略的本地数据目录。若未来需要恢复，必须先评估升级后新增的数据，
不能直接用旧备份覆盖现库。

## 10. 必要测试与验收证据

按用户要求没有运行全仓测试、mutation 或 benchmark，而是覆盖实际参与边界：

- 后端：298 项通过，0 项 xfail；
- 前端：3 个测试文件、22 项通过；
- Ruff 检查通过，74 个目标文件格式检查通过；
- mypy 检查 55 个相关源文件通过；
- Import Linter：16 条规则保留，0 条破坏；
- 前端 TypeScript 和定向 ESLint 通过；
- OpenAPI 与前端 API 类型已重新生成同步；
- C 新迁移的新库与填充 B 库升级测试通过；
- 真实库副本演练和升级后校验通过。

核心故障证据包括：

1. 在领域写入返回后、pending 保存前注入异常，确认实体没有残留；
2. 第二个真实数据库 session 在 Agent read 后提交用户新版，旧申请不能覆盖；
3. 同一批准请求重放，返回相同 target ID 且只有一个实体；
4. 实体旧版本 PATCH 返回 409，名称保持新版；
5. Skill 状态保存异常导致 Artifact revision 一并回滚；
6. 重复接受 Skill 不增加 revision；
7. base revision 过期时 Skill 接受返回 409并保留用户编辑；
8. 指导文档唯一索引和迁移默认值在新库、填充库中通过。

测试仍出现一项既有 Starlette/httpx 弃用警告。前端定向测试有既有 MSW 未匹配图片请求日志，
22 项行为断言均通过；这些日志没有被包装成 C 阶段通过证据，也没有扩大范围修理。

## 11. 异常情况下的稳定程度

| 异常 | 当前结果 | 稳定程度与证据边界 |
|---|---|---|
| pending 状态保存失败 | 业务效果回滚，pending 保持可重试 | 高；有事务边界注入测试 |
| 用户先改文档/实体 | 旧版本写入拒绝，用户内容保留 | 高；真实 SQLite 与第二 session 测试 |
| 双击或网络重放 approve | 返回首次结果，不重复创建 | 高；API 重放测试 |
| approve 与 reject 竞争 | 条件状态更新只有一个赢家 | 较高；SQL rowcount 与顺序竞争路径验证，未做长时间压力测试 |
| 两个 Artifact 编辑竞争 | current revision 条件推进，旧候选冲突 | 较高；revision 测试覆盖，未做高并发压力测试 |
| Skill 状态保存失败 | Artifact 效果与 candidate 决定一起回滚 | 高；故障注入测试 |
| SQLite 进程正常异常退出 | 已提交事务由 SQLite 保证，未提交事务回滚 | 设计上可靠；本阶段未直接杀进程 |
| 服务器在 SSE 中途崩溃 | 还不能按持久 run 自动恢复/查询最终状态 | 尚未解决，属于 D |
| 主库和资产库同时写 | 两个数据库不能共享原子事务 | 平台既有限制；本阶段确认效果均在主库 |

“高”只表示本阶段可控故障和真实数据库路径已有证据，不表示经过生产规模压力、断电或文件系统
损坏测试。报告明确保留这个边界，避免把 SQLite 的 ACID 原理说成无限条件下的绝对保证。

## 12. 使用变化与排错建议

### 12.1 Agent 提示“先读取”

这是版本保护生效。让 Agent 先调用对应读取工具，再重新提出修改。不要通过手工伪造版本绕过。

### 12.2 页面提示版本冲突

说明另一个操作已经保存了更新。刷新实体/文档/作品，查看最新版后重新编辑。冲突不是数据丢失，
而是系统主动拒绝覆盖。

### 12.3 重复点击批准

相同 pending/candidate ID 会返回第一次结果。若想提交新的内容，需要由 Agent 生成新的申请，
而不是修改或复用已批准记录。

### 12.4 应用仍在运行旧进程

数据库和代码已经升级；若本地开发服务器在升级前就已启动，需要按平常方式重启后端，让进程
加载新模型和接口。无需再次执行迁移。

## 13. 尚未解决的边界

C 已结束，但 A–H 总计划尚未完成：

- D：聊天 run 持久化、SSE 断线查询/回放、取消、刷新恢复 pending、旧流所有权；
- E：摘要覆盖证明、关键约束提取与按原消息恢复；
- F：跨会话长期记忆、来源、冲突、遗忘和删除；
- G：更完整的 Skill schema/gate/protected spans 与聊天适配；
- H：检索、缓存、token/成本观测和最终收口。

此外，legacy propose/confirm 是客户端回传草案的兼容路径，不使用 pending 状态机；本阶段保持
其既有逐项事务行为，没有把它扩展成新的持久确认系统。

## 14. 主要文件与复查入口

- 事务与 pending：`backend/app/agent/writes.py`、`backend/app/agent/repository.py`
- 工具读取基线：`backend/app/agent/tools.py`
- 文档 CAS：`backend/app/agent/documents.py`
- Entity version：`backend/app/entities/models.py`、`schemas.py`、`service.py`
- Artifact revision CAS：`backend/app/artifacts/service.py`、`repository.py`
- Production 事务参与：`backend/app/production/service.py`
- Skill base revision/决定：`backend/app/skills/models.py`、`service.py`
- 数据库迁移：`backend/migrations/versions/c184d5e6f7a8_atomic_confirmations.py`
- 故障基线：`backend/tests/integration/test_agent_reliability_baseline.py`
- C 迁移验收：`backend/tests/integration/test_agent_atomicity_migration.py`
- Skill 原子/过期验收：`backend/tests/integration/test_skills_api.py`
- 产品与设计说明：`docs/product-specs/agent-assistance.md`、`docs/design-docs/agent-system.md`

本阶段没有提交 Git、没有启动后台服务、没有调用真实计费模型、没有更新 feature 状态。
