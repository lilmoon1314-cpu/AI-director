# assets 模块 — 资产上传与查看

## 职责

- 实体资产（图片/文档）上传：类型白名单、大小上限校验
- 文件安全存储（uuid 重命名，原始文件名保留在元数据）
- 按实体检索资产列表
- 静态资产访问（限 data/assets/ 目录内，防路径穿越）

## 对外接口

### service 层（其他模块唯一入口）

| 函数 | 说明 | 异常 |
|------|------|------|
| `upload(entity_id: str, file: UploadFile) -> AssetRead` | 校验（白名单/上限）→ 校验实体存在 → 流式写盘 → 记录元数据 | NotFoundError（实体不存在）/ ValidationError（类型/大小） |
| `list_by_entity(entity_id: str) -> list[AssetRead]` | 实体资产列表 | NotFoundError |
| `delete(asset_id: str) -> None` | 删除记录与文件 | NotFoundError |

`AssetRead = { id, entity_id, filename(原始名), stored_path, mime, size, created_at }`；同时返回写入实体 `properties.assets` 后的实体最新状态（由前端用于刷新详情）。

### HTTP 路由（/api/assets）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/assets（multipart: entity_id + file） | 上传 |
| GET | /api/assets?entity_id= | 资产列表 |
| DELETE | /api/assets/{id} | 删除 |
| GET | /static/assets/{stored_name} | 静态访问（挂载点在 main.py，仅覆盖 data/assets/） |

## 依赖

- 依赖：core、entities（经 entities.service 校验实体存在）
- 被依赖：frontend（节点详情缩略图/链接）

## 约束

见本模块 [CONSTRAINTS.md](./CONSTRAINTS.md)（实现/修改 assets 前必读）。
