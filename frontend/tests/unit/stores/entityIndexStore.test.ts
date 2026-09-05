/**
 * F07 L1：entityIndexStore 单元测试（U3）——fetch 全 mock，不触网络。
 * 缓存命中/强制刷新两态（等价类）；网络失败不抛未捕获异常由调用方 catch。
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import { useEntityIndexStore } from "../../../src/stores/entityIndexStore";

const BRIEFS = [
  { id: "char-a", type: "character", name: "周兰", aliases: [], audience_known: true },
  { id: "item-x", type: "item", name: "青铜镜", aliases: [], audience_known: false },
];

describe("entityIndexStore（F07 U3）", () => {
  beforeEach(() => {
    useEntityIndexStore.setState({ briefs: [] });
    vi.unstubAllGlobals();
  });

  it("load 拉全量摘要并缓存；非 force 重复调用不再请求", async () => {
    // 设计依据: 等价类—缓存命中
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(BRIEFS), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await useEntityIndexStore.getState().load();
    await useEntityIndexStore.getState().load(); // 缓存命中

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/api/entities");
    expect(useEntityIndexStore.getState().briefs).toHaveLength(2);
    expect(useEntityIndexStore.getState().briefs[0]?.audience_known).toBe(true);
  });

  it("force=true 强制重新拉取（实体增删改后刷新）", async () => {
    // 设计依据: 等价类—强制刷新
    const fetchMock = vi.fn().mockImplementation(
      () =>
        new Response(JSON.stringify(BRIEFS), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await useEntityIndexStore.getState().load();
    await useEntityIndexStore.getState().load(true);

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
