/**
 * 消息流（F10，DESIGN.md §5.4）：user/assistant 消息渲染 + SSE 流式光标 +
 * 检索行为指示（tool 事件）+ 三要素错误条（error 事件）。
 * AgentHome 与 AgentDock 复用（同一会话池，DESIGN.md 决策②）。
 */

import { useEffect, useRef } from "react";

import type { AgentMessage } from "../../stores/agentStore";
import { ErrorStrip } from "../ui/ErrorStrip";

function MessageItem({ message }: { message: AgentMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`} data-testid="agent-message">
      <div
        className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm leading-relaxed ${
          isUser
            ? "bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900"
            : "ring-1 ring-black/5 bg-white/80 text-slate-800 backdrop-blur dark:ring-white/10 dark:bg-slate-800/80 dark:text-slate-200"
        }`}
      >
        {message.content}
        {message.streaming ? (
          <span className="ml-0.5 inline-block h-4 w-2 animate-pulse bg-slate-400 align-middle dark:bg-slate-500" />
        ) : null}
      </div>
    </div>
  );
}

export function MessageList({
  messages,
  loading,
  toolActivity,
  error,
  onErrorRetry,
  emptyHint,
}: {
  messages: AgentMessage[];
  loading: boolean;
  toolActivity: { name: string; phase: string } | null;
  error: { problem: string; fix: string } | null;
  onErrorRetry: () => void;
  emptyHint?: string;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // jsdom 无 scrollIntoView（测试环境守卫）；生产环境滚动到最新消息
    bottomRef.current?.scrollIntoView?.({ block: "end" });
  }, [messages]);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4" data-testid="agent-messages">
      {loading && messages.length === 0 ? (
        <p className="text-center text-xs text-slate-400 dark:text-slate-500">加载中…</p>
      ) : null}
      {messages.length === 0 && !loading ? (
        <p className="mt-8 text-center text-sm text-slate-400 dark:text-slate-500">
          {emptyHint ?? "开始你的第一句话吧。"}
        </p>
      ) : null}
      {messages.map((m) => (
        <MessageItem key={m.id} message={m} />
      ))}
      {toolActivity ? (
        <p className="text-center text-xs text-slate-400 dark:text-slate-500" data-testid="agent-tool-hint">
          正在检索图谱…
        </p>
      ) : null}
      {error ? (
        <ErrorStrip problem={error.problem} fix={error.fix} onRetry={onErrorRetry} testId="agent-error" />
      ) : null}
      <div ref={bottomRef} />
    </div>
  );
}
