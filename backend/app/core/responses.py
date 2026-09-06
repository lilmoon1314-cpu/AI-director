"""统一错误响应构造：code / problem / cause / fix / detail。"""

from typing import Any

from fastapi.exceptions import RequestValidationError

from app.core.exceptions import AppError


def _json_safe(value: Any) -> Any:
    """递归转换为 JSON 可序列化值（异常对象等转 repr 字符串）。

    作用:
        Pydantic v2 的 field_validator 抛 ValueError 时，错误列表 ctx 内嵌
        异常对象（不可 json.dumps）；响应体与 JSONL 日志共用本防线，避免
        「处理器内序列化崩溃把 422 变 500」（F11 实测暴露的共享层缺陷）。
    参数: value — 任意值。返回值: JSON 可序列化值。异常: 无。依赖: 无。
    """
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def validation_errors_brief(err: RequestValidationError, limit: int = 10) -> list[dict[str, Any]]:
    """提取 JSON 安全的校验错误列表（限长防膨胀）。

    作用: 422 响应 detail 与错误日志共用的唯一错误列表出口。
    参数: err — 请求校验异常；limit — 截断条数。返回值: list[dict]。
    异常: 无。依赖: _json_safe。
    """
    return [_json_safe(e) for e in err.errors()[:limit]]


def error_response(err: AppError) -> dict[str, Any]:
    """将 AppError 转换为统一结构的 JSON 响应体。

    作用:
        保证所有 API 错误响应结构一致（backend/CONSTRAINTS.md「异常与响应」），
        消费方可稳定解析三要素字段。
    参数:
        err: 已构造的应用异常（AppError 及其子类）。
    返回值:
        dict — 形如 {"code", "problem", "cause", "fix", "detail"}，可直接作为
        JSONResponse 的 content。
    异常:
        无。
    依赖:
        app.core.exceptions.AppError。
    """
    return {
        "code": err.code,
        "problem": err.problem,
        "cause": err.cause,
        "fix": err.fix,
        "detail": err.detail,
    }


def request_validation_error_response(err: RequestValidationError) -> dict[str, Any]:
    """将 Pydantic 请求校验错误转换为统一结构的 JSON 响应体。

    作用:
        请求格式/类型校验失败（FastAPI 默认结构）也纳入统一三要素结构，
        满足「所有 API 错误响应遵循统一结构」约束。
    参数:
        err: FastAPI 抛出的 RequestValidationError（含字段级错误列表）。
    返回值:
        dict — 统一结构，cause 中携带字段级错误摘要（限长防膨胀）。
    异常:
        无。
    依赖:
        fastapi.exceptions.RequestValidationError、validation_errors_brief。
    """
    brief = validation_errors_brief(err)
    errors = "; ".join(
        f"{'.'.join(str(loc) for loc in e.get('loc', []))}: {e.get('msg', '')}" for e in brief
    )
    return {
        "code": "VALIDATION_ERROR",
        "problem": "请求参数校验失败",
        "cause": errors or "请求体不符合接口约定的格式与类型",
        "fix": "按 OpenAPI 文档（/docs）修正对应字段后重试",
        "detail": {"errors": brief},
    }
