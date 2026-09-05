# 功能清单（第 1 批 MVP）

> 状态机：`not_started` → `active` → `passing` / `blocked`。
> 规则：同时只激活一个功能项；状态由验证脚本自动更新，禁止手工修改（AGENTS.md 功能清单规则）。
> 验证层级（docs/testing.md）：L1 单元 + L2 集成每功能必须；L3 E2E 仅"跨组件"功能必须。跳过任何必须层级 = 未完成。
> 每个功能实现时创建 `docs/tests/FXX_<name>.md` 测试文档，DoD 见 docs/testing.md §2。

| ID  | 功能            | 行为描述                                                                                                                            | 跨组件                                      | 验证命令（必须层级）                                                                                                   | 状态           |
| --- | ------------- | ------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ------------ |
| F01 | 项目初始化         | make setup 从零安装依赖/生成 .env/完成迁移；make dev 启动前后端；make test 示例测试通过                                                                  | 否                                        | `make setup && make test && make check`（L1 + 架构基线）                                                           | passing      |
| F02 | 实体 CRUD API   | POST/GET/PATCH/DELETE /api/entities：properties 按类型校验、id 系统生成、删除校验关系引用（应用层 ReferentialError + DB 层外键 ON DELETE RESTRICT 兜底）、@ 检索；首个迁移建齐 entities+relationships 两表并声明外键                                                      | 否                                        | L1: `pytest tests/unit/test_entities_service.py`；L2: `pytest tests/integration/test_entities_api.py`         | passing |
| F03 | 关系 CRUD API   | POST/GET/PATCH/DELETE /api/relations：端点存在性校验、自环/重复关系拒绝、known\_by 成员校验                                                           | 是（entities+relations）                    | L1: `pytest tests/unit/test_relations_service.py`；L2: `pytest tests/integration/test_relations_api.py`；L3: `pytest tests/e2e/test_relations_flow.py`                                                   | passing |
| F04 | 三视角过滤图查询      | GET /api/graph?perspective=author/character/audience：author 全量；character 按 known\_by 过滤且不泄露被过滤实体名；audience 按 audience\_known 过滤 | 是（entities+relations+perspectives）       | L1: `pytest tests/unit/test_perspectives_service.py`；L2/L3: `pytest tests/integration tests/e2e -k graph`    | passing |
| F05 | 前端图谱工作台       | G6 力导向图渲染实体/关系（缩放/拖拽/点击），节点详情面板（毛玻璃样式），CRUD 表单                                                                                  | 是（前后端联调）                                 | L1/L2: `pnpm test:unit && pnpm test:integration`；L3: Playwright `pnpm test:e2e`                              | passing |
| F06 | 视角切换 UI       | 一键切换三视角；character 视角选择角色（作者、角色、观众）；切换后图数据按视角刷新                                                                                  | 是（前后端联调）                                 | L1/L2: `pnpm test:unit && pnpm test:integration`；L3: Playwright `pnpm test:e2e`（场景含三视角切换 perspective.spec）                                                                                       | passing |
| F07 | @ 实体选择器       | 输入 @ 触发防抖检索，选择插入引用，提示该实体对当前视角是否可见                                                                                               | 是（前后端联调）                                 | L1: `pytest tests/unit/test_entities_service.py`；L1/L2 前端: `pnpm test:unit && pnpm test:integration`；L3: Playwright `pnpm test:e2e`（场景含 @ 检索 entity-picker.spec）                                                                                       | passing |
| F08 | 资产管理       | 独立资产库（data/assets.db，HTML 形态存储）；图片上传（白名单/上限/uuid 重命名/流式写盘）；通用资产 CRUD（分类/标题/描述/自由属性/多图）；项目资产=实体按类型分组卡片（缩略图/名称/概述），实体 HTML 资产页惰性生成、过期再生、删除联动清扫；工作台「图谱｜资产管理」双页 + 内嵌 HTML 查看器                                                      | 是（assets+entities+前后端联调）                       | L1: `pytest tests/unit/test_assets_service.py`；L2/L3: `pytest tests/integration tests/e2e -k asset`；前端: `pnpm test:unit && pnpm test:integration` + Playwright `pnpm test:e2e`         | active |
| F10 | Agent 对话与确认写入 | POST /api/agent/chat SSE 流式回复（上下文经视角过滤）；propose 生成结构化草案；confirm 确认后落库                                                           | 是（agent+entities+relations+perspectives） | L1: `pytest tests/unit/test_agent_service.py`；L2/L3: `pytest tests/integration tests/e2e -k agent`（LLM mock） | not\_started |

注：pytest 命令均在 backend/ 目录下执行（make test-\* 已封装）。

## 初始化验收清单（INIT.md，F01 完成条件）

- [x] `make setup` 从零开始能成功（Windows 经 `python scripts/task.py setup` 等价执行）
- [x] `make test` 至少有一个测试通过（后端 5 + 前端 2，含架构检查基线）
- [x] 新的 agent 会话能只看仓库回答"怎么跑"和"怎么测"（AGENTS.md 首次运行命令）
- [x] 任务分解文件存在且有至少 3 个任务（本清单，10 项）
- [x] 所有内容已提交到 git（F01 checkpoint）

