/**
 * projectStore：多项目底座（F11，DESIGN.md §7）。
 * - projects/currentProjectId：项目列表与当前项目（工作台数据调用的项目上下文来源）；
 * - 路由参数为项目上下文的事实源：Workbench 把 /projects/:projectId 同步进本 store
 *   （syncRoute 校验存在性，无效 id 置 routeInvalid 供壳层渲染错误页）；
 * - 切换项目的各 store 重置换机由叶子视图按 projectId 变化局部执行
 *   （GraphView/AssetLibrary 各自 reset+reload，避免父子 effect 顺序竞态）；
 * - 通用参考库为全局资源：assetStore.generalCards 跨项目复用，不随切换重置。
 */

import { create } from "zustand";
import { useOutletContext } from "react-router-dom";

import { api, ApiError, type ProjectCreate, type ProjectRead, type ProjectUpdate } from "../api/client";

interface ProjectState {
  projects: ProjectRead[];
  loading: boolean;
  error: string | null;
  errorFix: string | null;
  /** 当前项目 id（工作台叶子视图数据调用的项目上下文；null=未进入工作台）。 */
  currentProjectId: string | null;
  /** 路由当前携带的 projectId（syncRoute 输入）。 */
  routeProjectId: string | null;
  /** 路由参数指向不存在的项目（壳层渲染错误页 + 返回首屏）。 */
  routeInvalid: boolean;
  loadProjects: (force?: boolean) => Promise<void>;
  createProject: (body: ProjectCreate) => Promise<ProjectRead>;
  updateProject: (id: string, body: ProjectUpdate) => Promise<ProjectRead>;
  deleteProject: (id: string) => Promise<void>;
  /** 同步路由参数 → 当前项目（校验存在性；列表未加载时先拉取）。 */
  syncRoute: (projectId: string) => Promise<void>;
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  projects: [],
  loading: false,
  error: null,
  errorFix: null,
  currentProjectId: null,
  routeProjectId: null,
  routeInvalid: false,
  loadProjects: async (force = false) => {
    if (!force && get().projects.length > 0) return;
    set({ loading: true, error: null, errorFix: null });
    try {
      const projects = await api.listProjects();
      set({ projects, loading: false });
    } catch (cause) {
      const err =
        cause instanceof ApiError
          ? cause
          : new ApiError(0, {
              problem: "项目列表加载失败",
              cause: String(cause),
              fix: "确认后端服务已启动后重试",
            });
      set({ loading: false, error: err.problem, errorFix: err.fix });
    }
  },
  createProject: (body) => api.createProject(body),
  updateProject: (id, body) => api.updateProject(id, body),
  deleteProject: async (id) => {
    await api.deleteProject(id);
    // 删除后同步收缩列表与当前项目（当前项目被删由调用方导航回首屏）
    const projects = get().projects.filter((p) => p.id !== id);
    set({
      projects,
      ...(get().currentProjectId === id ? { currentProjectId: null } : {}),
    });
  },
  syncRoute: async (projectId) => {
    if (get().routeProjectId === projectId && get().projects.length > 0) return;
    await get().loadProjects();
    // 列表加载失败（网络/服务端错误）≠ 项目无效：保留工作台渲染，数据错误由各页呈现
    if (get().projects.length === 0 && get().error) return;
    const exists = get().projects.some((p) => p.id === projectId);
    set({
      routeProjectId: projectId,
      routeInvalid: !exists,
      currentProjectId: exists ? projectId : null,
    });
  },
}));

/** 当前项目对象（派生选择器；无当前项目返回 null）。 */
export function selectCurrentProject(
  state: Pick<ProjectState, "projects" | "currentProjectId">,
): ProjectRead | null {
  return state.projects.find((p) => p.id === state.currentProjectId) ?? null;
}

/**
 * 当前项目 id（叶子视图统一取用，F11）。
 * 优先读 Workbench Outlet context（渲染期同步可得——子组件挂载 effect 先于父组件
 * 的 syncRoute effect 执行，显式传参避免读到上一项目的旧值）；兜底 store 当前项目
 * （非路由挂载的单测环境 / 交互期重载场景）。
 */
export function useProjectId(): string | undefined {
  // 无路由挂载（单测直接渲染组件）时 useOutletContext 返回 null——空值防护兜底 store
  const ctx = useOutletContext<{ projectId?: string } | null>();
  const fromStore = useProjectStore((s) => s.currentProjectId);
  return ctx?.projectId ?? fromStore ?? undefined;
}
