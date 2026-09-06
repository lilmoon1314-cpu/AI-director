/**
 * 通用参考库（F08，F12 重构，DESIGN.md §5.3.1）：跨项目可复用参考素材（全局层）。
 * - 分区头：标题 + 「跨项目共享」徽标 + 分类 chips + 独立搜索框（前端过滤，AND 叠加）；
 * - 卡片网格：点击打开 HTML 查看器；编辑按钮 hover / focus 可见（键盘可达）；
 * - 新建/编辑经居中 modal（OQ-3：不再整区替换，卡片墙保持可见）；
 * - 状态矩阵：空库引导卡 / 搜索无命中提示 / 错误条。
 */

import { useCallback, useMemo, useState } from "react";

import { api, ApiError, type AssetRead } from "../../api/client";
import { filterGeneralAssets } from "../../lib/assetFilters";
import { useAssetStore } from "../../stores/assetStore";
import { AssetCardTile } from "./AssetCardTile";
import { GeneralAssetForm } from "./GeneralAssetForm";
import { Button } from "../ui/Button";
import { ErrorStrip } from "../ui/ErrorStrip";
import { Modal } from "../ui/Modal";

export function GeneralAssetSection() {
  const cards = useAssetStore((s) => s.generalCards);
  const loading = useAssetStore((s) => s.generalLoading);
  const error = useAssetStore((s) => s.generalError);
  const loadGeneral = useAssetStore((s) => s.loadGeneral);
  const openViewer = useAssetStore((s) => s.openViewer);
  const [category, setCategory] = useState<string>("");
  const [query, setQuery] = useState<string>("");
  const [editing, setEditing] = useState<AssetRead | "new" | null>(null);
  const [formError, setFormError] = useState<{ problem: string; fix: string } | null>(null);

  const refresh = useCallback(() => {
    void loadGeneral(true);
  }, [loadGeneral]);

  const categories = useMemo(
    () => Array.from(new Set(cards.map((c) => c.category).filter(Boolean))).sort(),
    [cards],
  );
  const visible = useMemo(() => filterGeneralAssets(cards, { query, category }), [cards, query, category]);

  const startEdit = async (cardId: string) => {
    setFormError(null);
    try {
      setEditing(await api.getGeneralAsset(cardId));
    } catch (cause) {
      const err = cause instanceof ApiError ? cause : null;
      setFormError({
        problem: err?.problem ?? "资产详情加载失败",
        fix: err?.fix ?? "确认后端服务已启动后重试",
      });
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-300">
          通用参考库
          <span className="rounded-full bg-white/70 px-2 py-0.5 text-[10px] font-normal text-slate-500 ring-1 ring-black/5 dark:bg-slate-800/70 dark:text-slate-400 dark:ring-white/10">
            跨项目共享
          </span>
        </h2>
        <div className="ml-auto flex items-center gap-2">
          <input
            type="search"
            data-testid="asset-search"
            aria-label="搜索通用参考库"
            placeholder="搜索标题 / 描述 / 分类…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-52 rounded-full border border-slate-200 bg-white/70 px-3 py-1 text-xs text-slate-800 outline-none transition-colors duration-150 focus:border-slate-400 dark:border-slate-700 dark:bg-slate-800/70 dark:text-slate-200"
          />
          {cards.length > 0 ? (
            <Button
              variant="ghost"
              data-testid="create-asset"
              onClick={() => setEditing("new")}
              className="rounded-full px-3 py-1 text-xs"
            >
              ＋ 新建库
            </Button>
          ) : null}
        </div>
      </div>

      {cards.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            data-testid="category-all"
            onClick={() => setCategory("")}
            className={`rounded-full px-3 py-1 text-xs transition-colors duration-150 ${
              category === ""
                ? "bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900"
                : "bg-white/70 text-slate-600 hover:bg-white dark:bg-slate-800/70 dark:text-slate-300"
            }`}
          >
            全部（{cards.length}）
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              type="button"
              data-testid={`category-${cat}`}
              onClick={() => setCategory(cat === category ? "" : cat)}
              className={`rounded-full px-3 py-1 text-xs transition-colors duration-150 ${
                category === cat
                  ? "bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900"
                  : "bg-white/70 text-slate-600 hover:bg-white dark:bg-slate-800/70 dark:text-slate-300"
              }`}
            >
              {cat}（{cards.filter((c) => c.category === cat).length}）
            </button>
          ))}
        </div>
      ) : null}

      {formError ? (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50/80 p-3 text-xs dark:border-red-900 dark:bg-red-950/60">
          <p className="font-medium text-red-700 dark:text-red-400">{formError.problem}</p>
          <p className="mt-1 text-red-600 dark:text-red-400">修复：{formError.fix}</p>
        </div>
      ) : null}

      {error ? (
        <ErrorStrip
          testId="asset-general-error"
          problem={error.problem}
          fix={error.fix}
          onRetry={() => void loadGeneral(true)}
        />
      ) : null}

      {loading ? (
        <p className="text-xs text-slate-500 dark:text-slate-400">加载中…</p>
      ) : !error && cards.length === 0 ? (
        <div
          data-testid="asset-general-empty"
          className="flex flex-col items-center gap-3 rounded-2xl bg-white/60 p-10 text-center backdrop-blur dark:bg-slate-800/60"
        >
          <p className="text-base font-medium text-slate-800 dark:text-slate-200">
            创建第一个参考库
          </p>
          <p className="max-w-sm text-sm text-slate-500 dark:text-slate-400">
            一条参考库 = 多张参考图 + 自由属性的独立 HTML 页，跨项目共享（表情 / 植被 / 风格…）
          </p>
          <Button data-testid="create-asset" onClick={() => setEditing("new")}>
            ＋ 新建库
          </Button>
        </div>
      ) : visible.length === 0 ? (
        <p
          data-testid="asset-search-empty"
          className="rounded-2xl bg-white/60 p-6 text-center text-sm text-slate-500 backdrop-blur dark:bg-slate-800/60 dark:text-slate-400"
        >
          未找到匹配「{query.trim()}」的资产——换个关键词，或清除分类筛选试试。
        </p>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-3" data-testid="general-asset-grid">
          {visible.map((card) => (
            <div key={card.id} className="group relative">
              <AssetCardTile
                testId={`general-asset-${card.id}`}
                title={card.title}
                description={card.description}
                coverUrl={card.cover_url}
                meta={`${card.category ? `${card.category} · ` : ""}${card.image_count} 图`}
                onOpen={() =>
                  openViewer({
                    url: api.assetPageUrl("general", card.id),
                    title: card.title,
                  })
                }
              />
              <button
                type="button"
                data-testid={`edit-asset-${card.id}`}
                aria-label={`编辑 ${card.title}`}
                onClick={() => startEdit(card.id)}
                className="absolute right-2 top-2 rounded-lg bg-white/85 px-1.5 py-0.5 text-[10px] text-slate-600 opacity-0 shadow transition-opacity duration-150 hover:bg-white group-focus-within:opacity-100 group-hover:opacity-100 dark:bg-slate-900/85 dark:text-slate-300"
              >
                编辑
              </button>
            </div>
          ))}
        </div>
      )}

      {editing ? (
        <Modal
          title={editing === "new" ? "新建通用资产" : "编辑通用资产"}
          testId="general-asset-modal"
        >
          <GeneralAssetForm
            asset={editing === "new" ? null : editing}
            onCancel={() => {
              setEditing(null);
              refresh();
            }}
            onSaved={(saved) => {
              if (editing === "new") {
                // 新建成功 → 无损转入编辑态（补传图片），modal 保持打开
                void startEdit(saved.id);
              } else {
                setEditing(saved);
              }
              refresh();
            }}
            onDelete={() => {
              setEditing(null);
              refresh();
            }}
          />
        </Modal>
      ) : null}
    </div>
  );
}
