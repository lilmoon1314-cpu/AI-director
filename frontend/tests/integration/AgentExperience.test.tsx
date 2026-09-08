/**
 * F13 L2：Agent 体验升级组件集成测试（FI4–FI9）——真实组件 + MSW mock 网络层。
 * 覆盖：ThinkingBlock 三态交互、UsageBar 容量条与琥珀阈值、SessionList 删除
 * 确认流、MemoryDocsArea 指导类置灰与两击删除、DocEditor 大弹窗三栏与 Esc
 * 脏确认、AgentDock 会话下拉/Esc 收起。
 * 用例设计（等价类/边界值标注）见 docs/tests/F13_agent_experience.md。
 */

import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import { useAgentStore } from "../../src/stores/agentStore";

const DOC_DETAIL = {
  id: "mdoc-1",
  kind: "style",
  title: "风格约定",
  version: 3,
  created_at: "2026-09-06T00:00:00Z",
  updated_at: "2026-09-08T00:00:00Z",
  sections: [
    { id: "msec-1", seq: 1, title: "叙事视角", content: "第一人称。", updated_by: "user", version: 1, updated_at: "2026-09-06T00:00:00Z" },
    { id: "msec-2", seq: 2, title: "影像风格", content: "冷色调 <参考>。", updated_by: "agent", version: 2, updated_at: "2026-09-06T00:00:00Z" },
  ],
};

const SESSIONS = [
  { id: "conv-1", project_id: "project-a", title: "海难主线", created_at: "2026-09-08T00:00:00Z", updated_at: new Date().toISOString() },
  { id: "conv-2", project_id: "project-a", title: "", created_at: "2026-09-08T00:00:00Z", updated_at: new Date().toISOString() },
];

let savedSections: { content: string; expected_version: number }[] = [];

