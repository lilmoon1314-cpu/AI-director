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
- 必须（F11 起生效，DESIGN.md §9）：统一卡片规范——rounded-2xl 毛玻璃容器（`ring-1 ring-black/5 bg-white/80`，dark: `ring-white/10 bg-slate-800/80`）+ hover 上浮（`-translate-y-1` + `shadow-md`）+ 封面 `group-hover:scale-105`（150–200ms ease-out）；封面 16:10 裁切懒加载；标题 1 行 / 概要 2 行截断；卡片 ⋯ 管理菜单 hover / focus 可见（键盘可达）。（项目首屏卡 F11、资产卡 F12 均已落地。）
- 必须：浮层层级规范——详情面板 10 / 下拉与浮钮 20 / AgentDock 30（规划，DESIGN.md §5.5）/ modal 与全屏 HTML 查看器 50（modal：ui/Modal，F12）。

## 资产管理（F08/F12）
- 必须：工作台为「图谱 | 资产管理」双页签壳层（Workbench），既有图谱能力整体收拢于 GraphView；资产 HTML 查看器（iframe）挂载于壳层，两页签均可打开。
- 必须：资产卡片为圆角矩形（缩略图 + 名称 + 概述），遵循 §9 统一卡片规范；无图时以类型色占位（项目资产带类型徽标）；图片懒加载（loading="lazy"）。
- 必须：图片与资产页地址一律经 api 客户端派生（图片规范地址 `/api/assets/file/{stored_name}`，与 HTML 资产页同源），禁止在其他层拼接后端地址。
- 必须（F12 落地，DESIGN.md §5.3）：资产页分区即子路由（URL 即状态）——`assets/general`（默认落点，OQ-6）| `assets/project`（类型库墙）| `assets/project/:entityType`（类型库详情）；无效 entityType 重定向回类型库墙；嵌套 `<Outlet>` 必须回传上层 context（projectId）——react-router 不自动继承，遗漏会使深层路由在 store 同步前读到 undefined。
- 必须（F12 落地）：各分区独立搜索为前端过滤（通用区标题/描述/分类与 chips AND 叠加；类型详情名称/描述），空串/纯空白 = 不过滤；空状态统一模式——空库/空类型引导卡（一句话 + 单个主按钮）、搜索无命中独立提示（与空库文案可区分）；空类型引导「去图谱页创建」经 `?create=entity&type=<valid>` 查询参数联动（GraphView 挂载时消费并清理参数）。
- 必须（F12 落地，OQ-3）：通用资产新建/编辑经居中 modal（ui/Modal），禁止整区替换列表；modal 不自带 Esc 关闭（表单含未保存输入，显式取消按钮为唯一出口）。

## 渲染性能
- 禁止：图高频交互（拖拽/缩放/hover）路径上的全树重渲染；交互状态必须通过 selector 局部订阅。
- 必须：G6 实例单例（挂载创建/卸载销毁）；数据变更走增量更新，禁止整图重建（视角切换全量替换除外）。
- 必须：所有 setData/render/hide/show/后处理经组件内渲染链（Promise 链）串行执行，任务前校验实例存活（E09——异步管线互相打断会打坏 G6 元素控制器，表现为边不渲染）。
- 必须：布局收敛后的硬分离（separateOverlaps）随每次数据变更重跑（持久 afterlayout 监听 + 防抖）——力导碰撞是软约束，残余重叠会触发标签避让隐藏节点名。

## 生命周期
- 必须：SSE 连接随组件卸载中断（AbortController），防泄漏。**规划修订（随 F10/AgentDock 落地时更新本条，DESIGN.md §5.5）**：SSE 生命周期挂会话级（agentStore），随会话结束/项目切换中断；侧边栏收起不中断（防泄漏本意由会话级 AbortController 承担）。
- 必须：检索输入防抖后再调用 API。
- 必须（F11 已落地，DESIGN.md §4.4/§7）：切换项目按 store 重置换机执行（perspective/selection/entityIndex/asset 项目分区重置，generalCards 全局缓存保留；SSE 中止项随 F10 AgentDock 落地）；路由参数 `:projectId` 为项目上下文唯一事实源（Outlet context 渲染期同步）。
