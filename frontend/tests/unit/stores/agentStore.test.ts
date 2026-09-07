/**
 * F10 L1：agentStore 单元测试（FU1）。fetch 全 mock，不触网络。
 * 用例设计（等价类/边界值标注）见 docs/tests/F10_agent_chat.md。
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAgentStore } from "../../../src/stores/agentStore";
import { useProjectStore } from "../../../src/stores/projectStore";

const SESSION = {
  id: "conv-1",
  project_id: "project-x",
  title: "既有会话",
  created_at: "2026-09-06T00:00:00Z",
  updated_at: "2026-09-06T00:00:00Z",
};

const DOC = {
  id: "mdoc-1",
  kind: "style",
  title: "风格约定",
  version: 1,
  updated_at: "2026-09-06T00:00:00Z",
  preview: "",
};

/** 构造 SSE 文本响应（fetch 流 mock）。 */
function sseResponse(frames: { event: string; data: unknown }[]): Response {
  const body = frames.map((f) => `event: ${f.event}\ndata: ${JSON.stringify(f.data)}\n\n`).join("");
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function routeFetch(handler: (url: string, init: RequestInit | undefined) => Response | Promise<Response>) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    return handler(url, init);
  });
}

describe("agentStore（FU1）", () => {
  beforeEach(() => {
    useAgentStore.setState({
      sessions: [],
      sessionsProjectId: null,
      sessionsLoading: false,
      sessionsError: null,
      messagesBySession: {},
      messagesLoading: false,
      streamingSessionId: null,
      toolActivity: null,
      sessionErrors: {},
      draftsBySession: {},
      confirming: false,
      docs: [],
      docsLoading: false,
      docsError: null,
      dockOpen: false,
    });
    useProjectStore.setState({ projects: [], currentProjectId: "project-x" });
    vi.unstubAllGlobals();
  });

  it("FU1-1: sendMessage 正常流 → token 拼接、done 后回读消息（等价类—有效会话轮；未知事件类型忽略不崩溃）", async () => {
    const fetchMock = routeFetch((url) => {
      if (url.includes("/agent/chat")) {
        return sseResponse([
          { event: "message_start", data: { conversation_id: "conv-1" } },
          { event: "token", data: { text: "你好" } },
          { event: "future_event", data: { anything: true } }, // F13 预留/未知类型：前向兼容忽略
          { event: "token", data: { text: "，作者。" } },
          { event: "done", data: { message_id: "msg-2" } },
        ]);
      }
      if (url.includes("/messages")) {
        return jsonResponse([
          { id: "msg-1", conversation_id: "conv-1", role: "user", content: "hi", created_at: "2026-09-06T00:00:00Z" },
          { id: "msg-2", conversation_id: "conv-1", role: "assistant", content: "你好，作者。", created_at: "2026-09-06T00:00:01Z" },
        ]);
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    await useAgentStore.getState().sendMessage("conv-1", "hi", "author");

    expect(useAgentStore.getState().streamingSessionId).toBeNull();
    const messages = useAgentStore.getState().messagesBySession["conv-1"]!;
    expect(messages).toHaveLength(2);
    expect(messages[1].content).toBe("你好，作者。");
    expect(useAgentStore.getState().sessionErrors["conv-1"]).toBeNull();
  });

  it("FU1-2: SSE error 事件 → 三要素错误置位（等价类—错误流）", async () => {
    const fetchMock = routeFetch((url) => {
      if (url.includes("/agent/chat")) {
        return sseResponse([
          { event: "message_start", data: {} },
          {
            event: "error",
            data: { code: "AGENT_FAILURE", problem: "LLM 调用失败", cause: "超时", fix: "重试" },
          },
        ]);
      }
      if (url.includes("/messages")) return jsonResponse([]);
      throw new Error(`unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    await useAgentStore.getState().sendMessage("conv-1", "hi", "author");

    const error = useAgentStore.getState().sessionErrors["conv-1"];
    expect(error?.problem).toBe("LLM 调用失败");
    expect(error?.fix).toBe("重试");
    expect(useAgentStore.getState().streamingSessionId).toBeNull();
  });

  it("FU1-3: propose→confirm→草案清空+摘要消息+图谱失效广播（两段式闭环）", async () => {
    const fetchMock = routeFetch((url, init) => {
      if (url.includes("/agent/propose")) {
        return jsonResponse({
          session_id: "conv-1",
          drafts: [
            { draft_id: "draft-1", kind: "entity", payload: { type: "character", name: "周兰" }, summary: "新增" },
          ],
        });
      }
      if (url.includes("/agent/confirm")) {
        return jsonResponse({
          created: [{ draft_id: "draft-1", kind: "entity", target_id: "ent-1", name: "周兰" }],
          failed: [],
        });
      }
      if (url.includes("/graph?")) return jsonResponse({ nodes: [], edges: [] });
      throw new Error(`unexpected fetch: ${url} ${init?.method}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    await useAgentStore.getState().proposeDrafts("conv-1", "加角色", "author");
    expect(useAgentStore.getState().draftsBySession["conv-1"]).toHaveLength(1);

    await useAgentStore.getState().confirmDrafts("conv-1");

    expect(useAgentStore.getState().draftsBySession["conv-1"]).toHaveLength(0);
    const messages = useAgentStore.getState().messagesBySession["conv-1"]!;
    expect(messages.at(-1)?.content).toContain("已写入 1 项");
    // 图谱失效广播：confirm 后触发 /api/graph 重载（DESIGN.md §5.4）
    const graphCalls = fetchMock.mock.calls.filter(([u]) => String(u).includes("/graph?"));
    expect(graphCalls.length).toBeGreaterThanOrEqual(1);
  });

  it("FU1-4: resetProjectScoped 中断流式并清空全部会话态（边界值—项目切换中断）", async () => {
    // 挂起的 SSE 流（body 永不结束）模拟进行中的对话；断言 abort signal 被触发
    const stream = new ReadableStream<Uint8Array>({ start() {} });
    let capturedSignal: AbortSignal | null = null;
    const fetchMock = routeFetch((url, init) => {
      if (url.includes("/agent/chat")) {
        capturedSignal = init?.signal ?? null;
        return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
      }
      return jsonResponse([]);
    });
    vi.stubGlobal("fetch", fetchMock);
    useAgentStore.setState({ dockOpen: true });
    const pending = useAgentStore.getState().sendMessage("conv-1", "hi", "author");
    await new Promise((r) => setTimeout(r, 0));
    expect(useAgentStore.getState().streamingSessionId).toBe("conv-1");

    useAgentStore.getState().resetProjectScoped();
    await new Promise((r) => setTimeout(r, 0));
    void pending; // 流挂起属预期（真实 fetch 中由 signal 中断）；不 await

    expect(capturedSignal?.aborted).toBe(true);
    expect(useAgentStore.getState().streamingSessionId).toBeNull();
    expect(useAgentStore.getState().sessions).toHaveLength(0);
    expect(useAgentStore.getState().dockOpen).toBe(false);
  });

  it("FU1-6: 流式中收起 Dock 不中断（等价类—SSE 会话级生命周期非中断态）", async () => {
    const stream = new ReadableStream<Uint8Array>({ start() {} });
    let capturedSignal: AbortSignal | null = null;
    const fetchMock = routeFetch((url, init) => {
      if (url.includes("/agent/chat")) {
        capturedSignal = init?.signal ?? null;
        return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
      }
      return jsonResponse([]);
    });
    vi.stubGlobal("fetch", fetchMock);
    useAgentStore.setState({ dockOpen: true });
    const pending = useAgentStore.getState().sendMessage("conv-1", "hi", "author");
    await new Promise((r) => setTimeout(r, 0));

    useAgentStore.getState().closeDock();
    await new Promise((r) => setTimeout(r, 0));
    void pending; // 挂起流由测试环境丢弃；不 await

    expect(capturedSignal?.aborted).toBe(false);
    expect(useAgentStore.getState().streamingSessionId).toBe("conv-1");
  });

  it("FU1-7: 他会议流式期间 sendMessage 全局单流守卫拒绝（边界值—重复轮次拒绝）", async () => {
    const stream = new ReadableStream<Uint8Array>({ start() {} });
    const fetchMock = routeFetch((url) => {
      if (url.includes("/agent/chat")) {
        return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
      }
      return jsonResponse([]);
    });
    vi.stubGlobal("fetch", fetchMock);
    const pending = useAgentStore.getState().sendMessage("conv-1", "hi", "author");
    await new Promise((r) => setTimeout(r, 0));

    await useAgentStore.getState().sendMessage("conv-2", "another", "author"); // 守卫：静默拒绝
    void pending;

    expect(useAgentStore.getState().streamingSessionId).toBe("conv-1");
    expect(useAgentStore.getState().messagesBySession["conv-2"]).toBeUndefined();
  });

  it("FU1-5: 会话列表与记忆文档加载（等价类—列表域读取）", async () => {
    const fetchMock = routeFetch((url) => {
      if (url.includes("/agent/sessions")) {
        return jsonResponse([SESSION]);
      }
      if (url.includes("/agent/memory-docs") && !url.includes("sections")) {
        return jsonResponse([DOC]);
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    await useAgentStore.getState().loadSessions("project-x");
    expect(useAgentStore.getState().sessions).toHaveLength(1);
    expect(useAgentStore.getState().sessions[0].title).toBe("既有会话");

    await useAgentStore.getState().loadDocs("project-x");
    expect(useAgentStore.getState().docs).toHaveLength(1);
  });
});
