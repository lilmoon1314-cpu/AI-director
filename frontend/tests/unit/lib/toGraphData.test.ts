/**
 * F05 L1：toGraphData 映射测试（U3，参数化）。
 * 设计依据: 等价类—映射有效（实体/关系）；边界值—空集、aliases 保序。
 */

import { describe, expect, it } from "vitest";

import type { GraphData } from "../../../src/api/client";
import { toGraphData } from "../../../src/lib/toGraphData";

describe("toGraphData（U3）", () => {
  it("实体与关系字段一一对应映射到 G6 data 结构（含数据驱动配色）", () => {
    const input: GraphData = {
      nodes: [
        { id: "char-a", type: "character", name: "周兰", aliases: ["兰姐", "阿兰"] },
        { id: "loc-l", type: "location", name: "青云山", aliases: [] },
      ],
      edges: [{ id: "rel-2", source: "char-a", target: "loc-l", type: "LIVES_IN" }],
    };
    const out = toGraphData(input);
    expect(out.nodes).toHaveLength(2);
    expect(out.nodes[0].id).toBe("char-a");
    expect(out.nodes[0].data.name).toBe("周兰");
    expect(out.nodes[0].data.aliases).toEqual(["兰姐", "阿兰"]);
    expect(out.nodes[0].data.aliases).not.toBe(input.nodes[0].aliases); // 拷贝而非引用
    expect(out.nodes[0].data.color).toBe("#ff5a7d"); // character 粉红
    expect(out.nodes[1].data.color).toBe("#40531b"); // location 暗绿
    expect(out.edges[0].id).toBe("rel-2");
    expect(out.edges[0].source).toBe("char-a");
    expect(out.edges[0].target).toBe("loc-l");
    expect(out.edges[0].data.type).toBe("LIVES_IN");
    expect(out.edges[0].data.stroke).toBe("#40531b"); // 人—地：随非人端（地点绿）
    expect(out.edges[0].data.opacity).toBe(0.22); // 边透明度减半
  });

  it.each([
    ["nodes 缺省", { edges: [{ id: "rel-1", source: "a", target: "b", type: "ALLY" }] }, 0, 1],
    ["edges 缺省", { nodes: [{ id: "a", type: "item", name: "镜", aliases: [] }] }, 1, 0],
    ["全空", {}, 0, 0],
  ])("%s → 对应集合空数组（边界值—空集）", (_name, input, nodeCount, edgeCount) => {
    const out = toGraphData(input as GraphData);
    expect(out.nodes).toHaveLength(nodeCount);
    expect(out.edges).toHaveLength(edgeCount);
  });
});
