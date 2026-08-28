"""标准化开发命令面板（跨平台 make 等价物）。

作用:
    Windows 环境通常没有 make 工具，本脚本用纯 Python 标准库实现 Makefile 的
    全部命令契约（INIT.md），命令名与行为与 Makefile 一一对应：
    有 make 的机器走 Makefile（内部同样委托本脚本），没有的直接
    `python scripts/task.py <命令>`。

用法:
    python scripts/task.py setup      # 安装前后端依赖 + 生成 .env + 数据库迁移
    python scripts/task.py dev        # 同时启动前后端开发服务器
    python scripts/task.py test       # 运行全部层级测试
    python scripts/task.py check      # 完整验证（lint + 类型 + 测试 + 构建）
    python scripts/task.py help       # 查看全部命令
"""

import shutil
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

# 项目根目录（scripts/ 的上一级）；所有子命令以此为锚点定位前后端
ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

# 命令面板（name -> 描述），help 与 --activate 校验共用
COMMANDS: dict[str, str] = {
    "setup": "初始化：安装前后端依赖 + 生成 .env + 数据库迁移",
    "dev": "同时启动前后端开发服务器（后端 :8000/docs，前端 :5173）",
    "dev-backend": "仅启动后端 http://localhost:8000（API 文档: /docs）",
    "dev-frontend": "仅启动前端 http://localhost:5173",
    "test": "运行全部层级测试（后端 + 前端）",
    "test-unit": "L1 单元测试（每功能必须通过）",
    "test-integration": "L2 集成测试（每功能必须通过）",
    "test-e2e": "L3 端到端测试（跨组件功能必须通过）",
    "test-backend": "后端全部测试（pytest）",
    "test-frontend": "前端全部测试（vitest）",
    "check": "完整验证：后端 ruff/format/import-linter/mypy/pytest + 前端 typecheck/lint/build",
    "backend-check": "仅后端验证",
    "frontend-check": "仅前端验证",
    "check-api-types": "前端 API 类型与后端 OpenAPI schema 同步检查（F05 起）",
    "verify": "功能项验证并自动更新清单状态：verify F01（见 scripts/verify_feature.py）",
    "mutate": "定向变异测试（docs/testing.md §9）：mutate <module> [test_path...]，如 mutate perspectives",
    "clean": "清理构建产物与缓存",
    "help": "显示本帮助",
}


def _resolve_executable(name: str) -> list[str]:
    """解析命令名为可直接启动的形式（Windows 兼容层）。

    作用:
        pnpm 等工具在 Windows 上是 .cmd 批处理脚本，CreateProcess 无法直接启动；
        用 shutil.which（识别 PATHEXT）定位真实路径，.cmd/.bat 则经 cmd /c 包装。
    参数:
        name — 命令名（如 pnpm / uv / python）。
    返回值:
        可执行前缀（[路径] 或 [cmd, /c, 路径]）。
    异常:
        命令不存在时经 _fail 终止（附三要素）。
    依赖: shutil / sys。
    """
    path = shutil.which(name)
    if path is None:
        _fail(
            f"未找到可执行程序: {name}",
            "系统 PATH 中不存在该命令（工具未安装或未加入 PATH）",
            "安装对应工具后重开终端，或确认 PATH 环境变量配置",
        )
    if sys.platform == "win32" and path.lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", path]
    return [path]


def _run(cmd: list[str], cwd: Path) -> None:
    """在指定目录执行一条命令，失败即终止面板并输出三要素错误。

    作用:
        所有子命令的唯一执行出口；实时透传 stdout/stderr（不做缓冲）；
        自动经 _resolve_executable 处理 Windows 的 .cmd 工具（如 pnpm）。
    参数:
        cmd — 命令及其参数（list 形式，不经 shell，跨平台无引号差异）。
        cwd — 工作目录（backend / frontend / 根目录）。
    返回值: 无（失败抛 SystemExit）。
    异常:
        SystemExit — 命令返回非 0 退出码时（附三要素错误消息）。
    依赖: subprocess / _resolve_executable。
    """
    resolved = _resolve_executable(cmd[0])
    print(f"\n==> {' '.join(cmd)}   [cwd: {cwd.relative_to(ROOT) or '.'}]")
    result = subprocess.run([*resolved, *cmd[1:]], cwd=cwd)
    if result.returncode != 0:
        _fail(
            f"命令失败（退出码 {result.returncode}）: {' '.join(cmd)}",
            f"该步骤在 {cwd.relative_to(ROOT) or '.'} 下执行未通过，详见上方命令的原始输出",
            "按上方输出定位首个 ERROR/FAIL 行，修复后重新执行本命令",
        )


