# frontend/ARCHITECTURE.md — 前端架构

> React 18 + TypeScript + Vite 单页应用。API 类型由后端 OpenAPI schema 自动生成。
> 交互设计基线：根目录 DESIGN.md（多项目工作台）。F11 起已引入 react-router（OQ-1 落定，DECISIONS 2026-09-06）：`/projects` 首屏 + `/projects/:projectId/graph|assets`（Agent 路由随 F10）。

## 1. 技术栈

React 18 / TypeScript 5 / Vite 5 / AntV G6 5.x / Zustand / Tailwind CSS + 自研轻量 UI 组件（shadcn/ui 风格：毛玻璃面板、按钮、输入框、表单；2026-08-28 决策不引入 shadcn CLI，详见 DECISIONS.md）。

## 2. 目录结构与分层

```
frontend/src/
├── api/                # openapi-typescript 生成的类型 + 轻量请求客户端
├── stores/             # Zustand 全局状态
│   ├── graphStore      # 节点/边数据 + 图数据加载
│   ├── perspectiveStore# 当前视角（author/character/audience + character_id）
│   ├── selectionStore  # 选中实体/关系、详情面板状态
│   ├── assetStore      # 资产卡片列表（通用/项目）+ 内嵌查看器状态（F08）
│   ├── projectStore    # 项目列表/当前项目/路由同步（F11 已落地，DESIGN.md §7；Outlet context 渲染期供给 projectId）
│   └── agentStore      # 会话池/消息缓冲/草案/记忆文档（F10 已落地：SSE 会话级生命周期——AbortController
│                       #   挂 store，Dock 收起不断流；confirm 后广播 graphStore.loadGraph 失效）
├── views/
│   ├── Workbench       # 工作台壳层（F11 路由化布局）：logo 返回首屏 + 项目切换器 + 主导航 NavLink「图谱 | 资产管理 | Agent」（F10 落地 tab-agent）
│   │                   #   + AgentDock 挂载于壳层（任一页签可唤起）
│   ├── GraphView       # 图谱页（画布 + 操作栏 + 详情面板，原 Workbench 主视图）
│   ├── AssetLibrary       # 资产管理页壳层（F08；F12 路由化：二级胶囊 NavLink「通用参考库｜项目资产」+ Outlet，
│   │                       #   分区即子路由 assets/general（默认落点）|assets/project（类型库墙）|assets/project/:entityType（详情））
│   ├── ProjectPicker   # 项目首屏（F11 已落地，DESIGN.md §5.1）
│   └── AgentHome       # Agent 对话主页（components/agent-panel/AgentHome，F10 已落地；
│                       #   路由 agent（欢迎页）| agent/s/:sessionId（会话视图），URL 即状态）
├── components/
│   ├── graph/          # GraphCanvas（G6 封装：布局/交互/缩放/拖拽）
│   ├── entity-selector/# @ 触发的实体搜索选择器（含视角可见性提示）
│   ├── entity-panel/   # 实体/关系详情（资产图片区、编辑表单）
│   ├── assets/         # 资产域组件（F08；F12 两级钻取：GeneralAssetSection 通用参考库含搜索/chips/modal 表单、
│   │                   #   ProjectTypeWall 类型库墙、EntityTypeAssets 类型库详情、AssetCardTile §9 规范卡、HTML 内嵌查看器）
│   ├── agent-panel/    # Agent 域组件（F10 已落地：AgentHome/AgentDock(z-30, Ctrl/⌘+J)/SessionView/
│   │                   #   MessageList(流式光标+tool 行为指示)/ChatInput(Enter 发送+产出草案)/
│   │                   #   DraftConfirmCard(两段式确认)/MemoryDocsArea/DocEditor(段级表单+iframe 预览)）
│   ├── projects/        # 项目域组件（ProjectSwitcher 顶栏切换器，F11）
│   └── ui/             # 自研轻量通用组件（毛玻璃面板/按钮/输入框/modal，shadcn/ui 风格）
└── lib/                # 工具（格式化、防抖等）
```

数据流（单向）：API → stores → selector 订阅 → 组件渲染；用户操作 → stores action → API → store 更新。

## 3. 状态管理设计

| store | 状态 | 更新来源 |
|-------|------|----------|
| graphStore | nodes/edges/loading | 视角切换、CRUD 完成后按需刷新 |
| perspectiveStore | perspective/character_id | 视角切换控件（切换即触发 graphStore 重载） |
| selectionStore | 选中 id、面板开合 | 图节点点击 |
| assetStore | 通用/项目资产卡片、HTML 查看器开关 | 资产管理页挂载与写操作后刷新（F08；F12 分区切换经路由，store 只承载数据缓存） |
| projectStore（F11 已落地） | projects/currentProjectId/routeInvalid | 首屏与切换器数据源；syncRoute 把路由参数同步为项目上下文（校验存在性），Outlet context 渲染期供给叶子视图（避免父子 effect 顺序竞态）；切换重置换机由叶子视图按 projectId 陈旧检测执行（矩阵见 DESIGN.md §7；generalCards 全局缓存跨项目复用） |
| agentStore（F10 已落地） | sessions/messagesBySession/streamingSessionId/draftsBySession/docs/dockOpen | SSE 流、propose/confirm、记忆文档 CRUD；SSE 挂会话级生命周期，项目切换 resetProjectScoped（abort + 全量清空） |

## 4. 渲染性能策略

- G6 Graph 实例**单例**（Workbench 挂载时创建、卸载时销毁）；数据变更走 G6 数据 API 增量更新，禁止整图重建。
- 视角切换是唯一允许全量替换 nodes/edges 的场景。
- 高频交互（拖拽/缩放/hover）状态隔离在 GraphCanvas 内部（局部 state/ref），不进全局 store。
- 资产缩略图懒加载（viewport 内加载）。
- 路由化（F11 已落地）：Workbench 以 key=projectId 包裹 Outlet，切换项目整树重挂载；G6 生命周期随 GraphView 挂载/卸载，单例约束不变。

对应硬约束见 [frontend/CONSTRAINTS.md](./CONSTRAINTS.md)「渲染性能」。

## 5. 组件生命周期管理

- GraphCanvas：`useEffect` 创建 G6 实例 → 订阅 store 变化同步数据 → 卸载时 `graph.destroy()` 释放。
- SSE 连接（F10 已落地）：生命周期挂会话级——agentStore 持有 AbortController，组件卸载/Dock 收起/切会话不断流；中断发生于显式停止与项目切换；全局单流（他会议流式中输入禁用，详见 frontend/CONSTRAINTS.md「生命周期」）。
- 实体选择器：输入防抖（300ms）后调用检索 API。

## 6. 视觉规范

见 [frontend/CONSTRAINTS.md](./CONSTRAINTS.md)「视觉」小节（修改 UI 前必读）。

## 7. API 契约

见 [frontend/CONSTRAINTS.md](./CONSTRAINTS.md)「API 契约」小节；类型生成流程见本文件 §2「api/」说明。
