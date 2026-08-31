/**
 * F06 L2：视角切换集成测试（I1–I5）——真实组件链 + MSW mock 网络层。
 * 三视角视图数据为 F04 过滤规则的镜像（docs/tests/F06_perspective_switch_ui.md 测试世界表）；
 * @antv/g6 为测试桩（test.alias），断言经 stats 文本与 MSW 捕获的请求 URL。
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import { Workbench } from "../../src/views/Workbench";
import { usePerspectiveStore } from "../../src/stores/perspectiveStore";

// ---- 测试世界（三视角视图镜像，见测试文档矩阵） ----

const AUTHOR_VIEW = {
  nodes: [
    { id: "char-a", type: "character", name: "周兰", aliases: [] },
    { id: "char-b", type: "character", name: "沈墨", aliases: [] },
    { id: "char-c", type: "character", name: "陆离", aliases: [] },
    { id: "item-x", type: "item", name: "青铜镜", aliases: [] },
    { id: "event-e", type: "event", name: "夜探药庐", aliases: [] },
    { id: "loc-l", type: "location", name: "青云山", aliases: [] },
  ],
  edges: [
    { id: "rel-1", source: "char-a", target: "char-b", type: "ALLY" },
    { id: "rel-2", source: "char-a", target: "loc-l", type: "LIVES_IN" },
    { id: "rel-3", source: "char-b", target: "event-e", type: "PARTICIPATES" },
  ],
};

const AUDIENCE_VIEW = {
  nodes: [
    { id: "char-a", type: "character", name: "周兰", aliases: [] },
    { id: "char-c", type: "character", name: "陆离", aliases: [] },
    { id: "event-e", type: "event", name: "夜探药庐", aliases: [] },
    { id: "loc-l", type: "location", name: "青云山", aliases: [] },
  ],
  edges: [{ id: "rel-2", source: "char-a", target: "loc-l", type: "LIVES_IN" }],
};

const CHARACTER_VIEW = {
  nodes: [
    { id: "char-a", type: "character", name: "周兰", aliases: [] },
    { id: "loc-l", type: "location", name: "青云山", aliases: [] },
  ],
  edges: [{ id: "rel-2", source: "char-a", target: "loc-l", type: "LIVES_IN" }],
};

const CHARACTERS = [
  { id: "char-a", type: "character", name: "周兰", aliases: [] },
  { id: "char-b", type: "character", name: "沈墨", aliases: [] },
  { id: "char-c", type: "character", name: "陆离", aliases: [] },
];

// ---- MSW 捕获 ----

const graphCalls: string[] = [];
const entityListCalls: string[] = [];

const server = setupServer(
  http.get("*/api/graph", ({ request }) => {
    const url = new URL(request.url);
    const params = url.searchParams;
    graphCalls.push(params.toString());
    const perspective = params.get("perspective");
    if (perspective === "audience") return HttpResponse.json(AUDIENCE_VIEW);
    if (perspective === "character" && params.get("character_id") === "char-a") {
      return HttpResponse.json(CHARACTER_VIEW);
    }
    if (perspective === "author") return HttpResponse.json(AUTHOR_VIEW);
    // character 缺角色/角色不存在等 → 后端同形 403 三要素
    return HttpResponse.json(
      {
        code: "PERSPECTIVE_FORBIDDEN",
        problem: "character 视角的角色不存在",
        cause: `character_id '${params.get("character_id") ?? ""}' 未在实体库中`,
        fix: "先调用 GET /api/entities?q= 检索确认角色 id 后重试",
      },
      { status: 403 },
    );
  }),
  http.get("*/api/entities", ({ request }) => {
    const url = new URL(request.url);
    entityListCalls.push(url.searchParams.toString());
    if (url.searchParams.get("type") === "character") return HttpResponse.json(CHARACTERS);
    return HttpResponse.json([]);
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  cleanup();
});
afterAll(() => server.close());

beforeEach(() => {
  graphCalls.length = 0;
  entityListCalls.length = 0;
  usePerspectiveStore.setState({
    perspective: "author",
    characterId: null,
    characters: [],
  });
});

async function renderWorkbench() {
  const user = userEvent.setup();
  render(<Workbench />);
  await waitFor(() => expect(screen.getByTestId("graph-stats")).toHaveTextContent("6 节点 · 3 边"));
  return user;
}

