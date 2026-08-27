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

## 2. 错误模式库

| ID | 日期 | 错误模式 | 什么问题 | 为什么 | 怎么修 | 自动化 |
|----|------|----------|----------|--------|--------|--------|
| E01 | 2026-08-24 | 文档虚登（把计划写成现状） | docs/testing.md §7 声称 conftest 已提供 RSS 回归守卫 fixture，实际 conftest.py 无此 fixture | 设计先行时未区分「已就位/计划」两种状态，读者误信机制存在而跳过落地 | 虚登处改为双态标注（已就位/计划 FXX）；守卫 fixture 随 F02 落地 | 审查清单（文档-代码一致性为语义级比对，暂无法自动化） |
| E02 | 2026-08-24 | 外部格式化改写清单文件致脚本失配 | IDE markdown 格式化器对 features.md 表格列对齐并把状态 `not_started` 转义为 `not\_started`，verify_feature.py 状态正则 `\w+` 无法匹配，verify F02+ 将报"未找到行" | 清单文件会被编辑器随手改写，脚本解析必须容错（转义与列宽变化） | 状态单元格匹配放宽为非空白非竖线字符、读取时剥离转义反斜杠 | 自动（回归测试 backend/tests/unit/test_verify_script.py） |
| E03 | 2026-08-24 | PowerShell 下 git commit -m 中文乱码 | Windows 中文系统 PowerShell 以 GBK 编码传递命令行参数，`git commit -m "中文"` 可能烤入乱码字节；且终端显示层 GBK 解码 UTF-8 也会出现"假乱码"，需用 UTF-8 控制台重定向验证才能区分 | 编码链路有三层（参数传递/存储/显示），任何一层用错编码都会损坏或误判 | 提交信息一律经临时文件 `git commit -F <file>`（Write 工具产出 UTF-8）；验证存储真实性用 `[Console]::OutputEncoding=UTF8` + 重定向 | 审查清单（提交流程无 lint 挂点；规避法即 -F 文件方式） |

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

日志独立维护（backend/logs/，gitignore，自动轮转）：

| 文件 | 内容 |
|------|------|
| app.jsonl | 运行事件（生命周期、请求、检查点） |
| error.jsonl | 错误专用：request_id + 参数摘要 + traceback + 三要素 |
| metrics.jsonl | 资源采样（RSS/CPU） |

排查入口：先查 error.jsonl（按 request_id 关联），再查 app.jsonl 还原路径，metrics.jsonl 看资源趋势。
