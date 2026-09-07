/**
 * 聊天输入框（F10，DESIGN.md §5.4）：Enter 发送 / Shift+Enter 换行；
 * 「产出草案」入口触发 propose（两段式第一段）；流式进行中显示停止按钮。
 * AgentHome 与 AgentDock 复用。
 */

import { useState } from "react";

import { Button } from "../ui/Button";

export function ChatInput({
  disabled,
  streaming,
  onSend,
  onPropose,
  onStop,
  testId = "agent-input",
}: {
  disabled?: boolean;
  streaming: boolean;
  onSend: (text: string) => void;
  onPropose?: (text: string) => void;
  onStop?: () => void;
  testId?: string;
}) {
  const [text, setText] = useState("");

  const submit = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled || streaming) return;
    onSend(trimmed);
    setText("");
  };

  return (
    <div className="shrink-0 border-t border-black/5 p-3 dark:border-white/10">
      <textarea
        data-testid={testId}
        value={text}
        disabled={disabled}
        placeholder={
          streaming
            ? "回复生成中…"
            : disabled
              ? "另一会话回复生成中，稍候…"
              : "输入消息，Enter 发送，Shift+Enter 换行"
        }
        className="max-h-32 min-h-[44px] w-full resize-none rounded-xl border border-slate-300 bg-white/70 px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400 disabled:opacity-60 dark:border-slate-600 dark:bg-slate-800/70 dark:text-slate-200"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
      />
      <div className="mt-2 flex items-center justify-end gap-2">
        {streaming ? (
          <Button variant="danger" className="px-3 py-1 text-xs" onClick={onStop} data-testid="agent-stop">
            停止
          </Button>
        ) : (
          <>
            {onPropose ? (
              <Button
                variant="ghost"
                className="px-3 py-1 text-xs"
                disabled={disabled || !text.trim()}
                data-testid="agent-propose"
                onClick={() => {
                  const trimmed = text.trim();
                  if (!trimmed) return;
                  onPropose(trimmed);
                  setText("");
                }}
              >
                产出草案
              </Button>
            ) : null}
            <Button
              className="px-3 py-1 text-xs"
              disabled={disabled || !text.trim()}
              data-testid={`${testId}-send`}
              onClick={submit}
            >
              发送
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
