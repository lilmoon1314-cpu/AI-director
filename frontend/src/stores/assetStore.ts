/**
 * assetStore：资产管理页全局状态（F08）。
 * - 通用资产卡片与项目资产卡片的列表 + 加载态（缓存式：已有数据不重复拉取）；
 * - 分类筛选（前端过滤，与后端 category 查询语义一致——用空过滤全量拉取后派生）；
 * - 内嵌 HTML 查看器开关（viewer：iframe 地址 + 标题）。
 * 列表刷新策略：任何写操作（上传/建/改/删）成功后由调用方显式 reload。
 */

import { create } from "zustand";

import { api, type AssetCard, type EntityAssetCard } from "../api/client";
import { useProjectStore } from "./projectStore";

export interface AssetViewerState {
  /** 资产 HTML 页地址（api.assetPageUrl 生成）。 */
  url: string;
  title: string;
}

interface AssetState {
  generalCards: AssetCard[];
  generalLoading: boolean;
  entityCards: EntityAssetCard[];
  entityLoading: boolean;
  /** 项目资产卡片已加载的项目（陈旧检测，F11；通用卡片为全局缓存无此概念）。 */
  entityCardsProjectId: string | null;
  viewer: AssetViewerState | null;
  loadGeneral: (force?: boolean) => Promise<void>;
  loadEntityCards: (projectId?: string, force?: boolean) => Promise<void>;
  openViewer: (viewer: AssetViewerState) => void;
  closeViewer: () => void;
  /** 项目切换重置换机（DESIGN.md §7）：清项目资产卡片与查看器；generalCards 为全局缓存保留。 */
  resetProjectScoped: () => void;
}

export const useAssetStore = create<AssetState>((set, get) => ({
  generalCards: [],
  generalLoading: false,
  entityCards: [],
  entityLoading: false,
  entityCardsProjectId: null,
  viewer: null,
  loadGeneral: async (force = false) => {
    if (!force && get().generalCards.length > 0) return;
    set({ generalLoading: true });
    try {
      const generalCards = await api.listGeneralAssets();
      set({ generalCards });
    } finally {
      set({ generalLoading: false });
    }
  },
  loadEntityCards: async (projectId?: string, force = false) => {
    const pid = projectId ?? useProjectStore.getState().currentProjectId ?? null;
    if (!force && get().entityCards.length > 0 && get().entityCardsProjectId === pid) return;
    set({ entityLoading: true });
    try {
      // 项目资产随实体间接归属项目（F11）：随当前项目拉取
      const entityCards = await api.listEntityCards(pid ?? undefined);
      set({ entityCards, entityCardsProjectId: pid });
    } finally {
      set({ entityLoading: false });
    }
  },
  openViewer: (viewer) => set({ viewer }),
  closeViewer: () => set({ viewer: null }),
  resetProjectScoped: () =>
    set({ entityCards: [], entityLoading: false, entityCardsProjectId: null, viewer: null }),
}));
