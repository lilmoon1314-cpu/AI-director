/**
 * F11 L3：多项目工作台端到端（Playwright）——DESIGN.md §6 剧本 A/B/E 全链路。
 * webServer 拉起真实后端（临时 SQLite + 迁移 + lifespan 播种默认项目）与前端 dev server。
 * 路径: frontend/e2e/projects.spec.ts（docs/tests/F11_multi_project_foundation.md FE1）。
 */

import { expect, test } from "@playwright/test";

import { openWorkbench, resetWorld, shoot } from "./helpers";

test("FE1: 新建项目 → 建实体 → 顶栏切换隔离 → 首屏删除项目（输入名确认）", async ({ page }) => {
  // 前置：清空全库（跨项目清理，保证计数断言稳定）
  await resetWorld(page.request);

  // —— 剧本 A：首屏新建项目（DESIGN §6 A）——
  await page.goto("/");
  await expect(page.getByTestId("project-picker")).toBeVisible();
  await shoot(page, "PR-01-项目首屏-含默认项目");

  await page.getByTestId("project-create").first().click();
  await page.getByLabel("项目名").fill("雾都旧事");
  await page.getByLabel(/一句话描述/).fill("民国悬疑世界");
  await page.getByTestId("project-form-submit").click();

  // 创建并进入：URL 即状态（/projects/:id/graph）
  await expect(page).toHaveURL(/\/projects\/project-[^/]+\/graph$/);
  await expect(page.getByTestId("graph-stats")).toHaveText(/0 节点 · 0 边/);
  await shoot(page, "PR-02-进入新项目-空图谱");

  // —— 建实体（隐式作用域：表单无项目选择，归属当前项目）——
  await page.getByRole("button", { name: "新建", exact: true }).click();
  await page.getByRole("button", { name: "实体", exact: true }).click();
  await page.getByLabel("名称").fill("沈青梧");
  await page.getByTestId("create-entity-form").getByRole("button", { name: "创建", exact: true }).click();
  await expect(page.getByTestId("graph-stats")).toHaveText(/1 节点/);

  // —— 剧本 B：顶栏切换默认项目 → 图谱隔离 ——
  await page.getByTestId("project-switcher-button").click();
  await page.getByTestId("switch-to-project-default").click();
  await expect(page).toHaveURL(/\/projects\/project-default\/graph$/);
  await expect(page.getByTestId("graph-stats")).toHaveText(/0 节点 · 0 边/); // 雾都旧事实体不泄露
  await shoot(page, "PR-03-切换默认项目-隔离为空");

  // 切回雾都旧事：数据仍在（项目数据随项目置换）
  await page.getByTestId("project-switcher-button").click();
  const fogItem = page.locator('[data-testid^="switch-to-project-"]', { hasText: "雾都旧事" });
  await fogItem.click();
  await expect(page.getByTestId("graph-stats")).toHaveText(/1 节点/);

  // —— 剧本 E：返回首屏删除项目（危险操作：输入项目名确认）——
  await page.getByTestId("logo-home").click();
  await expect(page.getByTestId("project-picker")).toBeVisible();

  const fogCard = page.locator('[data-testid^="project-card-"]', { hasText: "雾都旧事" });
  await expect(fogCard).toBeVisible();
  await fogCard.getByRole("button", { name: /管理菜单/ }).click();
  await fogCard.getByRole("button", { name: "删除", exact: true }).click();

  // 未输入正确名称前确认禁用（边界值—名称不匹配）
  const confirmButton = page.getByTestId("project-delete-confirm");
  await expect(confirmButton).toBeDisabled();
  await page.getByLabel(/输入项目名/).fill("错误名称");
  await expect(confirmButton).toBeDisabled();
  await page.getByLabel(/输入项目名/).fill("雾都旧事");
  await expect(confirmButton).toBeEnabled();
  await confirmButton.click();

  await expect(page.locator('[data-testid^="project-card-"]', { hasText: "雾都旧事" })).toHaveCount(0);
  await expect(page.getByTestId("project-card-project-default")).toBeVisible(); // 默认项目保留
  await shoot(page, "PR-04-删除后首屏-仅默认项目");

  // 级联生效：默认项目图谱仍为空、雾都旧事实体已随之消失（经 API 复核）
  const entities = (await (await page.request.get("/api/entities")).json()) as { id: string }[];
  expect(entities).toHaveLength(0);
});

test("FE1b: 默认项目工作台既有能力回归（首屏进入路径）", async ({ page }) => {
  await resetWorld(page.request);
  await openWorkbench(page); // / → 首屏 → 默认项目卡片 → 图谱页
  await expect(page.getByTestId("sidebar")).toBeVisible();
  await expect(page.getByTestId("main-nav")).toBeVisible();
});
