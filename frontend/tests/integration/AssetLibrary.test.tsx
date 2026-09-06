/**
 * F12 L2：资产管理集成测试（FI1–FI12，docs/tests/F12_workbench_navigation_assets.md）
 * ——真实组件链 + MSW mock 网络层，路由化 harness（镜像 App.tsx 资产三级子路由）。
 * 继承 F08 IF1–IF4 的等价类语义并迁移到两级钻取路径；@antv/g6 为测试桩。
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { useEffect } from "react";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { setupServer } from "msw/node";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import { Graph } from "../../src/test-stubs/g6-stub";
import { GraphView } from "../../src/views/GraphView";
import { Workbench } from "../../src/views/Workbench";
import { renderWorkbench as renderWorkbenchRoute } from "../workbenchHarness";
import { useAssetStore } from "../../src/stores/assetStore";
import { useProjectStore } from "../../src/stores/projectStore";
import { DEFAULT_PROJECT_ID } from "../workbenchHarness";

// ---- 测试世界 ----

let entities: Record<string, unknown>[] = [];
let generalAssets: Record<string, unknown>[] = [];
let entityImages: Record<string, unknown>[] = [];
let entityCards: Record<string, unknown>[] = [];
let createCalls = 0;

function resetWorld() {
  entities = [
    { id: "char-a", type: "character", name: "周兰", aliases: [], description: "主角", audience_known: true, properties: {} },
    { id: "loc-a", type: "location", name: "沉星湖", aliases: [], description: "荒废古湖", audience_known: true, properties: {} },
  ];
  generalAssets = [
    {
      id: "asset-g1",
      category: "表情参考",
      title: "愤怒",
      description: "皱眉",
      cover_url: "http://mock.local/static/assets/g1.png",
      image_count: 2,
      updated_at: "2026-09-05T00:00:00Z",
    },
    {
      id: "asset-g2",
      category: "风格参考",
      title: "水墨",
      description: "青灰色调",
      cover_url: null,
      image_count: 0,
      updated_at: "2026-09-05T00:00:00Z",
    },
  ];
  entityImages = [
    {
      id: "img-1",
      scope: "entity",
      owner_id: "char-a",
      filename_orig: "a.png",
      stored_name: "a.png",
      mime: "image/png",
      size: 1,
      created_at: "2026-09-05T00:00:00Z",
      url: "http://mock.local/static/assets/a.png",
    },
  ];
  entityCards = [
    {
      id: "char-a",
      type: "character",
      name: "周兰",
      description: "主角",
      cover_url: "http://mock.local/static/assets/a.png",
      image_count: 1,
    },
    {
      id: "loc-a",
      type: "location",
      name: "沉星湖",
      description: "荒废古湖",
      cover_url: null,
      image_count: 0,
    },
  ];
  createCalls = 0;
}

const server = setupServer(
  http.get("http://mock.local/api/projects", () =>
    HttpResponse.json([
      {
        id: DEFAULT_PROJECT_ID,
        name: "默认项目",
        description: "",
        entity_count: 6,
        relation_count: 3,
        created_at: "2026-09-06T00:00:00Z",
        updated_at: "2026-09-06T00:00:00Z",
      },
    ]),
  ),
  http.get("http://mock.local/api/graph", () =>
    HttpResponse.json({ nodes: [], edges: [] }),
  ),
  http.get("http://mock.local/api/entities", () => HttpResponse.json(entities)),
  http.get("http://mock.local/api/entities/:id", ({ params }) => {
    const entity = entities.find((e) => e.id === params.id);
    return entity
      ? HttpResponse.json(entity)
      : HttpResponse.json(
          { code: "NOT_FOUND", problem: "实体不存在", cause: "id 未在库中", fix: "检索确认 id", detail: {} },
          { status: 404 },
        );
  }),
  http.get("http://mock.local/api/characters", () => HttpResponse.json([])),
  http.get("http://mock.local/api/assets/general", () =>
    HttpResponse.json(generalAssets),
  ),
  http.get("http://mock.local/api/assets/entities", () =>
    HttpResponse.json(entityCards),
  ),
  http.get("http://mock.local/api/assets/images", ({ request }) => {
    const url = new URL(request.url);
    const scope = url.searchParams.get("scope");
    const owner = url.searchParams.get("owner_id");
    return HttpResponse.json(
      entityImages.filter((i) => i.scope === scope && i.owner_id === owner),
    );
  }),
  http.post("http://mock.local/api/assets/general", async ({ request }) => {
    createCalls += 1;
    const body = (await request.json()) as Record<string, unknown>;
    const asset = {
      id: `asset-new-${createCalls}`,
      kind: "general",
      category: body.category ?? "",
      title: body.title,
      description: body.description ?? "",
      attributes: body.attributes ?? {},
      cover_image_id: null,
      cover_url: null,
      images: [],
      created_at: "2026-09-05T00:00:00Z",
      updated_at: "2026-09-05T00:00:00Z",
    };
    generalAssets = [
      {
        id: asset.id,
        category: asset.category,
        title: asset.title,
        description: asset.description,
        cover_url: null,
        image_count: 0,
        updated_at: asset.updated_at,
      },
      ...generalAssets,
    ];
    return HttpResponse.json(asset, { status: 201 });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  cleanup();
  Graph.instances.length = 0;
});
afterAll(() => server.close());

beforeEach(() => {
  resetWorld();
  // assetStore 为模块级缓存（generalCards 跨项目保留语义），跨用例必须清零防泄漏
  useAssetStore.setState({
    generalCards: [],
    generalLoading: false,
    generalError: null,
    entityCards: [],
    entityLoading: false,
    entityError: null,
    entityCardsProjectId: null,
    viewer: null,
  });
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

async function goToAssets() {
  renderWorkbenchRoute();
  await userEvent.click(await screen.findByTestId("tab-assets"));
  await waitFor(() => expect(screen.getByTestId("section-general")).toBeTruthy());
}

// ---------------- 路由化：默认落点与深链（FI1/FI2/FI4） ----------------

describe("F12 路由化（FI1/FI2/FI4）", () => {
  it("FI1: /assets 默认落点重定向通用参考库（等价类—默认路由，OQ-6）", async () => {
    renderWorkbenchRoute(`/projects/${DEFAULT_PROJECT_ID}/assets`);
    expect(await screen.findByTestId("section-general")).toBeTruthy();
    expect(screen.getByTestId("general-asset-grid")).toBeTruthy();
  });

  it("FI2: 深链直达——类型库墙与类型库详情各渲染（等价类—深链，URL 即状态）", async () => {
    renderWorkbenchRoute(`/projects/${DEFAULT_PROJECT_ID}/assets/project`);
    expect(await screen.findByTestId("asset-type-wall")).toBeTruthy();
    cleanup();
    Graph.instances.length = 0;

    renderWorkbenchRoute(`/projects/${DEFAULT_PROJECT_ID}/assets/project/character`);
    expect(await screen.findByText("人物库")).toBeTruthy();
    expect(await screen.findByTestId("entity-asset-char-a")).toBeTruthy();
  });

  it.each(["ghost-type", "CHARACTER", "123"])(
    "FI4: 无效 entityType=%s 深链 → 重定向回类型库墙（等价类—无效路由参数：7 类型域外字符串）",
    async (ghost) => {
      renderWorkbenchRoute(`/projects/${DEFAULT_PROJECT_ID}/assets/project/${ghost}`);
      expect(await screen.findByTestId("asset-type-wall")).toBeTruthy();
      cleanup();
      Graph.instances.length = 0;
    },
  );
});

// ---------------- 两级钻取导航（FI3）与既有页签往返（IF1） ----------------

describe("F12 两级钻取（FI3）+ IF1 页签往返", () => {
  it("FI3: 墙卡片聚合计数 → 详情面包屑/卡片墙 → asset-type-back 返回（导航契约）", async () => {
    await goToAssets();
    await userEvent.click(screen.getByTestId("section-project"));

    const characterCard = await screen.findByTestId("asset-type-card-character");
    expect(characterCard.textContent).toContain("人物库");
    expect(characterCard.textContent).toContain("1 实体");
    expect(characterCard.textContent).toContain("1 张图");

    await userEvent.click(characterCard);
    expect(await screen.findByTestId("entity-asset-char-a")).toBeTruthy();
    expect(screen.getByTestId("asset-type-back")).toBeTruthy();

    await userEvent.click(screen.getByTestId("asset-type-back"));
    await waitFor(() => expect(screen.getByTestId("asset-type-wall")).toBeTruthy());
  });

  it("IF1: 默认图谱页；切资产页再切回图谱（往返，操作栏仍在）", async () => {
    renderWorkbenchRoute();
    expect(await screen.findByTestId("sidebar")).toBeTruthy();
    expect(await screen.findByTestId("graph-stats")).toBeTruthy();
    expect(screen.queryByTestId("section-general")).toBeNull();

    await userEvent.click(await screen.findByTestId("tab-assets"));
    await waitFor(() => expect(screen.getByTestId("section-general")).toBeTruthy());
    expect(screen.getByTestId("create-asset")).toBeTruthy();
    await userEvent.click(screen.getByTestId("section-project"));
    expect(screen.getByTestId("asset-type-wall")).toBeTruthy();
    await userEvent.click(screen.getByTestId("tab-graph"));
    expect(await screen.findByTestId("sidebar")).toBeTruthy();
    expect(screen.queryByTestId("section-general")).toBeNull();
  });
});

// ---------------- 通用参考库：搜索 / 空态 / modal（FI5/FI7/FI8/FI12） ----------------

describe("F12 通用参考库（FI5/FI7/FI8/FI12）", () => {
  it("FI5: 分区搜索过滤 + 与 chips AND 叠加；无命中提示区分空库（等价类—组合 + 边界值—过滤空集）", async () => {
    await goToAssets();
    await userEvent.type(screen.getByTestId("asset-search"), "青灰");
    await waitFor(() => expect(screen.getAllByTestId("general-asset-asset-g2")).toHaveLength(1));
    expect(screen.queryByTestId("general-asset-asset-g1")).toBeNull();

    // AND：query 命中 g2 描述，但 chip 选表情参考 → 无命中
    await userEvent.click(screen.getByTestId("category-表情参考"));
    expect(await screen.findByTestId("asset-search-empty")).toBeTruthy();

    // 清空 query → chip 单独生效
    await userEvent.clear(screen.getByTestId("asset-search"));
    await waitFor(() => expect(screen.getAllByTestId("general-asset-asset-g1")).toHaveLength(1));
    expect(screen.queryByTestId("asset-search-empty")).toBeNull();
  });

  it("FI7: 空库引导卡 + 主按钮打开 modal（等价类—空集）", async () => {
    server.use(http.get("http://mock.local/api/assets/general", () => HttpResponse.json([])));
    await goToAssets();
    const empty = await screen.findByTestId("asset-general-empty");
    expect(empty.textContent).toContain("创建第一个参考库");
    await userEvent.click(screen.getByTestId("create-asset"));
    expect(screen.getByTestId("general-asset-modal")).toBeTruthy();
  });

  it("FI8: modal 化——打开时卡片墙不被替换；空标题拦截；保存转编辑态；取消关闭（OQ-3）", async () => {
    await goToAssets();
    await userEvent.click(screen.getByTestId("create-asset"));
    expect(screen.getByTestId("general-asset-modal")).toBeTruthy();
    // 卡片墙仍在文档中（不再整区替换）
    expect(screen.getByTestId("general-asset-grid")).toBeTruthy();

    await userEvent.click(screen.getByRole("button", { name: "保存" }));
    expect(screen.getByText("标题不能为空")).toBeTruthy();
    expect(createCalls).toBe(0);

    await userEvent.type(screen.getByLabelText("标题 *"), "平静");
    await userEvent.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => expect(createCalls).toBe(1));
    await waitFor(() => expect(screen.getByTestId("asset-images")).toBeTruthy());

    await userEvent.click(screen.getByRole("button", { name: "取消" }));
    await waitFor(() => expect(screen.queryByTestId("general-asset-modal")).toBeNull());
    expect(screen.getByTestId("create-asset")).toBeTruthy();
  });

  it("FI12: 编辑按钮 hover 与 focus-within 均可见（§9 键盘可达契约）", async () => {
    await goToAssets();
    const edit = await screen.findByTestId("edit-asset-asset-g1");
    expect(edit.className).toContain("group-hover:opacity-100");
    expect(edit.className).toContain("group-focus-within:opacity-100");
  });
});

// ---------------- 类型库详情：搜索 / 空态 / 查看器（FI6/FI9/FI10） ----------------

describe("F12 类型库详情（FI6/FI9/FI10）", () => {
  it("FI6: 详情搜索按名称/描述过滤实体卡（等价类—有效过滤 + 无效—无命中）", async () => {
    await goToAssets();
    await userEvent.click(screen.getByTestId("section-project"));
    await userEvent.click(await screen.findByTestId("asset-type-card-character"));

    await userEvent.type(screen.getByTestId("asset-search"), "周兰");
    await waitFor(() => expect(screen.getAllByTestId("entity-asset-char-a")).toHaveLength(1));
    await userEvent.clear(screen.getByTestId("asset-search"));
    await userEvent.type(screen.getByTestId("asset-search"), "不存在的名字");
    expect(await screen.findByTestId("asset-search-empty")).toBeTruthy();
  });

  it("FI9: 实体卡 → 查看器 iframe 指向实体 HTML 资产页 → 返回关闭（IF3 迁移）", async () => {
    await goToAssets();
    await userEvent.click(screen.getByTestId("section-project"));
    await userEvent.click(await screen.findByTestId("asset-type-card-character"));

    const card = await screen.findByTestId("entity-asset-char-a");
    await userEvent.click(card);
    const viewer = await screen.findByTestId("asset-viewer");
    const frame = screen.getByTestId("asset-viewer-frame") as HTMLIFrameElement;
    expect(frame.src).toBe("http://mock.local/api/assets/entity/char-a/page");
    expect(viewer.textContent).toContain("周兰");

    await userEvent.click(screen.getByRole("button", { name: "返回资产列表" }));
    expect(screen.queryByTestId("asset-viewer")).toBeNull();
  });

  it("FI10: 空类型——墙虚线卡与详情深链均引导去图谱页并预选类型（等价类—空集 + 联动契约）", async () => {
    await goToAssets();
    await userEvent.click(screen.getByTestId("section-project"));
    // 墙上空类型（功法 0 实体）：点击直达图谱页新建表单并预选 skill
    await userEvent.click(screen.getByTestId("asset-type-card-skill"));
    expect(await screen.findByTestId("create-entity-form")).toBeTruthy();
    expect((screen.getByLabelText("类型") as HTMLSelectElement).value).toBe("skill");

    // 详情深链（location 有实体但 skill 无）：空类型引导卡
    cleanup();
    Graph.instances.length = 0;
    renderWorkbenchRoute(`/projects/${DEFAULT_PROJECT_ID}/assets/project/skill`);
    const empty = await screen.findByText("暂无功法实体");
    expect(empty).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "去图谱页创建" }));
    expect(await screen.findByTestId("create-entity-form")).toBeTruthy();
    expect((screen.getByLabelText("类型") as HTMLSelectElement).value).toBe("skill");
  });
});

// ---------------- 图谱页联动（FI11）与实体面板（IF4） ----------------

describe("F12 图谱页联动（FI11）+ IF4 实体面板图片区", () => {
  /** 路由位置探针：把当前 pathname+search 回传给断言（URL 即状态契约）。 */
  function LocationProbe({ onLocation }: { onLocation: (url: string) => void }) {
    const location = useLocation();
    useEffect(() => {
      onLocation(location.pathname + location.search);
    }, [location, onLocation]);
    return null;
  }

  it("FI11: ?create=entity&type=<valid> 展开新建表单并预选类型，消费后清理查询参数（防重挂载重复弹出）", async () => {
    let currentUrl = "";
    render(
      <MemoryRouter
        initialEntries={[`/projects/${DEFAULT_PROJECT_ID}/graph?create=entity&type=location`]}
      >
        <Routes>
          <Route path="/projects/:projectId" element={<Workbench />}>
            <Route
              path="graph"
              element={
                <>
                  <GraphView />
                  <LocationProbe onLocation={(url) => (currentUrl = url)} />
                </>
              }
            />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByTestId("create-entity-form")).toBeTruthy();
    expect((screen.getByLabelText("类型") as HTMLSelectElement).value).toBe("location");
    // 参数被消费后清理：URL 回归纯净路径（删除 setSearchParams 清理逻辑此断言必红）
    await waitFor(() =>
      expect(currentUrl).toBe(`/projects/${DEFAULT_PROJECT_ID}/graph`),
    );
    cleanup();
    Graph.instances.length = 0;

    // 无效类型回落默认（不崩溃、表单仍展开）
    renderWorkbenchRoute(`/projects/${DEFAULT_PROJECT_ID}/graph?create=entity&type=ghost`);
    expect(await screen.findByTestId("create-entity-form")).toBeTruthy();
    expect((screen.getByLabelText("类型") as HTMLSelectElement).value).toBe("character");
  });

  it("FI13: 加载失败 → 三要素错误条 + 重试恢复，不误显空库引导（DESIGN §5.3.1 error 态）", async () => {
    server.use(
      http.get("http://mock.local/api/assets/general", () => new HttpResponse(null, { status: 500 })),
      http.get("http://mock.local/api/assets/entities", () => new HttpResponse(null, { status: 500 })),
    );
    await goToAssets();

    // 通用区错误条：problem + 修复（fix）+ 重试；空库引导卡不得出现
    const err = await screen.findByTestId("asset-general-error");
    expect(err.textContent).toContain("请求失败");
    expect(err.textContent).toContain("修复：");
    expect(screen.queryByTestId("asset-general-empty")).toBeNull();

    // 恢复 handler → 重试 → 错误条消失、卡片出现
    server.use(
      http.get("http://mock.local/api/assets/general", () => HttpResponse.json(generalAssets)),
    );
    await userEvent.click(screen.getByRole("button", { name: "重试" }));
    await waitFor(() => expect(screen.queryByTestId("asset-general-error")).toBeNull());
    expect(screen.getByTestId("general-asset-grid")).toBeTruthy();

    // 项目资产区同一错误模式
    await userEvent.click(screen.getByTestId("section-project"));
    expect(await screen.findByTestId("asset-project-error")).toBeTruthy();
    server.use(
      http.get("http://mock.local/api/assets/entities", () => HttpResponse.json(entityCards)),
    );
    await userEvent.click(screen.getByRole("button", { name: "重试" }));
    await waitFor(() => expect(screen.queryByTestId("asset-project-error")).toBeNull());
    expect(screen.getByTestId("asset-type-wall")).toBeTruthy();
  });

  it("IF4: 选中实体 → 图片明细渲染 + 「查看资产页」打开查看器（F08 既有链路）", async () => {
    renderWorkbenchRoute();
    await waitFor(() => expect(Graph.instances.length).toBeGreaterThan(0));
    Graph.instances[0]?.emit("node:click", { target: { id: "char-a" } });

    const assets = await screen.findByTestId("entity-assets");
    await waitFor(() => {
      expect(assets.textContent).toContain("资产图片（1）");
    });
    const img = screen.getByAltText("a.png");
    expect(img).toHaveProperty("src", "http://mock.local/static/assets/a.png");

    await userEvent.click(screen.getByTestId("open-entity-page"));
    expect(screen.getByTestId("asset-viewer-frame")).toBeTruthy();
  });
});
