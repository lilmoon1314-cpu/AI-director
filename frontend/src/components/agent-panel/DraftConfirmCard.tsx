/**
 * 草案确认卡（F10，DESIGN.md §5.4 草案确认卡）：propose 产物内联渲染——
 * kind 徽标 + payload 摘要 + [确认写入][放弃]；确认后由 store 广播图谱失效。
 */

import type { DraftItem } from "../../api/client";
import { Button } from "../ui/Button";

const KIND_LABELS: Record<DraftItem["kind"], string> = {
  entity: "实体",
  relation: "关系",
};

function summarizePayload(draft: DraftItem): string {
  const p = draft.payload as Record<string, unknown>;
  const parts: string[] = [];
  if (typeof p.type === "string") parts.push(`类型 ${p.type}`);
  if (typeof p.name === "string") parts.push(`名称 ${p.name}`);
  if (typeof p.source === "string" && typeof p.target === "string") {
    parts.push(`${String(p.source)} → ${String(p.target)}`);
  }
  if (typeof p.description === "string" && p.description) parts.push(p.description);
  return parts.join(" · ") || JSON.stringify(p).slice(0, 80);
}

export function DraftConfirmCard({
  drafts,
  confirming,
  onConfirm,
  onDiscard,
}: {
  drafts: DraftItem[];
  confirming: boolean;
  onConfirm: () => void;
  onDiscard: () => void;
}) {
  if (drafts.length === 0) return null;
  return (
    <div className="mx-4 mb-2 rounded-2xl ring-1 ring-black/5 bg-white/80 p-3 shadow-sm backdrop-blur dark:ring-white/10 dark:bg-slate-800/80" data-testid="agent-draft-card">
      <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
        写入草案（{drafts.length} 项）——确认后落库
      </p>
      <ul className="mt-2 flex flex-col gap-2">
        {drafts.map((draft) => (
          <li
            key={draft.draft_id}
            className="rounded-xl bg-slate-50 px-3 py-2 text-sm dark:bg-slate-900/60"
            data-testid="agent-draft-item"
          >
            <span className="mr-2 inline-block rounded-full bg-slate-200 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-700 dark:text-slate-300">
              {KIND_LABELS[draft.kind]}
            </span>
            <span className="text-slate-800 dark:text-slate-200">{summarizePayload(draft)}</span>
            {draft.summary ? (
              <span className="mt-0.5 block text-xs text-slate-500 dark:text-slate-400">{draft.summary}</span>
            ) : null}
          </li>
        ))}
      </ul>
      <div className="mt-3 flex justify-end gap-2">
        <Button variant="ghost" className="px-3 py-1 text-xs" onClick={onDiscard} data-testid="agent-draft-discard">
          放弃
        </Button>
        <Button
          className="px-3 py-1 text-xs"
          disabled={confirming}
          onClick={onConfirm}
          data-testid="agent-draft-confirm"
        >
          {confirming ? "写入中…" : "确认写入"}
        </Button>
      </div>
    </div>
  );
}
