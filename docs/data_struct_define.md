
### 1. 实体表（`entities`）

所有实体共用一张表，通过 `type` 区分，特有属性存储在 `properties` JSON 中。这样做便于图数据库管理和扩展。

| 字段名              | 类型      | 说明                                                                                 | 静态/动态 |
| ---------------- | ------- | ---------------------------------------------------------------------------------- | ----- |
| `id`             | string  | 唯一ID                                                                               | 静态    |
| `type`           | string  | 实体类型：`character` / `faction` / `location` / `item` / `skill` / `event` / `concept` | 静态    |
| `name`           | string  | 名称                                                                                 | 静态    |
| `aliases`        | list    | 别名/称号                                                                              | 静态    |
| `description`    | string  | 简短描述                                                                               | 静态    |
| `audience_known` | boolean | 观众是否已知该实体存在及基本信息                                                                   | 动态    |
| `properties`     | object  | 类型特有属性，见下                                                                          | 混合    |

#### 各类型 `properties` 定义

##### 1.1 `character`（人物）

| 字段名                     | 类型            | 说明                                                                                              | 静态/动态 |
| ----------------------- | ------------- | ----------------------------------------------------------------------------------------------- | ----- |
| `age`                   | number/string | 年龄                                                                                              | 静态    |
| `gender`                | string        | 性别                                                                                              | 静态    |
| `occupation`            | string        | 身份/职业                                                                                           | 静态    |
| `social_class`          | string        | 阶层                                                                                              | 静态    |
| `resources`             | list          | 资源列表                                                                                            | 静态    |
| `obligations`           | list          | 义务/责任                                                                                           | 静态    |
| `abilities`             | list          | 能力/技能（关联 skill 实体ID）                                                                            | 静态    |
| `weaknesses`            | list          | 弱点                                                                                              | 静态    |
| `habits`                | object        | 习惯：`{quirks, diet, daily_routine, hobbies, unconscious_actions}`                                | 静态    |
| `outer_desire`          | string        | 外在欲望                                                                                            | 静态    |
| `inner_need`            | string        | 内在需要                                                                                            | 静态    |
| `wrong_belief`          | string        | 错误信念                                                                                            | 静态    |
| `main_opposition`       | string        | 主要对抗                                                                                            | 静态    |
| `final_choice`          | string        | 终局选择                                                                                            | 静态    |
| `observable_arc`        | string        | 可观察弧光                                                                                           | 静态    |
| `backstory`             | list          | 前史事件：`{event, choice, belief_debt_wound, current_influence}`                                    | 静态    |
| `core_symbol`           | object        | 核心象征（关联item实例）                                                                                  | 静态    |
| `conscious_creed`       | string        | 表意识信条                                                                                           | 静态    |
| `subconscious_desire`   | string        | 潜意识渴望                                                                                           | 静态    |
| `shadow`                | string        | 阴影                                                                                              | 静态    |
| `desire`                | string        | 贪求                                                                                              | 静态    |
| `aversion`              | string        | 憎恶                                                                                              | 静态    |
| `delusion`              | string        | 执念                                                                                              | 静态    |
| `cognitive_lens`        | string        | 认知模式                                                                                            | 静态    |
| `family_theme`          | string        | 原生家庭课题                                                                                          | 静态    |
| `worldview_initial`     | string        | 初期世界观                                                                                           | 静态    |
| `life_view_initial`     | string        | 初期人生观                                                                                           | 静态    |
| `value_view_initial`    | string        | 初期价值观                                                                                           | 静态    |
| `affiliation`           | string        | 所属组织/门派（关联 faction ID）                                                                          | 静态    |
| `origin`                | string        | 出身地                                                                                             | 静态    |
| `cultivation`           | object        | 能力体系（通用化，内部可替换）                                                                                 | 静态    |
| `pressure_behaviors`    | list          | 压力下行为：`{trigger, behavior}`                                                                     | 静态    |
| `language_fingerprint`  | list          | 语言指纹：`{dimension, value}`                                                                       | 静态    |
| `writing_guide`         | object        | 创作指南：`{cheapest_unusable_plan, blocked_reaction, strategy_change_trigger, final_burden_choice}` | 静态    |
| `forbidden_distortions` | list          | 禁止失真                                                                                            | 静态    |
| `visual_features`       | list          | 视觉特征                                                                                            | 静态    |

**注**：`worldview_initial`, `life_view_initial`, `value_view_initial` 为初始值，当前值在 `character_state` 中。

##### 1.2 `faction`（组织/门派）

