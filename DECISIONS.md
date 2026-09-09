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
- 约束: 判杀器层级 ⊇ 功能必须测试层级（docs/testing.md §9「判杀器构成」）——L1 单元恒为基线；模块含 router.py 必加 L2 集成路径（HTTP 语义变异仅集成可杀，task.py mutate 自动拦截缺 L2 的调用）；功能必须层级含 L3 时判杀器追加 e2e 路径（跨组件装配变异仅真实组合根可杀），存活分析出现「仅 e2e 可杀」变异体必须补 e2e 判杀重跑；错误类用例必须断言三要素完整文案 + detail 字典整体相等（仅断言单键视为断言不足，E05）；文档性字符串变异（OpenAPI tags/Query/Field description）登记等价性、不补用例。

## 2026-08-28: 等价性登记的豁免边界与三道防线（不影响运行时行为的变异体不钉死文案）
- 原因: OpenAPI 文档性字符串（tags/Query/Field description）不进入运行时数据流，行为测试对其必然存活；钉死文案的用例脆弱且阻碍正常文案迭代。但「不影响运行时行为」是人工判断，直接固化豁免有三类风险：误判（把行为载体当文档）、滥用（等价登记成为 kill rate 不达标的偷懒通道）、时效（今天的纯文档字段随演进进入运行时路径）。
- 否决: 全部钉死换 kill rate（用例脆、维护成本高，F04 已论证）；不设风控的口头豁免（§9 门槛被架空）。
- 约束: 豁免唯一判定标准 = 该标识符不进入任何运行时数据流（路由匹配/参数解析与校验/响应序列化/持久化/错误响应体均属运行时——错误三要素文案在响应体中，是行为契约，必须钉死；Query(alias)/Literal/Enum 值/prefix/path/response_model 貌似文档实为行为，严禁豁免）；等价登记逐条写明核实依据；测试文档须同时报告实杀数与等价登记数，等价数 > 变异体总数 20% 视为门槛失真、逐条复核；结论仅对当次验证时点有效，行为演进使文档字段进入运行时路径即失去豁免。规则落点 docs/testing.md §9「等价性登记」。

## 2026-08-28: F05 决策两项——前端功能豁免 mutmut；UI 组件自研轻量实现（不引入 shadcn CLI）
- 原因: mutmut 仅支持 Python，无法变异 TypeScript/React，DoD 第 5 条对前端功能不可执行；shadcn/ui 初始化是交互式 CLI 且需与 Tailwind v4 调试兼容，F05 所需组件少（毛玻璃面板/按钮/输入框/表单），完整引入成本远超收益。
- 否决: StrykerJS 前端变异（工具重、Windows 体验未知、拖慢首批交付，留待后续评估）；完整 shadcn/ui（CLI 自动化不确定性 + 兼容调试成本）。
- 约束: docs/testing.md §2 DoD 第 5 条与 §9 注明 mutmut 仅适用 backend/app 的 Python 模块，前端测试有效性由 §8 等价类/边界值设计 + L1/L2/L3 层级测试保障，引入前端变异工具前须先修订该条；UI 组件按 frontend/CONSTRAINTS.md 视觉规范自研（毛玻璃 backdrop-blur + 浅色基调 + 动效 ≤200ms），frontend/ARCHITECTURE.md §1/§2 措辞同步更新。

## 2026-08-28: F06 视角切换的作用面——仅约束 /api/graph 展示面，详情/编辑保持数据管理面完整
- 原因: F06 的需求是「切换后图数据按视角刷新」（展示面）；而后端 /api/entities/:id 等读写 API 自 F02 起就是无视角概念的数据管理接口（作者工具语义）。若让详情面板也按视角隐藏/禁用编辑，等于把「读者可见性」混入「作者编辑能力」，第 1 批 MVP 的数据管理目标会被视角切断（角色视角下无法修数据）。
- 否决: 详情面板按视角降级（隐藏字段/禁用编辑）——把两层语义耦合，成本高且与 MVP 目标冲突；character 视角禁用写操作——同上。
- 约束: 视角隔离的唯一执行点在后端 F04 perspectives.service 且仅作用于 GET /api/graph；前端断言面 = 参数透传 + 展示一致 + 观众视角页面文本不出现 audience_known=false 实体名（E2 不泄露断言）；详情面板/新建/编辑/删除保持全量管理能力；角色下拉数据源为管理接口 /api/entities?type=character（列全量角色，属作者工具面，非泄露通道）；characterId 回切保留但仅随 character 视角请求发送（不泄入 author/audience 请求，graphStore 收口 + 单测边界用例锁定）。