const server = setupServer(
  http.get("*/api/agent/memory-docs/:id", () => HttpResponse.json(DOC_DETAIL)),
  http.patch("*/api/agent/memory-docs/:id/sections/:sid", async ({ request }) => {
    const body = (await request.json()) as { content: string; expected_version: number };
    savedSections.push(body);
    return HttpResponse.json({
      id: "msec-2",
      seq: 2,
      title: "影像风格",
      content: body.content,
      updated_by: "user",
      version: body.expected_version + 1,
      updated_at: "2026-09-08T01:00:00Z",
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
  savedSections = [];
  vi.clearAllMocks();
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
    usageBySession: {},
    draftsBySession: {},
    confirming: false,
    docs: [],
    docsLoading: false,
    docsError: null,
    dockOpen: false,
  });
});

async function renderView(ui: React.ReactElement) {
  const { render } = await import("@testing-library/react");
  const user = userEvent.setup();
  render(ui);
  return user;
}

// ---- FI4: ThinkingBlock 三态 ----

describe("F13 FI4: ThinkingBlock", () => {
  const base = {
    id: "msg-a",
    role: "assistant" as const,
  };

  async function renderList(message: Record<string, unknown>) {
    const { MessageList } = await import("../../src/components/agent-panel/MessageList");
    return renderView(
      <MessageList messages={[{ ...base, ...message } as never]} loading={false} toolActivity={null} error={null} onErrorRetry={() => {}} />,
    );
  }

  it("思考中（无正文）自动展开跟随；正文到来折叠为「已思考 N 秒」", async () => {
    await renderList({ content: "", reasoning: "思考中片段", streaming: true });
    expect(screen.getByTestId("agent-thinking-body")).toHaveTextContent("思考中片段");

    cleanup();
    await renderList({ content: "正文来了", reasoning: "思考内容", streaming: true, reasoningSeconds: 6 });
    expect(screen.queryByTestId("agent-thinking-body")).toBeNull();
    expect(screen.getByTestId("agent-thinking-toggle")).toHaveTextContent("已思考 6 秒");
  });

  it("折叠态点击标题行可再展开；历史消息无计时显示「已思考」", async () => {
    const user = await renderList({ content: "正文", reasoning: "历史思考" });
    expect(screen.queryByTestId("agent-thinking-body")).toBeNull();
    await user.click(screen.getByTestId("agent-thinking-toggle"));
    expect(screen.getByTestId("agent-thinking-body")).toHaveTextContent("历史思考");
    expect(screen.getByTestId("agent-thinking-toggle")).toHaveTextContent("已思考");
  });
});

// ---- FI5: UsageBar ----

describe("F13 FI5: UsageBar", () => {
  async function renderBar(usage: Record<string, number | null> | null) {
    const { UsageBar } = await import("../../src/components/agent-panel/UsageBar");
    return renderView(<UsageBar usage={usage as never} messages={[{ id: "m", role: "assistant", content: "x", promptTokens: 100, completionTokens: 20 }]} />);
  }

  it("正常占比渲染数字与条宽；会话累计求和（等价类-有效）", async () => {
    await renderBar({ promptTokens: 3000, completionTokens: 400, contextMaxTokens: 8000, contextRatio: 0.375 });
    expect(screen.getByTestId("agent-usage-context")).toHaveTextContent("3.0k/8.0k");
    expect(screen.getByTestId("agent-usage-ratio")).toHaveTextContent("38%");
    expect(screen.getByTestId("agent-usage-turn")).toHaveTextContent("3.0k+400");
    expect(screen.getByTestId("agent-usage-total")).toHaveTextContent("120");
    expect(screen.getByTestId("agent-usage-meter-fill").style.width).toBe("38%");
  });

  it.each([
    [0.5, false],
    [0.95, true],
  ])("占比 %s → 琥珀警示=%s（边界值 0.8 由纯函数单测覆盖）", async (ratio, warn) => {
    await renderBar({ promptTokens: 1, completionTokens: 1, contextMaxTokens: 100, contextRatio: ratio });
    const bar = screen.getByTestId("agent-usage-bar");
    if (warn) expect(bar.className).toContain("amber");
    else expect(bar.className).not.toContain("amber");
  });

  it("无 usage → 「—」占位（等价类-缺失用量，兼容端点）", async () => {
    await renderBar(null);
    expect(screen.getByTestId("agent-usage-context")).toHaveTextContent("—");
    expect(screen.getByTestId("agent-usage-ratio")).toHaveTextContent("—");
  });
});

// ---- FI6: SessionList 删除确认流 ----

describe("F13 FI6: SessionList 删除", () => {
  async function renderList() {
    const { SessionList } = await import("../../src/components/agent-panel/SessionList");
    const { MemoryRouter } = await import("react-router-dom");
    const onDelete = vi.fn();
    const user = await renderView(
      <MemoryRouter initialEntries={["/projects/project-a/agent"]}>
        <SessionList sessions={SESSIONS as never} activeId={null} onCreate={() => {}} creating={false} onDelete={onDelete} />
      </MemoryRouter>,
    );
    return { user, onDelete };
  }

  it("🗑 → 输入标题确认：错误文本禁用、精确匹配可删（输入标题确认模式）", async () => {
    const { user, onDelete } = await renderList();
    await user.click(screen.getAllByTestId("agent-session-delete")[0]);
    const input = screen.getByTestId("agent-session-delete-input");
    const confirm = screen.getByTestId("agent-session-delete-confirm");
    expect(confirm).toBeDisabled();

    await user.type(input, "错误标题");
    expect(confirm).toBeDisabled();
    await user.clear(input);
    await user.type(input, "海难主线");
    expect(confirm).toBeEnabled();
    await user.click(confirm);
    expect(onDelete).toHaveBeenCalledWith("conv-1");
  });

  it("未命名会话要求输入「未命名对话」；取消退出确认（边界值-空标题）", async () => {
    const { user, onDelete } = await renderList();
    await user.click(screen.getAllByTestId("agent-session-delete")[1]);
    expect(screen.getByTestId("agent-session-delete-input")).toHaveProperty("placeholder", "未命名对话");
    await user.type(screen.getByTestId("agent-session-delete-input"), "未命名对话");
    await user.click(screen.getByTestId("agent-session-delete-confirm"));
    expect(onDelete).toHaveBeenCalledWith("conv-2");

    await user.click(screen.getAllByTestId("agent-session-delete")[0]);
    await user.click(screen.getByTestId("agent-session-delete-cancel"));
    expect(screen.queryByTestId("agent-session-delete-panel")).toBeNull();
  });
});

// ---- FI7: MemoryDocsArea 指导类置灰 + 两击删除 ----

describe("F13 FI7: MemoryDocsArea", () => {
  interface DocLike {
    id: string;
    kind: string;
    title: string;
    updated_at: string;
    preview: string;
  }

  async function renderArea(docs: DocLike[]) {
    const { MemoryDocsArea } = await import("../../src/components/agent-panel/MemoryDocsArea");
    const onCreate = vi.fn();
    const onDeleteDoc = vi.fn();
    const user = await renderView(
      <MemoryDocsArea
        docs={docs}
        loading={false}
        error={null}
        onRetry={() => {}}
        onCreate={onCreate}
        onDeleteDoc={onDeleteDoc}
        creating={false}
        projectId="project-a"
      />,
    );
    return { user, onCreate, onDeleteDoc };
  }

  it("指导类已存在 → 对应「＋」置灰且不可建；不存在 → 可建（409 由后端兜底）", async () => {
    const { user, onCreate } = await renderArea([
      { id: "mdoc-1", kind: "positioning", title: "世界观定位", updated_at: "2026-09-08T00:00:00Z", preview: "" },
    ]);
    const existing = screen.getByTestId("memory-doc-create-positioning");
    expect(existing).toBeDisabled();
    expect(existing).toHaveAttribute("title", "每项目仅一份指导文档");

    await user.click(screen.getByTestId("memory-doc-create-style"));
    expect(onCreate).toHaveBeenCalledWith("style");
  });

  it("文档卡 🗑 两击确认：首击变「确认？」，再击执行删除（轻确认模式）", async () => {
    const { user, onDeleteDoc } = await renderArea([
      { id: "mdoc-9", kind: "style", title: "风格约定", updated_at: "2026-09-08T00:00:00Z", preview: "" },
    ]);
    const del = screen.getByTestId("memory-doc-delete");
    await user.click(del);
    expect(del).toHaveTextContent("确认？");
    await user.click(del);
    expect(onDeleteDoc).toHaveBeenCalledWith("mdoc-9");
  });
});

// ---- FI8: DocEditor 大弹窗三栏 + Esc 脏确认 ----

describe("F13 FI8: DocEditor", () => {
  async function openEditor() {
    const { DocEditor } = await import("../../src/components/agent-panel/DocEditor");
    const onClose = vi.fn();
    const onSaved = vi.fn();
    const user = await renderView(<DocEditor docId="mdoc-1" onClose={onClose} onSaved={onSaved} />);
    await waitFor(() => expect(screen.getByTestId("doc-editor-section-2")).toBeInTheDocument());
    return { user, onClose, onSaved };
  }

  it("三栏结构：段列表（左）+ 编辑区（右）+ 实时预览 iframe（全转义 srcDoc）", async () => {
    await openEditor();
    expect(screen.getByTestId("doc-editor-section-list")).toBeInTheDocument();
    expect(screen.getByTestId("doc-editor-preview")).toHaveAttribute("sandbox", "");
    const srcDoc = screen.getByTestId("doc-editor-preview").getAttribute("srcdoc") ?? "";
    expect(srcDoc).toContain("<!DOCTYPE html>");
    expect(srcDoc).toContain("冷色调 &lt;参考&gt;。");
    // XSS 防线：载荷经转义后原文不得出现
    expect(srcDoc).not.toContain("<script");
  });

  it("段切换高亮 + 编辑置脏 + 保存本段（CAS 载荷）", async () => {
    const { user, onSaved } = await openEditor();
    await user.click(screen.getByTestId("doc-editor-section-2"));
    const textarea = screen.getByLabelText("2. 影像风格") as HTMLTextAreaElement;
    expect(textarea.value).toBe("冷色调 <参考>。");
    await user.type(textarea, "再冷一点");
    await user.click(screen.getByTestId("doc-section-save-2"));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(savedSections[0]).toEqual({ content: "冷色调 <参考>。再冷一点", expected_version: 2 });
  });

  it("Esc 关闭：无脏直接关；有脏先出确认条（放弃/继续两态）", async () => {
    const { user, onClose } = await openEditor();
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);

    cleanup();
    const again = await openEditor();
    await again.user.click(screen.getByTestId("doc-editor-section-2"));
    await again.user.type(screen.getByLabelText("2. 影像风格"), "改动");
    await again.user.keyboard("{Escape}");
    expect(screen.getByTestId("doc-editor-dirty-confirm")).toBeInTheDocument();
    expect(again.onClose).not.toHaveBeenCalled(); // 脏输入时首次 Esc 只出确认条
    await again.user.click(screen.getByTestId("doc-editor-dirty-stay"));
    expect(screen.queryByTestId("doc-editor-dirty-confirm")).toBeNull();
    expect(again.onClose).not.toHaveBeenCalled(); // 继续编辑：不关闭

    await again.user.keyboard("{Escape}");
    await again.user.click(screen.getByTestId("doc-editor-dirty-leave"));
    expect(again.onClose).toHaveBeenCalledTimes(1); // 放弃更改：关闭
  });
});