| 字段名 | 类型 | 说明 | 静态/动态 |
|--------|------|------|-----------|
| `description` | string | 宗旨、历史 | 静态 |
| `headquarters` | string | 驻地（关联 location ID） | 静态 |
| `members` | list | 成员角色ID | 静态 |
| `resources` | list | 势力资源 | 静态 |
| `doctrine` | string | 教义/规则 | 静态 |
| `public_relations` | list | 对外关系：`{faction_id, relation_type}` | 动态 |

##### 1.3 `location`（地点）

| 字段名 | 类型 | 说明 | 静态/动态 |
|--------|------|------|-----------|
| `location_type` | string | `region` / `terrain` / `building` / `site` | 静态 |
| `description` | string | 基础描述 | 静态 |
| `parent_location` | string | 上级地点 ID | 静态 |
| `climate` | string | 气候 | 静态 |
| `season` | string | 当前季节 | 动态 |
| `weather` | string | 当前天气 | 动态 |
| `time_of_day` | string | 昼夜状态 | 动态 |
| `crowd_state` | string | 群众状态 | 动态 |
| `special_restrictions` | list | 特殊限制 | 静态 |
| `visual_elements` | object | 视觉元素：`{flora, cuisine, architecture_style}` 等 | 静态 |
| `resources` | list | 自然资源 | 静态 |

##### 1.4 `item`（物件）

| 字段名 | 类型 | 说明 | 静态/动态 |
|--------|------|------|-----------|
| `appearance` | string | 外观描述 | 静态 |
| `authenticity` | string | 真伪状态 | 动态 |
| `damage` | string | 损坏情况 | 动态 |
| `location` | string | 当前位置（关联 location/character ID） | 动态 |
| `holder` | string | 当前持有人（关联 character ID） | 动态 |
| `seen_by` | list | 见过的角色ID | 动态 |

##### 1.5 `skill`（技能/能力）

| 字段名 | 类型 | 说明 | 静态/动态 |
|--------|------|------|-----------|
| `description` | string | 技能描述 | 静态 |
| `owner` | string | 拥有者角色ID | 静态 |
| `cost` | string | 使用代价/限制 | 静态 |
| `level` | string | 熟练度/境界 | 动态 |
| `category` | string | 分类（如功法、魔法、科技） | 静态 |

##### 1.6 `event`（事件）

| 字段名 | 类型 | 说明 | 静态/动态 |
|--------|------|------|-----------|
| `description` | string | 事件描述 | 静态 |
| `participants` | list | 参与角色ID | 静态 |
| `location` | string | 发生地点ID | 静态 |
| `time` | string | 发生时间（世界时间） | 静态 |
| `is_public` | boolean | 是否对观众公开 | 动态 |
| `known_by` | list | 知道该事件的角色ID | 动态 |

##### 1.7 `concept`（概念/文化元素）

| 字段名 | 类型 | 说明 | 静态/动态 |
|--------|------|------|-----------|
| `concept_type` | string | `flora` / `fauna` / `cuisine` / `custom` / `myth` 等 | 静态 |
| `description` | string | 描述 | 静态 |
| `origin` | string | 来源/传说 | 静态 |
| `image_ref` | string | 视觉资产路径 | 静态 |

---

### 2. 关系表（`relationships`）

| 字段名 | 类型 | 说明 | 静态/动态 |
|--------|------|------|-----------|
| `id` | string | 唯一ID | 静态 |
| `source` | string | 起点实体ID | 静态 |
| `target` | string | 终点实体ID | 静态 |
| `type` | string | 关系类型（如 `TRUSTS`, `BELONGS_TO`, `KNOWS_ABOUT`） | 静态 |
| `dynamic_type` | string | 关系模式（互补型/镜像型等） | 静态 |
| `element_interaction` | object | 能力交互（如五行生克、功法组合） | 静态 |
| `trust` | number | 信任度（0-1） | 动态 |
| `intimacy` | number | 亲密感（0-1） | 动态 |
| `dependency` | number | 依赖程度（0-1） | 动态 |
| `resentment` | number | 怨恨程度（0-1） | 动态 |
| `public_identity` | string | 公开身份 | 动态 |
| `private_identity` | string | 私下身份 | 动态 |
| `promise` | string | 承诺内容 | 动态 |
| `wants_from` | string | 想从对方得到什么 | 动态 |
| `believes_other_wants` | string | 认为对方想要什么 | 动态 |
| `leverage` | string | 筹码 | 动态 |
| `boundary` | string | 边界 | 动态 |
| `status` | string | 当前关系状态 | 动态 |
| `known_by` | list | 哪些角色知道此关系 | 动态 |
| `audience_known` | boolean | 观众是否已知此关系 | 动态 |

---

### 3. 角色动态状态表（`character_state`）

