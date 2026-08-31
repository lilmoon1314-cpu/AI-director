/**
 * PerspectiveSwitcher：三视角一键切换（F06）。
 * - 三段按钮组（aria-pressed 标注当前视角：作者/角色/观众）；
 * - character 视角显示角色下拉（数据源 GET /api/entities?type=character，懒加载一次）；
 *   未选角色不发起图请求——与后端 403 missing_character_id 对应的前端拦截（边界：缺参零请求）；
 * - 切换/选择角色即触发 loadGraph 按视角重载；回切 character 时已选角色保留并直接加载。
 * 视角过滤本体在后端（F04），本组件只负责切换交互。
 */

import { useEffect, useState } from "react";

import { useGraphStore } from "../../stores/graphStore";
import {
  PERSPECTIVE_LABELS,
  usePerspectiveStore,
  type Perspective,
} from "../../stores/perspectiveStore";

const PERSPECTIVES: readonly Perspective[] = ["author", "character", "audience"];

const SELECT_CLASSES =
  "w-full rounded-xl border border-slate-300 bg-white/70 px-3 py-2 text-sm text-slate-900 transition-colors duration-150 focus:border-slate-500 focus:outline-none dark:border-slate-600 dark:bg-slate-800/70 dark:text-slate-100 dark:focus:border-slate-400";

export function PerspectiveSwitcher() {
  const perspective = usePerspectiveStore((s) => s.perspective);
  const characterId = usePerspectiveStore((s) => s.characterId);
  const characters = usePerspectiveStore((s) => s.characters);
  const setPerspective = usePerspectiveStore((s) => s.setPerspective);
  const setCharacterId = usePerspectiveStore((s) => s.setCharacterId);
  const loadCharacters = usePerspectiveStore((s) => s.loadCharacters);
  const loadGraph = useGraphStore((s) => s.loadGraph);
  const [selectError, setSelectError] = useState<string | null>(null);

  // 角色下拉数据源兜底：挂载即拉取（store 内幂等，已加载则跳过）
  useEffect(() => {
    void loadCharacters().catch(() => {
      // 拉取失败不阻塞主流程——下拉为空时给出可修复提示
      setSelectError("角色列表加载失败，请确认后端服务后重试");
    });
  }, [loadCharacters]);

  const switchTo = (next: Perspective) => {
    setPerspective(next);
    setSelectError(null);
    if (next === "character" && !usePerspectiveStore.getState().characterId) {
      return; // 角色视角未选角色：不发请求（后端此情形必 403，前端直接拦截）
    }
    void loadGraph();
  };

  const onCharacterChange = (id: string) => {
    setCharacterId(id || null);
    setSelectError(null);
    if (id) void loadGraph();
  };

  return (
    <div className="flex flex-col gap-2" data-testid="perspective-switcher">
      <div
        role="group"
        aria-label="视角切换"
        className="flex gap-1 rounded-xl bg-white/50 p-1 dark:bg-slate-800/50"
      >
        {PERSPECTIVES.map((p) => {
          const active = perspective === p;
          return (
            <button
              key={p}
              type="button"
              data-testid={`perspective-${p}`}
              aria-pressed={active}
              onClick={() => switchTo(p)}
              className={`flex-1 rounded-lg px-2 py-1.5 text-sm font-medium transition-colors duration-150 ${
                active
                  ? "bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900"
                  : "text-slate-600 hover:bg-white/60 dark:text-slate-300 dark:hover:bg-slate-800/60"
              }`}
            >
              {PERSPECTIVE_LABELS[p]}
            </button>
          );
        })}
      </div>
      {perspective === "character" ? (
        <div className="flex flex-col gap-1">
          <label
            htmlFor="perspective-character"
            className="text-xs font-medium text-slate-700 dark:text-slate-300"
          >
            视角角色
          </label>
          <select
            id="perspective-character"
            data-testid="character-select"
            className={SELECT_CLASSES}
            value={characterId ?? ""}
            onChange={(e) => onCharacterChange(e.target.value)}
          >
            <option value="">请选择角色…</option>
            {characters.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          {selectError ? (
            <p role="alert" className="text-xs text-red-600 dark:text-red-400">
              {selectError}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
