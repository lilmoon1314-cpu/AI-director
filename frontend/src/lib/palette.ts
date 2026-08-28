/**
 * 实体类型配色与关系边配色规则（色值由用户指定，2026-08-28）。
 * - 节点：按实体类型固定标识色；
 * - 关系边：跟随「非 character 一端」的类型色，且透明度再减半（0.22）保持视图清晰；
 *   两端均为 character 时取中性蓝灰淡化；两端均非人时取 target 端类型色。
 */

export const TYPE_COLORS: Record<string, string> = {
  character: "#ff5a7d", // 人物 — 粉红
  faction: "#ffceff", // 门派 — 浅粉紫
  location: "#40531b", // 地点 — 暗绿
  item: "#a7ffff", // 物件 — 浅青
  skill: "#f86624", // 功法 — 橙
  event: "#ffff7e", // 事件 — 亮黄
  concept: "#97a7b3", // 概念 — 灰蓝
};

const FALLBACK_COLOR = TYPE_COLORS.concept;

export function nodeColor(type: string): string {
  return TYPE_COLORS[type] ?? FALLBACK_COLOR;
}

export interface EdgeStyleColor {
  /** 边描边色（跟随非人端类型色） */
  stroke: string;
  /** 关系边整体比节点更淡更透明（用户要求为基础值的一半） */
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
    opacity: 0.22,
  };
}
