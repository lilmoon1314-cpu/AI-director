# DECISIONS.md

> 每条决策记录：关键原因 / 否决方案（一句理由）/ 落地约束。详细背景见对应 git 提交与专题文档。

## 2026-08-24: 后端框架 FastAPI（Python 3.12+）
- 原因: Pydantic v2 运行时校验 + 自动 OpenAPI；原生 async 支持 SSE 与并发上传。
- 否决: Django/DRF（过重、async 不完整）；Flask（需拼装扩展、无类型校验）。
- 约束: 路由按领域模块拆分；请求/响应模型走 Pydantic。

## 2026-08-24: 数据库 SQLite（WAL）+ SQLAlchemy 2.0 + Alembic，图语义在应用层
- 原因: 单用户本地运行零部署；图查询=属性过滤（WHERE + 应用层），无需图数据库；ORM 隔离方言可切换 PostgreSQL。
- 否决: Neo4j（JVM 运维成本、动态 JSON schema 难管理）；直连 PostgreSQL（MVP 无并发写压力）；纯 JSON 文件（无约束校验）。
- 约束: 开 WAL + 外键；schema 变更走 Alembic；视角过滤在 service 层。

## 2026-08-24: 前端 React 18 + TypeScript 5 + Vite 5
- 原因: TS 类型对齐 Pydantic（自动生成）；Vite 快；图可视化生态最丰富。
- 否决: Vue 3（生态略逊）；CDN 无构建（无类型系统）。
- 约束: API 类型由 OpenAPI 自动生成，禁止手写。

## 2026-08-24: 图可视化 AntV G6 5.x
- 原因: 力导向/交互/缩放开箱即用，中文文档全，自定义节点可扩展。
- 否决: D3 裸用（成本过高）；Cytoscape（定制繁琐）；react-flow（偏 DAG）。
- 约束: 布局在前端；高频交互局部订阅。

## 2026-08-24: UI 样式 Tailwind CSS + shadcn/ui
- 原因: 匹配用户 Apple 风偏好（浅底高对比、毛玻璃）；shadcn 源码进仓库可控。
- 否决: Ant Design（设计语言差异大）；纯手写 CSS（无约束发散）。
- 约束: 视觉基调=浅底+高对比深文+毛玻璃+对称间距+克制动效。

## 2026-08-24: LLM 集成 openai SDK（兼容协议）
- 原因: 一套 SDK 兼容主流端点（.env 切换）；MVP 仅需对话+结构化输出。
- 否决: LangChain/LlamaIndex（抽象过度、API 不稳）。
- 约束: 写库必须经用户确认；调用设超时与降级；注入上下文先过视角过滤。

## 2026-08-24: 架构风格模块化单体 + 前后端分离
- 原因: MVP 无独立伸缩需求；模块边界=未来微服务边界；微服务级文档标准约束模块质量。
- 否决: 直接微服务（成本显著收益为零）；单文件大泥球（违反解耦）。
- 约束: 跨模块只走 service 层；模块变更同步其 ARCHITECTURE.md。

## 2026-08-24: 前端状态管理 Zustand
- 原因: 图数据全局共享；selector 粒度订阅避免全树重渲染。
- 否决: Redux Toolkit（样板多）；Context（高频交互全树重渲染）。
- 约束: 高频交互状态必须 selector 局部订阅。

## 2026-08-24: Markdown 同步 markdown-it-py + PyYAML（front matter）
- 原因: 满足离线编辑需求；updated_at 比对实现冲突检测。
- 否决: JSON 导入导出（需求明确为 Markdown 工作流）。
- 约束: 导入先出冲突报告，确认前不写库。

## 2026-08-24: 工具链 uv + pnpm + Makefile
- 原因: uv 锁文件可复现且快；pnpm 磁盘高效；Makefile 唯一命令入口。
- 否决: pip（无锁文件）；npm/yarn（磁盘/碎片化）。
- 约束: 开发命令收口 Makefile；check 聚合前后端全部验证。

## 2026-08-24: MVP 建表范围 entities + relationships 两张
- 原因: 第 1 批功能仅依赖两表；其余 7 张服务第 2 批，提前建=死表+schema 返工。
- 否决: 一次建齐 9 张（死表风险+提前固化错误 schema）。
- 约束: 第 2 批新表走 Alembic；9 张蓝图在 data_struct_define.md 保留。

