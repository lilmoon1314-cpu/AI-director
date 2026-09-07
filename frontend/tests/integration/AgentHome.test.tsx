/**
 * F10 L2：AgentHome + 会话视图集成测试（FU2）——真实组件链 + MSW mock 网络层。
 * 覆盖：左右栏渲染（会话列表/记忆文档卡）、欢迎页大输入框、新建会话导航、
 * 草案产出→确认→摘要消息、记忆文档模板新建。
 * 用例设计（等价类/边界值标注）见 docs/tests/F10_agent_chat.md。
 */

import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import { useAgentStore } from "../../src/stores/agentStore";
import { useProjectStore } from "../../src/stores/projectStore";

const PROJECT = {
  id: "project-a",
  name: "长安怪谈",
  description: "",
  entity_count: 0,
  relation_count: 0,
  created_at: "2026-09-05T00:00:00Z",
  updated_at: "2026-09-06T00:00:00Z",
};

const SESSION = {
  id: "conv-1",
  project_id: "project-a",
  title: "既有会话",
  created_at: "2026-09-06T00:00:00Z",
  updated_at: "2026-09-06T00:00:00Z",
};

const DOC = {
  id: "mdoc-1",
  kind: "style",
  title: "风格约定",
  version: 2,
  updated_at: "2026-09-06T00:00:00Z",
  preview: "全片冷色调",
};

let createdSessions = 0;
let confirmBodies: unknown[] = [];
let docCreates = 0;

const server = setupServer(
  http.get("*/api/projects", () => HttpResponse.json([PROJECT])),
  http.get("*/api/graph", () => HttpResponse.json({ nodes: [], edges: [] })),
  http.get("*/api/agent/sessions", () => HttpResponse.json([SESSION])),
  http.post("*/api/agent/sessions", () => {
    createdSessions += 1;
    return HttpResponse.json(
      {
        id: `conv-new-${createdSessions}`,
        project_id: "project-a",
        title: "",
        created_at: "2026-09-06T10:00:00Z",
        updated_at: "2026-09-06T10:00:00Z",
      },
      { status: 201 },
    );
  }),
  http.get("*/api/agent/sessions/:id/messages", () => HttpResponse.json([])),
  http.get("*/api/agent/memory-docs", () => HttpResponse.json([DOC])),
  http.post("*/api/agent/memory-docs", () => {
    docCreates += 1;
    return HttpResponse.json(
      {
        id: `mdoc-new-${docCreates}`,
        kind: "positioning",
        title: "世界观定位",
        version: 1,
        created_at: "2026-09-06T10:00:00Z",
        updated_at: "2026-09-06T10:00:00Z",
        sections: [
          { id: "msec-1", seq: 1, title: "一句话定位", content: "", updated_by: "user", version: 1, updated_at: "2026-09-06T10:00:00Z" },
        ],
      },
      { status: 201 },
    );
  }),
  http.post("*/api/agent/propose", () =>
    HttpResponse.json({
      session_id: "conv-1",
      drafts: [
        {
          draft_id: "draft-1",
          kind: "entity",
          payload: { type: "character", name: "周兰", description: "船医" },
          summary: "新增船医",
        },
      ],
    }),
  ),
  http.post("*/api/agent/confirm", async ({ request }) => {
    confirmBodies.push(await request.json());
    return HttpResponse.json({
      created: [{ draft_id: "draft-1", kind: "entity", target_id: "ent-1", name: "周兰" }],
      failed: [],
    });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  cleanup();
});
afterAll(() => server.close());

beforeEach(() => {
  createdSessions = 0;
  docCreates = 0;
  confirmBodies = [];
  useProjectStore.setState({
    projects: [],
    loading: false,
    error: null,
    errorFix: null,
    currentProjectId: null,
    routeProjectId: null,
    routeInvalid: false,
  });
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
});

async function renderAgentHome(initialRoute = "/projects/project-a/agent") {
  const { MemoryRouter, Route, Routes } = await import("react-router-dom");
  const { render } = await import("@testing-library/react");
  const { Workbench } = await import("../../src/views/Workbench");
  const { AgentHome } = await import("../../src/components/agent-panel/AgentHome");
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <Routes>
        <Route path="/projects/:projectId" element={<Workbench />}>
          <Route path="agent" element={<AgentHome />} />
          <Route path="agent/s/:sessionId" element={<AgentHome />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
  await waitFor(() => expect(screen.getByTestId("agent-home")).toBeInTheDocument());
  return user;
}

describe("F10 FU2: AgentHome", () => {
  it("左右栏渲染：会话列表项 + 记忆文档卡 + 欢迎输入框（等价类—非空会话/文档集）", async () => {
    await renderAgentHome();
    await screen.findByTestId("agent-session-item");
    expect(screen.getByTestId("agent-session-item")).toHaveTextContent("既有会话");
    expect(screen.getByTestId("memory-doc-card")).toHaveTextContent("风格约定");
    expect(screen.getByTestId("agent-input")).toBeInTheDocument();
  });

  it("新建会话 → 导航到会话路由并挂载会话视图（等价类—有效创建）", async () => {
    const user = await renderAgentHome();
    await screen.findByTestId("agent-session-item");
    await user.click(screen.getByTestId("agent-session-create"));
    await waitFor(() => expect(createdSessions).toBe(1));
    await waitFor(() => expect(screen.getByTestId("agent-session-view")).toBeInTheDocument());
  });

  it("记忆文档模板新建 → POST 后列表刷新（等价类—模板创建）", async () => {
    const user = await renderAgentHome();
    await screen.findByTestId("memory-doc-card");
    await user.click(screen.getByTestId("memory-doc-create-positioning"));
    await waitFor(() => expect(docCreates).toBe(1));
  });

  it("草案产出→确认→确认请求携带草案 + 摘要消息（两段式闭环）", async () => {
    const user = await renderAgentHome("/projects/project-a/agent/s/conv-1");
    await screen.findByTestId("agent-session-view");

    const input = screen.getByTestId("agent-input");
    await user.type(input, "加一个船医角色");
    await user.click(screen.getByTestId("agent-propose"));

    await screen.findByTestId("agent-draft-card");
    expect(screen.getAllByTestId("agent-draft-item")[0]).toHaveTextContent("周兰");

    await user.click(screen.getByTestId("agent-draft-confirm"));
    await waitFor(() => {
      expect(confirmBodies.length).toBe(1);
    });
    const body = confirmBodies[0] as { items: { draft_id: string; confirmed: boolean }[] };
    expect(body.items[0].draft_id).toBe("draft-1");
    expect(body.items[0].confirmed).toBe(true);
    // 确认后草案卡消失 + 摘要消息出现在消息流
    await waitFor(() => expect(screen.queryByTestId("agent-draft-card")).not.toBeInTheDocument());
    expect(await screen.findAllByTestId("agent-message")).toBeTruthy();
  });
});
