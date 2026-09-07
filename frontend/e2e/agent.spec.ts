/**
 * F10 L3：Agent 对话工作流端到端（Playwright，FE1）——DESIGN.md §6 剧本 C 前半链路。
 * 真实后端（会话/草案确认/记忆文档真实落库）；LLM 环节（chat SSE / propose）
 * 经 page.route 拦截 mock（后端测试环境无 LLM 密钥）。
 * 路径: frontend/e2e/agent.spec.ts（docs/tests/F10_agent_chat.md FE1）。
 */

import { expect, test, type Route } from "@playwright/test";

import { openWorkbench, resetWorld, shoot } from "./helpers";

/** 以 mock SSE 帧应答 chat 请求（真实后端参与握手与落库）。 */
async function mockChat(route: Route): Promise<void> {
  const body = [
    'event: message_start\ndata: {"conversation_id":"mock"}\n\n',
    'event: token\ndata: {"text":"建议补充一位船医"}\n\n',
    'event: token\ndata: {"text":"角色，名叫周兰。"}\n\n',
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

  // —— 记忆文档：清理残留 → 模板新建（真实）→ 段级编辑保存 → 卡片刷新 ——
  // e2e 库跨运行持久（data/e2e_test.db），先删本项目文档保证「新建即 v1」的确定性；
  // 不做 page.reload——浏览器层 mock 的 SSE 消息只存在于客户端 store，刷新即丢
  await page.getByTestId("tab-agent").click();
  const existingDocs = (await page.request.get("/api/agent/memory-docs?project_id=project-default").then((r) => r.json())) as { id: string }[];
  for (const doc of existingDocs) await page.request.delete(`/api/agent/memory-docs/${doc.id}`);

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
