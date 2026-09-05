# frontend/ARCHITECTURE.md — 前端架构

> React 18 + TypeScript + Vite 单页应用。API 类型由后端 OpenAPI schema 自动生成。

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
│   └── agentStore      # 对话消息、草案、确认流程
├── views/
│   ├── Workbench       # 工作台壳层：顶部主导航「图谱 | 资产管理」（F08 起）
│   ├── GraphView       # 图谱页（画布 + 操作栏 + 详情面板，原 Workbench 主视图）
│   └── AssetLibrary    # 资产管理页（通用资产 / 项目资产二级分区，F08）
├── components/
│   ├── graph/          # GraphCanvas（G6 封装：布局/交互/缩放/拖拽）
│   ├── entity-selector/# @ 触发的实体搜索选择器（含视角可见性提示）
│   ├── entity-panel/   # 实体/关系详情（资产图片区、编辑表单）
│   ├── assets/         # 资产卡片/编辑表单/通用与项目资产区/HTML 内嵌查看器（F08）
│   ├── agent-panel/    # 对话面板（SSE 渲染 + 草案确认 UI）
│   └── ui/             # 自研轻量通用组件（毛玻璃面板/按钮/输入框，shadcn/ui 风格）
└── lib/                # 工具（格式化、防抖等）
```

数据流（单向）：API → stores → selector 订阅 → 组件渲染；用户操作 → stores action → API → store 更新。

## 3. 状态管理设计

| store | 状态 | 更新来源 |
|-------|------|----------|
| graphStore | nodes/edges/loading | 视角切换、CRUD 完成后按需刷新 |
| perspectiveStore | perspective/character_id | 视角切换控件（切换即触发 graphStore 重载） |
| selectionStore | 选中 id、面板开合 | 图节点点击 |
| assetStore | 通用/项目资产卡片、HTML 查看器开关 | 资产管理页挂载与写操作后刷新（F08） |
| agentStore | 消息列表、流式缓冲、草案 | SSE 流、propose/confirm |

## 4. 渲染性能策略

- G6 Graph 实例**单例**（Workbench 挂载时创建、卸载时销毁）；数据变更走 G6 数据 API 增量更新，禁止整图重建。
- 视角切换是唯一允许全量替换 nodes/edges 的场景。
- 高频交互（拖拽/缩放/hover）状态隔离在 GraphCanvas 内部（局部 state/ref），不进全局 store。
- 资产缩略图懒加载（viewport 内加载）。

对应硬约束见 [frontend/CONSTRAINTS.md](./CONSTRAINTS.md)「渲染性能」。

## 5. 组件生命周期管理

- GraphCanvas：`useEffect` 创建 G6 实例 → 订阅 store 变化同步数据 → 卸载时 `graph.destroy()` 释放。
- SSE 连接：组件卸载即 AbortController 中断，避免泄漏。
- 实体选择器：输入防抖（300ms）后调用检索 API。

## 6. 视觉规范

见 [frontend/CONSTRAINTS.md](./CONSTRAINTS.md)「视觉」小节（修改 UI 前必读）。

## 7. API 契约

见 [frontend/CONSTRAINTS.md](./CONSTRAINTS.md)「API 契约」小节；类型生成流程见本文件 §2「api/」说明。
