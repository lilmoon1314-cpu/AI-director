import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SessionView } from "../../src/components/agent-panel/SessionView";
import { useAgentStore } from "../../src/stores/agentStore";

beforeEach(() => {
  useAgentStore.getState().resetProjectScoped();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("B request rejection reaches the creator", () => {
  it.each([
    ["AGENT_CONTEXT_BUDGET", "本轮上下文超过安全预算", "缩短输入或开启新会话"],
    ["AGENT_TURN_LIMIT", "本轮达到总时限", "缩小任务后重试"],
  ])("renders %s with its recovery action", async (code, problem, fix) => {
    const requests: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      requests.push(url);
      if (url.includes("/chat")) {
        return new Response(`event: error\ndata: ${JSON.stringify({ code, problem, cause: "test", fix })}\n\n`, {
          headers: { "Content-Type": "text/event-stream" },
        });
      }
      return new Response("[]", { headers: { "Content-Type": "application/json" } });
    }));
    render(<SessionView conversationId="conv-b" />);
    await waitFor(() => expect(requests.length).toBeGreaterThan(0));
    const user = userEvent.setup();
    await user.type(screen.getByTestId("agent-input"), "继续创作");
    await user.click(screen.getByTestId("agent-input-send"));
    expect(await screen.findByText(problem)).toBeInTheDocument();
    expect(screen.getByTestId("agent-error")).toHaveTextContent(fix);
    expect(screen.getByTestId("agent-context-scope")).toHaveTextContent("各视角及角色分别保留");
    expect(useAgentStore.getState().streamingSessionId).toBeNull();
  });
});
