/**
 * agentStore：Agent 对话与记忆文档全局状态（F10/F13/F14，DESIGN.md §5.4/§5.5/§13.1/§13.2）。
 * - 按项目的会话池（sessions + messagesBySession）；草案两段式（draftsBySession，legacy）；
 * - **SSE 生命周期挂会话级**：AbortController 由 store 持有——切会话、AgentDock
 *   收起、组件卸载均不断流；中断仅发生于显式停止与项目切换。全局同一时刻
 *   至多一轮流式（他会议流式中时输入层禁用，sendMessage 守卫兜底拒绝）；
 * - F14 轮末统一确认：done 事件携带 pending_writes 清单 → pendingBySession
 *   （确认卡数据源）→ approve 服务端二次校验落库 → 图谱/文档失效刷新；
 * - confirm（legacy）成功后同样广播图谱失效（graphStore.loadGraph 重载）。
 * 事件协议（agent/ARCHITECTURE.md）：message_start/token/reasoning/usage/tool/
 * done(含 pending_writes?)/error；draft/doc_patch/ask_user 为预留类型——本
 * store 忽略不渲染（前向兼容）。reasoning 增量累积进 assistant 消息
 * （ThinkingBlock 数据源），usage 写入 usageBySession（UsageBar 容量窗口）。
 * 约束：全部 async action 必须有 catch 并落三要素错误态（E16，frontend/CONSTRAINTS.md）。
 */

import { create } from "zustand";

import {
  api,
  agentChatPath,
  ApiError,
  type DraftItem,
  type MemoryDocBrief,
  type PendingWriteRead,
  type SessionRead,
} from "../api/client";
import { useGraphStore } from "./graphStore";
import { useProjectStore } from "./projectStore";

/** 三要素错误态（problem+fix 呈现；cause 由后端承载）。 */
export interface AgentErrorState {
  problem: string;
  fix: string;
}

export interface AgentMessage {
  id: string;
  role: "user" | "assistant" | "summary" | "tool";
  content: string;
  /** 思考过程（真流式 reasoning 增量累积 / 历史回读；user 行为 null）。 */
  reasoning?: string | null;
  /** 思考耗时秒数（本轮实测：首条 reasoning 至首个 token 的墙钟差；历史消息缺省）。 */
  reasoningSeconds?: number;
  /** 本轮 LLM usage（历史回读；null=端点未返回）。 */
  promptTokens?: number | null;
  completionTokens?: number | null;
  /** SSE 流式进行中的消息（光标动画渲染依据）。 */
  streaming?: boolean;
}

/** 本轮 usage 事件载荷（usageBySession 值；UsageBar 容量窗口数据源）。 */
export interface TurnUsage {
  promptTokens: number | null;
  completionTokens: number | null;
  contextMaxTokens: number | null;
  contextRatio: number | null;
}

export type PerspectiveValue = "author" | "character" | "audience";

function toErrorState(cause: unknown, fallbackProblem: string): AgentErrorState {
  const err = cause instanceof ApiError ? cause : null;
  return {
    problem: err?.problem ?? fallbackProblem,
    fix: err?.fix ?? "确认后端服务已启动后重试",
  };
}

/** SSE 会话级中断控制器（模块私有，不进可序列化状态）。 */
const abortControllers = new Map<string, AbortController>();

/** 解析 fetch 流为 SSE 事件（帧以空行分隔；事件名 + JSON data）。 */
async function* parseSse(response: Response): AsyncGenerator<{ event: string; data: Record<string, unknown> }> {
  const reader = response.body?.getReader();
  if (!reader) return;
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      let event = "message";
      let data = "";
      for (const line of frame.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7);
        else if (line.startsWith("data: ")) data = line.slice(6);
      }
      try {
        yield { event, data: JSON.parse(data) as Record<string, unknown> };
      } catch {
        // 心跳/畸形帧忽略（后端不发送，防御代理层噪声）
      }
      boundary = buffer.indexOf("\n\n");
    }
  }
}