// ---- FI9: AgentDock 会话下拉 + ＋新会话 + Esc 收起 ----

describe("F13 FI9: AgentDock", () => {
  async function openDock() {
    useAgentStore.setState({ dockOpen: true, sessions: SESSIONS as never });
    const { AgentDock } = await import("../../src/components/agent-panel/AgentDock");
    const user = await renderView(<AgentDock projectId="project-a" />);
    await waitFor(() => expect(screen.getByTestId("agent-dock-session-select")).toBeInTheDocument());
    return user;
  }

  it("顶部会话下拉列出会话并可切换；「＋」常驻头部", async () => {
    const user = await openDock();
    const select = screen.getByTestId("agent-dock-session-select") as HTMLSelectElement;
    expect(select.options).toHaveLength(2);
    expect(screen.getByTestId("agent-dock-create")).toBeInTheDocument();

    await user.selectOptions(select, "conv-2");
    expect((screen.getByTestId("agent-dock-session-select") as HTMLSelectElement).value).toBe("conv-2");
    expect(screen.getByTestId("agent-dock-input")).toBeInTheDocument();
  });

  it("「＋」创建新会话并切换到该会话（等价类-有效创建）", async () => {
    const user = await openDock();
    server.use(
      http.post("*/api/agent/sessions", () =>
        HttpResponse.json(
          { id: "conv-new", project_id: "project-a", title: "", created_at: "2026-09-08T02:00:00Z", updated_at: "2026-09-08T02:00:00Z" },
          { status: 201 },
        ),
      ),
    );
    await user.click(screen.getByTestId("agent-dock-create"));
    await waitFor(() =>
      expect((screen.getByTestId("agent-dock-session-select") as HTMLSelectElement).value).toBe("conv-new"),
    );
  });

  it("Dock 头部聚焦时 Esc 收起（F10 偏离清单兑现）", async () => {
    const user = await openDock();
    expect(screen.getByTestId("agent-dock")).toBeInTheDocument();
    screen.getByTestId("agent-dock-header").focus();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByTestId("agent-dock")).toBeNull());
    expect(useAgentStore.getState().dockOpen).toBe(false);
  });
});