| 字段名 | 类型 | 说明 | 静态/动态 |
|--------|------|------|-----------|
| `character_id` | string | 关联角色ID | 静态 |
| `location` | string | 当前位置 | 动态 |
| `emotional_state` | string | 当前情绪 | 动态 |
| `physical_state` | object | 身体状态：`{injuries, outfit, held_items, spatial_habits, title_changes}` | 动态 |
| `inventory` | list | 持有物品ID列表 | 动态 |
| `current_goal` | string | 当前目标 | 动态 |
| `camp` | string | 当前阵营/立场 | 动态 |
| `worldview_current` | string | 当前世界观 | 动态 |
| `life_view_current` | string | 当前人生观 | 动态 |
| `value_view_current` | string | 当前价值观 | 动态 |
| `knowledge_summary` | string | 当前知识摘要（由全知图生成） | 动态 |
| `relationship_summary` | string | 当前关系摘要 | 动态 |

---

### 4. 事实/知识表（`facts`）

| 字段名 | 类型 | 说明 | 静态/动态 |
|--------|------|------|-----------|
| `id` | string | 唯一ID | 静态 |
| `description` | string | 客观事实内容 | 静态 |
| `fact_type` | string | `observation` / `surface_interpretation` / `true_interpretation` | 静态 |
| `source` | string | 信息来源 | 静态 |
| `credibility` | number | 可信度（0-1） | 动态 |
| `acquired_scene` | string | 获知场次ID | 动态 |
| `is_shared` | boolean | 是否已分享 | 动态 |
| `known_by_characters` | list | 知道该事实的角色ID | 动态 |
| `audience_known` | boolean | 观众是否已知 | 动态 |

---

### 5. 线索表（`clues`）

| 字段名 | 类型 | 说明 | 静态/动态 |
|--------|------|------|-----------|
| `id` | string | 唯一ID | 静态 |
| `observation` | string | 观察事实 | 静态 |
| `surface_interpretation` | string | 表面解释 | 静态 |
| `true_interpretation` | string | 真实解释 | 静态 |
| `audience_exposure` | boolean | 观众是否已看到 | 动态 |
| `status` | string | 状态（未发现/已发现/已误解） | 动态 |
| `related_entities` | list | 关联实体ID | 静态 |

---

### 6. 线程表（`threads`）

| 字段名 | 类型 | 说明 | 静态/动态 |
|--------|------|------|-----------|
| `id` | string | 唯一ID | 静态 |
| `promise` | string | 承诺/目标描述 | 静态 |
| `owner` | string | 拥有者角色ID | 静态 |
| `current_stage` | string | 当前阶段 | 动态 |
| `last_change` | string | 上次变化场景ID | 动态 |
| `next_pressure` | string | 下一压力点 | 动态 |
| `recovery_condition` | string | 回收条件 | 静态 |
| `audience_known` | boolean | 观众是否知道该线程 | 动态 |

---

### 7. 状态变更日志表（`state_change_log`）

| 字段名 | 类型 | 说明 | 静态/动态 |
|--------|------|------|-----------|
| `id` | string | 唯一ID（自动生成） | 静态 |
| `dimension` | string | 变化维度（如 `knowledge`, `worldview`, `relationship`, `location`, `emotional_state`） | 静态 |
| `subject` | string | 主体ID（如 `char-zhou-lan`） | 静态 |
| `before` | string | 变化前状态描述 | 静态 |
| `after` | string | 变化后状态描述 | 静态 |
| `cause` | string | 变化原因（场景ID + 事件描述） | 静态 |
| `evidence` | string | 证据场景ID | 静态 |
| `world_time` | string | 世界时间戳 | 静态 |
| `scene_id` | string | 所属场次ID | 静态 |

---

### 8. 全局状态表（`global_state`）

| 字段名 | 类型 | 说明 | 静态/动态 |
|--------|------|------|-----------|
| `id` | string | 单例ID | 静态 |
| `world_time` | string | 当前世界时间 | 动态 |
| `elapsed_time` | string | 已过时长 | 动态 |
| `transportation` | string | 交通状态 | 动态 |
| `season` | string | 季节 | 动态 |
| `deadline` | string | 截止时间 | 动态 |
| `production_continuity` | object | 制作连续：`{makeup, blood, weather, crowd_state, special_restrictions}` | 动态 |

---

### 9. 观众模型表（`audience_model`）

| 字段名 | 类型 | 说明 | 静态/动态 |
|--------|------|------|-----------|
| `id` | string | 唯一ID | 静态 |
| `entity_id` | string | 关联实体/关系/事实ID | 静态 |
| `author_truth` | string | 作者真相 | 静态 |
| `character_cognition` | string | 人物认知（可能错误） | 动态 |
| `audience_evidence` | string | 观众证据（已呈现内容） | 动态 |
| `expected_inference` | string | 预期推断 | 静态 |
| `audience_known` | boolean | 观众是否已知 | 动态 |
