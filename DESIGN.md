# DESIGN.md — 前端交互设计基线（多项目工作台 v1）

> 状态：**设计基线**（2026-09-06 与用户对齐四项关键决策后成稿）。落地进度：F11 多项目底座（§4 导航骨架/§5.1 项目首屏/§7 重置矩阵/§8 后端蓝图）与 F12 工作台导航与资产页重构（§5.3 资产页两级钻取与分区搜索/空态引导/modal 化、§9 卡片规范资产卡落地、§10 testid 迁移；分区入 URL，OQ-3/OQ-6 落定）**均已实现**——验收状态以 docs/features.md 对应功能行（验证脚本唯一写入）与 docs/tests/F11、F12 测试文档为准，本文件不重复登记；F10（§5.4/§5.5 Agent）待实施。
> 读者：实现工作台导航 / 资产页 / Agent 界面 / 多项目改造相关功能前的 agent 与用户。
> 与其他文档的关系：本文约束**信息架构与交互流程**；视觉硬指标以 `frontend/CONSTRAINTS.md` 为准、技术决策以 `DECISIONS.md` 为准、数据蓝图以 `docs/data_struct_define.md` 为准——若冲突，以后三者为准并回改本文。

---

## 0. 文档定位

- **要解决的问题**：当前应用是隐式单项目（整个 app.db 即一个世界观），前端无路由、无项目概念、无 Agent 载体，无法支撑 F10（Agent 长对话与项目记忆）所需的多项目隔离；同时现有交互存在层级混乱、无搜索、无空状态引导等问题。
- **范围**：完整交互流程设计——信息架构、路由、五个界面的页面级设计、跨页面剧本、前端状态蓝图、多项目后端影响蓝图（供后续功能项拆解，**非本轮实施**）、测试锚点。
- **非目标**：本轮不改代码、不改 `docs/features.md`、不引入依赖；落地拆解见 §12（仅为建议稿，待用户审阅后另行立功能项）。

---

## 1. 现状诊断（为什么需要重设计）

基于 2026-09-06 对前后端代码的完整盘点（前端无路由无项目概念；后端 entities / relationships / asset_records 等全部无 project 维度；`backend/app/agent/` 为纯文档空壳）：

| # | 问题 | 事实依据 |
|---|------|----------|
| D1 | **无 URL 路由**：页面状态刷新即丢、浏览器后退失效、无法深链分享，e2e 只能靠 testid 点击链导航 | `App.tsx` 直接渲染 `<Workbench />`；package.json 无任何路由库 |
| D2 | **两级切换嵌套层级不清**：顶栏 tab（图谱\|资产）+ 资产页内二级胶囊（通用\|项目）语义重叠 | `Workbench.tsx` useState tab + `AssetLibrary.tsx` useState section |
| D3 | **「项目资产」命名失实**：现有"项目资产"实为"实体资产"，与真正的多项目概念撞名 | 后端 8 处「项目资产」docstring 均指实体资产分区 |
| D4 | **无搜索**：资产页与项目选择均无文本检索（全项目唯一防抖检索在 @ 选择器） | `AssetLibrary.tsx` 仅有分类 chips 前端过滤 |
| D5 | **表单替换式渲染丢上下文**：新建/编辑通用资产时整区被表单替换，卡片墙消失 | `GeneralAssetSection.tsx` 条件渲染 `GeneralAssetForm` |
| D6 | **Agent 零载体**：agentStore / agent-panel 仅存在于 ARCHITECTURE.md 规划，F10 无处安放对话入口 | `src/` 全目录 grep "agent" 零命中 |
| D7 | **空状态缺失**：空图谱 / 空资产 / 空项目无任何引导 | 各视图无 empty state 分支 |
| D8 | **多项目硬缺失**：无 projects 表、无 project 字段、无项目端点；`global_state` 单例表蓝图隐含单世界假设 | `docs/data_struct_define.md`、`config.py`、全部 router |
| D9 | **键盘可达性为零**：仅 Esc 关查看器一处 | 全局无快捷键约定 |

---

## 2. 设计原则

1. **上下文先行（Context before content）**——先选项目，再工作。项目上下文错误是本工具代价最高的误操作（污染图谱 / 污染 Agent 记忆），因此入口必须有明确的"选项目"仪式（独立首屏），而非默默直达。
2. **URL 即状态**——导航的唯一事实源放 URL：刷新 / 后退 / 深链 / e2e 锚点全部可靠；store 只承载 URL 之外的瞬态。
3. **渐进披露（Progressive disclosure）**——信息按"概览 → 分组 → 详情"逐级展开（项目卡片 → 类型库墙 → 实体卡片墙 → HTML 详情页），任何一屏只呈现当前层级需要的内容。
4. **内容优先、chrome 退后**——Apple 简约基调：大留白、毛玻璃轻层、克制动效（≤200ms）、控件在需要时出现（悬浮菜单、折叠区）。
5. **作用域永远可见可辨**——全局内容（通用参考库）与项目内容（图谱 / 项目资产 / 会话 / 记忆）在 UI 上始终有明确标识（徽标 / 位置 / 文案），用户任何时刻都能回答"我现在在哪个项目、看的是全局还是项目的东西"。
6. **危险操作显式化**——删除项目 / 删除实体等不可逆操作必须列出后果清单并二次确认；Agent 写库恒经 propose→confirm 两段式（既有决策）。

---

## 3. 核心概念模型：两层作用域

