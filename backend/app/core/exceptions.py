"""统一异常层级：三要素（problem / cause / fix）构造必填。

规范出处: docs/lessons.md §3 — 面向 Agent 的错误消息三要素。
所有业务异常必须继承 AppError，保证错误消息自解释。
"""

from typing import Any


class AppError(Exception):
    """应用错误基类。

    作用:
        所有业务异常的统一出口。构造时强制填写三要素，实例化即保证
        错误消息包含"什么出了问题 / 为什么 / 怎么修"。
    参数:
        problem: 什么出了问题（现象描述）。
        cause: 为什么会出问题（根因）。
        fix: 怎么修（可执行动作）。
        detail: 结构化补充信息（默认 None，规范化为 {}）。
    返回值:
        无（异常类）。
    异常:
        本类即异常；由业务代码 raise，不在内部抛出。
    依赖:
        无（仅标准库）。
    """

    code: str = "APP_ERROR"
    http_status: int = 500

    def __init__(
        self,
        problem: str,
        cause: str,
        fix: str,
        *,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(problem)
        self.problem = problem
        self.cause = cause
        self.fix = fix
        self.detail: dict[str, Any] = detail or {}


class NotFoundError(AppError):
    """404 资源不存在（参数与用法同基类 AppError）。"""

    code = "NOT_FOUND"
    http_status = 404


class ValidationError(AppError):
    """422 业务校验失败（区别于 Pydantic 请求格式校验；参数同基类）。"""

    code = "VALIDATION_ERROR"
    http_status = 422


class ConflictError(AppError):
    """409 冲突：唯一约束、导入冲突等（参数同基类）。"""

    code = "CONFLICT"
    http_status = 409


class ReferentialError(AppError):
    """409 删除了被其他数据引用的资源（参数同基类）。"""

    code = "REFERENTIAL_INTEGRITY"
    http_status = 409


class PerspectiveError(AppError):
    """403 视角违规：访问当前视角不可见的资源（参数同基类）。"""

    code = "PERSPECTIVE_DENIED"
    http_status = 403


class AgentError(AppError):
    """502 LLM 调用失败 / 超时（参数同基类）。"""

    code = "AGENT_FAILURE"
    http_status = 502
