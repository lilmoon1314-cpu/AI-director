"""统一信号采集（可观测性）：五类信号自动采集，业务代码零手写日志。

信号与采集机制（设计详见 core/ARCHITECTURE.md「可观测性」）:
    1. 应用生命周期  lifecycle（startup / ready / shutdown — lifespan 钩子发射）
    2. 功能路径      request.start / request.end（HTTP 中间件自动记录）
    3. 检查点/数据流 checkpoint（@checkpoint 装饰器声明式标注，含 in/out 摘要）
    4. 资源利用      metric（后台线程低频采样 RSS / CPU）
    5. 错误和异常    error（全局异常处理器：request_id + traceback + 三要素）

输出（logs/ 目录，RotatingFileHandler 自动轮转，不入版本库）:
    app.jsonl      运行事件（lifecycle / request / checkpoint）
    error.jsonl    错误专用（独立维护）
    metrics.jsonl  资源采样（供内存持续增长等异常模式分析）
"""

import functools
import json
import logging
import threading
import time
import traceback
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import psutil
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.config import Settings
from app.core.exceptions import AppError
from app.core.responses import error_response, request_validation_error_response

# 当前请求 ID：中间件写入、@checkpoint 读取，实现跨事件串联
current_request_id: ContextVar[str] = ContextVar("current_request_id", default="")

# 疑似敏感字段关键词（参数名命中即脱敏为 ***）
_SENSITIVE_KEYS = ("key", "token", "secret", "password")

# 三路 JSONL logger（setup() 初始化；键与输出文件名一致）
_loggers: dict[str, logging.Logger] = {}

# 资源采样线程的全局状态（每进程只启动一次）
_sampler_started = threading.Event()
_sampler_stop = threading.Event()


def _redact(name: str, value: Any) -> Any:
    """对疑似敏感的参数名脱敏。

    作用: 命中关键词（key/token/secret/password）的参数值替换为 ***，防止密钥入日志。
    参数: name — 参数名；value — 参数值。返回值: 脱敏后的值。异常: 无。依赖: 无。
    """
    if any(k in name.lower() for k in _SENSITIVE_KEYS):
        return "***"
    return value


