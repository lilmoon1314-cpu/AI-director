# PROGRESS.md

## 当前状态
- 最新commit：F05 前端图谱工作台完成（见 git log）
- 测试状态：后端 100 通过 + mutmut（F04 perspectives kill rate 95.4%）；前端 68（unit 46：stores/lib/GraphCanvas/约定检查 + integration 20（MSW）+ App 冒烟 2）+ Playwright e2e 6
- Lint：make check 全绿（后端 ruff/format/lint-imports/mypy/pytest + 前端 check-api-types/typecheck/lint/build，check-api-types F05 起挂链）
- 功能清单：F01–F05 passing（F06–F10 not_started）

## 当前已完成
- 2026-08-24: 设计阶段收口——技术栈/架构定稿、约束文档分块（10 份）、架构文档就位、features.md 任务分解（F01–F10）、质量保障体系（testing/architecture_checks/lessons）、错误体系与信号采集设计。详见 DECISIONS.md
- 2026-08-24: **F01 项目初始化完成（passing）**——前后端骨架 + 9 例测试 + 跨平台命令面板 task.py + 功能验证器 verify_feature.py。详见 docs/tests/F01_project_setup.md 与 git log
- 2026-08-24: 测试机制盘点修正——RSS 守卫虚登改双态标注（E01）、幽灵节点防线写入 F02 计划、verify 脚本容错（E02，含回归测试）。详见 docs/lessons.md 错误模式库
- 2026-08-27: **F02 实体 CRUD API 完成（passing）**——entities/relations 模块（CRUD/@检索/删除双层防线）+ 首个 Alembic 迁移建齐两表 + L1 10 例 + L2 10 例 + 内存回归守卫 fixture 落地。详见 docs/tests/F02_entity_crud_api.md 与 git log
- 2026-08-27: agent 规则升级——任务清单同步 PROGRESS/测试文档先行/测试失败记录 error.jsonl 三条硬规则写入 AGENTS.md；错误模式库迁移 backend/logs/error.jsonl（入版本库），运行时错误日志改名 runtime_error.jsonl。详见 DECISIONS.md 与 docs/lessons.md §2
- 2026-08-27: **F03 关系 CRUD API 完成（passing）**——relations 模块补全（自环/端点存在性经 entities.service/重复三元组/known_by 成员四重写入校验 + 条件查询路由）+ L1 11 例 + L2 10 例 + L3 e2e 2 例（含 F02×F03 引用解除闭环）；同场修正 E01 复发（T-20260827-03）：补齐映射表声称的三项架构测试。详见 docs/tests/F03_relation_crud_api.md 与 git log
- 2026-08-27: agent 规则升级（二）——测试用例设计方法学（等价类划分 + 边界值分析，参数化强制）与变异测试机制（mutmut，kill rate ≥ 85% + 存活变异体分析归档）写入 AGENTS.md 与 docs/testing.md §2/§8/§9，自 F04 起生效（工具随 F04 落地）。详见 DECISIONS.md
- 2026-08-28: **F04 三视角过滤图查询完成（passing）**——perspectives 模块（schemas/service/router 纯只读聚合，author 全量 / character 按 known_by+标记+端点推导 / audience 双端规则，PerspectiveError 403 三 reason）+ L1 18 例 + L2 12 例 + L3 e2e 2 例 + 变异测试落地：mutmut 判杀 kill rate 95.4%（83/87，存活 4 个 OpenAPI 文案等价性归档），判杀器纳入 L1+L2 双层（纯 unit 判杀对 HTTP 层变异失效，kill rate 曾仅 47%）；含 T0 前置修正（import-linter 三契约补登 + 负例注入验证，E01 复发 T-20260827-06）与 T1 变异工具（task.py mutate 命令）。详见 docs/tests/F04_graph_perspective_query.md、DECISIONS.md 与 git log
- 2026-08-28: 变异测试规则完整化（T-20260828-01 提升）——判杀器层级覆盖原则写入 docs/testing.md §9（L1 基线 + 含 router 必加 L2 + 必须层级含 L3 时加 e2e，防后续端到端场景漏杀）；task.py mutate 对含 router 模块缺 L2 判杀自动拦截（拦截/放行双分支已验证）；错误用例断言强度规范（三要素 + detail 字典钉死）登记 E05。详见 DECISIONS.md 与 backend/logs/error.jsonl（E04/E05）
- 2026-08-28: 等价性登记豁免边界与三道防线入规——不影响运行时行为的变异体（OpenAPI 文档性字符串）不钉死文案，但豁免附三防线：唯一判定标准（不进运行时数据流，错误文案/alias/Literal 值等行为载体严禁豁免）+ 滥用防线（逐条核实依据，等价数 > 总数 20% 视为门槛失真）+ 时效防线（结论仅对当次验证时点有效）；F04 测试文档回填实杀/等价拆分（83/4）。详见 DECISIONS.md 与 docs/testing.md §9「等价性登记」
- 2026-08-28: **F05 前端图谱工作台完成（passing）**——前端基建（G6 5.x/zustand/msw/openapi-typescript/Playwright 依赖 + test:integration/test:e2e/gen:api-types 脚本 + Playwright 配置（临时 SQLite webServer）+ check-api-types 挂链 check）+ api 客户端（VITE_API_BASE 注入，类型全由 OpenAPI 生成）+ graphStore（固定 author，F06 接管视角）/selectionStore + GraphCanvas（G6 单例/增量更新/卸载销毁）+ 毛玻璃轻量 UI 组件 + 实体详情面板（编辑 PATCH/删除二次确认/409 三要素展示）+ 实体与关系创建表单 + Workbench 聚合（图计数状态栏）；测试 L1 21 例 + L2 8 例（MSW）+ L3 e2e 2 例（真实前后端，API 播种 + 幂等清库）；两项决策入规（前端豁免 mutmut、UI 自研轻量组件）+ 新错误模式 E06（vi.mock×RTL TDZ，test.alias 桩方案 + file_conventions 回归检查）。详见 docs/tests/F05_frontend_graph_workbench.md、DECISIONS.md 与 git log
- 2026-08-28: e2e 验收截图机制——关键步骤经 `shoot()` 自动存档 `frontend/e2e-screenshots/`（序号命名按序即执行序，gitignore 不入库）；失败自动截图/录屏（screenshot/video retain-on-failure）+ HTML 报告（`pnpm exec playwright show-report`）。详见 frontend/e2e/helpers.ts
- 2026-08-28: **F05 增强轮（用户追加七项需求）**——①标签避让（G6 auto-adapt-label + force collide/linkDistance 加大）；②节点悬停高亮一跳邻域（hover-activate）、点击持续高亮相关路径且非相关淡出、再点取消（setElementState toggle）；③实体类型 7 色标识 + 关系边随非人端淡化（lib/palette.ts，两端均人取中性）；④properties 展示与 JSON 编辑（新建/编辑均支持，parse 校验；known_by/seen_by 等蓝图参数可填）；⑤「新建实体/关系」折叠进「新建」手风琴（实体默认展开）；⑥操作栏收起/展开；⑦深浅色双主题跟随系统（CSS dark: 变体 + G6 setTheme 经 matchMedia 联动）。测试 L1 49 例（新增 palette 参数化）/L2 12 例（properties/折叠/收起）/e2e 3 例（新增深色 E3 截图）；frontend/CONSTRAINTS 视觉小节同步双主题/分色/高亮硬约束。详见 docs/tests/F05_frontend_graph_workbench.md 与 git log

