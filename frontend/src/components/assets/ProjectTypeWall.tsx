/**
 * 项目资产 · 类型库墙（F12 第一级，DESIGN.md §5.3.2）：当前项目的 7 个实体类型库卡片。
 * - 库卡：类型色渐变封面 + 「XX库」+ 聚合计数（N 实体 · M 张图，前端 typeStats 聚合）；
 * - 空类型库：灰色虚线卡「暂无 XX 实体」+「去图谱页创建」引导（跳图谱页并预选类型）；
 * - 项目整体无实体时顶部显示引导卡（空状态统一模式）。
 */

import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { useAssetStore } from "../../stores/assetStore";
import { useProjectId } from "../../stores/projectStore";
import { ENTITY_TYPES } from "../../lib/entityForm";
import { typeStats } from "../../lib/assetFilters";
import { TYPE_COLORS, TYPE_LABELS } from "../../lib/palette";
import { Button } from "../ui/Button";
import { ErrorStrip } from "../ui/ErrorStrip";

export function ProjectTypeWall() {
  const navigate = useNavigate();
  const projectId = useProjectId();
  const cards = useAssetStore((s) => s.entityCards);
  const loading = useAssetStore((s) => s.entityLoading);
  const error = useAssetStore((s) => s.entityError);
  const loadEntityCards = useAssetStore((s) => s.loadEntityCards);
  const stats = useMemo(() => typeStats(cards), [cards]);
  const totalEntities = cards.length;

  if (loading) {
    return <p className="text-xs text-slate-500 dark:text-slate-400">加载中…</p>;
  }

  const graphWithPrefill = (type: string) =>
    `/projects/${projectId}/graph?create=entity&type=${type}`;

  return (
    <div className="flex flex-col gap-4" data-testid="asset-type-wall">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-300">
          项目资产
          <span className="rounded-full bg-white/70 px-2 py-0.5 text-[10px] font-normal text-slate-500 ring-1 ring-black/5 dark:bg-slate-800/70 dark:text-slate-400 dark:ring-white/10">
            随当前项目
          </span>
        </h2>
        <span className="ml-auto text-xs text-slate-400 dark:text-slate-500">
          共 {totalEntities} 实体 · {cards.reduce((sum, c) => sum + c.image_count, 0)} 张图
        </span>
      </div>

      {error ? (
        <ErrorStrip
          testId="asset-project-error"
          problem={error.problem}
          fix={error.fix}
          onRetry={() => void loadEntityCards(projectId, true)}
        />
      ) : null}

      {!error && totalEntities === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-2xl bg-white/60 p-10 text-center backdrop-blur dark:bg-slate-800/60">
          <p className="text-base font-medium text-slate-800 dark:text-slate-200">
            该项目还没有实体
          </p>
          <p className="max-w-sm text-sm text-slate-500 dark:text-slate-400">
            项目资产随图谱实体生长——先去图谱页创建实体，这里会出现对应的类型资产库
          </p>
          <Button onClick={() => navigate(graphWithPrefill("character"))}>去图谱页创建</Button>
        </div>
      ) : null}

      <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-3">
        {ENTITY_TYPES.map((type) => {
          const stat = stats[type];
          const label = TYPE_LABELS[type] ?? type;
          if (stat.count === 0) {
            return (
              <button
                key={type}
                type="button"
                data-testid={`asset-type-card-${type}`}
                onClick={() => navigate(graphWithPrefill(type))}
                className="group flex min-h-32 flex-col items-center justify-center gap-1.5 rounded-2xl border-2 border-dashed border-slate-300 p-4 text-slate-400 transition-all duration-150 hover:-translate-y-1 hover:border-slate-400 hover:text-slate-600 dark:border-slate-700 dark:text-slate-500 dark:hover:border-slate-500 dark:hover:text-slate-300"
              >
                <span className="text-sm font-medium">暂无{label}实体</span>
                <span className="text-xs group-hover:underline">去图谱页创建 →</span>
              </button>
            );
          }
          return (
            <button
              key={type}
              type="button"
              data-testid={`asset-type-card-${type}`}
              onClick={() => navigate(`/projects/${projectId}/assets/project/${type}`)}
              aria-label={`进入${label}库`}
              className="group flex flex-col overflow-hidden rounded-2xl bg-white/80 text-left shadow-sm ring-1 ring-black/5 backdrop-blur transition-all duration-150 hover:-translate-y-1 hover:shadow-md dark:bg-slate-800/80 dark:ring-white/10"
            >
              <div
                aria-hidden
                className="flex aspect-[16/10] items-center justify-center overflow-hidden"
                style={{ backgroundColor: `${TYPE_COLORS[type] ?? "#cbd5e1"}22` }}
              >
                <span
                  className="flex h-12 w-12 items-center justify-center rounded-2xl text-lg font-semibold text-white transition-transform duration-150 group-hover:scale-105"
                  style={{ backgroundColor: TYPE_COLORS[type] ?? "#cbd5e1" }}
                >
                  {label.slice(0, 1)}
                </span>
              </div>
              <div className="px-3 py-2">
                <p className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">
                  {label}库
                </p>
                <p className="pt-1 text-[10px] text-slate-400 dark:text-slate-500">
                  {stat.count} 实体 · {stat.images} 张图
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
