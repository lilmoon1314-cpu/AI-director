/**
 * F05 增强轮 L1：配色规则测试（U6/U7，参数化）。
 * 设计依据: 等价类—7 实体类型各有标识色 / 边色随非人端；
 * 边界值—未知类型回退、人—人无非人因素取中性、两端皆非人取 source 端。
 */

import { describe, expect, it } from "vitest";

import { nodeColor, relationEdgeColor, TYPE_COLORS } from "../../../src/lib/palette";

describe("nodeColor（U6 类型分色）", () => {
  it.each([
    ["character", "#5b8def"],
    ["faction", "#e0885a"],
    ["location", "#4caf7d"],
    ["item", "#d4b13f"],
    ["skill", "#a678d8"],
    ["event", "#e06a75"],
    ["concept", "#8a94a6"],
  ])("%s → 固定标识色（等价类—类型枚举逐一）", (type, color) => {
    expect(nodeColor(type)).toBe(color);
    expect(TYPE_COLORS[type]).toBe(color);
  });

  it("未知类型回退概念灰（无效等价类容错）", () => {
    expect(nodeColor("dragon")).toBe(TYPE_COLORS.concept);
  });
});

describe("relationEdgeColor（U7 边随非人端淡化）", () => {
  it.each([
    // 人—非人：跟随非人端类型色
    ["character", "item", "#d4b13f"],
    ["character", "faction", "#e0885a"],
    ["item", "character", "#d4b13f"], // 方向无关：非人端优先
    // 人—人：无非人因素，中性蓝灰
    ["character", "character", "#94a3b8"],
    // 两端皆非人：跟随 source 端
    ["location", "item", "#4caf7d"],
  ])("%s—%s → 边色 %s", (sourceType, targetType, expected) => {
    const edge = relationEdgeColor(sourceType, targetType);
    expect(edge.stroke).toBe(expected);
  });

  it("关系边整体比节点更淡更透明（opacity < 1）", () => {
    const edge = relationEdgeColor("character", "item");
    expect(edge.opacity).toBeGreaterThan(0);
    expect(edge.opacity).toBeLessThan(1);
  });
});
