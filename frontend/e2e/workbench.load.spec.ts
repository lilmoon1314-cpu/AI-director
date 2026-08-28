/**
 * 负载验收（@load）：~194 实体 + ~208 关系下的前端流畅性与内存监控。
 * 构成：20 人物 / 8 功法 / 6 门派 / 20 物体 / 20 地点 / 80 事件 / 40 概念。
 * 监控：播种耗时、/api/graph 响应耗时、数据就绪耗时、主线程往返、
 *       JS 堆内存四点采样（加载后 → 稳定后 → 交互后 → 静置后）。
 * 运行: pnpm test:e2e:load（独立配置 + 专用临时库，主验收不包含本文件）。
 */

import { expect, test, type APIRequestContext } from "@playwright/test";

import { resetWorld, shoot } from "./helpers";

const CHAR_NAMES = [
  "林长风", "苏晚晴", "叶青崖", "萧子衿", "陆云深", "沈若尘", "顾惊鸿", "白照影",
  "秦寒山", "江望舒", "林听雨", "苏渡寒", "叶疏影", "萧折玉", "陆扶摇", "沈栖梧",
  "顾星阑", "白暮雪", "秦流萤", "江知许",
];
const SKILLS = ["玄天诀", "碧波掌法", "御风术", "千机变", "焚天诀", "寒冰真经", "幻影身法", "雷音剑法"];
const FACTIONS = ["青云门", "天机阁", "万象宗", "流云寨", "玄冰谷", "赤焰盟"];
const ITEMS = [
  "青铜镜", "玉骨笛", "赤霄剑", "乾坤袋", "夜明珠", "残卷地图", "镇魂钟", "碧水珠",
  "乌金甲", "摄魂幡", "紫金葫芦", "龙纹玉佩", "断岳斧", "流云梭", "引雷符", "霜华扇",
  "噬魂珠", "玄龟盾", "织梦梭", "焚香炉",
];
const LOCATIONS = [
  "青云山", "落雁谷", "寒潭洞", "沉星湖", "赤焰谷", "天绝崖", "白帝城", "黑风林",
  "碧水镇", "乱星海", "幽冥涧", "万兽原", "栖霞岭", "断魂桥", "望月台", "藏剑山庄",
  "枯骨滩", "百花洲", "镇妖塔", "归墟",
];
const CONCEPTS = [
  "因果", "宿命", "执念", "心魔", "天命", "情劫", "道义", "背叛", "救赎", "轮回",
  "谎言", "忠诚", "欲望", "恐惧", "贪婪", "牺牲", "复仇", "宽恕", "传承", "叛逆",
  "秩序", "混沌", "离别", "重逢", "误会", "真相", "秘密", "代价", "选择", "成长",
  "堕落", "觉醒", "羁绊", "孤勇", "幻灭", "希望", "誓言", "遗忘", "执迷", "释然",
];

function pick<T>(arr: T[], i: number): T {
  return arr[i % arr.length];
}

function randInt(max: number): number {
  return Math.floor(Math.random() * max);
}

interface EntityPayload {
  type: string;
  name: string;
  aliases: string[];
  audience_known: boolean;
  description?: string;
  properties?: Record<string, unknown>;
}

