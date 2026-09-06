/**
 * F12 L3：资产管理端到端（Playwright）。webServer 拉起真实后端（临时双库）与前端。
 * FE1: 两级钻取全链路——API 播种实体+图片 → 类型库墙聚合计数 → 人物库详情 → 实体卡
 *      → 查看器 HTML → 返回 → asset-type-back 回墙 → 浏览器后退再回详情（路由化收益）。
 * FE2: 通用资产 modal 全链路——新建（modal 不替换卡片墙）→ 转编辑态 → 卡片出现 → 查看
 *      → 编辑 modal 删除 → 空态引导卡出现。
 * FE3: 分区搜索——类型详情搜实体名命中 / 搜不存在词显示无命中空态。
 * 路径: frontend/e2e/assets.spec.ts（docs/tests/F12_workbench_navigation_assets.md FE1–FE3）。
 */

import { expect, test } from "@playwright/test";

import { shoot, openWorkbench } from "./helpers";

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

test("FE1: 类型库墙 → 人物库详情 → 实体 HTML 查看器 → 返回/后退（两级钻取全链路）", async ({
  page,
  request,
}) => {
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

  await openWorkbench(page);
  await page.getByTestId("tab-assets").click();
  await page.getByTestId("section-project").click();

  // 第一级：类型库墙——人物库卡带聚合计数
  const typeCard = page.getByTestId("asset-type-card-character");
  await expect(typeCard).toBeVisible();
  await expect(typeCard).toContainText("人物库");
  await expect(typeCard).toContainText("1 实体");
  await shoot(page, "AS-01");

  // 第二级：人物库详情——面包屑 + 实体卡
  await typeCard.click();
  await expect(page.getByTestId("asset-type-back")).toBeVisible();
  const card = page.getByTestId(`entity-asset-${entityId}`);
  await expect(card).toBeVisible();
  await expect(card).toContainText("萧折玉");

  // 内嵌查看器：iframe 加载实体 HTML 页
  await card.click();
  const frame = page.frameLocator("[data-testid=asset-viewer-frame]");
  await expect(frame.locator("h1")).toContainText("萧折玉");
  await expect(frame.locator("img")).toHaveCount(1);
  await shoot(page, "AS-02");

  await page.getByRole("button", { name: "返回资产列表" }).click();
  await expect(page.getByTestId("asset-viewer")).toHaveCount(0);

  // asset-type-back 回类型库墙；浏览器后退再回详情（URL 即状态的收益）
  await page.getByTestId("asset-type-back").click();
  await expect(page.getByTestId("asset-type-wall")).toBeVisible();
  await page.goBack();
  await expect(page.getByTestId(`entity-asset-${entityId}`)).toBeVisible();
});

test("FE2: 通用资产 modal 新建-查看-删除全链路 + 空态引导", async ({ page, request }) => {
  await resetWorld(request);

  await openWorkbench(page);
  await page.getByTestId("tab-assets").click();

  // 空库：引导卡 + 主按钮打开 modal（modal 不替换列表区——OQ-3）
  await expect(page.getByTestId("asset-general-empty")).toBeVisible();
  await page.getByTestId("create-asset").click();
  await expect(page.getByTestId("general-asset-modal")).toBeVisible();

  // 新建：分类 + 标题 + 自定义属性
  await page.getByLabel("标题 *").fill("水墨风格");
  await page.getByLabel(/分类/).fill("风格参考");
  await page.getByRole("button", { name: "+ 添加属性" }).click();
  await page.getByLabel("属性名 1").fill("色调");
  await page.getByLabel("属性值 1").fill("青灰");
  await page.getByRole("button", { name: "保存", exact: true }).click();

  // 保存成功 → 自动转编辑态（图片区出现，modal 保持打开）
  await expect(page.getByTestId("asset-images")).toBeVisible();

  // 返回列表 → 卡片出现；经 API 取 id 精确定位卡片
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
  await page.getByRole("button", { name: "返回资产列表" }).click();

  // 编辑 modal → 删除 → 空态引导卡再现
  await page.getByTestId(`edit-asset-${created!.id}`).click();
  await page.getByTestId("delete-asset").click();
  await page.getByTestId("confirm-delete-asset").click();
  await expect(page.getByTestId("asset-general-empty")).toBeVisible();
});

test("FE3: 类型库详情分区搜索——命中实体名 / 无命中空态", async ({ page, request }) => {
  await resetWorld(request);

  for (const [type, name] of [
    ["character", "萧折玉"],
    ["location", "沉星湖"],
  ] as const) {
    const resp = await request.post("/api/entities", {
      data: { type, name, aliases: [], description: "", audience_known: true },
    });
    expect(resp.status()).toBe(201);
  }

  await openWorkbench(page);
  await page.getByTestId("tab-assets").click();
  await page.getByTestId("section-project").click();
  await page.getByTestId("asset-type-card-character").click();

  // 命中：人物库详情搜实体名
  await page.getByTestId("asset-search").fill("萧折玉");
  await expect(page.getByTestId("asset-search-empty")).toHaveCount(0);
  // 无命中：独立空态提示（非空库引导卡）
  await page.getByTestId("asset-search").fill("不存在的名字");
  await expect(page.getByTestId("asset-search-empty")).toBeVisible();
});
