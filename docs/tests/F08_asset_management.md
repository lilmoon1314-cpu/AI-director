# F08 资产管理 — 测试文档

## 测试目标
验证独立资产库（data/assets.db，HTML 形态存储）的图片上传校验、通用资产 CRUD 与 HTML 页、项目实体资产卡片/HTML 惰性生成与孤儿清扫，以及前端工作台「图谱|资产管理」双页切换、卡片网格与内嵌 HTML 查看器。

## 层级矩阵

| 层级 | 用例 | 测试文件 | 必须 | 状态 |
|------|------|----------|------|------|
| L1 单元 | U1–U11 | tests/unit/test_assets_service.py | 必须 | pass |
| L2 集成 | I1–I10 | tests/integration/test_assets_api.py | 必须 | pass |
| L3 E2E（后端） | E1 | tests/e2e/test_assets_flow.py | 必须 | pass |
| L1 前端 | UF1–UF2 | frontend/tests/unit/*.test.tsx | 必须 | pass |
| L2 前端 | IF1–IF4 | frontend/tests/integration/AssetLibrary.test.tsx | 必须 | pass |
| L3 E2E（前端） | EF1–EF2 | frontend/e2e/assets.spec.ts | 必须 | pass |

> L3 必须理由：跨组件（assets+entities 跨模块 + 前后端联调）。前端豁免 mutmut（docs/testing.md §9，2026-08-28 决策）。
> 2026-09-05 验证记录：后端 149 例全绿（含 assets L1 35 + L2 11 + e2e 1）；前端 vitest 108 例全绿；Playwright assets e2e 2 例全绿（截图 AS-01~03）。

## 用例说明

### 后端 L1 单元（tests/unit/test_assets_service.py）
- U1 参数化: MIME 白名单（等价类：有效 png/jpeg/webp/gif；无效 text/plain、application/octet-stream、image/svg+xml——svg 可携带脚本，须拒）→ 有效通过、无效 ValidationError
- U2 参数化: 大小上限边界（边界值：上限-1/上限 通过；上限+1 拒绝 ValidationError）
- U3 参数化: 存储名 uuid 重命名与路径穿越防护（等价类-无效：原始名含 `../`、`..\`、盘符绝对路径、中文与空格）→ 存储名 = `{uuid}.{ext}`，不含用户输入任何成分
- U4: 流式写盘分块（等价类-行为：mock 大于单块上限的上传体，断言按 chunk 循环写入而非整文件读入内存——backend/CONSTRAINTS.md 内存硬约束）
- U5 参数化: 通用资产创建校验（等价类：有效——基础字段+attributes dict；无效——title 空、title 超上限、attributes 非 dict）
- U6: 通用资产 HTML 渲染（attributes 键值渲染为结构化小节；图片以 `/static/assets/{stored_name}` 引用；title/description 含 `<script>` 等被 HTML 转义——XSS 防护，等价类-无效输入的安全行为）
- U7 参数化: 实体页过期判定（边界值：asset.updated_at == entity.updated_at 视为 fresh；entity 更新一刻 → stale；无记录 → missing）
- U8: 孤儿清扫（entity_id 不在存活实体集 → 删记录+删图片文件；在 → 原样保留；等价类：孤儿/存活）
- U9: 图片删除（记录删除+文件删除；若为封面则 cover 引用置空）
- U10: 通用资产删除级联（其名下图片记录与文件同步删除）
- U11: 图片上传实体存在性校验（owner 实体不存在 → NotFoundError——依赖 entities.service，等价类-无效）

### 后端 L2 集成（tests/integration/test_assets_api.py，真实双库）
- I1: POST /api/assets/images 上传成功 → 201 返回元数据（id/stored_name/url），文件落盘 ASSET_DIR
- I2 参数化: 上传无效（白名单外/超上限）→ 422，错误体三要素完整 + detail 字典整体断言
- I3: 通用资产全生命周期：POST 创建 → GET 列表（卡片字段含封面 url）→ GET page（text/html 且含标题）→ PATCH 更新 → page 反映变更 → DELETE → page 404
- I4: GET /api/assets/entities → 实体来自主库、封面来自资产库的分组卡片（按 type 分组、含名称/概述/缩略图），跨库 join 正确
- I5: 实体页惰性生成与过期再生：首次 GET /api/assets/entity/{id}/page 生成 HTML；PATCH 实体后再 GET 触发再生（内容反映新值）——updated_at 判过期
- I6: 实体删除联动清扫：删除实体后 GET /api/assets/entities → 该实体卡片消失，资产记录与图片文件被清扫
- I7: 上传目标实体不存在（主库校验经 entities.service）→ 404 三要素
- I8: 静态访问 /static/assets/{stored_name} 可取回原文件；越径请求（..%2f）被拒绝
- I9: GET /api/assets/images?scope=&owner_id= 返回按归属的图片明细（升序、含 url）
- I10: GET /api/assets/file/{stored_name} 同源图片路由返回图片字节（HTML 页内引用规范地址）；缺失 404
- I3 扩展: 通用资产两图上传（首图自动封面）→ PUT cover 显式换封面 → 卡片封面联动

### 后端 L3 E2E（tests/e2e/test_assets_flow.py，跨模块全链路）
- E1: 建实体（entities API）→ 传图（assets API）→ 建通用资产 → 实体 page HTML 含实体名与图片路径 → PATCH 实体名 → page 再生 → 删实体 → GET entities 清扫无卡片——assets+entities 跨模块 + 双库一致性（内存守卫 fixture 随行）

### 前端 L1 单元
- UF1: AssetCard 渲染（缩略图 url/名称/概述截断；无图时类型色占位——等价类：有图/无图）
- UF2: assetStore（列表加载与分类筛选选择器；查看器 open/close state；等价类：打开/关闭）

### 前端 L2 集成（msw mock API）
- IF1: 双页切换：默认「图谱」（画布与操作栏在）；切「资产管理」→ 通用资产区+项目资产区渲染；切回「图谱」画布内容仍在（数据不重拉或幂等重拉）
- IF2: 通用资产新建表单：填表+attributes 键值 → POST → 列表刷新出现新卡片；无效提交（空标题）被拦截
- IF3: 项目资产卡片点击 → 内嵌查看器打开（iframe src 指向 page url）→ 返回按钮关闭
- IF4: 实体详情面板图片区：上传图片 → 预览出现；「查看资产页」入口打开查看器

### 前端 L3 E2E（Playwright，真实前后端）
- EF1: API 播种实体+图片 → 切「资产管理」→ 项目资产卡片可见 → 点击打开内嵌查看器（HTML 含实体名）→ 返回（截图 AS-01/02）
- EF2: 通用资产新建全链路（表单提交 → 卡片出现 → 打开 page 查看）→ 删除 → 卡片消失（截图 AS-03）

## 变异测试结果（docs/testing.md §9；2026-09-05 三轮迭代）

- **scope**：app/assets 逻辑文件 7 个（db/models/repository/router/schemas/service/storage）；rendering.py（纯样式/HTML 模板）按 §9 成本控制条款收窄排除——其功能行为由 U6 转义断言、I3/I5 page 内容断言与前端 e2e 渲染检查覆盖
- **判杀器构成**：L1（tests/unit/test_assets_service.py，50 例）+ L2（tests/integration/test_assets_api.py，13 例）+ L3（tests/e2e/test_assets_flow.py，1 例），层级覆盖原则满足
- **结果**：总变异体 453；实杀 389 + 超时判杀 1 → **kill rate 85.9% ≥ 85% 达标**
- **迭代过程**：首轮全模块 549 变异体判杀率仅 50%（rendering 模板与声明式代码变异体不可有意义判杀）→ 排除 rendering 收窄 scope + 补契约钉死测试组（E05 文案精确相等 / ORM nullable 与 DDL / 常量与 Literal / @checkpoint 标注）→ 复跑达标
- **存活 63 项（13.9% < 20% 上限）逐类归档**：
  - 上传元数据回退分支（`upload.filename or ""` 等 6 项）：FastAPI UploadFile 实际必供元数据，测试桩恒定供值，回退分支不可达
  - 大小上限换算数字（`asset_max_size_mb * 1024 * 1024` 组合 6 项）：钉死需 10MB 级二进制载荷测试，成本高且阈值本身由 config 驱动
  - service 内冗余 mkdir（lifespan 已建目录）2 项：防御性冗余，行为不可由单测触发（settings 进程级缓存）
  - 生成时间 strftime 文本 3 项：时间展示文本，钉死属脆弱文案钉刺
  - wrong-kind 记录防护残余分支（set_cover/get_general_page 等行内组合变异）5 项
  - schemas Field 默认值/边界组合细节（Update 模型 default=None 语义等价）约 15 项
  - models 列声明组合细节（Text↔String 映射、Mapped 注解删除等，运行时由 create_all 自洽）约 9 项
  - db ensure_assets_dir 分支 3 项、storage 越界死分支/消息细节 8 项、extra=forbid/computed_field 5 项
- **过程事故**（error.jsonl E11/T-20260905-01/02）：首轮 mutmut 运行中并发编辑被测模块，编辑被还原机制覆盖丢失；被强杀的运行残留变异体与 .bak 一度被 git add -A 误提交（已从 .bak 恢复原始实现）。自动化转化：task.py mutate 脏工作区守卫 + 架构测试禁止 app/ 下 .bak 残留

## 验收判定
所有"必须"层级通过 + 状态列全 pass + 变异测试达标（kill rate ≥ 85%）+ make check 通过 → 功能完成。
