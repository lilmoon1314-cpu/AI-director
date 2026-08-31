/**
 * perspectiveStore：三视角切换状态（F06）。
 * - perspective：author 全知 / character 角色 / audience 观众（后端 /api/graph 契约）；
 * - characterId：character 视角的视角角色 id；切走再切回时保留（回切恢复，免重复选择）；
 * - characters：角色下拉数据源（GET /api/entities?type=character 摘要）。
 * 视角过滤逻辑本体在后端（F04 perspectives.service），本 store 只管切换状态与数据源。
 */

import { create } from "zustand";

import { api, type EntityBrief } from "../api/client";

export type Perspective = "author" | "character" | "audience";

/** 视角中文标签（切换控件与状态栏标注共用）。 */
export const PERSPECTIVE_LABELS: Record<Perspective, string> = {
  author: "作者",
  character: "角色",
  audience: "观众",
};

interface PerspectiveState {
  perspective: Perspective;
  characterId: string | null;
  /** 角色下拉数据源（懒加载：首次切到 character 视角时拉取） */
  characters: EntityBrief[];
  setPerspective: (perspective: Perspective) => void;
  setCharacterId: (id: string | null) => void;
  loadCharacters: () => Promise<void>;
}

export const usePerspectiveStore = create<PerspectiveState>((set, get) => ({
  perspective: "author",
  characterId: null,
  characters: [],
  setPerspective: (perspective) => set({ perspective }),
  setCharacterId: (characterId) => set({ characterId }),
  loadCharacters: async () => {
    if (get().characters.length > 0) return; // 已加载即复用（同一会话角色列表稳定）
    const characters = await api.listEntities({ type: "character" });
    set({ characters });
  },
}));
