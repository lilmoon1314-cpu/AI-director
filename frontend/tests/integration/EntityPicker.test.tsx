/**
 * F07 L2：@ 实体选择器集成测试（I1–I5）——真实组件链 + MSW mock 网络层。
 * 覆盖：详情面板名称解析（I1）、refTypes 分流渲染（I2）、@ 防抖检索与视角徽标（I3）、
 * 多值回填与 chip（I4）、提交仍存 ID 的契约（I5）。
 */

import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import { CreateEntityForm } from "../../src/components/entity-panel/CreateEntityForm";
import { EntityPanel } from "../../src/components/entity-panel/EntityPanel";
import { EntityPicker } from "../../src/components/entity-panel/EntityPicker";
import { useEntityIndexStore } from "../../src/stores/entityIndexStore";
import { useGraphStore } from "../../src/stores/graphStore";
import { useSelectionStore } from "../../src/stores/selectionStore";
import { toGraphData } from "../../src/lib/toGraphData";

const BRIEFS = [
  { id: "char-a", type: "character", name: "周兰", aliases: [], audience_known: true },
  { id: "char-b", type: "character", name: "沈墨", aliases: [], audience_known: false },
  { id: "loc-l", type: "location", name: "青云山", aliases: [], audience_known: true },
];

// 当前视角图数据：char-a 在场（可见），char-b 不在场（不可见）
const GRAPH = toGraphData({
  nodes: [
    { id: "char-a", type: "character", name: "周兰", aliases: [] },
    { id: "loc-l", type: "location", name: "青云山", aliases: [] },
  ],
  edges: [],
});

let lastPatchBody: Record<string, unknown> | null = null;
let searchCalls: string[] = [];

const server = setupServer(
  http.get("*/api/entities", ({ request }) => {
    const url = new URL(request.url);
    searchCalls.push(decodeURIComponent(url.searchParams.toString()));
    const q = url.searchParams.get("q") ?? "";
    const type = url.searchParams.get("type");
    let list = BRIEFS.filter((b) => b.name.includes(q) || b.aliases.some((a) => a.includes(q)));
    if (type) list = list.filter((b) => b.type === type);
    return HttpResponse.json(list);
  }),
  http.get("*/api/entities/:id", ({ params }) => {
    if (params.id === "item-x") {
      return HttpResponse.json({
        id: "item-x",
        type: "item",
        name: "青铜镜",
        aliases: [],
        description: "",
        audience_known: false,
        properties: { seen_by: ["char-a", "char-b"], holder: "char-a" },
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      });
    }
    return HttpResponse.json({ problem: "实体不存在" }, { status: 404 });
  }),
  http.patch("*/api/entities/:id", async ({ request }) => {
    lastPatchBody = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ id: "item-x", updated_at: "2026-01-02T00:00:00Z" });
  }),
  http.post("*/api/entities", () => new HttpResponse(null, { status: 501 })),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  cleanup();
});
afterAll(() => server.close());

beforeEach(() => {
  lastPatchBody = null;
  searchCalls = [];
  useEntityIndexStore.setState({ briefs: BRIEFS });
  useGraphStore.setState({ graph: GRAPH, loading: false, error: null, errorFix: null });
  useSelectionStore.setState({ selectedEntityId: null, selectedRelationId: null, panelOpen: false });
});

