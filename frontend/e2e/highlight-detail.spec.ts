/**
 * F05 单独验收：悬停高亮/放大 + 点击持续高亮 + 右侧结构化详情面板。
 * 播种小世界（4 实体 2 关系）便于定位；节点坐标经 dev 后门 window.__g6graph
 * （getElementPosition → getViewportByCanvas 换算为视口坐标）驱动真实 hover/click。
 * 截图存档 frontend/e2e-screenshots/HL-*.png。
 */

import { expect, test } from "@playwright/test";

import { resetWorld, shoot } from "./helpers";

interface ViewportPoint {
  x: number;
  y: number;
}

async function nodeViewportPoint(page: import("@playwright/test").Page, index: number): Promise<ViewportPoint> {
  // getViewportByCanvas 返回相对画布容器的坐标；page.mouse 用页面坐标——
  // 需叠加画布容器的 boundingBox 偏移（左侧有操作栏）
  return page.evaluate((i) => {
    const graph = (window as unknown as { __g6graph?: {
      getNodeData: () => { id: string }[];
      getElementPosition: (id: string) => number[];
      getViewportByCanvas: (p: number[]) => number[];
    } }).__g6graph;
    if (!graph) throw new Error("dev 后门 __g6graph 不存在（须以 dev server 运行）");
    const nodes = graph.getNodeData();
    const [cx, cy] = graph.getElementPosition(nodes[i].id);
    const [vx, vy] = graph.getViewportByCanvas([cx, cy, 0]);
    return { x: Math.round(vx), y: Math.round(vy) };
  }, index).then(async (p) => {
    const box = await page.getByTestId("graph-canvas").boundingBox();
    if (!box) throw new Error("画布容器不可见");
    return { x: Math.round(box.x + p.x), y: Math.round(box.y + p.y) };
  });
}

test("悬停高亮放大 + 点击持续高亮与结构化详情", async ({ page, request }) => {
  await resetWorld(request);
  const afterReset = (await (await request.get("/api/entities")).json()) as unknown[];
  const relsAfter = (await (await request.get("/api/relations")).json()) as unknown[];
  console.log(`[reset 后] 实体 ${afterReset.length} 关系 ${relsAfter.length}`);
  // 小世界：人物 + 地点 + 事件（人物带结构化 properties）+ 2 关系
  const respChar = await request.post("/api/entities", {
    data: {
      type: "character",
      name: "周兰",
      aliases: ["兰姐"],
      audience_known: true,
      description: "本书主角",
      properties: { occupation: "药师", gender: "女", origin: "青云山下" },
    },
  });
  expect(respChar.status()).toBe(201);
  const charId = (await respChar.json()).id;
  const respLoc = await request.post("/api/entities", {
    data: { type: "location", name: "青云山", aliases: [], audience_known: true },
  });
  const locId = (await respLoc.json()).id;
  const respEvent = await request.post("/api/entities", {
    data: {
      type: "event",
      name: "夜探药庐",
      aliases: [],
      audience_known: true,
      properties: { known_by: [charId], time: "第一夜" },
    },
  });
  const eventId = (await respEvent.json()).id;
  expect((await request.post("/api/relations", {
    data: { source: charId, target: locId, type: "LIVES_IN", audience_known: true },
  })).status()).toBe(201);
  expect((await request.post("/api/relations", {
    data: { source: charId, target: eventId, type: "PARTICIPATES", audience_known: true },
  })).status()).toBe(201);

  page.on("console", (msg) => {
    if (msg.text().includes("separateOverlaps")) console.log("[页面]", msg.text());
  });
  await page.goto("/");
  await expect(page.getByTestId("graph-stats")).toHaveText(/3 节点 · 2 边/);
  await page.waitForTimeout(10500); // 力导收敛 + 硬分离(兜底 9s+0.6s 去抖)完成
  const nodeCoords = await page.evaluate(() => {
    const graph = (window as unknown as { __g6graph?: {
      getNodeData: () => { id: string; data: { name: string } }[];
      getElementPosition: (id: string) => number[];
    } }).__g6graph;
    return graph?.getNodeData().map((n) => {
      const p = graph.getElementPosition(n.id);
      return { name: n.data.name, x: Math.round(p[0]), y: Math.round(p[1]) };
    });
  });
  console.log("[节点画布坐标]", JSON.stringify(nodeCoords));
  // 实验验证: translateElementTo 移动后 1s,位置是否被布局引擎拉回
  await page.evaluate(() => {
    const graph = (window as unknown as { __g6graph?: {
      getNodeData: () => { id: string; data: { name: string } }[];
      translateElementTo: (p: Record<string, Float32Array>, animation?: boolean) => void;
    } }).__g6graph;
    const target = graph?.getNodeData().find((n) => n.data.name === "夜探药庐");
    if (target) graph?.translateElementTo({ [target.id]: new Float32Array([700, 100, 0]) }, false);
  });
  await page.waitForTimeout(1000);
  const afterMove = await page.evaluate(() => {
    const graph = (window as unknown as { __g6graph?: {
      getNodeData: () => { id: string; data: { name: string } }[];
      getElementPosition: (id: string) => number[];
    } }).__g6graph;
    return graph?.getNodeData()
      .filter((n) => n.data.name === "夜探药庐")
      .map((n) => {
        const p = graph.getElementPosition(n.id);
        return { name: n.data.name, x: Math.round(p[0]), y: Math.round(p[1]) };
      });
  });
  console.log("[移动 1s 后]", JSON.stringify(afterMove));

  // —— 悬停人物节点：一跳邻域高亮、非邻接淡出、节点放大、边标签显示 ——
  const charPoint = await nodeViewportPoint(page, 0);
  await page.mouse.move(charPoint.x, charPoint.y);
  await page.waitForTimeout(800);
  await shoot(page, "HL-01-悬停人物-邻域高亮-微放大");

  // —— 点击：持续高亮 + 右侧结构化详情面板（按蓝图字段展示） ——
  await page.mouse.click(charPoint.x, charPoint.y);
  await expect(page.getByTestId("entity-panel")).toBeVisible();
  await expect(page.getByTestId("entity-panel")).toContainText("周兰");
  // 结构化字段：character 全部规定字段按蓝图展示（空值显示 —）
  const props = page.getByTestId("entity-properties");
  await expect(props).toContainText("身份/职业");
  await expect(props).toContainText("药师");
  await expect(props).toContainText("年龄");
  await expect(props).toContainText("—"); // 未填字段
  await page.waitForTimeout(500);
  await shoot(page, "HL-02-点击持续高亮-结构化详情面板");

  // —— 再次点击取消持续高亮（回到常态） ——
  await page.mouse.click(charPoint.x, charPoint.y);
  await page.waitForTimeout(500);
  await shoot(page, "HL-03-再次点击取消高亮");
});
