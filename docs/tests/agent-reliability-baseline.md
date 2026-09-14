# Agent 可靠性故障基线（A 切片）

本文件保留 A 阶段的原始故障证据，不代替产品验收状态。B 阶段修复四项上下文/限制
故障，C 阶段修复剩余两项写入故障；六项现均为普通通过回归，不再含 strict xfail。
下文“实际结果”及 20 passed / 6 xfailed 是 A 当时的历史结果。当前证据见
[B 分析报告](../reports/agent-improvement-slice-b-2026-09-13.md)和
[C 分析报告](../reports/agent-improvement-slice-c-2026-09-14.md)。

## 1. 场景、证据和修复归属

| A 计划场景 | 本次证据 | 实际结果与预期行为 | 后续归属 |
|---|---|---|---|
| author 秘密在同会话切 audience | 集成测试 `test_author_history_does_not_enter_audience_prompt` | 第二轮模型输入包含第一轮秘密；应按作用域隔离 | B |
| 8000 字符中文叠加工具 schema | `test_oversized_chinese_input_never_calls_provider` | 预算设为 100，8000 个中文字与实际工具契约仍发出 1 次请求；应为 0 次 | B |
| 单次响应返回超额调用 | `test_batch_executes_only_allowed_tool_count` | 额度 1，执行 3 次；应只执行 1 次并给未执行调用返回明确结果 | B |
| 超窗摘要失败 | `test_failed_summary_does_not_silently_hide_uncovered_requirement` | 摘要超时后旧约束不进入第三轮且无错误；应恢复原文或明确拒绝不完整上下文 | E（依赖 B/D） |
| read 与登记之间用户修改 | `test_user_edit_between_read_and_registration_cannot_be_overwritten` | 第二个真实数据库 session 保存新版后，旧内容生成的候选仍获批准并覆盖新版；应拒绝或保持用户新内容 | C |
| 业务提交后、批准状态提交前故障 | `test_failed_approval_persistence_does_not_leave_business_effect` | 在 save_pending 注入异常，批准返回失败但新实体已存在；应原子提交或完全不产生业务效果 | C |
| 刷新后 pending 回读 | 静态：`frontend/src/stores/agentStore.ts` 的 `loadMessages` 只调用 `api.listMessages`；后端已有 `list_pending_writes` | 缺少把持久 pending 恢复为确认卡的加载路径；应同时恢复消息和 pending | D |
| 切项目后旧流 finally 到达 | 静态：同文件 `sendMessage` 的 finally 无条件清空 `streamingSessionId`/`toolActivity`，无 generation/run 身份比较 | 旧请求有机会清空新流；应只有当前拥有者更新流状态 | D |

后两项为代码路径证据，尚未在浏览器或 store 测试中复现，不宣称已验证发生率。
批准故障测试是事务边界异常注入，不是杀进程实验；读后修改测试是受控交错，不是同时写压力测试。
C 另验证了数据库条件更新、重复 approve、approve/reject 单赢家语义、Skill 接受回滚和
stale Artifact revision 拒绝。真正断电/杀进程仍属于更高层恢复验证。

## 2. 内部契约验收

`backend/tests/unit/test_agent_contracts.py` 的 20 个用例覆盖：

- 作用域缺少角色、非角色携带角色、空项目和未知字段拒绝。
- 可变来源必须有读取版本，Artifact 来源必须有 revision。
- 跨项目/视角片段、强制约束被省略、输入加输出预留超预算拒绝；恰好等于预算允许。
- 工具失败必须带错误码，成功不能伪装重试，截断必须声明续取路径。
- 摘要来源顺序、重复来源、错误游标以及失败覆盖的拒绝。
- 运行事件序号、run 归属和终态不可反转。

这些测试证明元数据校验行为，不证明当前模型请求已有硬预算或当前数据库已有持久 Run。

## 3. 运行命令与实际结果

工作目录为 `backend`，使用项目已有虚拟环境，未安装依赖。2026-09-13 实际执行：

```powershell
.venv/Scripts/python.exe -m pytest tests/unit/test_agent_contracts.py tests/integration/test_agent_reliability_baseline.py -q -rx -p no:cacheprovider --tb=line
.venv/Scripts/python.exe -m ruff check app/agent/contracts.py tests/unit/test_agent_contracts.py tests/integration/test_agent_reliability_baseline.py --no-cache
.venv/Scripts/python.exe -m ruff format --check app/agent/contracts.py tests/unit/test_agent_contracts.py tests/integration/test_agent_reliability_baseline.py --no-cache
.venv/Scripts/python.exe -m mypy app/agent/contracts.py --follow-imports=silent
```

结果：**20 passed、6 xfailed；Ruff 检查/格式检查通过；mypy 1 个源文件通过。**
既有 Starlette/httpx 弃用警告 1 项，不在本任务范围。初次执行另遇 pytest 缓存目录写权限警告，
最终命令禁用该缓存，无需扩大权限。初次 Alembic heads 在仓库根目录执行因相对 migrations
路径失败；改在 backend 执行后读到唯一 head `f63c8db205a9`，未执行迁移。

故障建立时还运行了 `--runxfail`，确认六项实际落到目标缺陷断言。
其中读后修改测试初版夹具漏传 `updated_by` 导致普通失败，修正夹具后才复现目标覆盖故障。
不会把夹具错误算作产品缺陷。每个 xfail 仅接受专用 `UnmetAcceptance` 异常，
准备数据和请求状态的普通断言失败不会被隐藏；`strict=True` 使修好后必须移除旧标记。

## 4. 隔离与后续转换

测试复用 `tests/conftest.py` 的临时数据库、临时日志和资产目录，替换流式 provider 与摘要，
禁止创建真实模型客户端。不读取生产凭据、不访问真实模型、不修改用户项目数据。
未运行全仓测试、历史变异测试或基准测试，未更新 `feature_list.json`。

六项 xfail 已按 B/C 修复范围转为普通回归断言，并补有对应边界场景。
仅让本文件的六个用例通过仍不代表 A–H 整体计划验收完成；D–H 的恢复、摘要、长期记忆、
受控 Skill 协作和检索成本要求继续按各自阶段验收。
