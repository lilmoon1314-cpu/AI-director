/**
 * 图谱工作台主视图（F05，固定 author 视角）：图画布 + 左侧操作栏 + 详情面板。
 * - 操作栏可整体收起/展开（图区自动占满）；
 * - 「新建」面板手风琴收纳实体/关系两个表单（实体默认展开）；
 * - 深浅色跟随系统（CSS dark: 变体 + G6 主题在 GraphCanvas 内联动）。
 * 挂载即加载图数据；视角切换控件与 perspectiveStore 由 F06 接入。
 */

import { useEffect, useState } from "react";

import { CreateEntityForm } from "../components/entity-panel/CreateEntityForm";
import { CreateRelationForm } from "../components/entity-panel/CreateRelationForm";
import { EntityPanel } from "../components/entity-panel/EntityPanel";
import { GraphCanvas } from "../components/graph/GraphCanvas";
import { Button } from "../components/ui/Button";
import { GlassPanel } from "../components/ui/GlassPanel";
import { useGraphStore } from "../stores/graphStore";
import { useSelectionStore } from "../stores/selectionStore";

function AccordionSection({
  title,
  open,
  onToggle,
  children,
}: {
  title: string;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div>
      <button
        type="button"
        aria-expanded={open}
        onClick={onToggle}
        className="flex w-full items-center justify-between rounded-xl px-2 py-1.5 text-sm font-medium text-slate-800 transition-colors duration-150 hover:bg-white/60 dark:text-slate-200 dark:hover:bg-slate-800/60"
      >
        {title}
        <span aria-hidden className="text-xs text-slate-500 dark:text-slate-400">
          {open ? "收起 ▲" : "展开 ▼"}
        </span>
      </button>
      {open ? <div className="mt-2">{children}</div> : null}
    </div>
  );
}

export function Workbench() {
  const graph = useGraphStore((s) => s.graph);
  const loading = useGraphStore((s) => s.loading);
  const error = useGraphStore((s) => s.error);
  const errorFix = useGraphStore((s) => s.errorFix);
  const loadGraph = useGraphStore((s) => s.loadGraph);
  const selectEntity = useSelectionStore((s) => s.selectEntity);

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [openEntityForm, setOpenEntityForm] = useState(true);
  const [openRelationForm, setOpenRelationForm] = useState(false);

  useEffect(() => {
    void loadGraph();
  }, [loadGraph]);

  return (
    <div className="relative flex h-screen w-full gap-6 overflow-hidden bg-slate-100 p-6 dark:bg-slate-950">
      {sidebarOpen ? (
        <GlassPanel className="flex w-80 shrink-0 flex-col gap-4 overflow-y-auto p-4" data-testid="sidebar">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
              影视世界观工作台
            </h1>
            <Button
              variant="ghost"
              onClick={() => setSidebarOpen(false)}
              aria-label="收起操作栏"
              title="收起操作栏"
            >
              ◀
            </Button>
          </div>

          <GlassPanel className="p-3" data-testid="create-panel">
            <h2 className="mb-1 px-2 text-sm font-semibold text-slate-900 dark:text-slate-100">
              新建
            </h2>
            <AccordionSection
              title="实体"
              open={openEntityForm}
              onToggle={() => setOpenEntityForm((v) => !v)}
            >
              <CreateEntityForm />
            </AccordionSection>
            <AccordionSection
              title="关系"
              open={openRelationForm}
              onToggle={() => setOpenRelationForm((v) => !v)}
            >
              <CreateRelationForm />
            </AccordionSection>
          </GlassPanel>
        </GlassPanel>
      ) : (
        <Button
          variant="ghost"
          className="absolute left-6 top-6 z-20"
          onClick={() => setSidebarOpen(true)}
          aria-label="展开操作栏"
          title="展开操作栏"
        >
          ▶ 操作栏
        </Button>
      )}

      <GlassPanel className="relative min-w-0 flex-1 overflow-hidden">
        {error ? (
          <div role="alert" className="m-6 rounded-xl border border-red-200 bg-red-50/80 p-4 text-sm dark:border-red-900 dark:bg-red-950/60">
            <p className="font-medium text-red-700 dark:text-red-400">{error}</p>
            {errorFix ? <p className="mt-1 text-xs text-red-600 dark:text-red-400">修复：{errorFix}</p> : null}
          </div>
        ) : (
          <GraphCanvas graph={graph} onNodeClick={selectEntity} />
        )}
        {loading ? (
          <span data-testid="graph-loading" className="absolute bottom-4 left-4 text-xs text-slate-500 dark:text-slate-400">
            图数据加载中…
          </span>
        ) : null}
        <span
          data-testid="graph-stats"
          className="absolute right-4 bottom-4 rounded-lg bg-white/70 px-3 py-1 text-xs text-slate-600 backdrop-blur dark:bg-slate-800/70 dark:text-slate-300"
        >
          {graph.nodes.length} 节点 · {graph.edges.length} 边（author 视角）
        </span>
      </GlassPanel>

      <EntityPanel />
    </div>
  );
}
