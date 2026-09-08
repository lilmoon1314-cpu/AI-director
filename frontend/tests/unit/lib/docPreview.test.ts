/**
 * F13 L1：docPreview 转义渲染纯函数单元测试（FU1）。
 * 用例设计（等价类/边界值标注）见 docs/tests/F13_agent_experience.md；
 * XSS 向量全覆盖（html 替代 md 原则：预览载体为 HTML 分段模型，全量转义）。
 */

import { describe, expect, it } from "vitest";

import { renderDocPreviewHtml } from "../../../src/lib/docPreview";

describe("docPreview（FU1）", () => {
  it("FU1: 多段渲染——段标题带序号、空段落占位（等价类-有效多段）", () => {
    const html = renderDocPreviewHtml("世界观定位", [
      { seq: 1, title: "一句话定位", content: "海难与救赎。" },
      { seq: 2, title: "核心冲突", content: "" },
    ]);
    expect(html).toContain("<!DOCTYPE html>");
    expect(html).toContain("世界观定位");
    expect(html).toContain("1. 一句话定位");
    expect(html).toContain("海难与救赎。");
    expect(html).toContain("2. 核心冲突");
    expect(html).toContain("（空段落）");
  });

  it("FU1: XSS 向量参数化全转义——script/img onerror/引号/&,空内容", () => {
    const vectors: [string, string][] = [
      ["<script>alert(1)</script>", "&lt;script&gt;"],
      ["<img src=x onerror=alert(2)>", "&lt;img"],
      ['双引号"与单引号\'', "&quot;"],
      ["A&B", "&amp;"],
    ];
    for (const [payload, escaped] of vectors) {
      const html = renderDocPreviewHtml(payload, [{ seq: 1, title: payload, content: payload }]);
      expect(html.includes(payload)).toBe(false);
      expect(html).toContain(escaped);
    }
  });

  it("FU1: 空段列表占位（边界值-空集）", () => {
    const html = renderDocPreviewHtml("空文档", []);
    expect(html).toContain("（暂无段落）");
  });
});