```
┌─ 全局层（跨项目共享，不随项目切换变化）─────────────────┐
│  • 通用参考库（表情/植被/风格等 general 资产，assets.db） │
│  • Agent harness 与各类 skill（代码/配置层，非库表数据）    │
└──────────────────────────────────────────────┘
                    ↓ 被所有项目引用
┌─ 项目层（随项目切换整体置换）───────────────────────┐
│  Project = 一个影视世界观的完整工作区                  │
│  • 图谱：实体 + 关系（app.db，project 隔离）           │
│  • 项目资产：实体资产页 + 实体图片（assets.db，经实体归属）│
│  • 记忆文档：项目工作上下文（markdown，见 §5.4 定位）    │
│  • 对话会话：Agent 会话池（按项目隔离）                │
└──────────────────────────────────────────────┘
```

心智模型一句话：**「项目 = 一个世界；先进入世界，再查看它的图谱、资产，并和记忆着这个世界的 Agent 对话。」**

记忆文档的定位（对齐单一事实源约束）：记忆文档**不是世界观事实的副本**——事实以图谱为准；它是"给 Agent 的项目工作上下文"：项目定位与基调、风格约定、创作阶段、从对话沉淀的决策与待办。用户可建可编辑，Agent 可读（Agent 写入属第二阶段）。

---

## 4. 信息架构与导航

### 4.1 站点地图

```
/(redirect → /projects)
/projects                              项目首屏 ProjectPicker
│
└─ /projects/:projectId               工作台壳层（顶栏 + 内容区）
   ├─ /graph                          图谱页 GraphView
   ├─ /assets/general                 通用参考库（全局，默认落点）
   ├─ /assets/project                 项目资产 · 类型库墙
   │  └─ /assets/project/:entityType  类型库详情（实体卡片墙）
   └─ /agent                          Agent 主页（无会话 = 欢迎页）
      └─ /agent/s/:sessionId          Agent 主页（选中会话）

overlay（不占路由，壳层挂载）：
   • AgentDock 右侧对话边栏（图谱/资产页可唤起；?dock=1 可选深链）
   • AssetHtmlViewer 全屏 HTML 查看器（沿用 F08，z-50）
```

### 4.2 路由方案

- **引入 react-router（推荐，开放问题 OQ-1）**：`/projects/:projectId/*` 路径参数承载项目上下文，刷新 / 后退 / 深链天然可靠；实现期正式入 DECISIONS。
- 视角（perspective + characterId）与资产页搜索词留 store 不入 URL（MVP 简化；若 e2e 需要 `?perspective=` 深链再评估）。
- projectId 变化 = 各数据 store 的重置换机（§7 矩阵），路由参数是项目上下文的唯一事实源（URL ↔ projectStore.current 双向同步）。
- 无效 projectId（已删除 / 篡改）：显示错误页（三要素文案）+「返回项目首屏」按钮。

### 4.3 工作台壳层（顶栏）

```
┌────────────────────────────────────────────────────────────┐
│ ✦ [长安怪谈 ▾]      图谱   资产   Agent                ⚙   │
└────────────────────────────────────────────────────────────┘
  ↑logo(回首屏)  ↑项目切换器   ↑主导航(胶囊组)          ↑全局菜单
```

- **logo ✦**：点击返回项目首屏（不弹确认；项目数据已实时落库，无未保存态）。
- **项目切换器 `[当前项目 ▾]`**：下拉列出全部项目（名称 + 实体数）+「＋ 新建项目」+「管理全部项目」（回首屏）；选中即切换（§4.4）。
- **主导航**：三页签胶囊组「图谱 | 资产 | Agent」，激活态沿用现有样式（`bg-slate-800 text-white`）；testid 沿用 `main-nav` / `tab-graph` / `tab-assets`，新增 `tab-agent`。
- **全局菜单 ⚙**（MVP 可仅占位）：技能管理 / Agent harness 配置（全局层内容，第二阶段展开）。
- AssetHtmlViewer 与 AgentDock 挂载于壳层，任何页签可用。

### 4.4 项目切换交互

1. 触发：顶栏切换器选项目 / 首屏点卡片 / 删除当前项目后自动回首屏。
2. 执行序：**中止进行中的 SSE 流**（防跨项目上下文污染；会话历史已落库，回来可继续）→ 更新 URL → projectStore 置换 → 各 store 按 §7 矩阵重置 → 页面懒加载新项目数据。
3. 防误触：切换器内当前项目高亮标注「当前」，点击当前项目为无操作。
4. 图谱页表单若有未提交输入：MVP 不拦截（输入框内容随组件保留在 DOM，切回同项目不丢；跨项目丢弃）——登记开放问题 OQ-5。

---

## 5. 页面级设计

> 每页给出：线框 / 元素清单 / 状态矩阵（loading · empty · error）/ 关键操作流。卡片视觉规范统一见 §9。

### 5.1 项目首屏 ProjectPicker（`/projects`）

```
┌──────────────────────────────────────────────────┐
│                                                  │
│            ✦ 影视世界观工作台                      │
│         选择一个项目，或创建新世界                  │
│                                                  │
│         ┌────────────────────────┐             │
│         │ 🔍 搜索项目…            │             │
│         └────────────────────────┘             │
│                                                  │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌───┐ │
│   │ ▓▓▓▓▓▓▓ │  │ ▒▒▒▒▒▒▒ │  │ ░░░░░░░ │  │ ＋ │ │
│   │ 长安怪谈  │  │ 星海纪元  │  │ 雾都旧事  │  │新建│ │
│   │ 42实体    │  │ 18实体    │  │  7实体    │  │项目│ │
│   │ 昨天      │  │ 上周      │  │ 3 周前    │  │    │ │
│   └─────────┘  └─────────┘  └─────────┘  └───┘ │
│        (hover 微放大；卡片 ⋯ 菜单：重命名/删除)      │
└──────────────────────────────────────────────────┘
```

