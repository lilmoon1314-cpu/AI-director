/**
 * 新建关系表单：端点从当前图节点中选择（下拉），类型为自由文本（后端 F03 契约）；
 * POST /api/relations 成功后刷新图。后端 409/404（端点不存在等）展示 problem。
 */

import { useState } from "react";

import { api, ApiError } from "../../api/client";
import { useGraphStore } from "../../stores/graphStore";
import { Button } from "../ui/Button";
import { CheckboxInput, TextInput } from "../ui/Field";

export function CreateRelationForm() {
  const nodes = useGraphStore((s) => s.graph.nodes);
  const reloadGraph = useGraphStore((s) => s.loadGraph);
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const [type, setType] = useState("ALLY");
  const [audienceKnown, setAudienceKnown] = useState(false);
  const [issue, setIssue] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const nodeOptions = nodes.map((n) => (
    <option key={n.id} value={n.id}>
      {n.data.name}
    </option>
  ));

  const submit = async () => {
    if (!source || !target || type.trim().length === 0) {
      setIssue("请选择两端点并填写关系类型");
      return;
    }
    if (source === target) {
      setIssue("关系的两端不能是同一实体（后端拒绝自环）");
      return;
    }
    setIssue(null);
    setBusy(true);
    setError(null);
    try {
      await api.createRelation({
        source,
        target,
        type: type.trim().toUpperCase(),
        audience_known: audienceKnown,
      });
      await reloadGraph();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.problem : "创建关系失败，请稍后重试");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-3" data-testid="create-relation-form">
      {issue ? (
        <p role="alert" className="text-xs text-red-600 dark:text-red-400">
          {issue}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="rounded-xl border border-red-200 bg-red-50/80 p-3 text-xs text-red-700 dark:border-red-900 dark:bg-red-950/60 dark:text-red-400">
          {error}
        </p>
      ) : null}
      <label className="flex flex-col gap-1 text-xs font-medium text-slate-700 dark:text-slate-300">
        起点实体
        <select
          aria-label="关系起点"
          value={source}
          onChange={(e) => setSource(e.target.value)}
          className="w-full rounded-xl border border-slate-300 bg-white/70 px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none dark:border-slate-600 dark:bg-slate-800/70 dark:text-slate-100"
        >
          <option value="">请选择…</option>
          {nodeOptions}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs font-medium text-slate-700 dark:text-slate-300">
        终点实体
        <select
          aria-label="关系终点"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          className="w-full rounded-xl border border-slate-300 bg-white/70 px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none dark:border-slate-600 dark:bg-slate-800/70 dark:text-slate-100"
        >
          <option value="">请选择…</option>
          {nodeOptions}
        </select>
      </label>
      <TextInput
        id="create-relation-type"
        label="关系类型（如 ALLY）"
        value={type}
        onChange={(e) => setType(e.target.value)}
      />
      <CheckboxInput
        id="create-relation-audience"
        label="观众可见（audience_known）"
        checked={audienceKnown}
        onChange={(e) => setAudienceKnown(e.target.checked)}
      />
      <Button onClick={submit} disabled={busy || nodes.length === 0}>
        创建关系
      </Button>
    </div>
  );
}
