"""统一错误响应构造：code / problem / cause / fix / detail。"""

from typing import Any

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
