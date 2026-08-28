/**
 * 图谱工作台主视图（F05，固定 author 视角）：图画布 + 左侧创建表单栏 + 详情面板。
 * 挂载即加载图数据；视角切换控件与 perspectiveStore 由 F06 接入。
 */

import { useEffect } from "react";

import { CreateEntityForm } from "../components/entity-panel/CreateEntityForm";
import { CreateRelationForm } from "../components/entity-panel/CreateRelationForm";
import { EntityPanel } from "../components/entity-panel/EntityPanel";
import { GraphCanvas } from "../components/graph/GraphCanvas";
import { GlassPanel } from "../components/ui/GlassPanel";
import { useGraphStore } from "../stores/graphStore";
import { useSelectionStore } from "../stores/selectionStore";

export function Workbench() {
  const graph = useGraphStore((s) => s.graph);
  const loading = useGraphStore((s) => s.loading);
  const error = useGraphStore((s) => s.error);
  const errorFix = useGraphStore((s) => s.errorFix);
  const loadGraph = useGraphStore((s) => s.loadGraph);
  const selectEntity = useSelectionStore((s) => s.selectEntity);

  useEffect(() => {
    void loadGraph();
  }, [loadGraph]);

  return (
    <div className="relative h-screen w-full overflow-hidden bg-slate-100 p-6">
      <div className="flex h-full gap-6">
        <GlassPanel className="flex w-80 shrink-0 flex-col gap-5 overflow-y-auto p-5">
          <h1 className="text-xl font-semibold tracking-tight text-slate-900">
            影视世界观工作台
          </h1>
          <CreateEntityForm />
          <CreateRelationForm />
        </GlassPanel>

        <GlassPanel className="relative min-w-0 flex-1 overflow-hidden">
          {error ? (
            <div role="alert" className="m-6 rounded-xl border border-red-200 bg-red-50/80 p-4 text-sm">
              <p className="font-medium text-red-700">{error}</p>
              {errorFix ? <p className="mt-1 text-xs text-red-600">修复：{errorFix}</p> : null}
            </div>
          ) : (
            <GraphCanvas graph={graph} onNodeClick={selectEntity} />
          )}
          {loading ? (
            <span data-testid="graph-loading" className="absolute bottom-4 left-4 text-xs text-slate-500">
              图数据加载中…
            </span>
          ) : null}
          <span
            data-testid="graph-stats"
            className="absolute bottom-4 right-4 rounded-lg bg-white/70 px-3 py-1 text-xs text-slate-600 backdrop-blur"
          >
            {graph.nodes.length} 节点 · {graph.edges.length} 边（author 视角）
          </span>
        </GlassPanel>
      </div>

      <EntityPanel />
    </div>
  );
}
