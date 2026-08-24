# relations 模块硬约束

> 实现/修改 relations 模块前必读。

- 必须：关系端点（source/target）存在性校验经 entities.service；禁止直接查询 entities 表。
- 必须：known_by 成员必须是已存在的 character id（写入时校验，防脏数据破坏视角过滤）。
- 禁止：自环关系（source == target）。
- 禁止：重复关系（同 source+target+type）静默创建；必须返回 ConflictError。
- 必须：视角标记字段（known_by / audience_known）schema 变更时同步更新 perspectives 模块文档。