## 2026-08-28: F07 关联实体的可见性提示与名称解析——前端图数据判定 + 名称仅显示层
- 原因: 选择器需提示「实体对当前视角是否可见」，若新增后端可见性判定接口则每敲一次关键字都要跨视角重算（character 视角可见集依赖 known_by 推导，代价高且与 F04 查询语义重复）；关联字段若在存储层改名则破坏既有数据与 API 契约。
- 否决: 后端新增「按视角过滤检索」接口——重复 F04 职责、关键字检索无法廉价重算角色视角；属性存储层改为存名称——名称可改、id 才是引用稳定键，破坏单一事实源。
- 约束: 可见性判定 = 实体 id 是否在当前 graphStore 图数据节点集合内（author 全量恒可见，audience/character 与画布一致，无新增后端接口）；EntityBrief 仅新增只读字段 audience_known 供提示文案；表单态与 PATCH/POST 载荷恒存实体 ID，名称解析只发生在显示层（entityIndexStore 索引 + displayRefValue），未收录 id 回退原始值显示。

## 2026-09-05: F08 重新定界为「资产管理」（HTML 形态资产库），F09 Markdown 导入导出取消
- 原因: 用户决策——资产是后续向大模型传递多模态上下文的载体，沿用 Kimi「HTML 替代 Markdown 文件」理念，每个资产存为自包含美观 HTML；需要专门管理界面：工作台改「图谱|资产管理」双页，资产分通用资产（表情/风格/植被等可复用参考）与项目资产（实体按类型分组卡片，点开 HTML 资产页）。
- 否决: 保留 F09 Markdown 导入导出（被 HTML 资产形态取代，无残留需求）；沿用原 F08「仅上传+详情缩略图」设计（范围过窄，properties.assets 引用方案废弃）。
- 约束: features.md 移除 F09 行（本次为范围决策而非状态手改，状态列仍由脚本管理）；backend/app/sync 占位模块与全部文档引用一并移除；F10 编号不变；图片文件仍落盘 ASSET_DIR 并沿用白名单/大小上限/uuid 重命名/流式写盘硬约束。

## 2026-09-05: 资产库独立 SQLite 文件（data/assets.db）+ 启动 create_all 幂等引导（Alembic 例外）
- 原因: 用户确认「单开一个数据库」存资产 HTML 与图片元数据；资产库是派生展示层+素材存储，与世界观主库（单一事实源）生命周期不同，隔离后主库保持纯世界观语义。
- 否决: 主库加 assets 表（两种生命周期数据混在一个文件）；Alembic 双迁移链（为新建独立库引入双链配置与 task.py/conftest 联动成本，MVP 收益低）。
- 约束: assets.db 经 lifespan 启动时 metadata.create_all 幂等引导（backend/CONSTRAINTS.md「schema 变更走 Alembic」对资产库豁免，已同步修订约束文本）；后续 schema 变更须对既有文件向后兼容（加列加表，禁删改列），出现破坏性需求时再评估引入迁移链；图片文件不入库，仅存元数据与相对路径；assets→entities 单向依赖，实体资产页按 entity.updated_at 惰性生成/过期再生，实体删除的资产清理走「列表时孤儿清扫」而非删除回调（避免循环依赖与跨库 FK）。

## 2026-09-05: 通用资产自定义属性——MVP 以自由 attributes JSON 兜底，schema 注册表+agent 定制推迟第二阶段
- 原因: 用户需要表情参考等资产携带自定义属性（类型、提示词（眉毛/眼睛/嘴巴）、强度），且要求资产模块高度解耦、可热插拔；完整方案（按分类的属性 schema 注册表、动态表单、agent 辅助生成 schema 与 HTML 模板）复杂度高，用户确认复杂逻辑放第二阶段。
- 否决: 本期实现 schema 注册表+动态表单（工作量与风险大，且自由属性 JSON 可无损升级为 schema 驱动，推迟不损失数据）。
- 约束: 本期通用资产 = 固定基础字段（分类/标题/描述/图片）+ attributes 自由 JSON（HTML 模板按键值小节渲染）；分类为自由字符串标签，增删分类零代码变更；asset_records.attributes 列即热插拔边界，第二阶段 schema 注册表落地时作为迁移输入；第二阶段候选项（agent 辅助定制 schema/模板、HTML 源码级编辑）已登记 PROGRESS「下一步」，届时必须先立功能项再实施。