def _fail(problem: str, cause: str, fix: str) -> NoReturn:
    """输出三要素错误消息并终止。

    作用:
        统一错误出口，保证【问题/原因/修复】三要素完整（docs/lessons.md 规范）。
    参数:
        problem — 什么出了问题；cause — 为什么；fix — 怎么修。
    返回值: 无（总是 SystemExit(1)）。
    异常: SystemExit。
    依赖: 无。
    """
    print(f"\n[问题] {problem}\n[原因] {cause}\n[修复] {fix}", file=sys.stderr)
    sys.exit(1)


def _backend(*args: str) -> None:
    """在后端目录执行命令（便捷封装）。参数: args — 命令片段。返回值: 无。异常: 同 _run。依赖: _run。"""
    _run(["uv", "run", *args], BACKEND)


def _frontend(*args: str) -> None:
    """在前端目录执行命令（便捷封装）。参数: args — 命令片段。返回值: 无。异常: 同 _run。依赖: _run。"""
    _run(["pnpm", *args], FRONTEND)


# ---------------------------------------------------------------- 子命令实现


def cmd_setup() -> None:
    """初始化：安装前后端依赖 + 生成 .env + 数据库迁移。

    作用:
        对应 INIT.md 初始化契约第 1 条「可运行的环境」；幂等，可重复执行。
    参数: 无。返回值: 无。异常: 命令失败时经 _fail 终止。依赖: uv / pnpm / alembic。
    """
    _run(["uv", "sync"], BACKEND)
    env_file = BACKEND / ".env"
    if not env_file.exists():
        example = BACKEND / ".env.example"
        if not example.exists():
            _fail(
                "缺少 backend/.env.example",
                "环境变量模板文件不存在，无法生成 .env",
                "从版本库恢复 backend/.env.example 后重试",
            )
        env_file.write_bytes(example.read_bytes())
        print(f"==> 已生成 {env_file.relative_to(ROOT)}（如需自定义密钥请编辑该文件）")
    _backend("alembic", "upgrade", "head")
    _frontend("install")
    print("\n初始化完成：后端 http://localhost:8000/docs，前端 http://localhost:5173（make dev 启动）")


def cmd_dev() -> None:
    """同时启动前后端开发服务器（并行，任一退出则双双终止）。

    作用:
        对应 INIT.md 契约「启动开发服务器」；Ctrl+C 一次性停止两端。
    参数: 无。返回值: 无。异常: 无（进程信号由用户控制）。依赖: subprocess.Popen。
    """
    procs = [
        subprocess.Popen(["uv", "run", "uvicorn", "app.main:app", "--reload"], cwd=BACKEND),
        subprocess.Popen(["pnpm", "dev"], cwd=FRONTEND),
    ]
    print("后端 http://localhost:8000/docs | 前端 http://localhost:5173（Ctrl+C 停止全部）")
    try:
        procs[0].wait()
    except KeyboardInterrupt:
        pass
    finally:
        for proc in procs:
            proc.terminate()


def cmd_test_unit() -> None:
    """L1 单元测试（后端 -m unit；前端 test:unit 不存在时跳过）。

    作用: 验证层级 L1（docs/testing.md），每功能必须通过。
    参数: 无。返回值: 无。异常: 命令失败时经 _fail 终止。依赖: pytest / vitest。
    """
    _backend("pytest", "-m", "unit")
    _frontend("run", "--if-present", "test:unit")


def cmd_test_integration() -> None:
    """L2 集成测试（后端 -m integration；前端 test:integration 随 F05 引入）。

    作用: 验证层级 L2（docs/testing.md），每功能必须通过。
    参数: 无。返回值: 无。异常: 命令失败时经 _fail 终止。依赖: pytest / vitest。
    """
    _backend("pytest", "-m", "integration")
    _frontend("run", "--if-present", "test:integration")


