/**
 * F07 L3：@ 实体选择器端到端（Playwright）。webServer 拉起真实后端（临时 SQLite）与前端。
 * E1: UI 建物件 → @ 检索选当前持有人/见过的角色 → 提交 → API 验证存 ID → 画布点开详情验证显示名称。
 * E2: 观众视角下 audience_known=false 实体的下拉徽标为「当前视角不可见」。
 * 路径: frontend/e2e/entity-picker.spec.ts（docs/tests/F07_entity_reference_picker.md E1–E2）。
 */

import { expect, test } from "@playwright/test";

import { shoot } from "./helpers";

const SEED_ENTITIES = [
  { type: "character", name: "周兰", aliases: [], audience_known: true },
  { type: "character", name: "沈墨", aliases: [], audience_known: false },
  { type: "item", name: "青铜镜", aliases: [], audience_known: false },
  { type: "event", name: "夜探药庐", aliases: [], audience_known: true },
  { type: "location", name: "青云山", aliases: [], audience_known: true },
];

async function resetWorld(request: import("@playwright/test").APIRequestContext) {
  const relations = (await (await request.get("/api/relations")).json()) as { id: string }[];
  for (const r of relations) await request.delete(`/api/relations/${r.id}`);
  const entities = (await (await request.get("/api/entities")).json()) as { id: string }[];
  for (const e of entities) await request.delete(`/api/entities/${e.id}`);
}

async function seedWorld(request: import("@playwright/test").APIRequestContext) {
  const ids: Record<string, string> = {};
  for (const e of SEED_ENTITIES) {
    const resp = await request.post("/api/entities", { data: e });
    expect(resp.status()).toBe(201);
    ids[(await resp.json()).name] = (await resp.json()).id;
  }
  return ids;
}

test("E1+E2: @ 选择器建实体存 ID、详情显示名称、不可见徽标", async ({ page, request }) => {
  const ids = {} as Record<string, string>;
  await resetWorld(request);
  Object.assign(ids, await seedWorld(request));

  await page.goto("/");
  await expect(page.getByTestId("graph-stats")).toHaveText(/5 节点 · 0 边/);

  // 展开新建 → 实体，类型=物件
  await page.getByRole("button", { name: "新建", exact: true }).click();
  await page.getByRole("button", { name: "实体", exact: true }).click();
  await page.getByLabel("名称").fill("摄魂幡");
  await page.getByLabel("类型").selectOption("item");

  // 当前持有人：@ 检索选周兰（作者视角全部可见 → 徽标可见）
  const holder = page.getByTestId("create-prop-holder");
  await holder.click();
  await holder.fill("@周");
  const holderOptions = page.getByTestId("create-prop-holder-options");
  await expect(holderOptions).toBeVisible();
  await expect(holderOptions).toContainText("当前视角可见");
  await holderOptions.getByRole("button", { name: /周兰/ }).click();
  await expect(page.getByLabel("当前持有人（关联 character）")).toHaveValue("周兰");

  // 见过的角色：多值选择沈墨 + 周兰
  const seenBy = page.getByTestId("create-prop-seen_by");
  await seenBy.click();
  await seenBy.fill("@沈");
  await page.getByTestId("create-prop-seen_by-options").getByRole("button", { name: /沈墨/ }).click();
  await seenBy.fill("@周");
  await page.getByTestId("create-prop-seen_by-options").getByRole("button", { name: /周兰/ }).click();
  await expect(page.getByTestId("create-entity-form")).toContainText("沈墨");
  await expect(page.getByTestId("create-entity-form")).toContainText("周兰");

  await page
    .getByTestId("create-entity-form")
    .getByRole("button", { name: "创建", exact: true })
    .click();
  await expect(page.getByTestId("graph-stats")).toHaveText(/6 节点 · 0 边/);

  // API 验证：properties 存的是实体 ID（表单显示名称，存储层 ID 契约）。
  // 注意 list 端点返回摘要（无 properties），需再取详情
  const briefs = (await (await request.get("/api/entities?type=item")).json()) as {
    id: string;
    name: string;
  }[];
  const bannerId = briefs.find((b) => b.name === "摄魂幡")?.id;
  expect(bannerId).toBeTruthy();
  const full = (await (await request.get(`/api/entities/${bannerId}`)).json()) as {
    properties: { holder?: string; seen_by?: string[] };
  };
  expect(full.properties.holder).toBe(ids["周兰"]);
  expect(full.properties.seen_by).toEqual(expect.arrayContaining([ids["沈墨"], ids["周兰"]]));

  // E2: 切观众视角 → 沈墨（audience_known=false）不可见徽标
  await page.getByTestId("perspective-audience").click();
  await expect(page.getByTestId("graph-stats")).toHaveText(/3 节点 · 0 边/);
  await page.getByLabel("类型").selectOption("item"); // 创建成功后表单已重置，重选类型
  await page.getByTestId("create-prop-holder").click();
  await page.getByTestId("create-prop-holder").fill("@沈");
  const audOptions = page.getByTestId("create-prop-holder-options");
  await expect(audOptions).toBeVisible();
  await expect(audOptions).toContainText("沈墨");
  await expect(audOptions).toContainText("当前视角不可见");
  await shoot(page, "@-01-观众视角选择器-不可见徽标");

  // 回作者视角，画布点开摄魂幡详情 → 持有人/见过的角色显示名称（截图核验）
  await page.getByTestId("perspective-author").click();
  await expect(page.getByTestId("graph-stats")).toHaveText(/6 节点 · 0 边/);
  await page.waitForTimeout(11000); // 布局收敛 + 硬分离（E09 防线时序）
  const point = await page.evaluate(() => {
    const graph = (window as unknown as {
      __g6graph?: {
        getNodeData: () => { id: string; data: { name: string } }[];
        getElementPosition: (id: string) => number[];
        getViewportByCanvas: (p: number[]) => number[];
      };
    }).__g6graph;
    if (!graph) throw new Error("dev 后门 __g6graph 不存在");
    const node = graph.getNodeData().find((n) => n.data.name === "摄魂幡");
    if (!node) throw new Error("摄魂幡 节点不存在");
    const [cx, cy] = graph.getElementPosition(node.id);
    const [vx, vy] = graph.getViewportByCanvas([cx, cy, 0]);
    return { x: Math.round(vx), y: Math.round(vy) };
  });
  const box = await page.getByTestId("graph-canvas").boundingBox();
  if (!box) throw new Error("画布容器不可见");
  await page.mouse.click(box.x + point.x, box.y + point.y);
  const panel = page.getByTestId("entity-panel");
  await expect(panel).toContainText("摄魂幡");
  await expect(panel.getByTestId("prop-holder")).toContainText("周兰"); // 名称而非 char-xxx
  await expect(panel.getByTestId("prop-seen_by")).toContainText("沈墨、周兰");
  await page.waitForTimeout(500);
  await shoot(page, "@-02-详情面板-关联字段显示名称");
});