## 2026-09-06: 质量门禁双强化——变异证据机器门禁 + 验收审查子代理协议（用户决策）
- 原因: 用户指出两个流程风险——①变异测试暴露测试问题后『测试强化→重跑正常测试→重跑变异』闭环仅靠纪律无机器强制（E12 同类）；②实现者自查存在确认偏误（E13 实证：层叠缺陷在实现上下文里不可见，直到 e2e 才暴露），验收需要无实现上下文的独立审查。
- 否决: 仅登记审查清单（无强制力）；由主智能体附带审查（上下文污染，正是要解决的问题）；verify 内跑 mutmut（成本失控，按功能点手动触发的原则不变）。
- 约束: ①verify_feature.py 写 passing 前强制变异证据门禁（缓存存在/含该模块/kill rate≥85%/晚于模块最后提交；F04 起、L1 文件名约定定位模块；带 9 项单测）——重验旧功能时若其模块被后续功能改过会被要求重跑该模块变异（DoD 诚实反映）；②验收审查子代理协议落 docs/testing.md §10（只读、自包含 prompt、结构化发现、verify 前触发、发现按 lessons §1 提升），F11 试点即抓出 P0（E14：keyed 重挂载下 ref 跨挂载检测不可达，已修复并加锁定用例）；AGENTS.md 工作规则同步。

## 2026-09-06: F11/F12 功能拆解与多项目底座四项实现决策（用户批准按 DESIGN.md §12 建议稿开工）
- 原因: DESIGN.md 落地拆解获批——新增 F11 多项目底座、F12 工作台导航与资产页重构，F10 编号不变挪后执行；实现层面落定四项：①前端引入 react-router（OQ-1 落定，路由化是「URL 即状态」原则基础）；②API 渐进迁移——既有领域端点增加可选 `project_id` 查询参数（缺省=默认项目），`/api/projects/{pid}/...` 路径前缀迁移推迟（避免单功能点重写 155 项既有后端测试；内部 MVP 无外部消费者，前端类型重生成即可切换）；③projects 依赖方向执行——仅依赖 core；跨模块级联删除（删项目）在 projects.router 编排各领域 service（组合根模式，业务规则仍在各 service，避免 projects↔领域模块循环 import）；项目列表的实体/关系计数与最近活动时间戳为反规范化列，由 entities/relations 写路径在同库事务内维护（projects 只依赖 core 仍成立，读取无跨模块聚合）；④默认项目固定 id、迁移打包存量数据、不可删除（无 project_id 请求的兜底目标）可改名；删项目的 assets.db 清扫失败由既有「读取时孤儿清扫」兜底（跨库补偿）。
- 否决: 一步到位路径前缀式 API（单功能点重写全部 L2/e2e，粒度失控）；projects.service 反向调用领域 service 做级联（与领域模块循环 import，违反依赖方向）；读取时跨模块聚合计数（projects 需 import entities，同违依赖方向）；允许删除默认项目（无 project_id 的兜底写入目标失效，重建逻辑魔法化）。
- 约束: F11/F12 行已入 docs/features.md（状态由脚本管理）；F11 测试文档 docs/tests/F11_multi_project_foundation.md 先行；import-linter 契约随 projects 模块落地登记；DESIGN.md/backend·frontend 文档中「规划」条目随实现翻转为已就位（双态标注）。

