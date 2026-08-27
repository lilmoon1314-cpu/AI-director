```
重要设计决策与原因记录

记录格式示例：

{
    "id": "D01",
    "date": "2023-08-15",
    "decision": "使用 JSON 格式存储配置",
    "reason": "JSON 格式更易读，更符合 JSON 标准"
}
```
# DECISIONS.md

## 2026-08-24: 后端框架选型 FastAPI（Python 3.12+）
- 原因: 数据模型复杂（9 张表、7 类实体、类型化 JSON 字段），Pydantic v2 提供运行时校验并自动生成 OpenAPI 文档；原生 async 支持 Agent SSE 流式对话与并发文件上传；学习曲线平缓，与用户 Python 技术栈匹配。
- 否决方案: Django/DRF（Admin/模板/ORM 对纯 API 项目过重，async 支持不完整）；Flask（需拼装 cors/marshmallow 等多个扩展，无原生类型校验与 OpenAPI）。
- 约束: Python 3.12+；路由按领域模块拆分为独立 router；所有请求/响应模型走 Pydantic schema。

## 2026-08-24: 数据库选型 SQLite（WAL 模式）+ SQLAlchemy 2.0 + Alembic，图语义在应用层实现
- 原因: MVP 为单用户/小团队本地运行，SQLite 单文件零部署，WAL 模式支持并发读；entities/relationships 采用"扁平表 + JSON 字段"存储图数据，视角过滤本质是 known_by/audience_known 的属性过滤，SQL WHERE + 应用层判断即可完成；力导向布局在前端渲染，后端无需图遍历能力；SQLAlchemy 隔离方言，未来可无缝切换 PostgreSQL。
- 否决方案: Neo4j（需独立 JVM 服务，部署运维成本高；千级实体规模下图遍历优势无法体现；properties 动态 JSON schema 在图库中反而难管理）；直连 PostgreSQL（MVP 无并发写压力，经 ORM 隔离后切换成本低）；纯 JSON 文件存储（无关系查询、无约束校验、冲突检测无从实现）。
- 约束: 必须开启 WAL 与外键约束；schema 变更必须走 Alembic 迁移；known_by 以 JSON 数组存储，视角过滤在 service 层完成。

## 2026-08-24: 前端选型 React 18 + TypeScript 5 + Vite 5
- 原因: TS 静态类型对齐后端 Pydantic 模型（openapi-typescript 自动生成），防止前后端模型漂移；Vite 冷启动与 HMR 速度快；React 生态中图可视化集成方案与资料最丰富。
- 否决方案: Vue 3（能力相当，但图可视化生态与类型生成链路成熟度略逊）；CDN + 无构建（无法承载类型系统与组件化）。
- 约束: API 类型必须由 OpenAPI schema 自动生成，禁止手写重复接口类型。

## 2026-08-24: 图可视化选型 AntV G6 5.x
- 原因: 专为关系图设计：力导向布局（d3-force 内核）、节点/边交互事件、缩放平移、拖拽开箱即用；中文文档完整；支持自定义节点渲染（实体类型图标、资产缩略图），满足后续扩展。
- 否决方案: D3.js 裸用（力模拟/渲染/缩放平移需从零实现，MVP 成本过高）；Cytoscape.js（样式定制繁琐、中文资料少）；react-flow（偏 DAG 流程图，力导向支持弱）。
- 约束: 布局计算在前端完成，后端不感知布局；图高频交互状态必须局部订阅，禁止全树重渲染。

## 2026-08-24: UI 样式选型 Tailwind CSS + shadcn/ui
- 原因: 用户明确偏好 Apple 风格（浅底高对比、毛玻璃半透明、克制动效），需要深度定制的设计系统；Tailwind 原生支持 backdrop-blur 毛玻璃效果；shadcn/ui 组件源码进仓库，完全可控可改。
- 否决方案: Ant Design（企业风设计语言与 Apple 风差异大，深度覆写成本高于原子 CSS）；纯手写 CSS（无设计约束，长期发散）。
- 约束: 视觉基调固定为浅色背景 + 高对比深色文本 + 半透明毛玻璃层 + 对称间距 + 克制动效。

## 2026-08-24: LLM 集成选型 openai SDK（OpenAI 兼容协议）
- 原因: 一套 SDK 兼容 OpenAI/DeepSeek/Qwen/Ollama 等主流端点，通过 .env 切换 BASE_URL/API_KEY/MODEL；MVP 仅需多轮对话 + 结构化输出（JSON mode），直连 SDK 即可。
- 否决方案: LangChain/LlamaIndex（抽象层复杂度远超 MVP 收益，版本 API 不稳定）。
- 约束: Agent 产出的写库操作必须经用户确认后执行；调用必须设超时与错误降级；注入 Agent 上下文的实体必须先经视角过滤。

