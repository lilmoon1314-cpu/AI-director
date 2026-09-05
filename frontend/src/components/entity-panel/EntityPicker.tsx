/**
 * EntityPicker：关联实体字段选择器（F07，frontend/CONSTRAINTS API 契约）。
 * - 输入 @（或任意关键字）触发 250ms 防抖检索（GET /api/entities?q=&type=，
 *   refTypes 多于一个时不传 type 由前端过滤）；
 * - 下拉项 = 名称 + 类型 + 当前视角可见性徽标（判定基准：当前 graphStore 图数据
 *   节点集合——author 全量恒可见，audience/character 与画布一致）；
 * - 单值（text）选择回填实体 ID 并显示名称；多值（list）以逗号分隔 ID 存储，
 *   chip 显示名称、可移除；表单态恒为 ID，名称仅显示层（I5 契约）。
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { api, type EntityBrief } from "../../api/client";
import { TYPE_LABELS } from "../../lib/palette";
import { useEntityIndexStore } from "../../stores/entityIndexStore";
import { useGraphStore } from "../../stores/graphStore";

const SEARCH_DEBOUNCE_MS = 250;

interface EntityPickerProps {
  id: string;
  label: string;
  refTypes: string[];
  /** single（text 字段，存单个 id）| multi（list 字段，存逗号分隔 id） */
  mode: "single" | "multi";
  value: string;
  error?: string;
  onChange: (raw: string) => void;
}

export function EntityPicker({ id, label, refTypes, mode, value, error, onChange }: EntityPickerProps) {
  const briefs = useEntityIndexStore((s) => s.briefs);
  const graphNodes = useGraphStore((s) => s.graph.nodes);
  // 当前视角可见集合（图数据节点 id）；graph 引用变化即重建
  const visibleIds = useMemo(() => new Set(graphNodes.map((n) => n.id)), [graphNodes]);
  const nameById = useMemo(() => new Map(briefs.map((b) => [b.id, b.name])), [briefs]);

  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [options, setOptions] = useState<EntityBrief[]>([]);
  const [searching, setSearching] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  const selectedIds = value.split(/[,，、]/).map((s) => s.trim()).filter((s) => s.length > 0);

  // 单值模式：已选实体已知时输入框显示名称（表单态仍是 ID）
  const selectedName =
    mode === "single" && selectedIds.length > 0 ? (nameById.get(selectedIds[0]) ?? selectedIds[0]) : "";

  // 防抖检索：去掉前导 @ 后非空即触发
  useEffect(() => {
    const keyword = query.replace(/^@+/, "").trim();
    if (keyword.length === 0) {
      setOptions([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    const timer = setTimeout(() => {
      const type = refTypes.length === 1 ? refTypes[0] : undefined;
      api
        .listEntities({ q: keyword, type })
        .then((list) => {
          const filtered = refTypes.length > 1 ? list.filter((b) => refTypes.includes(b.type)) : list;
          setOptions(filtered);
          setSearching(false);
        })
        .catch(() => setSearching(false));
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query, refTypes]);

  // 点击面板外部收起下拉
  useEffect(() => {
    if (!open) return;
    const onDocMouseDown = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocMouseDown);
    return () => document.removeEventListener("mousedown", onDocMouseDown);
  }, [open]);

  const pick = (b: EntityBrief) => {
    if (mode === "single") {
      onChange(b.id);
      setQuery(b.name); // 输入框显示名称
    } else {
      const next = selectedIds.includes(b.id) ? selectedIds : [...selectedIds, b.id];
      onChange(next.join(","));
      setQuery("");
    }
    setOpen(false);
  };

  const removeId = (rid: string) => {
    onChange(selectedIds.filter((x) => x !== rid).join(","));
  };

  return (
    <div className="flex flex-col gap-1" ref={boxRef}>
      <label htmlFor={id} className="text-xs font-medium text-slate-700 dark:text-slate-300">
        {label}
      </label>
      {mode === "multi" && selectedIds.length > 0 ? (
        <div className="flex flex-wrap gap-1">
          {selectedIds.map((rid) => (
            <span
              key={rid}
              className="flex items-center gap-1 rounded-lg bg-slate-200/80 px-2 py-0.5 text-xs text-slate-700 dark:bg-slate-700/80 dark:text-slate-200"
            >
              {nameById.get(rid) ?? rid}
              <button
                type="button"
                aria-label={`移除 ${nameById.get(rid) ?? rid}`}
                className="text-slate-500 hover:text-slate-800 dark:hover:text-slate-100"
                onClick={() => removeId(rid)}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      ) : null}
      <input
        id={id}
        data-testid={id}
        className="w-full rounded-xl border border-slate-300 bg-white/70 px-3 py-2 text-sm text-slate-900 transition-colors duration-150 focus:border-slate-500 focus:outline-none dark:border-slate-600 dark:bg-slate-800/70 dark:text-slate-100 dark:focus:border-slate-400"
        placeholder="输入 @ 或名称检索实体…"
        value={mode === "single" && selectedName && !open ? selectedName : query}
        autoComplete="off"
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          setQuery(e.target.value);
          if (mode === "single") onChange(""); // 重新输入即清除已选
          setOpen(true);
        }}
      />
      {error ? (
        <p role="alert" className="text-xs text-red-600 dark:text-red-400">
          {error}
        </p>
      ) : null}
      {open && query.replace(/^@+/, "").trim().length > 0 ? (
        <ul
          data-testid={`${id}-options`}
          className="z-20 max-h-56 overflow-y-auto rounded-xl border border-slate-200 bg-white/95 shadow-lg dark:border-slate-700 dark:bg-slate-800/95"
        >
          {options.length === 0 ? (
            <li className="px-3 py-2 text-xs text-slate-500 dark:text-slate-400">
              {searching ? "检索中…" : "无匹配实体"}
            </li>
          ) : (
            options.map((b) => {
              const visible = visibleIds.has(b.id);
              return (
                <li key={b.id}>
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-700/70"
                    // mousedown 选择：先于输入框 blur，避免下拉先收起
                    onMouseDown={(e) => {
                      e.preventDefault();
                      pick(b);
                    }}
                  >
                    <span className="font-medium text-slate-800 dark:text-slate-100">{b.name}</span>
                    <span className="rounded-md bg-slate-200/70 px-1.5 py-0.5 text-xs text-slate-600 dark:bg-slate-700/70 dark:text-slate-300">
                      {TYPE_LABELS[b.type] ?? b.type}
                    </span>
                    <span
                      className={`ml-auto text-xs ${visible ? "text-emerald-600 dark:text-emerald-400" : "text-slate-400 dark:text-slate-500"}`}
                    >
                      {visible ? "当前视角可见" : "当前视角不可见"}
                    </span>
                  </button>
                </li>
              );
            })
          )}
        </ul>
      ) : null}
    </div>
  );
}
