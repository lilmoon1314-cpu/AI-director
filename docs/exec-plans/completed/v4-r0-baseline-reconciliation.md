# V4-R0 Baseline Reconciliation

## Purpose and scope

按用户授权，仅核对 V4 §69/80/83 的仓库基线，交付 still true / already changed / conflicts / migration facts 及 R1/R2 最小边界。允许修正文档事实；不修改功能代码、数据库、feature acceptance，不实施 R1/R2 或 Agent G/H。

基线：2026-09-19，main，HEAD `764db247628153434f247548baf017c4856584e7`。初始 `git status --short` 仅 `?? CODEX_REFACTOR_MASTER_PLAN_V4.md`，该文件为用户已有内容，保留原样。依据为根 V4 master plan、AGENTS.md、docs/PLANS.md、ARCHITECTURE.md 和目标代码。

## Progress

- [x] 2026-09-19 10:57–11:00 (+08:00) 核对 Git、active plan、迁移、feature、API/schema、前端及 G/H。
- [x] 2026-09-19 11:00–11:02 (+08:00) 汇总四类差异、修正 Agent plan 旧 Git 叙述，给出阶段边界并验证文档改动范围。

## Surprises / Discoveries

- HEAD 与 V4 撰写基线相同。Agent plan 的“A–F 修改均未提交 Git”已过时；G/H 仍未勾选。
- Workflow 缺少 Series/Episode 列表读取；R1 真实导航需要界定只读契约补齐。创建/打开/切换项目仍直接导航 graph。
- Gate 比较调用方 facts；Skill schema/protected spans/context 未完成 G 的权威校验。Artifact stale 按 block 选边，没有 source revision 过滤或 rebase。

## Decision Log

- 采用只读静态核对及必要的内存 schema 比对；不重跑历史测试、benchmark、mutation，不运行迁移。
- 独立 R0 记录不吸收已有 Agent active plan；只修正该计划当前 Git 恢复事实。

## Validation and acceptance

确认唯一 migration head 与本地库 revision，读取相关 feature 状态；将 app.openapi() 与已跟踪 schema 在内存比较；检查代码及入口。最终 git diff --check，并确认只有文档发生变化。静态证据不表述为重新通过行为验收。

实际结果：迁移图 15 revisions、唯一 head 与只读主库均为 `f4b7c8d9e0a1`；OpenAPI 73 paths / 100 schemas 与已存文件相等；所有 paths 出现在 TS 类型文件中（未宣称完整类型再生成一致）。feature 19 passing / 1 not_started（F16）。`git diff --check` 通过，仅提示既有 Windows 换行转换；改动仅文档。未跑业务测试、全仓检查、benchmark/mutation，未调用真实模型。

## Outcomes / Retrospective

R0 完成。四类差异、G/H 证据与下一阶段边界见 [审计报告](../../reports/v4-r0-baseline-reconciliation-2026-09-19.md)。已修正 Agent active plan 的 Recovery 事实，未改其进度/授权。用户已有 V4 master 文件未修改。教训：现有领域底座不代表 UI 可发现的读取 API 齐备；确定性比较也不代表 facts 权威。

## Recovery / restart point

无待继续的 R0 工作，无迁移或其他写库操作。R0 记录归档，Agent 计划继续 Active。所有文档改动未提交 Git；用户原 V4 文件仍未跟踪。仅在用户明确授权 R1/R2 或 G/H 后重新核对 HEAD 并建立对应阶段执行记录，不自动推进。
