# sync 模块硬约束

> 实现/修改 sync 模块前必读。

- 禁止：导入在用户确认（apply）前写库；必须先返回冲突报告。
- 必须：冲突判定 = 同 id 且 `imported.updated_at != local.updated_at` → conflict，须用户逐项裁决。
- 禁止：导入删除库内数据（导出文件中不存在的实体不受导入影响）。
- 禁止：front matter 解析失败时部分应用；必须整体拒绝。
- 禁止：静默改写 id / type 等不可变字段；与库内不一致按 conflict 处理。
