/**
 * F05 单独验收：悬停高亮/放大 + 点击持续高亮 + 右侧结构化详情面板。
 * 播种小世界（4 实体 2 关系 + 1 孤立节点）便于定位；节点坐标经 dev 后门 window.__g6graph
 * （getElementPosition → getViewportByCanvas 换算为视口坐标）驱动真实 hover/click。
 * HL3 回归（E08 防线）：点击后鼠标移开，选中邻域保持 selected、非邻接保持 inactive
 * （经 getElementState 断言图状态本身，不再只断言面板副作用）。
 * 截图存档 frontend/e2e-screenshots/HL-*.png。
 */

import { expect, test } from "@playwright/test";

import { resetWorld, shoot } from "./helpers";

interface ViewportPoint {
  x: number;
  y: number;
}

async function nodeViewportPoint(page: import("@playwright/test").Page, nodeName: string): Promise<ViewportPoint> {
  // getViewportByCanvas 返回相对画布容器的坐标；page.mouse 用页面坐标——
  // 需叠加画布容器的 boundingBox 偏移（左侧有操作栏）。
  // 按名称定位（ getNodeData 顺序非插入序，按索引取曾误落孤立节点）。
  return page.evaluate((target) => {
    const graph = (window as unknown as {
      __g6graph?: {
        getNodeData: () => { id: string; data: { name: string } }[];
        getElementPosition: (id: string) => number[];
        getViewportByCanvas: (p: number[]) => number[];
      };
    }).__g6graph;
    if (!graph) throw new Error("dev 后门 __g6graph 不存在（须以 dev server 运行）");
    const node = graph.getNodeData().find((n) => n.data.name === target);
    if (!node) throw new Error(`节点 ${target} 不存在`);
    const [cx, cy] = graph.getElementPosition(node.id);
    const [vx, vy] = graph.getViewportByCanvas([cx, cy, 0]);
    return { x: Math.round(vx), y: Math.round(vy) };
  }, nodeName).then(async (p) => {
    const box = await page.getByTestId("graph-canvas").boundingBox();
    if (!box) throw new Error("画布容器不可见");
    return { x: Math.round(box.x + p.x), y: Math.round(box.y + p.y) };
  });
}

/** dev 后门读取全部节点当前状态（按实体名索引）。 */
function readStates(page: import("@playwright/test").Page): Promise<Record<string, string[]>> {
  return page.evaluate(() => {
    const graph = (window as unknown as {
      __g6graph?: {
        getNodeData: () => { id: string; data: { name: string } }[];
        getElementState: (id: string) => string[];
      };
    }).__g6graph;
    if (!graph) throw new Error("dev 后门 __g6graph 不存在");
    return Object.fromEntries(graph.getNodeData().map((n) => [n.data.name, graph.getElementState(n.id)]));
  });
}

test("悬停高亮放大 + 点击持续高亮与结构化详情", async ({ page, request }) => {
  await resetWorld(request);
  const afterReset = (await (await request.get("/api/entities")).json()) as unknown[];
  const relsAfter = (await (await request.get("/api/relations")).json()) as unknown[];
  console.log(`[reset 后] 实体 ${afterReset.length} 关系 ${relsAfter.length}`);
  // 小世界：人物 + 地点 + 事件（相连）+ 孤立地点（北漠，验证非邻接淡出与复位）
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
  const respIsolated = await request.post("/api/entities", {
    data: { type: "location", name: "北漠", aliases: [], audience_known: true },
  });
  expect(respIsolated.status()).toBe(201);
  expect((await request.post("/api/relations", {
    data: { source: charId, target: locId, type: "LIVES_IN", audience_known: true },
  })).status()).toBe(201);
  expect((await request.post("/api/relations", {
    data: { source: charId, target: eventId, type: "PARTICIPATES", audience_known: true },
  })).status()).toBe(201);

  await page.goto("/");
  await expect(page.getByTestId("graph-stats")).toHaveText(/4 节点 · 2 边/);
  await page.waitForTimeout(10500); // 力导收敛 + 硬分离(兜底 9s+0.6s 去抖)完成

  // —— 悬停人物节点：一跳邻域高亮、非邻接淡出（inactiveState）、节点微放大 ——
  const charPoint = await nodeViewportPoint(page, "周兰");
  await page.mouse.move(charPoint.x, charPoint.y, { steps: 10 });
  await page.waitForTimeout(800);
  const hoverStates = await readStates(page);
  expect(hoverStates["周兰"]).toEqual(["active"]);
  expect(hoverStates["北漠"]).toEqual(["inactive"]); // 非邻接淡出（此前缺失，交互三轮补齐）
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
  // HL3 回归核心：鼠标移开画布角落后，持续高亮必须保持（E08：曾因闭包空数据全失效）
  const canvasBox = await page.getByTestId("graph-canvas").boundingBox();
  if (!canvasBox) throw new Error("画布容器不可见");
  await page.mouse.move(canvasBox.x + 40, canvasBox.y + canvasBox.height - 40);
  await page.waitForTimeout(600); // 悬停退出事件 + 状态过渡动画完成
  const selectedStates = await readStates(page);
  expect(selectedStates["周兰"]).toEqual(["selected"]);
  expect(selectedStates["青云山"]).toEqual(["selected"]);
  expect(selectedStates["夜探药庐"]).toEqual(["selected"]);
  expect(selectedStates["北漠"]).toEqual(["inactive"]);
  await shoot(page, "HL-02-点击持续高亮-鼠标移开仍保持-结构化详情面板");

  // —— 再次点击取消持续高亮（鼠标移开后全部复位） ——
  // 先关闭详情面板：面板是 HTML 覆盖层，节点恰在其下方时点击会落在面板上而非画布
  // （T-20260828-03：布局随机性致首跑通过/重跑失败的间歇失败根源）
  await page.getByRole("button", { name: "关闭面板" }).click();
  await page.mouse.move(charPoint.x, charPoint.y, { steps: 5 });
  await page.mouse.click(charPoint.x, charPoint.y);
  await page.mouse.move(canvasBox.x + 40, canvasBox.y + canvasBox.height - 40);
  await page.waitForTimeout(600);
  const clearedStates = await readStates(page);
  expect(clearedStates["周兰"]).toEqual([]);
  expect(clearedStates["北漠"]).toEqual([]);
  await shoot(page, "HL-03-再次点击取消高亮-复位");
});