interface AgentState {
  sessions: SessionRead[];
  sessionsProjectId: string | null;
  sessionsLoading: boolean;
  sessionsError: AgentErrorState | null;
  messagesBySession: Record<string, AgentMessage[]>;
  messagesLoading: boolean;
  /** 正在流式输出的会话（全局唯一：同一时刻至多一轮对话）。 */
  streamingSessionId: string | null;
  /** 检索行为指示（tool 事件驱动：「正在检索图谱…」）。 */
  toolActivity: { name: string; phase: "start" | "done" } | null;
  /** SSE error 事件 / 请求失败的三要素错误（按会话隔离）。 */
  sessionErrors: Record<string, AgentErrorState | null>;
  /** 本轮 usage（usage 事件写入，done 后保留至下一轮覆盖；UsageBar 数据源）。 */
  usageBySession: Record<string, TurnUsage>;
  draftsBySession: Record<string, DraftItem[]>;
  confirming: boolean;
  /** F14 待写入确认：done 事件清单按会话累积（确认卡数据源）。 */
  pendingBySession: Record<string, PendingWriteRead[]>;
  /** approve 请求进行中（按钮防重复提交）。 */
  approving: boolean;
  docs: MemoryDocBrief[];
  docsLoading: boolean;
  docsError: AgentErrorState | null;
  /** AgentDock 侧边栏开合（全局：页签间保持状态）。 */
  dockOpen: boolean;
  openDock: () => void;
  closeDock: () => void;
  loadSessions: (projectId: string, force?: boolean) => Promise<void>;
  createSession: (projectId: string) => Promise<SessionRead>;
  /** 删除会话（消息经后端级联清理；本地缓存一并移除）。 */
  deleteSession: (conversationId: string) => Promise<void>;
  loadMessages: (conversationId: string, force?: boolean) => Promise<void>;
  /** 发送一条消息并消费 SSE 事件流（会话级生命周期，可 stopStreaming 中断）。 */
  sendMessage: (
    conversationId: string,
    message: string,
    perspective: PerspectiveValue,
    characterId?: string,
  ) => Promise<void>;
  stopStreaming: (conversationId: string) => void;
  /** 生成写入草案（propose；草案卡内联渲染，确认走 confirmDrafts）。 */
  proposeDrafts: (
    conversationId: string,
    message: string,
    perspective: PerspectiveValue,
    characterId?: string,
  ) => Promise<void>;
  confirmDrafts: (conversationId: string) => Promise<void>;
  discardDrafts: (conversationId: string) => void;
  /** F14：批量批准待写入（只提交勾选 ids；图谱/文档失效刷新）。 */
  approvePendingWrites: (conversationId: string, ids: string[]) => Promise<void>;
  /** F14：放弃待写入（置 rejected；本地移除）。 */
  rejectPendingWrites: (conversationId: string, ids: string[]) => Promise<void>;
  loadDocs: (projectId: string, force?: boolean) => Promise<void>;
  createDoc: (kind: string, projectId: string) => Promise<void>;
  /** 删除记忆文档（段经后端级联清理；成功后刷新列表）。 */
  deleteDoc: (docId: string, projectId: string) => Promise<void>;
  updateDocSection: (
    docId: string,
    sectionId: string,
    content: string,
    expectedVersion: number,
  ) => Promise<void>;
  resetProjectScoped: () => void;
}

let localIdCounter = 0;
function localId(prefix: string): string {
  localIdCounter += 1;
  return `${prefix}-local-${localIdCounter}`;
}

