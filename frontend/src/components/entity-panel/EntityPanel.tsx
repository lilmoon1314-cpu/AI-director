/**
 * 实体详情面板：选中实体后拉取完整数据，支持编辑（PATCH）与删除（二次确认）。
 * - properties 按类型蓝图结构化展示（全部规定字段，空值显示 —）与编辑
 *   （与新建表单同一 schema 驱动，逐字段校验）；
 * - 后端 409（被引用）等业务错误原样展示三要素（problem + fix）。
 */

import { useEffect, useMemo, useState } from "react";

import { api, ApiError, type EntityRead } from "../../api/client";
import {
  EMPTY_ENTITY_FORM,
  ENTITY_TYPES,
  validateEntityForm,
  type EntityFormValues,
  type FormIssue,
} from "../../lib/entityForm";
import {
  buildProperties,
  displayPropertyValue,
  displayRefValue,
  propertiesSchema,
  toPropertyFormState,
  type PropertyFormState,
} from "../../lib/entityProperties";
import { useEntityIndexStore } from "../../stores/entityIndexStore";
import { useGraphStore } from "../../stores/graphStore";
import { useSelectionStore } from "../../stores/selectionStore";
import { Button } from "../ui/Button";
import { CheckboxInput, SelectInput, TextArea, TextInput } from "../ui/Field";
import { GlassPanel } from "../ui/GlassPanel";
import { PropertiesFields } from "./PropertiesFields";

function fromEntity(e: EntityRead): EntityFormValues {
  return {
    type: e.type,
    name: e.name,
    aliases: e.aliases?.join("，") ?? "",
    audienceKnown: e.audience_known,
    description: e.description,
  };
}

