/**
 * 项目首屏（F11，DESIGN.md §5.1）：多项目工作台入口。
 * - 毛玻璃项目卡片网格（名称 + 实体/关系计数 + 最近编辑），hover 微放大，点击进入工作台；
 * - 搜索（前端过滤名称/描述）+「＋ 新建项目」虚线卡（modal 表单：名称必填/一句话描述）；
 * - 卡片 ⋯ 菜单：重命名（modal）/ 删除（危险 modal：后果清单 + 输入项目名确认；
 *   默认项目不可删除——后端 422，前端以菜单禁用表达）；
 * - 状态矩阵：loading 骨架卡 / 空项目引导 / 错误条三要素 + 重试。
 */

import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError, type ProjectRead } from "../api/client";
import { Button } from "../components/ui/Button";
import { GlassPanel } from "../components/ui/GlassPanel";
import { TextArea, TextInput } from "../components/ui/Field";
import { useProjectStore } from "../stores/projectStore";

/** 最近编辑时间的轻量中文相对描述（MVP：天粒度即可）。 */
function describeActivity(updatedAt: string): string {
  const days = Math.floor((Date.now() - new Date(updatedAt).getTime()) / 86_400_000);
  if (days <= 0) return "今天";
  if (days === 1) return "昨天";
  if (days < 7) return `${days} 天前`;
  if (days < 30) return `${Math.floor(days / 7)} 周前`;
  return new Date(updatedAt).toLocaleDateString("zh-CN");
}

export function ProjectPicker() {
  const navigate = useNavigate();
  const projects = useProjectStore((s) => s.projects);
  const loading = useProjectStore((s) => s.loading);
  const error = useProjectStore((s) => s.error);
  const errorFix = useProjectStore((s) => s.errorFix);
  const loadProjects = useProjectStore((s) => s.loadProjects);

  const [query, setQuery] = useState("");
  const [creating, setCreating] = useState(false);
  const [renaming, setRenaming] = useState<ProjectRead | null>(null);
  const [deleting, setDeleting] = useState<ProjectRead | null>(null);

  useEffect(() => {
    // 首屏挂载即拉取（store 缓存 force=false；写操作后由各流程显式 force 刷新）
    void loadProjects();
  }, [loadProjects]);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return projects;
    return projects.filter(
      (p) =>
        p.name.toLowerCase().includes(needle) || p.description.toLowerCase().includes(needle),
    );
  }, [projects, query]);

  return (
    <div
      className="flex min-h-screen w-full flex-col items-center gap-8 bg-slate-100 px-6 py-16 dark:bg-slate-950"
      data-testid="project-picker"
    >
      <header className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
          ✦ 影视世界观工作台
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          选择一个项目进入它的世界，或创建新世界
        </p>
      </header>

      <TextInput
        id="project-search"
        label="搜索项目"
        value={query}
        placeholder="按名称或描述过滤…"
        onChange={(e) => setQuery(e.target.value)}
      />

      {error ? (
        <GlassPanel className="w-full max-w-3xl p-5">
          <p role="alert" className="text-sm font-medium text-red-700 dark:text-red-400">
            {error}
          </p>
          <p className="mt-1 text-xs text-red-600 dark:text-red-400">修复：{errorFix}</p>
          <div className="mt-3">
            <Button onClick={() => void loadProjects(true)}>重试</Button>
          </div>
        </GlassPanel>
      ) : loading && projects.length === 0 ? (
        <div className="grid w-full max-w-4xl grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-3">
          {Array.from({ length: 4 }, (_, i) => (
            <div
              key={i}
              className="h-40 animate-pulse rounded-2xl bg-white/60 shadow-sm dark:bg-slate-800/60"
              data-testid="project-skeleton"
            />
          ))}
        </div>
      ) : projects.length === 0 ? (
        <GlassPanel className="flex w-full max-w-md flex-col items-center gap-4 p-10 text-center">
          <p className="text-base font-medium text-slate-800 dark:text-slate-200">
            创建你的第一个世界观项目
          </p>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            每个项目拥有独立的图谱、资产与 Agent 记忆
          </p>
          <Button data-testid="project-create" onClick={() => setCreating(true)}>
            ＋ 新建项目
          </Button>
        </GlassPanel>
      ) : (
        <div className="grid w-full max-w-4xl grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-3">
          {visible.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onOpen={() => navigate(`/projects/${project.id}/graph`)}
              onRename={() => setRenaming(project)}
              onDelete={() => setDeleting(project)}
            />
          ))}
          <button
            type="button"
            data-testid="project-create"
            onClick={() => setCreating(true)}
            className="flex min-h-40 flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-slate-300 text-slate-500 transition-all duration-150 hover:-translate-y-1 hover:border-slate-400 hover:text-slate-700 dark:border-slate-700 dark:text-slate-400 dark:hover:border-slate-500 dark:hover:text-slate-200"
          >
            <span className="text-2xl" aria-hidden>
              ＋
            </span>
            <span className="text-sm font-medium">新建项目</span>
          </button>
        </div>
      )}

      {creating ? (
        <ProjectFormModal
          title="新建项目"
          confirmLabel="创建并进入"
          onClose={() => setCreating(false)}
          onSubmit={async (name, description) => {
            const created = await useProjectStore.getState().createProject({ name, description });
            await loadProjects(true);
            navigate(`/projects/${created.id}/graph`);
          }}
        />
      ) : null}
      {renaming ? (
        <ProjectFormModal
          title="重命名项目"
          confirmLabel="保存"
          initialName={renaming.name}
          initialDescription={renaming.description}
          onClose={() => setRenaming(null)}
          onSubmit={async (name, description) => {
            await useProjectStore.getState().updateProject(renaming.id, { name, description });
            await loadProjects(true);
          }}
        />
      ) : null}
      {deleting ? <DeleteProjectModal project={deleting} onClose={() => setDeleting(null)} /> : null}
    </div>
  );
}

