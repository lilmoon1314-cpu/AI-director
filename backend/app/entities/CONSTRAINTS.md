# entities 模块硬约束

> 实现/修改 entities 模块前必读。

- 必须：id 系统生成且创建后不可变；name 变更不得影响 id。
- 禁止：删除实体前未校验 relationships 引用；命中引用必须抛 ReferentialError（不物理级联）。
- 必须：properties 校验 schema 随类型演进时，旧数据读入宽容（unknown 字段保留）、写回严格。
- 禁止：其他模块 import 本模块 repository/models；批量读取一律走 service.get_many。
