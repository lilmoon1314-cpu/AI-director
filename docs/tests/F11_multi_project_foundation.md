# F11 多项目底座 — 测试文档

## 测试目标

验证多项目数据底座：projects 表与 project_id 归属（迁移打包存量数据进默认项目）、项目 CRUD API（计数器维护/改名保护/级联删除+资产清扫兜底）、既有领域端点的 project 维度过滤（查询参数渐进迁移：写入与图查询/资产卡片缺省=默认项目，实体/关系检索列表缺省=作者管理面全库，前端项目内恒显式携带 project_id），以及前端路由化工作台（项目首屏/顶栏切换器/store 重置换机）。

设计基线: DESIGN.md §4（导航）/§5.1（项目首屏）/§7（store 矩阵）/§8（后端蓝图）；决策: DECISIONS.md 2026-09-06 F11/F12 拆解四项。

## 层级矩阵

| 层级 | 用例 | 测试文件 | 必须 | 状态 |
|------|------|----------|------|------|
| L1 单元 | U1–U8: projects service 业务逻辑 | backend/tests/unit/test_projects_service.py | 必须 | pass |
| L2 集成 | I1–I10: 项目 CRUD + 级联 + 跨端点 scoping | backend/tests/integration/test_projects_api.py | 必须 | pass |
| L3 E2E 后端 | E1–E2: 双项目全链路隔离/默认项目兼容 | backend/tests/e2e/test_projects_flow.py | 必须（跨 projects+entities+relations+perspectives+assets） | pass |
| L1/L2 前端 | FU1–FU2: projectStore / ProjectPicker+路由 | frontend/tests/unit/stores/projectStore.test.ts、frontend/tests/integration/Projects.test.tsx | 必须 | pass |
| L3 前端 | FE1–FE2: Playwright 项目工作流 + 既有场景路由适配 | frontend/e2e/projects.spec.ts、workbench.spec.ts 等 | 必须（跨前后端联调） | pass |

## 用例说明

### 后端 L1（service 层，repository 内存 mock）

- U1: 有效创建（name+description）→ id 系统生成（`project-` 前缀）、entity_count/relation_count=0、时间戳填充（设计依据：等价类-有效创建）
- U2 参数化: 无效名称 name∈{"", "   "} → ValidationError 三要素完整（设计依据：等价类-无效：空名称/纯空白；两值属同一校验规则的不同表现，参数化断言同构）
- U3: 改名有效 → 名称更新且 updated_at 前进；改名目标不存在 → NotFoundError（设计依据：等价类-有效/无效-资源不存在）
- U4: 删除默认项目 → ValidationError（受保护资源，无 project_id 请求的兜底目标不可移除）（设计依据：等价类-无效-受保护资源）
- U5: 删除/读取不存在的项目 id → NotFoundError（设计依据：等价类-无效-不存在）
- U6: 计数器维护 touch(project_id, entity_delta, relation_delta) → 计数按增量更新、updated_at 刷新、负增量不允许越过 0（边界值：计数降至 0 停，不为负）；目标不存在 → NotFoundError（设计依据：边界值-计数下界 0 + 等价类-无效-不存在）
- U7: 列表按 updated_at 倒序（最近活跃在前，供首屏卡片排序）（设计依据：等价类-多项目排序契约）
- U8: 读取详情有效 → 全字段；无效 → NotFoundError 且三要素文案与 detail 整体相等（E05 范式：错误断言钉死完整契约）

### 后端 L2（HTTP 全链路，真实临时库）

- I1: POST /api/projects 有效载荷 → 201，ProjectRead 字段完整且计数为 0（设计依据：等价类-有效）
- I2 参数化: 名称边界 name∈{""（422）, " "（422）, "甲"（201，长度 1 下界）, 64 字符（201，上限）, 65 字符（422，上限+1）}（设计依据：边界值-长度两侧邻界；422 由 Pydantic min_length/max_length 产生，仅 HTTP 层可杀）
- I3: GET /api/projects → 列表含默认项目；创建实体后对应项目 entity_count 增长（真实链路验证反规范化计数器事务一致）（设计依据：等价类-有效-聚合契约）
- I4: PATCH /api/projects/{id} 改名 → 200 生效；不存在 id → 404 三要素 + detail 整体相等（设计依据：等价类-有效/无效-不存在）
- I5: DELETE /api/projects/{id} 级联 → 204；项目内实体/关系随后 404；assets.db 中该实体的图片记录与物理文件被清扫；项目列表不再含该项目；DELETE 默认项目 → 422（设计依据：等价类-有效级联 / 无效-受保护资源；跨库清扫为 DESIGN §8.2 显式级联路径）
- I6 参数化: 实体归属 scoping——POST /api/entities 带 project_id=A → 仅 A 可见；不带 project_id → 默认项目可见、A 不可见；project_id="ghost" → 404（设计依据：等价类-有效-显式归属/有效-缺省兜底/无效-项目不存在）
- I7: GET /api/graph?project_id=A → 节点仅含 A 的实体；缺省 → 默认项目图（设计依据：等价类-过滤维度正交叠加于视角过滤）
- I8 参数化: 跨项目引用（source / target / known_by 三个维度任一命中即 422，detail.rule=cross_project_reference）（设计依据：等价类-无效-跨项目关系，三维度同构断言参数化）
- I9: GET /api/assets/entities?project_id=A → 卡片仅含 A 的实体（设计依据：等价类-项目资产随项目隔离）
- I10: 通用资产无项目维度——POST /api/assets/general 后，任意项目视角下列表行为不变（不带 project 参数）（设计依据：等价类-全局资源恒共享，DESIGN §8.2）

