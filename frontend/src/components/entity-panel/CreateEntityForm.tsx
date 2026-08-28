/**
 * 新建实体表单：前端校验（等价类/边界值）→ POST /api/entities → 成功后刷新图。
 * properties 按所选类型列出蓝图规定的全部字段（结构化输入，见 entityProperties.ts），
 * 提交前逐字段校验（number/object 非法阻止提交），后端校验仍是唯一权威。
 */

import { useState } from "react";

import { api, ApiError } from "../../api/client";
import {
  EMPTY_ENTITY_FORM,
  ENTITY_TYPES,
  toEntityCreate,
  validateEntityForm,
  type EntityFormValues,
  type FormIssue,
} from "../../lib/entityForm";
import {
  buildProperties,
  propertiesSchema,
  toPropertyFormState,
  type PropertyFormState,
} from "../../lib/entityProperties";
import { useGraphStore } from "../../stores/graphStore";
import { Button } from "../ui/Button";
import { CheckboxInput, SelectInput, TextArea, TextInput } from "../ui/Field";
import { PropertiesFields } from "./PropertiesFields";

export function CreateEntityForm() {
  const reloadGraph = useGraphStore((s) => s.loadGraph);
  const [form, setForm] = useState<EntityFormValues>(EMPTY_ENTITY_FORM);
  const [propValues, setPropValues] = useState<PropertyFormState>(() =>
    toPropertyFormState(EMPTY_ENTITY_FORM.type, {}),
  );
  const [propIssues, setPropIssues] = useState<Record<string, string>>({});
  const [issues, setIssues] = useState<FormIssue[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const issueFor = (field: FormIssue["field"]) => issues.find((i) => i.field === field)?.message;

  const submit = async () => {
    const found = validateEntityForm(form);
    setIssues(found);
    if (found.length > 0) return; // 无效输入：拦截，零网络请求
    const { properties, issues: propIssueMap } = buildProperties(form.type, propValues);
    setPropIssues(propIssueMap);
    if (Object.keys(propIssueMap).length > 0) return;
    setBusy(true);
    setError(null);
    try {
      await api.createEntity({ ...toEntityCreate(form), properties });
      setForm(EMPTY_ENTITY_FORM);
      setPropValues(toPropertyFormState(EMPTY_ENTITY_FORM.type, {}));
      await reloadGraph();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.problem : "创建实体失败，请稍后重试");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-3" data-testid="create-entity-form">
      {error ? (
        <p role="alert" className="rounded-xl border border-red-200 bg-red-50/80 p-3 text-xs text-red-700 dark:border-red-900 dark:bg-red-950/60 dark:text-red-400">
          {error}
        </p>
      ) : null}
      <SelectInput
        id="create-type"
        label="类型"
        options={ENTITY_TYPES}
        value={form.type}
        error={issueFor("type")}
        onChange={(e) => {
          const nextType = e.target.value;
          setForm({ ...form, type: nextType });
          setPropValues(toPropertyFormState(nextType, {})); // 类型切换 → 重置为该类型字段
          setPropIssues({});
        }}
      />
      <TextInput
        id="create-name"
        label="名称"
        value={form.name}
        error={issueFor("name")}
        onChange={(e) => setForm({ ...form, name: e.target.value })}
      />
      <TextInput
        id="create-aliases"
        label="别名（逗号分隔）"
        value={form.aliases}
        onChange={(e) => setForm({ ...form, aliases: e.target.value })}
      />
      <TextArea
        id="create-description"
        label="描述"
        value={form.description}
        onChange={(e) => setForm({ ...form, description: e.target.value })}
      />
      <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
        {form.type} 属性（{propertiesSchema(form.type).length} 个字段）
      </p>
      <PropertiesFields
        fields={propertiesSchema(form.type)}
        values={propValues}
        errors={propIssues}
        idPrefix="create"
        onChange={(key, raw) => setPropValues((prev) => ({ ...prev, [key]: raw }))}
      />
      <CheckboxInput
        id="create-audience"
        label="观众可见（audience_known）"
        checked={form.audienceKnown}
        onChange={(e) => setForm({ ...form, audienceKnown: e.target.checked })}
      />
      <Button onClick={submit} disabled={busy}>
        创建
      </Button>
    </div>
  );
}