export function EntityPanel() {
  const selectedEntityId = useSelectionStore((s) => s.selectedEntityId);
  const panelOpen = useSelectionStore((s) => s.panelOpen);
  const clear = useSelectionStore((s) => s.clear);
  const reloadGraph = useGraphStore((s) => s.loadGraph);
  const briefs = useEntityIndexStore((s) => s.briefs);
  const loadEntities = useEntityIndexStore((s) => s.load);

  // 关联实体字段名称解析索引（F07）：面板挂载即确保加载（失败静默——显示回退原始 id）
  useEffect(() => {
    loadEntities().catch(() => {});
  }, [loadEntities]);
  const nameById = useMemo(() => new Map(briefs.map((b) => [b.id, b.name])), [briefs]);

  const [entity, setEntity] = useState<EntityRead | null>(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<EntityFormValues>(EMPTY_ENTITY_FORM);
  const [propValues, setPropValues] = useState<PropertyFormState>({});
  const [propIssues, setPropIssues] = useState<Record<string, string>>({});
  const [issues, setIssues] = useState<FormIssue[]>([]);
  const [error, setError] = useState<{ problem: string; fix: string } | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setEntity(null);
    setEditing(false);
    setError(null);
    setConfirmingDelete(false);
    setPropIssues({});
    if (!selectedEntityId) return;
    api
      .getEntity(selectedEntityId)
      .then((e) => {
        setEntity(e);
        setForm(fromEntity(e));
        setPropValues(toPropertyFormState(e.type, e.properties ?? {}));
      })
      .catch((cause: unknown) => {
        const err = cause instanceof ApiError ? cause : null;
        setError({
          problem: err?.problem ?? "实体详情加载失败",
          fix: err?.fix ?? "关闭面板后重试",
        });
      });
  }, [selectedEntityId]);

  if (!panelOpen || !selectedEntityId) return null;

  const issueFor = (field: FormIssue["field"]) => issues.find((i) => i.field === field)?.message;
  const fields = entity ? propertiesSchema(entity.type) : [];
  const extraEntries = entity
    ? Object.entries(entity.properties ?? {}).filter(
        ([k]) => !fields.some((f) => f.key === k),
      )
    : [];

  const save = async () => {
    if (!entity) return;
    const found = validateEntityForm(form);
    setIssues(found);
    if (found.length > 0) return;
    const { properties, issues: propIssueMap } = buildProperties(entity.type, propValues);
    setPropIssues(propIssueMap);
    if (Object.keys(propIssueMap).length > 0) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await api.updateEntity(entity.id, {
        name: form.name.trim(),
        aliases: form.aliases
          .split(/[,，、]/)
          .map((a) => a.trim())
          .filter((a) => a.length > 0),
        audience_known: form.audienceKnown,
        description: form.description.trim(),
        properties,
      });
      setEntity(updated);
      setEditing(false);
      await reloadGraph();
    } catch (cause) {
      const err = cause instanceof ApiError ? cause : null;
      setError({ problem: err?.problem ?? "保存失败", fix: err?.fix ?? "稍后重试" });
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!entity) return;
    setBusy(true);
    setError(null);
    try {
      await api.deleteEntity(entity.id);
      clear();
      await reloadGraph();
    } catch (cause) {
      const err = cause instanceof ApiError ? cause : null;
      setError({ problem: err?.problem ?? "删除失败", fix: err?.fix ?? "稍后重试" });
      setConfirmingDelete(false);
    } finally {
      setBusy(false);
    }
  };

  return (
    <GlassPanel data-testid="entity-panel" className="absolute top-6 right-6 z-10 max-h-[85vh] w-96 overflow-y-auto p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">实体详情</h2>
        <Button variant="ghost" onClick={clear} aria-label="关闭面板">
          关闭
        </Button>
      </div>

      {error ? (
        <div role="alert" className="mb-3 rounded-xl border border-red-200 bg-red-50/80 p-3 text-xs dark:border-red-900 dark:bg-red-950/60">
          <p className="font-medium text-red-700 dark:text-red-400">{error.problem}</p>
          <p className="mt-1 text-red-600 dark:text-red-400">修复：{error.fix}</p>
        </div>
      ) : null}

      {!entity ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">加载中…</p>
      ) : editing ? (
        <div className="flex flex-col gap-3">
          <SelectInput
            id="edit-type"
            label="类型"
            options={ENTITY_TYPES}
            value={form.type}
            error={issueFor("type")}
            disabled
            onChange={(e) => setForm({ ...form, type: e.target.value })}
          />
          <TextInput
            id="edit-name"
            label="名称"
            value={form.name}
            error={issueFor("name")}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <TextInput
            id="edit-aliases"
            label="别名（逗号分隔）"
            value={form.aliases}
            onChange={(e) => setForm({ ...form, aliases: e.target.value })}
          />
          <TextArea
            id="edit-description"
            label="描述"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
            {entity.type} 属性（{fields.length} 个字段）
          </p>
          <PropertiesFields
            fields={fields}
            values={propValues}
            errors={propIssues}
            idPrefix="edit"
            onChange={(key, raw) => setPropValues((prev) => ({ ...prev, [key]: raw }))}
          />
          <CheckboxInput
            id="edit-audience"
            label="观众可见（audience_known）"
            checked={form.audienceKnown}
            onChange={(e) => setForm({ ...form, audienceKnown: e.target.checked })}
          />
          <div className="flex gap-2">
            <Button onClick={save} disabled={busy}>
              保存
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                setEditing(false);
                setIssues([]);
                setPropIssues({});
                setForm(fromEntity(entity));
                setPropValues(toPropertyFormState(entity.type, entity.properties ?? {}));
              }}
            >
              取消
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-2 text-sm text-slate-700 dark:text-slate-300">
          <p>
            <span className="text-xs text-slate-500 dark:text-slate-400">名称</span>
            <br />
            <span className="font-medium text-slate-900 dark:text-slate-100">{entity.name}</span>
            <span className="ml-2 rounded-md bg-slate-200/70 px-2 py-0.5 text-xs dark:bg-slate-700/70">{entity.type}</span>
          </p>
          {entity.aliases && entity.aliases.length > 0 ? (
            <p>
              <span className="text-xs text-slate-500 dark:text-slate-400">别名</span>
              <br />
              {entity.aliases.join("、")}
            </p>
          ) : null}
          {entity.description ? (
            <p>
              <span className="text-xs text-slate-500 dark:text-slate-400">描述</span>
              <br />
              {entity.description}
            </p>
          ) : null}

          <div data-testid="entity-properties">
            <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
              {entity.type} 属性（{fields.length} 个字段）
            </p>
            <dl className="mt-1 space-y-1">
              {fields.map((f) => {
                const value = (entity.properties ?? {})[f.key];
                const display = f.refTypes
                  ? displayRefValue(value, nameById)
                  : displayPropertyValue(value);
                return (
                  <div
                    key={f.key}
                    data-testid={`prop-${f.key}`}
                    className="rounded-lg bg-slate-100/70 px-2 py-1 text-xs dark:bg-slate-800/70"
                  >
                    <dt className="font-medium text-slate-600 dark:text-slate-300">{f.label}</dt>
                    <dd className="break-all text-slate-700 dark:text-slate-400">{display}</dd>
                  </div>
                );
              })}
              {extraEntries.map(([key, value]) => (
                <div
                  key={key}
                  data-testid={`prop-${key}`}
                  className="rounded-lg bg-slate-100/70 px-2 py-1 text-xs dark:bg-slate-800/70"
                >
                  <dt className="font-medium text-slate-600 dark:text-slate-300">{key}</dt>
                  <dd className="break-all text-slate-700 dark:text-slate-400">
                    {displayPropertyValue(value)}
                  </dd>
                </div>
              ))}
            </dl>
          </div>

          <p className="text-xs text-slate-500 dark:text-slate-400">
            观众可见：{entity.audience_known ? "是" : "否"}
          </p>
          <div className="mt-2 flex gap-2">
            <Button onClick={() => setEditing(true)}>编辑</Button>
            {confirmingDelete ? (
              <>
                <span className="self-center text-xs text-red-600 dark:text-red-400">确认删除该实体？</span>
                <Button variant="danger" onClick={remove} disabled={busy}>
                  确认删除
                </Button>
                <Button variant="ghost" onClick={() => setConfirmingDelete(false)}>
                  取消
                </Button>
              </>
            ) : (
              <Button variant="danger" onClick={() => setConfirmingDelete(true)}>
                删除
              </Button>
            )}
          </div>
        </div>
      )}
    </GlassPanel>
  );
}
