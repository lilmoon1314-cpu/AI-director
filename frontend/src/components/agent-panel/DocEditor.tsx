/**
 * DocEditor：记忆文档段级编辑 modal（F10，OQ-2 裁决——HTML 分段模板取代
 * markdown 方案，DECISIONS 2026-09-06）。段级表单保存（PATCH + CAS 乐观锁，
 * 版本冲突呈现三要素）；「预览页面」新标签打开自包含 HTML 页。
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { api, type MemoryDocRead } from "../../api/client";
import { ApiError } from "../../api/client";
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
      setError(null);
    } catch (cause) {
      if (seq !== loadSeq.current) return;
      setError({ problem: cause instanceof ApiError ? cause.problem : "文档加载失败", fix: cause instanceof ApiError ? cause.fix : "关闭后重试" });
    }
  }, [docId]);

  useEffect(() => {
    void load();
  }, [load]);

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

  return (
    <Modal title={`编辑 · ${doc?.title ?? "…"}`} testId="doc-editor">
      {error ? (
        <div className="mb-3 rounded-xl border border-red-200 bg-red-50/80 p-3 text-xs dark:border-red-900 dark:bg-red-950/60" role="alert" data-testid="doc-editor-error">
          <p className="font-medium text-red-700 dark:text-red-400">{error.problem}</p>
          <p className="mt-0.5 text-red-600 dark:text-red-400">修复：{error.fix}</p>
        </div>
      ) : null}
      <div className="flex flex-col gap-4">
        {(doc?.sections ?? []).map((section) => {
          const draft = drafts[section.id];
          return (
            <div key={section.id}>
              <TextArea
                label={`${section.seq}. ${section.title}`}
                id={`doc-section-${section.id}`}
                value={draft?.content ?? ""}
                rows={3}
                onChange={(e) =>
                  setDrafts({
                    ...drafts,
                    [section.id]: { ...draft, content: e.target.value, dirty: true },
                  })
                }
              />
              <div className="mt-1 flex items-center justify-between">
                <span className="text-xs text-slate-400 dark:text-slate-500">
                  v{section.version} · {section.updated_by === "user" ? "作者" : "Agent"} 更新
                </span>
                <Button
                  variant="ghost"
                  className="px-3 py-1 text-xs"
                  disabled={saving || !draft?.dirty}
                  data-testid={`doc-section-save-${section.seq}`}
                  onClick={() => void saveSection(section.id)}
                >
                  保存本段
                </Button>
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-5 flex items-center justify-between">
        <a
          href={api.memoryDocPageUrl(docId)}
          target="_blank"
          rel="noreferrer"
          className="text-xs text-slate-500 underline-offset-2 hover:underline dark:text-slate-400"
          data-testid="doc-preview-link"
        >
          预览 HTML 页面 ↗
        </a>
        <div className="flex gap-2">
          <Button variant="ghost" className="px-3 py-1 text-xs" onClick={() => void load()}>
            重新加载
          </Button>
          <Button className="px-3 py-1 text-xs" onClick={onClose} data-testid="doc-editor-close">
            完成
          </Button>
        </div>
      </div>
    </Modal>
  );
}