## 2026-08-24: 架构风格选型模块化单体（Modular Monolith）+ 前后端分离
- 原因: MVP 功能（CRUD/视角过滤/上传/对话）无独立伸缩需求，微服务会引入网关、服务发现、跨服务事务与分布式调试成本；按领域边界划分模块，模块间仅通过 service 层接口交互，模块边界即未来微服务边界；每个模块目录配 ARCHITECTURE.md（职责/接口/依赖），以微服务级文档标准约束模块质量，而不支付微服务运维成本。
- 否决方案: 直接微服务（多进程 + 网关，MVP 阶段收益为零、成本显著）；单文件大泥球（违反模块解耦原则）。
- 约束: 禁止跨模块 import 其他模块的 ORM 模型/repository，必须走目标模块 service 层；模块接口或依赖变更必须同步更新该模块 ARCHITECTURE.md。

## 2026-08-24: 前端状态管理选型 Zustand
- 原因: 图数据（节点/边/选中态/视角状态）需全局共享，Zustand 无 Provider 包裹、无样板 action，selector 粒度订阅可避免全树重渲染。
- 否决方案: Redux Toolkit（样板代码多）；React Context（高频图交互引发全树重渲染）。
- 约束: 图高频交互状态必须通过 selector 局部订阅。

## 2026-08-24: Markdown 同步选型 markdown-it-py + PyYAML（YAML front matter 格式）
- 原因: 导出格式为 YAML front matter + Markdown 正文，满足用户离线编辑需求；导入时双向解析 + updated_at 时间戳比对实现冲突检测。
- 否决方案: 直接 JSON 导入导出（用户需求明确为 Markdown 离线编辑工作流）。
- 约束: 导入必须先生成冲突检测报告，用户确认前不得覆盖数据库。

## 2026-08-24: 工具链选型 uv + pnpm + Makefile
- 原因: uv 提供 uv.lock 锁文件保证 Python 依赖可复现且安装极快；pnpm 磁盘高效；Makefile 作为唯一命令入口（make init / dev-backend / dev-frontend / check），满足 AGENTS.md 的 make check 一致性检查要求。
- 否决方案: pip + requirements.txt（无锁文件，依赖漂移）；npm/yarn（磁盘占用大/版本碎片化）。
- 约束: 所有开发命令必须收口到 Makefile；make check 必须聚合后端 ruff + mypy + pytest 与前端 tsc + eslint + build。

## 2026-08-24: MVP 建表范围确定为 entities + relationships 两张
- 原因: 第 1 批功能（实体/关系 CRUD、视角过滤、资产上传、Markdown 同步、Agent 对话）仅依赖这两张表；data_struct_define.md 其余 7 张表（character_state/facts/clues/threads/state_change_log/global_state/audience_model）服务于第 2 批状态管理（Ledger），提前建表会形成死表，且 schema 大概率随第 2 批设计演进而返工。
- 否决方案: 一次建齐 9 张表（死表风险 + 提前固化可能错误的 schema）。
- 约束: 第 2 批新表必须通过 Alembic 迁移新增；data_struct_define.md 的 9 张表定义作为长期数据蓝图保留，不随 MVP 删除。

## 2026-08-24: 约束文档按模块分块（根 + backend + 7 模块 + frontend，共 10 份）
- 原因: 集中式 CONSTRAINTS.md 随功能增长必然过长，且模块约束与模块代码物理距离远；分块后每份文件保持短小，改哪个模块只读哪份约束，降低上下文负担；ARCHITECTURE.md（职责/接口/依赖）与 CONSTRAINTS.md（禁止/必须）职责分离，消除同一约束双份维护。
- 否决方案: 维持单一集中文件（长度失控，Agent 每次需读全量）；约束并入各 ARCHITECTURE.md（文档职责混杂，"何时读约束"不明确）。
- 约束: 根 CONSTRAINTS.md 只保留全局横切约束 + 模块导航表；模块约束变更时只更新该模块 CONSTRAINTS.md；AGENTS.md 文档路由规定每份文档的阅读时机。

## 2026-08-24: 开发命令契约对齐 INIT.md（setup / dev / test / check）
- 原因: INIT.md 规定初始化为独立阶段，启动就绪清单要求 make setup/dev/test/check 四命令可从零运行；统一命令名后新会话只看仓库即可回答"怎么跑/怎么测"；init.sh 降级为环境预检查 + make setup 薄封装，消除双份维护。
- 否决方案: 维持 init/dev-backend 等自定命令名（与 INIT.md 验收清单不符）；init.sh 独立实现安装逻辑（与 Makefile 重复，易漂移）。
- 约束: 命令名变更必须同步更新 AGENTS.md 首次运行命令、docs/features.md 验证命令与 INIT.md 验收清单。

