/**
 * F05 L1：GraphCanvas 单例生命周期测试（U5）。
 * @antv/g6 经 vite.config test.alias 指向测试桩（jsdom 无 canvas），
 * 用 vi.spyOn(Graph.prototype) 拦截并计数；实例经 Graph.instances 断言。
 * 设计依据: frontend/CONSTRAINTS 渲染性能—G6 单例/禁止整图重建（数据变更仅 setData）。
 */

import { cleanup, render } from "@testing-library/react";
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

describe("GraphCanvas（U5 单例生命周期）", () => {
  const renderSpy = vi.spyOn(Graph.prototype, "render");
  const setDataSpy = vi.spyOn(Graph.prototype, "setData");
  const destroySpy = vi.spyOn(Graph.prototype, "destroy");

  beforeEach(() => {
    Graph.instances.length = 0;
    vi.clearAllMocks();
  });
  afterEach(cleanup);

  it("挂载创建恰一个实例并完成首次渲染", () => {
    render(<GraphCanvas graph={DATA_A} />);
    expect(Graph.instances).toHaveLength(1);
    expect(renderSpy).toHaveBeenCalledTimes(1);
    expect(setDataSpy).not.toHaveBeenCalled(); // 初次数据经构造传入，不走增量
  });

  it("数据变更仅增量 setData，不重建实例", () => {
    const { rerender } = render(<GraphCanvas graph={DATA_A} />);
    rerender(<GraphCanvas graph={DATA_B} />);
    expect(Graph.instances).toHaveLength(1);
    expect(setDataSpy).toHaveBeenCalledTimes(1);
    expect(setDataSpy.mock.calls[0]?.[0]).toEqual(DATA_B);
    expect(renderSpy).toHaveBeenCalledTimes(2); // 首次 + 增量后各一次
  });

  it("node:click 事件经回调上抛节点 id", () => {
    const onNodeClick = vi.fn();
    render(<GraphCanvas graph={DATA_A} onNodeClick={onNodeClick} />);
    Graph.instances[0]?.emit("node:click", { target: { id: "char-a" } });
    expect(onNodeClick).toHaveBeenCalledWith("char-a");
  });

  it("卸载销毁实例（防泄漏）", () => {
    const { unmount } = render(<GraphCanvas graph={DATA_A} />);
    unmount();
    expect(destroySpy).toHaveBeenCalledTimes(1);
  });
});
