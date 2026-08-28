# docs/testing.md — 测试策略

> 判定功能是否完成的唯一依据（DoD）。编写任何测试或标记功能完成前必读。

## 1. 验证层级

| 层级 | 定义 | 范围 | 必须性 |
|------|------|------|--------|
| L1 单元 | 单函数/类，依赖全部 mock（内存） | 模块内 | **每个功能必须** |
| L2 集成 | 真实 SQLite（临时库），router→service→repository 全链路 | 单模块内 | **每个功能必须** |
| L3 E2E | 公开接口验证完整用户路径（后端 TestClient / 前端 Playwright） | 跨模块或跨前后端 | **涉及跨组件修改时必须** |

- **跳过任何必须层级 = 功能未完成**（不得标记 passing）。
- "跨组件"判定：功能涉及 ≥2 个领域模块协作，或前后端联调。features.md 每项已标注 `E2E` 列。

## 2. 完成定义（DoD）

功能标记 passing 需同时满足：

1. 实现代码 + 对应单元测试（根 CONSTRAINTS.md §1）
2. 测试文档 `docs/tests/FXX_<name>.md` 就位，层级矩阵中所有"必须"状态为 pass
3. 必须层级测试全部通过（验证命令见 features.md）
4. `make check` 通过
5. 变异测试达标（§9：定向 mutmut kill rate ≥ 85%，存活变异体已分析归档；工具随 F04 落地，自 F04 起生效；**仅适用 backend/app 的 Python 模块，前端功能豁免**——mutmut 无法变异 TypeScript，前端测试有效性由 §8 等价类/边界值设计 + L1/L2/L3 层级测试保障，适用范围详见 §9）

## 3. 目录结构

```
backend/tests/
├── conftest.py           # 共享 fixture（临时 DB、TestClient、内存采样）
├── unit/                 # L1：test_<模块>_<行为>.py
├── integration/          # L2：test_<模块>_api.py
├── e2e/                  # L3：test_<场景>_flow.py（跨模块）
└── architecture/         # 架构约束可执行检查（见 docs/architecture_checks.md）

frontend/tests/
├── unit/                 # L1：组件/store 单测（Vitest + RTL）
└── integration/          # L2：组件树 + mock API（Vitest + msw）
frontend/e2e/             # L3：全栈 E2E（Playwright，F05 引入）
```

## 4. 运行方式

```bash
make test-unit          # 后端: uv run pytest -m "unit"    前端: pnpm test:unit
make test-integration   # 后端: pytest -m "integration"    前端: pnpm test:integration
make test-e2e           # 后端: pytest -m "e2e"            前端: Playwright（F05 起）
make test               # 全部层级 + architecture
```

pytest marker 约定：`unit` / `integration` / `e2e` / `architecture`（conftest.py 注册，测试文件必须标注所属 marker）。

## 5. 测试文档模板（docs/tests/FXX_<name>.md）

```markdown
# FXX <功能名> — 测试文档

## 测试目标
一句话说明验证什么。

## 层级矩阵
| 层级 | 用例 | 测试文件 | 必须 | 状态 |
|------|------|----------|------|------|
| L1 单元 | U1: <行为> | tests/unit/xxx.py | 必须 | pending |
| L2 集成 | I1: <链路> | tests/integration/xxx.py | 必须 | pending |
| L3 E2E | E1: <场景>（跨组件理由） | tests/e2e/xxx.py | 必须/不适用 | pending |

## 用例说明
- U1: <前置/动作/预期>（设计依据：<等价类：有效 / 无效-xxx | 边界值：xxx>）
- I1: ...

## 变异测试结果（用例实现完成后填写；自 F04 起）
- scope（被测模块）/ kill rate / 存活变异体逐一分析（补用例或等价性登记）

## 验收判定
所有"必须"层级通过 + 状态列全 pass + 变异测试达标（§9，自 F04 起）+ make check 通过 → 功能完成。
```

状态列规则：与 features.md 相同，仅在验证命令通过后更新为 `pass`。

## 6. 命名与编写规范

- 测试文件：`test_<模块>_<行为>.py`；用例：`test_<行为>_<预期结果>`
- 一个用例只验证一个行为；断言消息包含三要素（什么/为什么/怎么修，见 docs/lessons.md）
- L3 用例必须走公开接口（HTTP/浏览器），禁止直接调用内部函数

## 7. 内存回归守卫

- 运行侧（**已就位**）：core observability 后台线程低频采样 RSS / CPU 写入 `logs/metrics.jsonl`（运行期资源趋势分析）。
- 测试侧（**已就位**，F02 落地）：conftest.py 提供 e2e 级 fixture——用例执行前后采样进程 RSS，增长超阈值（config: `memory_guard_threshold_mb`）即失败。
- 规则：文档描述机制必须区分「已就位 / 计划（FXX）」双态，禁止把计划写成现状（错误模式 E01，见 docs/lessons.md）。

## 8. 用例设计方法（等价类划分 + 边界值分析）

> AGENTS.md 工作规则强制项；测试文档的用例清单必须按本节方法设计并逐用例标注设计依据。自 F04 起生效。

- **等价类划分**：每个输入/校验维度先划分有效与无效等价类，每类至少一个用例：
    - 示例（关系创建 source/target 维度）：有效（端点存在且非自环）；无效（source 缺失、target 缺失、source == target 自环）。
    - 示例（known_by 维度）：有效（成员均为 character）；无效（成员缺失、成员非 character、列表含重复）。
