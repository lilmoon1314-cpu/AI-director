/**
 * 各实体类型的 properties 结构化定义（来源：docs/data_struct_define.md §各类型 properties 蓝图）。
 * 表单/详情/编辑三处统一由本 schema 驱动：选择类型后列出该类型全部规定字段；
 * 关联 ID 类字段（如 abilities/affiliation）按底层类型渲染，值由用户填实体 ID
 * （@ 选择器属 F07 范围）。
 */

export type PropertyKind = "text" | "number" | "list" | "bool" | "object";

export interface PropertyFieldDef {
  key: string;
  label: string;
  kind: PropertyKind;
}

export const PROPERTY_SCHEMAS: Record<string, PropertyFieldDef[]> = {
  character: [
    { key: "age", label: "年龄", kind: "number" },
    { key: "gender", label: "性别", kind: "text" },
    { key: "occupation", label: "身份/职业", kind: "text" },
    { key: "social_class", label: "阶层", kind: "text" },
    { key: "resources", label: "资源列表（逗号分隔）", kind: "list" },
    { key: "obligations", label: "义务/责任（逗号分隔）", kind: "list" },
    { key: "abilities", label: "能力（关联 skill ID，逗号分隔）", kind: "list" },
    { key: "weaknesses", label: "弱点（逗号分隔）", kind: "list" },
    { key: "habits", label: "习惯（JSON：quirks/diet/daily_routine/hobbies/unconscious_actions）", kind: "object" },
    { key: "outer_desire", label: "外在欲望", kind: "text" },
    { key: "inner_need", label: "内在需要", kind: "text" },
    { key: "wrong_belief", label: "错误信念", kind: "text" },
    { key: "main_opposition", label: "主要对抗", kind: "text" },
    { key: "final_choice", label: "终局选择", kind: "text" },
    { key: "observable_arc", label: "可观察弧光", kind: "text" },
    { key: "backstory", label: "前史事件（JSON 数组）", kind: "object" },
    { key: "core_symbol", label: "核心象征（JSON，关联 item 实例）", kind: "object" },
    { key: "conscious_creed", label: "表意识信条", kind: "text" },
    { key: "subconscious_desire", label: "潜意识渴望", kind: "text" },
    { key: "shadow", label: "阴影", kind: "text" },
    { key: "desire", label: "贪求", kind: "text" },
    { key: "aversion", label: "憎恶", kind: "text" },
    { key: "delusion", label: "执念", kind: "text" },
    { key: "cognitive_lens", label: "认知模式", kind: "text" },
    { key: "family_theme", label: "原生家庭课题", kind: "text" },
    { key: "worldview_initial", label: "初期世界观", kind: "text" },
    { key: "life_view_initial", label: "初期人生观", kind: "text" },
    { key: "value_view_initial", label: "初期价值观", kind: "text" },
    { key: "affiliation", label: "所属门派（关联 faction ID）", kind: "text" },
    { key: "origin", label: "出身地", kind: "text" },
    { key: "cultivation", label: "能力体系（JSON）", kind: "object" },
    { key: "pressure_behaviors", label: "压力下行为（JSON 数组）", kind: "object" },
    { key: "language_fingerprint", label: "语言指纹（JSON 数组）", kind: "object" },
    { key: "writing_guide", label: "创作指南（JSON）", kind: "object" },
    { key: "forbidden_distortions", label: "禁止失真（逗号分隔）", kind: "list" },
    { key: "visual_features", label: "视觉特征（逗号分隔）", kind: "list" },
  ],
  faction: [
    { key: "description", label: "宗旨、历史", kind: "text" },
    { key: "headquarters", label: "驻地（关联 location ID）", kind: "text" },
    { key: "members", label: "成员角色（关联 character ID，逗号分隔）", kind: "list" },
    { key: "resources", label: "势力资源（逗号分隔）", kind: "list" },
    { key: "doctrine", label: "教义/规则", kind: "text" },
    { key: "public_relations", label: "对外关系（JSON 数组）", kind: "object" },
  ],
  location: [
    { key: "location_type", label: "类型（region/terrain/building/site）", kind: "text" },
    { key: "description", label: "基础描述", kind: "text" },
    { key: "parent_location", label: "上级地点 ID", kind: "text" },
    { key: "climate", label: "气候", kind: "text" },
    { key: "season", label: "当前季节", kind: "text" },
    { key: "weather", label: "当前天气", kind: "text" },
    { key: "time_of_day", label: "昼夜状态", kind: "text" },
    { key: "crowd_state", label: "群众状态", kind: "text" },
    { key: "special_restrictions", label: "特殊限制（逗号分隔）", kind: "list" },
    { key: "visual_elements", label: "视觉元素（JSON：flora/cuisine/architecture_style 等）", kind: "object" },
    { key: "resources", label: "自然资源（逗号分隔）", kind: "list" },
  ],
  item: [
    { key: "appearance", label: "外观描述", kind: "text" },
    { key: "authenticity", label: "真伪状态", kind: "text" },
    { key: "damage", label: "损坏情况", kind: "text" },
    { key: "location", label: "当前位置（关联 location/character ID）", kind: "text" },
    { key: "holder", label: "当前持有人（关联 character ID）", kind: "text" },
    { key: "seen_by", label: "见过的角色（关联 character ID，逗号分隔）", kind: "list" },
  ],
  skill: [
    { key: "description", label: "技能描述", kind: "text" },
    { key: "owner", label: "拥有者（关联 character ID）", kind: "text" },
    { key: "cost", label: "使用代价/限制", kind: "text" },
    { key: "level", label: "熟练度/境界", kind: "text" },
    { key: "category", label: "分类（功法/魔法/科技）", kind: "text" },
  ],
  event: [
    { key: "description", label: "事件描述", kind: "text" },
    { key: "participants", label: "参与角色（关联 character ID，逗号分隔）", kind: "list" },
    { key: "location", label: "发生地点（关联 location ID）", kind: "text" },
    { key: "time", label: "发生时间（世界时间）", kind: "text" },
    { key: "is_public", label: "是否对观众公开", kind: "bool" },
    { key: "known_by", label: "知晓角色（关联 character ID，逗号分隔）", kind: "list" },
  ],
  concept: [
    { key: "concept_type", label: "概念类型（flora/fauna/cuisine/custom/myth 等）", kind: "text" },
    { key: "description", label: "描述", kind: "text" },
    { key: "origin", label: "来源/传说", kind: "text" },
    { key: "image_ref", label: "视觉资产路径", kind: "text" },
  ],
};

