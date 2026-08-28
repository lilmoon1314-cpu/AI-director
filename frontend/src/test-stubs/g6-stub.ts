/**
 * @antv/g6 测试桩（jsdom 无 canvas）：仅保留前端用到的方法面。
 * 经 vite.config test.alias 在测试环境替换真实依赖（构建不受影响）。
 * - graphInstances：记录已创建实例（断言单例约束）；
 * - emit：测试手动触发事件（如 node:click），验证回调链路；
 * - setData 存数据供 getNodeData/getEdgeData 读取（筛选/点击状态推导依赖实时数据）；
 * - hiddenIds/shownIds/lastStateBatch：记录显隐与状态调用（筛选/高亮链路断言）；
 * - 方法均为普通方法，测试内可 vi.spyOn(Graph.prototype, "setData") 拦截。
 */

interface StubNode {
  id: string;
  data: Record<string, unknown>;
}

interface StubEdge {
  id: string;
  source: string;
  target: string;
  data: Record<string, unknown>;
}

export class Graph {
  static instances: Graph[] = [];

  private listeners = new Map<string, (evt: unknown) => void>();
  private nodes: StubNode[] = [];
  private edges: StubEdge[] = [];

  /** hideElement/showElement 的调用累计（筛选链路断言用） */
  hiddenIds: string[] = [];
  shownIds: string[] = [];
  /** 最近一次批量 setElementState 的入参（点击高亮断言用） */
  lastStateBatch: Record<string, string[]> | null = null;

  constructor(public options: unknown) {
    const data = (options as { data?: { nodes?: StubNode[]; edges?: StubEdge[] } }).data;
    this.nodes = data?.nodes ? data.nodes.map((n) => ({ ...n })) : [];
    this.edges = data?.edges ? data.edges.map((e) => ({ ...e })) : [];
    Graph.instances.push(this);
  }

  on(event: string, callback: (evt: unknown) => void) {
    this.listeners.set(event, callback);
  }

  off() {}

  emit(event: string, evt: unknown) {
    this.listeners.get(event)?.(evt);
  }

  getNodeData(): StubNode[] {
    return this.nodes;
  }

  getEdgeData(): StubEdge[] {
    return this.edges;
  }

  setData(data: { nodes?: StubNode[]; edges?: StubEdge[] }) {
    this.nodes = data.nodes ? data.nodes.map((n) => ({ ...n })) : [];
    this.edges = data.edges ? data.edges.map((e) => ({ ...e })) : [];
  }

  setElementState(states: Record<string, string[]>) {
    this.lastStateBatch = states;
  }

  hideElement(ids: string[]) {
    this.hiddenIds.push(...ids);
  }

  showElement(ids: string[]) {
    this.shownIds.push(...ids);
  }

  async render(): Promise<undefined> {
    return undefined;
  }

  destroy() {}
}
