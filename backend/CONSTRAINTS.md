# backend/CONSTRAINTS.md — 后端硬约束

> 适用范围：backend/ 全部代码。修改后端任何代码前必读。

## 模块解耦与事务
- 必须：跨模块调用只允许 `from app.<module>.service import ...`。
- 禁止：跨模块 import 其他模块的 repository / models / schemas 内部类型（共享 DTO 由被调用方在 service 层签名导出）。
- 必须：事务边界在 service 层（service 函数接收 AsyncSession，自行 commit/rollback）；router 不感知事务。

## 数据与存储
- 必须：所有数据库访问经由 SQLAlchemy ORM；禁止裸 SQL 字符串拼接。
- 必须：SQLite 开启 WAL 模式与外键约束。
- 必须：relationships.source / relationships.target 声明外键指向 entities(id)，删除策略 ON DELETE RESTRICT——应用层 ReferentialError 为前置校验（友好提示），DB 层 RESTRICT 为兜底（防旁路写入产生悬空引用/幽灵节点）；F02 首个迁移同时创建 entities 与 relationships 两表（实体删除校验依赖关系表存在）。
- 必须：schema 变更一律通过 Alembic 迁移；禁止手改已生成的迁移文件。例外：资产库 assets.db 为独立派生存储，经 lifespan 启动时 metadata.create_all 幂等引导，其 schema 变更须对既有文件向后兼容（加列/加表，禁删改列）——DECISIONS 2026-09-05。
- 禁止：直接物理删除被关系引用的实体；删除前必须校验引用并返回阻断提示。
- 必须：id 由系统生成且创建后不可变更；name 变更不得影响 id。
- 必须：含 known_by / audience_known 的数据在写入时校验视角标记的完整性（类型与成员有效性）。

## 异常与响应
- 必须：所有 API 错误响应遵循统一结构（code / problem / cause / fix / detail），异常经全局异常处理器统一出口（层级见 backend/ARCHITECTURE.md §4）。
- 必须：错误消息三要素完整（什么出了问题/为什么/怎么修）；AppError 构造函数 problem/cause/fix 必填（规范见 docs/lessons.md §3）。
- 禁止：未捕获异常栈泄露给客户端。
- 必须：错误写入独立日志 logs/runtime_error.jsonl（request_id + 参数摘要 + traceback + 三要素；backend/logs/error.jsonl 为 agent 维护的错误模式库，两者职责不同，见 DECISIONS 2026-08-27）。

## 日志与信号采集
- 禁止：业务模块手写散点日志（直接调用 logging）；五类信号由 core observability 统一自动采集（设计见 core/ARCHITECTURE.md「可观测性」）。
- 必须：关键 service 路径用 @checkpoint 声明式标注（非日志语句）。
- 必须：日志文件自动轮转；logs/ 目录不入版本库。

## 内存
- 必须：文件上传与大数据响应流式处理；禁止整文件读入内存。
- 禁止：模块级可变全局缓存（防内存泄漏与多 worker 不一致）。