export const useAgentStore = create<AgentState>((set, get) => ({
  sessions: [],
  sessionsProjectId: null,
  sessionsLoading: false,
  sessionsError: null,
  messagesBySession: {},
  messagesLoading: false,
  streamingSessionId: null,
  toolActivity: null,
  sessionErrors: {},
  usageBySession: {},
  draftsBySession: {},
  confirming: false,
  pendingBySession: {},
  approving: false,
  docs: [],
  docsLoading: false,
  docsError: null,
  dockOpen: false,
  openDock: () => set({ dockOpen: true }),
  closeDock: () => set({ dockOpen: false }),

  loadSessions: async (projectId, force = false) => {
    if (!force && get().sessions.length > 0 && get().sessionsProjectId === projectId) return;
    set({ sessionsLoading: true, sessionsError: null });
    try {
      const sessions = await api.listSessions(projectId);
      set({ sessions, sessionsProjectId: projectId });
    } catch (cause) {
      set({ sessionsError: toErrorState(cause, "会话列表加载失败") });
    } finally {
      set({ sessionsLoading: false });
    }
  },

  createSession: async (projectId) => {
    const session = await api.createSession(projectId);
    set({ sessions: [session, ...get().sessions] });
    return session;
  },

  deleteSession: async (conversationId) => {
    // 删除命中流式中的会话先中断 SSE（会话不复存在，流必须停；审查 P2-2）
    if (get().streamingSessionId === conversationId) {
      abortControllers.get(conversationId)?.abort();
    }
    try {
      await api.deleteSession(conversationId);
      const messagesBySession = { ...get().messagesBySession };
      delete messagesBySession[conversationId];
      const usageBySession = { ...get().usageBySession };
      delete usageBySession[conversationId];
      set({
        sessions: get().sessions.filter((s) => s.id !== conversationId),
        messagesBySession,
        usageBySession,
        sessionErrors: { ...get().sessionErrors, [conversationId]: null },
      });
    } catch (cause) {
      set({ sessionsError: toErrorState(cause, "会话删除失败") });
    }
  },

  loadMessages: async (conversationId, force = false) => {
    if (!force && (get().messagesBySession[conversationId]?.length ?? 0) > 0) return;
    // 流式进行中禁止回读覆盖（挂载效应与乐观更新的竞态会把缓冲冲掉）——
    // done 事件后的 force 回读是唯一权威写入方
    if (!force && get().streamingSessionId === conversationId) return;
    set({ messagesLoading: true });
    try {
      const rows = await api.listMessages(conversationId);
      set({
        messagesBySession: {
          ...get().messagesBySession,
          [conversationId]: rows.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            reasoning: m.reasoning ?? null,
            promptTokens: m.prompt_tokens ?? null,
            completionTokens: m.completion_tokens ?? null,
          })),
        },
      });
    } finally {
      set({ messagesLoading: false });
    }
  },

  sendMessage: async (conversationId, message, perspective, characterId) => {
    // 全局单流守卫（UI 层已在他会议流式时禁用输入；此处兜底拒绝重复轮，
    // 拒绝时不清空任何状态——输入保留由调用方在守卫前置 disabled 保证）
    if (get().streamingSessionId) return;
    const controller = new AbortController();
    abortControllers.set(conversationId, controller);
    const assistantLocalId = localId("msg");
    set({
      streamingSessionId: conversationId,
      toolActivity: null,
      sessionErrors: { ...get().sessionErrors, [conversationId]: null },
      messagesBySession: {
        ...get().messagesBySession,
        [conversationId]: [
          ...(get().messagesBySession[conversationId] ?? []),
          { id: localId("msg"), role: "user", content: message },
          { id: assistantLocalId, role: "assistant", content: "", streaming: true },
        ],
      },
    });

    const patchAssistant = (patch: Partial<AgentMessage>) => {
      const list = get().messagesBySession[conversationId] ?? [];
      set({
        messagesBySession: {
          ...get().messagesBySession,
          [conversationId]: list.map((m) => (m.id === assistantLocalId ? { ...m, ...patch } : m)),
        },
      });
    };

    let streamed = "";
    let reasoningBuf = "";
    // 思考耗时：首条 reasoning 至首个 token 的墙钟差（「已思考 N 秒」数据源）
    let reasoningStartedAt: number | null = null;
    let reasoningSeconds: number | undefined;
    try {
      const resp = await fetch(agentChatPath(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversation_id: conversationId,
          message,
          perspective,
          character_id: characterId ?? "",
        }),
        signal: controller.signal,
      });
      if (!resp.ok || !resp.body) {
        let body: Record<string, unknown> = {};
        try {
          body = (await resp.json()) as Record<string, unknown>;
        } catch {
          // 非 JSON 错误体（代理层）→ 占位三要素
        }
        throw new ApiError(resp.status, body);
      }
      for await (const { event, data } of parseSse(resp)) {
        if (event === "token") {
          if (reasoningStartedAt !== null && reasoningSeconds === undefined) {
            reasoningSeconds = Math.max(1, Math.round((Date.now() - reasoningStartedAt) / 1000));
          }
          streamed += String(data.text ?? "");
          patchAssistant({
            content: streamed,
            reasoning: reasoningBuf || null,
            reasoningSeconds,
          });
        } else if (event === "reasoning") {
          if (reasoningStartedAt === null) reasoningStartedAt = Date.now();
          reasoningBuf += String(data.text ?? "");
          patchAssistant({ reasoning: reasoningBuf });
        } else if (event === "usage") {
          set({
            usageBySession: {
              ...get().usageBySession,
              [conversationId]: {
                promptTokens: (data.prompt_tokens as number | null | undefined) ?? null,
                completionTokens: (data.completion_tokens as number | null | undefined) ?? null,
                contextMaxTokens: (data.context_max_tokens as number | null | undefined) ?? null,
                contextRatio: (data.context_ratio as number | null | undefined) ?? null,
              },
            },
          });
        } else if (event === "tool") {
          set({ toolActivity: { name: String(data.name ?? ""), phase: "start" } });
        } else if (event === "error") {
          set({
            sessionErrors: {
              ...get().sessionErrors,
              [conversationId]: {
                problem: String(data.problem ?? "对话处理失败"),
                fix: String(data.fix ?? "重试；持续失败请检查服务端日志"),
              },
            },
          });
        } else if (event === "done") {
          // F14：done 携带本轮待写入清单（无写入时无该键）——累积进确认卡
          const pending = data.pending_writes as PendingWriteRead[] | undefined;
          if (pending && pending.length > 0) {
            set({
              pendingBySession: {
                ...get().pendingBySession,
                [conversationId]: [...(get().pendingBySession[conversationId] ?? []), ...pending],
              },
            });
          }
          // 以服务端落库结果为准回读（标题/消息 id 对齐）
          await get().loadMessages(conversationId, true);
        }
        // draft / doc_patch / ask_user：F14 预留事件——忽略（前向兼容）
      }
    } catch (cause) {
      if (!(cause instanceof DOMException && cause.name === "AbortError")) {
        set({
          sessionErrors: {
            ...get().sessionErrors,
            [conversationId]: toErrorState(cause, "对话请求失败"),
          },
        });
      }
    } finally {
      // 收尾：结束流式态；未回读成功（中断/错误）时保留本地缓冲但去掉 streaming 标记
      abortControllers.delete(conversationId);
      const list = get().messagesBySession[conversationId] ?? [];
      set({
        streamingSessionId: null,
        toolActivity: null,
        messagesBySession: {
          ...get().messagesBySession,
          [conversationId]: list.map((m) =>
            m.id === assistantLocalId && m.content === "" ? { ...m, content: "（未产生回复）", streaming: false } : { ...m, streaming: false },
          ),
        },
      });
    }
  },

  stopStreaming: (conversationId) => {
    abortControllers.get(conversationId)?.abort();
  },

  proposeDrafts: async (conversationId, message, perspective, characterId) => {
    try {
      const response = await api.propose({
        session_id: conversationId,
        message,
        perspective,
        character_id: characterId ?? "",
      });
      set({
        draftsBySession: { ...get().draftsBySession, [conversationId]: response.drafts ?? [] },
        messagesBySession: {
          ...get().messagesBySession,
          [conversationId]: [
            ...(get().messagesBySession[conversationId] ?? []),
            { id: localId("msg"), role: "user", content: message },
          ],
        },
        sessionErrors: { ...get().sessionErrors, [conversationId]: null },
      });
    } catch (cause) {
      set({
        sessionErrors: {
          ...get().sessionErrors,
          [conversationId]: toErrorState(cause, "草案生成失败"),
        },
      });
    }
  },

  confirmDrafts: async (conversationId) => {
    const drafts = get().draftsBySession[conversationId] ?? [];
    if (drafts.length === 0) return;
    set({ confirming: true });
    try {
      const result = await api.confirmDrafts({
        session_id: conversationId,
        items: drafts.map((d) => ({
          draft_id: d.draft_id,
          kind: d.kind as "entity" | "relation",
          payload: d.payload as Record<string, unknown>,
          confirmed: true,
        })),
      });
      const ok = result.created?.length ?? 0;
      const failedItems = result.failed ?? [];
      const bad = failedItems.length;
      const summary =
        bad === 0
          ? `✓ 已写入 ${ok} 项草案。`
          : `✓ 写入 ${ok} 项，失败 ${bad} 项：${failedItems.map((f) => f.reason).join("；")}`;
      set({
        messagesBySession: {
          ...get().messagesBySession,
          [conversationId]: [
            ...(get().messagesBySession[conversationId] ?? []),
            { id: localId("msg"), role: "assistant", content: summary },
          ],
        },
        draftsBySession: { ...get().draftsBySession, [conversationId]: [] },
      });
      // 广播图谱失效：确认写入改变图谱数据（DESIGN.md §5.4 确认后失效链路）
      const projectId = useProjectStore.getState().currentProjectId;
      if (projectId) void useGraphStore.getState().loadGraph(projectId);
    } catch (cause) {
      set({
        sessionErrors: {
          ...get().sessionErrors,
          [conversationId]: toErrorState(cause, "确认写入失败"),
        },
      });
    } finally {
      set({ confirming: false });
    }
  },

  discardDrafts: (conversationId) => {
    set({ draftsBySession: { ...get().draftsBySession, [conversationId]: [] } });
  },

  approvePendingWrites: async (conversationId, ids) => {
    if (ids.length === 0) return;
    set({ approving: true });
    try {
      const result = await api.approvePendingWrites({ conversation_id: conversationId, ids });
      const failedIds = new Set((result.failed ?? []).map((f) => f.id));
      // 成功提交且成功的项移除；失败项与未提交勾选的项保留（仍在服务端
      // pending，作者可重试/放弃——误删会让登记行在 UI 上永久不可操作）
      const remaining = (get().pendingBySession[conversationId] ?? []).filter(
        (p) => !ids.includes(p.id) || failedIds.has(p.id),
      );
      set({
        pendingBySession: { ...get().pendingBySession, [conversationId]: remaining },
        sessionErrors: { ...get().sessionErrors, [conversationId]: null },
      });
      // 失败项三要素可读（挂在会话错误态，确认卡旁可见）
      if (failedIds.size > 0) {
        const reasons = (result.failed ?? []).map((f) => f.reason).join("；");
        set({
          sessionErrors: {
            ...get().sessionErrors,
            [conversationId]: { problem: "部分待写入未能落库", fix: reasons },
          },
        });
      }
      // 广播失效：图谱（新实体/关系）与文档列表（新文档/段写入）双刷新
      const projectId = useProjectStore.getState().currentProjectId;
      if (projectId) {
        void useGraphStore.getState().loadGraph(projectId);
        void get().loadDocs(projectId, true);
      }
    } catch (cause) {
      set({
        sessionErrors: {
          ...get().sessionErrors,
          [conversationId]: toErrorState(cause, "待写入确认失败"),
        },
      });
    } finally {
      set({ approving: false });
    }
  },

  rejectPendingWrites: async (conversationId, ids) => {
    if (ids.length === 0) return;
    try {
      await api.rejectPendingWrites({ conversation_id: conversationId, ids });
      set({
        pendingBySession: {
          ...get().pendingBySession,
          [conversationId]: (get().pendingBySession[conversationId] ?? []).filter(
            (p) => !ids.includes(p.id),
          ),
        },
      });
    } catch (cause) {
      set({
        sessionErrors: {
          ...get().sessionErrors,
          [conversationId]: toErrorState(cause, "放弃待写入失败"),
        },
      });
    }
  },

  loadDocs: async (projectId, force = false) => {
    if (!force && get().docs.length > 0 && get().sessionsProjectId === projectId) return;
    set({ docsLoading: true, docsError: null });
    try {
      const docs = await api.listMemoryDocs(projectId);
      set({ docs });
    } catch (cause) {
      set({ docsError: toErrorState(cause, "记忆文档加载失败") });
    } finally {
      set({ docsLoading: false });
    }
  },

  createDoc: async (kind, projectId) => {
    try {
      await api.createMemoryDoc(kind, projectId);
      await get().loadDocs(projectId, true);
    } catch (cause) {
      set({ docsError: toErrorState(cause, "记忆文档创建失败") });
    }
  },

  deleteDoc: async (docId, projectId) => {
    try {
      await api.deleteMemoryDoc(docId);
      await get().loadDocs(projectId, true);
    } catch (cause) {
      set({ docsError: toErrorState(cause, "记忆文档删除失败") });
    }
  },

  updateDocSection: async (docId, sectionId, content, expectedVersion) => {
    await api.updateMemoryDocSection(docId, sectionId, { content, expected_version: expectedVersion });
    await get().loadDocs(useProjectStore.getState().currentProjectId ?? "", true);
  },

  resetProjectScoped: () => {
    // 项目切换即中断进行中的 SSE（DESIGN.md §7 重置矩阵：agentStore SSE abort 项）
    const active = get().streamingSessionId;
    if (active) abortControllers.get(active)?.abort();
    set({
      sessions: [],
      sessionsProjectId: null,
      sessionsLoading: false,
      sessionsError: null,
      messagesBySession: {},
      messagesLoading: false,
      streamingSessionId: null,
      toolActivity: null,
      sessionErrors: {},
      usageBySession: {},
      draftsBySession: {},
      confirming: false,
      pendingBySession: {},
      approving: false,
      docs: [],
      docsLoading: false,
      docsError: null,
      dockOpen: false,
    });
  },
}));
