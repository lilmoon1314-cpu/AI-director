/**
 * 实体详情面板：选中实体后拉取完整数据，支持编辑（PATCH）与删除（二次确认）。
 * 后端 409（被引用）等业务错误原样展示三要素（problem + fix）。
 */

import { useEffect, useState } from "react";

import { api, ApiError, type EntityRead } from "../../api/client";
import {
  EMPTY_ENTITY_FORM,
  ENTITY_TYPES,
  validateEntityForm,
  type EntityFormValues,
  type FormIssue,
} from "../../lib/entityForm";
import { useGraphStore } from "../../stores/graphStore";
import { useSelectionStore } from "../../stores/selectionStore";
import { Button } from "../ui/Button";
import { CheckboxInput, SelectInput, TextArea, TextInput } from "../ui/Field";
import { GlassPanel } from "../ui/GlassPanel";

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

  const [entity, setEntity] = useState<EntityRead | null>(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<EntityFormValues>(EMPTY_ENTITY_FORM);
  const [issues, setIssues] = useState<FormIssue[]>([]);
  const [error, setError] = useState<{ problem: string; fix: string } | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setEntity(null);
    setEditing(false);
    setError(null);
    setConfirmingDelete(false);
    if (!selectedEntityId) return;
    api
      .getEntity(selectedEntityId)
      .then((e) => {
        setEntity(e);
        setForm(fromEntity(e));
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

  const issueFor = (field: FormIssue["field"]) =>
    issues.find((i) => i.field === field)?.message;

  const save = async () => {
    if (!entity) return;
    const found = validateEntityForm(form);
    setIssues(found);
    if (found.length > 0) return;
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
    <GlassPanel data-testid="entity-panel" className="absolute top-6 right-6 z-10 w-96 p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900">实体详情</h2>
        <Button variant="ghost" onClick={clear} aria-label="关闭面板">
          关闭
        </Button>
      </div>

      {error ? (
        <div role="alert" className="mb-3 rounded-xl border border-red-200 bg-red-50/80 p-3 text-xs">
          <p className="font-medium text-red-700">{error.problem}</p>
          <p className="mt-1 text-red-600">修复：{error.fix}</p>
        </div>
      ) : null}

      {!entity ? (
        <p className="text-sm text-slate-500">加载中…</p>
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
                setForm(fromEntity(entity));
              }}
            >
              取消
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-2 text-sm text-slate-700">
          <p>
            <span className="text-xs text-slate-500">名称</span>
            <br />
            <span className="font-medium text-slate-900">{entity.name}</span>
            <span className="ml-2 rounded-md bg-slate-200/70 px-2 py-0.5 text-xs">{entity.type}</span>
          </p>
          {entity.aliases && entity.aliases.length > 0 ? (
            <p>
              <span className="text-xs text-slate-500">别名</span>
              <br />
              {entity.aliases.join("、")}
            </p>
          ) : null}
          {entity.description ? (
            <p>
              <span className="text-xs text-slate-500">描述</span>
              <br />
              {entity.description}
            </p>
          ) : null}
          <p className="text-xs text-slate-500">
            观众可见：{entity.audience_known ? "是" : "否"}
          </p>
          <div className="mt-2 flex gap-2">
            <Button onClick={() => setEditing(true)}>编辑</Button>
            {confirmingDelete ? (
              <>
                <span className="self-center text-xs text-red-600">确认删除该实体？</span>
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
