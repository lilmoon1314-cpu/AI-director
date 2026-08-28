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
| L1 单元 | U6: 实体类型分色参数化（7 类型 + 未知回退） | tests/unit/lib/palette.test.ts | 必须 | pass |
| L1 单元 | U7: 关系边色随非人端淡化参数化 | 同上 | 必须 | pass |
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
| L3 E2E | E3: 深色模式跟随系统（emulate prefers-color-scheme: dark） | 同上 | 必须 | pass |
| L2 集成（增强轮） | I9: properties 只读展示（known_by 等蓝图参数） | tests/integration/Workbench.test.tsx | 必须 | pass |
| L2 集成（增强轮） | I10: properties JSON 编辑 → PATCH 携带新值 | 同上 | 必须 | pass |
| L2 集成（增强轮） | I11: 新建手风琴（实体默认展开/关系收起，点击切换） | 同上 | 必须 | pass |
| L2 集成（增强轮） | I12: 操作栏收起/展开 | 同上 | 必须 | pass |
| L3 E2E（增强轮） | HL: 悬停高亮微放大→点击持续高亮+结构化详情面板→再点取消（截图 HL-01~03） | e2e/highlight-detail.spec.ts | 必须 | pass |
| L3 E2E（视觉二轮） | HL2: 新配色/节点减半/边透明度 0.22/collide 防重叠（LOAD 截图核验） | e2e/workbench.load.spec.ts | 必须 | pass |

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
- U6 参数化: 7 实体类型各映射固定标识色；未知类型回退概念灰（设计依据：等价类—类型枚举逐一；无效等价类—未知类型容错）
- U7 参数化: 关系边色随「非 character 一端」类型色（方向无关）；人—人取中性蓝灰；两端皆非人取 source 端；opacity < 1（更淡更透明，用户规则）（设计依据：等价类—端点类型组合；边界值—双 character/双非人）
- I9: 选中含 properties 的实体（event-e: known_by/place）→ 面板按类型蓝图结构化展示全部规定字段（label 为字段中文名，空值显示 —），额外键兜底列出（设计依据：视觉二轮—详情面板按 schema 列字段）
- I10: 结构化字段编辑（known_by 逗号分隔输入）→ 保存 → PATCH properties.known_by 为解析后数组 → 面板更新（设计依据：视觉二轮—schema 驱动修改主路径；buildProperties 逐字段校验 list/number/object）
- I11: 「新建」手风琴——实体表单默认展开、关系表单默认收起；点「关系」标题展开、再点收起（设计依据：增强轮—折叠收纳交互，等价类—开/关两态）
- I12: 点「收起操作栏」→ 侧栏移除、展开按钮出现；点「展开操作栏」→ 恢复（设计依据：增强轮—工作台收起展开，等价类—两态往返）
- E3: emulateMedia(colorScheme: dark) → 页面以深色主题渲染（图计数与加载正常），截图存档（设计依据：增强轮—深浅色跟随系统 prefers-color-scheme；G6 主题经 setTheme 联动，视觉由截图人工核验）
- HL: 播种小世界（3 实体 2 关系）→ 经 dev 后门 window.__g6graph 取节点画布坐标（getElementPosition + getViewportByCanvas + 容器 boundingBox 换算页面坐标）→ 真实 mouse.hover 断言面板前截图（悬停：一跳邻域高亮/非邻接淡出/节点微放大/边标签显示）→ mouse.click 断言详情面板结构化字段（身份/职业=药师、年龄=—）并截图（持续高亮+右侧蓝图字段）→ 再点截图（取消高亮）（设计依据：视觉二轮—高亮交互与结构化详情的人工核验自动化；G6 内置渲染行为无法在 jsdom 断言）
- HL2: 负载全景截图（LOAD-01/02）核验视觉二轮：节点 size 13（原 26 减半）、collide=80 防重叠、边 opacity 0.22、新色板（人物 ff5a7d/事件 ffff7e/物件 a7ffff/地点 40531b/门派 ffceff/概念 97a7b3/功法 f86624）（设计依据：视觉二轮—负载规模下的清晰度人工核验）

## 测试设施约定
- L1/L2 运行于 jsdom；@antv/g6 经 vite.config `test.alias` 指向测试桩（src/test-stubs/g6-stub.ts，jsdom 无 canvas），断言经桩实例收到的数据与手动 emit 的回调（E06：vi.mock 与 RTL 并存会触发转换期 TDZ，已禁用该组合）；L2 网络层用 MSW（handlers 按测试世界装配），`VITE_API_BASE` 指向 MSW 可匹配的绝对前缀（vitest test.env 注入）。
- L3 Playwright `webServer` 自动拉起 uvicorn（临时 SQLite）与 vite dev；断言基于真实 API 与 DOM；关键步骤经 `shoot()` 截图存档 `frontend/e2e-screenshots/`（gitignore），深色模式用 `emulateMedia` 模拟系统偏好。
- 视觉高亮（hover-activate 悬停 / 点击 selected / auto-adapt-label 标签避让）为 G6 内置行为，jsdom 无法断言渲染效果，由 e2e 截图人工核验；数据驱动的配色规则由 U3/U6/U7 在 L1 锁定。
- 变异测试（§9）：**豁免**（2026-08-28 决策）——mutmut 仅支持 Python，本功能为 TypeScript/React；docs/testing.md §2 DoD 第 5 条与 §9 已注明适用范围仅 backend/app。前端测试有效性由本文件 §8 等价类/边界值设计标注与 L1/L2/L3 层级测试保障。

## 验收判定
所有"必须"层级通过 + 状态列全 pass + make check 通过（含 check-api-types 挂链）→ 功能完成；变异测试按 §9 豁免（DoD 第 5 条不适用）。
