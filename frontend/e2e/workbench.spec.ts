/**
 * F05 L3：全栈端到端（Playwright）。webServer 拉起真实后端（临时 SQLite + 迁移）
 * 与前端 dev server；断言基于真实 API 与 DOM。
 * 路径: frontend/e2e/workbench.spec.ts（docs/tests/F05_frontend_graph_workbench.md E1–E2）。
 */

import { expect, test, type APIRequestContext } from "@playwright/test";

import { shoot } from "./helpers";

// 测试世界种子（与 docs/tests/F05_graph 种子一致）：e2e 库为全新空库，
// 经真实后端 API 播种（走 vite 代理），保证「周兰」等下拉端点存在。
const SEED_ENTITIES = [
  { type: "character", name: "周兰", aliases: [], audience_known: true },
  { type: "character", name: "沈墨", aliases: [], audience_known: false },
  { type: "character", name: "陆离", aliases: [], audience_known: true },
  { type: "item", name: "青铜镜", aliases: [], audience_known: false },
  { type: "event", name: "夜探药庐", aliases: [], audience_known: true },
  { type: "location", name: "青云山", aliases: [], audience_known: true },
];

/** 清空库（先删关系再删实体，规避引用 409）——保证测试幂等，不依赖库初始状态。 */
async function resetWorld(request: APIRequestContext) {
  const relations = (await (await request.get("/api/relations")).json()) as { id: string }[];
  for (const r of relations) await request.delete(`/api/relations/${r.id}`);
  const entities = (await (await request.get("/api/entities")).json()) as { id: string }[];
  for (const e of entities) await request.delete(`/api/entities/${e.id}`);
}

test("E1: UI 建实体 → 建关系 → 图计数经真实后端刷新", async ({ page }) => {
  await resetWorld(page.request);

  // 播种：建 6 实体并记录 id，再按 id 建 3 关系
  const ids: Record<string, string> = {};
  for (const e of SEED_ENTITIES) {
    const resp = await page.request.post("/api/entities", { data: e });
    expect(resp.status()).toBe(201);
    ids[(await resp.json()).name] = (await resp.json()).id;
  }
  const relations = [
    { source: ids["周兰"], target: ids["沈墨"], type: "ALLY", audience_known: true },
    { source: ids["周兰"], target: ids["青云山"], type: "LIVES_IN", audience_known: true },
    { source: ids["沈墨"], target: ids["夜探药庐"], type: "PARTICIPATES", audience_known: true },
  ];
  for (const r of relations) {
    const resp = await page.request.post("/api/relations", { data: r });
    expect(resp.status()).toBe(201);
  }

  await page.goto("/");
  await expect(page.getByTestId("graph-stats")).toHaveText(/6 节点 · 3 边/);
  await shoot(page, "E1-01-首屏加载完成-6节点3边");

  // 建实体（用户写入路径）
  await page.getByLabel("名称").fill("顾长风");
  await page
    .getByTestId("create-entity-form")
    .getByRole("button", { name: "创建", exact: true })
    .click();
  await expect(page.getByTestId("graph-stats")).toHaveText(/7 节点 · 3 边/);
  await shoot(page, "E1-02-新建实体后-7节点");

  // 建关系：端点从图节点下拉选择
  await page.getByLabel("关系起点").selectOption({ label: "顾长风" });
  await page.getByLabel("关系终点").selectOption({ label: "周兰" });
  await page.getByLabel("关系类型（如 ALLY）").fill("MENTORS");
  await page.getByRole("button", { name: "创建关系" }).click();
  await expect(page.getByTestId("graph-stats")).toHaveText(/7 节点 · 4 边/);
  await shoot(page, "E1-03-新建关系后-7节点4边");
});

test("E2: 刷新页面后 E1 的数据仍在（持久化单一事实源）", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("graph-stats")).toHaveText(/7 节点 · 4 边/);
  await shoot(page, "E2-01-刷新前-数据在");
  await page.reload();
  await expect(page.getByTestId("graph-stats")).toHaveText(/7 节点 · 4 边/);
  await shoot(page, "E2-02-刷新持久化后-数据仍在");
});