export function propertiesSchema(type: string): PropertyFieldDef[] {
  return PROPERTY_SCHEMAS[type] ?? [];
}

/** 表单态：所有值统一为字符串（list 逗号分隔、object 为 JSON 文本、bool 为 "true"/"false"）。 */
export type PropertyFormState = Record<string, string>;

/** 真实 properties 数据 → 表单态（新建时传 {}）。 */
export function toPropertyFormState(type: string, data: Record<string, unknown> | undefined): PropertyFormState {
  const state: PropertyFormState = {};
  for (const f of propertiesSchema(type)) {
    const v = data?.[f.key];
    if (v === undefined || v === null) {
      state[f.key] = f.kind === "bool" ? "false" : "";
    } else if (f.kind === "list") {
      state[f.key] = Array.isArray(v) ? v.map(String).join(",") : String(v);
    } else if (f.kind === "object") {
      state[f.key] = JSON.stringify(v, null, 2);
    } else {
      state[f.key] = String(v);
    }
  }
  // schema 外的额外键：统一以 JSON 文本兜底展示（buildProperties 按 JSON 解析还原，
  // 原始字符串序列化为带引号 JSON 保持往返一致），编辑提交时原样保留
  for (const [k, v] of Object.entries(data ?? {})) {
    if (!(k in state)) state[k] = JSON.stringify(v, null, 2);
  }
  return state;
}

/** 表单态 → properties 载荷：空值字段剔除；object 非法 JSON 时返回错误。 */
export function buildProperties(
  type: string,
  state: PropertyFormState,
): { properties: Record<string, unknown>; issues: Record<string, string> } {
  const properties: Record<string, unknown> = {};
  const issues: Record<string, string> = {};
  const extraKeys = Object.keys(state).filter((k) => !propertiesSchema(type).some((f) => f.key === k));
  for (const [key, raw] of Object.entries(state)) {
    const def = propertiesSchema(type).find((f) => f.key === key);
    const kind = def?.kind ?? (extraKeys.includes(key) ? "object" : "text");
    if (kind === "bool") {
      if (raw === "true") properties[key] = true;
      continue;
    }
    if (raw.trim().length === 0) continue; // 空值字段不写入
    if (kind === "number") {
      const n = Number(raw);
      if (Number.isNaN(n)) {
        issues[key] = "必须是数字";
      } else {
        properties[key] = n;
      }
    } else if (kind === "list") {
      properties[key] = raw
        .split(/[,，、]/)
        .map((s) => s.trim())
        .filter((s) => s.length > 0);
    } else if (kind === "object") {
      try {
        properties[key] = JSON.parse(raw) as unknown;
      } catch {
        issues[key] = "不是合法 JSON";
      }
    } else {
      properties[key] = raw.trim();
    }
  }
  return { properties, issues };
}

/** 真实值 → 详情面板显示文本（空值显示 —）。 */
export function displayPropertyValue(value: unknown): string {
  if (value === undefined || value === null || value === "") return "—";
  if (Array.isArray(value)) return value.length > 0 ? value.map(String).join("、") : "—";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
