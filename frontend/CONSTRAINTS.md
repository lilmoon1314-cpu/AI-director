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
- 必须：高亮 = 原样式提高透明度（fill/stroke/label opacity→1，不叠色、不加粗、不改字重），微放大经 state size；淡出 = 适度调低透明度（inactive: 0.5/0.42/0.4）让出视觉重心而非隐藏；禁止节点光晕（halo:false 显式关闭）。
- 必须：悬停淡出经 hover-activate `inactiveState` 配置（只配激活侧则淡出不生效）；点击持续选中经全量状态机写 `selected/inactive`（实时读 graph 数据，禁止闭包 props 首帧值），选中期间经 `enable` 门控禁用悬停。
- 必须：实体类型筛选经 `hideElement/showElement` 增量显隐（不触发重布局），边随双端可见性联动隐藏；工作台内容区块默认全部折叠。

## 渲染性能
- 禁止：图高频交互（拖拽/缩放/hover）路径上的全树重渲染；交互状态必须通过 selector 局部订阅。
- 必须：G6 实例单例（挂载创建/卸载销毁）；数据变更走增量更新，禁止整图重建（视角切换全量替换除外）。

## 生命周期
- 必须：SSE 连接随组件卸载中断（AbortController），防泄漏。
- 必须：检索输入防抖后再调用 API。
