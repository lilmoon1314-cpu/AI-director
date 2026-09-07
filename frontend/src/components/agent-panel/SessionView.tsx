/**
 * 会话视图（F10）：消息流 + 草案确认卡 + 输入框的组合——AgentHome 会话路由
 * 与 AgentDock 复用（同一会话池，DESIGN.md 决策②）。视角随 perspectiveStore
 * 当前值透传（上下文经视角过滤）。
 */

import { useEffect } from "react";

import { useAgentStore, type PerspectiveValue } from "../../stores/agentStore";
import { usePerspectiveStore } from "../../stores/perspectiveStore";
import { ChatInput } from "./ChatInput";
import { DraftConfirmCard } from "./DraftConfirmCard";
import { MessageList } from "./MessageList";

/** 稳定空数组（selector 返回新引用会触发 useSyncExternalStore 无限循环警告）。 */
const EMPTY_DRAFTS: never[] = [];

export function SessionView({ conversationId, testId = "agent-input" }: { conversationId: string; testId?: string }) {
  const messages = useAgentStore((s) => s.messagesBySession[conversationId]);
  const messagesLoading = useAgentStore((s) => s.messagesLoading);
  const streaming = useAgentStore((s) => s.streamingSessionId === conversationId);
  const toolActivity = useAgentStore((s) => s.toolActivity);
  const error = useAgentStore((s) => s.sessionErrors[conversationId] ?? null);
  const drafts = useAgentStore((s) => s.draftsBySession[conversationId] ?? EMPTY_DRAFTS);
  const confirming = useAgentStore((s) => s.confirming);
  const loadMessages = useAgentStore((s) => s.loadMessages);
  const sendMessage = useAgentStore((s) => s.sendMessage);
  const stopStreaming = useAgentStore((s) => s.stopStreaming);
  const proposeDrafts = useAgentStore((s) => s.proposeDrafts);
  const confirmDrafts = useAgentStore((s) => s.confirmDrafts);
  const discardDrafts = useAgentStore((s) => s.discardDrafts);

  useEffect(() => {
    void loadMessages(conversationId);
  }, [conversationId, loadMessages]);

  const withPerspective = () => {
    const { perspective, characterId } = usePerspectiveStore.getState();
    return {
      perspective: perspective as PerspectiveValue,
      characterId: characterId ?? "",
    };
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col" data-testid="agent-session-view">
      <MessageList
        messages={messages ?? []}
        loading={messagesLoading}
        toolActivity={streaming ? toolActivity : null}
        error={error}
        onErrorRetry={() => void loadMessages(conversationId, true)}
      />
      <DraftConfirmCard
        drafts={drafts}
        confirming={confirming}
        onConfirm={() => void confirmDrafts(conversationId)}
        onDiscard={() => discardDrafts(conversationId)}
      />
      <ChatInput
        testId={testId}
        disabled={false}
        streaming={streaming}
        onSend={(text) => {
          const { perspective, characterId } = withPerspective();
          void sendMessage(conversationId, text, perspective, characterId);
        }}
        onPropose={(text) => {
          const { perspective, characterId } = withPerspective();
          void proposeDrafts(conversationId, text, perspective, characterId);
        }}
        onStop={() => stopStreaming(conversationId)}
      />
    </div>
  );
}