def _summarize(value: Any, max_len: int = 120) -> Any:
    """将任意值压缩为可读摘要（防日志膨胀）。

    作用: 标量截断 repr；容器只记类型与长度；dict 只记前 8 个键值。
    参数: value — 任意值；max_len — 标量最大长度。返回值: 摘要。异常: 无。依赖: 无。
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        text = repr(value)
        return text if len(text) <= max_len else text[:max_len] + "…"
    if isinstance(value, (list, tuple, set)):
        return f"{type(value).__name__}[{len(value)}]"
    if isinstance(value, dict):
        return {str(k): _summarize(v, 40) for k, v in list(value.items())[:8]}
    return type(value).__name__


def _emit(
    event: str,
    level: str = "info",
    *,
    request_id: str | None = None,
    component: str | None = None,
    phase: str | None = None,
    data: dict[str, Any] | None = None,
    stream: str = "app",
) -> None:
    """写入一条结构化事件（JSON Lines，统一 schema）。

    作用: 所有信号的唯一输出口；setup 未初始化时静默跳过（如模块导入期）。
    参数:
        event — 事件类型（lifecycle/request.start/checkpoint/error/metric 等）。
        level — 级别（info/error）。
        request_id — 关联请求 ID（缺省取当前上下文）。
        component — 组件标识（如 "GET /api/health"、"app.entities.service.create"）。
        phase — 阶段（enter/exit/startup/ready/shutdown 等）。
        data — 事件负载。stream — 输出流（app/error/metrics）。
    返回值: 无。异常: 无（日志失败静默，绝不影响业务）。依赖: logging。
    """
    logger = _loggers.get(stream)
    if logger is None:
        return
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "event": event,
        "level": level,
        "request_id": request_id or current_request_id.get(),
        "component": component,
        "phase": phase,
        "data": data or {},
    }
    logger.info(json.dumps(record, ensure_ascii=False, default=str))


def emit_event(
    event: str,
    *,
    component: str | None = None,
    phase: str | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    """对外接口：写入运行事件（app.jsonl）。

    作用: 供 lifespan 等非装饰器场景显式发射事件。
    参数: event/component/phase/data — 同 _emit。返回值: 无。异常: 无。依赖: _emit。
    """
    _emit(event, "info", component=component, phase=phase, data=data, stream="app")


def emit_lifecycle(phase: str, data: dict[str, Any] | None = None) -> None:
    """对外接口：写入生命周期事件（startup/ready/shutdown）。

    作用: 记录应用各阶段状态（信号 1）。
    参数: phase — 阶段名；data — 附加信息。返回值: 无。异常: 无。依赖: emit_event。
    """
    emit_event("lifecycle", component="app", phase=phase, data=data)


def checkpoint[**P, R](func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """声明式装饰器：自动记录关键 service 路径的入口/出口与数据摘要。

    作用:
        采集功能路径检查点与数据流信号（信号 2/3）；函数抛异常时记 error 事件后原样透传。
    参数:
        func — 被标注的 async 函数（service 层）。
    返回值:
        包装后的 async 函数（保留原元数据）。
    异常:
        原样透传业务异常（仅记录，不吞不改）。
    依赖:
        contextvars（request_id 串联）、functools.wraps。
    """
    component = f"{func.__module__}.{func.__name__}"

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        rid = current_request_id.get()
        safe_in = {f"a{i}": _summarize(_redact(f"a{i}", v)) for i, v in enumerate(args)}
        safe_in.update({k: _summarize(_redact(k, v)) for k, v in kwargs.items()})
        _emit(
            "checkpoint",
            "info",
            request_id=rid,
            component=component,
            phase="enter",
            data={"in": safe_in},
        )
        try:
            result = await func(*args, **kwargs)
        except Exception as exc:
            _emit(
                "checkpoint",
                "error",
                request_id=rid,
                component=component,
                phase="error",
                data={"error": type(exc).__name__},
            )
            raise
        _emit(
            "checkpoint",
            "info",
            request_id=rid,
            component=component,
            phase="exit",
            data={"out": _summarize(result)},
        )
        return result

    return wrapper


class RequestSignalMiddleware(BaseHTTPMiddleware):
    """HTTP 中间件：自动记录请求开始/结束与耗时，注入 x-request-id 响应头。

    作用: 采集功能路径信号（信号 2）；request_id 存入 ContextVar 供 @checkpoint 串联。
    参数: 无（中间件类）。异常: 业务异常原样上抛（由异常处理器统一出口）。依赖: starlette。
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = uuid.uuid4().hex[:12]
        token = current_request_id.set(request_id)
        label = f"{request.method} {request.url.path}"
        _emit(
            "request.start",
            "info",
            request_id=request_id,
            component=label,
            data={"query": str(request.url.query)[:200]},
        )
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration = round((time.perf_counter() - started) * 1000, 1)
            _emit(
                "request.end",
                "error",
                request_id=request_id,
                component=label,
                data={"status": 500, "duration_ms": duration},
            )
            current_request_id.reset(token)
            raise
        duration = round((time.perf_counter() - started) * 1000, 1)
        _emit(
            "request.end",
            "info",
            request_id=request_id,
            component=label,
            data={"status": response.status_code, "duration_ms": duration},
        )
        response.headers["x-request-id"] = request_id
        current_request_id.reset(token)
        return response


async def app_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """全局异常出口：AppError → 统一三要素响应，并写 error.jsonl。

    作用: 采集错误信号（信号 5）+ 保证响应结构统一。
    参数: _request — 当前请求（未使用）；exc — 已构造的应用异常（签名取 Exception
        以满足 Starlette 处理器契约，函数体内收窄回 AppError）。
    返回值: JSONResponse（exc.http_status）。异常: 无。依赖: app.core.responses。
    """
    if not isinstance(exc, AppError):  # 防御：类型不符时转兜底出口，绝不泄露栈
        return await unhandled_error_handler(_request, exc)
    _emit(
        "error",
        "error",
        component="exception",
        data={
            "code": exc.code,
            "problem": exc.problem,
            "cause": exc.cause,
            "fix": exc.fix,
            "detail": exc.detail,
        },
        stream="error",
    )
    return JSONResponse(status_code=exc.http_status, content=error_response(exc))


