# assets 模块 — 资产管理（HTML 形态资产库）

> 2026-09-05 重新定界（F08，用户需求 + DECISIONS 2026-09-05 三条）：资产以 HTML 形态存储于独立资产库，服务通用参考素材管理与实体多模态查看，为后续向 LLM 传递多模态上下文铺路。

## 职责

- 图片上传：类型白名单、大小上限校验，uuid 重命名流式写盘 `data/assets/`，元数据入资产库
- 通用资产 CRUD：跨项目可复用参考素材（表情参考/风格参考/植被参考等，分类为自由标签），字段 = 基础字段 + attributes 自由 JSON，模板渲染为自包含 HTML 存库
- 项目资产（实体资产）：主库实体按类型分组的卡片列表（跨库聚合缩略图/名称/概述）；实体 HTML 资产页按 `entity.updated_at` 惰性生成、过期再生
- 实体删除联动：卡片列表请求时孤儿清扫（删除孤儿资产记录与图片文件）
- HTML 资产页访问（`text/html`）与图片静态访问（限 `data/assets/` 内，防路径穿越）

## 存储模型（独立资产库 assets.db，非主库）

```
asset_records                         asset_images
├── id (uuid, PK)                     ├── id (uuid, PK)
├── kind ('general' | 'entity')       ├── scope ('general' | 'entity')
├── entity_id (可空, 索引)             ├── owner_id (general 资产 id 或实体 id)
├── category (自由标签)                ├── filename_orig
├── title                             ├── stored_name ({uuid}.{ext})
├── description                       ├── mime
├── attributes (JSON, 可空)           ├── size
├── html (自包含 HTML 全文)           └── created_at
├── cover_image_id (可空)
├── created_at / updated_at
```

- 两表间应用层引用（cover_image_id → asset_images.id），无跨库 FK；写路径维护一致性
- assets.db 由 lifespan 启动 `create_all` 幂等引导（Alembic 豁免，见 DECISIONS 2026-09-05）；schema 变更须向后兼容

## 对外接口

### service 层（其他模块唯一入口）

| 函数 | 说明 | 异常 |
|------|------|------|
| `upload_image(scope, owner_id, file) -> AssetImageRead` | 校验（白名单/上限）→ 校验 owner 存在（entity 经 entities.service）→ 流式写盘 → 元数据入库 | NotFoundError / ValidationError |
| `delete_image(image_id) -> None` | 删文件+记录；若为封面同步清空引用 | NotFoundError |
| `set_cover(asset_id, image_id) -> AssetRead` | 设通用资产封面 | NotFoundError / ValidationError |
| `create_general(payload) -> AssetRead` | 创建通用资产 + 渲染 HTML | ValidationError |
| `update_general(asset_id, payload) -> AssetRead` | 更新基础字段/attributes → 重渲染 HTML | NotFoundError / ValidationError |
| `delete_general(asset_id) -> None` | 级联删除其图片（记录+文件） | NotFoundError |
| `list_general(category?) -> list[AssetCard]` | 通用资产卡片列表 | — |
| `get_general(asset_id) -> AssetRead` | 通用资产详情（含图片明细，编辑表单数据源） | NotFoundError |
| `get_general_page(asset_id) -> str` | 通用资产 HTML 全文 | NotFoundError |
| `list_images(scope, owner_id) -> list[AssetImageRead]` | 图片明细列表（面板图片区数据源） | — |
| `list_entity_cards() -> list[EntityAssetCard]` | 实体按类型分组卡片（跨库：实体来自 entities.service，封面来自资产库）；调用时先孤儿清扫 | — |
| `get_entity_page(entity_id, session) -> str` | 实体 HTML 页惰性生成/过期再生并返回 | NotFoundError（实体不存在） |
| `get_image_file(stored_name) -> Path` | 图片物理路径（限 ASSET_DIR 内，防穿越；/api/assets/file 数据源） | NotFoundError / ValidationError |

### HTTP 路由（/api/assets）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/assets/images（multipart: file + scope + owner_id） | 上传图片 |
| GET | /api/assets/images?scope=&owner_id= | 图片明细列表（面板图片区/编辑表单数据源） |
| DELETE | /api/assets/images/{image_id} | 删除图片 |
| GET | /api/assets/general?category= | 通用资产卡片列表 |
| POST | /api/assets/general | 创建通用资产 |
| GET | /api/assets/general/{asset_id} | 通用资产详情（含图片明细，编辑表单数据源） |
| PATCH | /api/assets/general/{asset_id} | 更新通用资产 |
| DELETE | /api/assets/general/{asset_id} | 删除通用资产 |
| GET | /api/assets/general/{asset_id}/page | 通用资产 HTML 页（text/html） |
| PUT | /api/assets/general/{asset_id}/cover | 设封面 |
| GET | /api/assets/entities | 项目资产卡片（按类型分组，含孤儿清扫） |
| GET | /api/assets/entity/{entity_id}/page | 实体 HTML 资产页（text/html，惰性生成） |
| GET | /api/assets/file/{stored_name} | 图片文件访问（/api 同源路由，HTML 页内图片引用的规范地址） |
| GET | /static/assets/{stored_name} | 图片静态访问（挂载点在 main.py，仅覆盖 data/assets/；保留兼容） |

图片规范地址为 `/api/assets/file/{stored_name}`（与页面同源，开发期经 vite /api 代理，
生产经网关统一转发）；/static 挂载保留但不作为 HTML 内引用地址。

## 依赖

- 依赖：core、entities（经 entities.service：实体存在校验 / 卡片与页面取实体数据）
- 被依赖：frontend（资产管理页、详情面板缩略图）；第二阶段 agent（资产注入 LLM 上下文）
- 被依赖方向恒为单向（assets 不被 entities 反向依赖；实体删除清理走读取时孤儿清扫）

## 约束

见本模块 [CONSTRAINTS.md](./CONSTRAINTS.md)（实现/修改 assets 前必读）。
