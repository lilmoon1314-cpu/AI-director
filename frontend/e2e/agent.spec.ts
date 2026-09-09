/**
 * F10 L3：Agent 对话工作流端到端（Playwright，FE1）——DESIGN.md §6 剧本 C 前半链路。
 * 真实后端（会话/草案确认/记忆文档真实落库）；LLM 环节（chat SSE / propose）
 * 经 page.route 拦截 mock（后端测试环境无 LLM 密钥）。
 * 路径: frontend/e2e/agent.spec.ts（docs/tests/F10_agent_chat.md FE1）。
 */

import { expect, test, type Route } from "@playwright/test";

import { openWorkbench, resetWorld, shoot } from "./helpers";

/** 以 mock SSE 帧应答 chat 请求（真实后端参与握手与落库；F13 增 reasoning/usage 帧）。 */
async function mockChat(route: Route): Promise<void> {
  const body = [
    'event: message_start\ndata: {"conversation_id":"mock"}\n\n',
    'event: reasoning\ndata: {"text":"思考：主角团缺辅助位。"}\n\n',
    'event: token\ndata: {"text":"建议补充一位船医"}\n\n',
    'event: token\ndata: {"text":"角色，名叫周兰。"}\n\n',
    'event: usage\ndata: {"prompt_tokens":520,"completion_tokens":96,"context_max_tokens":8000,"context_ratio":0.065}\n\n',
    'event: done\ndata: {"message_id":"msg-mock"}\n\n',
  ].join("");
  await route.fulfill({
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
    body,
  });
}

test("FE1: Agent 对话 → 草案确认写入图谱 → 记忆文档编辑 + Dock 开合", async ({ page }) => {
  await resetWorld(page.request);

  // —— 记忆文档与会话清理前置（F13 唯一性：指导类已存在时「＋」置灰，须在进页面前
  // 清空，保证挂载后 docs 为空、「新建即 v1」的确定性；会话跨运行堆积会把
  // 记忆文档区挤出视口，点击被滚动边缘拦截——e2e 库持久不重建）——
  const existingDocs = (await page.request.get("/api/agent/memory-docs?project_id=project-default").then((r) => r.json())) as { id: string }[];
  for (const doc of existingDocs) await page.request.delete(`/api/agent/memory-docs/${doc.id}`);
  const existingSessions = (await page.request.get("/api/agent/sessions?project_id=project-default").then((r => r.json()))) as { id: string }[];
  for (const session of existingSessions) await page.request.delete(`/api/agent/sessions/${session.id}`);

  // —— 拦截 LLM 环节（chat SSE / propose）——
  await page.route("**/api/agent/chat", mockChat);
  await page.route("**/api/agent/propose", (route) =>
    route.fulfill({
      status: 200,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: "mock",
        drafts: [
          {
            draft_id: "draft-1",
            kind: "entity",
            payload: { type: "character", name: "周兰", description: "船医" },
            summary: "新增船医周兰",
          },
        ],
      }),
    }),
  );

  // —— 进入 Agent 主页（真实建会话）——
  await openWorkbench(page);
  await page.getByTestId("tab-agent").click();
  await expect(page).toHaveURL(/\/projects\/project-default\/agent$/);
  await expect(page.getByTestId("agent-input")).toBeVisible();
  await shoot(page, "AG-01-Agent主页-欢迎页");

  await page.getByTestId("agent-input").fill("主角团缺什么角色？");
  await page.getByTestId("agent-input-send").click();

  // —— 会话视图：mock 流式回复经真实后端落库并回读 ——
  await expect(page).toHaveURL(/\/agent\/s\/conv-/);
  await expect(page.getByTestId("agent-messages")).toContainText("建议补充一位船医角色，名叫周兰。", {
    timeout: 10_000,
  });
  await shoot(page, "AG-02-对话回复渲染");

  // —— F13 UsageBar：usage 事件写入轮次状态（done 回读不清空 usageBySession）——
  await expect(page.getByTestId("agent-usage-context")).toContainText("520/8.0k");
  await expect(page.getByTestId("agent-usage-turn")).toContainText("520+96");
  await expect(page.getByTestId("agent-usage-ratio")).toContainText("7%");

  // —— 产出草案（mock propose）→ 确认写入（真实落库）——
  await page.getByTestId("agent-input").fill("就加周兰吧");
  await page.getByTestId("agent-propose").click();
  await expect(page.getByTestId("agent-draft-card")).toContainText("周兰");
  await shoot(page, "AG-03-草案确认卡");

  await page.getByTestId("agent-draft-confirm").click();
  await expect(page.getByTestId("agent-messages")).toContainText("已写入 1 项", { timeout: 10_000 });

  // —— 图谱失效广播：切回图谱页可见新实体 ——
  await page.getByTestId("tab-graph").click();
  await expect(page.getByTestId("graph-stats")).toHaveText(/1 节点/);
  await shoot(page, "AG-04-确认后图谱出现新实体");

  // —— 记忆文档：模板新建（真实）→ 段级编辑保存 → 卡片刷新 ——
  // （清理已前置到 resetWorld 之后；F13 唯一性下挂载时 docs 为空，按钮可用）
  await page.getByTestId("tab-agent").click();

  await page.getByTestId("memory-doc-create-style").click();
  await expect(page.getByTestId("memory-doc-card").first()).toContainText("风格约定");

  await page.getByTestId("memory-doc-card").first().click();
  await expect(page.getByTestId("doc-editor")).toBeVisible();
  // 等文档载入完成（段元信息出现），避免 open-load 与 fill 竞态重置输入
  await expect(page.getByTestId("doc-editor")).toContainText("v1 · 作者 更新");
  await page.getByLabel(/1\. 叙事视角/).fill("第一人称限制视角。");
  // 保存成功后按钮立即变 disabled（dirty 复位）→ Playwright 会无限重试点击；
  // force 单次派发 + 以 PATCH 响应作为完成依据
  const sectionPatch = page.waitForResponse(
    (resp) => resp.url().includes("/sections/") && resp.request().method() === "PATCH",
  );
  await page.getByTestId("doc-section-save-1").click({ force: true });
  await sectionPatch;
  await expect(page.getByTestId("doc-editor")).toContainText("v2", { timeout: 10_000 });
  await shoot(page, "AG-05-记忆文档段级编辑");
  await page.getByTestId("doc-editor-close").click();

  // —— AgentDock：图谱页唤起侧边栏（同一会话池——草案确认消息在池内可见）——
  // 注：浏览器层 mock 的 chat 不落库，done 后的服务端回读会清掉首轮回复
  // （生产行为正确：服务端有持久化）；断言改用客户端追加的确认摘要
  await page.getByTestId("tab-graph").click();
  await page.getByTestId("agent-dock-toggle").click();
  await expect(page.getByTestId("agent-dock")).toBeVisible();
  await expect(page.getByTestId("agent-dock")).toContainText("已写入 1 项草案", { timeout: 10_000 });
  await page.getByTestId("agent-dock-close").click();
  await expect(page.getByTestId("agent-dock")).toHaveCount(0);
  await shoot(page, "AG-06-Dock侧边栏复用会话");
});

