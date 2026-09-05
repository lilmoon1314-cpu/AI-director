/**
 * F07 L1：refTypes schema 契约（U1）与关联字段名称解析（U2）参数化测试。
 * 用例设计见 docs/tests/F07_entity_reference_picker.md。
 */

import { describe, expect, it } from "vitest";

import {
  displayRefValue,
  propertiesSchema,
  type PropertyFieldDef,
} from "../../../src/lib/entityProperties";

// U1: refTypes 字段契约（key/父类型/refTypes 逐一钉死，防 schema 演进丢标注）
const REF_CONTRACT: [string, string, string[]][] = [
  ["character", "abilities", ["skill"]],
  ["character", "affiliation", ["faction"]],
  ["faction", "headquarters", ["location"]],
  ["faction", "members", ["character"]],
  ["location", "parent_location", ["location"]],
  ["item", "location", ["location", "character"]],
  ["item", "holder", ["character"]],
  ["item", "seen_by", ["character"]],
  ["skill", "owner", ["character"]],
  ["event", "participants", ["character"]],
  ["event", "location", ["location"]],
  ["event", "known_by", ["character"]],
];

describe("entityProperties（F07 U1 refTypes 契约）", () => {
  it.each(REF_CONTRACT)("%s.%s refTypes=%j", (entityType, key, refTypes) => {
    // 设计依据: 等价类—ref 字段枚举逐一
    const field = propertiesSchema(entityType).find((f) => f.key === key);
    expect(field).toBeDefined();
    expect(field?.refTypes).toEqual(refTypes);
    // ref 字段的底层 kind 必须是 text（单值）或 list（多值），其余 kind 不可引用
    expect(["text", "list"]).toContain(field?.kind);
  });

  it("非 ref 字段无 refTypes 标注（边界值—反向）", () => {
    const plain = propertiesSchema("character").filter((f) => !f.refTypes);
    expect(plain.length).toBeGreaterThan(0);
    expect(plain.every((f: PropertyFieldDef) => f.refTypes === undefined)).toBe(true);
  });
});

describe("entityProperties（F07 U2 displayRefValue）", () => {
  const nameById = new Map([
    ["char-a", "周兰"],
    ["char-b", "沈墨"],
  ]);

  it.each([
    [["char-a", "char-b"], "周兰、沈墨"], // list 全解析
    [["char-a", "unknown-x"], "周兰、unknown-x"], // 未知 id 回退原始值（边界值）
    ["char-a", "周兰"], // text 单值解析
    ["unknown-x", "unknown-x"], // 未知单值回退
    [[], "—"], // 空数组（边界值—空集）
    ["", "—"], // 空串
    [undefined, "—"], // 未填
    [null, "—"], // null
  ])("%j → %j", (value, expected) => {
    // 设计依据: 等价类—已收录/未收录 id；边界值—空集/空串/未填
    expect(displayRefValue(value, nameById)).toBe(expected);
  });
});
