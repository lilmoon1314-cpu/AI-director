/**
 * GraphCanvas：G6 5.x 封装（frontend/CONSTRAINTS.md「渲染性能」）：
 * - 实例单例：仅挂载时创建、卸载时 destroy，数据变更走 setData（禁止整图重建）；
 * - 渲染链串行化：所有 setData/render/后处理经 Promise 链排队执行（E09——异步管线
 *   互相打断会打坏 G6 元素控制器，表现为边不渲染/'draw' of undefined）；每个任务执行前
 *   校验实例存活（StrictMode 双挂载销毁首实例后，排队任务必须静默跳过）；
 * - auto-adapt-label：标签避让（视口空间 + 重叠检测，按度中心性排序显示优先级）；
 * - 布局收敛 → 硬分离：afterlayout 持久监听 + 防抖 600ms 执行 separateOverlaps，
 *   每次数据变更（如视角切换）重跑——力导碰撞是软约束会残余重叠，重叠又触发标签避让
 *   隐藏节点名（E09：分离监听器曾首跑后自注销，切换视角后不再生效）；
 * - hover-activate：悬停高亮一跳邻域（active）+ 无关元素淡出（inactiveState），
 *   持续选中期间经 enable 门控整体禁用（选中视图不被悬停扰动）；
 * - 点击：该节点及其邻接边/对端节点持续高亮（selected），其余淡出（inactive），
 *   再次点击取消——状态全量批量写回（实时读 graph 数据，不闭包 props 首帧空数据）；
 * - 类型筛选：hideElement/showElement 增量显隐（不触发重布局），边随双端可见性联动；
 * - 节点/边颜色由数据驱动（palette.ts：类型色 / 边随非人端淡化）；
 * - 动画：状态过渡与显隐淡入淡出（element.animation show/hide/enter 阶段 + API animation 参数）；
 * - 深浅色跟随系统：matchMedia 监听 → graph.setTheme 切换 G6 内置主题。
 */

import { Graph } from "@antv/g6";
import { useEffect, useRef } from "react";

import type { G6GraphData } from "../../lib/toGraphData";

interface GraphCanvasProps {
  graph: G6GraphData;
  /** 画布上可见的实体类型集合（类型筛选；不在集合内的类型其节点与关联边隐藏） */
  visibleTypes: Set<string>;
  onNodeClick?: (id: string) => void;
}

/** 节点最小中心间距（画布单位）：节点直径 + 标签 + autoFit 缩放余量，低于即硬性推开。 */
const MIN_NODE_DISTANCE = 120;

/** 硬分离重叠节点对：多轮推开直至无重叠（实时取节点数据——闭包首帧是空图，勿传）。 */
function separateOverlaps(graph: Graph): void {
  if (graph.destroyed) return;
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
  void graph.translateElementTo(target, false);
}

function prefersDark(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  );
}

/** 全量重算类型筛选下的隐藏元素集合（节点按类型；边随双端可见性——防端点不可见的悬空边）。 */
function hiddenTargets(graph: Graph, visibleTypes: Set<string>): Set<string> {
  const hidden = new Set<string>();
  const visibleNodes = new Set<string>();
  for (const n of graph.getNodeData()) {
    const type = (n.data as { type?: string }).type;
    if (visibleTypes.has(type ?? "")) visibleNodes.add(String(n.id));
    else hidden.add(String(n.id));
  }
  for (const e of graph.getEdgeData()) {
    const source = String(e.source);
    const target = String(e.target);
    if (!visibleNodes.has(source) || !visibleNodes.has(target)) hidden.add(String(e.id));
  }
  return hidden;
}

/** 点击持续高亮全量状态机：选中节点+一跳邻域（selected），其余淡出（inactive）；null = 全部复位。
 *  状态从 graph 实时数据推导（getNodeData/getEdgeData），不闭包 props——数据异步加载后点击才生效（E08）。 */
