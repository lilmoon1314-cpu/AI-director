import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import { ProjectMemoriesArea } from "../../src/components/agent-panel/ProjectMemoriesArea";
import { useAgentStore } from "../../src/stores/agentStore";

const proposed = {
  id: "mem-1",
  project_id: "project-a",
  context_key: "author",
  kind: "constraint" as const,
  subject_key: "结局",
  content: "结局必须保持开放。",
  status: "proposed" as const,
  origin: "model_suggestion" as const,
  version: 1,
  valid_from: null,
  valid_until: null,
  sources: [{
    id: "msrc-1",
    source_kind: "message" as const,
    source_id: "msg-1",
    conversation_id: "conv-1",
    context_key: "author",
    source_version: null,
  }],
  created_at: "2026-09-18T00:00:00Z",
  updated_at: "2026-09-18T00:00:00Z",
};

let current = [proposed];
let forgot = false;
const server = setupServer(
  http.get("*/api/agent/memories", () => HttpResponse.json(current)),
  http.post("*/api/agent/memories/:id/accept", () => {
    current = [{ ...proposed, status: "accepted", version: 2 }];
    return HttpResponse.json(current[0]);
  }),
  http.get("*/api/agent/memories/:id/deletion-preview", () =>
    HttpResponse.json({
      memory_id: "mem-1",
      source_count: 1,
      source_conversation_ids: ["conv-1"],
      will_create_tombstone: true,
      effect: "忘记该派生记忆并建立墓碑；原始会话和作品内容不删除。",
    }),
  ),
  http.delete("*/api/agent/memories/:id", () => {
    forgot = true;
    current = [];
    return new HttpResponse(null, { status: 204 });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => { cleanup(); server.resetHandlers(); });
afterAll(() => server.close());

describe("F 跨会话记忆 UI", () => {
  beforeEach(() => {
    current = [proposed];
    forgot = false;
    useAgentStore.setState({
      sessionsProjectId: "project-a",
      memories: current,
      memoriesLoading: false,
      memoriesError: null,
    });
  });

  it("明确区分建议与已接受状态，并在遗忘前展示依赖预览", async () => {
    const user = userEvent.setup();
    render(<ProjectMemoriesArea projectId="project-a" />);
    expect(screen.getByText("待确认")).toBeInTheDocument();
    expect(screen.getByText(/Agent 建议/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "接受" }));
    await waitFor(() => expect(screen.getByText("已接受")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "遗忘" }));
    expect(await screen.findByText(/来源 1 项。再次点击确认/)).toBeInTheDocument();
    expect(forgot).toBe(false);
    await user.click(screen.getByRole("button", { name: "确认遗忘" }));
    await waitFor(() => expect(forgot).toBe(true));
  });
});