test("AG-07: F14 写入工具登记 → 确认卡 → 全部写入 → 图谱与文档刷新", async ({ page }) => {
  await resetWorld(page.request);

  // —— 拦截 LLM chat：done 携带 pending_writes 清单（浏览器层 mock，登记经真实后端语义渲染）——
  await page.route("**/api/agent/chat", (route) => {
    const body = [
      'event: message_start\ndata: {"conversation_id":"mock"}\n\n',
      'event: token\ndata: {"text":"我登记了两项写入，请确认。"}\n\n',
      `event: done\ndata: {"message_id":"msg-mock","pending_writes":[{"id":"pw-mock-1","conversation_id":"mock","kind":"create_entity","payload":{"type":"character","name":"船医周兰"},"baseline":null,"status":"pending","summary":"新增实体「船医周兰」（character）","created_at":"2026-09-08T00:00:00Z"},{"id":"pw-mock-2","conversation_id":"mock","kind":"write_doc_section","payload":{"doc_id":"mdoc-mock","seq":1,"content":"海难求生。"},"baseline":null,"status":"pending","summary":"写入《世界观定位》第 1 段","created_at":"2026-09-08T00:00:01Z"}]}\n\n`,
    ].join("");
    return route.fulfill({
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
      body,
    });
  });
  // approve 走真实后端（登记行不存在会失败）→ 改拦截为 mock 成功 + 真实失效刷新可观察
  let approvedIds: string[] = [];
  await page.route("**/api/agent/pending-writes/approve", async (route) => {
    const req = route.request();
    const body = (await req.postDataJSON()) as { ids: string[] };
    approvedIds = body.ids;
    return route.fulfill({
      status: 200,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        created: body.ids.map((id) => ({ id, kind: "create_entity", target_id: "ent-e2e", name: "船医周兰" })),
        failed: [],
      }),
    });
  });

  await openWorkbench(page);
  await page.getByTestId("tab-agent").click();
  await expect(page.getByTestId("agent-input")).toBeVisible();

  await page.getByTestId("agent-input").fill("登记一个船医");
  await page.getByTestId("agent-input-send").click();

  // —— 确认卡渲染：两项 + 默认全选 ——
  await expect(page.getByTestId("agent-pending-card")).toBeVisible({ timeout: 10_000 });
  const pendingItems = page.getByTestId("agent-pending-item");
  await expect(pendingItems).toHaveCount(2);
  await expect(pendingItems.nth(0)).toHaveText(/船医周兰/);
  await expect(pendingItems.nth(1)).toHaveText(/世界观定位/);
  await expect(page.getByTestId("agent-pending-approve")).toContainText("写入所选（2）");
  await shoot(page, "AG-07-待写入确认卡");

  // —— 全部写入 → 成功后卡片消失 ——
  await page.getByTestId("agent-pending-approve").click();
  await expect(page.getByTestId("agent-pending-card")).toHaveCount(0, { timeout: 10_000 });
  expect(approvedIds.sort()).toEqual(["pw-mock-1", "pw-mock-2"]);
  await shoot(page, "AG-08-确认后卡片消失");
});