- 2026-08-28: **F05 光点样式 + 负载验收（用户追加）**——①节点改发散型光点（三层光圈透明度递减：核心实色→内描边 0.6→halo 0.15→shadow 柔光），悬停/选中微放大（state size 26→31）+ 光圈增强；②负载验收落地：`pnpm test:e2e:load`（独立 playwright.load.config.ts + 8010 端口/专用库与主验收隔离），播种 20 人物/8 功法/6 门派/20 物体/20 地点/80 事件/40 概念 + 208 关系；**结果：/api/graph 33ms、首屏就绪 3.4s、交互期间主线程往返 ~400ms、JS 堆净增 25MB（峰值 173MB）无泄漏**；③边标签默认隐藏（多边场景喧宾夺主，悬停/选中高亮时经 state 显示）。环境坑链修复：globalSetup 在 webServer 之后执行（杀进程会误伤本轮）、uvicorn shim+python 进程链需 /T 树杀、残留进程占 8000 端口致轮询误命中旧库——负载环境改独立端口 + webServer command 前置 taskkill + spec 内 resetWorld 兜底。详见 frontend/e2e/workbench.load.spec.ts 与 git log

- 2026-08-28: **F05 视觉二轮 + 结构化属性（用户追加）**——①节点减半（26→13）+ collide=80 防重叠 + 边透明度减半（0.22）+ 用户指定 7 色板（人物 ff5a7d/事件 ffff7e/物件 a7ffff/地点 40531b/门派 ffceff/概念 97a7b3/功法 f86624）；②properties 结构化：按蓝图 7 类型字段定义（lib/entityProperties.ts，character 36 字段等）驱动新建/编辑/详情三处——表单按类型列出全部规定字段（list 逗号分隔/number/bool/object JSON，逐字段校验），详情面板结构化展示空值显示 —，额外键 JSON 兜底；③单独验收 spec e2e/highlight-detail.spec.ts：dev 后门 window.__g6graph 取节点坐标（canvas→viewport→页面坐标换算）驱动真实 hover/click，截图 HL-01~03（悬停邻域高亮+微放大、点击持续高亮+结构化详情、再点取消）；④E07 登记 Windows uvicorn 进程链残留 + Playwright webServer→globalSetup 时序 + workers 并行互踩（fullyParallel:false 不约束文件间并行，config workers:1 修复——多 spec 共库 reset/播种交错致 stats 恒 9/5）。测试 L1 49 + L2 12 + e2e 4 例全过。详见 docs/tests/F05_frontend_graph_workbench.md、backend/logs/error.jsonl（E07）与 git log

