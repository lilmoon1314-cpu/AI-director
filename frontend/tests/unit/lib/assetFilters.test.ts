/**
 * F12 L1：资产过滤与类型聚合纯函数测试（FU1–FU6，docs/tests/F12_workbench_navigation_assets.md）。
 * 等价类/边界值设计依据见各用例标注；同一断言逻辑的多情况用例参数化。
 */

import { describe, expect, it } from "vitest";

import {
  filterEntityCards,
  filterGeneralAssets,
  typeStats,
} from "../../../src/lib/assetFilters";
import { ENTITY_TYPES } from "../../../src/lib/entityForm";

const generalCards = [
  { id: "g1", title: "愤怒表情", description: "皱眉咬牙", category: "表情参考" },
  { id: "g2", title: "水墨风格", description: "青灰色调", category: "风格参考" },
  { id: "g3", title: "竹林", description: "风格参考式的植被排布", category: "植被参考" },
];

describe("filterGeneralAssets（FU1–FU4）", () => {
  it.each([
    { query: "愤怒", field: "title", id: "g1" },
    { query: "青灰", field: "description", id: "g2" },
    { query: "植被", field: "category", id: "g3" },
  ])(
    "FU1: query=$query 命中 $field（等价类—有效：三匹配字段同构）",
    ({ query, id }) => {
      const result = filterGeneralAssets(generalCards, { query, category: "" });
      expect(result).toHaveLength(1);
      expect(result[0].id).toBe(id);
    },
  );

  it("FU2: 无命中 → 空数组；空串/纯空白 → 全量（等价类—无效-不匹配 + 边界值—空查询两形态）", () => {
    expect(filterGeneralAssets(generalCards, { query: "不存在的词", category: "" })).toEqual([]);
    expect(filterGeneralAssets(generalCards, { query: "", category: "" })).toHaveLength(3);
    expect(filterGeneralAssets(generalCards, { query: "   ", category: "" })).toHaveLength(3);
  });

  it("FU3: query 与 category chip 叠加为 AND（等价类—组合条件）", () => {
    // 「风格」命中 g2（分类）与 g3（描述），但 category=风格参考 时只剩 g2
    const result = filterGeneralAssets(generalCards, { query: "风格", category: "风格参考" });
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("g2");
    // query 命中但分类不符 → 排除（AND 语义）
    expect(
      filterGeneralAssets(generalCards, { query: "竹林", category: "风格参考" }),
    ).toEqual([]);
  });

  it("FU4: 大小写不敏感且匹配前 trim（等价类—大小写变体 + 边界值—首尾空白）", () => {
    const latin = [{ id: "x", title: "Mood ABC", description: "", category: "" }];
    expect(filterGeneralAssets(latin, { query: "abc", category: "" })).toHaveLength(1);
    expect(filterGeneralAssets(latin, { query: "  Mood ", category: "" })).toHaveLength(1);
  });
});

describe("filterEntityCards（FU5）", () => {
  const entityCards = [
    { id: "e1", name: "玄机子", description: "隐世高人" },
    { id: "e2", name: "沈青梧", description: "女捕快" },
  ];

  it("FU5: name/description 命中；无效 query → 空；空白 query → 全量（等价类—有效/无效 + 边界值—空白）", () => {
    expect(filterEntityCards(entityCards, "玄机")[0].id).toBe("e1");
    expect(filterEntityCards(entityCards, "捕快")[0].id).toBe("e2");
    expect(filterEntityCards(entityCards, "不存在")).toEqual([]);
    expect(filterEntityCards(entityCards, "  ")).toHaveLength(2);
  });
});

describe("typeStats（FU6）", () => {
  it("FU6a: 按类型聚合实体数与图片数求和（等价类—多类型聚合）", () => {
    const cards = [
      { type: "character", image_count: 3 },
      { type: "character", image_count: 1 },
      { type: "location", image_count: 2 },
    ];
    const stats = typeStats(cards);
    expect(stats.character).toEqual({ count: 2, images: 4 });
    expect(stats.location).toEqual({ count: 1, images: 2 });
    expect(stats.item).toEqual({ count: 0, images: 0 });
  });

  it("FU6b: 空列表 → 全 7 类计数 0（边界值—空集）", () => {
    const stats = typeStats([]);
    expect(Object.keys(stats)).toEqual(ENTITY_TYPES);
    for (const type of ENTITY_TYPES) expect(stats[type]).toEqual({ count: 0, images: 0 });
  });

  it("FU6c: 未知类型卡片被忽略不进任何库（等价类—无效类型防御）", () => {
    const stats = typeStats([{ type: "unknown-type", image_count: 9 }]);
    for (const type of ENTITY_TYPES) expect(stats[type].count).toBe(0);
    expect(stats["unknown-type"]).toBeUndefined();
  });
});