## 2026-08-24: 测试三层验证体系（L1 单元 / L2 集成 / L3 E2E）+ 每功能测试文档
- 原因: 功能完成的判定必须客观可验证——L1 验证单函数行为（mock 依赖）、L2 验证模块内全链路（真实 DB）、L3 验证跨组件用户路径（公开接口）；跳过任何必须层级即未完成，防止"实现即完成"的虚假进度；每个功能一份测试文档（docs/tests/FXX）作为验收载体，与 features.md 状态联动；后端用 pytest marker 分层（TestClient 承担后端 E2E），前端 Vitest 分目录，全栈 E2E 用 Playwright（F05 引入，业界标准）。
- 否决方案: 仅单层测试（无法验证模块协作与跨组件路径）；每功能多份计划文档（维护漂移，收敛为一份测试文档）；后端 E2E 独立起服务进程（TestClient 覆盖 HTTP 全链路，进程级 E2E 属过度工程）。
- 约束: pytest 测试必须标注 marker（unit/integration/e2e/architecture）；L3 用例只走公开接口；测试文档状态列仅验证通过后更新（docs/testing.md）。

## 2026-08-24: 架构约束可执行化——import-linter 契约 + 自定义架构测试 + 映射表
- 原因: 文字约束对 agent 无强制力，必须转为可执行检查才能持续生效；import-linter 专做 import 依赖契约（每模块"仅 service 可被外部 import"、core 纯净性），自定义架构测试（tests/architecture/）覆盖 AST 级规则（router 不碰数据层、禁散点日志、禁硬编码配置模式），前端用 eslint 限制规则 + 类型同步检查（重新生成 + git diff）；docs/architecture_checks.md 维护"约束→检查"映射表，暂无法自动化的进审查清单并经 lessons 流程持续转化——保证每条约束有出处、有机制、有状态。
- 否决方案: 仅靠人工审查（不可持续、易遗漏）；全部自研检查框架（import-linter 已是标准工具）。
- 约束: 新增约束必须同功能点内登记映射表；检查命令纳入 make check。

## 2026-08-24: 错误消息三要素 + 独立错误日志 + core 可观测性统一信号采集
- 原因: agent 修复错误依赖错误信息的自解释性——三要素（什么问题/为什么/怎么修）由 AppError 构造必填参数强制保证；错误日志独立（error.jsonl 含 request_id+参数摘要+traceback+三要素）与运行日志分离便于排查；五类信号（生命周期/功能路径/数据流/资源利用/错误）由 core observability 统一自动采集（lifespan 钩子、HTTP 中间件、@checkpoint 声明式装饰器、资源采样线程、全局异常处理器），业务代码零手写日志，杜绝遗漏与格式漂移；输出统一 schema 的 JSONL 三流（app/error/metrics）+ 自动轮转，jq 可查，符合最小可维护结构。
- 否决方案: 依赖 agent 手写日志（必然遗漏且格式不一致）；OpenTelemetry 全家桶（MVP 阶段运维复杂度过高）；单文件混合日志（错误排查需全量扫描）。
- 约束: 业务模块禁止直接调用 logging；@checkpoint 摘要自动脱敏限长；资源采样间隔与轮转阈值来自 config。

## 2026-08-24: 审查反馈提升流程（错误模式库 + 自动化转化）
- 原因: agent 错误会重复发生，除非错误类型被沉淀为自动检查——每次审查/测试失败发现新类型错误，当次会话登记 docs/lessons.md 错误模式库（三要素记录），能自动化的立即转为 lint/架构测试/回归测试并更新映射表，暂不能的入审查清单；同一类错误只允许发生一次。
- 否决方案: 无沉淀机制（同类错误反复出现）；仅人工记忆（跨会话失效）。
- 约束: 新类型错误当次会话内完成登记与转化评估，禁止延后。

## 2026-08-24: 跨平台命令面板 scripts/task.py（Makefile 全量委托，单一实现源）
- 原因: 开发机为 Windows 且无 make 工具，Makefile 的 bash 语法（`[ -f .env ] || cp`、`rm -rf`）在 Windows 全部失效；用纯 Python 标准库实现全部命令契约（setup/dev/test/check/verify 等 18 条），Makefile 每个 target 委托该脚本，两个入口行为永远一致；Windows 兼容层（shutil.which 解析 pnpm 等 .cmd 工具 + cmd /c 包装）内置于脚本。
- 否决方案: 只保留 Makefile（Windows 不可用）；Makefile 与 task.py 双实现（行为漂移）；命令内嵌 bash 语法依赖 Git Bash（环境假设强）。
- 约束: 新增命令只改 task.py（COMMANDS + DISPATCH），Makefile 仅加一行委托；命令名变更同步 AGENTS.md / INIT.md / docs/features.md。

