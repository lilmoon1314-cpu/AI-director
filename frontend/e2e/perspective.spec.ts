/**
 * F06 L3：三视角切换端到端（Playwright）。webServer 拉起真实后端（临时 SQLite + 迁移）
 * 与前端 dev server；播种后按 作者→观众→角色→作者 顺序切换，断言各视角图计数与不泄露面。
 * 路径: frontend/e2e/perspective.spec.ts（docs/tests/F06_perspective_switch_ui.md E1–E2）。
 */

import { expect, test, type APIRequestContext } from "@playwright/test";

import { shoot } from "./helpers";

const SEED_ENTITIES = [
  { type: "character", name: "周兰", aliases: [], audience_known: true },
  { type: "character", name: "沈墨", aliases: [], audience_known: false },
  { type: "character", name: "陆离", aliases: [], audience_known: true },
  { type: "item", name: "青铜镜", aliases: [], audience_known: false },
  { type: "event", name: "夜探药庐", aliases: [], audience_known: true },
  { type: "location", name: "青云山", aliases: [], audience_known: true },
];

/** 清空库（先删关系再删实体）——幂等，不依赖库初始状态（E07 防线）。 */
async function resetWorld(request: APIRequestContext) {
  const relations = (await (await request.get("/api/relations")).json()) as { id: string }[];
  for (const r of relations) await request.delete(`/api/relations/${r.id}`);
  const entities = (await (await request.get("/api/entities")).json()) as { id: string }[];
  for (const e of entities) await request.delete(`/api/entities/${e.id}`);
}

/** 播种测试世界：6 实体 + 3 关系（audience_known / known_by 与测试文档世界一致）。 */
async function seedWorld(request: APIRequestContext) {
  const ids: Record<string, string> = {};
  for (const e of SEED_ENTITIES) {
    const resp = await request.post("/api/entities", { data: e });
    expect(resp.status()).toBe(201);
    ids[(await resp.json()).name] = (await resp.json()).id;
  }
  const relations = [
    { source: ids["周兰"], target: ids["沈墨"], type: "ALLY", audience_known: true, known_by: [ids["沈墨"]] },
    { source: ids["周兰"], target: ids["青云山"], type: "LIVES_IN", audience_known: true, known_by: [ids["周兰"]] },
    { source: ids["沈墨"], target: ids["夜探药庐"], type: "PARTICIPATES", audience_known: false, known_by: [ids["沈墨"]] },
  ];
  for (const r of relations) {
    const resp = await request.post("/api/relations", { data: r });
    expect(resp.status()).toBe(201);
  }
}

test("E3: 快速连续切换视角——渲染链串行防线（无 G6 内部错误、数据完整、无严重重叠）", async ({ page }) => {
  // 设计依据: 交互反馈轮（E09 防线）——不等布局收敛就连点视角曾打坏 G6 元素控制器（边消失）
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => {
    if (m.type() === "error" && m.text().includes("G6")) errors.push(m.text());
  });

  await resetWorld(page.request);
  await seedWorld(page.request);
  await page.goto("/");
  await expect(page.getByTestId("graph-stats")).toHaveText(/6 节点 · 3 边/);

  // 不等布局收敛就连点（复现用户操作节奏）
  await page.getByTestId("perspective-audience").click();
  await page.waitForTimeout(200);
  await page.getByTestId("perspective-author").click();
  await page.waitForTimeout(200);
  await page.getByTestId("perspective-audience").click();
  await expect(page.getByTestId("graph-stats")).toHaveText(/4 节点 · 1 边/);
  await page.waitForTimeout(2500); // 渲染链排空 + 布局收敛 + 硬分离

  expect(errors).toEqual([]); // 无 'draw' of undefined / instance destroyed 等内部错误
  const edgeCount = await page.evaluate(() => {
    const g = (window as unknown as { __g6graph?: { getEdgeData: () => unknown[] } }).__g6graph;
    if (!g) throw new Error("dev 后门 __g6graph 不存在");
    return g.getEdgeData().length;
  });
  expect(edgeCount).toBe(1); // 观众视图的关系数据完整（边未因打断丢失）
  await shoot(page, "P-04-快速连续切换-数据完整无内部错误");
});

test("E1+E2: 三视角切换全链路（作者→观众→角色→作者）与观众视角不泄露", async ({ page }) => {
  await resetWorld(page.request);
  await seedWorld(page.request);

  await page.goto("/");
  // 作者视角：全量 6 节点 3 边
  await expect(page.getByTestId("graph-stats")).toHaveText(/6 节点 · 3 边/);
  await expect(page.getByTestId("graph-stats")).toHaveText(/（作者视角）/);

  // 切观众：4 节点 1 边；audience_known=false 的「沈墨」不出现在页面任何文本（E2 不泄露断言）
  await page.getByTestId("perspective-audience").click();
  await expect(page.getByTestId("graph-stats")).toHaveText(/4 节点 · 1 边/);
  await expect(page.getByTestId("graph-stats")).toHaveText(/（观众视角）/);
  await expect(page.getByText("沈墨")).toHaveCount(0);
  await page.waitForTimeout(2500); // 布局稳定后截图
  await shoot(page, "P-01-观众视角-4节点1边");

  // 切角色：未选角色零新请求（画布保持原数据），下拉选周兰 → 2 节点 1 边
  await page.getByTestId("perspective-character").click();
  const select = page.getByTestId("character-select");
  await expect(select).toBeVisible();
  await select.selectOption({ label: "周兰" });
  await expect(page.getByTestId("graph-stats")).toHaveText(/2 节点 · 1 边/);
  await expect(page.getByTestId("graph-stats")).toHaveText(/（角色视角·周兰）/);
  await page.waitForTimeout(2500);
  await shoot(page, "P-02-角色视角周兰-2节点1边");

  // 切回作者：全量恢复
  await page.getByTestId("perspective-author").click();
  await expect(page.getByTestId("graph-stats")).toHaveText(/6 节点 · 3 边/);
  await expect(page.getByTestId("graph-stats")).toHaveText(/（作者视角）/);
  await page.waitForTimeout(2500);
  await shoot(page, "P-03-切回作者视角-全量恢复");
});
