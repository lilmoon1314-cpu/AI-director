"""agent 模块记忆文档模板注册表（service 与 tools 的共享常量层）。

作用:
    DOC_TEMPLATES / GUIDE_KINDS 原定义在 service.py；F14 写入工具
    （create_memory_doc）需要在 tools.py 内校验模板合法性与指导类唯一性，
    为解除 tools↔service 循环 import 而抽出为独立常量模块（零逻辑）。
约束:
    作品类多实例模板（outline/screenplay/episode_script/storyboard）随 F15
    扩展时，GUIDE_KINDS 必须同步收窄为指导类（F13 审查 P2-6 登记）。
"""

from typing import Any

# 记忆文档模板（F10 内置两种；作品类模板（outline/screenplay/…）随 F15 落地）
DOC_TEMPLATES: dict[str, dict[str, Any]] = {
    "positioning": {
        "label": "世界观定位",
        "title": "世界观定位",
        "sections": ["一句话定位", "核心冲突", "基调与题材", "目标观众与体量"],
    },
    "style": {
        "label": "风格约定",
        "title": "风格约定",
        "sections": ["叙事视角", "影像与语言风格", "节奏与时长约定", "禁忌与红线"],
    },
}

# 指导类 kind（项目内唯一——每项目仅一份定位/风格文件；F13 验收缺陷修复，
# 作品类多实例 kind 随 F15 扩展时在此登记分类学）
GUIDE_KINDS = frozenset(DOC_TEMPLATES)