## 2026-08-24: 功能清单状态由 verify_feature.py 唯一写入
- 原因: AGENTS.md 规定"状态由验证脚本自动更新，禁止手工修改"，需要可执行的承载——脚本解析 features.md 中该功能的验证命令列，翻译为跨平台形式（make→task.py / pytest→backend 下 uv run / pnpm→frontend 下）逐条执行，全过写 passing、任一失败写 blocked（先跑完再写，保留完整失败上下文）；--activate 支持开工置 active。
- 否决方案: 人工改状态（虚报风险）；验证中断即写状态（丢失后续命令的失败信息）。
- 约束: 功能验证命令列只允许 make/pytest/pnpm 三种前缀（新前缀需在 _adapt_command 登记）。

## 2026-08-24: pnpm 存储仓库收进项目根（.pnpm-store）+ 配置文件 ASCII-only
- 原因: 实测两个 Windows 环境坑——(1) pnpm 默认 store 在 D:\.pnpm-store（项目外），沙箱/安全软件拦截项目外写入导致全量 EPERM 下载失败，store-dir/cache-dir/state-dir 收进项目根 .pnpm-store 后 13 秒装完 295 包；(2) 中文 Windows 的 Python 以 GBK locale 读 alembic.ini，中文注释触发 UnicodeDecodeError，配置文件保持 ASCII 是跨平台底线。
- 否决方案: 要求用户关闭安全软件/修改系统环境（对小白用户不友好）；改用 npm 安装（绕开问题但放弃 pnpm 决策）。
- 约束: .pnpm-store 入 .gitignore；alembic.ini 等配置文件禁止非 ASCII 字符（新增配置文件时检查）。

## 2026-08-24: 前端骨架采用 Tailwind CSS v4（CSS-first 配置）
- 原因: Tailwind v4 已是当前稳定版本，无需 tailwind.config.ts / postcss.config.js，仅 @tailwindcss/vite 插件 + `@import "tailwindcss"` 两行接入，配置面最小；shadcn/ui 已完整支持 v4（F05 引入时无阻碍）；毛玻璃视觉基调（backdrop-blur）v4 原生支持。
- 否决方案: Tailwind v3（多两份配置文件，v3 生态进入维护期）；CSS Modules/手写样式（放弃决策文档既定的 Tailwind + shadcn/ui 体系）。
- 约束: 全局样式只从 src/index.css 入口扩展（@theme 自定义设计令牌）；组件内类名遵循 frontend/CONSTRAINTS.md 视觉约束。

## 2026-08-24: 幽灵节点双层防线——FK DDL（ON DELETE RESTRICT）+ foreign_key_check 巡检，F02 首迁移建齐两表
- 原因: "删除被引用实体"仅靠应用层 ReferentialError 校验存在旁路风险（任何绕过 service 的写入路径都会产生悬空引用/幽灵节点）；PRAGMA foreign_keys=ON 只对 DDL 声明了外键的表生效，故必须建表即声明；F02 的删除校验依赖 relationships 表存在，两表在 F02 首个迁移同时创建（对齐既有决策"MVP 建表范围 entities + relationships"）。
- 否决方案: 仅应用层校验（旁路无防护）；ON DELETE CASCADE（静默级联删除是数据失踪事故的常见源头，违反 entities/CONSTRAINTS"不物理级联"约束）；F02 只建 entities 表（F02 验收项"删除校验关系引用"无从验证）。
- 约束: 集成测试纳入 `PRAGMA foreign_key_check` 空结果巡检；架构测试断言迁移/模型含 FK+RESTRICT 声明（映射表 F02 行，docs/architecture_checks.md）。

## 2026-08-24: 文档机制双态标注（已就位/计划 FXX），verify 脚本容错格式化改写
- 原因: 测试机制盘点发现两处缺陷——(1) testing.md §7 把"计划中的 RSS 守卫 fixture"写成现状（文档虚登，E01）；(2) IDE markdown 格式化器会重排 features.md 表格并把 not_started 转义为 not\_started，verify_feature.py 状态正则失配（E02）。文档描述机制一律区分「已就位/计划（FXX）」双态；脚本对清单文件的解析宽容化（剥离转义、非空白非竖线状态匹配）并以单元测试固化。
- 否决方案: 文档与实现状态混写（读者误信机制存在）；脚本假定清单格式永恒不变（编辑器随手保存即破坏验证链）。
- 约束: E01 入审查清单（语义级暂无法自动化）；E02 回归测试 backend/tests/unit/test_verify_script.py 必须常绿。