- 2026-08-28: **F05 视觉返工（用户反馈）**——①高亮 = 原样式提亮（fill/stroke/label opacity→1），不叠色不加粗不改字重；淡出 = 适度降透明度（0.5/0.42/0.4）让出视觉重心；②移除节点光晕（halo/shadow 移除 + active/selected 显式 halo:false，G6 5 内置主题默认叠加）；③防重叠真修：G6 force 的碰撞半径来自 nodeSize+nodeSpacing（传 collide:数字不生效，回退默认半径 5 致重叠）——preventOverlap:true + nodeSize 46/nodeSpacing 24/collideStrength 1 + **animation:false（布局同步算完，模拟 tick 不再覆盖分离结果）+ 布局停止后硬分离（separateOverlaps 经 translateElementTo 推开 <120 画布单位的节点对，O(n²) 毫秒级）**；④结构化属性表单按蓝图 7 类型字段驱动（entityProperties.ts，character 36 字段等），新建/编辑/详情三处统一；⑤单独验收 e2e/highlight-detail.spec.ts（dev 后门 __g6graph 取坐标驱动真实 hover/click，截图 HL-01~03）；⑥task.py dev 修复 Windows 前端启动（pnpm 裸名 Popen 失败，改经 _resolve_executable）；⑦scripts/seed_mock.py 模拟数据播种工具（清库+194 实体+208 关系入开发库）。测试 L1 49 + L2 12 + e2e 4 例全过。详见 docs/tests/F05_frontend_graph_workbench.md 与 git log

