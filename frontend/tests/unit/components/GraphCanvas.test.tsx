/**
 * F05 L1：GraphCanvas 单例生命周期测试（U5）。
 * @antv/g6 经 vite.config test.alias 指向测试桩（jsdom 无 canvas），
 * 用 vi.spyOn(Graph.prototype) 拦截并计数；实例经 Graph.instances 断言。
 * 设计依据: frontend/CONSTRAINTS 渲染性能—G6 单例/禁止整图重建（数据变更仅 setData）。
 * 交互三轮起渲染经组件内 Promise 链串行（E09）：断言用 waitFor 等微任务排空。
 */

import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Graph } from "../../../src/test-stubs/g6-stub";
import { GraphCanvas } from "../../../src/components/graph/GraphCanvas";
import type { G6GraphData } from "../../../src/lib/toGraphData";

const DATA_A: G6GraphData = {
  nodes: [{ id: "char-a", data: { type: "character", name: "周兰", aliases: [] } }],
  edges: [],
};
const DATA_B: G6GraphData = {
  nodes: [
    { id: "char-a", data: { type: "character", name: "周兰", aliases: [] } },
    { id: "char-b", data: { type: "character", name: "沈墨", aliases: [] } },
  ],
  edges: [{ id: "rel-1", source: "char-a", target: "char-b", data: { type: "ALLY" } }],
};
/** 必填筛选 prop：全类型可见（等价 Workbench 默认全选初值） */
const ALL_TYPES = new Set(["character", "faction", "location", "item", "skill", "event", "concept"]);

describe("GraphCanvas（U5 单例生命周期）", () => {
  const renderSpy = vi.spyOn(Graph.prototype, "render");
  const setDataSpy = vi.spyOn(Graph.prototype, "setData");
  const destroySpy = vi.spyOn(Graph.prototype, "destroy");

  beforeEach(() => {
    Graph.instances.length = 0;
    vi.clearAllMocks();
  });
  afterEach(cleanup);

  it("挂载创建恰一个实例并完成首次渲染（渲染链异步排空后）", async () => {
    render(<GraphCanvas graph={DATA_A} visibleTypes={ALL_TYPES} />);
    expect(Graph.instances).toHaveLength(1);
    await waitFor(() => expect(renderSpy).toHaveBeenCalledTimes(1));
    expect(setDataSpy).not.toHaveBeenCalled(); // 初次数据经构造传入，不走增量
  });

  it("数据变更仅增量 setData，不重建实例（渲染链串行：先挂载渲染后增量）", async () => {
    const { rerender } = render(<GraphCanvas graph={DATA_A} visibleTypes={ALL_TYPES} />);
    rerender(<GraphCanvas graph={DATA_B} visibleTypes={ALL_TYPES} />);
    expect(Graph.instances).toHaveLength(1);
    await waitFor(() => expect(setDataSpy).toHaveBeenCalledTimes(1));
    expect(setDataSpy.mock.calls[0]?.[0]).toEqual(DATA_B);
    await waitFor(() => expect(renderSpy).toHaveBeenCalledTimes(2)); // 首次 + 增量后各一次
  });

  it("卸载后渲染链排队任务静默跳过（E09 存活守卫：不崩、不再触实例）", async () => {
    const { rerender, unmount } = render(<GraphCanvas graph={DATA_A} visibleTypes={ALL_TYPES} />);
    rerender(<GraphCanvas graph={DATA_B} visibleTypes={ALL_TYPES} />);
    unmount(); // 立即卸载：排队的 setData/render 任务应跳过而非操作已销毁实例
    await waitFor(() => expect(destroySpy).toHaveBeenCalledTimes(1));
    expect(Graph.instances).toHaveLength(1); // 不重建
  });

  it("node:click 事件经回调上抛节点 id", () => {
    const onNodeClick = vi.fn();
    render(<GraphCanvas graph={DATA_A} visibleTypes={ALL_TYPES} onNodeClick={onNodeClick} />);
    Graph.instances[0]?.emit("node:click", { target: { id: "char-a" } });
    expect(onNodeClick).toHaveBeenCalledWith("char-a");
  });

  it("卸载销毁实例（防泄漏）", () => {
    const { unmount } = render(<GraphCanvas graph={DATA_A} visibleTypes={ALL_TYPES} />);
    unmount();
    expect(destroySpy).toHaveBeenCalledTimes(1);
  });
});
