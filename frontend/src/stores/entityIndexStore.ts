/**
 * entityIndexStore：实体摘要索引（F07 @ 实体选择器与名称解析的数据源）。
 * - load()：GET /api/entities 全量摘要（194 实体约 20KB，可接受）；默认缓存，
 *   force=true 重新拉取（实体增删改后随图刷新调用）；
 * - 名称解析（id→name）在组件层由 briefs 派生 Map，store 不存冗余索引。
 */

import { create } from "zustand";

import { api, type EntityBrief } from "../api/client";
import { useProjectStore } from "./projectStore";

interface EntityIndexState {
  briefs: EntityBrief[];
  /** 索引已加载的项目（陈旧检测：项目切换后 reset 清空重拉，F11）。 */
  loadedProjectId: string | null;
  load: (force?: boolean, projectId?: string) => Promise<void>;
  /** 项目切换重置换机（DESIGN.md §7）：清空摘要索引（随项目隔离）。 */
  reset: () => void;
}

export const useEntityIndexStore = create<EntityIndexState>((set, get) => ({
  briefs: [],
  loadedProjectId: null,
  load: async (force = false, projectId?: string) => {
    const pid = projectId ?? useProjectStore.getState().currentProjectId ?? null;
    if (!force && get().briefs.length > 0 && get().loadedProjectId === pid) return;
    // @ 选择器与名称解析随项目隔离（跨项目引用被后端拒绝，F11 I8）
    const briefs = await api.listEntities(pid ? { project_id: pid } : undefined);
    set({ briefs, loadedProjectId: pid });
  },
  reset: () => set({ briefs: [], loadedProjectId: null }),
}));
