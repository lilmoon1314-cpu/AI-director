/**
 * graphStore：图数据（G6 格式）+ 加载状态。
 * F05 固定 author 视角加载（全量）；视角切换（perspectiveStore）由 F06 接管。
 */

import { create } from "zustand";

import { api, ApiError } from "../api/client";
import { toGraphData, type G6GraphData } from "../lib/toGraphData";

interface GraphState {
  graph: G6GraphData;
  loading: boolean;
  error: string | null;
  errorFix: string | null;
  loadGraph: () => Promise<void>;
}

export const useGraphStore = create<GraphState>((set) => ({
  graph: { nodes: [], edges: [] },
  loading: false,
  error: null,
  errorFix: null,
  loadGraph: async () => {
    set({ loading: true, error: null, errorFix: null });
    try {
      const data = await api.getGraph("author");
      set({ graph: toGraphData(data), loading: false });
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
