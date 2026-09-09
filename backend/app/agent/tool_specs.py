"""Agent 工具声明（纯契约数据模块）。

作用:
    集中存放 TOOL_SPECS——openai function calling 格式的工具声明
    （名称/描述/参数 schema）。名称与描述是 prompt 契约的一部分，属静态
    契约数据而非逻辑；独立成模块使「数据」与「执行」分离，并允许变异
    测试按 docs/testing.md §9 等价豁免口径把本文件排除在变异路径外
    （描述文本变异无法被行为测试判杀，逐条登记等价性成本过高）。
参数: 无（常量模块）。
返回值: 无。异常: 无。依赖: typing（仅类型标注，防循环引用）。
"""

from typing import Any

# 工具定义（openai function 格式；名称/描述是 prompt 契约的一部分）
TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_entities",
            "description": "按名称或别名检索项目内当前视角可见的实体，返回完整详情。",
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {"type": "string", "description": "检索关键词（名称或别名片段）"}
                },
                "required": ["q"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_entity_detail",
            "description": "按 id 查看单个实体的完整属性（须为当前视角可见实体）。",
            "parameters": {
                "type": "object",
                "properties": {"entity_id": {"type": "string", "description": "实体 id"}},
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_neighborhood",
            "description": "查看某实体的全部一度关系（仅当前视角可见的关系）。",
            "parameters": {
                "type": "object",
                "properties": {"entity_id": {"type": "string", "description": "实体 id"}},
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_doc_section",
            "description": "按段读取记忆文档的完整内容（doc_id 与段号见文档目录）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "文档 id"},
                    "seq": {"type": "integer", "description": "段序号（从 1 开始）"},
                },
                "required": ["doc_id", "seq"],
            },
        },
    },
    # ---- 写入类工具（F14：执行仅登记待写入，落库需作者在轮末确认卡批准）----
    {
        "type": "function",
        "function": {
            "name": "create_entity",
            "description": (
                "登记新建实体（不立即写入——待作者在本轮结束的确认卡批准后生效；"
                "实体类型：character/faction/location/item/skill/event/concept）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "description": "实体类型"},
                    "name": {"type": "string", "description": "实体名称（必填）"},
                    "description": {"type": "string", "description": "简介"},
                    "aliases": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "别名列表",
                    },
                    "audience_known": {
                        "type": "boolean",
                        "description": "观众视角是否已知（缺省 false）",
                    },
                    "properties": {"type": "object", "description": "类型扩展属性"},
                },
                "required": ["type", "name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_entity",
            "description": (
                "登记更新实体属性（不立即写入——待作者确认后生效）；"
                "properties_patch 为与既有属性的浅合并补丁。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "实体 id"},
                    "name": {"type": "string", "description": "新名称（可选）"},
                    "description": {"type": "string", "description": "新简介（可选）"},
                    "aliases": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "新别名全量列表（可选，整体替换）",
                    },
                    "audience_known": {"type": "boolean", "description": "（可选）"},
                    "properties_patch": {
                        "type": "object",
                        "description": "属性补丁（浅合并进既有 properties）",
                    },
                },
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_relation",
            "description": (
                "登记新建关系（不立即写入——待作者确认后生效）；端点用实体名称"
                "（或别名）指定，登记时解析为实体 id，未命中会返回错误提示先检索。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "source_name": {"type": "string", "description": "源实体名称"},
                    "target_name": {"type": "string", "description": "目标实体名称"},
                    "relation_type": {"type": "string", "description": "关系类型"},
                    "known_by": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "知晓该关系的角色名称列表（可选）",
                    },
                    "trust": {"type": "number", "description": "信任 0-1（可选）"},
                    "intimacy": {"type": "number", "description": "亲密 0-1（可选）"},
                    "dependency": {"type": "number", "description": "依赖 0-1（可选）"},
                    "resentment": {"type": "number", "description": "怨恨 0-1（可选）"},
                },
                "required": ["source_name", "target_name", "relation_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_memory_doc",
            "description": (
                "登记按模板新建记忆文档（positioning/style，指导类每项目仅一份；"
                "不立即写入——待作者确认后生效）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "description": "模板键（positioning/style）",
                    },
                    "title": {"type": "string", "description": "文档标题（可选，缺省模板标题）"},
                },
                "required": ["kind"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_doc_section",
            "description": (
                "登记写入记忆文档单段内容（不立即写入——待作者确认后生效）；"
                "登记时记录段版本基线，作者此后手改该段则登记自动失效（CAS）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "文档 id"},
                    "seq": {"type": "integer", "description": "段序号（从 1 开始）"},
                    "content": {"type": "string", "description": "新段内容（全量替换）"},
                    "title": {"type": "string", "description": "新段标题（可选）"},
                },
                "required": ["doc_id", "seq", "content"],
            },
        },
    },
]
