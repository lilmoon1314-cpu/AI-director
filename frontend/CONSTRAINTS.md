# frontend/CONSTRAINTS.md — 前端硬约束

> 适用范围：frontend/ 全部代码。修改前端任何代码前必读。

## API 契约
- 必须：API 客户端类型由后端 OpenAPI schema 自动生成；禁止手写与后端重复的接口类型。
- 必须：API 基础 URL 经 Vite 环境变量 `VITE_API_BASE` 配置，禁止硬编码。

## 视觉
- 必须：视觉基调为浅色背景 + 高对比深色文本 + 毛玻璃半透明层（backdrop-blur）+ 对称间距；同时提供深色主题，**跟随系统**（`prefers-color-scheme`，CSS dark: 变体 + G6 `setTheme` 联动），不提供手动切换开关。
- 必须：动效克制（过渡 ≤200ms，无强烈震动反馈）。
- 必须：实体节点按类型固定标识色（lib/palette.ts）；关系边跟随非 character 一端的类型色且更淡更透明（两端均 character 取中性淡化）。
- 必须：图标签避让开启（G6 auto-adapt-label）；节点悬停高亮一跳邻域、点击持续高亮相关路径、再次点击取消。
- 必须：高亮 = 原样式提亮（fill/label opacity→1）+ 外围透明淡黄光环（stroke #ffe58f / lineWidth 8 / strokeOpacity 0.4，模拟光圈，用户 2026-08-28 指定），微放大经 state size；淡出 = 适度调低透明度（inactive: 0.5/0.42/0.4）让出视觉重心而非隐藏；禁止内置光晕（halo:false）。active/selected 必须显式钉死 stroke/lineWidth/labelFontWeight——内置主题会注入黑色描边与标签加粗（E10）。
- 必须：悬停淡出经 hover-activate `inactiveState` 配置（只配激活侧则淡出不生效）；点击持续选中经全量状态机写 `selected/inactive`（实时读 graph 数据，禁止闭包 props 首帧值），选中期间经 `enable` 门控禁用悬停。
- 必须：实体类型筛选经 `hideElement/showElement` 增量显隐（不触发重布局），边随双端可见性联动隐藏；工作台内容区块默认全部折叠。

## 资产管理（F08）
- 必须：工作台为「图谱 | 资产管理」双页签壳层（Workbench），既有图谱能力整体收拢于 GraphView；资产 HTML 查看器（iframe）挂载于壳层，两页签均可打开。
- 必须：资产卡片为圆角矩形（缩略图 + 名称 + 概述）；无图时以类型色占位（项目资产带类型徽标）；图片懒加载（loading="lazy"）。
- 必须：图片与资产页地址一律经 api 客户端派生（图片规范地址 `/api/assets/file/{stored_name}`，与 HTML 资产页同源），禁止在其他层拼接后端地址。

## 渲染性能
- 禁止：图高频交互（拖拽/缩放/hover）路径上的全树重渲染；交互状态必须通过 selector 局部订阅。
- 必须：G6 实例单例（挂载创建/卸载销毁）；数据变更走增量更新，禁止整图重建（视角切换全量替换除外）。
- 必须：所有 setData/render/hide/show/后处理经组件内渲染链（Promise 链）串行执行，任务前校验实例存活（E09——异步管线互相打断会打坏 G6 元素控制器，表现为边不渲染）。
- 必须：布局收敛后的硬分离（separateOverlaps）随每次数据变更重跑（持久 afterlayout 监听 + 防抖）——力导碰撞是软约束，残余重叠会触发标签避让隐藏节点名。

## 生命周期
- 必须：SSE 连接随组件卸载中断（AbortController），防泄漏。
- 必须：检索输入防抖后再调用 API。
