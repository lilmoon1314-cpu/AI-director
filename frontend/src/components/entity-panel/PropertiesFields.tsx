/**
 * properties 结构化字段组（表单/编辑共用受控组件）：
 * 按类型 schema 渲染全部规定字段——text→输入框、number→数字输入、
 * list→逗号分隔输入、bool→复选框、object→JSON 文本域；errors 为逐字段错误。
 */

import type { PropertyFieldDef } from "../../lib/entityProperties";
import { CheckboxInput, TextArea, TextInput } from "../ui/Field";

interface PropertiesFieldsProps {
  fields: PropertyFieldDef[];
  values: Record<string, string>;
  errors?: Record<string, string>;
  idPrefix: string;
  onChange: (key: string, raw: string) => void;
}

export function PropertiesFields({ fields, values, errors, idPrefix, onChange }: PropertiesFieldsProps) {
  return (
    <div className="flex flex-col gap-2" data-testid="property-fields">
      {fields.map((f) => {
        const id = `${idPrefix}-prop-${f.key}`;
        const error = errors?.[f.key];
        const value = values[f.key] ?? "";
        if (f.kind === "bool") {
          return (
            <CheckboxInput
              key={f.key}
              id={id}
              label={f.label}
              checked={value === "true"}
              onChange={(e) => onChange(f.key, e.target.checked ? "true" : "false")}
            />
          );
        }
        if (f.kind === "object") {
          return (
            <TextArea
              key={f.key}
              id={id}
              label={f.label}
              value={value}
              error={error}
              rows={3}
              onChange={(e) => onChange(f.key, e.target.value)}
            />
          );
        }
        return (
          <TextInput
            key={f.key}
            id={id}
            label={f.label}
            value={value}
            error={error}
            inputMode={f.kind === "number" ? "decimal" : undefined}
            onChange={(e) => onChange(f.key, e.target.value)}
          />
        );
      })}
    </div>
  );
}
