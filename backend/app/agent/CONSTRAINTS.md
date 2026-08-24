# agent 模块硬约束

> 实现/修改 agent 模块前必读。

- 必须：写库两段式——propose 只产草案，confirm 经用户确认后才落库。
- 禁止：向 LLM 上下文注入当前视角不可见的实体/关系（必须先经 perspectives.service 过滤）。
- 必须：LLM 端点/密钥/模型/超时全部来自 config（LLM_*），禁止硬编码。
- 必须：LLM 调用设超时与错误处理；失败抛 AgentError（可读错误），禁止未捕获异常冒泡。
- 必须：会话历史上限与淘汰策略记录于本模块 ARCHITECTURE.md（上限值来自 config）。
- 禁止：草案 JSON 解析失败无限重试；最多 1 次修复重试后返回 ValidationError。
