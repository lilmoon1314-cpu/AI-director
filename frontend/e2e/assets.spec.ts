/**
 * F08 L3：资产管理端到端（Playwright）。webServer 拉起真实后端（临时双库）与前端。
 * EF1: API 播种实体+图片 → 资产管理页项目卡片可见 → 内嵌查看器打开 HTML → 返回。
 * EF2: UI 新建通用资产（含自定义属性）→ 卡片出现 → 打开查看 → 删除 → 卡片消失。
 * 路径: frontend/e2e/assets.spec.ts（docs/tests/F08_asset_management.md EF1–EF2）。
 */

import { expect, test } from "@playwright/test";

import { shoot } from "./helpers";

const PNG_BYTES = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

async function resetWorld(request: import("@playwright/test").APIRequestContext) {
  const relations = (await (await request.get("/api/relations")).json()) as { id: string }[];
  for (const r of relations) await request.delete(`/api/relations/${r.id}`);
  const entities = (await (await request.get("/api/entities")).json()) as { id: string }[];
  for (const e of entities) await request.delete(`/api/entities/${e.id}`);
  const assets = (await (await request.get("/api/assets/general")).json()) as { id: string }[];
  for (const a of assets) await request.delete(`/api/assets/general/${a.id}`);
}

test("EF1: 项目资产卡片与内嵌查看器", async ({ page, request }) => {
  await resetWorld(request);

  // API 播种：实体 + 图片
  const entityResp = await request.post("/api/entities", {
    data: { type: "character", name: "萧折玉", aliases: [], description: "剑客", audience_known: true },
  });
  expect(entityResp.status()).toBe(201);
  const entityId = ((await entityResp.json()) as { id: string }).id;
  const upload = await request.post("/api/assets/images", {
    multipart: {
      file: {
        name: "portrait.png",
        mimeType: "image/png",
        buffer: PNG_BYTES,
      },
      scope: "entity",
      owner_id: entityId,
    },
  });
  expect(upload.status()).toBe(201);

  await page.goto("/");
  await page.getByTestId("tab-assets").click();
  await page.getByTestId("section-project").click();

  const card = page.getByTestId(`entity-asset-${entityId}`);
  await expect(card).toBeVisible();
  await expect(card).toContainText("萧折玉");
  await shoot(page, "AS-01");

  // 打开内嵌查看器：iframe 加载实体 HTML 页
  await card.click();
  const frame = page.frameLocator("[data-testid=asset-viewer-frame]");
  await expect(frame.locator("h1")).toContainText("萧折玉");
  await expect(frame.locator("img")).toHaveCount(1);
  await shoot(page, "AS-02");

  await page.getByRole("button", { name: /返回/ }).click();
  await expect(page.getByTestId("asset-viewer")).toHaveCount(0);
});

test("EF2: 通用资产新建-查看-删除全链路", async ({ page, request }) => {
  await resetWorld(request);

  await page.goto("/");
  await page.getByTestId("tab-assets").click();

  // 新建：分类 + 标题 + 自定义属性
  await page.getByTestId("create-asset").click();
  await page.getByLabel("标题 *").fill("水墨风格");
  await page.getByLabel(/分类/).fill("风格参考");
  await page.getByRole("button", { name: "+ 添加属性" }).click();
  await page.getByLabel("属性名 1").fill("色调");
  await page.getByLabel("属性值 1").fill("青灰");
  await page.getByRole("button", { name: "保存", exact: true }).click();

  // 保存成功 → 自动转编辑态（图片区出现）
  await expect(page.getByTestId("asset-images")).toBeVisible();

  // 返回列表 → 卡片出现（表单取消时刷新触发）；经 API 取 id 精确定位卡片
  await page.getByRole("button", { name: "取消", exact: true }).click();
  const assets = (await (await request.get("/api/assets/general")).json()) as {
    id: string;
    title: string;
  }[];
  const created = assets.find((a) => a.title === "水墨风格");
  expect(created).toBeTruthy();
  const card = page.getByTestId(`general-asset-${created!.id}`);
  await expect(card).toBeVisible();
  await shoot(page, "AS-03");

  // 打开查看器 → HTML 含标题与属性键
  await card.click();
  const frame = page.frameLocator("[data-testid=asset-viewer-frame]");
  await expect(frame.locator("h1")).toContainText("水墨风格");
  await expect(frame.locator("body")).toContainText("色调");
  await page.getByRole("button", { name: /返回/ }).click();

  // 编辑 → 删除 → 卡片消失（列表刷新为空态文案）
  await page.getByTestId(`edit-asset-${created!.id}`).click();
  await page.getByTestId("delete-asset").click();
  await page.getByTestId("confirm-delete-asset").click();
  await expect(page.getByText(/暂无通用资产/)).toBeVisible();
  await expect(page.getByTestId("general-asset-grid")).toHaveCount(0);
});
