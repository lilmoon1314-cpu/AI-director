/**
 * DocEditor：记忆文档段级编辑「大悬浮弹窗」（F13，DESIGN.md §13.1——验收反馈
 * 「点击编辑默认打开大弹窗而非原地小框」）。max-w-5xl 三栏布局：左栏段列表
 * （当前段高亮）+ 右栏当前段编辑表单（PATCH + CAS 乐观锁）+ 底部 iframe 实时
 * 预览（lib/docPreview 全转义渲染，含未保存草稿；**html 替代 md 原则**，
 * OQ-2 裁决）。Esc 关闭：无脏输入直接关；有脏输入先出确认条（继续编辑/放弃）。
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { api, type MemoryDocRead } from "../../api/client";
import { ApiError } from "../../api/client";
import { renderDocPreviewHtml } from "../../lib/docPreview";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";
import { TextArea } from "../ui/Field";

interface Draft {
  sectionId: string;
  content: string;
  version: number;
  dirty: boolean;
}

export function DocEditor({
  docId,
  onClose,
  onSaved,
}: {
  docId: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [doc, setDoc] = useState<MemoryDocRead | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [dirtyConfirm, setDirtyConfirm] = useState(false);
  const [error, setError] = useState<{ problem: string; fix: string } | null>(null);
  const [saving, setSaving] = useState(false);
  // 载入序号：StrictMode 双挂载/重复保存后的并发载入只应用最新一次（防旧响应覆盖用户输入）
  const loadSeq = useRef(0);

  const load = useCallback(async () => {
    const seq = ++loadSeq.current;
    try {
      const fresh = await api.getMemoryDoc(docId);
      if (seq !== loadSeq.current) return;
      setDoc(fresh);
      const next: Record<string, Draft> = {};
      for (const section of fresh.sections ?? []) {
        next[section.id] = { sectionId: section.id, content: section.content, version: section.version, dirty: false };
      }
      setDrafts(next);
      setSelectedId((prev) => (prev && next[prev] ? prev : (fresh.sections?.[0]?.id ?? null)));
      setError(null);
    } catch (cause) {
      if (seq !== loadSeq.current) return;
      setError({ problem: cause instanceof ApiError ? cause.problem : "文档加载失败", fix: cause instanceof ApiError ? cause.fix : "关闭后重试" });
    }
  }, [docId]);

  useEffect(() => {
    void load();
  }, [load]);

  const sections = doc?.sections ?? [];
  const hasDirty = Object.values(drafts).some((d) => d.dirty);
  const selected = selectedId ? (drafts[selectedId] ?? null) : null;
  const selectedSection = sections.find((s) => s.id === selectedId) ?? null;

  const requestClose = useCallback(() => {
    if (hasDirty && !dirtyConfirm) {
      setDirtyConfirm(true);
      return;
    }
    onClose();
  }, [hasDirty, dirtyConfirm, onClose]);

  // Esc 关闭（DESIGN §13.1）：有脏输入先确认，无脏直接关
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      e.preventDefault();
      requestClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [requestClose]);

  const saveSection = async (sectionId: string) => {
    const draft = drafts[sectionId];
    if (!draft) return;
    setSaving(true);
    try {
      await api.updateMemoryDocSection(docId, sectionId, {
        content: draft.content,
        expected_version: draft.version,
      });
      await load();
      onSaved();
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 409) {
        setError({
          problem: "该段刚被其他人（或 Agent）修改过（版本冲突）",
          fix: "点击「重新加载」获取最新内容后再次保存",
        });
      } else {
        setError({
          problem: cause instanceof ApiError ? cause.problem : "保存失败",
          fix: cause instanceof ApiError ? cause.fix : "检查网络后重试",
        });
      }
    } finally {
      setSaving(false);
    }
  };

  const previewHtml = doc
    ? renderDocPreviewHtml(
        doc.title,
        sections.map((s) => ({
          seq: s.seq,
          title: s.title,
          content: drafts[s.id]?.content ?? s.content,
        })),
      )
    : "";

  return (
    <Modal
      title={`编辑 · ${doc?.title ?? "…"}`}
      testId="doc-editor"
      panelClassName="flex max-w-5xl flex-col p-5"
    >
      {error ? (
        <div className="mb-3 rounded-xl border border-red-200 bg-red-50/80 p-3 text-xs dark:border-red-900 dark:bg-red-950/60" role="alert" data-testid="doc-editor-error">
          <p className="font-medium text-red-700 dark:text-red-400">{error.problem}</p>
          <p className="mt-0.5 text-red-600 dark:text-red-400">修复：{error.fix}</p>
        </div>
      ) : null}
      {dirtyConfirm ? (
        <div
          role="alert"
          data-testid="doc-editor-dirty-confirm"
          className="mb-3 flex items-center justify-between rounded-xl border border-amber-300 bg-amber-50/80 p-3 text-xs dark:border-amber-700 dark:bg-amber-950/50"
        >
          <span className="text-amber-700 dark:text-amber-300">有未保存的修改——确定放弃并关闭？</span>
          <span className="flex gap-2">
            <Button
              variant="ghost"
              className="px-3 py-1 text-xs"
              data-testid="doc-editor-dirty-stay"
              onClick={() => setDirtyConfirm(false)}
            >
              继续编辑
            </Button>
            <Button className="px-3 py-1 text-xs" data-testid="doc-editor-dirty-leave" onClick={onClose}>
              放弃更改并关闭
            </Button>
          </span>
        </div>
      ) : null}

      <div className="flex min-h-[50vh] flex-1 gap-4 overflow-hidden">
        {/* 左栏：段列表（当前段高亮，脏段标 *） */}
        <nav className="flex w-44 shrink-0 flex-col gap-1 overflow-y-auto" data-testid="doc-editor-section-list" aria-label="段落列表">
          {sections.map((section) => (
            <button
              key={section.id}
              type="button"
              data-testid={`doc-editor-section-${section.seq}`}
              onClick={() => {
                setSelectedId(section.id);
                setDirtyConfirm(false);
              }}
              className={`rounded-lg px-3 py-2 text-left text-xs transition-colors duration-150 ${
                section.id === selectedId
                  ? "bg-slate-800/90 text-white dark:bg-slate-200 dark:text-slate-900"
                  : "text-slate-600 hover:bg-black/5 dark:text-slate-300 dark:hover:bg-white/10"
              }`}
            >
              <span className="line-clamp-2">
                {section.seq}. {section.title}
                {drafts[section.id]?.dirty ? " *" : ""}
              </span>
            </button>
          ))}
        </nav>

        {/* 右栏：当前段编辑表单（CAS 乐观锁保存） */}
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          {selected && selectedSection ? (
            <>
              <TextArea
                label={`${selectedSection.seq}. ${selectedSection.title}`}
                id={`doc-section-${selectedSection.id}`}
                value={selected.content}
                rows={14}
                onChange={(e) =>
                  setDrafts({
                    ...drafts,
                    [selectedSection.id]: { ...selected, content: e.target.value, dirty: true },
                  })
                }
              />
              <div className="mt-2 flex items-center justify-between">
                <span className="text-xs text-slate-400 dark:text-slate-500">
                  v{selectedSection.version} · {selectedSection.updated_by === "user" ? "作者" : "Agent"} 更新
                </span>
                <Button
                  variant="ghost"
                  className="px-3 py-1 text-xs"
                  disabled={saving || !selected.dirty}
                  data-testid={`doc-section-save-${selectedSection.seq}`}
                  onClick={() => void saveSection(selectedSection.id)}
                >
                  保存本段
                </Button>
              </div>
            </>
          ) : (
            <p className="m-auto text-xs text-slate-400 dark:text-slate-500">左侧选择要编辑的段落。</p>
          )}
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between">
        <a
          href={api.memoryDocPageUrl(docId)}
          target="_blank"
          rel="noreferrer"
          className="text-xs text-slate-500 underline-offset-2 hover:underline dark:text-slate-400"
          data-testid="doc-preview-link"
        >
          新标签打开服务端渲染页 ↗
        </a>
        <div className="flex gap-2">
          <Button variant="ghost" className="px-3 py-1 text-xs" onClick={() => void load()}>
            重新加载
          </Button>
          <Button className="px-3 py-1 text-xs" onClick={requestClose} data-testid="doc-editor-close">
            完成
          </Button>
        </div>
      </div>
      {/* 底部：实时预览（srcDoc 含未保存草稿；全转义 + sandbox 禁脚本） */}
      <iframe
        title="记忆文档实时预览"
        data-testid="doc-editor-preview"
        sandbox=""
        srcDoc={previewHtml}
        className="mt-2 h-64 w-full rounded-xl border border-black/10 bg-slate-950 dark:border-white/10"
      />
    </Modal>
  );
}
