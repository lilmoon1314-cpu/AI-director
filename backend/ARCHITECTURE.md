# backend/ARCHITECTURE.md — 后端架构

> FastAPI 模块化单体。全局模块依赖见根目录 ARCHITECTURE.md；各领域模块细节见 app/*/ARCHITECTURE.md。

## 1. 技术栈

Python 3.12+ / FastAPI / Pydantic v2 / SQLAlchemy 2.0 (async) / Alembic / SQLite（WAL）/ openai SDK（OpenAI 兼容协议）。

## 2. 目录结构

```
backend/
├── pyproject.toml          # uv 管理依赖与锁 + import-linter 契约
├── .env.example            # 环境变量模板（复制为 .env）
├── migrations/             # Alembic 迁移
├── data/                   # SQLite 数据库文件 + assets/ 上传存储（不入库）
├── logs/                   # 信号日志 app/error/metrics.jsonl（不入库，自动轮转）
├── tests/                  # 分层测试（策略见 docs/testing.md）
│   ├── conftest.py         # 共享 fixture（临时 DB、TestClient、内存采样）
│   ├── unit/               # L1 单元：模块内，依赖 mock
│   ├── integration/        # L2 集成：真实 DB，router→service→repository
│   ├── e2e/                # L3 E2E：跨模块 HTTP 全链路（TestClient）
│   └── architecture/       # 架构约束可执行检查（docs/architecture_checks.md）
└── app/
    ├── main.py             # 应用工厂、路由挂载、全局异常处理、lifespan
    ├── config.py           # Pydantic Settings，从环境变量/.env 读取
    ├── core/               # 基础设施（见 core/ARCHITECTURE.md）
    ├── entities/           # 实体模块
    ├── relations/          # 关系模块
    ├── perspectives/       # 视角过滤模块
    ├── assets/             # 资产模块
    ├── sync/               # Markdown 同步模块
    └── agent/              # LLM 对话模块
```

每个领域模块内部统一四层：

```
router.py       # HTTP 路由，仅做参数解析与响应包装，不含业务逻辑
service.py      # 业务逻辑，模块唯一对外接口（其他模块只允许 import 此层）
repository.py   # 数据访问，唯一允许 import ORM 模型的层
models.py       # SQLAlchemy ORM 模型
schemas.py      # Pydantic 请求/响应模型
```

## 3. 模块解耦规则

跨模块调用、事务边界与 DTO 导出规则见 [backend/CONSTRAINTS.md](./CONSTRAINTS.md)「模块解耦与事务」（修改后端任何代码前必读）。

## 4. 全局异常处理机制

统一错误响应结构（三要素规范见 docs/lessons.md §3）：

```json
{
  "code": "ENTITY_NOT_FOUND",
  "problem": "实体不存在",
  "cause": "id 'char-x' 未在库中",
  "fix": "先调用 GET /api/entities?q= 检索确认 id",
  "detail": { "entity_id": "char-x" }
}
```

异常层级（定义于 core/exceptions.py）。`AppError(problem, cause, fix, ...)` 三要素为构造必填参数——实例化即保证错误消息完整：

```
AppError（基类: code, problem, cause, fix, http_status, detail）
├── NotFoundError          # 404 资源不存在
├── ValidationError        # 422 业务校验失败（区别于 Pydantic 请求校验）
├── ConflictError          # 409 冲突（如 Markdown 导入冲突、唯一约束）
├── ReferentialError       # 409 删除被引用资源
├── PerspectiveError       # 403 视角违规（访问不可见资源）
└── AgentError             # 502 LLM 调用失败/超时
```

`main.py` 注册 `app.exception_handler(AppError)` 统一出口；未捕获异常统一 500（`INTERNAL_ERROR`），禁止异常栈泄露给客户端。所有错误同时写入独立错误日志 logs/runtime_error.jsonl（含 request_id、参数摘要、traceback、三要素，见 core/ARCHITECTURE.md「可观测性」）。

## 5. 应用生命周期（lifespan）

```
startup:  加载 config（缺失必填项快速失败）
          → 检查 data/ 与 data/assets/ 目录存在
          → 注册静态资产挂载（限 data/assets/ 内，防路径穿越）
          → AsyncEngine 进程单例初始化
shutdown: dispose AsyncEngine、释放 LLM 客户端连接
```

- DB 会话：每请求一个 `AsyncSession`（FastAPI yield 依赖），请求结束自动释放。
- LLM 客户端：懒加载进程单例（首次调用创建），超时与重试参数来自 config。

## 6. 内存管理策略

- 文件上传**流式**写盘（分块读取），禁止将整个文件读入内存。
- SSE 流式响应使用 async generator，客户端断开时自动终止并释放。
- 图查询接口返回全量节点/边（MVP 千级实体规模），不做服务端分页；超出规模后引入分页/增量同步。
- 禁止模块级可变全局缓存（防止内存泄漏与多 worker 不一致）。

## 7. API 路由总表

| 前缀 | 模块 | 说明 |
|------|------|------|
| /api/entities | entities | 实体 CRUD + 搜索 |
| /api/relations | relations | 关系 CRUD |
| /api/graph | perspectives | 三视角过滤图查询 |
| /api/assets | assets | 资产上传/列表/静态访问 |
| /api/sync | sync | Markdown 导入导出 |
| /api/agent | agent | SSE 对话、建议草案、确认写入 |

OpenAPI 文档自动生成于 `/docs`（FastAPI 内建），前端类型由该 schema 派生。

## 8. 配置项（.env，经 config.py 读取）

| 键 | 说明 |
|----|------|
| DATABASE_URL | SQLite 连接串（默认 sqlite+aiosqlite:///data/app.db） |
| ASSET_DIR | 资产存储目录（默认 data/assets） |
| ASSET_MAX_SIZE_MB | 上传大小上限 |
| ASSET_ALLOWED_TYPES | 类型白名单（逗号分隔） |
| LLM_BASE_URL / LLM_API_KEY / LLM_MODEL | OpenAI 兼容端点 |
| LLM_TIMEOUT_SECONDS | 调用超时 |
| CORS_ORIGINS | 前端来源（默认 http://localhost:5173） |
| LOG_DIR | 信号日志目录（默认 backend/logs） |
| LOG_LEVEL | 运行事件级别（默认 INFO） |
| LOG_ROTATE_MAX_MB / LOG_ROTATE_BACKUP_COUNT | 日志轮转阈值 |
| METRIC_SAMPLE_INTERVAL_SECONDS | 资源采样间隔（默认 30） |
| MEMORY_GUARD_THRESHOLD_MB | 测试内存回归守卫阈值 |
