/**
 * 资产卡片瓦片（F08）：圆角矩形卡片——缩略图（无图用类型色占位）+ 名称 + 概述。
 * - 通用资产与项目资产共用；占位色取 lib/palette 的类型色（项目资产）或中性色；
 * - 点击卡片触发 onOpen（由父级决定打开查看器或编辑）。
 */

import { TYPE_COLORS, TYPE_LABELS } from "../../lib/palette";

export function AssetCardTile({
  title,
  description,
  coverUrl,
  placeholderType,
  meta,
  onOpen,
  testId,
}: {
  title: string;
  description: string;
  coverUrl: string | null;
  /** 无图占位色的实体类型（通用资产不传则用中性色）。 */
  placeholderType?: string;
  meta?: string;
  onOpen: () => void;
  testId: string;
}) {
  const placeholderColor =
    placeholderType && TYPE_COLORS[placeholderType]
      ? TYPE_COLORS[placeholderType]
      : "#cbd5e1";
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onOpen}
      className="group flex flex-col overflow-hidden rounded-2xl bg-white/80 text-left shadow-sm ring-1 ring-black/5 backdrop-blur transition-all duration-150 hover:-translate-y-0.5 hover:shadow-md dark:bg-slate-800/80 dark:ring-white/10"
    >
      <div
        className="relative flex h-28 w-full items-center justify-center overflow-hidden"
        style={{ backgroundColor: `${placeholderColor}22` }}
      >
        {coverUrl ? (
          <img
            src={coverUrl}
            alt={title}
            loading="lazy"
            className="h-full w-full object-cover transition-transform duration-150 group-hover:scale-[1.03]"
          />
        ) : (
          <span
            aria-hidden
            className="h-10 w-10 rounded-full ring-2 ring-white/70"
            style={{ backgroundColor: placeholderColor }}
          />
        )}
        {placeholderType ? (
          <span className="absolute left-2 top-2 rounded-md bg-white/80 px-1.5 py-0.5 text-[10px] text-slate-600 backdrop-blur dark:bg-slate-900/70 dark:text-slate-300">
            {TYPE_LABELS[placeholderType] ?? placeholderType}
          </span>
        ) : null}
      </div>
      <div className="flex flex-1 flex-col gap-1 px-3 py-2">
        <p className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">{title}</p>
        {description ? (
          <p className="line-clamp-2 text-xs leading-5 text-slate-500 dark:text-slate-400">
            {description}
          </p>
        ) : null}
        {meta ? (
          <p className="mt-auto pt-1 text-[10px] text-slate-400 dark:text-slate-500">{meta}</p>
        ) : null}
      </div>
    </button>
  );
}
