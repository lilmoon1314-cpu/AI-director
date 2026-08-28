"""perspectives 模块 Pydantic 模型：三视角过滤图查询的输出投影。

设计约束（perspectives/CONSTRAINTS.md）:
    - 本模块禁止写库（只读聚合），无 models/repository 层；
    - GraphNode/GraphEdge 为轻量投影（图渲染够用即止），不含 properties/
      description/known_by 等动态细节——既控制响应体积，也收窄泄露通道。
字段蓝图: docs/data_struct_define.md §1/§2（实体摘要与关系四元组）。
"""

from typing import Literal

from pydantic import BaseModel, Field

# 视角枚举（/api/graph 路由契约，backend/ARCHITECTURE.md §7）
Perspective = Literal["author", "character", "audience"]


class GraphNode(BaseModel):
    """图节点投影（实体轻量摘要）。

    作用: 图可视化节点数据；仅含渲染必需字段，不含 properties/description
        （收窄 character 视角的信息泄露通道，perspectives/CONSTRAINTS.md）。
    参数: 无（字段定义见下）。返回值: 无（模型类）。异常: 无。依赖: pydantic。
    """

    id: str
    type: str = Field(description="实体类型（character/faction/location/item/skill/event/concept）")
    name: str
    aliases: list[str]


class GraphEdge(BaseModel):
    """图边投影（关系轻量摘要，仅 id 四元组——不含任何名称字段，被过滤实体名不可能经边泄露）。

    作用: 图可视化边数据。
    参数: 无（字段定义见下）。返回值: 无（模型类）。异常: 无。依赖: pydantic。
    """

    id: str
    source: str
    target: str
    type: str


class GraphData(BaseModel):
    """三视角过滤图查询响应（GET /api/graph）。

    作用: 过滤后的 nodes+edges 集合，供前端 G6 渲染。
    参数: 无（字段定义见下）。返回值: 无（模型类）。异常: 无。依赖: pydantic。
    """

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