## 2026-09-06: 交互设计基线 DESIGN.md v1——独立项目首屏 + Agent 同一会话池 + 通用库留驻资产页（本轮仅设计文档）
- 原因: F10（Agent 长对话与项目记忆）硬依赖多项目隔离（图谱/项目资产/记忆/会话随项目，通用资产与 harness/skills 全局），而现状为隐式单项目且前端无路由、无项目概念、agent 零载体；经与用户对齐四项交互决策后成稿交互设计基线（现状诊断 9 条/两层作用域模型/路由方案/五页面设计/端到端剧本/前后端蓝图/测试锚点/开放问题 OQ1–OQ7）。
- 否决: 直达最近项目无独立首屏（项目上下文错位代价高，误写入污染图谱与记忆）；侧边栏临时快聊不持久（割裂长期记忆，违背 F10 目标）；通用库独立顶层入口（创作时找参考多一跳）；多项目改造并入 F10（粒度过大，违背一次一个功能点）。
- 约束: 本轮只交付设计文档——不改代码、不改 features.md 功能清单，落地拆解（建议：多项目底座→工作台与资产页重构→F10 挪后）待用户审阅 DESIGN.md 后另行立功能项；路由库引入（OQ-1 推荐 react-router）等开放问题实现期正式决策；AgentDock 会话级 SSE 生命周期落地时须同步修订 frontend/CONSTRAINTS.md「SSE 随组件卸载中断」条目；DESIGN.md 已收录 AGENTS.md 专题文档路由（改导航/页面结构/多项目交互前必读）。

## 2026-09-06: F12 工作台导航与资产页重构——分区路由化 + 两级钻取 + modal 化落定（按 DESIGN.md §5.3/§9/§10 实施）
- 原因: F12 立项（F11/F12 拆解决策延续）——资产页原为组件内 useState 双分区（刷新即丢、无法深链），项目资产平铺 7 组过长（D2/D4/D7），通用资产表单整区替换丢上下文（D5）；按交互基线将分区状态升级入 URL。
- 否决: 分区/类型库状态留 store 不入 URL（违背「URL 即状态」原则，浏览器后退/深链失效——两级钻取的后退收益正是路由化动机）；搜索词入 URL（DESIGN §4.2 明确 MVP 留 store/组件态，深链需求出现再评估）；复用 ProjectPicker 内联 modal 结构（三处 modal 使用已具共性，抽 ui/Modal 组件收敛，但不回改 ProjectPicker 既有 modal——不在实现 A 时顺便重构 B）。
- 约束: ①资产页分区即子路由 `assets/general`（默认落点，OQ-6）|`assets/project`（类型库墙）|`assets/project/:entityType`（详情），无效 entityType 重定向回墙；②react-router 嵌套 `<Outlet>` 不自动继承 context——AssetLibrary 必须显式回传 Workbench 的 projectId context（集成测试抓出的真缺陷：遗漏时深链在 store 同步前拼出 /projects/undefined/...，已入 frontend/CONSTRAINTS.md）；③空类型引导「去图谱页创建」经 `?create=entity&type=<valid>` 查询参数联动，GraphView 挂载时消费并清理（防重挂载重复弹出），非法类型回落默认；④分区搜索为前端过滤纯函数（lib/assetFilters.ts，L1 覆盖），空库引导卡与搜索无命中提示文案可区分；⑤F12 纯前端无后端改动——变异证据门禁按模块定位规则自动跳过（无 test_<module>_service.py 约定文件），后端资产集成回归 16 项通过；ProjectAssetSection 平铺分组组件语义退役删除，testid 迁移映射见 docs/tests/F12 测试文档。

## 2026-09-07: F10/F13 范围切分——F10 对话底座先行，创作工作流（harness 清单/plan-and-execute）拆 F13
- 原因: 用户对任务10的规划诉求覆盖记忆/思考模式/检索/prompt 成本/安全五域，其中创作工作流（harness 必须事项清单核对、故事大纲模板含权重时长、plan-and-execute 步骤可视化、作者意见征求交互）体量大，与「每次只完成一个功能点」规则冲突。
- 否决: F10 一次做全（验证周期失控，测试面过大）。
- 约束: F10 = 会话持久化 + SSE 对话 + 草案两段式 + 记忆文档 + 图谱检索 + SSE 事件协议预留（draft/doc_patch/ask_user/plan/step 事件类型仅定义不消费）；F13 = harness 清单（L0 配置层）逐项核对、故事大纲模板、plan/step 步骤卡、ask_user 征求卡、多方案备选征求；已登记 PROGRESS「下一步」，届时先立功能项。

