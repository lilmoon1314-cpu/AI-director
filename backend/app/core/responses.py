"""统一错误响应构造：code / problem / cause / fix / detail。"""

from typing import Any

from fastapi.exceptions import RequestValidationError

from app.core.exceptions import AppError


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
        fastapi.exceptions.RequestValidationError。
    """
    errors = "; ".join(
        f"{'.'.join(str(loc) for loc in e.get('loc', []))}: {e.get('msg', '')}"
        for e in err.errors()[:10]
    )
    return {
        "code": "VALIDATION_ERROR",
        "problem": "请求参数校验失败",
        "cause": errors or "请求体不符合接口约定的格式与类型",
        "fix": "按 OpenAPI 文档（/docs）修正对应字段后重试",
        "detail": {"errors": err.errors()[:10]},
    }
