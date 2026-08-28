/**
 * F05 L1：selectionStore 单元测试（U2）。纯内存，无依赖。
 * 用例设计：等价类—选中/清除两态；边界值—重复选同 id 幂等、实体/关系互斥。
 */

import { beforeEach, describe, expect, it } from "vitest";

import { useSelectionStore } from "../../../src/stores/selectionStore";

describe("selectionStore（U2）", () => {
  beforeEach(() => {
    useSelectionStore.setState({
      selectedEntityId: null,
      selectedRelationId: null,
      panelOpen: false,
    });
  });

  it("selectEntity 置 id 并开面板", () => {
    useSelectionStore.getState().selectEntity("char-a");
    const s = useSelectionStore.getState();
    expect(s.selectedEntityId).toBe("char-a");
    expect(s.selectedRelationId).toBeNull();
    expect(s.panelOpen).toBe(true);
  });

  it("重复点击同节点幂等（面板不闪断）", () => {
    useSelectionStore.getState().selectEntity("char-a");
    useSelectionStore.getState().selectEntity("char-a");
    const s = useSelectionStore.getState();
    expect(s.selectedEntityId).toBe("char-a");
    expect(s.panelOpen).toBe(true);
  });

  it("实体/关系互斥：选边清除实体选中", () => {
    useSelectionStore.getState().selectEntity("char-a");
    useSelectionStore.getState().selectRelation("rel-1");
    const s = useSelectionStore.getState();
    expect(s.selectedRelationId).toBe("rel-1");
    expect(s.selectedEntityId).toBeNull();
    expect(s.panelOpen).toBe(true);
  });

  it("clear 复位全部选中与面板", () => {
    useSelectionStore.getState().selectEntity("char-a");
    useSelectionStore.getState().clear();
    const s = useSelectionStore.getState();
    expect(s.selectedEntityId).toBeNull();
    expect(s.selectedRelationId).toBeNull();
    expect(s.panelOpen).toBe(false);
  });
});