describe("视角切换集成（F06 I1–I5）", () => {
  it("I1: 默认渲染三段切换（作者选中）与 stats 作者视角标注", async () => {
    // 设计依据: 等价类—默认态
    await renderWorkbench();
    expect(screen.getByTestId("perspective-author")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("perspective-character")).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByTestId("perspective-audience")).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByTestId("graph-stats")).toHaveTextContent("（作者视角）");
    expect(screen.queryByTestId("character-select")).not.toBeInTheDocument();
  });

  it("I2: 切「观众」→ 请求 perspective=audience → 图刷新 4 节点 1 边", async () => {
    // 设计依据: 主路径—视角切换重载
    const user = await renderWorkbench();
    await user.click(screen.getByTestId("perspective-audience"));
    await waitFor(() => expect(screen.getByTestId("graph-stats")).toHaveTextContent("4 节点 · 1 边"));
    expect(graphCalls[graphCalls.length - 1]).toBe("perspective=audience");
    expect(screen.getByTestId("perspective-audience")).toHaveAttribute("aria-pressed", "true");
  });

  it("I3: 切「角色」→ 下拉数据源 type=character；未选角色零图请求；选周兰 → 2 节点 1 边", async () => {
    // 设计依据: 等价类—选角色有效；边界值—缺参零请求（后端此情形必 403，前端拦截）
    const user = await renderWorkbench();
    await user.click(screen.getByTestId("perspective-character"));
    const select = await screen.findByTestId("character-select");
    await waitFor(() => expect(entityListCalls.some((q) => q.includes("type=character"))).toBe(true));
    expect(graphCalls).toHaveLength(1); // 仅挂载时的 author，切角色未选不新增（边界值）
    expect(screen.getByTestId("graph-stats")).toHaveTextContent("（角色视角·未选择角色）");

    await screen.findByRole("option", { name: "周兰" }); // 选项异步加载完成后才可选
    await user.selectOptions(select, "char-a");
    await waitFor(() => expect(screen.getByTestId("graph-stats")).toHaveTextContent("2 节点 · 1 边"));
    expect(graphCalls[graphCalls.length - 1]).toBe("perspective=character&character_id=char-a");
    expect(screen.getByTestId("graph-stats")).toHaveTextContent("（角色视角·周兰）");
  });

  it("I4: character 视角 403 → alert 展示三要素（problem+fix）不白屏", async () => {
    // 设计依据: 无效等价类—角色不存在等服务端拒绝的前端呈现
    const user = await renderWorkbench();
    await user.click(screen.getByTestId("perspective-character"));
    await screen.findByRole("option", { name: "沈墨" }); // 选项加载完成
    await user.selectOptions(await screen.findByTestId("character-select"), "char-b");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("character 视角的角色不存在");
    expect(alert).toHaveTextContent("先调用 GET /api/entities?q= 检索确认角色 id 后重试");
  });

  it("I5: 角色→作者恢复全量→再切角色已选保留并自动重载（回切恢复）", async () => {
    // 设计依据: 回切恢复设计；等价类—两态往返
    const user = await renderWorkbench();
    // 进角色视角选周兰
    await user.click(screen.getByTestId("perspective-character"));
    await screen.findByRole("option", { name: "周兰" }); // 选项加载完成
    await user.selectOptions(await screen.findByTestId("character-select"), "char-a");
    await waitFor(() => expect(screen.getByTestId("graph-stats")).toHaveTextContent("2 节点 · 1 边"));

    // 切回作者 → 全量
    await user.click(screen.getByTestId("perspective-author"));
    await waitFor(() => expect(screen.getByTestId("graph-stats")).toHaveTextContent("6 节点 · 3 边"));
    expect(graphCalls[graphCalls.length - 1]).toBe("perspective=author");

    // 再切角色：无需重选，自动按已选角色加载
    const callsBefore = graphCalls.length;
    await user.click(screen.getByTestId("perspective-character"));
    await waitFor(() => expect(screen.getByTestId("graph-stats")).toHaveTextContent("2 节点 · 1 边"));
    expect(graphCalls.length).toBeGreaterThan(callsBefore);
    expect(graphCalls[graphCalls.length - 1]).toBe("perspective=character&character_id=char-a");
    expect(screen.getByTestId("character-select")).toHaveValue("char-a");
  });
});
