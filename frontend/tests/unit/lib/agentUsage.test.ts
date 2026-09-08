/**
 * F13 L1：agentUsage 纯函数单元测试（FU2/FU3）。
 * 用例设计（等价类/边界值标注）见 docs/tests/F13_agent_experience.md。
 */

import { describe, expect, it } from "vitest";

import { isUsageWarn, ratioPercent, sumMessageUsage } from "../../../src/lib/agentUsage";

describe("agentUsage（FU2/FU3）", () => {
  it.each([
    [0, false, "零占比"],
    [0.79, false, "阈值下界内"],
    [0.8, false, "边界值-恰为0.8不警示"],
    [0.81, true, "边界值-超0.8警示"],
    [1, true, "满容量"],
    [1.2, true, "超上限原值"],
  ])("FU2: isUsageWarn(%s) → %s（%s）", (ratio, expected, _label) => {
    expect(isUsageWarn(ratio)).toBe(expected);
  });

  it.each([
    [null, false, "None 安全"],
    [undefined, false, "缺省安全"],
  ])("FU2: isUsageWarn(%s) → false（%s）", (ratio, expected, _label) => {
    expect(isUsageWarn(ratio)).toBe(expected);
  });

  it.each([
    [null, 0, "None → 0 宽"],
    [0.5, 50, "半容量"],
    [0.8, 80, "边界值"],
    [1.5, 100, "展示层钳制到100"],
  ])("FU2: ratioPercent(%s) → %s（%s）", (ratio, expected, _label) => {
    expect(ratioPercent(ratio)).toBe(expected);
  });

  it("FU3: 会话累计——空列表归零（边界值-空集）", () => {
    expect(sumMessageUsage([])).toEqual({ promptTokens: 0, completionTokens: 0 });
  });

  it("FU3: 会话累计——null usage 按 0 计（等价类-缺失用量）", () => {
    const totals = sumMessageUsage([
      { promptTokens: null, completionTokens: null },
      { promptTokens: 100, completionTokens: 20 },
    ]);
    expect(totals).toEqual({ promptTokens: 100, completionTokens: 20 });
  });

  it("FU3: 会话累计——多消息求和（等价类-有效累加）", () => {
    const totals = sumMessageUsage([
      { promptTokens: 100, completionTokens: 20 },
      { promptTokens: undefined, completionTokens: 5 },
      { promptTokens: 50, completionTokens: null },
    ]);
    expect(totals).toEqual({ promptTokens: 150, completionTokens: 25 });
  });
});