## 2026-09-07: 记忆文档 HTML 分段模板取代 DESIGN OQ-2 的 markdown 方案（用户「坚持 html 替代 md」）
- 原因: 影视文本长且强关联，全文重写浪费 token——段级存储（memory_doc_sections）使 LLM 与用户都只读写单段；与既有 assets HTML 自包含渲染实践（DECISIONS 2026-09-05）同构，模板按 kind 定义段结构、段内容独立替换。
- 否决: memory_docs 单列 markdown（OQ-2 原推荐，全文读写+整篇覆盖冲突面大）；富文本编辑器依赖（前端零依赖原则，段级结构化表单+iframe 预览够用）。
- 约束: 段级 CAS 乐观锁——agent patch 与用户保存共用 PATCH 端点（expected_version 不符 409，绝不覆盖：用户手改优先，agent 基于旧版本的 patch 一律作废重读）；doc.version 与 section.version 双层 ETag；LLM 常驻只读「目录（段标题+内容 hash）」，全文经工具按段读取；事实边界不变——世界观事实只进图谱，禁止写入记忆文档（agent/CONSTRAINTS.md）；F10 内置 positioning/style 两模板，story_outline 模板留 F13。

## 2026-09-07: 思考模式——外层 Plan-and-Execute（F13）+ 步内轻量 ReAct（配额受控）+ 多方案征求替代 ToT
- 原因: 用户要求引入 AI coding IDE 的 plan-and-execute 使过程可视化（progress 作用）；ToT 树搜索 token 成本数倍且创作评价主观，作者本就该对创作分叉拍板——人在环中的「2-3 备选方案征求」以极低成本获得同等的探索-收敛效果。
- 否决: 真 ToT 树搜索（成本/收益失配）；无工具单轮生成（长文本强关联场景下上下文要么爆炸要么失忆）。
- 约束: F10 落受控 ReAct——每条用户消息工具调用配额来自 config（AGENT_MAX_TOOL_CALLS_PER_TURN），超限撤下工具定义强制作答，防循环；SSE 事件协议预留 plan/step/ask_user 类型，F13 消费；tool 事件前端渲染为「正在检索图谱…」行为指示。

## 2026-09-07: 图谱检索——目录式两跳 + perspectives.filter_entities_for_agent（不引向量库）
- 常驻上下文只放「图谱目录」（类型分组 id+名称+别名紧凑清单，来自 get_graph 轻量投影，天然过视角过滤）与「文档目录」（段标题+hash），实体完整属性经四个检索工具按需两跳获取；GraphData 投影无 properties/description，故在 perspectives 模块内新增 filter_entities_for_agent（复用 _visible_sets 单一可见性规则，返回含 description/properties 的 EntityContext 全量投影）——可见性判定仍单一在 perspectives，agent 禁止绕过。
- 否决: 向量检索/嵌入库（项目千级实体规模下名称+别名检索+目录导航足够，引入嵌入管线成本不成比例，登记第二阶段再评估）；agent 侧复制可见性规则（违反单一事实源）。
- 约束: filter_entities_for_agent 对请求中不可见/不存在的 id 静默剔除（调用方决定语义）；工具结果注入前必须经 wrap_data 数据分隔符包裹 + truncate_output 截断（提示注入与上下文保护双防线）。

## 2026-09-07: Prompt 成本与安全——分层前缀缓存 + 预算裁剪 + 内置三防线 + 内容合规 hook（用户确认）
- 拼装顺序稳定→易变（system→文档段→图谱目录→摘要→近期消息）以吃满 OpenAI 兼容端点的自动前缀缓存；预算裁剪固定顺序（文档段全文降级为目录→丢摘要→自最旧裁消息，system 与本轮输入永不裁）；摘要等杂活路由轻量模型（LLM_MODEL_LIGHT）；usage 逐调用记入运行事件观测。
- 安全三防线内置：写入安全（草案 Pydantic 白名单+confirm 服务端复核+会话归属项目注入+两段式）、提示注入防护（数据/指令分隔符+「数据非指令」声明+工具输出截断）、输出安全（HTML 全转义+SSE 事件白名单+密钥仅 config+日志脱敏）；内容合规做成 config 开关 hook（AGENT_CONTENT_REVIEW_ENABLED，MVP 本地敏感词表，预留外部审核 API 替换位），默认关闭。
- 否决: MVP 即外接内容审核 API（需选型/密钥/按量成本，hook 位已预留）；无预算控制的全文注入（长剧本场景 token 失控）。
- 约束: 上下文预算与窗口/配额/截断上限全部来自 config（AGENT_*），禁止硬编码；llm.py 对 SDK/网络异常统一包装 AgentError 三要素，禁止原始异常冒泡；usage 经 core.observability.emit_event 采集（禁散点日志）。

