/**
 * 项目资产 · 类型库详情（F12 第二级，DESIGN.md §5.3.3）：某实体类型的实体卡片墙。
 * - 面包屑「项目资产 / XX库」+ 返回按钮（asset-type-back）——浏览器后退同样有效（路由化收益）；
 * - 独立搜索框（asset-search，前端过滤名称/描述）；实体卡点击打开 HTML 资产页查看器；
 * - 空类型（深链直达）→ 引导去图谱页创建并预选类型；搜索无命中 → 独立提示；
 * - 无效 entityType → 重定向回类型库墙（路由参数防御）。
 */

import { useMemo, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";

import { api } from "../../api/client";
import { filterEntityCards } from "../../lib/assetFilters";
import { ENTITY_TYPES } from "../../lib/entityForm";
import { TYPE_LABELS } from "../../lib/palette";
import { useAssetStore } from "../../stores/assetStore";
import { useProjectId } from "../../stores/projectStore";
import { AssetCardTile } from "./AssetCardTile";
import { Button } from "../ui/Button";
import { ErrorStrip } from "../ui/ErrorStrip";

export function EntityTypeAssets() {
  const { entityType } = useParams<{ entityType: string }>();
  const navigate = useNavigate();
  const projectId = useProjectId();
  const cards = useAssetStore((s) => s.entityCards);
  const loading = useAssetStore((s) => s.entityLoading);
  const error = useAssetStore((s) => s.entityError);
  const loadEntityCards = useAssetStore((s) => s.loadEntityCards);
  const openViewer = useAssetStore((s) => s.openViewer);
  const [query, setQuery] = useState("");

  // 钩子先于条件渲染（hooks 顺序恒定），无效类型在渲染层重定向
  const valid = !!entityType && ENTITY_TYPES.includes(entityType as (typeof ENTITY_TYPES)[number]);
  const label = valid && entityType ? (TYPE_LABELS[entityType] ?? entityType) : "";

  const ofType = useMemo(
    () => (valid ? cards.filter((c) => c.type === entityType) : []),
    [cards, entityType, valid],
  );
  const visible = useMemo(
    () => (valid ? filterEntityCards(ofType, query) : []),
    [ofType, query, valid],
  );

  if (!valid) {
    return <Navigate to={`/projects/${projectId}/assets/project`} replace />;
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <Button
          variant="ghost"
          data-testid="asset-type-back"
          onClick={() => navigate(`/projects/${projectId}/assets/project`)}
          className="px-2 py-1 text-xs"
        >
          ◀ 返回类型库
        </Button>
        <nav aria-label="面包屑" className="text-sm text-slate-500 dark:text-slate-400">
          <Link
            to={`/projects/${projectId}/assets/project`}
            className="hover:text-slate-800 hover:underline dark:hover:text-slate-200"
          >
            项目资产
          </Link>
          <span className="mx-1.5">/</span>
          <span className="font-medium text-slate-800 dark:text-slate-200">{label}库</span>
        </nav>
        <input
          type="search"
          data-testid="asset-search"
          aria-label={`搜索${label}库`}
          placeholder={`搜索${label}名称 / 描述…`}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="ml-auto w-52 rounded-full border border-slate-200 bg-white/70 px-3 py-1 text-xs text-slate-800 outline-none transition-colors duration-150 focus:border-slate-400 dark:border-slate-700 dark:bg-slate-800/70 dark:text-slate-200"
        />
      </div>

      {error ? (
        <ErrorStrip
          testId="asset-project-error"
          problem={error.problem}
          fix={error.fix}
          onRetry={() => void loadEntityCards(projectId, true)}
        />
      ) : loading ? (
        <p className="text-xs text-slate-500 dark:text-slate-400">加载中…</p>
      ) : !error && ofType.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-2xl bg-white/60 p-10 text-center backdrop-blur dark:bg-slate-800/60">
          <p className="text-base font-medium text-slate-800 dark:text-slate-200">
            暂无{label}实体
          </p>
          <p className="max-w-sm text-sm text-slate-500 dark:text-slate-400">
            去图谱页创建{label}实体，创建后这里会出现它的资产卡
          </p>
          <Button onClick={() => navigate(`/projects/${projectId}/graph?create=entity&type=${entityType}`)}>
            去图谱页创建
          </Button>
        </div>
      ) : visible.length === 0 ? (
        <p
          data-testid="asset-search-empty"
          className="rounded-2xl bg-white/60 p-6 text-center text-sm text-slate-500 backdrop-blur dark:bg-slate-800/60 dark:text-slate-400"
        >
          未找到匹配「{query.trim()}」的实体——换个关键词试试。
        </p>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-3">
          {visible.map((card) => (
            <AssetCardTile
              key={card.id}
              testId={`entity-asset-${card.id}`}
              title={card.name}
              description={card.description}
              coverUrl={card.cover_url}
              placeholderType={entityType}
              meta={card.image_count > 0 ? `${card.image_count} 图` : undefined}
              onOpen={() =>
                openViewer({
                  url: api.assetPageUrl("entity", card.id),
                  title: card.name,
                })
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}
