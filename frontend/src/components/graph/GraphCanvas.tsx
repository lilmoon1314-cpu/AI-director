/**
 * GraphCanvas：G6 5.x 封装（frontend/CONSTRAINTS.md「渲染性能」）：
 * - 实例单例：仅挂载时创建、卸载时 destroy，数据变更走 setData（禁止整图重建）；
 * - auto-adapt-label：标签避让（视口空间 + 重叠检测，按度中心性排序显示优先级）；
 * - hover-activate：悬停高亮一跳邻域（active），非邻接淡出（inactive）；
 * - 点击：该节点及其邻接边/对端节点持续高亮（selected），再次点击取消恢复；
 * - 节点/边颜色由数据驱动（palette.ts：类型色 / 边随非人端淡化）；
 * - 深浅色跟随系统：matchMedia 监听 → graph.setTheme 切换 G6 内置主题；
 * - 高频交互（缩放/拖拽）交由 G6 behaviors，状态不进全局 store。
 */

import { Graph } from "@antv/g6";
import { useEffect, useRef, type MutableRefObject } from "react";

import type { G6GraphData } from "../../lib/toGraphData";

interface GraphCanvasProps {
  graph: G6GraphData;
  onNodeClick?: (id: string) => void;
}

function prefersDark(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  );
}

export function GraphCanvas({ graph: graphData, onNodeClick }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  // 点击回调经 ref 最新化：G6 监听只在挂载时注册一次，不随 props 重建
  const onNodeClickRef = useRef(onNodeClick);
  onNodeClickRef.current = onNodeClick;
  // 点击持续高亮的节点 id（null = 无持续高亮）
  const highlightedRef = useRef<string | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const graph = new Graph({
      container,
      data: graphData,
      theme: prefersDark() ? "dark" : "light",
      autoFit: "view",
      padding: 40,
      layout: {
        type: "force",
        linkDistance: 180,
        nodeStrength: -400,
        collide: 60, // 节点碰撞半径：配合标签避让减少拥挤
      },
      node: {
        style: {
          size: 28,
          fill: (d: { data?: { color?: string } }) => d.data?.color ?? "#8a94a6",
          labelText: (d: { data?: { name?: string } }) => d.data?.name ?? "",
        },
        state: {
          active: { lineWidth: 3, stroke: "#f59e0b", labelFontWeight: 600 },
          selected: { lineWidth: 3, stroke: "#f59e0b", labelFontWeight: 600 },
          inactive: { fillOpacity: 0.25, strokeOpacity: 0.2, labelOpacity: 0.2 },
        },
      },
      edge: {
        style: {
          stroke: (d: { data?: { stroke?: string } }) => d.data?.stroke ?? "#94a3b8",
          opacity: (d: { data?: { opacity?: number } }) => d.data?.opacity ?? 0.45,
          endArrow: true,
          labelText: (d: { data?: { type?: string } }) => d.data?.type ?? "",
        },
        state: {
          active: { opacity: 0.95, lineWidth: 2.5, labelOpacity: 1 },
          selected: { opacity: 0.95, lineWidth: 2.5, labelOpacity: 1 },
          inactive: { opacity: 0.08, labelOpacity: 0 },
        },
      },
      behaviors: [
        "zoom-canvas",
        "drag-canvas",
        "drag-element",
        "auto-adapt-label",
        // 悬停高亮一跳邻域；非邻接淡出（G6 内置，状态见上方 node/edge.state）
        { type: "hover-activate", degree: 1, direction: "both" },
      ],
    });
    graphRef.current = graph;
    void graph.render();

    graph.on("node:click", (evt) => {
      const id = (evt as unknown as { target?: { id?: string } }).target?.id;
      if (!id) return;
      toggleHighlight(graph, graphData, id, highlightedRef);
      onNodeClickRef.current?.(id);
    });

    // 深浅色跟随系统：系统切换主题时热更新 G6 主题（jsdom 无 matchMedia，防御跳过）
    if (typeof window.matchMedia === "function") {
      const media = window.matchMedia("(prefers-color-scheme: dark)");
      const onSchemeChange = (e: MediaQueryListEvent) => {
        void graphRef.current?.setTheme(e.matches ? "dark" : "light");
      };
      media.addEventListener("change", onSchemeChange);
      return () => {
        media.removeEventListener("change", onSchemeChange);
        graph.destroy();
        graphRef.current = null;
      };
    }

    return () => {
      graph.destroy();
      graphRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 单例：仅挂载/卸载执行；初始数据为闭包首帧值
  }, []);

  // 数据变更 → 增量更新（G6 数据 API），不重建实例；重置点击高亮（图已换）
  const lastDataRef = useRef(graphData);
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph || lastDataRef.current === graphData) return;
    lastDataRef.current = graphData;
    highlightedRef.current = null;
    graph.setData(graphData);
    void graph.render();
  }, [graphData]);

  return <div ref={containerRef} data-testid="graph-canvas" className="h-full w-full" />;
}

/** 点击 toggle：选中该节点及其邻接边/对端节点（selected），其余淡出（inactive）；再点同节点取消。 */
function toggleHighlight(
  graph: Graph,
  graphData: G6GraphData,
  nodeId: string,
  highlightedRef: MutableRefObject<string | null>,
): void {
  if (highlightedRef.current === nodeId) {
    // 取消：全部恢复常态
    for (const n of graphData.nodes) void graph.setElementState(n.id, []);
    for (const e of graphData.edges) void graph.setElementState(e.id, []);
    highlightedRef.current = null;
    return;
  }
  // 先清除上一轮
  if (highlightedRef.current) {
    const prev = highlightedRef.current;
    void graph.setElementState(prev, []);
    for (const e of graphData.edges) {
      if (e.source === prev || e.target === prev) void graph.setElementState(e.id, []);
    }
  }
  const incidentEdges = graphData.edges.filter(
    (e) => e.source === nodeId || e.target === nodeId,
  );
  const neighbors = new Set(incidentEdges.flatMap((e) => [e.source, e.target]));
  for (const n of graphData.nodes) {
    void graph.setElementState(n.id, n.id === nodeId || neighbors.has(n.id) ? ["selected"] : ["inactive"]);
  }
  for (const e of graphData.edges) {
    void graph.setElementState(e.id, incidentEdges.includes(e) ? ["selected"] : ["inactive"]);
  }
  highlightedRef.current = nodeId;
}