- **布局**：居中窄栏（max-w-4xl）；卡片网格 `auto-fill minmax(240px,1fr)`；「＋新建项目」为同网格虚线卡。
- **项目卡片**：封面（MVP：类型色系渐变占位，后续可取项目资产封面；开放问题 OQ-4）+ 项目名 + 元信息行（N 实体 · 最近编辑时间）；hover 上浮微放大；点击进入 `/projects/:id/graph`。
- **卡片 ⋯ 菜单**（hover 时右上角浮现）：重命名（modal 表单）/ 删除（危险流程：modal 红色警示 + 后果清单「将删除该项目的图谱（N 实体 / M 关系）、项目资产（X 张图）、记忆文档与全部对话会话；通用参考库不受影响」+ **输入项目名确认**）。
- **新建流程**：点虚线卡 → modal（项目名必填 + 一句话描述选填）→「创建并进入」→ 直接进新项目图谱页。
- **搜索**：防抖（250ms，沿用既有常量）前端过滤（名称/描述）。
- **键盘**（MVP 最小集）：`/` 聚焦搜索；↑↓ 在卡片间移动；Enter 进入。
- **状态矩阵**：

| 状态 | 呈现 |
|------|------|
| loading | 骨架卡片 ×6（shimmer 占位） |
| empty（无任何项目） | 中央引导：「创建你的第一个世界观项目」+ 大号新建按钮 |
| error | 错误条三要素 + 重试按钮 |

### 5.2 图谱页 GraphView（`/projects/:id/graph`）

继承现有全部能力（左侧操作栏：视角切换 / 新建实体·关系 / 类型筛选；G6 画布；EntityPanel 浮层；右下统计），仅做以下改动：

1. **数据加载挂路由参数**：projectId 变化触发 graphStore / entityIndexStore / perspectiveStore.characters 重置换机（§7）。
2. **右上新增「💬 Agent」唤起按钮**（ghost 样式，`agent-dock-toggle` testid）：打开 AgentDock（§5.5）；AgentDock 打开时按钮变激活态。
3. **空图谱引导**（新项目首屏）：画布中央引导卡——「创建第一个实体」（聚焦新建表单）或「让 Agent 帮你起草」（唤起 Dock 并预填引导语）。
4. **EntityPanel 不变**：含 F08 资产图片区与「查看资产页（HTML）」。
5. 新建实体/关系表单**自动归属当前项目**（隐式作用域，表单不出现项目选择）。

### 5.3 资产管理页 AssetLibrary（`/projects/:id/assets/...`）

页内顶部为二级胶囊（沿用 `section-general` / `section-project` testid）：

```
┌ Tab: [通用参考库] [项目资产] ─────────── 🔍 搜索(分区各自) ┐
```

#### 5.3.1 通用参考库（`/assets/general`，全局）

- **分区头**：标题「通用参考库」+ 徽标`跨项目共享`（明确不随项目切换）+ 分类 chips（全部 / 表情参考 / 植被参考 / 风格参考 / …动态来自 category 去重）+「＋ 新建库」。
- **「库」的语义**：一条通用资产记录 = 一个参考库（多图 + 自由属性 → 一个自包含 HTML 页），与 F08 数据模型完全一致，只是把「库」心智在 UI 上显式化。
- **卡片**（§9 规范）：封面（16:10）+ 库名 + 概要 2 行 + 元信息（N 张图 · 分类）；点击 → AssetHtmlViewer（沿用全屏毛玻璃 overlay，顶栏返回 / 新标签打开 / Esc）。
- **管理**：「＋ 新建库」→ 表单（**建议从"整区替换"升级为居中 modal**，开放问题 OQ-3，字段沿用 GeneralAssetForm：标题/分类/描述/自由属性/多图/封面）；卡片 ⋯ 菜单：编辑（modal）/ 删除（二次确认）。
- **搜索**：标题 / 描述 / 分类 前端过滤，与 chips 叠加（AND）。
- **缓存**：generalCards 为全局缓存，跨项目复用不重拉（§7 亮点）。
- **状态**：empty →「创建第一个参考库」引导卡；error → 三要素错误条 + 重试。

#### 5.3.2 项目资产 · 类型库墙（`/assets/project`，随项目）

第一级：当前项目的 7 个实体类型库卡片（固定 7 类）。

```
┌────────────────────────────────────────────────┐
│  项目资产                                        │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐  │
│  │ 🧑 人物库│ │ ⚑ 势力库│ │ 📍 地点库│ │ 📦 物品库│  │
│  │ 12 实体  │ │  4 实体  │ │  9 实体 │ │ 暂无    │  │
│  │ 36 张图  │ │  8 张图  │ │ 21 张图 │ │ (虚线卡) │  │
│  └────────┘ └────────┘ └────────┘ └────────┘  │
│  ┌────────┐ ┌────────┐ ┌────────┐              │
│  │ ✦ 技能库│ │ ⚡ 事件库│ │ 💡 概念库│   (hover 微放大) │
│  └────────┘ └────────┘ └────────┘              │
└────────────────────────────────────────────────┘
```

- **库卡片**：类型色渐变封面 + 大号类型图标 + 「人物库」+ 计数（N 实体 · M 张图）；hover 微放大；点击进入第二级。
- **空类型库**：灰色虚线卡「暂无人物实体」+ 引导链接「去图谱页创建」（跳 `/graph` 并展开新建实体表单、预选该类型）。
- 数据：沿用 `GET /api/assets/entities`（多项目后随 project 过滤），前端聚合计数。

