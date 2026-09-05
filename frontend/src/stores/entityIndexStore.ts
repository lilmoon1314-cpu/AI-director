/**
 * entityIndexStore：实体摘要索引（F07 @ 实体选择器与名称解析的数据源）。
 * - load()：GET /api/entities 全量摘要（194 实体约 20KB，可接受）；默认缓存，
 *   force=true 重新拉取（实体增删改后随图刷新调用）；
 * - 名称解析（id→name）在组件层由 briefs 派生 Map，store 不存冗余索引。
 */

import { create } from "zustand";

import { api, type EntityBrief } from "../api/client";

interface EntityIndexState {
  briefs: EntityBrief[];
  load: (force?: boolean) => Promise<void>;
}

export const useEntityIndexStore = create<EntityIndexState>((set, get) => ({
  briefs: [],
  load: async (force = false) => {
    if (!force && get().briefs.length > 0) return;
    const briefs = await api.listEntities();
    set({ briefs });
  },
}));
