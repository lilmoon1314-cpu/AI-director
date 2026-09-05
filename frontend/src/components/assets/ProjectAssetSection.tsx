/**
 * 项目资产区（F08）：当前项目数据库的实体，按 7 类分组排列。
 * - 卡片 = 圆角矩形（缩略图/名称/概述），点击打开实体 HTML 资产页（内嵌查看器）；
 * - 分组顺序与色点沿用 lib/palette 类型序；每卡片图片计数角标。
 */

import { useMemo } from "react";

import { api } from "../../api/client";
import { ENTITY_TYPES } from "../../lib/entityForm";
import { TYPE_COLORS, TYPE_LABELS } from "../../lib/palette";
import { useAssetStore } from "../../stores/assetStore";
import { AssetCardTile } from "./AssetCardTile";

export function ProjectAssetSection() {
  const cards = useAssetStore((s) => s.entityCards);
  const loading = useAssetStore((s) => s.entityLoading);
  const openViewer = useAssetStore((s) => s.openViewer);

  const byType = useMemo(() => {
    const groups = new Map<string, typeof cards>();
    for (const card of cards) {
      const list = groups.get(card.type) ?? [];
      list.push(card);
      groups.set(card.type, list);
    }
    return groups;
  }, [cards]);

  if (loading) {
    return <p className="text-xs text-slate-500 dark:text-slate-400">加载中…</p>;
  }

  return (
    <div className="flex flex-col gap-6" data-testid="project-assets">
      {ENTITY_TYPES.map((type) => {
        const list = byType.get(type) ?? [];
        return (
          <section key={type}>
            <h3 className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-300">
              <span
                aria-hidden
                className="h-2.5 w-2.5 rounded-full ring-1 ring-black/10 dark:ring-white/20"
                style={{ backgroundColor: TYPE_COLORS[type] }}
              />
              {TYPE_LABELS[type]}
              <span className="text-xs font-normal text-slate-400 dark:text-slate-500">
                （{list.length}）
              </span>
            </h3>
            {list.length === 0 ? (
              <p className="rounded-xl bg-white/50 px-4 py-3 text-xs text-slate-400 dark:bg-slate-800/50 dark:text-slate-500">
                暂无该类型实体
              </p>
            ) : (
              <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-3">
                {list.map((card) => (
                  <AssetCardTile
                    key={card.id}
                    testId={`entity-asset-${card.id}`}
                    title={card.name}
                    description={card.description}
                    coverUrl={card.cover_url}
                    placeholderType={type}
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
          </section>
        );
      })}
    </div>
  );
}
