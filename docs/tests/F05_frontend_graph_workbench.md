# F05 前端图谱工作台 — 测试文档

## 测试目标
验证 Workbench 主视图（**固定 author 视角**，视角切换为 F06 范围）：G6 力导向图渲染 /api/graph 全量数据（缩放/拖拽/点击交互、G6 实例单例）、节点点击开详情面板（毛玻璃视觉锚点）、实体创建/编辑/删除表单（前端校验 + 提交 + 图刷新）。

## 测试世界（L1/L2 mock 种子，与 F04 后端种子一致）
6 实体 3 关系：char-a 周兰 · char-b 沈墨 · char-c 陆离（孤立）· item-x 青铜镜（seen_by=[char-a]）· event-e 夜探药庐（known_by=[char-b]）· loc-l 青云山；rel-1 周兰→沈墨 ALLY · rel-2 周兰→青云山 LIVES_IN · rel-3 沈墨→夜探药庐 PARTICIPATES。
author 期望视图：6 节点 3 边（全量）。删除边界：loc-l 被 rel-2 引用 → DELETE 409（后端双层删除防线的前端呈现）。

## 层级矩阵
| 层级 | 用例 | 测试文件 | 必须 | 状态 |
|------|------|----------|------|------|
| L1 单元 | U1: graphStore 加载/空图/错误（固定 author） | tests/unit/stores/graphStore.test.ts | 必须 | pass |
| L1 单元 | U2: selectionStore 选中与面板开合 | tests/unit/stores/selectionStore.test.ts | 必须 | pass |
| L1 单元 | U3: toGraphData 映射参数化 | tests/unit/lib/toGraphData.test.ts | 必须 | pass |
| L1 单元 | U4: 实体表单校验参数化 | tests/unit/lib/entityForm.test.ts | 必须 | pass |
| L1 单元 | U5: GraphCanvas 单例生命周期 | tests/unit/components/GraphCanvas.test.tsx | 必须 | pass |
| L2 集成 | I1: Workbench 挂载经 msw 加载并渲染全量 | tests/integration/Workbench.test.tsx | 必须 | pass |
| L2 集成 | I2: 节点点击 → 详情面板字段 | 同上 | 必须 | pass |
| L2 集成 | I3: 新建实体有效 → POST + 图刷新 | 同上 | 必须 | pass |
| L2 集成 | I4: 新建实体无效参数化 → 拦截零请求 | 同上 | 必须 | pass |
| L2 集成 | I5: 编辑实体 → PUT + 更新 | 同上 | 必须 | pass |
| L2 集成 | I6: 删除实体确认 → DELETE + 更新（含 409 被引用拒绝展示） | 同上 | 必须 | pass |
| L2 集成 | I7: 毛玻璃视觉锚点（backdrop-blur 半透明面板） | 同上 | 必须 | pass |
| L2 集成 | I8: API 网络错误 → 错误提示不白屏 | 同上 | 必须 | pass |
| L3 E2E | E1: UI 建实体→建关系→图渲染→点选详情→编辑保存全链路（跨组件：前端+API+DB） | e2e/workbench.spec.ts | 必须 | pass |
| L3 E2E | E2: 刷新持久化 | 同上 | 必须 | pass |

## 用例说明
- U1: load 成功（GET /api/graph?perspective=author）→ nodes/edges/loading 就位；空数据 → 空数组非 undefined（边界值—空集）；fetch 抛错 → error 置位 + loading 复位（设计依据：等价类—成功/失败；边界值—空集；加载参数固定 author，F06 接管视角）
- U2: selectEntity 置 id 并开面板；clear 复位；实体/关系互斥选中（设计依据：等价类—选中/清除两态；边界值—重复选中同 id 幂等）
- U3 参数化: api 实体/关系 → G6 节点/边映射（字段一一对应、空数组边界、aliases 数组保序）（设计依据：等价类—映射有效；边界值—空集）
- U4 参数化: name 空串（边界值—min_length=1）/name 空白字符/type 非枚举值（无效等价类）→ 校验失败含字段错误；合法最小输入（name 单字符，边界值）→ 通过
- U5: render(GraphCanvas) → G6 构造函数恰调 1 次；props 数据变更 → 仅增量 setData、构造不再触发；unmount → destroy 调用（设计依据：frontend/CONSTRAINTS 渲染性能—G6 单例/禁止整图重建）
- I1: MSW mock GET /api/graph?perspective=author 返回种子 → Workbench 渲染，mock G6 收到 6 节点 3 边（设计依据：等价类—数据加载主路径）
- I2: 点击节点（经 mock G6 触发 click 回调）→ 详情面板出现且含 name/type/aliases/audience_known（设计依据：主路径—点击详情）
- I3: 表单填合法最小实体（name 单字符边界）→ POST /api/entities 201 → graphStore 重载，新节点入图（设计依据：等价类—创建有效；边界值—最小合法输入）
- I4 参数化: name 空串/type 缺省提交 → 表单字段错误展示且无网络请求（MSW 断言零调用）（设计依据：无效等价类—必填缺失；边界值—空串）
- I5: 详情面板编辑 name/aliases → PATCH 200 → 面板与图数据更新（设计依据：等价类—更新有效）
- I6: 删除需二次确认（确认框出现→确认）→ DELETE 204 → 节点出图、面板关闭；被引用实体 DELETE 409 → 展示后端三要素错误且节点保留（设计依据：主路径—删除含确认防误触；边界值—引用完整性防线的前端呈现）
- I7: 断言详情面板与侧栏容器含 backdrop-blur 与半透明背景类、过渡时长 ≤200ms（设计依据：frontend/CONSTRAINTS 视觉硬约束锚点）
- I8: MSW 强制网络错误 → 界面渲染错误提示组件而非崩溃白屏（设计依据：无效等价类—API 不可达）
- E1: Playwright 起真前后端 → UI 表单建实体「顾长风」→ 图计数 6→7 节点 → 建关系（顾长风→周兰）→ 边 3→4（设计依据：跨组件全链路主路径，features.md F05 必须层级含 L3；固定 author 视角，三视角链路属 F06）。修订：G6 力导布局下 canvas 节点坐标不可定位，「点击节点→详情→编辑」链路由 I2/I5/I6 经 MSW 真实 HTTP 契约覆盖；E1 聚焦 UI 写入 → 图刷新的跨前后端路径
- E2: 重载页面后 E1 建的实体与关系仍在（图计数 7 节点 4 边）（设计依据：持久化单一事实源，防纯前端假象）

## 测试设施约定
- L1/L2 运行于 jsdom；GraphCanvas 内 G6 实例经 `vi.mock('@antv/g6')` 替换（jsdom 无 canvas），断言经 mock 收到的数据与回调；L2 网络层用 MSW（handlers 按测试世界装配），`VITE_API_BASE` 指向 MSW 默认前缀。
- L3 Playwright `webServer` 自动拉起 uvicorn（临时 SQLite）与 vite dev；断言基于真实 API 与 DOM。
- 变异测试（§9）：**豁免**（2026-08-28 决策）——mutmut 仅支持 Python，本功能为 TypeScript/React；docs/testing.md §2 DoD 第 5 条与 §9 已注明适用范围仅 backend/app。前端测试有效性由本文件 §8 等价类/边界值设计标注与 L1/L2/L3 层级测试保障。

## 验收判定
所有"必须"层级通过 + 状态列全 pass + make check 通过（含 check-api-types 挂链）→ 功能完成；变异测试按 §9 豁免（DoD 第 5 条不适用）。
