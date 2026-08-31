/**
 * F06 L1：perspectiveStore 单元测试（三态切换 + 角色保留）。
 * 纯状态机测试，不触网络（loadCharacters 的网络链路由 L2 集成覆盖）。
 * 用例设计见 docs/tests/F06_perspective_switch_ui.md（U1）。
 */

import { beforeEach, describe, expect, it } from "vitest";

import { usePerspectiveStore } from "../../../src/stores/perspectiveStore";

describe("perspectiveStore（F06 U1 三态切换）", () => {
  beforeEach(() => {
    usePerspectiveStore.setState({
      perspective: "author",
      characterId: null,
      characters: [],
    });
  });

  it("初始态：author 视角、无角色（边界值—初始态）", () => {
    const s = usePerspectiveStore.getState();
    expect(s.perspective).toBe("author");
    expect(s.characterId).toBeNull();
    expect(s.characters).toEqual([]);
  });

  it("setPerspective 三态逐一切换生效", () => {
    // 设计依据: 等价类—视角枚举逐一（author/character/audience）
    const store = usePerspectiveStore.getState();
    store.setPerspective("audience");
    expect(usePerspectiveStore.getState().perspective).toBe("audience");
    usePerspectiveStore.getState().setPerspective("character");
    expect(usePerspectiveStore.getState().perspective).toBe("character");
    usePerspectiveStore.getState().setPerspective("author");
    expect(usePerspectiveStore.getState().perspective).toBe("author");
  });

  it("切走再切回 character，已选角色保留（回切恢复设计）", () => {
    // 设计依据: 边界值—视角往返后角色 id 不丢失
    usePerspectiveStore.getState().setCharacterId("char-a");
    usePerspectiveStore.getState().setPerspective("audience");
    expect(usePerspectiveStore.getState().characterId).toBe("char-a"); // 切走不清空
    usePerspectiveStore.getState().setPerspective("character");
    const s = usePerspectiveStore.getState();
    expect(s.perspective).toBe("character");
    expect(s.characterId).toBe("char-a");
  });

  it("setCharacterId 置位与清空两态", () => {
    // 设计依据: 等价类—置位/清除
    usePerspectiveStore.getState().setCharacterId("char-b");
    expect(usePerspectiveStore.getState().characterId).toBe("char-b");
    usePerspectiveStore.getState().setCharacterId(null);
    expect(usePerspectiveStore.getState().characterId).toBeNull();
  });
});
