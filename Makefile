# 影视多智能体协作平台 — 标准化开发命令入口
# 初始化契约见 docs/INIT.md；测试层级见 docs/testing.md
# 实现说明：全部命令委托 scripts/task.py（Windows 无 make 时直接 `python scripts/task.py <命令>`）

PYTHON ?= python

.PHONY: setup dev dev-backend dev-frontend test test-unit test-integration test-e2e \
        test-backend test-frontend check check-api-types backend-check frontend-check \
        verify clean help

## setup: 初始化（安装前后端依赖 + 生成 .env + 数据库迁移）
setup:
	$(PYTHON) scripts/task.py setup

## dev: 同时启动前后端开发服务器（后端 :8000 /docs，前端 :5173）
dev:
	$(PYTHON) scripts/task.py dev

## dev-backend: 仅启动后端 http://localhost:8000（API 文档: /docs）
dev-backend:
	$(PYTHON) scripts/task.py dev-backend

## dev-frontend: 仅启动前端 http://localhost:5173
dev-frontend:
	$(PYTHON) scripts/task.py dev-frontend

## test: 运行全部层级测试（后端 unit+integration+e2e+architecture / 前端全部）
test:
	$(PYTHON) scripts/task.py test

## test-unit: L1 单元测试（每功能必须通过）
test-unit:
	$(PYTHON) scripts/task.py test-unit

## test-integration: L2 集成测试（每功能必须通过）
test-integration:
	$(PYTHON) scripts/task.py test-integration

## test-e2e: L3 端到端测试（跨组件功能必须通过；前端 Playwright 随 F05 引入）
test-e2e:
	$(PYTHON) scripts/task.py test-e2e

test-backend:
	$(PYTHON) scripts/task.py test-backend

test-frontend:
	$(PYTHON) scripts/task.py test-frontend

## check: 完整验证（后端 ruff+format+import-linter+mypy+pytest / 前端 typecheck+lint+build）
check:
	$(PYTHON) scripts/task.py check

## check-api-types: 前端 API 类型与后端 OpenAPI schema 同步检查（F05 起）
check-api-types:
	$(PYTHON) scripts/task.py check-api-types

## verify: 功能项验证并自动更新清单状态（如 make verify F01）
verify:
	$(PYTHON) scripts/task.py verify $(filter-out $@,$(MAKECMDGOALS))

backend-check:
	$(PYTHON) scripts/task.py backend-check

frontend-check:
	$(PYTHON) scripts/task.py frontend-check

## clean: 清理构建产物与缓存
clean:
	$(PYTHON) scripts/task.py clean

help:
	@$(PYTHON) scripts/task.py help
