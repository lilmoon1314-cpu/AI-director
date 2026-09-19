import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation, useNavigate, type NavigateFunction } from "react-router-dom";
import { afterAll, afterEach, beforeAll, beforeEach, expect, it } from "vitest";
import { delay, http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import App from "../../src/App";
import { useProjectStore } from "../../src/stores/projectStore";
import { useAgentStore } from "../../src/stores/agentStore";

const stamp = "2026-09-19T00:00:00Z";
const projects = ["a", "b"].map((id) => ({ id, name: `项目 ${id}`, description: "", entity_count: 0, relation_count: 0, created_at: stamp, updated_at: stamp }));
const series = { id: "s1", project_id: "a", title: "行歌", created_at: stamp };
const episode = { id: "ep1", project_id: "a", series_id: "s1", position: 0, title: "晨练", outline: "陈知澜来到修习场。", status: "draft", created_at: stamp };
const server = setupServer(
  http.get("*/api/projects", () => HttpResponse.json(projects)),
  http.get("*/api/workflow/series", ({ request }) => HttpResponse.json(new URL(request.url).searchParams.get("project_id") === "a" ? [series] : [])),
  http.get("*/api/workflow/series/:id", ({ request }) => new URL(request.url).searchParams.get("project_id") === "a" ? HttpResponse.json(series) : HttpResponse.json({ problem: "系列不属于项目" }, { status: 422 })),
  http.get("*/api/workflow/episodes", () => HttpResponse.json([episode])),
  http.get("*/api/workflow/episodes/:id", () => HttpResponse.json(episode)),
  http.get("*/api/production/documents", () => HttpResponse.json([{ id: "doc1", project_id: "a", episode_id: "ep1", scene_id: null, artifact_id: "art1", document_type: "screenplay", source_document_id: null, source_artifact_id: null, source_block_ids: [], created_at: stamp }])),
  http.get("*/api/graph", () => HttpResponse.json({ nodes: [], edges: [] })),
  http.get("*/api/entities", () => HttpResponse.json([])),
);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());
afterEach(() => { cleanup(); server.resetHandlers(); });
beforeEach(() => {
  useProjectStore.setState({ projects: [], currentProjectId: null, routeProjectId: null, routeInvalid: false, error: null, loading: false });
  useAgentStore.getState().resetProjectScoped();
});
function open(path: string) {
  const router = { state: { location: { pathname: path } }, navigate: (() => {}) as NavigateFunction };
  function Probe() {
    router.state.location = useLocation();
    router.navigate = useNavigate();
    return null;
  }
  render(<MemoryRouter initialEntries={[path]}><Probe /><App /></MemoryRouter>);
  return router;
}

it("project default, series/episode deep links, production rail and browser back share real scope", async () => {
  const router = open("/projects/a");
  const user = userEvent.setup();
  await screen.findByRole("heading", { name: "项目概览" });
  expect(router.state.location.pathname).toBe("/projects/a/overview");
  expect(screen.getByText("当前阶段")).toBeInTheDocument();
  await user.click(await screen.findByRole("link", { name: /行歌.*查看剧集/ }));
  await user.click(await screen.findByRole("link", { name: /剧集 1.*晨练/ }));
  expect(await screen.findByText("陈知澜来到修习场。")).toBeInTheDocument();
  expect(screen.getByTestId("scope-bar")).toHaveTextContent("项目 a/系列与剧集/行歌/晨练");
  expect(await screen.findByText(/已保存记录/)).toBeInTheDocument();
  await user.click(screen.getByText("制作流程 · 概览"));
  await user.click(within(screen.getByTestId("production-rail")).getByRole("link", { name: "时间轴" }));
  expect(await screen.findByRole("heading", { name: "时间轴 · 浏览入口" })).toBeInTheDocument();
  await act(async () => { await router.navigate(-1); });
  expect(await screen.findByText("陈知澜来到修习场。")).toBeInTheDocument();
});

it("refresh-equivalent episode deep link resolves scope; forged project scope shows error", async () => {
  const router = open("/projects/a/series/s1/episodes/ep1/script");
  expect(await screen.findByRole("heading", { name: "剧本 · 浏览入口" })).toBeInTheDocument();
  await act(async () => { await router.navigate("/projects/b/series/s1/episodes/ep1/script"); });
  expect(await screen.findByRole("alert")).toHaveTextContent("系列不属于项目");
  expect(screen.queryByText("晨练")).not.toBeInTheDocument();
});

it("late previous-project list cannot pollute a new project, and empty state remains honest", async () => {
  let finish: (() => void) | undefined;
  server.use(http.get("*/api/workflow/series", async ({ request }) => {
    if (new URL(request.url).searchParams.get("project_id") === "a") {
      await new Promise<void>((resolve) => { finish = resolve; });
      return HttpResponse.json([series]);
    }
    return HttpResponse.json([]);
  }));
  const router = open("/projects/a/overview");
  await waitFor(() => expect(finish).toBeDefined());
  await act(async () => { await router.navigate("/projects/b/overview"); });
  await screen.findByText(/当前项目还没有系列/);
  await act(async () => { finish?.(); await delay(20); });
  expect(screen.queryByText("行歌")).not.toBeInTheDocument();
  expect(screen.getByTestId("scope-bar")).toHaveTextContent("项目 b");
});

it("request errors retry; visual entry explicitly stays unavailable", async () => {
  server.use(http.get("*/api/workflow/series", () => HttpResponse.json({ problem: "连接暂时失败" }, { status: 503 })));
  const router = open("/projects/a/overview");
  expect(await screen.findByRole("alert")).toHaveTextContent("连接暂时失败");
  server.resetHandlers();
  await userEvent.click(screen.getByRole("button", { name: "重试" }));
  expect(await screen.findByRole("link", { name: /行歌.*查看剧集/ })).toBeInTheDocument();
  await act(async () => { await router.navigate("/projects/a/create/visual"); });
  expect(await screen.findByText(/视觉资产工作区待开放/)).toBeInTheDocument();
});

it("pagination exposes records after the first page", async () => {
  server.use(http.get("*/api/workflow/series", ({ request }) => {
    const offset = Number(new URL(request.url).searchParams.get("offset"));
    return HttpResponse.json(offset ? [{ ...series, id: "last", title: "第二页系列" }] : Array.from({ length: 20 }, (_, i) => ({ ...series, id: `s${i}`, title: `系列 ${i}` })));
  }));
  open("/projects/a/overview");
  await userEvent.click(await screen.findByRole("button", { name: "下一页" }));
  expect(await screen.findByRole("link", { name: /第二页系列/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "下一页" })).toBeDisabled();
});
