/**
 * 新建实体表单：前端校验（等价类/边界值）→ POST /api/entities → 成功后刷新图。
 * properties 为 JSON 文本编辑（默认 {}；known_by/seen_by 等任意结构均可填），
 * 提交前 parse 校验，非法 JSON 阻止提交（前端即时反馈，后端校验仍是唯一权威）。
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

export function CreateEntityForm() {
  const reloadGraph = useGraphStore((s) => s.loadGraph);
  const [form, setForm] = useState<EntityFormValues>(EMPTY_ENTITY_FORM);
  const [propsText, setPropsText] = useState("{}");
  const [propsIssue, setPropsIssue] = useState<string | null>(null);
  const [issues, setIssues] = useState<FormIssue[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const issueFor = (field: FormIssue["field"]) => issues.find((i) => i.field === field)?.message;

  const parseProps = (): Record<string, unknown> | null => {
    try {
      const value = JSON.parse(propsText || "{}") as unknown;
      if (typeof value !== "object" || value === null || Array.isArray(value)) {
        setPropsIssue("properties 必须是 JSON 对象（如 {\"known_by\": [\"char-a\"]}）");
        return null;
      }
      setPropsIssue(null);
      return value as Record<string, unknown>;
    } catch {
      setPropsIssue("properties 不是合法 JSON，请检查格式");
      return null;
    }
  };

  const submit = async () => {
    const found = validateEntityForm(form);
    setIssues(found);
    if (found.length > 0) return; // 无效输入：拦截，零网络请求
    const props = parseProps();
    if (props === null) return;
    setBusy(true);
    setError(null);
    try {
      await api.createEntity({ ...toEntityCreate(form), properties: props });
      setForm(EMPTY_ENTITY_FORM);
      setPropsText("{}");
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
      <TextArea
        id="create-props"
        label="属性 properties（JSON）"
        value={propsText}
        error={propsIssue ?? undefined}
        onChange={(e) => setPropsText(e.target.value)}
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