#### 5.3.3 类型库详情（`/assets/project/:entityType`，第二级）

```
┌ 项目资产 / 人物库 [← 返回] ──────────── 🔍 搜索实体 ┐
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐            │
│  │缩略图│ │缩略图│ │缩略图│ │缩略图│ │缩略图│            │
│  │玄机子│ │沈青梧│ │裴照  │ │阿萤  │ │……  │            │
│  │隐世高人│ │女捕快│ │画师  │ │药童  │ │    │            │
│  └────┘ └────┘ └────┘ └────┘ └────┘            │
└────────────────────────────────────────────────┘
```

- **面包屑 + 返回**：`项目资产 / 人物库`（点击「项目资产」回类型库墙；浏览器后退同样有效——路由化的收益）。
- **实体卡片**：沿用 AssetCardTile 现状（封面 / 类型徽标 / 名称 / 概要 / 图片数）；点击 → 实体 HTML 查看器（overlay）。
- **搜索**：名称 / 描述前端过滤。
- **状态**：empty（该类型无实体）→ 引导回图谱页创建。

### 5.4 Agent 主页 AgentHome（`/projects/:id/agent`）

Claude 式两栏（左栏可折叠）：

```
┌──────────┬──────────────────────────────────────┐
│ ＋ 新对话  │                                      │
│──────────│        晚上好，长安怪谈的世界正在等你    │
│ 今天      │                                      │
│  · 师父设定 │   ┌──────────────────────────────┐  │
│ 7 天内    │   │ 和 Agent 聊聊这个世界…          │  │
│  · 势力草图│   └──────────────────────────────┘  │
│ 更早      │                                      │
│──────────│   📚 项目记忆文档                     │
│ 📚 记忆文档│   ┌────────┐ ┌────────┐ ┌─────┐   │
│           │   │世界观定位│ │风格约定  │ │＋ 新建│   │
│           │   │9-05 更新│ │9-03 更新│ │      │   │
└──────────┴──┴────────┴─┴────────┴─┴──────┴───┘
```

- **左栏（w-72）**：顶部「＋ 新对话」；会话列表按更新时间分组（今天 / 7 天内 / 更早），标题取首条用户消息截断或自动命名；底部「📚 记忆文档」区块入口（滚动到主页记忆区 / 或独立小节）。
- **欢迎页（未选中会话）**：项目名问候 + 大输入框（Claude 风格，Enter 发送 / Shift+Enter 换行）+ 记忆文档卡片区。
- **记忆文档区**：当前项目记忆文档列表（文档名 + 更新时间 + 首行摘要）；点击查看/编辑（**OQ-2 已裁决（F10，DECISIONS 2026-09-07）**：HTML 分段模板取代 markdown 方案——modal 内段级表单编辑 + iframe 预览，段级 patch/CAS 冲突消解）；「＋ 新建」提供两个模板（世界观定位 / 风格约定）。
- **会话视图（`/agent/s/:sessionId`）**：消息流（用户 / Agent 气泡，SSE 流式渲染 + 光标动画）+ 底部输入框 + **草案确认卡**（propose 产物内联渲染：`实体` / `关系` kind 徽标 + payload 摘要表 + [确认写入] [放弃] 按钮）；confirm 后卡片转成功态（「✓ 已写入 2 实体 · 1 关系」）并触发图谱数据失效。（F10 落地注记：成功态以消息流摘要 + 草案卡清空实现，语义等价，DECISIONS 2026-09-07）
- **空状态**：新项目无会话无记忆文档 → 欢迎页 + 「从模板创建记忆文档」引导。
- 记忆文档**不是**图谱事实副本（§3 定位）；Agent 对话上下文 = 记忆文档 + 经视角过滤的图谱数据（F10 既有约束）。

### 5.5 Agent 侧边栏 AgentDock（图谱 / 资产页 overlay）

```
┌──────────────────────────────┬───────────────┐
│                              │ [师父设定 ▾] ✕ │
│         （图谱画布，           │───────────────│
│        非模态仍可交互）         │ 用户：帮我把主角│
│                              │ 的师父建成实体…  │
│                              │ Agent：好的，起草│
│                              │ ┌───────────┐ │
│                              │ │草案·实体    │ │
│                              │ │玄机子 character│
│                              │ │ [确认写入][放弃]│
│                              │ └───────────┘ │
│  [💬 Agent]                  │───────────────│
│                              │ [输入框    发送] │
└──────────────────────────────┴───────────────┘
```

- **唤起**：图谱 / 资产页右上「💬 Agent」按钮（`agent-dock-toggle`）或快捷键 `Ctrl/⌘+J`；右滑入 `w-[400px]` 全高 GlassPanel（背景更实：`bg-white/75`），**非模态**（不遮画布，可边看图边聊）。
- **顶部**：会话切换下拉（本项目会话池，默认接续最近会话）+「＋ 新会话」+ ✕ 关闭。（F10 落地注记：顶部暂为标题 + 收起按钮——会话切换下拉与「＋新会话」随 F13 落地，期间经 AgentHome 会话列表切换，DECISIONS 2026-09-07）
- **中部 / 底部**：与 AgentHome **复用同一套消息渲染组件与草案确认卡**（同一会话池，已对齐决策 ②）。
- **联动**：侧边栏 confirm 落库 → graphStore 失效刷新 → 画布新节点淡入；收起侧边栏不中断已落库会话（回 Agent 主页可继续）。
- **流式收起语义**：SSE 生命周期挂在**会话（store 层）**而非组件——侧边栏收起后流式继续写入 store，重开可见全部内容。⚠ 此设计需修订 `frontend/CONSTRAINTS.md`「SSE 连接随组件卸载中断」条目为「随会话结束/项目切换中断」（防泄漏的本意由会话级 AbortController 承担），落地时同步修订并在 DECISIONS 登记。
- **Esc**：焦点在 Dock 内时收起。（F10 落地注记：暂未实现，随 F13 落地——当前经 ✕ 关闭按钮与 Ctrl/⌘+J 切换，DECISIONS 2026-09-07）

