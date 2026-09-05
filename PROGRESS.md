# PROGRESS.md

## 当前状态
- 最新commit：见 git log（F07 收尾后进入 F08 重新定界：资产管理）
- 测试状态：后端 101 通过 + mutmut（F04 perspectives kill rate 95.4%）；前端 97（unit 53 + integration 42 + App 冒烟 2）+ Playwright e2e 8
- Lint：make check 全绿（后端 ruff/format/lint-imports/mypy/pytest + 前端 check-api-types/typecheck/lint/build）
- 功能清单：F01–F07 passing；F08 active（重新定界为「资产管理」，用户 2026-09-05 需求）；F09 已取消移除；F10 not_started

## 当前已完成
- 2026-08-24: 设计阶段收口——技术栈/架构定稿、约束文档分块（10 份）、features 分解（F01–F10）、质量保障体系（testing/architecture_checks/lessons）、错误体系与信号采集设计。详见 DECISIONS.md
- 2026-08-24~27: **F01 初始化 + F02 实体 CRUD + F03 关系 CRUD（passing）**——前后端骨架与跨平台命令面板 task.py；entities/relations 两表（FK RESTRICT 双层防线）+ CRUD/@ 检索/删除引用校验；L1/L2/L3 分层测试体系与错误模式库（error.jsonl）落地；期间 agent 规则升级三条（任务清单同步/测试文档先行/等价类+边界值设计与变异测试方法论）。详见 docs/tests/F01~F03、docs/testing.md 与 git log
- 2026-08-28: **F04 三视角过滤图查询（passing）**——perspectives 纯只读聚合（author 全量/character known_by 推导/audience 双端规则，403 三 reason）+ L1 18 + L2 12 + e2e 2；mutmut kill rate 95.4%；判杀器层级覆盖原则与等价性登记豁免边界两项决策入规（docs/testing.md §9）。详见 docs/tests/F04 与 DECISIONS.md
- 2026-08-28: **F05 前端图谱工作台（passing）+ 六轮增强返工**——前端基建（G6 5.x/zustand/msw/Playwright/openapi 类型链）+ GraphCanvas（单例/增量更新/渲染链串行化）+ 实体详情面板/创建表单/Workbench 聚合；用户追加七项（标签避让/高亮一跳邻域/7 色板/结构化属性表单/手风琴折叠/操作栏收起/双主题）→ 光点样式 + 负载验收（/api/graph 33ms、首屏 3.4s）→ 视觉返工（防重叠真修：preventOverlap+nodeSize/nodeSpacing+animation:false+布局后硬分离）→ 交互三轮（高亮状态机修复 E08/类型筛选增量显隐/动画）；负载与 e2e 截图机制就位；错误模式 E06–E08 登记。终态测试 L1 35 + L2 15 + e2e 5。详见 docs/tests/F05、frontend/CONSTRAINTS.md 与 git log
- 2026-08-28: **F06 视角切换 UI（passing）+ 反馈修复轮**——perspectiveStore 三态切换 + graphStore 视角透传（character_id 仅随 character 视角发送）+ PerspectiveSwitcher + stats 动态标注；修复硬分离自注销（E09）与渲染异步竞态（串行化+存活守卫）；「视角仅约束 /api/graph 展示面」决策入 DECISIONS。测试前端 68 + e2e 7。详见 docs/tests/F06 与 git log
- 2026-08-28: **F07 @ 实体选择器（passing）+ 视觉反馈修复**——EntityBrief 增 audience_known + EntityPicker（@ 防抖检索/可见性徽标/回填 ID 显示名称）+ entityIndexStore + 详情面板名称解析；高亮黑圈改淡黄光环（E10：G6 内置主题 state 注入四键钉死）；可见性判定与名称显示层决策入 DECISIONS。测试后端 11 + 前端 97 + e2e 8。详见 docs/tests/F07 与 git log
- 2026-09-05: **F08 重新定界 + F09 取消（用户需求）**——工作台改「图谱|资产管理」双页；资产以 HTML 形态存储（替代 Markdown 工作流）；独立资产库 SQLite（data/assets.db）；通用资产（表情/风格/植被等可复用参考）+ 项目资产（实体按类型分组卡片，点开 HTML 资产页）；F09 Markdown 导入导出移除；通用资产自定义属性 schema + agent 定制推迟第二阶段。详见 DECISIONS.md 2026-09-05 三条

## 进行中
**F08 资产管理（active）** 任务清单：
1. [x] 撰写测试文档 docs/tests/F08_asset_management.md（用例清单 pending）
2. [x] features.md：F08 行为描述改写、F09 行移除；sync 占位模块与文档路由清理；DECISIONS 登记
3. [x] 后端：assets 模块骨架重建——独立资产库（data/assets.db）模型 + 启动 create_all 引导 + config 新键
4. [x] 后端：图片上传（白名单/大小上限/uuid 重命名/流式写盘）+ 图片删除 + 封面设定
5. [x] 后端：通用资产 CRUD + HTML 模板渲染 + page 查看路由
6. [x] 后端：项目实体资产——按类型分组卡片列表 + 实体 HTML 页惰性生成/过期再生 + 孤儿清扫（实体删除联动）
7. [ ] 后端测试：L1/L2/L3 用例实现完成（149 例全绿）；mutmut 复跑分析中
8. [x] 前端：Workbench 顶层「图谱|资产管理」导航改造（现内容整体迁入图谱页）
9. [x] 前端：assetStore + OpenAPI 类型再生成
10. [x] 前端：通用资产区（分类筛选 + 卡片网格 + 新建/编辑表单 + 多图上传）
11. [x] 前端：项目资产区（类型分组卡片 + 内嵌 HTML 查看器）+ 实体详情面板图片区与查看入口
12. [x] 前端测试：L1/L2 vitest（108 例全绿）+ L3 Playwright e2e（EF1/EF2 全绿，截图 AS-01~03）
13. [ ] 文档同步（已完成：模块/前端/架构映射/数据蓝图/E11 登记）+ make check + verify F08 + PROGRESS 收尾

> 过程记录（error.jsonl E11/T-20260905-01）：mutmut 运行期并发编辑被测模块被其还原机制覆盖（修改丢失 + 判杀基线失真）——已终止首轮、补做修改、落地 task.py mutate 脏树守卫（自动化转化），代码定稿后重跑。

## 已知问题
- 无

## 下一步
1. 完成 F08 上述任务清单（一次一个，全部通过后 verify F08 收尾）
2. F10（Agent 对话与确认写入）——通用资产的自定义属性 schema 注册表与 agent 辅助定制作为第二阶段候选项，届时先立功能项再实施
3. 通用资产页 HTML 源码级自定义编辑：第二阶段候选
