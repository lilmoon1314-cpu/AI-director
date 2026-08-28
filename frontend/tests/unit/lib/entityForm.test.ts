/**
 * F05 L1：实体表单校验与载荷装配测试（U4，参数化）。
 * 设计依据: 无效等价类—name 空串/空白字符/type 非枚举；
 * 边界值—name 单字符（min_length=1 紧邻合法侧）；载荷装配—aliases 分隔容错。
 */

import { describe, expect, it } from "vitest";

import {
  EMPTY_ENTITY_FORM,
  toEntityCreate,
  validateEntityForm,
  type EntityFormValues,
} from "../../../src/lib/entityForm";

function form(overrides: Partial<EntityFormValues>): EntityFormValues {
  return { ...EMPTY_ENTITY_FORM, ...overrides };
}

describe("validateEntityForm（U4）", () => {
  it.each([
    ["name 空串", form({ name: "" }), "name"],
    ["name 纯空白", form({ name: "  \u3000" }), "name"],
    ["type 非枚举值", form({ name: "周兰", type: "dragon" }), "type"],
  ])("%s → 校验失败且指向对应字段（无效等价类）", (_name, values, expectedField) => {
    const issues = validateEntityForm(values);
    expect(issues.map((i) => i.field)).toContain(expectedField);
    expect(issues.every((i) => i.message.length > 0)).toBe(true);
  });

  it("合法最小输入（name 单字符，边界值—min_length=1 紧邻合法侧）→ 通过", () => {
    expect(validateEntityForm(form({ name: "兰" }))).toEqual([]);
  });
});

describe("toEntityCreate（载荷装配）", () => {
  it("name 去首尾空白；aliases 按中英逗号/顿号分隔并剔除空白项", () => {
    const payload = toEntityCreate(
      form({ name: "  周兰  ", aliases: " 兰姐 ，阿兰、  ,,", type: "character" }),
    );
    expect(payload.name).toBe("周兰");
    expect(payload.aliases).toEqual(["兰姐", "阿兰"]);
    expect(payload.type).toBe("character");
    expect(payload.audience_known).toBe(false);
    expect(payload.description).toBe("");
  });
});