---

## 6. 跨页面端到端剧本

### 剧本 A：首次使用
`/` → 空首屏引导 → 新建「长安怪谈」→ 进入空图谱页 → 引导卡二选一：手建首个实体 / 唤起 Agent 起草 → 图谱出现首批节点。

### 剧本 B：切换项目
顶栏 `[长安怪谈 ▾]` → 选「星海纪元」→ URL 置换 → SSE（若有）中止 → 各 store 重置 → 星海纪元的图谱 / 资产 / 会话 / 记忆加载；通用参考库区**不重拉**（全局缓存）→ 顶栏与各页项目标识更新为「星海纪元」。

### 剧本 C：创作回路（F10 核心链路）
图谱页 → `Ctrl+J` 唤起 Dock（接续最近会话）→ 输入「帮我把主角的师父创建成实体，隐世高人，和沈青梧是师徒」→ Agent 流式回复 + propose 草案卡（实体·玄机子 + 关系·师徒）→ 点[确认写入] → confirm 落库 → 草案卡转成功态 → 画布刷新、新节点淡入 → 继续对话（上下文含刚写入的结果）。

### 剧本 D：资产参考流
资产页 → 通用参考库 → 搜「表情」→ 点「表情参考库」卡 → HTML 查看器全屏阅读 → Esc 返回 → 切到项目资产 → 人物库 → 搜「玄机子」→ 点卡 → 实体 HTML 资产页（含 F08 上传的图片）。

### 剧本 E：删除项目
首屏卡片 ⋯ → 删除 → 危险 modal（后果清单 + 输入项目名）→ 确认 → 后端级联（图谱 / 项目资产 / 记忆 / 会话；通用库不动，见 §8）→ 回首屏。

---

## 7. 前端状态蓝图

### 新增 projectStore

| 字段 / 动作 | 说明 |
|---|---|
| `projects: ProjectSummary[]` | 列表（含实体数 / 最近编辑时间，供首屏与切换器） |
| `currentProjectId: string \| null` | 与 URL `:projectId` 双向同步（路由参数为事实源） |
| `loadProjects()` / `createProject()` / `renameProject()` / `deleteProject()` | CRUD |
| `switchProject(id)` | 校验存在 → 置换 current → 触发依赖 store 重置 |

### 切换项目重置矩阵

| store | 切换时行为 |
|---|---|
| graphStore | reset；进入图谱页懒加载 |
| perspectiveStore | 重置 author 默认；characters 清空重载 |
| selectionStore | clear（面板关闭） |
| assetStore.entityCards | 清空；进资产页重载 |
| assetStore.generalCards | **保留（全局缓存，跨项目复用）** |
| assetStore.viewer / Dock 开合 | 关闭 |
| entityIndexStore | 清空重载（@ 名称解析随项目） |
| agentStore（新建） | 会话池按项目重载；进行中 SSE abort；当前会话清空 |

### agentStore（新建，F10 载体）

- 字段：`sessions[]`、`currentSessionId`、`messagesBySession`、`streamingSessionId`、`drafts[]`（待确认草案）。
- SSE 挂会话级生命周期（§5.5 修订点）；confirm 成功后广播「图谱已变更」事件供 graphStore 订阅刷新。

---

## 8. 多项目后端蓝图（供后续功能项拆解，非本轮实施）

### 8.1 主库 app.db（Alembic 迁移）

- 新表 `projects`：`id, name, description, created_at, updated_at`（封面第二阶段）。
- `entities` / `relationships` 增加 `project_id`（FK projects + 索引）；迁移将既有数据打包进自动创建的「默认项目」，保证向后兼容。
- `global_state` 单例表（第 2 批蓝图）届时需改为按 project 维度——已在蓝图层面预警。

### 8.2 资产库 assets.db（沿用 2026-09-05 双库决策）

- `kind='general'` 通用资产：**保持全局**（无 project 字段）。
- 实体资产：经 `owner_id → entity → project` 间接归属，现有结构与孤儿清扫逻辑不变。
- **删除项目级联**：现有「列表时孤儿清扫」无法感知成批实体消失，需新增显式清扫流程（删项目事务：主库删实体/关系 → 按该项目实体集合清扫 asset_records / asset_images / 物理文件）；跨库边界（两库各自事务 + 失败补偿）是实现期设计点。

### 8.3 Agent 数据（F10 前置）

- 建议入**主库**（单一事实源原则；assets.db 定位是派生展示层，不承载会话/记忆）：`conversations`（project_id, title, updated_at）、`messages`（conversation_id, role, content, created_at）、`memory_docs`（project_id, title, content-markdown, updated_at）。
- harness / skills 为全局代码与配置层，不落库表。

### 8.4 API 形态（建议）

