# sync 模块 — Markdown 导入导出

## 职责

- 全量实体/关系导出为 Markdown 文件（YAML front matter + 正文）
- Markdown 文件导入解析，与库内数据比对生成冲突检测报告
- 用户确认后应用导入变更（新增/更新，不做删除）

## 对外接口

### service 层（其他模块唯一入口）

| 函数 | 说明 | 异常 |
|------|------|------|
| `export_all() -> str` | 全量导出为 Markdown 文本（front matter 含元数据与 updated_at） | — |
| `parse_import(content: str) -> ImportReport` | 解析 + 冲突检测（updated_at 比对），不写库 | ValidationError（格式非法） |
| `apply_import(report_id: str) -> SyncResult` | 对已确认报告应用变更 | ConflictError（报告过期/数据已变） |

`ImportReport = { items: [{ action: create|update|conflict, entity|relation, local_updated_at, imported_updated_at }] }`。

### HTTP 路由（/api/sync）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/sync/export | 下载全量 Markdown |
| POST | /api/sync/import（multipart 文件） | 解析并返回冲突报告（不写库） |
| POST | /api/sync/apply | 按报告应用变更 |

### 导出格式契约

```markdown
---
kind: entity            # entity | relation
id: char-zhou-lan
type: character
name: 周澜
updated_at: 2026-08-24T10:00:00
audience_known: true
aliases: [周姑娘, 澜姐]
...                     # 其余字段平铺
---

## description
正文描述...
```

## 依赖

- 依赖：core、entities（create/update/get_many）、relations（create/update/get_all）
- 被依赖：frontend（导入导出入口）

## 约束

见本模块 [CONSTRAINTS.md](./CONSTRAINTS.md)（实现/修改 sync 前必读）。
