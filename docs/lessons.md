# docs/lessons.md — 审查反馈提升流程与错误模式库

> 目标：每次发现新类型的 agent 错误，都沉淀为自动化检查，让同一类错误只发生一次。
> 代码审查或发现新错误类型时必读必更。

## 1. 提升流程（发现新类型错误时执行）

```
发现错误（代码审查 / 测试失败 / logs/error.jsonl）
   │
   ├─ 已知类型 → 引用既有条目修复，结束
   │
   └─ 新类型 → ①登记错误模式库（三要素）
                ②转化评估：能否自动化？
                    ├─ 能 → 添加 lint 规则 / 架构测试 / 回归测试
                    │        并更新 docs/architecture_checks.md 映射表
                    └─ 暂不能 → 加入审查清单（注明原因）
                ③复跑触发场景，确认检查生效
```

规则：新类型错误必须在当次会话内完成登记与转化评估，禁止"下次再说"。

## 2. 错误模式库（backend/logs/error.jsonl）

> 库已迁移为 JSONL 格式，唯一事实源：`backend/logs/error.jsonl`（入版本库；app/metrics 等运行日志仍 gitignore，见 §4）。

### 2.1 记录格式（JSONL，每行一条，UTF-8）

错误模式条目（`type: "error_pattern"`）：

```json
{"type": "error_pattern", "id": "E04", "date": "YYYY-MM-DD", "pattern": "错误模式名",
 "problem": "什么出了问题", "cause": "为什么", "fix": "怎么修",
 "automation": "自动（检查名）/ 审查清单（原因）"}
```

测试失败记录条目（`type: "test_failure"`，每次测试不通过时追加）：

```json
{"type": "test_failure", "id": "T-YYYYMMDD-NN", "date": "YYYY-MM-DD", "feature": "FXX",
 "command": "触发的验证命令", "problem": "现象（含关键报错输出摘要）",
 "cause": "根因分析", "fix": "修复动作",
 "disposition": "resolved-known / promoted-E04 / resolved-unique"}
```

### 2.2 记录与归档规则

- **每次测试不通过必须当场记录**一条 `test_failure`（三要素齐全，禁止事后补记或漏记）。
- 修复后按 §1 提升流程归档：
    - 命中既有错误模式 → `disposition: "resolved-known"`，`cause` 中注明引用的 `EXX`；
    - 属于新类型错误 → 先按 2.1 追加 `error_pattern` 条目（递增 ID），测试失败记录写 `disposition: "promoted-E0X"`，并完成自动化转化评估；
    - 一次性失误无沉淀价值 → `disposition: "resolved-unique"`。
- `error_pattern` 条目一经登记不可删除，只可追加；`test_failure` 条目保留原始记录，不覆写。

## 3. 面向 Agent 的错误消息三要素（规范）

所有错误消息（异常、lint 输出、测试失败、命令报错）必须包含：

1. **什么出了问题**（现象）
2. **为什么**（根因）
3. **怎么修**（可执行动作）

示例：

```
错误: pytest tests/unit/test_entities_service.py 失败 — fixture 'db_session' 未定义
原因: 该文件未复用 tests/conftest.py 的共享 fixture（conftest 尚未定义 db_session）
修复: 在 backend/tests/conftest.py 中添加 db_session fixture，或在本文件内局部定义
```

后端落地：`AppError(problem, cause, fix)` 三字段构造必填，由 core/exceptions.py 保证（见 backend/ARCHITECTURE.md §4）。

## 4. 信号采集与日志维护

五类信号由 core observability 统一自动采集（设计见 backend/app/core/ARCHITECTURE.md「可观测性」）：
生命周期 / 功能路径 / 数据流 / 资源利用 / 错误上下文。

日志独立维护（backend/logs/，运行日志 gitignore + 自动轮转；错误模式库 error.jsonl 例外，入版本库且不轮转）：

| 文件 | 入版本库 | 内容 |
|------|----------|------|
| app.jsonl | 否 | 运行事件（生命周期、请求、检查点） |
| runtime_error.jsonl | 否 | 运行时错误：request_id + 参数摘要 + traceback + 三要素 |
| metrics.jsonl | 否 | 资源采样（RSS/CPU） |
| error.jsonl | **是** | 错误模式库 + 测试失败记录（§2，agent 维护，非运行时写入） |

排查入口：先查 runtime_error.jsonl（按 request_id 关联），再查 app.jsonl 还原路径，metrics.jsonl 看资源趋势；错误模式复盘查 error.jsonl。
