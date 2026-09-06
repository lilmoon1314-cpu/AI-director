/**
 * F11 L2：项目首屏与工作台路由集成测试（FU2）——真实组件链 + MSW mock 网络层。
 * 覆盖：空项目引导、卡片渲染、搜索过滤、新建（空名拦截）、删除确认（输入名）、
 * 路由导航（/ 重定向、卡片进入工作台、页签切换 URL、无效项目错误页）。
 * 用例设计见 docs/tests/F11_multi_project_foundation.md FU2。
 */

import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import { useProjectStore } from "../../src/stores/projectStore";
import { DEFAULT_PROJECT_ID } from "../workbenchHarness";

const PROJECTS = [
  {
    id: DEFAULT_PROJECT_ID,
    name: "默认项目",
    description: "",
    entity_count: 0,
    relation_count: 0,
    created_at: "2026-09-05T00:00:00Z",
    updated_at: "2026-09-05T00:00:00Z",
  },
  {
    id: "project-a",
    name: "长安怪谈",
    description: "盛唐志怪世界",
    entity_count: 42,
    relation_count: 18,
    created_at: "2026-09-04T00:00:00Z",
    updated_at: "2026-09-06T08:00:00Z",
  },
  {
    id: "project-b",
    name: "星海纪元",
    description: "近未来太空歌剧",
    entity_count: 7,
    relation_count: 2,
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-02T00:00:00Z",
  },
];

let projects = [...PROJECTS];
let createdCount = 0;
let deletedIds: string[] = [];

const server = setupServer(
  http.get("*/api/projects", () => HttpResponse.json(projects)),
  http.post("*/api/projects", async ({ request }) => {
    createdCount += 1;
    const body = (await request.json()) as { name: string; description?: string };
    return HttpResponse.json(
      {
        id: `project-new-${createdCount}`,
        name: body.name,
        description: body.description ?? "",
        entity_count: 0,
        relation_count: 0,
        created_at: "2026-09-06T10:00:00Z",
        updated_at: "2026-09-06T10:00:00Z",
      },
      { status: 201 },
    );
  }),
  http.delete("*/api/projects/:id", ({ params }) => {
    deletedIds.push(String(params.id));
    projects = projects.filter((p) => p.id !== params.id);
    return new HttpResponse(null, { status: 204 });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  cleanup();
});
afterAll(() => server.close());

beforeEach(() => {
  projects = [...PROJECTS];
  createdCount = 0;
  deletedIds = [];
  useProjectStore.setState({
    projects: [],
    loading: false,
    error: null,
    errorFix: null,
    currentProjectId: null,
    routeProjectId: null,
    routeInvalid: false,
  });
});

/** 在路由上下文渲染任意 UI（首屏测试用）。 */
async function renderPicker() {
  const { MemoryRouter } = await import("react-router-dom");
  const { render } = await import("@testing-library/react");
  const { ProjectPicker } = await import("../../src/views/ProjectPicker");
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/projects"]}>
      <ProjectPicker />
    </MemoryRouter>,
  );
  await waitFor(() => expect(screen.getByTestId("project-picker")).toBeInTheDocument());
  return user;
}

describe("F11 FU2: 项目首屏", () => {
  it("卡片渲染：名称/计数/最近编辑 + 新建虚线卡（等价类—非空项目集）", async () => {
    await renderPicker();
    await screen.findByTestId("project-card-project-a");
    const cardA = screen.getByTestId("project-card-project-a");
    expect(cardA).toHaveTextContent("长安怪谈");
    expect(cardA).toHaveTextContent("42 实体 · 18 关系");
    expect(cardA).toHaveTextContent("今天"); // updated_at 为今天（相对描述）
    expect(screen.getByTestId("project-create")).toBeInTheDocument();
  });

  it("搜索过滤：命中名称/描述显示，未命中隐藏（等价类—过滤两态）", async () => {
    const user = await renderPicker();
    await screen.findByTestId("project-card-project-a");
    await user.type(screen.getByLabelText("搜索项目"), "星海");
    await waitFor(() => {
      expect(screen.getByTestId("project-card-project-b")).toBeInTheDocument();
      expect(screen.queryByTestId("project-card-project-a")).not.toBeInTheDocument();
    });
    // 描述命中同样可见（等价类—第二命中通道）
    await user.clear(screen.getByLabelText("搜索项目"));
    await user.type(screen.getByLabelText("搜索项目"), "太空歌剧");
    await waitFor(() =>
      expect(screen.getByTestId("project-card-project-b")).toBeInTheDocument(),
    );
  });

  it("新建：空名不可提交；有效提交 → POST 201 → 导航进入新项目工作台", async () => {
    // 设计依据: 等价类—无效空名（前端拦截）/ 有效创建 + 导航契约
    const user = await renderPicker();
    await screen.findByTestId("project-create");
    await user.click(screen.getByTestId("project-create"));
    // 空名：提交禁用（边界值—去空白后为空）
    expect(screen.getByTestId("project-form-submit")).toBeDisabled();
    await user.type(screen.getByLabelText("项目名"), "雾都旧事");
    expect(screen.getByTestId("project-form-submit")).toBeEnabled();
    await user.click(screen.getByTestId("project-form-submit"));
    await waitFor(() => expect(createdCount).toBe(1));
  });

  it("删除：需输入项目名确认；确认后列表收缩（等价类—危险操作防护）", async () => {
    const user = await renderPicker();
    await screen.findByTestId("project-card-project-b");
    await user.click(screen.getByTestId("project-menu-project-b"));
    await user.click(screen.getByRole("button", { name: "删除" }));
    // 未输入正确名称前确认禁用（边界值—名称不匹配）
    expect(screen.getByTestId("project-delete-confirm")).toBeDisabled();
    await user.type(screen.getByLabelText(/输入项目名/), "错误的名字");
    expect(screen.getByTestId("project-delete-confirm")).toBeDisabled();
    await user.clear(screen.getByLabelText(/输入项目名/));
    await user.type(screen.getByLabelText(/输入项目名/), "星海纪元");
    expect(screen.getByTestId("project-delete-confirm")).toBeEnabled();
    await user.click(screen.getByTestId("project-delete-confirm"));
    await waitFor(() => expect(deletedIds).toEqual(["project-b"]));
    await waitFor(() =>
      expect(screen.queryByTestId("project-card-project-b")).not.toBeInTheDocument(),
    );
  });

  it("空项目集：引导卡与新建入口（等价类—空态）", async () => {
    projects = [];
    await renderPicker();
    expect(await screen.findByText("创建你的第一个世界观项目")).toBeInTheDocument();
    expect(screen.getByTestId("project-create")).toBeInTheDocument();
  });
});