- 路径参数式：`/api/projects`（CRUD）+ `/api/projects/{pid}/entities|relations|graph|assets/entities|agent/sessions|agent/chat|agent/memory-docs`。
- 既有无项目端点的处置（实现期决策）：建议迁移期绑定默认项目并标 deprecated，前端类型重生成切换后移除——内部 MVP 无外部消费者，亦可直接切换 + e2e 同步更新。

### 8.5 模块边界

- 新 `projects` 模块仅依赖 core；entities / relations / perspectives / assets / agent 经 projects service 校验归属（跨模块只走 service 层，根 CONSTRAINTS §2）。
- import-linter 新契约与 source 兄弟枚举同步登记（2026-08-27 决策）；模块文档（ARCHITECTURE/CONSTRAINTS）随功能项落地。

---

## 9. 视觉规范增量（不与 frontend/CONSTRAINTS.md 冲突，为其补充）

### 统一卡片规范（项目卡 / 库卡 / 实体卡 / 记忆文档卡共用）

| 属性 | 值 |
|---|---|
| 容器 | `rounded-2xl ring-1 ring-black/5 bg-white/80 shadow-sm backdrop-blur`（dark: `ring-white/10 bg-slate-800/80`） |
| hover | 容器 `-translate-y-1 shadow-md`；封面 `group-hover:scale-105`；过渡 150–200ms ease-out（遵守 ≤200ms 上限） |
| 封面 | 16:10 `object-cover` 裁切 + `loading="lazy"`；无图用类型色 / 中性色 `#cbd5e1` 占位（沿用现状） |
| 文本 | 标题 1 行截断 `font-medium`；概要 2 行截断 `text-sm text-slate-500` |
| 网格 | `auto-fill minmax(220px,1fr) gap-3`（项目首屏 `minmax(240px,1fr)`） |
| ⋯ 菜单 | hover 时右上角浮现（`opacity-0 group-hover:opacity-100`），键盘可达（卡片 focus 时同样可见） |

### 其他

- 建议把「玻璃卡 + hover 位移」沉淀为 `GlassCard` 组件（GlassPanel + hover 变体），避免类名散落——实现期决策。
- 颜色体系不变：slate 基调 + 7 实体类型色（lib/palette.ts）；深色主题继续跟随系统。
- 空状态统一模式：居中引导卡（一句话 + 单个主按钮 + 可选次级链接）。
- z-index 现状沿用（面板 10 / 下拉与浮钮 20 / 全屏查看器 50），AgentDock 取 30（高于面板、低于查看器）——实现时在 CONSTRAINTS 补一条 z-index 规范。

---

## 10. 测试与验收锚点

### testid 迁移映射（保护既有 e2e；F11/F12 落地后已按实际名回写）

| 既有（保留） | 新增（落地实际名） |
|---|---|
| `main-nav` / `tab-graph` / `tab-assets` | `tab-agent`（随 F10） |
| `section-general` / `section-project`（F12 起为 NavLink，分区入 URL） | `project-picker` / `project-card-{id}` / `project-create` / `project-menu-{id}`（F11 首屏）；`asset-type-wall` / `asset-type-card-{type}` / `asset-type-back` / `asset-search` / `asset-general-empty` / `asset-search-empty`（F12 资产页，全清单见 docs/tests/F12 测试文档「testid 迁移契约」） |
| `asset-viewer`（HTML 查看器） | — |
| `sidebar` / `entity-panel` / `perspective-*` / `filter-*` | `agent-dock` / `agent-dock-toggle` / `agent-session-list` / `agent-input` / `memory-doc-card`（随 F10） |

### e2e 场景建议（实现各功能项时入测试文档）

1. 新建项目 → 建实体 → 切换项目 → 验证图谱 / 会话 / 记忆隔离、通用库共享。
2. 首屏搜索过滤 + 删除项目（输入名确认）级联验证。
3. 类型库墙 → 库详情 → 实体 HTML 全链路 + 面包屑后退。
4. Dock 对话 → propose → confirm → 图谱节点出现（剧本 C）。
5. 通用库新建 / 编辑（modal）/ 删除 + 两项目间可见性一致。

---

## 11. 已对齐决策与开放问题

### 已对齐（2026-09-06 用户确认，已登记 DECISIONS.md）

1. **独立项目首屏**：每次启动先进项目选择页，顶栏再提供快速切换（否决「直达最近项目」——项目上下文错位代价高）。
2. **Agent 同一会话池**：侧边栏与主页操作同一套项目会话，收起不丢上下文（否决「临时快聊」——割裂长期记忆，违背 F10 目标）。
3. **通用库留驻资产页**：作「通用参考库」分区 + 跨项目徽标（否决「独立顶层入口」——找参考多一跳）。
4. **本轮只出设计文档**：不改功能清单、不实施（落地拆解待审阅）。

### 开放问题（实现期决策，逐项附推荐）

| # | 问题 | 推荐 |
|---|---|---|
| OQ-1 | 是否引入 react-router | 是（URL 即状态原则的基础；正式引入时入 DECISIONS） |
| OQ-2 | 记忆文档编辑器形态 | **已裁决（F10，2026-09-07）**：modal 内段级表单编辑 + iframe 预览（HTML 分段模板取代 markdown，段级 patch/CAS）；独立页第二阶段 |
| OQ-3 | 通用资产表单从整区替换改 modal | 是（保上下文）；组件复用 GeneralAssetForm |
| OQ-4 | 项目封面来源 | MVP 渐变色占位；后续取项目内最新资产封面 |
| OQ-5 | 切换项目时未提交表单输入的保护 | MVP 不拦截；出现真实损失案例再做草稿暂存 |
| OQ-6 | 资产页默认落点 | `assets/general`（按用户叙述顺序）；可随使用反馈调整 |
| OQ-7 | Agent 会话标题生成 | MVP 取首条用户消息截断；自动命名（LLM）第二阶段 |
| OQ-8 | agent 写入工具的用户许可模式 | **已裁决（2026-09-08）**：轮末统一确认（见 §12.2） |
| OQ-9 | 多系列共享世界观的组织方式 | **已裁决（2026-09-08）**：项目内系列维度（见 §12.4） |
| OQ-10 | 全局用户画像沉淀方式 | **已裁决（2026-09-08）**：自动沉淀 + 透明可编辑（见 §12.3） |

