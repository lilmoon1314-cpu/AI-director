/**
 * AgentDock 侧边栏（F10，DESIGN.md §5.5）：图谱/资产页右上「💬 Agent」浮钮
 * （testid agent-dock-toggle）或 Ctrl/⌘+J 唤起；右滑入 w-[400px] 全高面板，
 * 非模态（z-30，面板 10 < Dock 30 < 查看器 50）；与 AgentHome 复用同一会话池
 * 与会话视图——收起不中断流式（SSE 生命周期挂会话级）。
 */

import { useEffect, useState } from "react";

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

  // Dock 面板打开时确保会话池就绪（页签间共享 store，已加载则跳过）
  useEffect(() => {
    if (dockOpen) void loadSessions(projectId);
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

  // Dock 展示的会话：优先流式中的会话（收起再打开不丢现场），否则最近一个
  const activeSessionId = streamingSessionId ?? sessions[0]?.id ?? null;

  const createAndShow = async () => {
    setCreating(true);
    try {
      await createSession(projectId);
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
          className="fixed right-3 top-16 bottom-3 z-30 flex w-[400px] flex-col overflow-hidden p-0"
          data-testid="agent-dock"
        >
          <div className="flex shrink-0 items-center justify-between border-b border-black/5 px-4 py-2 dark:border-white/10">
            <p className="text-sm font-medium text-slate-800 dark:text-slate-200">💬 Agent</p>
            <Button variant="ghost" className="px-2 py-0.5 text-xs" onClick={closeDock} data-testid="agent-dock-close">
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
              <Button data-testid="agent-dock-create" disabled={creating} onClick={() => void createAndShow()}>
                ＋ 新对话
              </Button>
            </div>
          )}
        </GlassPanel>
      ) : null}
    </>
  );
}
