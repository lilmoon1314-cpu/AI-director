/**
 * docPreview：DocEditor 实时预览的 HTML 渲染纯函数（F13）。
 * **html 替代 md 原则**（DECISIONS 2026-09-06）：编辑/预览载体始终是 HTML
 * 分段模型——本渲染器与后端 agent/rendering.py 同型（自包含 HTML、全量
 * 转义 `_esc`、暗色适配），把「草稿态」段内容即席渲染进 iframe srcDoc，
 * 使未保存编辑也能实时可见。所有插值必须经 `_esc` 转义（XSS 防线）。
 */

export interface PreviewSection {
  seq: number;
  title: string;
  content: string;
}

/** HTML 全量转义（& < > " '——与后端 rendering._esc 同规则）。 */
function esc(text: string): string {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#x27;");
}

/** 渲染自包含预览 HTML（暗色、无脚本；iframe sandbox 下安全）。 */
export function renderDocPreviewHtml(title: string, sections: PreviewSection[]): string {
  const body = sections
    .map(
      (s) => `
    <section class="sec">
      <h2>${esc(`${s.seq}. ${s.title}`)}</h2>
      <p>${esc(s.content) || '<span class="empty">（空段落）</span>'}</p>
    </section>`,
    )
    .join("\n");
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>${esc(title)}</title>
<style>
  :root { color-scheme: dark; }
  body {
    margin: 0; padding: 24px 28px; background: #0f172a; color: #e2e8f0;
    font: 14px/1.7 -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
  }
  h1 { font-size: 18px; margin: 0 0 4px; }
  .meta { font-size: 12px; color: #94a3b8; margin: 0 0 20px; }
  .sec { border-top: 1px solid #1e293b; padding: 14px 0; }
  .sec h2 { font-size: 13px; color: #7dd3fc; margin: 0 0 6px; }
  .sec p { margin: 0; white-space: pre-wrap; word-break: break-word; }
  .empty { color: #64748b; font-style: italic; }
</style>
</head>
<body>
<h1>${esc(title)}</h1>
<p class="meta">实时预览（含未保存草稿）</p>
${body || '<p class="empty">（暂无段落）</p>'}
</body>
</html>`;
}