async def request_validation_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """请求校验错误出口：统一三要素结构（422），并写 error.jsonl。

    作用: 将 FastAPI 默认的校验错误结构转换为统一错误响应结构
        （backend/CONSTRAINTS.md「所有 API 错误响应遵循统一结构」）。
    参数: _request — 当前请求（未使用）；exc — 请求校验异常（签名取 Exception
        以满足 Starlette 处理器契约，函数体内收窄回 RequestValidationError）。
    返回值: JSONResponse（422）。异常: 无。依赖: app.core.responses。
    """
    if not isinstance(exc, RequestValidationError):  # 防御：类型不符走兜底出口
        return await unhandled_error_handler(_request, exc)
    _emit(
        "error",
        "error",
        component="exception",
        data={
            "code": "VALIDATION_ERROR",
            "problem": "请求参数校验失败",
            "errors": exc.errors()[:10],
        },
        stream="error",
    )
    return JSONResponse(status_code=422, content=request_validation_error_response(exc))


async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """兜底出口：未捕获异常 → 500 通用响应（不泄露栈），完整上下文写 error.jsonl。

    作用: 保证任何异常都有统一出口与完整记录（信号 5）。
    参数: _request — 当前请求（未使用）；exc — 未捕获异常。
    返回值: JSONResponse（500）。异常: 无。依赖: traceback。
    """
    _emit(
        "error",
        "error",
        component="exception",
        data={
            "code": "INTERNAL_ERROR",
            "problem": "服务器内部错误",
            "exception": type(exc).__name__,
            "traceback": traceback.format_exc(limit=20),
        },
        stream="error",
    )
    body = {
        "code": "INTERNAL_ERROR",
        "problem": "服务器内部错误",
        "cause": "服务端出现未预期的异常，细节已记录在 logs/error.jsonl",
        "fix": "请携带响应头 x-request-id 反馈给开发者排查",
        "detail": {},
    }
    return JSONResponse(status_code=500, content=body)


def _metric_sampler_loop(interval_seconds: int) -> None:
    """后台采样循环：低频记录进程 RSS / CPU（信号 4）。

    作用: 供内存持续增长等异常模式分析；间隔来自 config。
    参数: interval_seconds — 采样间隔（秒）。返回值: 无（守护线程循环）。异常: 无。依赖: psutil。
    """
    proc = psutil.Process()
    while not _sampler_stop.wait(interval_seconds):
        _emit(
            "metric",
            "info",
            component="process",
            data={
                "rss_mb": round(proc.memory_info().rss / 1024 / 1024, 1),
                "cpu_percent": proc.cpu_percent(interval=None),
            },
            stream="metrics",
        )


def _init_logger(name: str, path: Path, max_mb: int, backup_count: int) -> logging.Logger:
    """初始化单路 JSONL logger（幂等：重复调用不叠加 handler）。

    作用: 统一三路日志的创建（RotatingFileHandler 自动轮转，仅 core 允许使用 logging）。
    参数: name — logger 名；path — 输出文件；max_mb — 单文件上限 MB；backup_count — 保留份数。
    返回值: logging.Logger。异常: 无（文件系统错误由 logging 吞掉）。依赖: logging。
    """
    logger = logging.getLogger(f"ai_director.{name}")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        logger.propagate = False
        handler = RotatingFileHandler(
            path, maxBytes=max_mb * 1024 * 1024, backupCount=backup_count, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    return logger


def setup(app: FastAPI, settings: Settings) -> None:
    """装配全部信号采集（main.py 应用工厂调用，幂等）。

    作用:
        初始化三路 JSONL 日志（app/error/metrics）、请求中间件、
        全局异常处理器与资源采样线程——业务代码从此零手写日志。
    参数:
        app — FastAPI 实例；settings — 全局配置。
    返回值: 无。
    异常: 无。
    依赖:
        logging（仅 core 允许）、starlette 中间件、psutil。
    """
    if getattr(app.state, "observability_installed", False):
        return
    app.state.observability_installed = True

    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    for stream in ("app", "error", "metrics"):
        _loggers[stream] = _init_logger(
            stream,
            log_dir / f"{stream}.jsonl",
            settings.log_rotate_max_mb,
            settings.log_rotate_backup_count,
        )

    app.add_middleware(RequestSignalMiddleware)
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    if not _sampler_started.is_set():
        _sampler_started.set()
        _sampler_stop.clear()
        threading.Thread(
            target=_metric_sampler_loop,
            args=(settings.metric_sample_interval_seconds,),
            daemon=True,
            name="metric-sampler",
        ).start()