---

## 12. 落地建议（非承诺，待用户审阅后立功能项）

建议按依赖序拆三个功能项（编号顺延、F10 编号不变挪后执行）：

1. **多项目底座**：后端 projects 表 + project_id 迁移 + 默认项目打包；前端 react-router + 项目首屏 + 顶栏切换器 + store 重置矩阵。
2. **工作台导航与资产页重构**：资产页两级钻取 + 搜索 + 空状态引导 + 表单 modal 化 + testid 迁移。
3. **F10 Agent 对话与确认写入**（既有清单项）：后端 chat/propose/confirm + 会话/记忆文档表 + AgentHome + AgentDock + 剧本 C 全链路。

> 依 AGENTS.md 规则：正式开工前须先在 docs/features.md 增补功能项行（范围决策，非状态手改）+ 撰写对应 docs/tests/FXX 测试文档（先行）+ PROGRESS 任务清单。

---

## 13. Agent 体验与记忆体系升级（2026-09-08 验收反馈规划，F13–F16）

> 背景：F10 验收暴露五类问题——①伪流式无思考可视化、无 token 观测；②会话/记忆文档不可删除；③agent 只有检索工具、写入流程断裂（草案需手动转录）；④指导文档可重复创建、编辑框过小、长期记忆体系（剧本/台本/分镜/用户画像/跨会话）缺失；⑤多系列共享世界观无从组织。四项关键分叉已由用户裁决（OQ-8/9/10 + 实施顺序），登记 DECISIONS 2026-09-08。

### 13.1 F13 对话体验升级

**真流式 + 思考可视化**（实测百炼 `deepseek-v4-flash-0731` 原生输出 `reasoning_content`，`stream=True` + `include_usage` 可用，2026-09-08）：

- 后端 `llm.py` 新增 `stream_chat_turn`（流式生成器：reasoning delta / content delta / 聚合后的 tool_calls / usage 四类产出；流式 tool_calls 分片按 index 聚合）；`chat_turn` 保留给摘要/propose 等非流式路径。
- SSE 协议扩展两事件：`reasoning`（思考增量，逐 chunk 下发）与 `usage`（done 前：prompt/completion tokens + 上下文容量占比 = 本轮 prompt_tokens ÷ AGENT_CONTEXT_MAX_TOKENS）；`token` 事件改真流式（废除 _TOKEN_CHUNK_CHARS 伪分块）。
- 前端 `ThinkingBlock`：气泡内顶部灰字小字思考流；思考中自动展开跟随滚动、回复开始后自动折叠为「已思考 N 秒」标题行、点击可再展开（Z-code 式）；assistant 消息模型增加 `reasoning` 字段。
- `UsageBar`：输入框上方细条——本轮 prompt/completion 数字 + 会话累计 + 容量占比条（超 80% 变琥珀色警示）。

```
┌─ Agent 气泡 ─────────────────────────────┐
│ ▸ 已思考 6 秒                     （灰小字）│ ← 折叠态，点击展开
│ 9.9 大（9.9 = 9.90 > 9.11）。正文流式逐字… │
└──────────────────────────────────────┘
┌──────────────────────────────────────┐
│ 上下文 3.2k / 100k ▓▓░░░░░ 3%  本轮 97+106 │ ← UsageBar
└──────────────────────────────────────┘
```

**删除能力**：`DELETE /api/agent/sessions/{id}`（级联 messages）、`DELETE /api/agent/memory-docs/{id}`（级联 sections）；前端会话项 hover 🗑（输入标题确认，对齐项目删除模式）+ 文档卡 🗑（轻确认）。

**文档编辑大弹窗**：DocEditor 由原地小框改全屏 Modal（max-w-5xl 级）：左栏段列表（当前段高亮）+ 右栏段编辑表单 + 底部 iframe 实时预览；Esc 关闭（有脏输入时确认）。

**指导文档唯一性（验收缺陷，提前修复）**：`create_doc` 服务层按 kind 查重——指导类（positioning/style）项目内已存在即 409（三要素）；前端「＋新建」对指导类置灰并提示「每项目仅一份」。

**Dock 遗留交互**（F10 落地基线偏离清单兑现）：顶部会话切换下拉 +「＋新会话」；焦点在 Dock 内 Esc 收起。

### 13.2 F14 Agent 写入工具链（OQ-8：轮末统一确认）

**工具扩展**（tools.py，写入类工具执行≠落库，仅登记 pending）：

- 图谱写入：`create_entity(type, name, properties?)`、`update_entity(entity_id, properties_patch)`、`create_relation(source_name, target_name, relation_type, known_by?)`
- 文档写入：`create_memory_doc(kind, title)`、`write_doc_section(doc_id, seq, title?, content)`（段级 CAS 语义保留：登记时记录基线 version，落库校验）
- 读取不变：四检索工具 + 目录常驻。

**轮末统一确认流**（已裁决）：

