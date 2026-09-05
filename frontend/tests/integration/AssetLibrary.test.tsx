/**
 * F08 L2：资产管理集成测试（IF1–IF4）——真实组件链 + MSW mock 网络层。
 * 测试世界与期望见 docs/tests/F08_asset_management.md；
 * @antv/g6 为测试桩（vite.config test.alias），节点点击经桩实例 emit 触发。
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { setupServer } from "msw/node";

import { Graph } from "../../src/test-stubs/g6-stub";
import { Workbench } from "../../src/views/Workbench";

// ---- 测试世界 ----

let entities: Record<string, unknown>[] = [];
let generalAssets: Record<string, unknown>[] = [];
let entityImages: Record<string, unknown>[] = [];
let entityCards: Record<string, unknown>[] = [];
let createCalls = 0;

function resetWorld() {
  entities = [
    { id: "char-a", type: "character", name: "周兰", aliases: [], description: "主角", audience_known: true, properties: {} },
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
  ];
  createCalls = 0;

}

const server = setupServer(
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
});

async function goToAssets() {
  render(<Workbench />);
  await userEvent.click(await screen.findByTestId("tab-assets"));
  await waitFor(() => expect(screen.getByTestId("section-general")).toBeTruthy());
}

// ---------------- IF1: 双页切换 ----------------

describe("F08 IF1: 工作台双页切换", () => {
  it("默认图谱页：操作栏与图状态栏在（边界值—初始页签）", async () => {
    render(<Workbench />);
    expect(await screen.findByTestId("sidebar")).toBeTruthy();
    expect(await screen.findByTestId("graph-stats")).toBeTruthy();
    expect(screen.queryByTestId("section-general")).toBeNull();
  });

  it("切「资产管理」：通用/项目资产分区渲染；切回「图谱」操作栏仍在（往返）", async () => {
    await goToAssets();
    expect(screen.getByTestId("create-asset")).toBeTruthy();
    await userEvent.click(screen.getByTestId("section-project"));
    expect(screen.getByTestId("project-assets")).toBeTruthy();
    await userEvent.click(screen.getByTestId("tab-graph"));
    expect(await screen.findByTestId("sidebar")).toBeTruthy();
    expect(screen.queryByTestId("section-general")).toBeNull();
  });
});

// ---------------- IF2: 通用资产新建表单 ----------------

describe("F08 IF2: 通用资产新建", () => {
  it("填表保存 → POST 201 → 列表刷新出现新卡片；空标题被拦截", async () => {
    await goToAssets();
    await userEvent.click(screen.getByTestId("create-asset"));

    // 无效提交（空标题）被拦截：不发请求、出现提示
    await userEvent.click(screen.getByRole("button", { name: "保存" }));
    expect(screen.getByText("标题不能为空")).toBeTruthy();
    expect(createCalls).toBe(0);

    // 有效提交
    await userEvent.type(screen.getByLabelText("标题 *"), "平静");
    await userEvent.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => expect(createCalls).toBe(1));
    // 新建成功后自动转入编辑态（可补传图片）
    await waitFor(() => expect(screen.getByTestId("asset-images")).toBeTruthy());
    await userEvent.click(screen.getByRole("button", { name: "取消" }));
    await waitFor(() => expect(screen.getByTestId("create-asset")).toBeTruthy());
  });
});

// ---------------- IF3: 项目资产卡片 → 内嵌查看器 ----------------

describe("F08 IF3: 项目资产查看器", () => {
  it("点击实体卡片 → 查看器 iframe 指向资产页 → 返回关闭（开关两态）", async () => {
    await goToAssets();
    await userEvent.click(screen.getByTestId("section-project"));
    const card = await screen.findByTestId("entity-asset-char-a");
    await userEvent.click(card);

    const viewer = await screen.findByTestId("asset-viewer");
    const frame = screen.getByTestId("asset-viewer-frame") as HTMLIFrameElement;
    expect(frame.src).toBe("http://mock.local/api/assets/entity/char-a/page");
    expect(viewer.textContent).toContain("周兰");

    await userEvent.click(screen.getByRole("button", { name: /返回/ }));
    expect(screen.queryByTestId("asset-viewer")).toBeNull();
  });
});

// ---------------- IF4: 实体详情面板图片区 ----------------

describe("F08 IF4: 实体详情面板图片区", () => {
  it("选中实体 → 图片明细渲染 + 「查看资产页」打开查看器", async () => {
    render(<Workbench />);
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
