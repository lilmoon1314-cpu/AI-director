/**
 * 实体表单校验（与后端 EntityCreate 契约对齐：name min_length=1、type 枚举；
 * 空白字符视同缺失）。校验只做前端即时反馈，后端校验仍是唯一权威。
 */

export const ENTITY_TYPES = [
  "character",
  "faction",
  "location",
  "item",
  "skill",
  "event",
  "concept",
] as const;

export type EntityType = (typeof ENTITY_TYPES)[number];

export interface EntityFormValues {
  type: string;
  name: string;
  aliases: string;
  audienceKnown: boolean;
  description: string;
}

export const EMPTY_ENTITY_FORM: EntityFormValues = {
  type: "character",
  name: "",
  aliases: "",
  audienceKnown: false,
  description: "",
};

export interface FormIssue {
  field: "name" | "type";
  message: string;
}

export function validateEntityForm(values: EntityFormValues): FormIssue[] {
  const issues: FormIssue[] = [];
  if (values.name.trim().length === 0) {
    issues.push({ field: "name", message: "名称不能为空（至少 1 个非空白字符）" });
  }
  if (!(ENTITY_TYPES as readonly string[]).includes(values.type)) {
    issues.push({ field: "type", message: `类型必须是：${ENTITY_TYPES.join("/")}` });
  }
  return issues;
}

/** 表单值 → EntityCreate 载荷（aliases 输入按逗号/顿号分隔，空白项剔除）。 */
export function toEntityCreate(values: EntityFormValues): {
  type: EntityType;
  name: string;
  aliases: string[];
  audience_known: boolean;
  description: string;
} {
  return {
    type: values.type as EntityType,
    name: values.name.trim(),
    aliases: values.aliases
      .split(/[,，、]/)
      .map((a) => a.trim())
      .filter((a) => a.length > 0),
    audience_known: values.audienceKnown,
    description: values.description.trim(),
  };
}
