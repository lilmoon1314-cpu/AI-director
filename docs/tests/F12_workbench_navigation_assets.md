# F12 工作台导航与资产页重构 — 测试文档

## 测试目标

验证资产页两级钻取重构（URL 驱动：`/projects/:id/assets` 分区路由 + 7 类型库墙 → 类型库详情卡片墙 → 实体 HTML 查看器 overlay）、各分区独立前端搜索、空状态引导卡（空库/空类型/无搜索命中）、通用资产表单 modal 化（OQ-3，不再整区替换）、AssetCardTile 卡片规范统一（DESIGN.md §9）与 testid 迁移契约（DESIGN.md §10：保留 `section-general`/`section-project`/`asset-viewer`，新增 `asset-type-card-*`/`asset-type-back`/`asset-search`）。

设计基线: DESIGN.md §5.3（资产页）/§9（卡片规范）/§10（testid 映射与 e2e 场景建议）；决策: DECISIONS.md 2026-09-06（F11/F12 拆解 + OQ-3/OQ-6 落定）。

## 层级矩阵

| 层级 | 用例 | 测试文件 | 必须 | 状态 |
|------|------|----------|------|------|
| L1 前端单元 | FU1–FU6（10 个参数化实例）: 资产过滤/类型聚合纯函数 | frontend/tests/unit/lib/assetFilters.test.ts | 必须 | pass |
| L2 前端集成 | FI1–FI13 + 保留回归 IF1/IF4: 资产页路由/两级钻取/搜索/空态/modal/错误态 | frontend/tests/integration/AssetLibrary.test.tsx | 必须 | pass |
| L3 前端 E2E | FE1–FE3: 两级钻取全链路/通用库 modal 全链路/搜索 | frontend/e2e/assets.spec.ts | 必须（前后端联调：真实双库 HTML 资产页） | pass |
| L2 后端回归 | RI1: 既有资产集成回归（F12 无后端改动） | `pytest tests/integration -k asset` | 必须 | pass |

## 实现期记录（用例实现后回填）

- 嵌套 Outlet context 缺陷（FI4 抓出）：AssetLibrary 自渲染的 `<Outlet />` 不自动继承 Workbench 提供的 context，类型库详情深链在 store 同步前 `useProjectId()` 读到 undefined，导航拼出 `/projects/undefined/...` 触发错误页——已改为 `useOutletContext()` 回传（frontend/CONSTRAINTS.md 增硬约束），FI4 以三组域外字符串参数化锁定。
- assetStore 模块级缓存跨用例泄漏（FI7 抓出）：集成测试 beforeEach 需重置 assetStore（与 projectStore 同待遇），否则 generalCards 缓存使空库用例不可达。
- FI4 用例设计修正：`"../escape"` 含字面斜杠在路由匹配层即为非法单段（到不了 entityType 校验层），替换为同属「7 类型域外字符串」等价类的 `"CHARACTER"`/`"123"`。

## 用例说明

### 前端 L1（纯函数：src/lib/assetFilters.ts）

- FU1 参数化: 通用资产搜索 query 分别命中 title / description / category 三字段 → 均返回该卡（设计依据：等价类-有效：三匹配字段同构，参数化断言）
- FU2: query 无任何命中 → 空数组；query 为空串/纯空白 → 全量返回（设计依据：等价类-无效-不匹配 + 边界值-空串与纯空白等价于未输入）
- FU3: query 与 category chip 叠加为 AND 语义——单独命中 query 不够，须同时落在所选分类（设计依据：等价类-组合条件）
- FU4: query 大小写不敏感（"ABC" 命中 "abc"），且匹配前 trim（设计依据：等价类-大小写变体 + 边界值-首尾空白）
- FU5: 类型库详情搜索按 name / description 命中；无效 query → 空（设计依据：等价类-有效/无效）
- FU6: 类型聚合 typeStats——按 ENTITY_TYPES 聚合实体数与 image_count 求和；空列表 → 全类型 0；未知类型卡片被忽略不进任何库（设计依据：边界值-空集 + 等价类-无效类型防御）

### 前端 L2（真实组件链 + MSW，路由化 harness）

