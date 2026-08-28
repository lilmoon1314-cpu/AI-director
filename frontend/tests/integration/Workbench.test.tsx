/**
 * F05 L2：Workbench 组件树集成测试（I1–I8）——真实组件链 + MSW mock 网络层。
 * 测试世界与期望见 docs/tests/F05_frontend_graph_workbench.md；
 * @antv/g6 为测试桩（test.alias），节点点击经桩实例 emit 触发真实回调链。
 */

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import { Graph } from "../../src/test-stubs/g6-stub";
import { Workbench } from "../../src/views/Workbench";

// ---- 测试世界（可变状态：CRUD 用例修改后影响后续 graph 响应） ----

interface SeedEntity {
  id: string;
  type: string;
  name: string;
  aliases: string[];
  description: string;
  audience_known: boolean;
  properties?: Record<string, unknown>;
}

let entities: SeedEntity[] = [];
let relations: { id: string; source: string; target: string; type: string }[] = [];
let createCalls = 0;
let deleteCalls = 0;
let lastPatchBody: Record<string, unknown> | null = null;
let genSeq = 0;

function resetWorld() {
  entities = [
    { id: "char-a", type: "character", name: "周兰", aliases: [], description: "", audience_known: true },
    { id: "char-b", type: "character", name: "沈墨", aliases: [], description: "", audience_known: false },
    { id: "char-c", type: "character", name: "陆离", aliases: [], description: "", audience_known: true },
    { id: "item-x", type: "item", name: "青铜镜", aliases: [], description: "", audience_known: false },
    {
      id: "event-e",
      type: "event",
      name: "夜探药庐",
      aliases: [],
      description: "",
      audience_known: true,
      properties: { known_by: ["char-b"], place: "药庐后院" },
    },
    { id: "loc-l", type: "location", name: "青云山", aliases: [], description: "", audience_known: true },
  ];
  relations = [
    { id: "rel-1", source: "char-a", target: "char-b", type: "ALLY" },
    { id: "rel-2", source: "char-a", target: "loc-l", type: "LIVES_IN" },
    { id: "rel-3", source: "char-b", target: "event-e", type: "PARTICIPATES" },
  ];
  createCalls = 0;
  deleteCalls = 0;
  lastPatchBody = null;
}

const graphBody = () => ({
  nodes: entities.map((e) => ({ id: e.id, type: e.type, name: e.name, aliases: e.aliases })),
  edges: relations.map((r) => ({ id: r.id, source: r.source, target: r.target, type: r.type })),
});

