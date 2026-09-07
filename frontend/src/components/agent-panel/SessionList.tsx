/**
 * 会话列表（F10，DESIGN.md §5.4 左栏）：＋新对话 + 按「今天 / 7 天内 / 更早」
 * 分组的会话列表（最近活跃在前，后端契约）；点击切换会话路由。
 */

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
}: {
  sessions: SessionRead[];
  activeId: string | null;
  onCreate: () => void;
  creating: boolean;
}) {
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
                  <li key={session.id}>
                    <Link
                      to={`../agent/s/${session.id}`}
                      data-testid="agent-session-item"
                      className={`block truncate rounded-lg px-2 py-1.5 text-sm transition-colors duration-150 ${
                        session.id === activeId
                          ? "bg-slate-800/90 text-white dark:bg-slate-200 dark:text-slate-900"
                          : "text-slate-700 hover:bg-white/60 dark:text-slate-300 dark:hover:bg-slate-800/60"
                      }`}
                      title={session.title || "未命名对话"}
                    >
                      {session.title || "未命名对话"}
                    </Link>
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
