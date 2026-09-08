/**
 * 会话列表（F10/F13，DESIGN.md §5.4/§13.1 左栏）：＋新对话 + 按「今天 / 7 天内 /
 * 更早」分组的会话列表（最近活跃在前，后端契约）；点击切换会话路由。
 * 删除（反馈②）：条目 hover 出现 🗑 → 展开行内确认（输入会话标题确认，
 * 对齐项目删除模式；未命名会话输入「未命名对话」）→ 确认后回调删除。
 */

import { useState } from "react";
import { Link } from "react-router-dom";

import type { SessionRead } from "../../api/client";
import { Button } from "../ui/Button";

function groupLabel(updatedAt: string): "今天" | "7 天内" | "更早" {
  const updated = new Date(updatedAt).getTime();
  const now = Date.now();
  const dayStart = new Date();
  dayStart.setHours(0, 0, 0, 0);
  if (updated >= dayStart.getTime()) return "今天";
  if (now - updated <= 7 * 24 * 3600 * 1000) return "7 天内";
  return "更早";
}

const GROUP_ORDER = ["今天", "7 天内", "更早"] as const;

export function SessionList({
  sessions,
  activeId,
  onCreate,
  creating,
  onDelete,
}: {
  sessions: SessionRead[];
  activeId: string | null;
  onCreate: () => void;
  creating: boolean;
  /** 确认删除回调（输入标题校验通过后触发；导航清理由调用方处理）。 */
  onDelete: (sessionId: string) => void;
}) {
  // 行内删除确认态：confirmId 非空时该条目展开输入行
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [confirmText, setConfirmText] = useState("");

  const startConfirm = (session: SessionRead) => {
    setConfirmId(session.id);
    setConfirmText("");
  };

  const expectedText = (session: SessionRead) => session.title || "未命名对话";

  return (
    <div className="flex min-h-0 flex-col gap-2" data-testid="agent-session-list">
      <Button className="w-full px-3 py-1.5 text-xs" onClick={onCreate} disabled={creating} data-testid="agent-session-create">
        ＋ 新对话
      </Button>
      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        {GROUP_ORDER.map((group) => {
          const items = sessions.filter((s) => groupLabel(s.updated_at) === group);
          if (items.length === 0) return null;
          return (
            <div key={group} className="mt-2">
              <p className="px-2 text-xs text-slate-400 dark:text-slate-500">{group}</p>
              <ul className="mt-1">
                {items.map((session) => (
                  <li key={session.id} className="group relative">
                    <Link
                      to={`../agent/s/${session.id}`}
                      data-testid="agent-session-item"
                      className={`block truncate rounded-lg pr-7 pl-2 py-1.5 text-sm transition-colors duration-150 ${
                        session.id === activeId
                          ? "bg-slate-800/90 text-white dark:bg-slate-200 dark:text-slate-900"
                          : "text-slate-700 hover:bg-white/60 dark:text-slate-300 dark:hover:bg-slate-800/60"
                      }`}
                      title={session.title || "未命名对话"}
                    >
                      {session.title || "未命名对话"}
                    </Link>
                    {confirmId !== session.id ? (
                      <button
                        type="button"
                        data-testid="agent-session-delete"
                        aria-label={`删除会话 ${session.title || "未命名对话"}`}
                        onClick={() => startConfirm(session)}
                        className="absolute top-1/2 right-1 -translate-y-1/2 rounded px-1 text-xs text-slate-400 opacity-0 transition-all duration-150 group-hover:opacity-100 hover:text-red-500 focus-visible:opacity-100 dark:text-slate-500 dark:hover:text-red-400"
                      >
                        🗑
                      </button>
                    ) : null}
                    {confirmId === session.id ? (
                      <div className="mt-1 rounded-lg bg-white/70 p-2 ring-1 ring-black/10 dark:bg-slate-800/70 dark:ring-white/10" data-testid="agent-session-delete-panel">
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          输入「{expectedText(session)}」确认删除：
                        </p>
                        <input
                          data-testid="agent-session-delete-input"
                          value={confirmText}
                          onChange={(e) => setConfirmText(e.target.value)}
                          placeholder={expectedText(session)}
                          className="mt-1 w-full rounded-md border border-slate-300 bg-white/80 px-2 py-1 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-slate-400 dark:border-slate-600 dark:bg-slate-900/60 dark:text-slate-200"
                        />
                        <div className="mt-1.5 flex justify-end gap-1">
                          <Button
                            variant="ghost"
                            className="px-2 py-0.5 text-xs"
                            data-testid="agent-session-delete-cancel"
                            onClick={() => setConfirmId(null)}
                          >
                            取消
                          </Button>
                          <Button
                            className="px-2 py-0.5 text-xs"
                            data-testid="agent-session-delete-confirm"
                            disabled={confirmText !== expectedText(session)}
                            onClick={() => {
                              onDelete(session.id);
                              setConfirmId(null);
                            }}
                          >
                            删除
                          </Button>
                        </div>
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
        {sessions.length === 0 ? (
          <p className="mt-4 px-2 text-xs text-slate-400 dark:text-slate-500">暂无会话</p>
        ) : null}
      </div>
    </div>
  );
}