```
agent 调写入工具 → 工具登记 pending write（返回 tool result「已登记，待作者确认」）
→ 本轮回复流式完毕（done 事件携带 pending_writes 摘要）
→ 前端渲染待写入卡（复用草案卡视觉，逐项勾选/全选）
→ [全部写入] → POST /api/agent/pending-writes/approve（批量）
   → 服务端逐项二次校验（名称冲突/端点存在/段 CAS）→ 落库 → 卡片转成功态
   → graphStore/docStore 失效刷新（画布新节点淡入）
→ [放弃] → 状态置 rejected，卡片转灰
```

- 新表 `agent_pending_writes(id, conversation_id, project_id, kind, payload_json, baseline_json, status: pending/approved/rejected, created_at)`；对话内多轮的 pending 互不覆盖，确认以卡为单位。
- `propose` 端点保留标注 legacy（对话内写入工具为主路径）；写入落库全部复用 entities/relations/agent 既有 service（校验单一来源）。
- 安全：写入工具参数 Pydantic 白名单；approve 时服务端复核不信任前端；每轮 pending 数量上限（config AGENT_MAX_PENDING_WRITES）。

### 13.3 F15 长期记忆体系（OQ-10：自动沉淀 + 透明可编辑）

**文档类型学**（memory_docs.kind 扩展为两类）：

- **guide 指导类（项目内唯一）**：世界观定位 positioning、风格约定 style——项目级共享，不可重复（13.1 已先行唯一性约束）；项目创建/存量项目首次进入 Agent 时惰性补建空模板。
- **work 作品类（多实例）**：故事大纲 outline（结构分段 + 权重 + 时长，原 F13 计划并入）、剧本 screenplay、台本 episode_script、分镜 storyboard——模板注册表 DOC_TEMPLATES 扩展，各定义段结构；可建任意多份（「正传第 1 集剧本」「外传序幕」并存）。
- UI：文档区分「指导 / 作品」两组；新建入口只列作品类模板；每卡显示 kind 徽标与更新时间。

**全局用户画像（跨项目，自动沉淀）**：

- 新表 `global_memory_entries(id, kind: preference/motif/taboo/fact, content, source_conversation_id, created_at, updated_at)`（主库，无 project_id）。
- 每轮对话结束 `LLM_MODEL_LIGHT` 后台提炼候选条目（限 N 条/轮，config 开关 AGENT_PROFILE_AUTO_CAPTURE 默认开）→ 自动入库；下一轮 system 前缀注入全局画像摘要（预算内截断）——跨项目生效。
- 透明可编辑：项目首屏新增「全局记忆」入口（/global-memory）——列表 + 手动新增/编辑/删除 + 来源会话链接；agent 自动条目与手动条目同权展示。

**跨会话记忆**：

- 新工具 `search_session_summaries(q)`：检索本项目历史会话 summary + 标题 + 时间（MVP LIKE 匹配）；默认不注入全部历史（成本），按需检索。
- 会话滚动摘要（F10 已有）继续作为会话内压缩层；跨会话显式记忆一律沉淀进 memory_docs / 全局画像，维持「图谱=事实、文档=过程、画像=偏好」三源分工。

### 13.4 F16 多系列剧情线（OQ-9：项目内系列维度）

**模型**：项目 = 世界观宇宙；新增 `series(id, project_id FK, name, description, ...)` 与 `entity_series(entity_id, series_id)` 多对多——**无关联 = 全系列共享底座**，挂关联 = 系列专属/重点；`memory_docs.series_id FK NULL`（NULL=项目级共享文档；非 NULL=该系列剧情文档）。关系不挂系列（过滤按端点实体归属推导）。

**过滤语义**：`GET /api/graph?series=<id|shared|all>`——series 视图 = 共享实体 ∪ 该系列实体 + 其间关系；agent 对话参数增 series（图谱目录与检索工具同口径过滤，创作默认聚焦当前系列、共享底座常驻）。

**UI**：项目内系列管理（AgentHome 记忆区上方「系列」条：新建/改名/删除/切换当前系列）；图谱页顶栏系列筛选下拉（复用视角切换器视觉）；文档卡显示系列徽标；资产页按系列过滤为后置增强（图片资产随实体走）。

```
项目「长安怪谈宇宙」
├─ 共享底座: 图谱 194 实体 · 指导文档 · 通用资产
├─ 系列《正传》: 剧本/分镜/大纲挂系列 + 专属实体标记
└─ 系列《外传》: 独立剧情文档 + 专属实体标记
```

### 13.5 功能拆分与编号重组（已立项 features.md F13–F16）

| 功能 | 主题 | 来源 |
|---|---|---|
| F13 | 对话体验升级（真流式/思考可视化/usage 窗口/删除/大弹窗/指导唯一/Dock 遗留） | 反馈①② + F10 偏离清单 |
| F14 | 写入工具链（读写工具 + 轮末统一确认 + pending 落库 + 图谱失效联动） | 反馈③ |
| F15 | 长期记忆体系（文档类型学/作品模板/全局画像/跨会话检索） | 反馈④ |
| F16 | 多系列剧情线（series 表/实体关联/文档挂载/过滤） | 反馈⑤ |

- 实施顺序（用户裁决）：F13 → F14 → F15 → F16。
- 原登记的「F13 创作工作流」重组：故事大纲模板并入 F15 作品类模板；ask_user 多方案征求卡并入 F14 确认机制族（后续增强）；plan/step 步骤卡与 harness 必须事项清单移第二阶段候选（PROGRESS 登记）。
- 每个 FXX 照 AGENTS.md 流程：features.md 行 → 测试文档先行 → 实现 → §10 审查 → verify。
