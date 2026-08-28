/**
 * F05 L1：graphStore 单元测试（U1–U3）。fetch 全 mock，不触网络。
 * 种子世界见 docs/tests/F05_frontend_graph_workbench.md。
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import { useGraphStore } from "../../../src/stores/graphStore";

const SEED_GRAPH = {
  nodes: [
    { id: "char-a", type: "character", name: "周兰", aliases: [] },
    { id: "char-b", type: "character", name: "沈墨", aliases: [] },
  ],
  edges: [{ id: "rel-1", source: "char-a", target: "char-b", type: "ALLY" }],
};

describe("graphStore（U1–U3）", () => {
  beforeEach(() => {
    useGraphStore.setState({
      graph: { nodes: [], edges: [] },
      loading: false,
      error: null,
      errorFix: null,
    });
    vi.unstubAllGlobals();
  });

  it("U1: 加载成功 → nodes/edges 填充且 loading 经历 true→false", async () => {
    // 设计依据: 等价类—API 有效响应
    const loadingDuringFetch = vi.fn();
    const fetchMock = vi.fn(async () => {
      loadingDuringFetch(useGraphStore.getState().loading);
      return new Response(JSON.stringify(SEED_GRAPH), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    await useGraphStore.getState().loadGraph();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    // 请求固定 author 视角（F06 才引入切换）
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("perspective=author");
    expect(loadingDuringFetch).toHaveBeenCalledWith(true); // fetch 期间 loading 已置位
    expect(useGraphStore.getState().loading).toBe(false);
    expect(useGraphStore.getState().graph.nodes.map((n) => n.id)).toEqual(["char-a", "char-b"]);
    expect(useGraphStore.getState().graph.edges.map((e) => e.id)).toEqual(["rel-1"]);
  });

  it("U2: fetch 失败 → error 置位 + loading 复位 + 不抛未捕获异常", async () => {
    // 设计依据: 无效等价类—网络失败
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );
    await expect(useGraphStore.getState().loadGraph()).resolves.toBeUndefined();
    const s = useGraphStore.getState();
    expect(s.loading).toBe(false);
    expect(s.error).toBeTruthy();
    expect(s.errorFix).toBeTruthy();
    expect(s.graph.nodes).toEqual([]); // 失败不污染旧数据
  });

  it("U3: 空图 → 空数组而非 undefined（边界值—空集）", async () => {
    // 设计依据: 边界值—数据集空集
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ nodes: [], edges: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    await useGraphStore.getState().loadGraph();
    const { graph, error } = useGraphStore.getState();
    expect(graph.nodes).toEqual([]);
    expect(graph.edges).toEqual([]);
    expect(error).toBeNull();
  });
});