### 后端 L3 E2E（TestClient 跨模块）

- E1: 双项目全链路——建 A/B → 各建 2 实体 + 1 关系 → graph 按 project 隔离 → 删除 A → B 数据完好、A 实体 404、资产清扫生效（跨组件理由：projects+entities+relations+perspectives+assets 五模块协作 + 双库）
- E2: 向后兼容——全部旧调用不带 project_id → 数据落默认项目、既有行为不变（迁移打包存量语义等价验证）

### 前端 L1/L2

- FU1: projectStore——loadProjects 成功/失败态、缓存 force 语义、createProject 后列表刷新、syncRoute 有效/幽灵/加载失败三分支（等价类-正常流/错误流 + 边界值-force 两态）；**重置换机**（DESIGN §7 矩阵）：切换项目经全局 graphStore.loadedProjectId 陈旧检测触发 perspective/selection/entityIndex/asset 项目分区重置换（Workbench 以 key=projectId 整树重挂载，组件内 ref 无法跨挂载记忆上一项目——E14），generalCards 全局缓存保留（设计依据：等价类-切换置两态 + 全局缓存契约，集成用例锁定）
- FU2: ProjectPicker——空状态引导、卡片渲染（名称/实体数）、搜索前端过滤、新建表单（空名不可提交）、删除确认（输入项目名才能确认）；路由——/ 重定向 /projects、卡片点击进入 /projects/:id/graph、页签切换 URL 变化、无效 projectId 错误页返回（设计依据：等价类-空/非空项目集 + 导航契约）

### 前端 L3（Playwright）

- FE1: 项目工作流——首屏新建项目 → 进入图谱 → 新建实体 → 顶栏切换第二项目 → 图谱隔离 → 返回首屏删除项目（输入名确认）→ 列表移除（设计依据：DESIGN §6 剧本 A/B/E 全链路）
- FE2: 既有 e2e 场景（workbench/perspective/entity-picker/assets/graph）路由适配后全绿（回归：URL 即状态迁移不破坏既有能力）

## 变异测试结果（2026-09-06，task.py mutate projects）

- scope: `backend/app/projects/`（125 个变异体）
- 判杀器: L1 `tests/unit/test_projects_service.py` + L2 `tests/integration/test_projects_api.py` + 架构测试 `tests/architecture/test_architecture.py`（models 层 DDL 契约变异仅 ORM 元数据断言可杀）
- **kill rate: 100%（125/125），零存活、零等价登记**
- 过程记录（两轮）:
  1. 首轮（判杀器=L1+L2）kill rate 63.2%（79/125）：46 存活体逐一分析——路由 path/响应模型、Schema 约束值（描述长度 500/501、空白名消息、extra=forbid、单字/超长改名）、默认项目常量与保护错误三要素、DDL 声明等均可补用例杀灭；据此补齐契约边界用例（I1–I5 增强四例）与架构测试 `test_projects_schema_declared`。
  2. 次轮 99.2%（124/125），唯一存活体（ensure_default_project 的 `now=None`）手动 apply 验证实为可杀——mutmut 结果缓存跨轮残留旧状态（E12）；task.py mutate 已改为启动前清缓存，清缓存重跑后 125/125。
- @checkpoint 删除类变异体在本轮判杀器下全部被杀（架构测试的 core 纯净性/散点日志检查覆盖装饰器存在性），无需等价登记。
- L3 判杀器说明（§9 层级覆盖原则）：未追加 e2e 判杀路径——存活体分析中无「仅 e2e 可杀」变异体（路由挂载/迁移/启动链类装配变异由架构测试的迁移 DDL 断言与 L2 的 TestClient 全链路覆盖，与 L2 所杀完全重叠，符合 §9 重叠豁免）。

## 验收审查记录（docs/testing.md §10 协议，2026-09-06 首次试点）

独立只读审查子代理对本功能 diff 执行协议审查，发现 7 条（P0×1 / P1×2 / P2×4）：

- **P0（已修复）**：GraphView 重置换机以组件内 useRef 判定"上一项目"，但 Workbench 以 key=projectId 整树重挂载使该分支不可达——视角角色/选中面板/查看器跨项目残留，且 FU1 声称的机制无测试锁定（E08 同型 + 文档漂移）。处置：改读全局 graphStore.loadedProjectId 做陈旧检测（页签往返不误触发），新增 FU1 集成用例锁定置换行为与 generalCards 保留；错误模式 E14 登记。
- **P1×2（已回写）**：①FU1 文档描述与实现机制不符（switchProject action 不存在）→ 按落地机制重写；②I8 实际参数化了 known_by 维度但文档未载 → 用例说明补齐。
- **P2×4（已处置）**：默认项目 id 三处魔法串 → 收敛为 api/client.ts 导出 DEFAULT_PROJECT_ID；测试目标"缺省=默认项目"口径笼统 → 精确化为写入/展示面 vs 检索列表两义；变异结果补 e2e 重叠论证（见上）。
- 新增错误模式：E14（keyed 重挂载下组件内 ref 跨挂载状态检测不可达）。

## 验收判定

所有「必须」层级通过 + 状态列全 pass + 变异测试达标（100% ≥ 85%，零存活）+ make check 通过 → 功能完成。
验证命令已由 `python scripts/task.py verify F11` 全部执行通过（2026-09-06，features.md 状态 active → passing）。
