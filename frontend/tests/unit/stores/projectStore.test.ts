/**
 * F11 L1：projectStore 单元测试（FU1）。fetch 全 mock，不触网络。
 * 用例设计（等价类/边界值标注）见 docs/tests/F11_multi_project_foundation.md。
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import { useProjectStore } from "../../../src/stores/projectStore";

const PROJECT = {
  id: "project-x",
  name: "长安怪谈",
  description: "盛唐志怪",
  entity_count: 2,
  relation_count: 1,
  created_at: "2026-09-06T00:00:00Z",
  updated_at: "2026-09-06T00:00:00Z",
};

const DEFAULT_PROJECT = {
  ...PROJECT,
  id: "project-default",
  name: "默认项目",
  entity_count: 0,
  relation_count: 0,
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("projectStore（FU1）", () => {
  beforeEach(() => {
    useProjectStore.setState({
      projects: [],
      loading: false,
      error: null,
      errorFix: null,
      currentProjectId: null,
      routeProjectId: null,
      routeInvalid: false,
    });
    vi.unstubAllGlobals();
  });

  it("FU1-1: loadProjects 成功 → 列表填充；缓存语义（有数据不重拉，force 强制）", async () => {
    // 设计依据: 等价类—成功路径 + 边界值—force 两态
    const fetchMock = vi.fn(async () => jsonResponse([DEFAULT_PROJECT, PROJECT]));
    vi.stubGlobal("fetch", fetchMock);

    await useProjectStore.getState().loadProjects();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(useProjectStore.getState().projects).toHaveLength(2);

    await useProjectStore.getState().loadProjects(); // 缓存：不重拉
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await useProjectStore.getState().loadProjects(true); // force：重拉
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("FU1-2: loadProjects 失败 → error 三要素置位（等价类—错误路径）", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );
    await useProjectStore.getState().loadProjects();
    const s = useProjectStore.getState();
    expect(s.loading).toBe(false);
    // ApiError 路径：problem/fix 来自统一错误体（无法连接服务器 → 确认后端）
    expect(s.error).toBe("无法连接服务器");
    expect(s.errorFix).toContain("后端服务");
  });

  it("FU1-3: syncRoute 有效项目 → current 置位且 routeInvalid=false；同参跳过", async () => {
    // 设计依据: 等价类—路由同步有效值；边界值—重复同步幂等
    const fetchMock = vi.fn(async () => jsonResponse([DEFAULT_PROJECT, PROJECT]));
    vi.stubGlobal("fetch", fetchMock);

    await useProjectStore.getState().syncRoute(PROJECT.id);
    const s = useProjectStore.getState();
    expect(s.currentProjectId).toBe(PROJECT.id);
    expect(s.routeInvalid).toBe(false);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await useProjectStore.getState().syncRoute(PROJECT.id); // 同参 + 已有列表 → 零请求
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("FU1-4: syncRoute 幽灵项目 → routeInvalid=true 且 current 置空（等价类—无效值）", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse([DEFAULT_PROJECT])));
    await useProjectStore.getState().syncRoute("project-ghost");
    const s = useProjectStore.getState();
    expect(s.routeInvalid).toBe(true);
    expect(s.currentProjectId).toBeNull();
  });

  it("FU1-5: syncRoute 列表加载失败 → 不判无效（数据不可得≠项目不存在，防护分支）", async () => {
    // 设计依据: 等价类—网络失败与无效路由的区分（避免误渲染错误页）
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );
    await useProjectStore.getState().syncRoute(PROJECT.id);
    const s = useProjectStore.getState();
    expect(s.routeInvalid).toBe(false);
  });

  it("FU1-6: deleteProject → 列表收缩；删除当前项目 → current 置空", async () => {
    // 设计依据: 等价类—删除后状态收缩（边界值—删除目标为当前项目）
    useProjectStore.setState({
      projects: [DEFAULT_PROJECT, PROJECT],
      currentProjectId: PROJECT.id,
    });
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await useProjectStore.getState().deleteProject(PROJECT.id);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const s = useProjectStore.getState();
    expect(s.projects.map((p) => p.id)).toEqual([DEFAULT_PROJECT.id]);
    expect(s.currentProjectId).toBeNull();
  });
});
