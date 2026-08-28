/**
 * @antv/g6 测试桩（jsdom 无 canvas）：仅保留前端用到的方法面。
 * 经 vite.config test.alias 在测试环境替换真实依赖（构建不受影响）。
 * - graphInstances：记录已创建实例（断言单例约束）；
 * - emit：测试手动触发事件（如 node:click），验证回调链路；
 * - 方法均为普通方法，测试内可 vi.spyOn(Graph.prototype, "setData") 拦截。
 */

export class Graph {
  static instances: Graph[] = [];

  private listeners = new Map<string, (evt: unknown) => void>();

  constructor(public options: unknown) {
    Graph.instances.push(this);
  }

  on(event: string, callback: (evt: unknown) => void) {
    this.listeners.set(event, callback);
  }

  off() {}

  emit(event: string, evt: unknown) {
    this.listeners.get(event)?.(evt);
  }

  setElementState() {}

  async render(): Promise<undefined> {
    return undefined;
  }

  setData() {}

  destroy() {}
}
