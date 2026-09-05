/**
 * F08 L1：assetStore 单元测试（UF2 等价类：缓存加载/强制刷新/查看器开关）。
 * load* 的网络链路由 L2 集成（MSW）覆盖；此处仅验证状态机语义。
 */

import { beforeEach, describe, expect, it } from "vitest";

import { useAssetStore } from "../../../src/stores/assetStore";

const CARD = {
  id: "asset-1",
  category: "表情参考",
  title: "愤怒",
  description: "",
  cover_url: null as string | null,
  image_count: 0,
  updated_at: "2026-09-05T00:00:00Z",
};

describe("assetStore（F08 UF2）", () => {
  beforeEach(() => {
    useAssetStore.setState({
      generalCards: [],
      generalLoading: false,
      entityCards: [],
      entityLoading: false,
      viewer: null,
    });
  });

  it("初始态：空列表、无查看器（边界值—初始态）", () => {
    const s = useAssetStore.getState();
    expect(s.generalCards).toEqual([]);
    expect(s.entityCards).toEqual([]);
    expect(s.viewer).toBeNull();
  });

  it("openViewer/closeViewer 开关两态（等价类：打开/关闭）", () => {
    const store = useAssetStore.getState();
    store.openViewer({ url: "/api/assets/general/asset-1/page", title: "愤怒" });
    expect(useAssetStore.getState().viewer?.title).toBe("愤怒");
    useAssetStore.getState().closeViewer();
    expect(useAssetStore.getState().viewer).toBeNull();
  });

  it("set 列表数据后缓存生效：loadGeneral 不 force 且已有数据时跳过重拉", async () => {
    // 设计依据: 等价类—缓存命中/未命中；网络 mock 缺席时命中路径不发起请求
    useAssetStore.setState({ generalCards: [CARD] });
    await useAssetStore.getState().loadGeneral(false);
    expect(useAssetStore.getState().generalCards).toEqual([CARD]);
  });
});
