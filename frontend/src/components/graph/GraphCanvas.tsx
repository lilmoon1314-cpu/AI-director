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

/** 节点最小中心间距（画布单位）：节点直径 + 标签 + autoFit 缩放余量，低于即硬性推开。 */
const MIN_NODE_DISTANCE = 120;

/** 硬分离重叠节点对：多轮推开直至无重叠（实时取节点数据——闭包首帧是空图，勿传）。 */
function separateOverlaps(graph: Graph): void {
  const MIN_DIST_SQ = MIN_NODE_DISTANCE * MIN_NODE_DISTANCE;
  const nodes = graph.getNodeData();
  const positions = new Map<string, number[]>(
    nodes.map((n) => [n.id, Array.from(graph.getElementPosition(n.id).slice(0, 2))] as const),
  );
  for (let iter = 0; iter < 4; iter++) {
    let moved = false;
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = positions.get(nodes[i].id);
        const b = positions.get(nodes[j].id);
        if (!a || !b) continue;
        const dx = b[0] - a[0];
        const dy = b[1] - a[1];
        const distSq = dx * dx + dy * dy;
        if (distSq >= MIN_DIST_SQ) continue;
        const dist = Math.sqrt(distSq);
        if (dist < 0.5) {
          // 完全重合：沿固定方向拆开
          a[0] -= MIN_NODE_DISTANCE / 2;
          b[0] += MIN_NODE_DISTANCE / 2;
        } else {
          const push = (MIN_NODE_DISTANCE - dist) / 2;
          const ux = dx / dist;
          const uy = dy / dist;
          a[0] -= ux * push;
          a[1] -= uy * push;
          b[0] += ux * push;
          b[1] += uy * push;
        }
        moved = true;
      }
    }
    if (!moved) break;
  }
  if (import.meta.env.DEV) {
    console.log("[separateOverlaps] 节点数", nodes.length, "已写回平移");
  }
  // translateElementTo 是官方元素平移 API（updateNodeData+draw 在布局模拟后会被覆盖失效）
  const target: Record<string, Float32Array> = {};
  for (const n of nodes) {
    const p = positions.get(n.id);
    if (p) target[n.id] = new Float32Array([p[0], p[1], 0]);
  }
  graph.translateElementTo(target, false);
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
  // 布局收敛检测定时器（afterlayout 去抖后执行硬分离）
  const settleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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
        // 布局不动画：同步算完直接出最终位置——硬分离在 render 后 0.6s 执行，
        // 若开动画，模拟 tick 会持续覆盖分离结果（曾致节点仍重叠）
        animation: false,
        linkDistance: 220,
        nodeStrength: -800,
        // 防重叠的正确开关：碰撞半径由 nodeSize+nodeSpacing 推导
        // （传 collide: <数字> 不会生效——radius 会回退为默认 nodeSize 10 的一半，
        //   远小于实际节点光圈，导致重叠，见 2026-08-28 视觉返工）
        preventOverlap: true,
        nodeSize: 46,
        nodeSpacing: 24,
        collideStrength: 1,
        collideIterations: 6,
      },
      node: {
        style: {
          size: 13,
          fill: (d: { data?: { color?: string } }) => d.data?.color ?? "#97a7b3",
          stroke: (d: { data?: { color?: string } }) => d.data?.color ?? "#97a7b3",
          strokeOpacity: 0.6,
          lineWidth: 2,
          fillOpacity: 0.88,
          labelText: (d: { data?: { name?: string } }) => d.data?.name ?? "",
        },
        state: {
          // 高亮 = 在原样式上提高透明度（不叠色、不加粗、不改字重）；
          // halo:false 显式关闭——G6 5 内置主题会给 active/selected 默认叠加光晕
          active: { size: 16, fillOpacity: 1, strokeOpacity: 1, labelOpacity: 1, halo: false },
          selected: { size: 16, fillOpacity: 1, strokeOpacity: 1, labelOpacity: 1, halo: false },
          inactive: { fillOpacity: 0.5, strokeOpacity: 0.42, labelOpacity: 0.4, halo: false },
        },
      },
      edge: {
        style: {
          stroke: (d: { data?: { stroke?: string } }) => d.data?.stroke ?? "#94a3b8",
          opacity: (d: { data?: { opacity?: number } }) => d.data?.opacity ?? 0.22,
          endArrow: true,
          labelText: (d: { data?: { type?: string } }) => d.data?.type ?? "",
          // 多边场景边标签默认隐藏（喧宾夺主），悬停/选中高亮时经 state 显示
          labelOpacity: 0,
        },
        state: {
          active: { opacity: 0.7, labelOpacity: 1 },
          selected: { opacity: 0.7, labelOpacity: 1 },
          inactive: { opacity: 0.1, labelOpacity: 0 },
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

    // 布局停止后执行一次硬分离：力导碰撞力是软约束仍可能残余重叠，
    // 这里按最小间距把过近节点对沿连线推开（O(n²) 每轮毫秒级，200 节点无感）
    const onAfterLayout = () => {
      if (settleTimerRef.current) clearTimeout(settleTimerRef.current);
      settleTimerRef.current = setTimeout(() => {
        graph.off("afterlayout", onAfterLayout);
        separateOverlaps(graph);
      }, 600);
    };
    graph.on("afterlayout", onAfterLayout);
    // 兜底：afterlayout 事件时序不确定，布局动画常规时长内再固定触发一次
    setTimeout(() => {
      graph.emit("afterlayout");
    }, 9000);

    // dev 验收后门：e2e 经其读取节点画布坐标（getViewportByCanvas 换算后 hover/click）；
    // 仅开发环境挂载，生产构建不暴露
    if (import.meta.env.DEV) {
      (window as unknown as { __g6graph?: Graph }).__g6graph = graph;
    }

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
      graph.off("afterlayout", onAfterLayout);
      if (settleTimerRef.current) clearTimeout(settleTimerRef.current);
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