## 2026-09-07: F10 落地基线偏离清单（验收审查 §10 第 3 轮触发登记）
- 偏离项（DESIGN.md 已同步加 F10 落地注记）: ①Dock Esc 收起与「会话切换下拉+＋新会话」顶栏暂未实现（随 F13——期间经 AgentHome 会话列表与 ✕/Ctrl+J 切换）；②confirm 成功态以「消息流摘要 + 草案卡清空」实现（DESIGN 原文卡片转成功态，语义等价）。
- 原因: F10 范围收敛于对话底座（2026-09-06 用户切分决策）；Esc/下拉属交互增强非链路必需，成功态两形态信息量一致。
- 约束: 后续功能落地上述交互时必须回写 DESIGN.md 移除注记；不得在无关功能中「顺便」实现（工作规则）。

## 2026-09-07: 会话/记忆文档端点越权边界——不可猜 id 为 MVP 防线（验收审查 §10 触发登记）
- 决策: agent 会话/消息/记忆文档端点按全局唯一 id 寻址、仅校验存在性——不携带项目上下文校验归属；跨项目越权防护以 id 不可猜性（conv-/msg-/mdoc-/msec- + uuid 前缀 12 位十六进制）为 MVP 边界。
- 原因: F11 渐进迁移约定下 agent 端点为查询参数式项目维度（路径无项目段），逐端点强制归属需引入 project_id 参数或从资源反查——MVP 单用户本地场景收益低；图谱数据注入已由视角过滤硬防线覆盖（I3 钉死），越权面仅限会话内容与文档读写。
- 约束: 路径参数式项目维度 API 演进（DESIGN §8.4 终态）时收紧为归属校验；升级前禁止在 agent 端点暴露任何按项目枚举的未鉴权列表；read_doc_section 工具已按会话归属项目拒绝跨项目读取（tools.py，保持）。

## 2026-09-08: Agent 写入工具用户许可——轮末统一确认（用户裁决，DESIGN OQ-8）
- 原因: agent 具备写文档/建实体/建关系能力后必须保留作者主导权；轮末确认不打断流式、实现可靠（无 SSE 挂起等待机制）、与 F10 两段式写入哲学同构——写入工具执行时仅登记 pending（agent 收到「待作者确认」tool result），本轮 done 事件携带待写入清单，前端渲染确认卡（逐项勾选/全部写入/放弃），approve 时服务端二次校验后落库并触发图谱/文档失效刷新。
- 否决: 工具级即时确认（每次写入暂停流式等待批准——SSE 单向流需挂起机制，长对话反复停顿体验碎、实现复杂度高）；全自动写入（违背作者主导）。
- 约束: 新表 agent_pending_writes（conversation/project/kind/payload/baseline/status）；落库复用 entities/relations/agent 既有 service（校验单一来源）；approve 服务端复核不信任前端；每轮 pending 上限走 config（AGENT_MAX_PENDING_WRITES）；段级写入保留 CAS（baseline version 落库时校验，冲突作废重读）；propose 端点保留标注 legacy。

## 2026-09-08: 多系列共享世界观——项目内系列维度（用户裁决，DESIGN OQ-9）
- 原因: 项目 = 世界观宇宙（图谱/指导文档/通用资产全系列共享），series 表 + entity_series 多对多（无关联=共享底座、挂关联=系列专属），memory_docs.series_id 挂载剧情文档——一次建世界观多系列复用，图查询/资产/agent 上下文按系列过滤；用户明确否决分开管理（多项目割裂）。
- 否决: 多项目 + 实体引用继承（引用同步复杂、切换割裂）；自由标签轻量起步（无结构约束力，后期迁移成本高）。
- 约束: 关系不挂系列（过滤按端点实体归属推导）；series 视图 = 共享实体 ∪ 该系列实体；agent 对话带 series 参数（目录与检索工具同口径过滤，共享底座常驻）；资产图片随实体走不做独立系列归属；F16 落地。

