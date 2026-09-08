/**
 * ThinkingBlock（F13，DESIGN.md §13.1）：assistant 气泡内的思考过程折叠卡
 * （Z-code 式）——思考中灰字自动展开跟随；正文开始后自动折叠为「已思考 N 秒」
 * 标题行；点击标题行可再展开/收起。
 * 交互语义：思考进行中为「自动跟随」态——手动收起会被跟随逻辑立即重新展开
 * （审查 P2-3 记录，属预期产品选择）；手动切换的自由度从正文到来后生效。
 * 历史消息（reasoning 已落库、无计时）展示为可展开的「已思考」。
 */

import { useEffect, useState } from "react";

export function ThinkingBlock({
  reasoning,
  streaming,
  hasContent,
  seconds,
}: {
  reasoning: string | null | undefined;
  streaming?: boolean;
  hasContent: boolean;
  seconds?: number;
}) {
  const [manualOpen, setManualOpen] = useState<boolean | null>(null);
  const thinkingInProgress = Boolean(streaming && !hasContent && reasoning);
  const expanded = manualOpen ?? thinkingInProgress;

  // 思考进行中强制展开跟随；正文到来（自动折叠）后清除手动态以便下轮自动行为
  useEffect(() => {
    if (thinkingInProgress) setManualOpen(null);
  }, [thinkingInProgress]);

  if (!reasoning) return null;

  const label =
    thinkingInProgress && !expanded
      ? "思考中…"
      : seconds !== undefined
        ? `已思考 ${seconds} 秒`
        : "已思考";

  return (
    <div className="mb-1.5" data-testid="agent-thinking">
      <button
        type="button"
        data-testid="agent-thinking-toggle"
        onClick={() => setManualOpen(!expanded)}
        className="flex items-center gap-1 text-xs text-slate-400 transition-colors duration-150 hover:text-slate-500 dark:text-slate-500 dark:hover:text-slate-400"
        aria-expanded={expanded}
      >
        <span className={`inline-block transition-transform duration-150 ${expanded ? "rotate-90" : ""}`}>▸</span>
        <span className={thinkingInProgress ? "animate-pulse" : ""}>{label}</span>
      </button>
      {expanded ? (
        <div
          data-testid="agent-thinking-body"
          className="mt-1 max-h-40 overflow-y-auto whitespace-pre-wrap rounded-lg bg-black/5 px-3 py-2 text-xs leading-relaxed text-slate-500 dark:bg-white/5 dark:text-slate-400"
        >
          {reasoning}
        </div>
      ) : null}
    </div>
  );
}
