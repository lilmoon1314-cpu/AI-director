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

/** 播种测试世界：经真实后端 API 建 6 实体并按 id 建 3 关系。 */
async function seedWorld(request: APIRequestContext) {
  const ids: Record<string, string> = {};
  for (const e of SEED_ENTITIES) {
    const resp = await request.post("/api/entities", { data: e });
    expect(resp.status()).toBe(201);
    ids[(await resp.json()).name] = (await resp.json()).id;
  }
  const relations = [
    { source: ids["周兰"], target: ids["沈墨"], type: "ALLY", audience_known: true },
    { source: ids["周兰"], target: ids["青云山"], type: "LIVES_IN", audience_known: true },
    { source: ids["沈墨"], target: ids["夜探药庐"], type: "PARTICIPATES", audience_known: true },
  ];
  for (const r of relations) {
    const resp = await request.post("/api/relations", { data: r });
    expect(resp.status()).toBe(201);
  }
}

test("E1: UI 建实体 → 建关系 → 图计数经真实后端刷新", async ({ page }) => {
  await resetWorld(page.request);
  await seedWorld(page.request);

  await page.goto("/");
  await expect(page.getByTestId("graph-stats")).toHaveText(/6 节点 · 3 边/);
  await shoot(page, "E1-01-首屏加载完成-6节点3边");

  // 建实体（用户写入路径）：所有区块默认折叠（交互三轮），逐层展开「新建 → 实体」
  await page.getByRole("button", { name: "新建", exact: true }).click();
  await page.getByRole("button", { name: "实体", exact: true }).click();
  await page.getByLabel("名称").fill("顾长风");
  await page
    .getByTestId("create-entity-form")
    .getByRole("button", { name: "创建", exact: true })
    .click();
  await expect(page.getByTestId("graph-stats")).toHaveText(/7 节点 · 3 边/);
  await shoot(page, "E1-02-新建实体后-7节点");

  // 建关系：展开「关系」手风琴后从图节点下拉选择端点（提示文字 aria-hidden，按钮名即「关系」）
  await page.getByRole("button", { name: "关系", exact: true }).click();
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

test("E3: 深色模式跟随系统（emulate prefers-color-scheme: dark）", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await resetWorld(page.request);
  await seedWorld(page.request);
  await page.goto("/");
  await expect(page.getByTestId("graph-stats")).toHaveText(/6 节点 · 3 边/);
  await shoot(page, "E3-01-深色模式首屏");
});

test("E4: 类型筛选——取消勾选人物 → 仅非人物可见（3 节点 0 边）→ 恢复勾选复原", async ({ page }) => {
  // 设计依据: docs/tests/F05 交互三轮 E4——真实画布显隐 + 状态栏可见计数联动（截图人工核验动画淡入淡出）
  await resetWorld(page.request);
  await seedWorld(page.request);

  await page.goto("/");
  await expect(page.getByTestId("graph-stats")).toHaveText(/6 节点 · 3 边/);
  await page.getByRole("button", { name: "筛选", exact: true }).click();
  await page.getByLabel("人物 (3)").uncheck();
  await expect(page.getByTestId("graph-stats")).toHaveText(/3 节点 · 0 边/);
  await expect(page.getByTestId("graph-stats")).toHaveText(/（已筛选）/);
  await page.waitForTimeout(800); // 淡出动画结束后截图
  await shoot(page, "E4-01-取消人物-仅非人物3节点0边");

  await page.getByLabel("人物 (3)").check();
  await expect(page.getByTestId("graph-stats")).toHaveText(/6 节点 · 3 边/);
  await expect(page.getByTestId("graph-stats")).not.toHaveText(/已筛选/);
  await page.waitForTimeout(800);
  await shoot(page, "E4-02-恢复人物-6节点3边");
});
