/**
 * ProjectSwitcher：工作台顶栏项目切换器（F11，DESIGN.md §4.3）。
 * - 下拉列出全部项目（名称 + 实体数）+「＋ 新建项目」「管理全部项目」回首屏；
 * - 选中即切换（导航 /projects/:id/graph）；当前项目高亮标注，重复点击为无操作；
 * - 切换项目的数据重置换机由目标项目页面挂载驱动（DESIGN.md §4.4/§7）。
 */

import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useProjectStore } from "../../stores/projectStore";

export function ProjectSwitcher() {
  const navigate = useNavigate();
  const projects = useProjectStore((s) => s.projects);
  const currentProjectId = useProjectStore((s) => s.currentProjectId);
  const loadProjects = useProjectStore((s) => s.loadProjects);
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  // 点击组件外部收起下拉
  useEffect(() => {
    if (!open) return;
    const onDocMouseDown = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocMouseDown);
    return () => document.removeEventListener("mousedown", onDocMouseDown);
  }, [open]);

  const current = projects.find((p) => p.id === currentProjectId);

  const switchTo = (projectId: string) => {
    setOpen(false);
    if (projectId === currentProjectId) return; // 防误触：当前项目为无操作
    void navigate(`/projects/${projectId}/graph`);
  };

  return (
    <div ref={boxRef} className="relative" data-testid="project-switcher">
      <button
        type="button"
        data-testid="project-switcher-button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-sm font-medium text-slate-800 transition-colors duration-150 hover:bg-white/60 dark:text-slate-200 dark:hover:bg-slate-800/60"
      >
        <span className="max-w-48 truncate">{current?.name ?? "选择项目…"}</span>
        <span aria-hidden className="text-xs text-slate-500 dark:text-slate-400">
          ▾
        </span>
      </button>
      {open ? (
        <div
          role="listbox"
          aria-label="切换项目"
          className="absolute left-0 top-10 z-30 flex w-56 flex-col rounded-xl bg-white/95 p-1 text-sm shadow-lg ring-1 ring-black/5 backdrop-blur dark:bg-slate-900/95 dark:ring-white/10"
        >
          {projects.map((p) => (
            <button
              key={p.id}
              type="button"
              role="option"
              aria-selected={p.id === currentProjectId}
              data-testid={`switch-to-${p.id}`}
              onClick={() => switchTo(p.id)}
              className={`flex flex-col items-start rounded-lg px-3 py-1.5 text-left transition-colors duration-150 ${
                p.id === currentProjectId
                  ? "bg-white/70 font-medium text-slate-900 dark:bg-slate-800/70 dark:text-slate-100"
                  : "text-slate-700 hover:bg-white/60 dark:text-slate-300 dark:hover:bg-slate-800/60"
              }`}
            >
              <span className="flex w-full items-center gap-1">
                <span className="truncate">{p.name}</span>
                {p.id === currentProjectId ? (
                  <span className="ml-auto text-[10px] text-slate-400">当前</span>
                ) : null}
              </span>
              <span className="text-xs text-slate-400 dark:text-slate-500">
                {p.entity_count} 实体
              </span>
            </button>
          ))}
          <div className="my-1 h-px bg-slate-200/70 dark:bg-slate-700/70" aria-hidden />
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              void navigate("/projects");
            }}
            className="rounded-lg px-3 py-1.5 text-left text-slate-600 hover:bg-white/60 dark:text-slate-300 dark:hover:bg-slate-800/60"
          >
            ＋ 新建 / 管理全部项目
          </button>
        </div>
      ) : null}
    </div>
  );
}