function applySelection(graph: Graph, selectedId: string | null, animation: boolean): void {
  if (graph.destroyed) return;
  const states: Record<string, string[]> = {};
  const nodes = graph.getNodeData();
  // G6 的边端点/id 是 string|number 联合，统一归一化为 string 参与集合运算
  const edges = graph.getEdgeData().map((e) => ({
    id: String(e.id),
    source: String(e.source),
    target: String(e.target),
  }));
  if (!selectedId) {
    for (const n of nodes) states[String(n.id)] = [];
    for (const e of edges) states[e.id] = [];
  } else {
    const incidentIds = new Set(
      edges.filter((e) => e.source === selectedId || e.target === selectedId).map((e) => e.id),
    );
    const neighbors = new Set(
      edges.filter((e) => incidentIds.has(e.id)).flatMap((e) => [e.source, e.target]),
    );
    for (const n of nodes) {
      const id = String(n.id);
      states[id] = id === selectedId || neighbors.has(id) ? ["selected"] : ["inactive"];
    }
    for (const e of edges) states[e.id] = incidentIds.has(e.id) ? ["selected"] : ["inactive"];
  }
  void graph.setElementState(states, animation);
}

export function GraphCanvas({ graph: graphData, visibleTypes, onNodeClick }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  // 点击回调经 ref 最新化：G6 监听只在挂载时注册一次，不随 props 重建
  const onNodeClickRef = useRef(onNodeClick);
  onNodeClickRef.current = onNodeClick;
  // 筛选集合经 ref 最新化：渲染链任务里读当前筛选而非闭包首帧值
  const visibleTypesRef = useRef(visibleTypes);
  visibleTypesRef.current = visibleTypes;
  // 点击持续高亮的节点 id（null = 无持续高亮）
  const selectedRef = useRef<string | null>(null);
  // 上一次筛选的隐藏集合（增量显隐的 diff 基准；null = 尚未初始化）
  const prevHiddenRef = useRef<Set<string> | null>(null);
  // 布局收敛检测定时器（防抖后执行硬分离）
  const settleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 渲染链：setData/render/后处理严格串行（E09——并行打断会打坏 G6 元素控制器）
  const chainRef = useRef<Promise<void>>(Promise.resolve());
  // matchMedia 清理函数经 ref 传递（挂载 effect 的 cleanup 双路径）
  const cleanupRef = useRef<(() => void) | null>(null);

  const scheduleSettle = (graph: Graph): void => {
    if (settleTimerRef.current) clearTimeout(settleTimerRef.current);
    settleTimerRef.current = setTimeout(() => {
      settleTimerRef.current = null;
      if (graphRef.current !== graph || graph.destroyed) return;
      separateOverlaps(graph);
    }, 600);
  };

  /** 渲染链入队：任务执行前校验实例仍存活且仍是当前实例（防销毁后操作，E09）。 */
  const runExclusive = (task: (graph: Graph) => Promise<void>): void => {
    const graph = graphRef.current;
    if (!graph) return;
    chainRef.current = chainRef.current
      .then(() => {
        if (graphRef.current !== graph || graph.destroyed) return;
        return task(graph);
      })
      .catch((cause) => {
        if (import.meta.env.DEV) console.warn("[GraphCanvas] 渲染链任务异常", cause);
      });
  };

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
        // 布局不动画：同步算完直接出最终位置——硬分离在渲染完成后 0.6s 执行，
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
        // 动画阶段：进场淡入 + 筛选显隐淡入淡出（位置动画仍禁用，只有透明度）
        animation: {
          enter: [{ fields: ["opacity"], duration: 400, easing: "ease" }],
          show: [{ fields: ["opacity"], duration: 260, easing: "ease" }],
          hide: [{ fields: ["opacity"], duration: 220, easing: "ease" }],
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
        animation: {
          enter: [{ fields: ["opacity"], duration: 400, easing: "ease" }],
          show: [{ fields: ["opacity"], duration: 260, easing: "ease" }],
          hide: [{ fields: ["opacity"], duration: 220, easing: "ease" }],
        },
      },
      behaviors: [
        "zoom-canvas",
        "drag-canvas",
        "drag-element",
        "auto-adapt-label",
        // 悬停高亮一跳邻域（active）+ 无关元素淡出（inactiveState——缺省不配置时
        // 非邻接元素保持常态，淡出不会生效）；animation:true 状态过渡平滑；
        // enable 门控：存在点击持续选中时整体禁用悬停（选中视图不被悬停扰动）
        {
          type: "hover-activate",
          degree: 1,
          direction: "both",
          inactiveState: "inactive",
          animation: true,
          enable: () => selectedRef.current === null,
        },
      ],
    });
    graphRef.current = graph;

    // 布局收敛 → 硬分离（持久监听 + 防抖；每次数据变更/重布局后都重新调度——
    // 力导碰撞是软约束仍可能残余重叠，重叠会触发标签避让隐藏节点名）
    graph.on("afterlayout", () => scheduleSettle(graph));

    // dev 验收后门：e2e 经其读取节点画布坐标与元素状态（getViewportByCanvas 换算后 hover/click）；
    // 仅开发环境挂载，生产构建不暴露
    if (import.meta.env.DEV) {
      (window as unknown as { __g6graph?: Graph }).__g6graph = graph;
    }

    graph.on("node:click", (evt) => {
      const id = (evt as unknown as { target?: { id?: string } }).target?.id;
      if (!id || graph.destroyed) return;
      // toggle：同节点再点取消；状态推导用 graph 实时数据（E08：闭包首帧空数据曾致高亮全失效）
      selectedRef.current = selectedRef.current === id ? null : id;
      applySelection(graph, selectedRef.current, true);
      onNodeClickRef.current?.(id);
    });

    // 深浅色跟随系统：系统切换主题时热更新 G6 主题（jsdom 无 matchMedia，防御跳过）
    if (typeof window.matchMedia === "function") {
      const media = window.matchMedia("(prefers-color-scheme: dark)");
      const onSchemeChange = (e: MediaQueryListEvent) => {
        void graphRef.current?.setTheme(e.matches ? "dark" : "light");
      };
      media.addEventListener("change", onSchemeChange);
      cleanupRef.current = () => media.removeEventListener("change", onSchemeChange);
    }

    // 首次渲染走渲染链（与后续数据变更串行）
    runExclusive(async (g) => {
      await g.render();
      scheduleSettle(g);
    });

    return () => {
      cleanupRef.current?.();
      if (settleTimerRef.current) clearTimeout(settleTimerRef.current);
      chainRef.current = Promise.resolve(); // 丢弃排队任务（任务内有存活守卫，双保险）
      graph.destroy();
      graphRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 单例：仅挂载/卸载执行；初始数据为闭包首帧值
  }, []);

  // 数据变更 → 渲染链排队：setData + render + 按当前筛选全量重挂 + 重新调度硬分离
  const lastDataRef = useRef(graphData);
  useEffect(() => {
    if (lastDataRef.current === graphData) return;
    lastDataRef.current = graphData;
    runExclusive(async (graph) => {
      selectedRef.current = null;
      graph.setData(graphData);
      await graph.render();
      // render 重建全部元素，显隐复位——按当前筛选全量重挂（动画关闭：与进场动画叠加会闪烁）
      const hidden = hiddenTargets(graph, visibleTypesRef.current);
      prevHiddenRef.current = hidden;
      if (hidden.size > 0) await graph.hideElement([...hidden], false);
      scheduleSettle(graph);
    });
  }, [graphData]);

  // 类型筛选变更 → 渲染链排队：增量显隐（hide/show 不触发重布局，画布其余元素位置稳定）
  useEffect(() => {
    if (prevHiddenRef.current === null) {
      // 挂载首跑：仅记录基准（数据渲染链完成后负责首次全量应用）
      const graph = graphRef.current;
      prevHiddenRef.current = graph ? hiddenTargets(graph, visibleTypes) : new Set();
      return;
    }
    runExclusive(async (graph) => {
      const target = hiddenTargets(graph, visibleTypes);
      const prev = prevHiddenRef.current ?? new Set();
      const toHide = [...target].filter((id) => !prev.has(id));
      const toShow = [...prev].filter((id) => !target.has(id));
      prevHiddenRef.current = target;
      if (toShow.length > 0) await graph.showElement(toShow, true);
      if (toHide.length > 0) await graph.hideElement(toHide, true);
      // 重放持续选中态：重新显示的元素不应携带隐藏前的旧状态
      if (selectedRef.current) applySelection(graph, selectedRef.current, false);
    });
  }, [visibleTypes]);

  return <div ref={containerRef} data-testid="graph-canvas" className="h-full w-full" />;
}