def cmd_test_e2e() -> None:
    """L3 端到端测试（后端 -m e2e；前端 Playwright 随 F05 引入）。

    作用: 验证层级 L3（docs/testing.md），跨组件功能必须通过。
    参数: 无。返回值: 无。异常: 命令失败时经 _fail 终止。依赖: pytest。
    """
    _backend("pytest", "-m", "e2e")


def cmd_check() -> None:
    """完整验证：后端（ruff + format + import-linter + mypy + pytest）与前端（typecheck + lint + build）。

    作用:
        对应 INIT.md 契约「完整验证」，即功能完成判定 DoD 的机器部分（docs/testing.md §2）。
    参数: 无。返回值: 无。异常: 命令失败时经 _fail 终止。依赖: cmd_backend_check / cmd_frontend_check。
    """
    cmd_backend_check()
    cmd_frontend_check()


def cmd_backend_check() -> None:
    """仅后端验证：ruff check → ruff format --check → lint-imports → mypy → pytest。

    作用: 后端质量门禁（静态检查 + 类型 + 架构契约 + 全量测试）。
    参数: 无。返回值: 无。异常: 命令失败时经 _fail 终止。依赖: ruff / mypy / import-linter / pytest。
    """
    _backend("ruff", "check", ".")
    _backend("ruff", "format", "--check", ".")
    _backend("lint-imports")
    _backend("mypy", "app")
    _backend("pytest")


def cmd_frontend_check() -> None:
    """仅前端验证：typecheck → lint → build。

    作用: 前端质量门禁（类型 + 规范 + 生产构建）。
    参数: 无。返回值: 无。异常: 命令失败时经 _fail 终止。依赖: tsc / eslint / vite。
    """
    _frontend("typecheck")
    _frontend("lint")
    _frontend("build")


def cmd_check_api_types() -> None:
    """前端 API 类型同步检查（openapi-typescript 生成 + git diff 校验，F05 起启用）。

    作用:
        保证前端 API 类型与后端 OpenAPI schema 一致（frontend/CONSTRAINTS.md「API 契约」）。
    参数: 无。返回值: 无。异常: F05 前因 gen:api-types 脚本缺失而失败（预期行为）。依赖: pnpm / git。
    """
    _frontend("run", "gen:api-types")
    _run(["git", "diff", "--exit-code", "--", "src/api/"], FRONTEND)


def cmd_clean() -> None:
    """清理构建产物（frontend/dist）。

    作用: 释放本地构建垃圾；不动依赖与数据库（危险操作需手动执行）。
    参数: 无。返回值: 无。异常: 无。依赖: shutil。
    """
    import shutil

    dist = FRONTEND / "dist"
    if dist.exists():
        shutil.rmtree(dist)
        print("已清理 frontend/dist")


def cmd_mutate(module: str, *test_paths: str) -> None:
    """定向变异测试（docs/testing.md §9）：仅对指定模块运行 mutmut。

    作用:
        变异测试封装——mutmut 只变异 backend/app/<module>/ 下源码，以
        「判杀测试命令」的退出码判定变异体存活；结束时打印结果汇总，
        kill rate ≥ 85% 才算达标（存活变异体逐一分析后归档测试文档）。
        不纳入 make check 常规链（成本控制，按功能点手动触发）。
    参数:
        module — 模块名（app/ 下的目录名，如 perspectives）；
        test_paths — 判杀测试路径（可选，默认 tests/unit/test_<module>_service.py，
        该文件不存在时必须显式指定）。
    返回值: 无。异常: 模块不存在、缺判杀器、或模块含 router.py 而判杀器缺
        L2 集成测试时经 _fail 终止（docs/testing.md §9 判杀器构成）。依赖: mutmut / pytest。
    """
    if not (BACKEND / "app" / module).is_dir():
        _fail(
            f"未知模块: {module}",
            f"backend/app/{module} 目录不存在",
            "用法: python scripts/task.py mutate <module>（app/ 下的模块名，如 perspectives）",
        )
    default_test = BACKEND / "tests" / "unit" / f"test_{module}_service.py"
    tests = list(test_paths) or (
        [f"tests/unit/test_{module}_service.py"] if default_test.exists() else []
    )
    if not tests:
        _fail(
            f"模块 {module} 缺少默认判杀测试",
            f"backend/tests/unit/test_{module}_service.py 不存在",
            "显式传入判杀测试路径: python scripts/task.py mutate <module> <test_path...>",
        )
    if (BACKEND / "app" / module / "router.py").is_file() and not any(
        p.replace("\\", "/").startswith("tests/integration/") for p in tests
    ):
        _fail(
            f"模块 {module} 含 router.py 但判杀器缺少 L2 集成测试（docs/testing.md §9 判杀器构成）",
            "路由注册（prefix/path/装饰器）与参数校验类变异不改变 service 运行时行为，"
            "仅 L1 单元判杀会在 HTTP 语义层留下漏杀盲区（F04 首轮 kill rate 仅 47%）",
            "判杀器追加该功能集成测试路径，如: python scripts/task.py mutate <module> "
            "tests/unit/test_<module>_service.py tests/integration/test_<feature>.py",
        )
    runner = f"python -m pytest -x -q {' '.join(tests)}"
    _backend(
        "mutmut",
        "run",
        f"--paths-to-mutate=app/{module}/",
        f"--runner={runner}",
        "--tests-dir=tests/",
    )
    _backend("mutmut", "results")


