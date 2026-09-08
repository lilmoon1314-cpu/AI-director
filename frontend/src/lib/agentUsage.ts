/**
 * agentUsage：UsageBar 派生纯函数（F13，DESIGN.md §13.1）。
 * - 会话累计 = 全部消息 usage 求和（None 按 0）；
 * - 琥珀警示阈值 = 容量占比 > 0.8（DESIGN「超 80% 变琥珀」；0.8 恰好不警示）。
 * 数据语义与展示语义分离：占比原值透传（可 >1），钳制只在展示层。
 */

/** 消息上的 usage 字段形状（agentStore.AgentMessage 子集）。 */
export interface UsageCarrier {
  promptTokens?: number | null;
  completionTokens?: number | null;
}

export interface UsageTotals {
  promptTokens: number;
  completionTokens: number;
}

/** 会话累计：全部消息 usage 求和（null/undefined 按 0 计）。 */
export function sumMessageUsage(messages: UsageCarrier[]): UsageTotals {
  let promptTokens = 0;
  let completionTokens = 0;
  for (const m of messages) {
    promptTokens += m.promptTokens ?? 0;
    completionTokens += m.completionTokens ?? 0;
  }
  return { promptTokens, completionTokens };
}

/** 琥珀警示判定：占比严格大于 0.8（边界值 0.8 不警示）。 */
export function isUsageWarn(contextRatio: number | null | undefined): boolean {
  if (contextRatio === null || contextRatio === undefined) return false;
  return contextRatio > 0.8;
}

/** 占比 → 条宽百分比（展示层钳制 0–100）。 */
export function ratioPercent(contextRatio: number | null | undefined): number {
  if (contextRatio === null || contextRatio === undefined) return 0;
  return Math.round(Math.min(Math.max(contextRatio, 0), 1) * 100);
}