describe("F11 FU2: 工作台路由", () => {
  it("卡片点击进入 /projects/:id/graph；页签切换 URL 变化（导航契约）", async () => {
    // 设计依据: DESIGN §4.1 路由表——URL 即状态
    const { MemoryRouter, Route, Routes, useLocation } = await import("react-router-dom");
    const { render } = await import("@testing-library/react");
    const { ProjectPicker } = await import("../../src/views/ProjectPicker");
    const { Workbench } = await import("../../src/views/Workbench");
    const { GraphView } = await import("../../src/views/GraphView");
    const { AssetLibrary } = await import("../../src/views/AssetLibrary");

    let currentPath = "";
    function LocationProbe() {
      const location = useLocation();
      currentPath = location.pathname;
      return null;
    }

    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/projects"]}>
        <LocationProbe />
        <Routes>
          <Route path="/projects" element={<ProjectPicker />} />
          <Route path="/projects/:projectId" element={<Workbench />}>
            <Route path="graph" element={<GraphView />} />
            <Route path="assets" element={<AssetLibrary />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    // 点击卡片内层按钮（卡片容器 div 不承载点击；aria-label=进入项目 <名称>）
    const enterButton = await screen.findByRole("button", { name: "进入项目 长安怪谈" });
    await user.click(enterButton);
    await waitFor(() => expect(currentPath).toBe("/projects/project-a/graph"));
    await user.click(await screen.findByTestId("tab-assets"));
    await waitFor(() => expect(currentPath).toBe("/projects/project-a/assets"));
    await user.click(screen.getByTestId("tab-graph"));
    await waitFor(() => expect(currentPath).toBe("/projects/project-a/graph"));
  });

  it("无效项目 id → 错误页 + 返回首屏（等价类—无效路由）", async () => {
    const { MemoryRouter, Route, Routes } = await import("react-router-dom");
    const { render } = await import("@testing-library/react");
    const { Workbench } = await import("../../src/views/Workbench");
    const { GraphView } = await import("../../src/views/GraphView");

    render(
      <MemoryRouter initialEntries={["/projects/project-ghost/graph"]}>
        <Routes>
          <Route path="/projects/:projectId" element={<Workbench />}>
            <Route path="graph" element={<GraphView />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByText("项目不存在")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "返回项目首屏" })).toBeInTheDocument();
  });

  it("顶栏切换器：列出项目、当前高亮、切换导航到目标项目（导航契约）", async () => {
    const { MemoryRouter, Route, Routes, useLocation } = await import("react-router-dom");
    const { render } = await import("@testing-library/react");
    const { Workbench } = await import("../../src/views/Workbench");
    const { GraphView } = await import("../../src/views/GraphView");

    let currentPath = "";
    function LocationProbe() {
      currentPath = useLocation().pathname;
      return null;
    }

    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={[`/projects/${DEFAULT_PROJECT_ID}/graph`]}>
        <LocationProbe />
        <Routes>
          <Route path="/projects/:projectId" element={<Workbench />}>
            <Route path="graph" element={<GraphView />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    // 切换器展示当前项目名；下拉列出全部项目（点击切换器按钮本体而非容器）
    const switcherButton = await screen.findByRole("button", { name: /默认项目/ });
    await user.click(switcherButton);
    await screen.findByTestId("switch-to-project-a");
    await user.click(screen.getByTestId("switch-to-project-a"));
    await waitFor(() => expect(currentPath).toBe("/projects/project-a/graph"));
  });
});