## 2026-09-08: 全局用户画像——自动沉淀 + 透明可编辑（用户裁决，DESIGN OQ-10）
- 原因: 跨项目偏好/画像靠手动维护必然荒废（用户不记得自己的偏好表达），agent 每轮经 LLM_MODEL_LIGHT 后台提炼候选条目自动入库（限 N 条/轮，config 开关），下一轮 system 注入画像摘要跨项目生效；同时全部条目在 /global-memory 页可查看/编辑/删除/手动新增——自动积累与透明可控并存。
- 否决: 每次确认后沉淀（频繁打断对话、积累慢）；纯手动（画像目标落空）。
- 约束: 新表 global_memory_entries（无 project_id，kind: preference/motif/taboo/fact + 来源会话）；画像注入预算内截断；默认开关 AGENT_PROFILE_AUTO_CAPTURE=true；F15 落地。

## 2026-09-08: F13–F16 立项与编号重组（用户裁决：体验→写入→记忆→系列）
- 内容: F10 验收反馈五类问题拆四个功能项（features.md 已增行）：F13 对话体验升级（真流式+reasoning_content 思考可视化+usage/上下文容量窗口+会话/文档删除+编辑大弹窗+指导文档唯一性+Dock 下拉/Esc 兑现）；F14 写入工具链（轮末统一确认，见上条决策）；F15 长期记忆体系（guide 唯一/work 多实例文档类型学+outline/screenplay/episode_script/storyboard 作品模板+全局画像+search_session_summaries 跨会话检索）；F16 多系列剧情线（见上条决策）。
- 原编号重组: 原「F13 创作工作流」拆解——故事大纲模板并入 F15 作品类模板注册表；ask_user 多方案征求卡并入 F14 确认机制族；plan/step 步骤卡与 harness 必须事项清单移第二阶段候选。
- 技术前提（已实测 2026-09-08）: 百炼 deepseek-v4-flash-0731 原生输出 reasoning_content（默认开启）、stream=True 分片可用、include_usage 可取精确 token 统计——真流式与思考可视化方案成立。
- 约束: 每功能照 AGENTS.md 全流程（测试文档先行/§10 审查/verify 含变异门禁）；实施顺序 F13→F14→F15→F16，不得并行开工。


## 2026-09-09: 变异测试成本治理——文件级缩域 + 契约数据源头豁免 + 指纹续跑
- 决策: `task.py mutate` 升级三能力：①`--files=a.py,b.py` 文件级缩域（功能级运行默认只变异本功能触碰的文件，未触碰文件的判杀力由既往功能验证；模块级里程碑/重构或怀疑未触碰区域漏杀时才全量）；②静态契约数据源头豁免——纯声明数据独立成零逻辑模块（先例：agent/tool_specs.py）并排除在缩域路径外，等效 §9 等价性登记的源头化（行级 `# pragma: no mutate` 为备选）；③缓存按基线指纹（模块源码树 + 判杀器 + 变异路径 sha256）管理——指纹一致（同基线中断恢复）续跑、任一变化清空重跑，E12「旧存活状态残留谎报 kill rate」防控保持且比 mutmut 自带失效机制更严。
- 原因: agent 模块变异体 F13→F14 由 1174 涨至 1887（tools.py 633 + service.py 608 占 66%），全模块口径下每功能重付全价、缓存每轮清空（E12 正当但使中断即全废），实测 ~6s/变异体 ≈ 3 小时/功能不可持续；工具描述等 prompt 契约文本变异无法被行为测试判杀，逐条等价登记的分析成本同样畸高。
- 否决: 升级 mutmut 3（原生并行可降墙钟 4-8 倍，但缓存 schema/命令体系全变、verify 变异门禁需重写，迁移风险大——留作独立基建项评估）；跨功能复用缓存（判杀器每功能必变，mutmut 2.x 失效机制不可靠见 E12，不安全）。
- 约束: 缩域证据与 verify 变异门禁兼容（门禁按模块前缀聚合缓存）；被排除文件必须零逻辑纯数据且在测试文档「变异测试结果」披露 scope；docs/testing.md §9 范围/等价豁免/成本控制条目已同步修订。
