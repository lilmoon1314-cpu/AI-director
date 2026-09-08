/**
 * UsageBar（F13，DESIGN.md §13.1）：输入框上方的上下文容量细条——
 * 本轮 prompt/completion tokens + 容量占比条（= prompt ÷ AGENT_CONTEXT_MAX_TOKENS）
 * + 会话累计；占比 > 80% 转琥珀色警示（isUsageWarn，边界 0.8 不警示）。
 * 端点未返回 usage 时以「—」占位（兼容等价类）。
 */

import type { AgentMessage, TurnUsage } from "../../stores/agentStore";
import { isUsageWarn, ratioPercent, sumMessageUsage } from "../../lib/agentUsage";

function fmt(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
}

export function UsageBar({
  usage,
  messages,
}: {
  usage: TurnUsage | null;
  messages: AgentMessage[];
}) {
  const totals = sumMessageUsage(messages);
  const ratio = usage?.contextRatio ?? null;
  const warn = isUsageWarn(ratio);
  const percent = ratioPercent(ratio);
  const hasUsage = usage !== null && (usage.promptTokens !== null || usage.completionTokens !== null);

  return (
    <div
      data-testid="agent-usage-bar"
      className={`flex shrink-0 items-center gap-2 border-t px-4 py-1 text-[11px] ${
        warn
          ? "border-amber-500/20 text-amber-600 dark:text-amber-400"
          : "border-black/5 text-slate-400 dark:border-white/10 dark:text-slate-500"
      }`}
    >
      <span data-testid="agent-usage-context">
        上下文 {hasUsage ? fmt(usage?.promptTokens ?? null) : "—"}/{fmt(usage?.contextMaxTokens ?? null)}
      </span>
      <span
        data-testid="agent-usage-meter"
        className={`h-1.5 min-w-16 flex-1 overflow-hidden rounded-full ${
          warn ? "bg-amber-500/20" : "bg-black/10 dark:bg-white/10"
        }`}
        aria-hidden
      >
        <span
          data-testid="agent-usage-meter-fill"
          className={`block h-full rounded-full transition-all duration-200 ${
            warn ? "bg-amber-500" : "bg-slate-400 dark:bg-slate-500"
          }`}
          style={{ width: `${percent}%` }}
        />
      </span>
      <span data-testid="agent-usage-ratio">{hasUsage ? `${percent}%` : "—"}</span>
      <span data-testid="agent-usage-turn">
        本轮 {hasUsage ? `${fmt(usage?.promptTokens ?? null)}+${fmt(usage?.completionTokens ?? null)}` : "—"}
      </span>
      <span data-testid="agent-usage-total">
        累计 {totals.promptTokens + totals.completionTokens > 0 ? `${totals.promptTokens + totals.completionTokens}` : "—"}
      </span>
    </div>
  );
}