- 2026-08-28: **F05 交互三轮（用户反馈）**——①修复点击持续高亮失效（根因：node:click 监听闭包捕获首帧空 graphData，悬停因走 G6 内置行为而正常造成假象，e2e 只断言面板副作用未断言图状态致两轮漏检——登记 E08）：applySelection 全量状态机实时读 graph.getNodeData/getEdgeData 推导 selected/inactive；②悬停/选中淡出补齐：hover-activate 配 inactiveState（激活侧配置淡出侧缺省则不生效）+ enable 门控（选中期间禁用悬停互不踩踏）；③动画：状态过渡与 setElementState/hide/show 带 animation，节点/边 enter/show/hide 淡入淡出（布局动画仍禁用）；④类型筛选：工作台「筛选」面板 7 类型勾选（计数+色点）经 hideElement/showElement 增量显隐不触发重布局，边随双端可见性联动，状态栏可见计数+已筛选标注；⑤工作台所有内容默认折叠（新建两层手风琴/筛选）。测试前端 52 例（L1 35 + L2 15：I11 重写默认折叠、I13–I15 新增）+ e2e 5 例（HL3 点击持久回归断言 getElementState、E4 筛选截图）全过；新增 T-20260828-02（e2e 节点定位改按实体名——getNodeData 序非插入序）与 T-20260828-03（交互坐标复用前须防覆盖层遮挡，先关面板再点击）。详见 docs/tests/F05_frontend_graph_workbench.md、backend/logs/error.jsonl 与 git log

- 2026-08-28: **F06 视角切换 UI 完成（passing）**——perspectiveStore（三态 + characterId 回切保留 + 角色列表懒加载）+ graphStore.loadGraph 实时读视角透传（character_id 仅随 character 视角发送，不泄入其他视角请求——边界用例锁定）+ api.client 补 listEntities(type 检索) + PerspectiveSwitcher 三段切换控件（aria-pressed，character 视角角色下拉、未选角色零图请求对齐后端 missing_character_id）+ Workbench 挂载与 stats 动态视角标注（角色视角·周兰）；视角作用面决策入 DECISIONS（仅约束 /api/graph 展示面，详情/编辑保持管理面完整）。测试前端 68 例（L1 46：perspectiveStore 4 + graphStore 视角透传参数化 7；L2 20：I1–I5 三视角/缺参零请求/403 三要素/回切恢复）+ e2e 6 例（E1 三视角全链路截图 P-01~03 + E2 观众视角不泄露断言）全过；变异测试按 2026-08-28 决策豁免。详见 docs/tests/F06_perspective_switch_ui.md、DECISIONS.md 与 git log

## 进行中
- F06 反馈修复轮（用户报告 2026-08-28：切换视角重叠+标签隐藏、角色/观众视角边消失）——已修复待提交
  - [x] 诊断：①硬分离监听器首跑后自注销，数据变更后不再分离（重叠→标签避让隐藏名字）②setData/render 异步管线无串行化，快速切换/StrictMode 卸载打断打坏 G6 元素控制器（边消失，探查抓到 'draw' of undefined + instance destroyed）
  - [x] 修复：GraphCanvas 渲染链串行化（chainRef + 存活守卫）+ 持久 afterlayout→防抖硬分离随每次数据变更重跑；dev 服务器快速切换实测零内部错误、138 节点分离良好、77 边完整
  - [x] 回归：U5 适配异步渲染链 + 新增卸载排队守卫用例（前端 vitest 69 全过）+ e2e E3 快速切换防线（7 例全过）；E09 登记；CONSTRAINTS 渲染性能补两条硬约束
  - [ ] 提交推送
- F07 @ 实体选择器（用户需求并入：所有「关联某类实体 id」字段用选择器 + 直接显示名称而非 id）——未开工

## 已知问题
- 无

# 下一步
1. 执行 F07（@ 实体选择器）：输入 @ 触发防抖检索，选择插入引用，提示该实体对当前视角是否可见（开工时 `python scripts/task.py verify F07 --activate`）；首任务：撰写测试文档 docs/tests/F07
2. F07–F10 依次逐功能实现（一次一个，端到端通过后再下一个）
