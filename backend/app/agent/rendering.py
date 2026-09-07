"""agent 模块 HTML 渲染器：记忆文档页（自包含 HTML，段级内容来自段表拼装）。

安全约束（对齐 assets/rendering.py 同模式）:
    所有动态内容一律经 _esc 转义后拼接，禁止任何未转义插值（XSS 防线——
    段内容来自用户编辑与 LLM patch）。

形态约束（DECISIONS 2026-09-06：记忆文档 HTML 分段模板取代 markdown 方案）:
    每份文档 = 单份自包含 HTML（内联 CSS，无外部依赖，支持暗色）；
    模板按 kind 定义段结构，段内容独立存储、独立替换（token 经济核心）。
"""

import html
from collections.abc import Sequence
from typing import Any, Protocol


class SectionLike(Protocol):
    """文档段数据的结构契约（不 import agent.schemas 之外的模块类型）。

    作用: 渲染器只依赖此处声明的只读属性；MemoryDocSectionRead 天然满足。
    """

    @property
    def seq(self) -> int: ...

    @property
    def title(self) -> str: ...

    @property
    def content(self) -> str: ...

    @property
    def updated_by(self) -> str: ...

    @property
    def version(self) -> int: ...


def _esc(value: Any) -> str:
    """HTML 转义（XSS 防线的唯一转义出口）。

    参数: value — 任意动态值。返回值: str — 转义后文本。异常: 无。依赖: html。
    """
    return html.escape(str(value), quote=True)


_CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
  background: #f4f5f7; color: #1d2129; line-height: 1.7; padding: 32px 16px;
}
@media (prefers-color-scheme: dark) {
  body { background: #17181c; color: #e8eaed; }
  .card { background: #23252b !important; }
  .sec-head { border-color: #3a3d45 !important; }
  .meta { color: #9aa0aa !important; }
}
.page { max-width: 860px; margin: 0 auto; display: flex; flex-direction: column; gap: 18px; }
.card {
  background: #ffffff; border-radius: 16px; padding: 24px 28px;
  box-shadow: 0 1px 3px rgba(0,0,0,.06), 0 8px 24px rgba(0,0,0,.04);
}
h1 { font-size: 24px; font-weight: 650; letter-spacing: .2px; }
.kind-chip {
  display: inline-block; padding: 2px 12px; border-radius: 999px;
  background: #eef0f3; color: #4e5661; font-size: 13px; margin-bottom: 10px;
}
@media (prefers-color-scheme: dark) {
  .kind-chip { background: #2c2e35 !important; color: #cfd3da !important; }
}
.sec { padding-top: 14px; }
.sec-head {
  display: flex; align-items: baseline; gap: 10px;
  border-bottom: 1px solid #e5e7eb; padding-bottom: 6px; margin-bottom: 10px;
}
.sec-no { font-size: 13px; color: #6b7280; font-variant-numeric: tabular-nums; }
.sec-title { font-size: 16px; font-weight: 600; }
.sec-body { white-space: pre-wrap; font-size: 14.5px; }
.sec-body.empty { color: #9ca3af; font-style: italic; }
.meta { font-size: 12px; color: #6b7280; margin-top: 8px; text-align: right; }
"""


def render_doc_page(title: str, kind_label: str, sections: Sequence[SectionLike]) -> str:
    """渲染记忆文档的自包含 HTML 页（段结构 + 全转义）。

    作用: GET /api/agent/memory-docs/{id}/page 的响应体；段内容独立成块，
        与段级存储/段级 patch 的模型一一对应；空段以占位样式呈现。
    参数: title — 文档标题；kind_label — 模板中文名（如「世界观定位」）；
        sections — 段列表（seq 升序）。
    返回值: str — 完整 HTML 文本。
    异常: 无。依赖: html.escape。
    """
    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{_esc(title)}</title>",
        f"<style>{_CSS}</style>",
        "</head>",
        "<body>",
        '<div class="page">',
        '<div class="card">',
        f'<span class="kind-chip">{_esc(kind_label)}</span>',
        f"<h1>{_esc(title)}</h1>",
        "</div>",
    ]
    for sec in sections:
        body = sec.content.strip()
        body_html = (
            f'<p class="sec-body">{_esc(body)}</p>'
            if body
            else '<p class="sec-body empty">（本段暂无内容）</p>'
        )
        parts.extend(
            [
                '<div class="card sec">',
                '<div class="sec-head">',
                f'<span class="sec-no">{_esc(sec.seq)}</span>',
                f'<span class="sec-title">{_esc(sec.title)}</span>',
                "</div>",
                body_html,
                f'<div class="meta">{_esc(sec.updated_by)} 更新 · v{_esc(sec.version)}</div>',
                "</div>",
            ]
        )
    parts.extend(["</div>", "</body>", "</html>"])
    return "\n".join(parts)