/** 生成非人物实体（174 个）的 API 载荷与类型索引；人物由 seed() 先建（known_by/seen_by 需引用其 id）。 */
function buildEntities(charIds: string[]): { payloads: EntityPayload[]; counts: Record<string, number> } {
  const payloads: EntityPayload[] = [];
  const randChars = (n: number) =>
    Array.from({ length: n }, () => charIds[randInt(charIds.length)]);

  SKILLS.forEach((name) =>
    payloads.push({ type: "skill", name, aliases: [], audience_known: true, description: "上乘功法传承" }),
  );
  FACTIONS.forEach((name) =>
    payloads.push({ type: "faction", name, aliases: [], audience_known: true }),
  );
  ITEMS.forEach((name, i) =>
    payloads.push({
      type: "item",
      name,
      aliases: [],
      audience_known: false,
      properties: { seen_by: randChars(1 + (i % 2)) },
    }),
  );
  LOCATIONS.forEach((name) =>
    payloads.push({ type: "location", name, aliases: [], audience_known: true }),
  );
  for (let i = 1; i <= 80; i++) {
    payloads.push({
      type: "event",
      name: `${pick(["夜袭", "密会", "失踪", "寻宝", "谈判", "突袭", "布局", "反杀"], i)}·第${i}夜`,
      aliases: [],
      audience_known: i % 3 !== 0,
      properties: { known_by: randChars(1 + (i % 3)), date: `第${i}夜` },
    });
  }
  CONCEPTS.forEach((name) =>
    payloads.push({ type: "concept", name, aliases: [], audience_known: true }),
  );

  const counts: Record<string, number> = {};
  for (const p of payloads) counts[p.type] = (counts[p.type] ?? 0) + 1;
  return { payloads, counts };
}

async function seed(request: APIRequestContext): Promise<number> {
  // 先建人物，事件/物体的 known_by/seen_by 需要引用其 id
  const charIds: string[] = [];
  for (const name of CHAR_NAMES) {
    const resp = await request.post("/api/entities", {
      data: { type: "character", name, aliases: [], audience_known: true },
    });
    expect(resp.status(), `播种人物 ${name}`).toBe(201);
    charIds.push((await resp.json()).id);
  }

  const { payloads, counts } = buildEntities(charIds);
  const idsByType: Record<string, string[]> = { character: charIds };
  const t0 = Date.now();
  for (const p of payloads) {
    const resp = await request.post("/api/entities", { data: p });
    expect(resp.status(), `播种实体 ${p.name}`).toBe(201);
    (idsByType[p.type] ??= []).push((await resp.json()).id);
  }
  const entitiesCount = payloads.length;
  const tEntities = Date.now() - t0;

  // 关系：人-人 / 人-门派 / 人-地点 / 人-事件 / 人-物 / 事件链 / 概念-事件 / 门派驻地 / 人-功法
  const char = idsByType.character;
  const rels: { source: string; target: string; type: string; audience_known: boolean }[] = [];
  for (let i = 0; i < 15; i++)
    rels.push({ source: char[i], target: char[i + 1], type: "ALLY", audience_known: true });
  for (let i = 0; i < 10; i++)
    rels.push({ source: char[i], target: char[(i + 7) % 20], type: "RIVAL", audience_known: false });
  char.forEach((id, i) =>
    rels.push({ source: id, target: idsByType.faction[i % 6], type: "BELONGS_TO", audience_known: true }),
  );
  char.forEach((id, i) =>
    rels.push({ source: id, target: idsByType.location[i], type: "LIVES_IN", audience_known: true }),
  );
  for (let i = 0; i < 60; i++)
    rels.push({ source: char[i % 20], target: idsByType.event[i], type: "PARTICIPATES", audience_known: true });
  char.forEach((id, i) =>
    rels.push({ source: id, target: idsByType.item[i], type: "OWNS", audience_known: false }),
  );
  for (let i = 0; i < 15; i++)
    rels.push({ source: idsByType.event[i], target: idsByType.event[i + 1], type: "FOLLOWS", audience_known: true });
  for (let i = 0; i < 30; i++)
    rels.push({ source: idsByType.concept[i], target: idsByType.event[i * 2], type: "REFLECTS", audience_known: true });
  idsByType.faction.forEach((id, i) =>
    rels.push({ source: id, target: idsByType.location[10 + i], type: "BASED_AT", audience_known: true }),
  );
  for (let i = 0; i < 12; i++)
    rels.push({ source: char[(i + 5) % 20], target: idsByType.skill[i % 8], type: "MASTERS", audience_known: true });

  const t1 = Date.now();
  for (const r of rels) {
    const resp = await request.post("/api/relations", { data: r });
    expect(resp.status(), `播种关系 ${r.type}`).toBe(201);
  }
  const tRelations = Date.now() - t1;
  console.log(
    `[播种] 实体 ${entitiesCount + 20}（${JSON.stringify(counts)}，人物 20）耗时 ${tEntities}ms；关系 ${rels.length} 耗时 ${tRelations}ms`,
  );
  return entitiesCount + 20;
}

