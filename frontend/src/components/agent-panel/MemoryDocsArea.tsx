/**
 * 记忆文档卡片区（F10，DESIGN.md §5.4 左栏底部「📚 记忆文档」区）：
 * 文档卡（名称+更新时间+首行摘要，memory-doc-card）＋新建两个内置模板
 * （世界观定位 / 风格约定）；点击卡片打开段级编辑 modal。
 */

import { useState } from "react";

import { Button } from "../ui/Button";
import { ErrorStrip } from "../ui/ErrorStrip";
import { GlassPanel } from "../ui/GlassPanel";
import { DocEditor } from "./DocEditor";

const TEMPLATES = [
  { kind: "positioning", label: "世界观定位" },
  { kind: "style", label: "风格约定" },
] as const;

export function MemoryDocsArea({
  docs,
  loading,
  error,
  onRetry,
  onCreate,
  creating,
  projectId,
}: {
  docs: { id: string; title: string; updated_at: string; preview: string }[];
  loading: boolean;
  error: { problem: string; fix: string } | null;
  onRetry: () => void;
  onCreate: (kind: string) => void;
  creating: boolean;
  projectId: string;
}) {
  const [editingDocId, setEditingDocId] = useState<string | null>(null);

  return (
    <GlassPanel className="flex min-h-0 flex-col p-3" data-testid="memory-docs-area">
      <div className="flex items-center justify-between px-1">
        <p className="text-xs font-medium text-slate-500 dark:text-slate-400">📚 记忆文档</p>
        <div className="flex gap-1">
          {TEMPLATES.map(({ kind, label }) => (
            <Button
              key={kind}
              variant="ghost"
              className="px-2 py-0.5 text-xs"
              disabled={creating}
              onClick={() => onCreate(kind)}
              data-testid={`memory-doc-create-${kind}`}
            >
              ＋{label}
            </Button>
          ))}
        </div>
      </div>
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
          <li key={doc.id}>
            <button
              type="button"
              data-testid="memory-doc-card"
              onClick={() => setEditingDocId(doc.id)}
              className="w-full rounded-xl bg-white/50 px-3 py-2 text-left ring-1 ring-black/5 transition-all duration-150 hover:-translate-y-0.5 hover:shadow-md dark:bg-slate-800/50 dark:ring-white/10"
            >
              <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-200">{doc.title}</p>
              <p className="mt-0.5 line-clamp-2 text-xs text-slate-500 dark:text-slate-400">
                {doc.preview || "（空文档）"}
              </p>
              <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                {new Date(doc.updated_at).toLocaleString("zh-CN", { dateStyle: "short", timeStyle: "short" })}
              </p>
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
