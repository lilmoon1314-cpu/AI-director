"""assets 模块 HTML 渲染器：通用资产页与实体资产页（自包含 HTML 全文）。

安全约束（assets/CONSTRAINTS.md）:
    所有动态内容一律经 _esc / _render_value 转义后拼接，禁止任何未转义插值
    （XSS 防线——资产页内容来自用户输入与主库实体数据）。

形态约束（DECISIONS 2026-09-05）:
    每个资产页 = 单份自包含 HTML（内联 CSS，无外部依赖）；图片经
    /static/assets/{stored_name} 绝对路径引用；美观且便于后续作为多模态
    上下文注入 LLM。
"""

import html
from typing import Any, Protocol

from app.assets.schemas import ENTITY_TYPE_LABELS, AssetImageRead


class EntityLike(Protocol):
    """实体数据的结构契约（不 import entities.schemas，模块解耦见 backend/CONSTRAINTS.md）。

    作用: 渲染器只依赖此处声明的只读属性；entities.service 返回的 EntityRead
        天然满足该协议（结构化鸭子类型；成员声明为只读 property 以兼容 Literal 子类型）。
    """

    @property
    def id(self) -> str: ...

    @property
    def type(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def aliases(self) -> list[str]: ...

    @property
    def description(self) -> str: ...

    @property
    def properties(self) -> dict[str, Any]: ...


_CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
  background: #f4f5f7; color: #1d2129; line-height: 1.65; padding: 32px 16px;
}
@media (prefers-color-scheme: dark) {
  body { background: #17181c; color: #e8eaed; }
  .card, .attr-item { background: #23252b !important; }
  .chip { background: #2c2e35 !important; color: #cfd3da !important; }
}
.page { max-width: 960px; margin: 0 auto; display: flex; flex-direction: column; gap: 20px; }
.card {
  background: #ffffff; border-radius: 16px; padding: 24px 28px;
  box-shadow: 0 1px 3px rgba(0,0,0,.06), 0 8px 24px rgba(0,0,0,.04);
}
h1 { font-size: 26px; font-weight: 650; letter-spacing: .2px; }
h2 { font-size: 15px; font-weight: 600; opacity: .55; margin-bottom: 12px; letter-spacing: .5px; }
.chip {
  display: inline-block; padding: 2px 12px; border-radius: 999px;
  background: #eef0f3; color: #4e5661; font-size: 13px; margin-right: 8px;
}
.header-meta { margin-top: 8px; }
.aliases { color: #6b7280; font-size: 14px; margin-top: 6px; }
.desc-text { white-space: pre-wrap; }
dl.attrs { display: grid; grid-template-columns: 1fr; gap: 10px; }
.attr-item {
  background: #f8f9fb; border-radius: 12px; padding: 10px 16px;
  display: grid; grid-template-columns: 180px 1fr; gap: 12px; align-items: baseline;
}
.attr-key { font-size: 13px; color: #6b7280; word-break: break-all; }
.attr-val { font-size: 14px; min-width: 0; }
.attr-val ul { padding-left: 18px; }
.gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 14px; }
.gallery figure {
  border-radius: 12px; overflow: hidden; background: #f8f9fb;
  border: 1px solid rgba(0,0,0,.05);
}
.gallery img { width: 100%; height: 180px; object-fit: cover; display: block; }
.gallery figcaption {
  font-size: 12px; color: #6b7280; padding: 6px 10px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.gallery-empty { color: #9ca3af; font-size: 14px; }
footer { text-align: center; font-size: 12px; color: #9ca3af; padding: 8px 0 20px; }
@media (max-width: 640px) { .attr-item { grid-template-columns: 1fr; gap: 2px; } }
"""


def _esc(value: Any) -> str:
    """HTML 转义（XSS 防线的唯一转义出口）。

    作用: 任意值转 string 后做全量 HTML 转义（含引号），供安全插值。
    参数: value — 任意动态值。返回值: str — 转义后文本。异常: 无。依赖: html.escape。
    """
    return html.escape(str(value), quote=True)


def _format_scalar(value: Any) -> str:
    """标量值的安全渲染（bool → 是/否，None → 占位符，其余转义）。

    作用: 属性值的叶级渲染。
    参数: value — 标量值。返回值: str — 安全 HTML 片段。异常: 无。依赖: _esc。
    """
    if value is None:
        return "<span class='attr-val'>—</span>"
    if isinstance(value, bool):
        return _esc("是" if value else "否")
    return _esc(value)


def _render_value(value: Any) -> str:
    """属性值递归渲染（标量 / 列表 / 对象）。

    作用: 结构化属性的安全 HTML 化——list 渲染为无序列表（纯标量列表内联）、
        dict 渲染为嵌套键值对；所有叶值经 _format_scalar/_esc 转义。
    参数: value — 任意 JSON 值。返回值: str — 安全 HTML 片段。异常: 无。依赖: _esc。
    """
    if isinstance(value, dict):
        rows = "".join(
            f"<div class='attr-item'><span class='attr-key'>{_esc(k)}</span>"
            f"<span class='attr-val'>{_render_value(v)}</span></div>"
            for k, v in value.items()
        )
        return f"<div class='attr-val'>{rows}</div>"
    if isinstance(value, list):
        if not value:
            return "<span class='attr-val'>—</span>"
        if all(not isinstance(v, (list, dict)) for v in value):
            return _esc("、".join(str(v) for v in value))
        items = "".join(f"<li>{_render_value(v)}</li>" for v in value)
        return f"<ul>{items}</ul>"
    return _format_scalar(value)


def _render_attrs(title: str, pairs: list[tuple[str, Any]]) -> str:
    """渲染键值属性小节（空键值对集合时整节约省略）。

    作用: 通用资产 attributes 与实体 properties 的共用渲染器。
    参数: title — 小节标题；pairs — (键, 值) 列表（保持插入序）。
    返回值: str — 安全 HTML 片段。异常: 无。依赖: _esc、_render_value。
    """
    if not pairs:
        return ""
    rows = "".join(
        f"<div class='attr-item'><span class='attr-key'>{_esc(k)}</span>"
        f"<span class='attr-val'>{_render_value(v)}</span></div>"
        for k, v in pairs
    )
    return f"<section class='card'><h2>{_esc(title)}</h2><dl class='attrs'>{rows}</dl></section>"


def _render_gallery(images: list[AssetImageRead]) -> str:
    """渲染图片画廊小节（含懒加载；无图时显示占位文案）。

    作用: 两类资产页共用的图片展示区。
    参数: images — 图片元数据列表。
    返回值: str — 安全 HTML 片段。异常: 无。依赖: _esc。
    """
    if not images:
        section_title = "<h2>图片（0）</h2>"
        return (
            f"<section class='card'>{section_title}<p class='gallery-empty'>暂无图片</p></section>"
        )
    figures = "".join(
        "<figure><img loading='lazy' src='"
        + _esc(img.url)
        + "' alt='"
        + _esc(img.filename_orig)
        + "'><figcaption>"
        + _esc(img.filename_orig)
        + "</figcaption></figure>"
        for img in images
    )
    return (
        f"<section class='card'><h2>图片（{len(images)}）</h2>"
        f"<div class='gallery'>{figures}</div></section>"
    )


def _page_shell(title: str, body: str, generated_at: str) -> str:
    """包装为完整自包含 HTML 文档。

    作用: 统一文档骨架（内联 CSS + 页脚生成时间）；title 与 body 均为已转义内容。
    参数: title — 文档标题（调用方已转义）；body — 已转义的主体片段；generated_at — 生成时间文本。
    返回值: str — 完整 HTML。异常: 无。依赖: _esc。
    """
    return (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{title} · AI Director 资产</title>"
        f"<style>{_CSS}</style></head><body><main class='page'>{body}"
        f"<footer>AI Director 资产库 · 生成于 {_esc(generated_at)}</footer>"
        "</main></body></html>"
    )


def render_general_page(
    *,
    title: str,
    category: str,
    description: str,
    attributes: dict[str, Any],
    images: list[AssetImageRead],
    generated_at: str,
) -> str:
    """渲染通用资产页 HTML 全文。

    作用: 通用资产（表情/风格/植被等参考）的展示页——标题 + 分类/描述 +
        attributes 键值小节 + 图片画廊；全部动态内容转义。
    参数:
        title — 资产标题；category — 分类标签（可空）；description — 描述；
        attributes — 自由属性键值；images — 图片列表；generated_at — 生成时间文本。
    返回值: str — 完整自包含 HTML。
    异常: 无。
    依赖: _page_shell、_render_attrs、_render_gallery、_esc。
    """
    header = (
        "<section class='card'><div>"
        + (f"<span class='chip'>{_esc(category)}</span>" if category else "")
        + f"</div><h1>{_esc(title)}</h1>"
        + (
            f"<section class='header-meta'><h2>概述</h2>"
            f"<p class='desc-text'>{_esc(description)}</p></section>"
            if description
            else ""
        )
        + "</section>"
    )
    body = header + _render_attrs("自定义属性", list(attributes.items())) + _render_gallery(images)
    return _page_shell(_esc(title), body, generated_at)


def render_entity_page(
    *,
    entity: EntityLike,
    images: list[AssetImageRead],
    generated_at: str,
) -> str:
    """渲染实体资产页 HTML 全文（项目资产详情）。

    作用: 主库实体的展示页——类型/名称/别名 + 概述 + 全量结构化属性 +
        图片画廊；properties 保持插入序整体渲染，未声明字段一并展示。
    参数: entity — 实体数据（满足 EntityLike 结构契约，entities.service 导出）；
        images — 实体图片；generated_at — 生成时间文本。
    返回值: str — 完整自包含 HTML。
    异常: 无。
    依赖: _page_shell、_render_attrs、_render_gallery、_esc。
    """
    type_label = ENTITY_TYPE_LABELS.get(entity.type, entity.type)
    aliases_text = "、".join(entity.aliases)
    header = (
        "<section class='card'><div>"
        f"<span class='chip'>{_esc(type_label)}</span>"
        f"<span class='chip'>{_esc(entity.id)}</span></div>"
        f"<h1>{_esc(entity.name)}</h1>"
        + (f"<p class='aliases'>别名：{_esc(aliases_text)}</p>" if aliases_text else "")
        + (
            f"<section class='header-meta'><h2>概述</h2>"
            f"<p class='desc-text'>{_esc(entity.description)}</p></section>"
            if entity.description
            else ""
        )
        + "</section>"
    )
    body = (
        header
        + _render_attrs("类型属性", list(entity.properties.items()))
        + _render_gallery(images)
    )
    return _page_shell(_esc(entity.name), body, generated_at)
