/**
 * 新建实体表单：前端校验（等价类/边界值）→ POST /api/entities → 成功后刷新图。
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
import { useGraphStore } from "../../stores/graphStore";
import { Button } from "../ui/Button";
import { CheckboxInput, SelectInput, TextArea, TextInput } from "../ui/Field";
import { GlassPanel } from "../ui/GlassPanel";

export function CreateEntityForm() {
  const reloadGraph = useGraphStore((s) => s.loadGraph);
  const [form, setForm] = useState<EntityFormValues>(EMPTY_ENTITY_FORM);
  const [issues, setIssues] = useState<FormIssue[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const issueFor = (field: FormIssue["field"]) => issues.find((i) => i.field === field)?.message;

  const submit = async () => {
    const found = validateEntityForm(form);
    setIssues(found);
    if (found.length > 0) return; // 无效输入：拦截，零网络请求
    setBusy(true);
    setError(null);
    try {
      await api.createEntity(toEntityCreate(form));
      setForm(EMPTY_ENTITY_FORM);
      await reloadGraph();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.problem : "创建实体失败，请稍后重试");
    } finally {
      setBusy(false);
    }
  };

  return (
    <GlassPanel data-testid="create-entity-form" className="p-5">
      <h2 className="mb-3 text-sm font-semibold text-slate-900">新建实体</h2>
      {error ? (
        <p role="alert" className="mb-3 rounded-xl border border-red-200 bg-red-50/80 p-3 text-xs text-red-700">
          {error}
        </p>
      ) : null}
      <div className="flex flex-col gap-3">
        <SelectInput
          id="create-type"
          label="类型"
          options={ENTITY_TYPES}
          value={form.type}
          error={issueFor("type")}
          onChange={(e) => setForm({ ...form, type: e.target.value })}
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
    </GlassPanel>
  );
}
