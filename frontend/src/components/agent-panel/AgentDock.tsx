/**
 * AgentDock 侧边栏（F10/F13，DESIGN.md §5.5/§13.1）：图谱/资产页右上「💬 Agent」
 * 浮钮（testid agent-dock-toggle）或 Ctrl/⌘+J 唤起；右滑入 w-[400px] 全高面板，
 * 非模态（z-30，面板 10 < Dock 30 < 查看器 50）；与 AgentHome 复用同一会话池
 * 与会话视图——收起不中断流式（SSE 生命周期挂会话级）。
 * F13 遗留交互兑现：顶部会话切换下拉（agent-dock-session-select）+「＋新会话」
 * 常驻（agent-dock-create）；焦点在 Dock 内按 Esc 收起。
 */

import { useEffect, useRef, useState } from "react";

import { Button } from "../ui/Button";
import { GlassPanel } from "../ui/GlassPanel";
import { SessionView } from "./SessionView";
import { useAgentStore } from "../../stores/agentStore";

export function AgentDock({ projectId }: { projectId: string }) {
  const dockOpen = useAgentStore((s) => s.dockOpen);
  const openDock = useAgentStore((s) => s.openDock);
  const closeDock = useAgentStore((s) => s.closeDock);
  const sessions = useAgentStore((s) => s.sessions);
  const loadSessions = useAgentStore((s) => s.loadSessions);
  const createSession = useAgentStore((s) => s.createSession);
  const streamingSessionId = useAgentStore((s) => s.streamingSessionId);
  const [creating, setCreating] = useState(false);
  // 用户显式选择的会话（下拉驱动）；null 时回退流式会话/最近会话
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  // Dock 面板打开时确保会话池就绪（页签间共享 store，已加载则跳过）+ 聚焦以承接 Esc
  useEffect(() => {
    if (dockOpen) {
      void loadSessions(projectId);
      panelRef.current?.focus();
    }
  }, [dockOpen, projectId, loadSessions]);

  // Ctrl/⌘+J 唤起/收起（DESIGN.md §5.5 键盘可达）
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "j") {
        e.preventDefault();
        if (useAgentStore.getState().dockOpen) closeDock();
        else openDock();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [openDock, closeDock]);

  // 展示的会话：显式选择 > 流式中的会话（收起再打开不丢现场）> 最近一个；
  // 显式选择已不存在（被删除）时自动回退
  const selectedExists = selectedId ? sessions.some((s) => s.id === selectedId) : false;
  const activeSessionId =
    (selectedExists ? selectedId : null) ?? streamingSessionId ?? sessions[0]?.id ?? null;

  const createAndShow = async () => {
    setCreating(true);
    try {
      const created = await createSession(projectId);
      setSelectedId(created.id);
    } finally {
      setCreating(false);
    }
  };

  return (
    <>
      {!dockOpen ? (
        <button
          type="button"
          data-testid="agent-dock-toggle"
          onClick={openDock}
          className="fixed right-4 top-20 z-20 rounded-full bg-slate-800 px-4 py-2 text-sm text-white shadow-md transition-all duration-150 hover:-translate-y-0.5 hover:shadow-lg dark:bg-slate-200 dark:text-slate-900"
        >
          💬 Agent
        </button>
      ) : null}
      {dockOpen ? (
        <GlassPanel
          className="fixed right-3 top-16 bottom-3 z-30 flex w-[400px] flex-col overflow-hidden p-0 outline-none"
          data-testid="agent-dock"
        >
          <div
            ref={panelRef}
            tabIndex={-1}
            data-testid="agent-dock-header"
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                e.stopPropagation();
                closeDock();
              }
            }}
            className="flex shrink-0 items-center gap-2 border-b border-black/5 px-3 py-2 outline-none dark:border-white/10"
          >
            <p className="shrink-0 text-sm font-medium text-slate-800 dark:text-slate-200">💬</p>
            <select
              data-testid="agent-dock-session-select"
              aria-label="切换会话"
              value={activeSessionId ?? ""}
              onChange={(e) => setSelectedId(e.target.value)}
              className="min-w-0 flex-1 truncate rounded-lg border border-slate-300 bg-white/80 px-2 py-1 text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-slate-400 dark:border-slate-600 dark:bg-slate-900/70 dark:text-slate-200"
            >
              {sessions.length === 0 ? <option value="">（暂无会话）</option> : null}
              {sessions.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.title || "未命名对话"}
                </option>
              ))}
            </select>
            <Button
              variant="ghost"
              className="shrink-0 px-2 py-0.5 text-xs"
              disabled={creating}
              onClick={() => void createAndShow()}
              data-testid="agent-dock-create"
            >
              ＋
            </Button>
            <Button variant="ghost" className="shrink-0 px-2 py-0.5 text-xs" onClick={closeDock} data-testid="agent-dock-close">
              收起
            </Button>
          </div>
          {activeSessionId ? (
            <SessionView conversationId={activeSessionId} testId="agent-dock-input" />
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
              <p className="text-sm text-slate-500 dark:text-slate-400">
                当前项目还没有会话——新建一个，或到 Agent 主页查看记忆文档。
              </p>
              <Button data-testid="agent-dock-create-empty" disabled={creating} onClick={() => void createAndShow()}>
                ＋ 新对话
              </Button>
            </div>
          )}
        </GlassPanel>
      ) : null}
    </>
  );
}
