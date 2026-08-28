/**
 * selectionStore：画布选中态（实体/关系互斥）+ 详情面板开合。
 * 选中实体存 id，详情数据由面板按需拉取（不缓存实体快照，防陈旧）。
 */

import { create } from "zustand";

interface SelectionState {
  selectedEntityId: string | null;
  selectedRelationId: string | null;
  panelOpen: boolean;
  selectEntity: (id: string) => void;
  selectRelation: (id: string) => void;
  clear: () => void;
}

export const useSelectionStore = create<SelectionState>((set) => ({
  selectedEntityId: null,
  selectedRelationId: null,
  panelOpen: false,
  selectEntity: (id) =>
    set((state) =>
      state.selectedEntityId === id && state.panelOpen
        ? state // 重复点击同节点幂等（不闪面板）
        : { selectedEntityId: id, selectedRelationId: null, panelOpen: true },
    ),
  selectRelation: (id) =>
    set({ selectedRelationId: id, selectedEntityId: null, panelOpen: true }),
  clear: () => set({ selectedEntityId: null, selectedRelationId: null, panelOpen: false }),
}));