async function heapMB(page: import("@playwright/test").Page): Promise<number> {
  return page.evaluate(
    () =>
      Math.round(
        ((performance as unknown as { memory?: { usedJSHeapSize: number } }).memory
          ?.usedJSHeapSize ?? 0) / (1024 * 1024),
      ),
  );
}

test("负载验收: 194 实体 + 208 关系的加载/交互/内存", async ({ page, request }) => {
  test.setTimeout(600_000);

  // 清库兜底（残留 uvicorn 复用旧库时保证幂等），再全新播种
  await resetWorld(request);
  const entityCount = await seed(request);

  // —— 加载耗时 ——
  const tGo = Date.now();
  await page.goto("/");
  await expect(page.getByTestId("graph-stats")).toHaveText(
    new RegExp(`${entityCount} 节点 · 208 边`),
  );
  const tReady = Date.now() - tGo;
  const apiDuration = await page.evaluate(() => {
    const entries = performance.getEntriesByType("resource") as PerformanceResourceTiming[];
    const graphCall = entries.find((e) => e.name.includes("/api/graph"));
    return graphCall ? Math.round(graphCall.duration) : -1;
  });
  const memAfterLoad = await heapMB(page);

  // —— 布局收敛稳定 ——
  await page.waitForTimeout(11500); // 布局收敛 + 硬分离(兜底 9s+0.6s)
  const memAfterStable = await heapMB(page);
  await shoot(page, "LOAD-01-全景-194节点-208边");

  // —— 交互：连续缩放 + 主线程响应 ——
  const tInteract = Date.now();
  for (let i = 0; i < 6; i++) {
    await page.mouse.move(640, 360);
    await page.mouse.wheel(0, -240);
    await page.waitForTimeout(200);
  }
  const pingStart = Date.now();
  await page.evaluate(() => 40 + 2);
  const tPing = Date.now() - pingStart;
  const tInteractTotal = Date.now() - tInteract;
  const memAfterInteract = await heapMB(page);
  await shoot(page, "LOAD-02-交互缩放后");

  await page.waitForTimeout(5000);
  const memAfterIdle = await heapMB(page);

  const report = [
    "======== 负载验收报告 ========",
    `数据规模: ${entityCount} 实体 / 208 关系`,
    `播种耗时: 实体+关系（见上方播种日志）`,
    `GET /api/graph 响应: ${apiDuration}ms`,
    `首屏数据就绪（goto→stats 显示 ${entityCount} 节点）: ${tReady}ms`,
    `6 次缩放交互总耗时: ${tInteractTotal}ms（含人为间隔 200ms×6）`,
    `交互期间主线程往返(evaluate 42): ${tPing}ms`,
    `内存 JS 堆 MB: 加载后=${memAfterLoad} → 稳定后=${memAfterStable} → 交互后=${memAfterInteract} → 静置5s后=${memAfterIdle}（净增 ${memAfterIdle - memAfterLoad}）`,
    "================================",
  ];
  console.log(report.join("\n"));

  // —— 验收阈值（首基线：按本机实测定档，后续回归对照） ——
  expect(apiDuration).toBeLessThan(3000); // 后端聚合查询 < 3s
  expect(tReady).toBeLessThan(20000); // 首屏数据就绪 < 20s
  expect(tPing).toBeLessThan(1000); // 交互后主线程仍即时响应
  expect(memAfterIdle - memAfterLoad).toBeLessThan(150); // 无显著内存泄漏
  expect(memAfterIdle).toBeLessThan(800); // 堆绝对量上限（宽松）
});
