/**
 * 实体类型配色与关系边配色规则。
 * - 节点：按实体类型固定标识色（与深浅主题均保持可读的中饱和度色）；
 * - 关系边：跟随「非 character 一端」的类型色，且更淡更透明（用户规则）；
 *   两端均为 character 时取中性蓝灰淡化；两端均非人时取 target 端类型色。
 */

export const TYPE_COLORS: Record<string, string> = {
  character: "#5b8def", // 人 — 蓝
  faction: "#e0885a", // 门派 — 橙
  location: "#4caf7d", // 地点 — 绿
  item: "#d4b13f", // 物 — 金
  skill: "#a678d8", // 功法 — 紫
  event: "#e06a75", // 事件 — 红
  concept: "#8a94a6", // 概念 — 灰
};

const FALLBACK_COLOR = TYPE_COLORS.concept;

export function nodeColor(type: string): string {
  return TYPE_COLORS[type] ?? FALLBACK_COLOR;
}

export interface EdgeStyleColor {
  /** 边描边色（跟随非人端类型色） */
  stroke: string;
  /** 关系边整体比节点更淡更透明 */
  opacity: number;
}

export function relationEdgeColor(sourceType: string, targetType: string): EdgeStyleColor {
  const sourceIsCharacter = sourceType === "character";
  const targetIsCharacter = targetType === "character";
  const anchorType = sourceIsCharacter && targetIsCharacter
    ? null // 人—人：无非人因素，取中性
    : sourceIsCharacter
      ? targetType // 人—非人：跟随非人端
      : sourceType; // 非人—任意：跟随 source（两端皆非人时也成立）
  return {
    stroke: anchorType ? nodeColor(anchorType) : "#94a3b8",
    opacity: 0.45,
  };
}
