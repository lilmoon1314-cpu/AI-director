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
  /** 角色下拉数据源（懒加载：首次切到 character 视角时拉取，随项目隔离） */
  characters: EntityBrief[];
  /** 角色列表已加载的项目（陈旧检测：项目切换后 reset 清空并重新拉取，F11）。 */
  loadedProjectId: string | null;
  setPerspective: (perspective: Perspective) => void;
  setCharacterId: (id: string | null) => void;
  loadCharacters: (projectId?: string) => Promise<void>;
  /** 项目切换重置换机（DESIGN.md §7）：回 author 默认、清角色选择与下拉缓存。 */
  reset: () => void;
}

export const usePerspectiveStore = create<PerspectiveState>((set, get) => ({
  perspective: "author",
  characterId: null,
  characters: [],
  loadedProjectId: null,
  setPerspective: (perspective) => set({ perspective }),
  setCharacterId: (characterId) => set({ characterId }),
  loadCharacters: async (projectId?: string) => {
    const pid = projectId ?? null;
    if (get().characters.length > 0 && get().loadedProjectId === pid) return; // 同项目已加载即复用
    const characters = await api.listEntities({
      type: "character",
      ...(pid ? { project_id: pid } : {}),
    });
    set({ characters, loadedProjectId: pid });
  },
  reset: () =>
    set({ perspective: "author", characterId: null, characters: [], loadedProjectId: null }),
}));
