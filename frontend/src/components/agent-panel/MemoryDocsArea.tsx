/**
 * 记忆文档卡片区（F10/F13，DESIGN.md §5.4/§13.1 左栏底部「📚 记忆文档」区）：
 * 文档卡（名称+更新时间+首行摘要，memory-doc-card）＋新建内置模板
 * （世界观定位 / 风格约定——指导类项目内唯一，已存在即置灰提示「每项目仅一份」，
 * 后端 409 兜底）；点击卡片打开大编辑弹窗；文档卡 🗑 两击轻确认删除。
 */

import { useEffect, useRef, useState } from "react";

import { Button } from "../ui/Button";
import { ErrorStrip } from "../ui/ErrorStrip";
import { GlassPanel } from "../ui/GlassPanel";
import { DocEditor } from "./DocEditor";

const TEMPLATES = [
  { kind: "positioning", label: "世界观定位" },
  { kind: "style", label: "风格约定" },
] as const;

/** 指导类模板（项目内唯一；与后端 GUIDE_KINDS 同口径，F15 类型学扩展时同步）。 */
const GUIDE_KINDS = new Set(TEMPLATES.map((t) => t.kind));

export function MemoryDocsArea({
  docs,
  loading,
  error,
  onRetry,
  onCreate,
  onDeleteDoc,
  creating,
  projectId,
}: {
  docs: { id: string; kind: string; title: string; updated_at: string; preview: string }[];
  loading: boolean;
  error: { problem: string; fix: string } | null;
  onRetry: () => void;
  onCreate: (kind: string) => void;
  /** 两击确认后的删除回调（store 刷新由调用方完成）。 */
  onDeleteDoc: (docId: string) => void;
  creating: boolean;
  projectId: string;
}) {
  const [editingDocId, setEditingDocId] = useState<string | null>(null);
  // 两击轻确认：第一次点击进入待确认态（3s 超时自动还原），再点执行删除
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const deleteTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (deleteTimer.current) clearTimeout(deleteTimer.current);
    },
    [],
  );

  const handleDeleteClick = (docId: string) => {
    if (pendingDeleteId === docId) {
      if (deleteTimer.current) clearTimeout(deleteTimer.current);
      setPendingDeleteId(null);
      onDeleteDoc(docId);
      return;
    }
    setPendingDeleteId(docId);
    deleteTimer.current = setTimeout(() => setPendingDeleteId(null), 3000);
  };

  return (
    <GlassPanel className="flex min-h-0 flex-col p-3" data-testid="memory-docs-area">
      <div className="flex items-center justify-between px-1">
        <p className="text-xs font-medium text-slate-500 dark:text-slate-400">📚 记忆文档</p>
        <div className="flex gap-1">
          {TEMPLATES.map(({ kind, label }) => {
            const exists = docs.some((d) => d.kind === kind);
            return (
              <Button
                key={kind}
                variant="ghost"
                className="px-2 py-0.5 text-xs"
                disabled={creating || (GUIDE_KINDS.has(kind) && exists)}
                title={exists ? "每项目仅一份指导文档" : undefined}
                onClick={() => onCreate(kind)}
                data-testid={`memory-doc-create-${kind}`}
              >
                ＋{label}
              </Button>
            );
          })}
        </div>
      </div>
      <p className="px-1 text-[11px] text-slate-400 dark:text-slate-500">指导类每项目仅一份</p>
      {error ? (
        <div className="mt-2">
          <ErrorStrip problem={error.problem} fix={error.fix} onRetry={onRetry} testId="memory-doc-error" />
        </div>
      ) : null}
      {loading && docs.length === 0 ? (
        <p className="px-2 py-4 text-center text-xs text-slate-400 dark:text-slate-500">加载中…</p>
      ) : null}
      {!loading && docs.length === 0 && !error ? (
        <p className="px-2 py-4 text-center text-xs text-slate-400 dark:text-slate-500">
          还没有记忆文档——用上方模板创建第一份，Agent 会在对话中读取它们。
        </p>
      ) : null}
      <ul className="mt-2 flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto">
        {docs.map((doc) => (
          <li key={doc.id} className="group relative">
            <button
              type="button"
              data-testid="memory-doc-card"
              onClick={() => setEditingDocId(doc.id)}
              className="w-full rounded-xl bg-white/50 px-3 py-2 pr-8 text-left ring-1 ring-black/5 transition-all duration-150 hover:-translate-y-0.5 hover:shadow-md dark:bg-slate-800/50 dark:ring-white/10"
            >
              <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-200">{doc.title}</p>
              <p className="mt-0.5 line-clamp-2 text-xs text-slate-500 dark:text-slate-400">
                {doc.preview || "（空文档）"}
              </p>
              <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                {new Date(doc.updated_at).toLocaleString("zh-CN", { dateStyle: "short", timeStyle: "short" })}
              </p>
            </button>
            <button
              type="button"
              data-testid="memory-doc-delete"
              aria-label={`删除文档 ${doc.title}`}
              onClick={() => handleDeleteClick(doc.id)}
              className={`absolute top-2 right-2 rounded px-1 text-xs transition-all duration-150 group-hover:opacity-100 focus-visible:opacity-100 ${
                pendingDeleteId === doc.id
                  ? "text-red-500 opacity-100 dark:text-red-400"
                  : "text-slate-400 opacity-0 hover:text-red-500 dark:text-slate-500"
              }`}
            >
              {pendingDeleteId === doc.id ? "确认？" : "🗑"}
            </button>
          </li>
        ))}
      </ul>
      {editingDocId ? (
        <DocEditor
          docId={editingDocId}
          onClose={() => setEditingDocId(null)}
          onSaved={() => {
            /* 列表刷新由 store.updateDocSection 完成 */
            void projectId;
          }}
        />
      ) : null}
    </GlassPanel>
  );
}
