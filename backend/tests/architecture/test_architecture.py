"""架构约束可执行检查。

映射: docs/architecture_checks.md §2 —
    - core 纯净性（core 禁止 import 领域模块）                    [F01]
    - 禁止业务代码散点日志（logging 仅 core.observability 允许）   [F01]
    - router 不碰数据层（router.py 禁止 import repository/models）[F02]
    - 配置禁止硬编码（扫描源码端口/URL/密钥样式字面量）           [F02]
    - relationships 外键 DDL 声明 ON DELETE RESTRICT             [F02]
"""

import ast
import re
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[2] / "app"
CORE_DIR = APP_DIR / "core"
MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations" / "versions"

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
    """解析源码中全部 import 的完整模块名（含相对导入的近似表示）。

    作用: 为架构检查提供 AST 级 import 事实（不执行代码）；相对导入按
        `相对层级:<模块名>` 记录，供 router 数据层检查区分自模块内层引用。
    参数: source — Python 源码文本。返回值: set[str]。异常: SyntaxError（源码非法）。
    依赖: ast。
    """
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = "" if node.module is None else node.module
            suffix = f".{prefix}" if node.level > 0 else ""
            modules.add(f"{node.level}:{suffix}{prefix}" if node.level else node.module or "")
    return {m for m in modules if m}


def _python_files(directory: Path) -> list[Path]:
    """列出目录下全部 .py 文件（含子目录）。"""
    return sorted(directory.rglob("*.py"))


def _string_constants(source: str) -> list[str]:
    """提取源码中全部字符串常量（排除模块/类/函数 docstring）。

    作用: 为硬编码扫描提供准确的字面量集合——文档字符串中的示例 URL 属于
        说明性内容而非配置，必须豁免。
    参数: source — Python 源码文本。
    返回值: list[str]。异常: SyntaxError（源码非法）。
    依赖: ast。
    """
    tree = ast.parse(source)
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                docstrings.add(id(body[0].value))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


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


def test_router_does_not_import_data_layer() -> None:
    """router.py 禁止 import repository/models（架构约束: 路由层不含数据访问）。

    失败含义:
        【问题】router 层出现数据层依赖
        【原因】路由直接访问 repository/models 会绕过 service 层的校验与事务边界
        【修复】把数据访问移到 service 层，router 只做参数解析与响应包装
    """
    violations: list[str] = []
    for file in _python_files(APP_DIR):
        if file.name != "router.py":
            continue
        modules = _imported_modules(file.read_text(encoding="utf-8"))
        for module in modules:
            # 相对导入记录形如 "1:.repository"，冒号归一为点后按段精确匹配
            parts = module.replace(":", ".").split(".")
            if "repository" in parts or "models" in parts:
                violations.append(f"{file.relative_to(APP_DIR)} -> {module}")
    assert not violations, (
        f"【问题】router 层出现数据层依赖: {violations}\n"
        "【原因】路由直接 import repository/models 绕过 service 层（校验/事务边界失效）\n"
        "【修复】数据访问移入 service 层，router 仅做参数解析与响应包装"
    )


# 硬编码配置的字面量样式（启发式；白名单 config.py——默认值即配置契约）
_HARDCODED_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^https?://"), "URL 字面量"),
    (re.compile(r"^www\."), "URL 字面量"),
    (re.compile(r"localhost:\d+"), "主机端口"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"), "IP 地址"),
    (re.compile(r"(?i)\bsk-[a-z0-9]{8,}\b"), "密钥样式字面量"),
)


def test_no_hardcoded_config_literals() -> None:
    """业务源码禁止端口/URL/密钥样式字面量（配置一律经 config.py 从环境读取）。

    失败含义:
        【问题】源码出现硬编码配置样式字面量
        【原因】绕过 config.py 的配置无法经 .env 覆盖，密钥类字面量还有泄露风险
        【修复】把字面量移入 config.py 配置项（环境变量/.env 读取后引用）
    """
    violations: list[str] = []
    for file in _python_files(APP_DIR):
        if file.name == "config.py":
            continue
        for constant in _string_constants(file.read_text(encoding="utf-8")):
            for pattern, label in _HARDCODED_PATTERNS:
                if pattern.search(constant):
                    violations.append(f"{file.relative_to(APP_DIR)}: {label} {constant[:60]!r}")
    assert not violations, (
        f"【问题】源码出现硬编码配置样式字面量: {violations}\n"
        "【原因】配置未集中到 config.py，环境切换与密钥管理失效\n"
        "【修复】把字面量改为 config.py 配置项（环境变量/.env 读取）后引用"
    )


def test_relationships_fk_declared_on_delete_restrict() -> None:
    """relationships.source/target 外键必须声明 ON DELETE RESTRICT（幽灵节点 DB 层兜底）。

    失败含义:
        【问题】relationships 外键缺失或删除策略不是 RESTRICT
        【原因】缺失 FK/RESTRICT 时旁路写入可产生悬空引用（幽灵节点）
        【修复】在 app/relations/models.py 为 source/target 声明
            ForeignKey("entities.id", ondelete="RESTRICT") 并生成 Alembic 迁移
    """
    from app.relations.models import Relationship

    ondelete = {fk.parent.name: fk.ondelete for fk in Relationship.__table__.foreign_keys}
    assert ondelete.get("source") == "RESTRICT" and ondelete.get("target") == "RESTRICT", (
        f"【问题】relationships 外键声明不符: {ondelete}\n"
        "【原因】ORM 模型 FK 缺失或未声明 ondelete=RESTRICT（DB 层兜底失效）\n"
        "【修复】source/target 改为 ForeignKey('entities.id', ondelete='RESTRICT') 并迁移"
    )

    migration_sql = "\n".join(
        f.read_text(encoding="utf-8") for f in sorted(MIGRATIONS_DIR.glob("*.py"))
    )
    assert "RESTRICT" in migration_sql, (
        "【问题】迁移文件未包含 RESTRICT 外键策略\n"
        "【原因】ORM 声明与迁移 DDL 脱节（库表实际缺少约束）\n"
        "【修复】重新生成 Alembic 迁移使 DDL 与 ORM 模型一致"
    )
