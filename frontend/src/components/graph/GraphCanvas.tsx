/**
 * GraphCanvas：G6 5.x 封装（frontend/CONSTRAINTS.md「渲染性能」）：
 * - 实例单例：仅挂载时创建、卸载时 destroy，数据变更走 setData（禁止整图重建）；
 * - 高频交互（缩放/拖拽）交由 G6 behaviors，状态不进全局 store；
 * - 节点点击经回调上抛（onNodeClick），由调用方决定选中语义。
 */

import { Graph } from "@antv/g6";
import { useEffect, useRef } from "react";

import type { G6GraphData } from "../../lib/toGraphData";

interface GraphCanvasProps {
  graph: G6GraphData;
  onNodeClick?: (id: string) => void;
}

export function GraphCanvas({ graph: graphData, onNodeClick }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  // 点击回调经 ref 最新化：G6 监听只在挂载时注册一次，不随 props 重建
  const onNodeClickRef = useRef(onNodeClick);
  onNodeClickRef.current = onNodeClick;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const graph = new Graph({
      container,
      data: graphData,
      layout: { type: "force", linkDistance: 140, nodeStrength: -300, collide: 30 },
      node: {
        style: {
          size: 28,
          fill: "#475569",
          labelText: (d: { data?: { name?: string } }) => d.data?.name ?? "",
          labelFill: "#1e293b",
          labelBackground: true,
          labelBackgroundFill: "rgba(255,255,255,0.85)",
          labelPadding: [1, 4],
        },
      },
      edge: {
        style: {
          stroke: "#94a3b8",
          endArrow: true,
          labelText: (d: { data?: { type?: string } }) => d.data?.type ?? "",
          labelFill: "#475569",
        },
      },
      behaviors: ["zoom-canvas", "drag-canvas", "drag-element"],
    });
    graphRef.current = graph;
    void graph.render();

    graph.on("node:click", (evt) => {
      const id = (evt as unknown as { target?: { id?: string } }).target?.id;
      if (id) onNodeClickRef.current?.(id);
    });

    return () => {
      graph.destroy();
      graphRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 单例：仅挂载/卸载执行；初始数据为闭包首帧值
  }, []);

  // 数据变更 → 增量更新（G6 数据 API），不重建实例；首帧数据已随构造传入，跳过
  const lastDataRef = useRef(graphData);
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph || lastDataRef.current === graphData) return;
    lastDataRef.current = graphData;
    graph.setData(graphData);
    void graph.render();
  }, [graphData]);

  return <div ref={containerRef} data-testid="graph-canvas" className="h-full w-full" />;
}
