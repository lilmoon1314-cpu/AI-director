/**
 * graphStore：图数据（G6 格式）+ 加载状态。
 * F06 起按 perspectiveStore 当前视角加载（author 全量 / character 按 known_by / audience 双端规则
 * ——过滤本体在后端 F04 perspectives.service）；每次 loadGraph 实时读视角状态。
 * F11 起按 projectStore.currentProjectId 加载（项目维度与视角过滤正交叠加，缺省=默认项目）。
 */

import { create } from "zustand";

import { api, ApiError } from "../api/client";
import { toGraphData, type G6GraphData } from "../lib/toGraphData";
import { usePerspectiveStore } from "./perspectiveStore";
import { useProjectStore } from "./projectStore";

interface GraphState {
  graph: G6GraphData;
  loading: boolean;
  error: string | null;
  errorFix: string | null;
  /** 已加载图数据所属项目（陈旧检测：GraphView 据此触发切换重置换机，F11）。 */
  loadedProjectId: string | null;
  loadGraph: (projectId?: string) => Promise<void>;
}

export const useGraphStore = create<GraphState>((set) => ({
  graph: { nodes: [], edges: [] },
  loading: false,
  error: null,
  errorFix: null,
  loadedProjectId: null,
  loadGraph: async (projectId?: string) => {
    const { perspective, characterId } = usePerspectiveStore.getState();
    // 显式传参优先（Outlet context 渲染期同步值），兜底 store 当前项目
    const pid = projectId ?? useProjectStore.getState().currentProjectId ?? undefined;
    set({ loading: true, error: null, errorFix: null });
    try {
      // character_id 仅随 character 视角发送（回切保留的角色 id 不泄入其他视角请求）
      const data = await api.getGraph(
        perspective,
        perspective === "character" ? (characterId ?? undefined) : undefined,
        pid,
      );
      set({ graph: toGraphData(data), loading: false, loadedProjectId: pid ?? null });
    } catch (cause) {
      const err =
        cause instanceof ApiError
          ? cause
          : new ApiError(0, {
              problem: "图数据加载失败",
              cause: String(cause),
              fix: "刷新页面重试",
            });
      set({ loading: false, error: err.problem, errorFix: err.fix });
    }
  },
}));