- FI1: 默认落点——点击 tab-assets → `/assets` 重定向 `/assets/general`，通用分区渲染（OQ-6；设计依据：等价类-默认路由）
- FI2: URL 即状态——深链直达 `/assets/project` 渲染类型库墙；深链 `/assets/project/character` 渲染人物库详情（设计依据：等价类-深链直达，URL 为状态事实源）
- FI3: 两级钻取导航——类型库墙卡片显示「N 实体 · M 张图」聚合计数 → 点击 `asset-type-card-character` → 详情页面包屑「项目资产 / 人物库」+ 实体卡片墙 → 点击 `asset-type-back` 返回类型库墙（设计依据：DESIGN §5.3.2/§5.3.3 导航契约）
- FI4 参数化: 无效 entityType（不在 7 类中）深链 → 重定向回类型库墙，不崩溃（设计依据：等价类-无效路由参数）
- FI5: 通用区搜索——`asset-search` 输入按 title/description/category 过滤并与 chips AND 叠加；搜索无命中显示「无匹配」提示，与空库引导卡文案可区分（设计依据：等价类-组合 + 边界值-过滤后空集≠库空）
- FI6: 类型详情搜索——`asset-search` 输入按名称过滤实体卡（设计依据：等价类-有效过滤）
- FI7: 通用库空状态——空列表显示「创建第一个参考库」引导卡，主按钮打开新建 modal（设计依据：等价类-空集 + DESIGN §5.3.1 状态矩阵）
- FI8: 表单 modal 化（OQ-3）——`create-asset` 打开居中 modal（卡片墙不被替换仍在文档中）；空标题拦截不发请求；有效保存 → 转编辑态（asset-images 出现）；取消关闭 modal 回卡片墙（设计依据：F08 IF2 迁移 + 等价类-有效/无效提交）
- FI9: 既有链路迁移——类型详情实体卡点击 → `asset-viewer` iframe 指向实体 HTML 资产页 → 返回关闭（F08 IF3 迁移到两级钻取路径下）
- FI10: 空类型库引导——无实体的类型库详情显示「暂无人物实体」引导 + 「去图谱页创建」链接 → 跳转 `/graph?create=entity&type=character`（设计依据：DESIGN §5.3.3 空态 + 导航契约）
- FI11: 图谱页联动——GraphView 挂载且 URL 带 `?create=entity&type=<valid>` → 自动展开「新建」组与实体表单并预选该类型；**查询参数消费后被清理**（LocationProbe 断言 URL 回归纯净路径——删除清理逻辑此断言必红；非法类型回落默认不崩溃）（设计依据：跨视图联动契约 + 等价类-有效/无效参数 + 防重挂载重复弹出）
- FI12: 通用卡片编辑入口键盘可达——卡片 ⋯ 编辑按钮在 group hover 与 focus-within 下均可见（设计依据：DESIGN §9 ⋯菜单键盘可达约束）
- FI13: 加载失败态——通用区/项目资产区数据加载失败呈现三要素错误条（problem + 修复 + 重试），不误显空库引导卡；恢复后重试按钮重载数据（设计依据：DESIGN §5.3.1 状态矩阵 error 态 + 错误三要素约束；验收审查 P1 发现补齐）
- 保留回归 IF1/IF4：F08 既有「页签往返」与「实体面板图片区」用例随矩阵迁移保留于同文件（矩阵外的显式登记）。

### 前端 L3（Playwright，真实前后端）

- FE1: 两级钻取全链路（DESIGN §10 场景 3）——API 播种实体+图片 → tab-assets → section-project → 类型库墙显示人物库（1 实体）→ `asset-type-card-character` → 实体卡 → 查看器 iframe 含 h1 与图片 → 返回 → `asset-type-back` 回类型库墙 → 浏览器后退回到详情（路由化收益：后退可用）
- FE2: 通用资产 modal 全链路（DESIGN §10 场景 5 + 空态）——新建（modal 中保存，卡片墙不被替换）→ 转编辑态 → 取消 → 卡片出现 → 打开查看器含标题与属性键 → 编辑 modal 删除 → 空态引导卡出现
- FE3: 分区搜索——类型详情搜实体名命中 → 搜不存在的词显示无匹配空态（设计依据：等价类-有效/无效搜索）

### 后端回归

- RI1: `pytest tests/integration -k asset` 全过（F12 纯前端重构 + 路由化，不改任何后端端点；回归防迁移期误伤）。

## testid 迁移契约（DESIGN.md §10 实施记录）

