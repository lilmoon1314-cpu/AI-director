import { useState } from "react";

import { api, type ProjectMemoryRead } from "../../api/client";
import { useAgentStore } from "../../stores/agentStore";
import { Button } from "../ui/Button";
import { ErrorStrip } from "../ui/ErrorStrip";
import { GlassPanel } from "../ui/GlassPanel";

const STATUS_LABEL: Record<string, string> = {
  proposed: "待确认",
  accepted: "已接受",
  disputed: "有冲突",
  superseded: "已替代",
};

const KINDS = ["constraint", "decision", "preference", "open_task", "exact_reference"] as const;

export function ProjectMemoriesArea({ projectId }: { projectId: string }) {
  const memories = useAgentStore((state) => state.memories);
  const loading = useAgentStore((state) => state.memoriesLoading);
  const error = useAgentStore((state) => state.memoriesError);
  const load = useAgentStore((state) => state.loadMemories);
  const create = useAgentStore((state) => state.createMemory);
  const update = useAgentStore((state) => state.updateMemory);
  const accept = useAgentStore((state) => state.acceptMemory);
  const resolve = useAgentStore((state) => state.resolveMemory);
  const forget = useAgentStore((state) => state.forgetMemory);
  const [editing, setEditing] = useState<ProjectMemoryRead | null>(null);
  const [content, setContent] = useState("");
  const [subjectKey, setSubjectKey] = useState("");
  const [kind, setKind] = useState<(typeof KINDS)[number]>("decision");
  const [forgetPreview, setForgetPreview] = useState<{ id: string; text: string } | null>(null);

  const resetEditor = () => {
    setEditing(null);
    setContent("");
    setSubjectKey("");
    setKind("decision");
  };

  const save = async () => {
    if (!content.trim() || !subjectKey.trim()) return;
    const input = { kind, subject_key: subjectKey.trim(), content: content.trim() };
    if (editing) await update(projectId, editing, input);
    else await create(projectId, input);
    resetEditor();
  };

  const previewForget = async (memory: ProjectMemoryRead) => {
    if (forgetPreview?.id === memory.id) {
      await forget(projectId, memory);
      setForgetPreview(null);
      return;
    }
    const preview = await api.projectMemoryDeletionPreview(memory.id);
    setForgetPreview({
      id: memory.id,
      text: `${preview.effect} 来源 ${preview.source_count} 项。再次点击确认。`,
    });
  };

  return (
    <GlassPanel className="flex min-h-0 flex-col p-3" data-testid="project-memories-area">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400">🧠 跨会话记忆</p>
          <p className="text-[11px] text-slate-400">只有“已接受”内容会进入新会话</p>
        </div>
        <Button variant="ghost" className="px-2 py-0.5 text-xs" onClick={resetEditor}>
          ＋手动记忆
        </Button>
      </div>
      {error ? (
        <div className="mt-2">
          <ErrorStrip
            problem={error.problem}
            fix={error.fix}
            onRetry={() => void load(projectId, true)}
            testId="project-memory-error"
          />
        </div>
      ) : null}
      <div className="mt-2 grid gap-1">
        <select
          aria-label="记忆类型"
          value={kind}
          onChange={(event) => setKind(event.target.value as (typeof KINDS)[number])}
          className="rounded border border-slate-300 bg-white px-2 py-1 text-xs dark:border-slate-600 dark:bg-slate-900"
        >
          {KINDS.map((value) => <option key={value}>{value}</option>)}
        </select>
        <input
          aria-label="记忆主题"
          value={subjectKey}
          onChange={(event) => setSubjectKey(event.target.value)}
          placeholder="主题，例如：结局"
          className="rounded border border-slate-300 bg-white px-2 py-1 text-xs dark:border-slate-600 dark:bg-slate-900"
        />
        <textarea
          aria-label="记忆内容"
          value={content}
          onChange={(event) => setContent(event.target.value)}
          placeholder="写下需要跨会话遵守的决定或偏好"
          className="min-h-14 resize-y rounded border border-slate-300 bg-white px-2 py-1 text-xs dark:border-slate-600 dark:bg-slate-900"
        />
        <Button className="py-1 text-xs" disabled={!content.trim() || !subjectKey.trim()} onClick={() => void save()}>
          {editing ? "保存修改" : "保存为作者决定"}
        </Button>
      </div>
      {loading && memories.length === 0 ? <p className="py-3 text-center text-xs text-slate-400">加载中…</p> : null}
      <ul className="mt-2 max-h-60 space-y-2 overflow-y-auto">
        {memories.map((memory) => (
          <li key={memory.id} className="rounded-lg bg-white/50 p-2 text-xs ring-1 ring-black/5 dark:bg-slate-800/50 dark:ring-white/10">
            <div className="flex items-center gap-1">
              <span className={memory.status === "disputed" ? "text-amber-600" : "text-slate-500"}>
                {STATUS_LABEL[memory.status] ?? memory.status}
              </span>
              <span className="truncate text-slate-400">{memory.subject_key}</span>
            </div>
            <p className="mt-1 whitespace-pre-wrap text-slate-700 dark:text-slate-200">{memory.content}</p>
            <p className="mt-1 text-[10px] text-slate-400">
              {memory.origin === "author_decision" ? "作者决定" : "Agent 建议"} · v{memory.version} · 来源 {memory.sources?.length ?? 0}
            </p>
            {forgetPreview?.id === memory.id ? <p className="mt-1 text-[10px] text-red-500">{forgetPreview.text}</p> : null}
            <div className="mt-1 flex flex-wrap gap-1">
              {memory.status === "proposed" ? <Button variant="ghost" className="px-2 py-0.5 text-xs" onClick={() => void accept(projectId, memory)}>接受</Button> : null}
              {memory.status === "disputed" ? <Button variant="ghost" className="px-2 py-0.5 text-xs" onClick={() => void resolve(projectId, memory)}>采用此项</Button> : null}
              {memory.status !== "superseded" ? (
                <Button
                  variant="ghost"
                  className="px-2 py-0.5 text-xs"
                  onClick={() => {
                    setEditing(memory);
                    setContent(memory.content);
                    setSubjectKey(memory.subject_key);
                    setKind(memory.kind);
                  }}
                >
                  编辑
                </Button>
              ) : null}
              <Button variant="ghost" className="px-2 py-0.5 text-xs text-red-500" onClick={() => void previewForget(memory)}>
                {forgetPreview?.id === memory.id ? "确认遗忘" : "遗忘"}
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </GlassPanel>
  );
}
