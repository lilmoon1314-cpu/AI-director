/**
 * API GraphData → G6 5.x 数据格式映射（字段一一对应；G6 5 将业务数据置于 data 字段）。
 */

import type { GraphData } from "../api/client";

export interface G6Node {
  // G6 5.x NodeData 带字符串索引签名，这里保持一致以直接兼容 Graph.setData
  [key: string]: unknown;
  id: string;
  data: { type: string; name: string; aliases: string[] };
}

export interface G6Edge {
  [key: string]: unknown;
  id: string;
  source: string;
  target: string;
  data: { type: string };
}

export interface G6GraphData {
  nodes: G6Node[];
  edges: G6Edge[];
}

export function toGraphData(graph: GraphData): G6GraphData {
  return {
    nodes: (graph.nodes ?? []).map((n) => ({
      id: n.id,
      data: { type: n.type, name: n.name, aliases: [...n.aliases] },
    })),
    edges: (graph.edges ?? []).map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      data: { type: e.type },
    })),
  };
}
