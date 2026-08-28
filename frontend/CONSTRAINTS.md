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

## 渲染性能
- 禁止：图高频交互（拖拽/缩放/hover）路径上的全树重渲染；交互状态必须通过 selector 局部订阅。
- 必须：G6 实例单例（挂载创建/卸载销毁）；数据变更走增量更新，禁止整图重建（视角切换全量替换除外）。

## 生命周期
- 必须：SSE 连接随组件卸载中断（AbortController），防泄漏。
- 必须：检索输入防抖后再调用 API。
