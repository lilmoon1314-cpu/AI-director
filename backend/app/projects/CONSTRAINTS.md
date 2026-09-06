# projects 模块硬约束

> 实现/修改 projects 模块前必读。

- 必须：projects 业务层（service / repository / models / schemas）零领域模块依赖；跨模块级联删除只在 router 组合层编排（import-linter 契约，DECISIONS 2026-09-06）。
- 必须：默认项目（DEFAULT_PROJECT_ID 固定 id）由 lifespan 幂等确保存在；禁止提供删除默认项目的路径（可改名）；一切「不带 project_id」的领域写入归属默认项目。
- 必须：entity_count / relation_count 只经 `service.touch` 在领域写路径事务内维护，禁止客户端直写、禁止读取时跨模块聚合回填；计数器下界钳制 0。
- 必须：`touch` 为事务内辅助函数（不自行 commit），只允许被领域模块 service 在其事务内调用；常规写函数（create/update/delete）自行 commit。
- 必须：删除项目先 `assert_deletable` 再执行任何数据删除（保护判定先于数据动作）；主库删除经 `projects.delete` 的 commit 原子提交。
- 必须：schema 变更（projects 表 / project_id 列）走 Alembic 迁移；迁移把存量数据打包进默认项目（向后兼容）。
- 禁止：项目名去空白后为空（请求层 422）；id 创建后不可变。
