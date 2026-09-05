/**
 * 图谱页（F08 起为工作台「图谱」页签内容；原 Workbench 主视图整体迁入）：
 * 图画布 + 左侧操作栏 + 详情面板。
 * - 操作栏可整体收起/展开（图区自动占满）；
 * - 所有内容区块默认折叠：「新建」（实体/关系表单）与「筛选」（实体类型显隐勾选）；
 * - 状态栏计数为画布可见数（筛选后随之减少并标注「已筛选」）；
 * - 深浅色跟随系统（CSS dark: 变体 + G6 主题在 GraphCanvas 内联动）。
 */

import { useEffect, useMemo, useState } from "react";

import { CreateEntityForm } from "../components/entity-panel/CreateEntityForm";
import { CreateRelationForm } from "../components/entity-panel/CreateRelationForm";
import { EntityPanel } from "../components/entity-panel/EntityPanel";
import { GraphCanvas } from "../components/graph/GraphCanvas";
import { PerspectiveSwitcher } from "../components/perspective/PerspectiveSwitcher";
import { Button } from "../components/ui/Button";
import { GlassPanel } from "../components/ui/GlassPanel";
import { ENTITY_TYPES } from "../lib/entityForm";
import { TYPE_COLORS, TYPE_LABELS } from "../lib/palette";
import { useEntityIndexStore } from "../stores/entityIndexStore";
import { useGraphStore } from "../stores/graphStore";
import { PERSPECTIVE_LABELS, usePerspectiveStore } from "../stores/perspectiveStore";
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

export function GraphView() {
  const graph = useGraphStore((s) => s.graph);
  const loading = useGraphStore((s) => s.loading);
  const error = useGraphStore((s) => s.error);
  const errorFix = useGraphStore((s) => s.errorFix);
  const loadGraph = useGraphStore((s) => s.loadGraph);
  const selectEntity = useSelectionStore((s) => s.selectEntity);
  const perspective = usePerspectiveStore((s) => s.perspective);
  const characterId = usePerspectiveStore((s) => s.characterId);
  const characters = usePerspectiveStore((s) => s.characters);
  const loadEntities = useEntityIndexStore((s) => s.load);

  // 实体摘要索引随图数据刷新（实体增删改后 reloadGraph → 索引同步，F07 名称解析保持新鲜）
  useEffect(() => {
    loadEntities(true).catch(() => {});
  }, [graph, loadEntities]);

  const [sidebarOpen, setSidebarOpen] = useState(true);
  // 全部区块默认折叠（用户要求）：新建组、组内实体/关系表单、筛选面板
  const [openCreate, setOpenCreate] = useState(false);
  const [openEntityForm, setOpenEntityForm] = useState(false);
  const [openRelationForm, setOpenRelationForm] = useState(false);
  const [openFilter, setOpenFilter] = useState(false);
  // 类型筛选：勾选 = 画布显示该类型（默认全选）
  const [visibleTypes, setVisibleTypes] = useState<Set<string>>(() => new Set(ENTITY_TYPES));

  useEffect(() => {
    void loadGraph();
  }, [loadGraph]);

  const toggleType = (type: string) => {
    setVisibleTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  // 各类型实体数与画布可见计数（状态栏随筛选联动）
  const countByType = useMemo(() => {
    const counts = new Map<string, number>();
    for (const n of graph.nodes) counts.set(n.data.type, (counts.get(n.data.type) ?? 0) + 1);
    return counts;
  }, [graph.nodes]);

  const visibleNodes = useMemo(
    () => graph.nodes.filter((n) => visibleTypes.has(n.data.type)),
    [graph.nodes, visibleTypes],
  );
  const visibleNodeIds = useMemo(() => new Set(visibleNodes.map((n) => n.id)), [visibleNodes]);
  const visibleEdgeCount = useMemo(
    () =>
      graph.edges.filter((e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target))
        .length,
    [graph.edges, visibleNodeIds],
  );
  const isFiltered = visibleTypes.size < ENTITY_TYPES.length;

  return (
    <div className="relative flex h-full min-w-0 flex-1 gap-4 overflow-hidden">
      {sidebarOpen ? (
        <GlassPanel className="flex w-80 shrink-0 flex-col gap-4 overflow-y-auto p-4" data-testid="sidebar">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-100">
              图谱
            </h2>
            <Button
              variant="ghost"
              onClick={() => setSidebarOpen(false)}
              aria-label="收起操作栏"
              title="收起操作栏"
            >
              ◀
            </Button>
          </div>

          <PerspectiveSwitcher />

          <div className="flex flex-col gap-1" data-testid="create-panel">
            <AccordionSection
              title="新建"
              open={openCreate}
              onToggle={() => setOpenCreate((v) => !v)}
            >
              <div className="flex flex-col gap-1">
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
              </div>
            </AccordionSection>
            <AccordionSection
              title="筛选"
              open={openFilter}
              onToggle={() => setOpenFilter((v) => !v)}
            >
              <div className="flex flex-col gap-1.5 px-2 py-1" data-testid="filter-panel">
                {ENTITY_TYPES.map((type) => {
                  const count = countByType.get(type) ?? 0;
                  return (
                    <label
                      key={type}
                      className="flex cursor-pointer items-center gap-2 text-sm text-slate-700 dark:text-slate-300"
                    >
                      <input
                        type="checkbox"
                        checked={visibleTypes.has(type)}
                        onChange={() => toggleType(type)}
                        aria-label={`${TYPE_LABELS[type]} (${count})`}
                        data-testid={`filter-${type}`}
                        className="h-3.5 w-3.5 accent-slate-700 dark:accent-slate-300"
                      />
                      <span
                        aria-hidden
                        className="h-2.5 w-2.5 rounded-full ring-1 ring-black/10 dark:ring-white/20"
                        style={{ backgroundColor: TYPE_COLORS[type] }}
                      />
                      <span>{TYPE_LABELS[type]}</span>
                      <span className="ml-auto text-xs text-slate-500 dark:text-slate-400">
                        {count}
                      </span>
                    </label>
                  );
                })}
              </div>
            </AccordionSection>
          </div>
        </GlassPanel>
      ) : (
        <Button
          variant="ghost"
          className="absolute left-4 top-4 z-20"
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
          <GraphCanvas graph={graph} visibleTypes={visibleTypes} onNodeClick={selectEntity} />
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
          {visibleNodes.length} 节点 · {visibleEdgeCount} 边（{PERSPECTIVE_LABELS[perspective]}视角
          {perspective === "character"
            ? `·${characters.find((c) => c.id === characterId)?.name ?? "未选择角色"}`
            : ""}
          ）{isFiltered ? "（已筛选）" : ""}
        </span>
      </GlassPanel>

      <EntityPanel />
    </div>
  );
}