- **边界值分析**：数值与长度约束取边界与两侧邻界：
    - 0-1 标度字段（trust/intimacy/dependency/resentment）：0、1（边界上）、0.01、0.99（紧邻内侧）、-0.01、1.01（紧邻外侧）。
    - `min_length=1` / `max_length` 字段：空串、1、上限、上限+1。
    - 列表字段：空、单元素、多元素、含重复元素。
- **参数化强制**：同一断言逻辑的等价类/边界值用例一律用 `@pytest.mark.parametrize` 实现为参数化测试（用例 id 标注设计依据），禁止复制粘贴同构测试函数。
- 测试文档「用例说明」按 §5 模板为每个用例标注设计依据，例：`I8 参数化: 0-1 标度越界（边界值：trust∈{-0.01, 1.01} 均 422）`。

## 9. 变异测试（mutmut）

> 状态：**已就位（F04 落地）**——mutmut 2.x 已入 dev 依赖，封装命令 `python scripts/task.py mutate <module> [test_path...]`（等价 `make mutate <module>`）。**适用范围：仅 backend/app 的 Python 模块**（2026-08-28 决策：mutmut 无法变异 TypeScript/React，前端功能 DoD 不含变异测试，其测试有效性由 §8 用例设计方法 + L1/L2/L3 层级测试保障；若未来引入前端变异工具须先修订本条）。

- **判杀器构成（层级覆盖原则，F04 教训 E04 固化）**：判杀测试集合必须覆盖该功能 DoD 的全部「必须」测试层级——判杀器缺哪一层，那一层语义的变异就存在漏杀盲区：
    - **L1 单元（恒为基线）**：`tests/unit/test_<module>_service.py`（默认判杀器，不存在时显式传入）；负责杀过滤规则/校验/投影等纯逻辑变异；
    - **L2 集成（模块含 `router.py` 即必须）**：显式追加该功能集成测试路径——路由注册（prefix/path/装饰器删除）与 Literal/Query 参数校验类变异不改变 service 运行时行为，只有经 HTTP 的集成测试可杀（F04 实测：仅 L1 判杀 kill rate 47%，补 L2 后 95.4%）；`task.py mutate` 对含 router 而判杀器缺 `tests/integration/` 路径的调用自动拦截；
    - **L3 端到端（功能必须层级含 L3 时）**：判杀器须追加对应 e2e 测试路径（可配 `-k` 选择器收窄）——跨组件装配变异（路由挂载、依赖注入、迁移、启动链）在 L1/L2 的桩/裁剪环境下不可见，只有真实组合根的 e2e 可杀。当前若 e2e 所杀变异与 L2 完全重叠可不追加，但存活变异体分析中一旦出现「仅 e2e 可杀」的变异体（L1/L2 判杀下存活、行为只在全链路显现），必须把 e2e 补入判杀器重跑后再归档。
- **时机**：测试文档撰写完成后即把变异测试列入任务清单；用例实现完成、`verify FXX` 之前执行。
- **范围**：仅对本功能被测模块定向运行（如 F04 → `mutate perspectives`），禁止全仓库无差别变异（耗时且噪声大）。
- **达标判据**：kill rate ≥ 85%；未达标时存活变异体必须逐一分析——能补用例则按 §8 补设计补用例，确属等价变异体则按下方「等价性登记」规则处理。错误类用例的断言强度不足（仅断言单键/存在性）会以「三要素文案与 detail 键值变异存活」的形式暴露（E05）：补用例时按三要素完整文案精确相等 + detail 字典整体相等钉死（F04 U4/U5 范式）。
- **等价性登记（不影响运行时行为的变异体豁免规则，含风控）**：不参与、不影响运行时行为的变异体（典型：OpenAPI 文档性字符串——`tags`、`Query/Field description`）无需补用例钉死，登记等价性即视作已处理。「不影响运行时行为」是人工判断，该豁免附带三道防线，缺一不可：
    - **误判防线（唯一判定标准 = 不进入任何运行时数据流）**：路由匹配、参数解析与校验、响应序列化、持久化、错误响应体均属运行时——错误三要素文案出现在 HTTP 响应中，是对外行为契约，必须钉死、不适用本豁免（见 E05）；貌似文档实为行为的标识符严禁登记等价（反例：`Query(alias=...)` 影响参数解析、`Literal`/Enum 值决定校验集合、路由 prefix/path、`response_model` 引用）。
    - **滥用防线（登记要件与比例透明）**：等价登记必须逐条写明核实依据（该标识符在运行时路径的哪个环节被排除），禁止无依据打包豁免；测试文档「变异测试结果」须同时报告实杀数与等价登记数——等价登记数超过变异体总数 20% 即视为 kill rate 门槛失真，必须逐条复核或改判补用例。
    - **时效防线（结论仅对当次验证时点有效）**：模块后续演进使原「纯文档」字段进入运行时路径（如前端开始消费 description 渲染表单）时，对应变异体自动失去豁免资格，须转为可杀用例；变异测试按功能点触发重跑，天然复检。
- **归档**：scope、kill rate、实杀数/等价登记数与存活变异体分析记入该功能测试文档「变异测试结果」小节（模板见 §5）。
- **成本控制**：mutmut 不纳入 make check 常规链，按功能点手动触发；运行时长异常时收窄 scope（模块内单文件/单函数）。
