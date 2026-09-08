/**
 * Agent 对话主页（F10，DESIGN.md §5.4 /projects/:id/agent）：
 * 左栏 = 会话列表 + 记忆文档区；右栏 = 欢迎页（大输入框，发送即建会话）
 * 或会话视图（/agent/s/:sessionId，URL 即状态）。
 * 项目切换重置换机：本视图挂载时按 sessionsProjectId 陈旧检测执行
 * （GraphView 的置换链覆盖不到 Agent 页签驻留场景）。
 */

import { useEffect, useState } from "react";
import { useNavigate, useOutletContext, useParams } from "react-router-dom";

import { GlassPanel } from "../ui/GlassPanel";
import { ErrorStrip } from "../ui/ErrorStrip";
import { Button } from "../ui/Button";
import { MemoryDocsArea } from "./MemoryDocsArea";
import { SessionList } from "./SessionList";
import { SessionView } from "./SessionView";
import { useAgentStore, type PerspectiveValue } from "../../stores/agentStore";
import { usePerspectiveStore } from "../../stores/perspectiveStore";
import { useProjectStore } from "../../stores/projectStore";

export function AgentHome() {
  const { projectId } = useOutletContext<{ projectId: string }>();
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const projectName = useProjectStore((s) => s.projects.find((p) => p.id === projectId)?.name ?? projectId);

  const sessions = useAgentStore((s) => s.sessions);
  const sessionsError = useAgentStore((s) => s.sessionsError);
  const docs = useAgentStore((s) => s.docs);
  const docsLoading = useAgentStore((s) => s.docsLoading);
  const docsError = useAgentStore((s) => s.docsError);
  const loadSessions = useAgentStore((s) => s.loadSessions);
  const createSession = useAgentStore((s) => s.createSession);
  const loadDocs = useAgentStore((s) => s.loadDocs);
  const createDoc = useAgentStore((s) => s.createDoc);
  const deleteSession = useAgentStore((s) => s.deleteSession);
  const deleteDoc = useAgentStore((s) => s.deleteDoc);
  const resetProjectScoped = useAgentStore((s) => s.resetProjectScoped);
  const sendMessage = useAgentStore((s) => s.sendMessage);
  const [creatingSession, setCreatingSession] = useState(false);
  const [creatingDoc, setCreatingDoc] = useState(false);
  const [welcomeText, setWelcomeText] = useState("");

  useEffect(() => {
    // 陈旧检测：store 缓存属于另一项目（本页签驻留期间切换项目）→ 置换后再加载
    const cached = useAgentStore.getState().sessionsProjectId;
    if (cached !== null && cached !== projectId) resetProjectScoped();
    void loadSessions(projectId);
    void loadDocs(projectId);
  }, [projectId, loadSessions, loadDocs, resetProjectScoped]);

  const createAndOpen = async (): Promise<string | null> => {
    setCreatingSession(true);
    try {
      const session = await createSession(projectId);
      navigate(`/projects/${projectId}/agent/s/${session.id}`);
      return session.id;
    } catch {
      return null;
    } finally {
      setCreatingSession(false);
    }
  };

  const sendWelcome = async () => {
    const text = welcomeText.trim();
    if (!text) return;
    const created = await createAndOpen();
    if (!created) return;
    const { perspective, characterId } = usePerspectiveStore.getState();
    await sendMessage(created, text, perspective as PerspectiveValue, characterId ?? "");
  };

  return (
    <div className="flex min-h-0 flex-1 gap-3" data-testid="agent-home">
      {/* 左栏 */}
      <GlassPanel className="flex w-72 shrink-0 flex-col gap-3 p-3">
        <SessionList
          sessions={sessions}
          activeId={sessionId ?? null}
          creating={creatingSession}
          onCreate={() => void createAndOpen()}
          onDelete={(id) => {
            void deleteSession(id);
            // 删除的是当前打开的会话 → 退回 Agent 主页（URL 即状态）
            if (sessionId === id) navigate(`/projects/${projectId}/agent`);
          }}
        />
        {sessionsError ? (
          <ErrorStrip
            problem={sessionsError.problem}
            fix={sessionsError.fix}
            onRetry={() => void loadSessions(projectId, true)}
            testId="agent-sessions-error"
          />
        ) : null}
        <MemoryDocsArea
          docs={docs}
          loading={docsLoading}
          error={docsError}
          onRetry={() => void loadDocs(projectId, true)}
          onCreate={(kind) => {
            setCreatingDoc(true);
            void createDoc(kind, projectId).finally(() => setCreatingDoc(false));
          }}
          onDeleteDoc={(docId) => void deleteDoc(docId, projectId)}
          creating={creatingDoc}
          projectId={projectId}
        />
      </GlassPanel>

      {/* 右栏 */}
      <GlassPanel className="flex min-h-0 flex-1 flex-col overflow-hidden">
        {sessionId ? (
          <SessionView conversationId={sessionId} />
        ) : (
          <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-6 p-8">
            <div className="text-center">
              <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
                ✦ {projectName} · Agent
              </h1>
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                与创作助理对话：梳理设定、查询图谱、产出写入草案。左栏可维护记忆文档。
              </p>
            </div>
            <div className="w-full max-w-xl">
              <textarea
                data-testid="agent-input"
                value={welcomeText}
                onChange={(e) => setWelcomeText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void sendWelcome();
                  }
                }}
                placeholder="描述你想创作的内容，Enter 发送…"
                className="max-h-40 min-h-24 w-full resize-none rounded-2xl border border-slate-300 bg-white/70 px-4 py-3 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400 dark:border-slate-600 dark:bg-slate-800/70 dark:text-slate-200"
              />
              <div className="mt-2 flex justify-end">
                <Button data-testid="agent-input-send" disabled={!welcomeText.trim()} onClick={() => void sendWelcome()}>
                  发送
                </Button>
              </div>
            </div>
          </div>
        )}
      </GlassPanel>
    </div>
  );
}