describe("@ 实体选择器集成（F07 I1–I5）", () => {
  it("I1: 详情面板 ref 字段显示名称而非 id（seen_by → 周兰、沈墨）", async () => {
    // 设计依据: 主路径—名称显示替代抽象 id（用户需求原文）
    useSelectionStore.setState({ selectedEntityId: "item-x", panelOpen: true });
    render(<EntityPanel />);
    const seenBy = await screen.findByTestId("prop-seen_by");
    await waitFor(() => expect(seenBy).toHaveTextContent("周兰、沈墨"));
    expect(seenBy).not.toHaveTextContent("char-a");
    expect(seenBy).toHaveTextContent("周兰"); // 名称
    const holder = screen.getByTestId("prop-holder");
    await waitFor(() => expect(holder).toHaveTextContent("周兰"));
  });

  it("I2: 新建表单按 refTypes 分流——holder 渲染选择器、appearance 仍为文本框", async () => {
    // 设计依据: 等价类—ref/非 ref 字段分流
    const user = userEvent.setup();
    render(<CreateEntityForm />);
    await user.selectOptions(screen.getByLabelText("类型"), "item");
    expect(screen.getByTestId("create-prop-holder")).toBeInTheDocument();
    expect(screen.getByLabelText("外观描述").tagName).toBe("INPUT"); // 非 ref 字段仍是普通输入框
  });

  it("I3: 输入「@周」→ 防抖检索 q=周&type=character → 下拉含名称/类型/当前视角可见徽标", async () => {
    // 设计依据: 主路径—@ 触发防抖检索 + 视角提示（features.md F07 定义）
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <EntityPicker
        id="t-holder"
        label="当前持有人"
        refTypes={["character"]}
        mode="single"
        value=""
        onChange={onChange}
      />,
    );
    const input = screen.getByTestId("t-holder");
    await user.click(input);
    await user.type(input, "@周");
    await waitFor(() => expect(searchCalls.some((q) => q.includes("q=周"))).toBe(true));
    await waitFor(() => expect(screen.getByTestId("t-holder-options")).toHaveTextContent("周兰"));
    expect(screen.getByTestId("t-holder-options")).toHaveTextContent("人物");
    expect(screen.getByTestId("t-holder-options")).toHaveTextContent("当前视角可见");
    expect(screen.getByTestId("t-holder-options")).not.toHaveTextContent("沈墨"); // 不匹配关键字
  });

  it("I4: 多值选择回填 ID、chip 显示名称、重复选择去重", async () => {
    // 设计依据: 等价类—单值/多值；边界值—重复选择去重
    const user = userEvent.setup();
    const onChange = vi.fn();
    const { rerender } = render(
      <EntityPicker
        id="t-seen"
        label="见过的角色"
        refTypes={["character"]}
        mode="multi"
        value=""
        onChange={onChange}
      />,
    );
    const input = screen.getByTestId("t-seen");
    await user.type(input, "@兰");
    await waitFor(() => expect(screen.getByTestId("t-seen-options")).toHaveTextContent("周兰"));
    await user.click(within(screen.getByTestId("t-seen-options")).getByRole("button", { name: /周兰/ }));
    expect(onChange).toHaveBeenLastCalledWith("char-a");

    rerender(
      <EntityPicker
        id="t-seen"
        label="见过的角色"
        refTypes={["character"]}
        mode="multi"
        value="char-a"
        onChange={onChange}
      />,
    );
    expect(screen.getByText("周兰")).toBeInTheDocument(); // chip 显示名称（input 外的 chip 元素）
    await user.type(input, "@墨");
    await waitFor(() => expect(screen.getByTestId("t-seen-options")).toHaveTextContent("沈墨"));
    await user.click(within(screen.getByTestId("t-seen-options")).getByRole("button", { name: /沈墨/ }));
    expect(onChange).toHaveBeenLastCalledWith("char-a,char-b");
  });

  it("I5: 编辑保存 → PATCH properties.holder 为实体 ID（表单态存 ID 不存名称）", async () => {
    // 设计依据: 契约—存储层仍是 ID，名称仅显示层
    const user = userEvent.setup();
    useSelectionStore.setState({ selectedEntityId: "item-x", panelOpen: true });
    render(<EntityPanel />);
    await user.click(await screen.findByRole("button", { name: "编辑" }));
    const holderInput = screen.getByTestId("edit-prop-holder");
    await user.clear(holderInput);
    await user.type(holderInput, "@沈");
    await waitFor(() => expect(screen.getByTestId("edit-prop-holder-options")).toHaveTextContent("沈墨"));
    await user.click(
      within(screen.getByTestId("edit-prop-holder-options")).getByRole("button", { name: /沈墨/ }),
    );
    await user.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => {
      const props = (lastPatchBody ?? {}) as { properties?: Record<string, unknown> };
      expect(props.properties).toMatchObject({ holder: "char-b" }); // 原 char-a → 改选沈墨
    });
  });
});
