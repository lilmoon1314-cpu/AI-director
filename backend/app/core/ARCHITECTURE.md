# core 模块 — 基础设施

## 职责

- 配置管理（config.py 位于 app/ 根，core 提供配置访问辅助）
- AsyncEngine / AsyncSession 工厂（SQLite WAL + 外键 pragma）
- 统一异常层级（AppError 及其子类，三要素必填）
- 日志与可观测性：五类信号统一自动采集（见「可观测性」）
- 日志配置（结构化 JSON 事件，请求 ID 关联）

## 对外接口

| 入口 | 说明 |
|------|------|
| `core.db.get_engine()` | AsyncEngine 进程单例（WAL + foreign_keys=ON） |
| `core.db.get_session()` | FastAPI 依赖：每请求一个 AsyncSession |
| `core.exceptions.*` | AppError / NotFoundError / ConflictError / ReferentialError / PerspectiveError / AgentError |
| `core.observability.setup(app)` | 注册信号采集（中间件/lifespan 钩子/异常处理器/采样线程） |
| `core.observability.@checkpoint` | 关键路径声明式标注（入口/检查点/出口 + 数据摘要） |
| `core.logging.setup()` | 日志初始化（保留兼容入口，实际由 observability 统一装配） |

## 可观测性（信号自动采集）

原则：**不依赖业务代码手写日志**。信号由本模块统一采集，业务代码至多用 `@checkpoint` 做声明式标注。

| 信号 | 事件类型 | 采集机制（自动） |
|------|----------|------------------|
| 应用生命周期 | `lifecycle`（startup/ready/shutdown） | lifespan 钩子统一发射 |
| 功能路径 | `request.start` / `request.end` | HTTP 中间件：request_id、method、path、status、耗时 |
| 功能路径（检查点） | `checkpoint` | `@checkpoint` 装饰器标注关键 service 函数（入口/出口） |
| 数据流 | `checkpoint` 事件携带 in/out 摘要 | 装饰器自动提取参数/返回摘要（类型、计数、id 列表；脱敏 + 限长） |
| 资源利用 | `metric`（rss/cpu） | 后台采样线程，间隔来自 config，低频常开 |
| 错误和异常 | `error` | 全局异常处理器：request_id + 参数摘要 + traceback + 三要素 |

统一事件 schema（JSON Lines，一行一事件）：

```json
{ "ts": "...", "event": "request.end", "level": "info",
  "request_id": "...", "component": "app.entities.service", "phase": "exit", "data": { } }
```

输出与维护（logs/ 目录，gitignore，RotatingFileHandler 自动轮转）：

| 文件 | 内容 |
|------|------|
| app.jsonl | 运行事件（lifecycle / request / checkpoint） |
| error.jsonl | 错误专用，独立维护：完整上下文 + traceback + 三要素 |
| metrics.jsonl | 资源采样，供异常模式（如内存持续增长）人工/脚本分析 |

## 内部结构

```
core/
├── db.py               # 引擎与会话工厂
├── exceptions.py       # 异常层级（problem/cause/fix 构造必填）
├── observability.py    # 信号采集：中间件、@checkpoint、采样线程、事件写入
└── responses.py        # 统一错误响应构造（code/problem/cause/fix/detail）
```

## 依赖

- 依赖：无（最底层；仅标准库与三方框架）
- 被依赖：entities / relations / perspectives / assets / sync / agent、main.py

## 约束

见本模块 [CONSTRAINTS.md](./CONSTRAINTS.md)（修改 core 前必读）。
