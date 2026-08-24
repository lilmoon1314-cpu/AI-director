# core 模块硬约束

> 修改 core 模块前必读。

- 禁止：core import 任何领域模块（保持零业务知识）。
- 禁止：在 core 放置业务工具函数；通用工具仅在 ≥2 个模块复用时才可下沉。
- 必须：SQLite 每次连接启用 `PRAGMA journal_mode=WAL` 与 `PRAGMA foreign_keys=ON`。
- 必须：observability 对业务代码保持零侵入——采集全部通过中间件/lifespan/异常处理器/装饰器完成。
- 必须：@checkpoint 记录的数据摘要自动脱敏（密钥/令牌类字段）并限长（防日志膨胀）。
