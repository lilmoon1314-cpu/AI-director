/**
 * assetStore：资产管理页全局状态（F08；F12 增分区错误态——DESIGN.md §5.3.1
 * 状态矩阵「error → 三要素错误条 + 重试」，错误不再吞成空态误导）。
 * - 通用资产卡片与项目资产卡片的列表 + 加载/错误态（缓存式：已有数据不重复拉取）；
 * - 分类筛选（前端过滤，与后端 category 查询语义一致——用空过滤全量拉取后派生）；
 * - 内嵌 HTML 查看器开关（viewer：iframe 地址 + 标题）。
 * 列表刷新策略：任何写操作（上传/建/改/删）成功后由调用方显式 reload。
 */

import { create } from "zustand";

import { api, ApiError, type AssetCard, type EntityAssetCard } from "../api/client";
import { useProjectStore } from "./projectStore";

/** 三要素错误态（什么出了问题 / 怎么修；why 由后端 cause 承载，UI 呈现 problem+fix）。 */
export interface AssetErrorState {
  problem: string;
  fix: string;
}

export interface AssetViewerState {
  /** 资产 HTML 页地址（api.assetPageUrl 生成）。 */
  url: string;
  title: string;
}

interface AssetState {
  generalCards: AssetCard[];
  generalLoading: boolean;
  generalError: AssetErrorState | null;
  entityCards: EntityAssetCard[];
  entityLoading: boolean;
  entityError: AssetErrorState | null;
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

function toErrorState(cause: unknown, fallbackProblem: string): AssetErrorState {
  const err = cause instanceof ApiError ? cause : null;
  return {
    problem: err?.problem ?? fallbackProblem,
    fix: err?.fix ?? "确认后端服务已启动后重试",
  };
}

export const useAssetStore = create<AssetState>((set, get) => ({
  generalCards: [],
  generalLoading: false,
  generalError: null,
  entityCards: [],
  entityLoading: false,
  entityError: null,
  entityCardsProjectId: null,
  viewer: null,
  loadGeneral: async (force = false) => {
    if (!force && get().generalCards.length > 0) return;
    set({ generalLoading: true, generalError: null });
    try {
      const generalCards = await api.listGeneralAssets();
      set({ generalCards });
    } catch (cause) {
      set({ generalError: toErrorState(cause, "通用参考库加载失败") });
    } finally {
      set({ generalLoading: false });
    }
  },
  loadEntityCards: async (projectId?: string, force = false) => {
    const pid = projectId ?? useProjectStore.getState().currentProjectId ?? null;
    if (!force && get().entityCards.length > 0 && get().entityCardsProjectId === pid) return;
    set({ entityLoading: true, entityError: null });
    try {
      // 项目资产随实体间接归属项目（F11）：随当前项目拉取
      const entityCards = await api.listEntityCards(pid ?? undefined);
      set({ entityCards, entityCardsProjectId: pid });
    } catch (cause) {
      set({ entityError: toErrorState(cause, "项目资产加载失败") });
    } finally {
      set({ entityLoading: false });
    }
  },
  openViewer: (viewer) => set({ viewer }),
  closeViewer: () => set({ viewer: null }),
  resetProjectScoped: () =>
    set({
      entityCards: [],
      entityLoading: false,
      entityError: null,
      entityCardsProjectId: null,
      viewer: null,
    }),
}));