## 2026-08-24: 约束文档按模块分块（根+backend+7 模块+frontend 共 10 份）
- 原因: 集中文件长度必然失控；分块后改哪读哪；ARCHITECTURE 与 CONSTRAINTS 职责分离。
- 否决: 单一集中文件（长度失控）；约束并入 ARCHITECTURE（职责混杂）。
- 约束: 根文件只留横切约束+导航；AGENTS.md 规定阅读时机。

## 2026-08-24: 开发命令契约对齐 INIT.md（setup/dev/test/check）
- 原因: 新会话只看仓库即知怎么跑怎么测；init.sh 降级薄封装消除双份维护。
- 否决: 自定命令名（与验收清单不符）；init.sh 独立实现（与 Makefile 重复）。
- 约束: 命令名变更同步 AGENTS.md / features.md / INIT.md。

## 2026-08-24: 测试三层验证（L1/L2/L3）+ 每功能测试文档
- 原因: 完成判定客观可验证，防止"实现即完成"；每功能一份测试文档作验收载体。
- 否决: 仅单层测试；每功能多份文档（漂移）；后端独立起进程 E2E（过度工程）。
- 约束: pytest 标 marker；L3 只走公开接口；测试文档验证通过后更新状态。

## 2026-08-24: 架构约束可执行化（import-linter + 架构测试 + 映射表）
- 原因: 文字约束无强制力，必须转为可执行检查；映射表保证每条约束有出处有状态。
- 否决: 仅人工审查（不可持续）；自研检查框架（import-linter 已是标准）。
- 约束: 新增约束同功能点登记映射表；检查纳入 make check。

## 2026-08-24: 错误三要素 + 独立错误日志 + core 统一信号采集
- 原因: 错误信息自解释（problem/cause/fix 构造必填）；五类信号自动采集，业务零手写日志。
- 否决: agent 手写日志（遗漏+格式漂移）；OpenTelemetry（MVP 运维过重）；单文件混合日志。
- 约束: 业务模块禁直接 logging；@checkpoint 自动脱敏限长；采样/轮转参数走 config。

## 2026-08-24: 审查反馈提升流程（错误模式库 + 自动化转化）
- 原因: 错误类型沉淀为自动检查，同类错误只发生一次。
- 否决: 无沉淀机制；仅人工记忆（跨会话失效）。
- 约束: 新类型错误当次会话登记并评估转化，禁止延后。

## 2026-08-24: 跨平台命令面板 scripts/task.py（Makefile 全量委托）
- 原因: Windows 无 make 且 bash 语法失效；纯 Python 实现全部 18 条命令，单一实现源。
- 否决: 只留 Makefile（Windows 不可用）；双实现（行为漂移）；依赖 Git Bash（环境假设强）。
- 约束: 新命令只改 task.py，Makefile 加一行委托；命令名变更同步三处文档。

## 2026-08-24: 功能清单状态由 verify_feature.py 唯一写入
- 原因: 状态自动更新杜绝虚报；先跑完再写终态，保留完整失败上下文。
- 否决: 人工改状态（虚报）；中断即写（丢失失败信息）。
- 约束: 验证命令列只允许 make/pytest/pnpm 前缀。

## 2026-08-24: pnpm store 收进项目根 + 配置文件 ASCII-only
- 原因: 沙箱拦截项目外写入致 EPERM；中文 Windows GBK 读非 ASCII 配置崩溃。
- 否决: 要求用户改系统环境（不友好）；改 npm（放弃 pnpm）。
- 约束: .pnpm-store 入 .gitignore；配置文件禁非 ASCII。

## 2026-08-24: 前端骨架 Tailwind CSS v4（CSS-first）
- 原因: 无需两份配置文件，两行接入；shadcn 已支持 v4；backdrop-blur 原生支持。
- 否决: v3（多配置、进维护期）；CSS Modules（放弃既定体系）。
- 约束: 全局样式只从 index.css 扩展。

## 2026-08-24: 幽灵节点双层防线（FK DDL + ON DELETE RESTRICT）+ foreign_key_check 巡检
- 原因: 应用层校验有旁路风险；PRAGMA 只对声明了外键的表生效，须建表即声明。
- 否决: 仅应用层（旁路无防护）；CASCADE（静默级联=数据失踪）；F02 只建 entities（删除校验无从验证）。
- 约束: 集成测试巡检 foreign_key_check；架构测试断言 FK+RESTRICT；F02 首迁移建齐两表。

## 2026-08-24: 文档机制双态标注 + verify 脚本容错格式化改写
- 原因: 文档虚登（E01）与格式化转义致脚本失配（E02）两处缺陷；机制描述须区分已就位/计划。
- 否决: 文档与实现混写；脚本假定清单格式不变。
- 约束: E01 入审查清单；E02 回归测试必须常绿。