const server = setupServer(
  http.get("*/api/graph", ({ request }) => {
    const url = new URL(request.url);
    if (url.searchParams.get("perspective") !== "author") {
      return HttpResponse.json({ code: "INVALID", problem: "仅支持 author" }, { status: 400 });
    }
    return HttpResponse.json(graphBody());
  }),
  http.get("*/api/entities/:id", ({ params }) => {
    const found = entities.find((e) => e.id === params.id);
    if (!found) {
      return HttpResponse.json(
        { code: "NOT_FOUND", problem: "实体不存在", cause: "id 未在实体库", fix: "检索确认 id" },
        { status: 404 },
      );
    }
    return HttpResponse.json({ ...found, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" });
  }),
  http.post("*/api/entities", async ({ request }) => {
    createCalls += 1;
    const body = (await request.json()) as Partial<SeedEntity>;
    genSeq += 1;
    const created: SeedEntity = {
      id: `gen-${genSeq}`,
      type: body.type ?? "character",
      name: body.name ?? "",
      aliases: body.aliases ?? [],
      description: body.description ?? "",
      audience_known: body.audience_known ?? false,
    };
    entities.push(created);
    return HttpResponse.json(
      { ...created, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
      { status: 201 },
    );
  }),
  http.patch("*/api/entities/:id", async ({ request, params }) => {
    const found = entities.find((e) => e.id === params.id);
    if (!found) return HttpResponse.json({ problem: "实体不存在" }, { status: 404 });
    const body = (await request.json()) as Partial<SeedEntity>;
    lastPatchBody = body;
    Object.assign(found, body);
    return HttpResponse.json({ ...found, updated_at: "2026-01-02T00:00:00Z" });
  }),
  http.delete("*/api/entities/:id", ({ params }) => {
    deleteCalls += 1;
    const id = String(params.id);
    if (relations.some((r) => r.source === id || r.target === id)) {
      return HttpResponse.json(
        {
          code: "ENTITY_REFERENCED",
          problem: "实体被关系引用，无法删除",
          cause: `id '${id}' 仍被 relationships 引用`,
          fix: "先删除该实体的全部关系再试",
        },
        { status: 409 },
      );
    }
    entities = entities.filter((e) => e.id !== id);
    return new HttpResponse(null, { status: 204 });
  }),
  http.post("*/api/relations", () => new HttpResponse(null, { status: 501 })),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  cleanup();
});
afterAll(() => server.close());

beforeEach(() => {
  resetWorld();
  Graph.instances.length = 0;
  vi.clearAllMocks();
});

async function renderWorkbench() {
  const user = userEvent.setup();
  render(<Workbench />);
  await waitFor(() => expect(screen.getByTestId("graph-stats")).toHaveTextContent("6 节点 · 3 边"));
  return user;
}

describe("Workbench 集成（I1–I8）", () => {
  it("I1: 挂载经 MSW 加载 author 全量并渲染（6 节点 3 边）", async () => {
    // 设计依据: 等价类—数据加载主路径
    await renderWorkbench();
    expect(Graph.instances).toHaveLength(1);
  });

  it("I2: 节点点击 → 拉取详情 → 面板展示名称与类型", async () => {
    // 设计依据: 主路径—点击详情
    const user = await renderWorkbench();
    Graph.instances[0]?.emit("node:click", { target: { id: "char-a" } });
    const panel = await screen.findByTestId("entity-panel");
    expect(panel).toHaveTextContent("周兰");
    expect(panel).toHaveTextContent("character");
    expect(panel).toHaveClass("backdrop-blur-xl");
    // 面板不再需要时保持可关闭
    await user.click(screen.getByRole("button", { name: "关闭面板" }));
    expect(screen.queryByTestId("entity-panel")).not.toBeInTheDocument();
  });

  it("I3: 新建实体（合法最小输入）→ POST 201 → 图刷新为 7 节点", async () => {
    // 设计依据: 等价类—创建有效；边界值—name 单字符（最小合法）
    const user = await renderWorkbench();
    await user.type(screen.getByLabelText("名称"), "顾");
    await user.click(screen.getByRole("button", { name: "创建" }));
    await waitFor(() => expect(screen.getByTestId("graph-stats")).toHaveTextContent("7 节点"));
    expect(createCalls).toBe(1);
  });

  it("I4: 新建实体（空名称）→ 前端拦截，零网络请求", async () => {
    // 设计依据: 无效等价类—必填缺失；边界值—空串
    const user = await renderWorkbench();
    await user.click(screen.getByRole("button", { name: "创建" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("名称不能为空");
    expect(createCalls).toBe(0);
    expect(screen.getByTestId("graph-stats")).toHaveTextContent("6 节点");
  });

  it("I5: 编辑实体名称 → PATCH 200 → 面板与图更新", async () => {
    // 设计依据: 等价类—更新有效
    const user = await renderWorkbench();
    Graph.instances[0]?.emit("node:click", { target: { id: "char-a" } });
    await user.click(await screen.findByRole("button", { name: "编辑" }));
    // 创建表单与编辑表单都有「名称」字段，selector 限定编辑面板内的输入
    const nameInput = screen.getByLabelText("名称", { selector: "#edit-name" });
    await user.clear(nameInput);
    await user.type(nameInput, "周兰然");
    await user.click(screen.getByRole("button", { name: "保存" }));
    const panel = await screen.findByTestId("entity-panel");
    await waitFor(() => expect(panel).toHaveTextContent("周兰然"));
    await waitFor(() => expect(screen.getByTestId("graph-stats")).toHaveTextContent("6 节点 · 3 边"));
  });

  it("I6: 删除无引用实体成功；被引用实体 409 展示后端三要素", async () => {
    // 设计依据: 主路径—删除含确认；边界值—引用完整性防线（F02 双层删除）前端呈现
    const user = await renderWorkbench();

    // 成功分支：char-c 孤立无引用
    Graph.instances[0]?.emit("node:click", { target: { id: "char-c" } });
    await user.click(await screen.findByRole("button", { name: "删除" }));
    await user.click(await screen.findByRole("button", { name: "确认删除" }));
    await waitFor(() => expect(screen.getByTestId("graph-stats")).toHaveTextContent("5 节点"));

    // 拒绝分支：loc-l 被 rel-2 引用
    Graph.instances[0]?.emit("node:click", { target: { id: "loc-l" } });
    await user.click(await screen.findByRole("button", { name: "删除" }));
    await user.click(await screen.findByRole("button", { name: "确认删除" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("实体被关系引用，无法删除");
    expect(alert).toHaveTextContent("先删除该实体的全部关系再试");
    expect(screen.getByTestId("graph-stats")).toHaveTextContent("5 节点"); // 被拒节点保留
    expect(deleteCalls).toBe(2); // 两次删除请求均真实发出（一成功一被拒）
  });

  it("I7: 面板与侧栏为毛玻璃半透明（视觉硬约束锚点）", async () => {
    // 设计依据: frontend/CONSTRAINTS 视觉约束
    await renderWorkbench();
    const sidebars = document.querySelectorAll(".backdrop-blur-xl");
    expect(sidebars.length).toBeGreaterThanOrEqual(2); // 侧栏 + 画布容器
    Graph.instances[0]?.emit("node:click", { target: { id: "char-a" } });
    const panel = await screen.findByTestId("entity-panel");
    expect(panel).toHaveClass("backdrop-blur-xl");
    expect(panel.className).toContain("bg-white/55"); // 半透明底
  });

  it("I8: API 不可达 → 错误提示组件而非白屏", async () => {
    // 设计依据: 无效等价类—网络失败
    server.use(
      http.get("*/api/graph", () => HttpResponse.error()),
    );
    render(<Workbench />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("无法连接服务器");
  });

  it("I9: properties 只读展示（known_by 等蓝图参数可见）", async () => {
    // 设计依据: 增强轮—详情面板展示完整参数（properties 键值）
    await renderWorkbench();
    Graph.instances[0]?.emit("node:click", { target: { id: "event-e" } });
    const props = await screen.findByTestId("entity-properties");
    expect(props).toHaveTextContent("known_by");
    expect(props).toHaveTextContent("char-b");
    expect(props).toHaveTextContent("place");
    expect(props).toHaveTextContent("药庐后院");
  });

  it("I10: properties JSON 编辑 → PATCH 携带新值 → 面板更新", async () => {
    // 设计依据: 增强轮—参数修改主路径；无效 JSON 阻止提交
    const user = await renderWorkbench();
    Graph.instances[0]?.emit("node:click", { target: { id: "event-e" } });
    await user.click(await screen.findByRole("button", { name: "编辑" }));
    const propsInput = screen.getByLabelText("属性 properties（JSON）", { selector: "#edit-props" });
    // JSON 含 {}——userEvent.type 会将其解析为键盘特殊键标记，改用 change 事件直接设值
    await user.clear(propsInput);
    fireEvent.change(propsInput, { target: { value: '{"known_by": ["char-a", "char-b"]}' } });
    await user.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => {
      const props = (lastPatchBody ?? {}) as { properties?: Record<string, unknown> };
      expect(props.properties).toEqual({ known_by: ["char-a", "char-b"] });
    });
    const panel = await screen.findByTestId("entity-panel");
    await waitFor(() => expect(panel).toHaveTextContent("char-a"));
  });

  it("I11: 新建手风琴——实体默认展开、关系默认收起，点标题展开", async () => {
    // 设计依据: 增强轮—折叠收纳交互（提示文字 aria-hidden，按钮名即「关系」）
    const user = await renderWorkbench();
    expect(screen.getByTestId("create-entity-form")).toBeInTheDocument();
    expect(screen.queryByTestId("create-relation-form")).not.toBeInTheDocument();
    const relationToggle = screen.getByRole("button", { name: "关系", exact: true });
    await user.click(relationToggle); // 展开
    expect(screen.getByTestId("create-relation-form")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "关系", exact: true })); // 再点收起
    expect(screen.queryByTestId("create-relation-form")).not.toBeInTheDocument();
  });

  it("I12: 操作栏收起/展开（图区占满，状态可恢复）", async () => {
    // 设计依据: 增强轮—工作台收起展开
    const user = await renderWorkbench();
    await user.click(screen.getByRole("button", { name: "收起操作栏" }));
    expect(screen.queryByTestId("sidebar")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "展开操作栏" }));
    expect(screen.getByTestId("sidebar")).toBeInTheDocument();
  });
});
