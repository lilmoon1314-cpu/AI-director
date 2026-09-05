# F07 @ 实体选择器 — 测试文档

## 测试目标
所有「关联某类实体 ID」的 properties 字段（schema 标注 refTypes 的 9 个字段）改用实体选择器：输入 @（或任意关键字）触发防抖检索，下拉按名称选择回填 ID，选项带当前视角可见性提示；详情面板只读展示将关联 ID 解析为实体名称（未知 id 回退原始值）。

## 测试世界（L1/L2 mock 种子，与 F05/F06 一致 + item 关联字段）
6 实体 3 关系（同 F06 世界），item-x 青铜镜 properties: `{ seen_by: ["char-a", "char-b"] }`（详情面板名称解析断言用）。当前视角可见性以 graphStore 已加载图数据的节点集合为判定基准。

## refTypes 字段清单（schema 契约）
| 字段 | 类型字段 | refTypes |
|------|---------|----------|
| abilities | character (list) | [skill] |
| affiliation | character (text) | [faction] |
| headquarters | faction (text) | [location] |
| members | faction (list) | [character] |
| parent_location | location (text) | [location] |
| location | item (text) | [location, character] |
| holder | item (text) | [character] |
| seen_by | item (list) | [character] |
| owner | skill (text) | [character] |
| participants | event (list) | [character] |
| location | event (text) | [location] |
| known_by | event (list) | [character] |

## 层级矩阵
| 层级 | 用例 | 测试文件 | 必须 | 状态 |
|------|------|----------|------|------|
| L1 单元 | B1: EntityBrief 含 audience_known 字段（后端摘要契约扩展） | backend/tests/unit/test_entities_service.py | 必须 | pass |
| L1 单元 | U1: refTypes schema 完整性——上表 12 个字段逐一断言（参数化） | frontend/tests/unit/lib/entityProperties.test.ts | 必须 | pass |
| L1 单元 | U2: displayRefValue 参数化——list 解析名称/text 单值解析/未知 id 回退/空值 —（边界值） | 同上 | 必须 | pass |
| L1 单元 | U3: entityIndexStore——load 拉全量、force 刷新、briefs 就位 | frontend/tests/unit/stores/entityIndexStore.test.ts | 必须 | pass |
| L2 集成 | I1: 详情面板 ref 字段显示名称（seen_by → 周兰、沈墨，非 char-a/char-b） | frontend/tests/integration/EntityPicker.test.tsx | 必须 | pass |
| L2 集成 | I2: 编辑/新建表单按 refTypes 渲染选择器（item: 当前持有人=选择器，外观描述=文本框） | 同上 | 必须 | pass |
| L2 集成 | I3: 输入「@周」→ 250ms 防抖后请求 /api/entities?q=周&type=character → 下拉含名称/类型/当前视角可见徽标 | 同上 | 必须 | pass |
| L2 集成 | I4: 选择回填 ID、chip 显示名称；多值字段（seen_by）追加两个 ID 逗号存储 | 同上 | 必须 | pass |
| L2 集成 | I5: 提交 → PATCH properties.holder 为实体 ID（表单态存 ID 不存名称） | 同上 | 必须 | pass |
| L3 E2E | E1: UI 建物件 → @ 选择当前持有人=周兰 → 提交 → 详情面板 ref 字段显示名称（跨组件 UI+API+DB，截图 @-01/02） | frontend/e2e/entity-picker.spec.ts | 必须 | pass |
| L3 E2E | E2: 视角可见提示——观众视角下 audience_known=false 实体的下拉徽标为不可见 | 同上 | 必须 | pass |

## 用例说明
- B1: EntityBrief.model_validate 后 audience_known 与库值一致（设计依据：等价类—true/false；@ 选择器可见性提示的数据来源）
- U1 参数化: 12 个 ref 字段的 key/父类型/refTypes 逐一钉死（设计依据：等价类—ref 字段枚举逐一；防止 schema 回退丢标注）
- U2 参数化: ["char-a","char-b"]+{char-a:周兰,char-b:沈墨} → "周兰、沈墨"；"char-a" → "周兰"；"unknown-id" → "unknown-id"（边界值—未收录 id 回退原始值）；空/" " → "—"（边界值—空集）
- U3: load() 经 GET /api/entities 拉全量并缓存；force=true 重复调用重新拉取（等价类—缓存命中/强制刷新）
- I1: 选中 item-x → prop-seen_by 文本含「周兰」「沈墨」且不含「char-a」「char-b」（设计依据：主路径—名称显示替代抽象 id，用户需求原文）
- I2: 编辑 item → 当前持有人 渲染 EntityPicker（data-testid picker-holder），外观描述仍为 TextInput（设计依据：等价类—ref/非 ref 字段分流）
- I3: 输入 @周 → 等待防抖 → MSW 断言请求 URL q=周&type=character → 选项含 周兰/角色/「当前视角可见」（char-a 在已加载图节点集）（设计依据：主路径—@ 触发防抖检索+视角提示，features.md F07 定义）
- I4: 点选 周兰 → 表单值 = char-a、chip 显示 周兰；seen_by 依次点选两人 → 表单值 "char-a,char-b"、两枚 chip 均名称（设计依据：等价类—单值/多值；边界值—重复选择去重）
- I5: 保存 → lastPatchBody.properties.holder === "char-a"（设计依据：契约—存储层仍是 ID，名称仅显示层）
- E1: 新建表单类型=物件 → 当前持有人输入 @周 → 选择 周兰 → 提交 → 图刷新 → API 查该 item properties.holder 为周兰 id → 点开详情显示「周兰」（设计依据：跨组件全链路；features.md F07 必须层级含 L3 场景含 @ 检索）
- E2: 观众视角下打开选择器输入 @沈 → 沈墨 选项徽标「当前视角不可见」（设计依据：无效等价类—当前视角不可见实体；提示文案不阻断选择）

## 测试设施约定
- L1/L2 jsdom + MSW（vi.mock×RTL 禁用，E06）；选择器防抖用真实 setTimeout + waitFor。
- L3 Playwright 沿用既有模式（webServer 临时库、workers:1、resetWorld 幂等、shoot() 截图）。
- 可见性判定 = 当前 graphStore 图数据节点集合（author 全量→全部可见；audience/character→与画布一致），不新增后端可见性接口。
- 变异测试（docs/testing.md §9）：**豁免**——前端 TypeScript/React + 后端本功能仅 schema 字段扩展（实体摘要加一列只读映射），无独立分支逻辑；后端既有 entities 模块判杀已在 F02 覆盖。

## 验收判定
所有"必须"层级通过 + 状态列全 pass + make check 通过 → 功能完成；变异测试按 §9 豁免。