## 2026-08-27: 错误模式库迁移 JSONL（backend/logs/error.jsonl 入版本库）+ 运行时错误日志改名 runtime_error.jsonl
- 原因: 错误模式与测试失败记录需跨会话持久且可被 agent 机器读写；与运行时轮转日志混写同一文件会被 RotatingFileHandler 轮转丢失且污染 git 跟踪内容。
- 否决: 保留 markdown 表格（无法程序化追加/检索）；运行时日志与模式库共用 error.jsonl（轮转+混写）。
- 约束: error.jsonl 只由 agent 维护（追加不覆写）；运行时错误流写 runtime_error.jsonl（gitignore）；AGENTS.md 工作规则新增任务清单同步/测试文档先行/测试失败记录三条硬规则。

## 2026-08-27: F04 三视角过滤规则细化（视角角色恒可见 + marker 字段映射 + audience 边双端校验）
- 原因: 模块文档过滤规则有语义空隙——视角角色自身可见性未定义、实体 known 标记字段按类型分散、audience 边与端点可见性未约束（悬空边/间接泄露风险）。
- 否决: entities 加顶层 known_by 列（改表+迁移，第 1 批无此需求）；audience 只按边自身标记过滤（端点不可见时渲染悬空边并泄露结构）。
- 约束: 实体可见 = 自身 ∪ 标记命中（event→properties.known_by、item→properties.seen_by，脏数据容错）∪ 可见边端点；audience 边须双端可见；character 视角错误统一 PerspectiveError 403（reason 三值）；投影不含 properties/description/known_by（收窄泄露通道）；规则同步模块 ARCHITECTURE.md。

## 2026-08-27: import-linter 契约落地（allow_indirect_imports 只拦直接引用）+ mutmut 2.x 定向变异封装
- 原因: forbidden 契约默认传递闭包，模块自身装配链（router→service→repository）会让组合根与 service 间合法调用误报；mutmut 3.x 配置仅限 pyproject 静态路径、无法按模块参数化，2.x 支持 CLI 定向。
- 否决: ignore_imports 豁免装配边（逐边枚举、新模块必漂移）；mutmut 3.x（无法 `mutate <module>` 参数化）；全仓变异（噪声+耗时）。
- 约束: 内部层私有契约一律 `allow_indirect_imports=true`；新模块落地时同步登记契约与 source 兄弟枚举；mutmut 固定 >=2.4,<3.0，经 `task.py mutate <module> [test_path...]` 触发，不进 make check；kill rate ≥ 85% 且存活变异体逐一分析归档测试文档。

## 2026-08-27: 测试有效性双机制——等价类/边界值设计 + 变异测试（mutmut）
- 原因: 用例数量不等于检出能力；变异测试把「测试有效性」变为可量化指标（kill rate），等价类划分/边界值分析在源头保证覆盖结构，参数化杜绝同构用例漂移。
- 否决: cosmic-ray（维护与并行体验弱）；仅人工断言强度审查（不可量化）；变异测试纳入 make check（全量运行过慢）。
- 约束: mutmut 仅 dev 依赖、按功能模块定向执行（F04 落地工具与 task.py mutate 命令）；kill rate ≥ 85% 且存活变异体逐一分析（补用例或登记等价性）；自 F04 起写入 DoD（docs/testing.md §2/§8/§9）。

## 2026-08-28: F04 变异测试首轮实践——判杀器必须覆盖 L1+L2，错误用例断言须钉死三要素
- 原因: F04 首轮仅以 L1 单元测试判杀，kill rate 仅 47%（41/87）：router 路由注册（prefix/path/装饰器删除）与 Perspective Literal 枚举变异不改变 service 运行时行为，只有经 HTTP 语义的 L2 集成测试可杀；错误三要素文案与 detail 键值变异因 U4/U5 仅断言 reason 单键而存活。
- 否决: 断言 OpenAPI 文档文案（tags/Query/Field description）换 kill rate（钉死文案阻碍正常迭代，4 个变异登记等价性）；仅看 kill rate 总值不逐一分类存活变异体（会漏掉判杀器结构性缺口）。
- 约束: `task.py mutate <module>` 判杀器默认 unit，含 router/schemas 的模块须显式追加 L2 集成测试路径；错误类用例必须断言三要素完整文案 + detail 字典整体相等（仅断言单键视为断言不足）；文档性字符串变异登记等价性、不补用例。