function ProjectCard({
  project,
  onOpen,
  onRename,
  onDelete,
}: {
  project: ProjectRead;
  onOpen: () => void;
  onRename: () => void;
  onDelete: () => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const isDefault = project.id === "project-default";

  return (
    <div
      data-testid={`project-card-${project.id}`}
      className="group relative overflow-hidden rounded-2xl bg-white/80 shadow-sm ring-1 ring-black/5 backdrop-blur transition-all duration-150 hover:-translate-y-1 hover:shadow-md dark:bg-slate-800/80 dark:ring-white/10"
    >
      <button
        type="button"
        onClick={onOpen}
        className="flex h-full w-full flex-col gap-3 p-4 text-left"
        aria-label={`进入项目 ${project.name}`}
      >
        <div
          aria-hidden
          className="h-16 rounded-xl bg-gradient-to-br from-slate-200 to-slate-100 transition-transform duration-150 group-hover:scale-[1.03] dark:from-slate-700 dark:to-slate-800"
        />
        <div>
          <p className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">
            {project.name}
          </p>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            {project.entity_count} 实体 · {project.relation_count} 关系
          </p>
          <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">
            上次编辑 {describeActivity(project.updated_at)}
          </p>
        </div>
      </button>
      <div className="absolute right-2 top-2 opacity-0 transition-opacity duration-150 focus-within:opacity-100 group-hover:opacity-100">
        <button
          type="button"
          aria-label={`项目 ${project.name} 的管理菜单`}
          data-testid={`project-menu-${project.id}`}
          onClick={() => setMenuOpen((v) => !v)}
          className="rounded-lg bg-white/80 px-2 py-0.5 text-sm text-slate-600 shadow-sm dark:bg-slate-900/80 dark:text-slate-300"
        >
          ⋯
        </button>
        {menuOpen ? (
          <div className="absolute right-0 top-8 z-20 flex w-28 flex-col rounded-xl bg-white/95 p-1 text-sm shadow-lg ring-1 ring-black/5 dark:bg-slate-900/95 dark:ring-white/10">
            <button
              type="button"
              onClick={() => {
                setMenuOpen(false);
                onRename();
              }}
              className="rounded-lg px-3 py-1.5 text-left text-slate-700 hover:bg-white/70 dark:text-slate-200 dark:hover:bg-slate-800/70"
            >
              重命名
            </button>
            <button
              type="button"
              disabled={isDefault}
              title={isDefault ? "默认项目不可删除（可改名后使用）" : undefined}
              onClick={() => {
                setMenuOpen(false);
                onDelete();
              }}
              className="rounded-lg px-3 py-1.5 text-left text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:text-slate-400 dark:text-red-400 dark:hover:bg-red-950/40 dark:disabled:text-slate-600"
            >
              删除
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function ProjectFormModal({
  title,
  confirmLabel,
  initialName = "",
  initialDescription = "",
  onClose,
  onSubmit,
}: {
  title: string;
  confirmLabel: string;
  initialName?: string;
  initialDescription?: string;
  onClose: () => void;
  onSubmit: (name: string, description: string) => Promise<void>;
}) {
  const [name, setName] = useState(initialName);
  const [description, setDescription] = useState(initialDescription);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nameValid = name.trim().length > 0;

  return (
    <div
      role="dialog"
      aria-label={title}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-200/70 p-4 backdrop-blur-sm"
    >
      <GlassPanel className="w-full max-w-md p-6">
        <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">{title}</h2>
        <div className="mt-4 flex flex-col gap-3">
          <TextInput
            id="project-form-name"
            label="项目名"
            value={name}
            error={name.length > 0 && !nameValid ? "项目名不能为空白" : undefined}
            onChange={(e) => setName(e.target.value)}
          />
          <TextArea
            id="project-form-description"
            label="一句话描述（可选）"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          {error ? (
            <p role="alert" className="text-xs text-red-600 dark:text-red-400">
              {error}
            </p>
          ) : null}
          <div className="mt-2 flex justify-end gap-2">
            <Button variant="ghost" onClick={onClose} disabled={busy}>
              取消
            </Button>
            <Button
              disabled={!nameValid || busy}
              data-testid="project-form-submit"
              onClick={async () => {
                setBusy(true);
                setError(null);
                try {
                  await onSubmit(name.trim(), description.trim());
                  onClose();
                } catch (cause) {
                  setError(
                    cause instanceof ApiError ? cause.problem : "操作失败，请稍后重试",
                  );
                } finally {
                  setBusy(false);
                }
              }}
            >
              {confirmLabel}
            </Button>
          </div>
        </div>
      </GlassPanel>
    </div>
  );
}

function DeleteProjectModal({ project, onClose }: { project: ProjectRead; onClose: () => void }) {
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const confirmed = typed === project.name;

  return (
    <div
      role="dialog"
      aria-label={`删除项目 ${project.name}`}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-200/70 p-4 backdrop-blur-sm"
    >
      <GlassPanel className="w-full max-w-md p-6">
        <h2 className="text-base font-semibold text-red-700 dark:text-red-400">
          删除项目「{project.name}」
        </h2>
        <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">
          将永久删除该项目的图谱（{project.entity_count} 实体 / {project.relation_count}{" "}
          关系）、项目资产图片与后续的 Agent 记忆和对话；通用参考库不受影响。
        </p>
        <div className="mt-4">
          <TextInput
            id="project-delete-input"
            label={`输入项目名「${project.name}」确认`}
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
          />
        </div>
        {error ? (
          <p role="alert" className="mt-2 text-xs text-red-600 dark:text-red-400">
            {error}
          </p>
        ) : null}
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            取消
          </Button>
          <Button
            variant="danger"
            data-testid="project-delete-confirm"
            disabled={!confirmed || busy}
            onClick={async () => {
              setBusy(true);
              setError(null);
              try {
                await useProjectStore.getState().deleteProject(project.id);
                onClose();
              } catch (cause) {
                setError(cause instanceof ApiError ? cause.problem : "删除失败，请稍后重试");
              } finally {
                setBusy(false);
              }
            }}
          >
            永久删除
          </Button>
        </div>
      </GlassPanel>
    </div>
  );
}