- 保留不变：`main-nav`/`tab-graph`/`tab-assets`、`section-general`/`section-project`（语义升级为 NavLink 路由切换）、`asset-viewer`/`asset-viewer-frame`、`create-asset`、`category-all`/`category-{cat}`、`general-asset-{id}`/`edit-asset-{id}`、`entity-asset-{id}`、`general-asset-grid`、`general-asset-form`、`asset-images`、`delete-asset`/`confirm-delete-asset`。
- 新增：`asset-type-card-{type}`（类型库墙卡片）、`asset-type-back`（详情页返回按钮）、`asset-search`（各分区独立搜索框，互斥挂载不冲突）、`asset-type-wall`（类型库墙容器）、`asset-general-empty`/`asset-search-empty`（空库引导/无命中提示）。
- 语义退役：`project-assets`（原平铺分组容器）由 `asset-type-wall` 承接。

## 变异测试结果

F12 不适用 mutmut 定向变异：本功能为纯前端重构，verify 命令中无 `test_<module>_service.py` 约定的后端 L1 文件（变异证据门禁按模块定位规则自动跳过，见 scripts/verify_feature.py `_mutation_modules`——纯前端命令返回空）；前端无 mutmut 运行配置（mutmut 仅覆盖后端 Python 模块，F04 决策）。后端 assets 模块本轮零改动，其既有变异证据随 F08 轮次留档。判杀力替代验证：审查子代理对关键用例做了删除实现的变异思想实验（Outlet context 透传→FI4 红、参数清理→FI11 红、错误态→FI13 红、过滤字段/AND/防御分支→FU1–FU3/FU6 红）。

## 验收审查记录（2026-09-06，docs/testing.md §10 协议首轮 F12）

只读审查子代理（Explore）输出 12 条发现（P0×0 / P1×3 / P2×9），处置如下：

| # | 级别 | 发现 | 处置 |
|---|------|------|------|
| 1 | P1 | DESIGN.md 头部虚登「verify F12 passing」（审查在 verify 之前，E01 双态漂移同型） | 修复：状态注记改为指向唯一事实源（docs/features.md 行 + 测试文档），本文件不再登记绝对状态 |
| 2 | P1 | FI11「查询参数消费后清理」零断言（变异体必存活） | 修复：FI11 增加 LocationProbe 断言 URL 回归纯净路径 |
| 3 | P1 | §5.3.1 error 态被 `.catch(() => {})` 吞成空库引导，偏离基线未登记 | 修复（按基线实现而非登记偏离）：assetStore 增 generalError/entityError 三要素错误态 + ui/ErrorStrip（problem/fix/重试）接入通用区/类型墙/类型详情 + FI13 锁定；编辑详情加载失败的 formError 同步补 fix 呈现 |
| 4 | P2 | AssetCardTile 概要 text-xs 偏离 §9 规范文本 text-sm | 修复：对齐 text-sm |
| 5 | P2 | DESIGN §10 testid 表与落地名漂移；CONSTRAINTS 浮层清单缺 modal 层级 | 修复：§10 表按 F11/F12 实际名回写；CONSTRAINTS 补 modal z-50 |
| 6 | P2 | 卡片规范（§9）类名无测试钉死 | 驳回：与 F11 首屏卡先例一致——类名字符串断言脆弱；§9 的关键交互项（键盘可达）已由 FI12 钉死 |
| 7 | P2 | PROGRESS「L1（9）」计数不符（实为 8，FU1 参数化后为 10 实例） | 修复：文档更正 |
| 8 | P2 | PROGRESS「下一步」仍写 F12 not_started 与 active 矛盾 | 修复：同步更新 |
| 9 | P2 | IF1/IF4 矩阵外保留回归未登记；F08 测试文档 IF2「整区替换」语义失效未回注 | 修复：本文件矩阵显式登记保留回归；F08 测试文档 IF2 加回注 |
| 10 | P2 | FU1/FI4 用 for 循环而非 it.each（首例失败掩盖后续） | 修复：改 it.each 逐实例独立判红 |
| 11 | P2 | 纯函数/Modal docstring 单行摘要缺参数/返回值要素 | 驳回：与仓库前端既有惯例一致（lib/palette.ts、toGraphData.ts 同型单行摘要）；模块头 docstring 已含职责与约束说明 |
| 12 | P2 | 编辑详情加载失败仅显示 problem 不显示 fix | 修复（并入 #3）：formError 改为 {problem, fix} 双行呈现 |

新错误模式登记：无新类型——#1 属 E01（文档双态漂移）既有模式复发，#2/#3 属测试缺口与基线偏离，均按既有条款处置。

## 验收判定

所有"必须"层级通过 + 状态列全 pass + make check 通过 → 功能完成。