# ---------------------------------------------------------------- 命令分派

# 分派表：命令名 -> 实现函数（help 文案见 COMMANDS；简单转发命令用 lambda 直连）
DISPATCH: dict[str, object] = {
    "setup": cmd_setup,
    "dev": cmd_dev,
    "dev-backend": lambda: _backend("uvicorn", "app.main:app", "--reload"),
    "dev-frontend": lambda: _frontend("dev"),
    "test": lambda: (_run(["uv", "run", "pytest"], BACKEND), _frontend("test")),
    "test-unit": cmd_test_unit,
    "test-integration": cmd_test_integration,
    "test-e2e": cmd_test_e2e,
    "test-backend": lambda: _backend("pytest"),
    "test-frontend": lambda: _frontend("test"),
    "check": cmd_check,
    "backend-check": cmd_backend_check,
    "frontend-check": cmd_frontend_check,
    "check-api-types": cmd_check_api_types,
    "clean": cmd_clean,
    "help": lambda: print_help(),
}


def print_help() -> None:
    """打印命令面板帮助（命令名 + 一句话说明）。

    作用: `python scripts/task.py help` / 无参数时的输出，与 Makefile help 对齐。
    参数: 无。返回值: 无。异常: 无。依赖: COMMANDS。
    """
    print("用法: python scripts/task.py <命令>   （Makefile 同名 target 委托至此）\n")
    for name, desc in COMMANDS.items():
        print(f"  {name:<18} {desc}")


def main(argv: list[str]) -> None:
    """命令入口：解析参数并分派到对应实现。

    作用:
        支持 `python scripts/task.py <cmd>` 与 `verify` 转发（调 verify_feature.py）。
    参数:
        argv — 命令行参数（argv[0] 为命令名，其余为该命令参数）。
    返回值: 无。
    异常:
        未知命令时打印帮助并以退出码 1 终止。
    依赖: DISPATCH / subprocess。
    """
    if not argv or argv[0] in ("help", "-h", "--help"):
        print_help()
        return
    name = argv[0]
    if name == "verify":
        if len(argv) < 2:
            _fail(
                "verify 命令缺少功能项 ID",
                "未在命令行传入要验证的功能项（如 F01）",
                "用法: python scripts/task.py verify F01",
            )
        # 转发到功能验证脚本（独立文件，职责单一）
        _run([sys.executable, str(ROOT / "scripts" / "verify_feature.py"), *argv[1:]], ROOT)
        return
    if name == "mutate":
        if len(argv) < 2:
            _fail(
                "mutate 命令缺少模块名",
                "未在命令行传入要变异的模块",
                "用法: python scripts/task.py mutate <module> [test_path...]",
            )
        cmd_mutate(*argv[1:])
        return
    handler = DISPATCH.get(name)
    if handler is None:
        print(
            f"[问题] 未知命令: {name}\n"
            "[原因] 命令面板（scripts/task.py）中没有该命令\n"
            "[修复] 执行 python scripts/task.py help 查看全部可用命令",
            file=sys.stderr,
        )
        sys.exit(1)
    handler()  # type: ignore[operator]


if __name__ == "__main__":
    main(sys.argv[1:])
