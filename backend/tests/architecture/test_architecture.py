"""架构约束可执行检查（基线，F01）。

映射: docs/architecture_checks.md §2 —
    - core 纯净性（core 禁止 import 领域模块）
    - 禁止业务代码散点日志（logging 仅 core.observability 允许使用）
"""

import ast
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[2] / "app"
CORE_DIR = APP_DIR / "core"

# core 禁止依赖的领域模块前缀（CONSTRAINTS: core 保持零业务知识）
FORBIDDEN_IN_CORE = (
    "app.entities",
    "app.relations",
    "app.perspectives",
    "app.assets",
    "app.sync",
    "app.agent",
)

pytestmark = pytest.mark.architecture


def _imported_modules(source: str) -> set[str]:
    """解析源码中全部 import 的完整模块名。

    作用: 为架构检查提供 AST 级 import 事实（不执行代码）。
    参数: source — Python 源码文本。返回值: set[str]。异常: SyntaxError（源码非法）。
    依赖: ast。
    """
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            modules.add(node.module)
    return modules


def _python_files(directory: Path) -> list[Path]:
    """列出目录下全部 .py 文件（含子目录）。"""
    return sorted(directory.rglob("*.py"))


def test_core_purity() -> None:
    """core 不得 import 任何领域模块（架构约束: core 保持零业务知识）。

    失败含义:
        【问题】core 引用了领域模块，违反最底层纯净性约束
        【原因】core 是基础设施层，反向依赖业务模块会形成循环依赖
        【修复】把依赖倒过来：由领域模块调用 core 的 service/工具函数
    """
    violations: list[str] = []
    for file in _python_files(CORE_DIR):
        modules = _imported_modules(file.read_text(encoding="utf-8"))
        for module in modules:
            if any(
                module == prefix or module.startswith(prefix + ".") for prefix in FORBIDDEN_IN_CORE
            ):
                violations.append(f"{file.relative_to(APP_DIR)} -> {module}")
    assert not violations, (
        f"【问题】core 出现领域模块依赖: {violations}\n"
        "【原因】core 为最底层基础设施，禁止依赖任何业务模块（循环依赖风险）\n"
        "【修复】将调用方向反转：领域模块 import core，而非 core import 领域模块"
    )


def test_no_scattered_logging_outside_core() -> None:
    """业务代码禁止直接 import logging（散点日志约束，仅 core 允许）。

    失败含义:
        【问题】core 之外的模块直接使用了 logging
        【原因】五类信号由 core.observability 统一自动采集，散点日志会造成格式漂移与遗漏
        【修复】删除手写日志；关键路径用 @checkpoint 声明式标注（app.core.observability）
    """
    violations: list[str] = []
    for file in _python_files(APP_DIR):
        if file.is_relative_to(CORE_DIR):
            continue  # core（observability）是唯一允许使用 logging 的地方
        modules = _imported_modules(file.read_text(encoding="utf-8"))
        if "logging" in modules:
            violations.append(str(file.relative_to(APP_DIR)))
    assert not violations, (
        f"【问题】以下模块直接 import logging: {violations}\n"
        "【原因】信号采集统一由 core.observability 自动完成，散点日志违反约束且格式不一致\n"
        "【修复】移除 logging 调用；需要检查点时使用 @checkpoint 装饰器（app.core.observability）"
    )
