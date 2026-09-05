# F06 视角切换 UI — 测试文档

## 测试目标
验证三视角一键切换（作者/角色/观众）+ character 视角角色选择下拉 + 切换后图数据按视角经 `/api/graph` 重载（后端 F04 过滤，前端断言展示面一致与不泄露），以及 403 三要素错误呈现。

## 测试世界（L1/L2 mock 种子，与 F04/F05 种子一致）
6 实体 3 关系：char-a 周兰（audience_known=true）· char-b 沈墨（false）· char-c 陆离（true）· item-x 青铜镜（false）· event-e 夜探药庐（true，known_by=[char-b]）· loc-l 青云山（true）；rel-1 周兰→沈墨 ALLY（audience_known=true，known_by=[char-b]）· rel-2 周兰→青云山 LIVES_IN（true，known_by=[char-a]）· rel-3 沈墨→夜探药庐 PARTICIPATES（false，known_by=[char-b]）。

各视角期望视图（后端 F04 规则的镜像，作为前端 mock 响应与断言基准）：
| 视角 | 节点 | 边 |
|------|------|----|
| author | 6（全量） | 3（全量） |
| audience | 4（周兰/陆离/夜探药庐/青云山） | 1（rel-2，双端可见且 audience_known） |
| character=周兰 | 2（周兰+青云山：自身∪可见关系端点） | 1（rel-2，known_by 命中） |

## 层级矩阵
| 层级 | 用例 | 测试文件 | 必须 | 状态 |
|------|------|----------|------|------|
| L1 单元 | U1: perspectiveStore 三态切换与角色 id 置位/保留 | frontend/tests/unit/stores/perspectiveStore.test.ts | 必须 | pass |
| L1 单元 | U2: graphStore.loadGraph 按视角状态透传参数（参数化三视角）+ 403 三要素落位 | frontend/tests/unit/stores/graphStore.test.ts | 必须 | pass |
| L2 集成 | I1: 默认渲染三段切换控件（author 选中）与 stats 视角标注 | frontend/tests/integration/Perspective.test.tsx | 必须 | pass |
| L2 集成 | I2: 切「观众」→ 请求 ?perspective=audience → 图刷新 4 节点 1 边 | 同上 | 必须 | pass |
| L2 集成 | I3: 切「角色」→ 角色下拉出现且数据源为 ?type=character 检索；未选角色不发图请求（边界值—缺参）；选择周兰 → ?perspective=character&character_id=char-a → 2 节点 1 边 | 同上 | 必须 | pass |
| L2 集成 | I4: character 视角 403（角色不存在）→ alert 三要素不白屏 | 同上 | 必须 | pass |
| L2 集成 | I5: 切回「作者」恢复全量；再切「角色」已选角色保留并直接加载（回切恢复） | 同上 | 必须 | pass |
| L3 E2E | E1: 三视角切换全链路——author 6/3 → 观众 4/1 → 角色选周兰 2/1 → 回作者 6/3（跨组件：UI+API+DB，截图 P-01~03） | frontend/e2e/perspective.spec.ts | 必须 | pass |
| L3 E2E | E2: 观众视角不泄露断言——audience_known=false 的「沈墨」不出现在页面任何文本中 | 同上 | 必须 | pass |
| L3 E2E（反馈修复轮） | E3: 快速连续切换视角——零 G6 内部错误（渲染链串行 E09 防线）+ 边数据完整（截图 P-04） | e2e/perspective.spec.ts | 必须 | pass |

## 用例说明
- U1: 初始 author/null（边界值—初始态）；setPerspective("character"→"audience"→"character") 角色 id 保留（回切恢复设计）；setCharacterId 置位/清空（等价类—置位/清除两态）
- U2 参数化: author / character+char-a / audience 三组输入 → api.getGraph 收到完全相同参数（设计依据：等价类—视角枚举逐一；边界值—characterId null 不拼参）；403 ApiError → error=problem、errorFix=fix、loading 复位（无效等价类—服务端拒绝三要素）
- I1: 挂载后三个视角按钮可见且 author aria-pressed=true，stats 含「（author 视角）」（设计依据：等价类—默认态）
- I2: 点「观众」→ MSW 捕获请求 URL 含 perspective=audience → 返回 audience 种子 → stats「4 节点 · 1 边」（设计依据：主路径—视角切换重载）
- I3: 点「角色」→ 角色下拉出现（数据源请求 /api/entities?type=character）；未选角色时零 /api/graph 请求（边界值—character 视角缺 character_id 前端即拦截，与后端 403 reason=missing_character_id 对应）；选周兰 → URL 含 perspective=character&character_id=char-a → stats「2 节点 · 1 边」（设计依据：等价类—选角色有效；边界值—缺参零请求）
- I4: MSW 对 character+char-a 返回 403 三要素 → role=alert 展示 problem 与 fix，组件树不崩溃（设计依据：无效等价类—角色不存在 not_character 系错误的前端呈现）
- I5: 切回作者 → 6/3 全量；再切角色 → 下拉仍选中周兰且自动重载 2/1（设计依据：回切恢复设计；等价类—两态往返）
- E1: 真实前后端：播种上述世界 → 断言 author 6/3 → 切观众断言 4/1 截图 → 切角色选周兰断言 2/1 截图 → 切回作者断言 6/3 截图（设计依据：跨组件三视角全链路，features.md F06 验证要求含三视角切换场景）
- E2: 观众视角下 `expect(page.getByText("沈墨"))` 不存在——audience_known=false 实体名不出现在画布标签/面板任何位置（设计依据：不泄露断言的前端面；后端过滤正确的端到端佐证）

## 测试设施约定
- L1/L2 运行于 jsdom；@antv/g6 经 vite.config `test.alias` 测试桩（E06 约定：禁 vi.mock×RTL）；L2 网络层 MSW，graph handler 按 URL perspective/character_id 参数路由到对应种子（含 403 覆盖用 server.use 注入）。
- L3 Playwright：沿用 F05 模式（webServer 拉起临时 SQLite 后端 + vite dev，workers:1，spec 内 resetWorld 幂等清库，shoot() 截图存档 e2e-screenshots/）。
- 视角过滤逻辑本体已由 F04 后端三层测试锁定（kill rate 95.4%）；本功能前端只断言「参数透传 + 展示面一致 + 不泄露 + 错误呈现」。
- 变异测试（docs/testing.md §9）：**豁免**——本功能全部为 TypeScript/React 前端代码，mutmut 仅支持 Python（docs/testing.md §2 DoD 第 5 条，2026-08-28 决策）。

## 验收判定
所有"必须"层级通过 + 状态列全 pass + make check 通过 → 功能完成；变异测试按 §9 豁免。
