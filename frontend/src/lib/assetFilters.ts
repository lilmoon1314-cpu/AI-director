/**
 * 资产页前端过滤与类型聚合纯函数（F12，DESIGN.md §5.3）。
 * 分区独立搜索为前端过滤（不发起请求）：通用区按标题/描述/分类，类型库详情按名称/描述；
 * 所有匹配不区分大小写且先 trim（空串/纯空白 = 不过滤）。
 */

import { ENTITY_TYPES } from "./entityForm";

export interface GeneralFilterOptions {
  /** 搜索词：匹配标题/描述/分类任一。 */
  query: string;
  /** 分类 chip（空串 = 全部分类），与 query 叠加为 AND 语义。 */
  category: string;
}

interface GeneralLike {
  title: string;
  description: string;
  category: string;
}

/** 通用参考库过滤：query（标题/描述/分类任一命中）AND 分类 chip。 */
export function filterGeneralAssets<T extends GeneralLike>(
  cards: T[],
  options: GeneralFilterOptions,
): T[] {
  const needle = options.query.trim().toLowerCase();
  return cards.filter((card) => {
    if (options.category && card.category !== options.category) return false;
    if (!needle) return true;
    return (
      card.title.toLowerCase().includes(needle) ||
      card.description.toLowerCase().includes(needle) ||
      card.category.toLowerCase().includes(needle)
    );
  });
}

/** 类型库详情过滤：实体名称/描述命中。 */
export function filterEntityCards<T extends { name: string; description: string }>(
  cards: T[],
  query: string,
): T[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return cards;
  return cards.filter(
    (card) =>
      card.name.toLowerCase().includes(needle) || card.description.toLowerCase().includes(needle),
  );
}

export interface TypeStats {
  /** 该类型实体数 */
  count: number;
  /** 该类型图片总数（image_count 求和） */
  images: number;
}

/** 类型库墙聚合（DESIGN.md §5.3.2）：仅统计 7 个固定类型，未知类型防御性忽略。 */
export function typeStats(cards: { type: string; image_count: number }[]): Record<string, TypeStats> {
  const stats: Record<string, TypeStats> = {};
  for (const type of ENTITY_TYPES) stats[type] = { count: 0, images: 0 };
  for (const card of cards) {
    const stat = stats[card.type];
    if (!stat) continue;
    stat.count += 1;
    stat.images += card.image_count;
  }
  return stats;
}
