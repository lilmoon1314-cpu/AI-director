/**
 * 通用资产区（F08）：跨项目可复用参考素材（表情/风格/植被等）。
 * - 分类 chips 过滤（全部 + 动态去重）；卡片网格；点击卡片打开 HTML 查看器；
 * - 新建/编辑经 GeneralAssetForm；编辑进入前经详情接口拉全量（attributes 不丢）；
 * - 表单保存/图片变更后由本区触发列表刷新。
 */

import { useCallback, useMemo, useState } from "react";

import { api, ApiError, type AssetRead } from "../../api/client";
import { useAssetStore } from "../../stores/assetStore";
import { AssetCardTile } from "./AssetCardTile";
import { GeneralAssetForm } from "./GeneralAssetForm";

export function GeneralAssetSection() {
  const cards = useAssetStore((s) => s.generalCards);
  const loading = useAssetStore((s) => s.generalLoading);
  const loadGeneral = useAssetStore((s) => s.loadGeneral);
  const openViewer = useAssetStore((s) => s.openViewer);
  const [category, setCategory] = useState<string>("");
  const [editing, setEditing] = useState<AssetRead | "new" | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    void loadGeneral(true);
  }, [loadGeneral]);

  const categories = useMemo(
    () => Array.from(new Set(cards.map((c) => c.category).filter(Boolean))).sort(),
    [cards],
  );
  const visible = useMemo(
    () => (category ? cards.filter((c) => c.category === category) : cards),
    [cards, category],
  );

  const startEdit = async (cardId: string) => {
    setFormError(null);
    try {
      setEditing(await api.getGeneralAsset(cardId));
    } catch (cause) {
      const err = cause instanceof ApiError ? cause : null;
      setFormError(err?.problem ?? "资产详情加载失败");
    }
  };

  if (editing) {
    return (
      <div className="mx-auto w-full max-w-2xl rounded-2xl bg-white/80 p-5 shadow-sm ring-1 ring-black/5 backdrop-blur dark:bg-slate-800/80 dark:ring-white/10">
        <h3 className="mb-3 text-sm font-semibold text-slate-900 dark:text-slate-100">
          {editing === "new" ? "新建通用资产" : "编辑通用资产"}
        </h3>
        <GeneralAssetForm
          asset={editing === "new" ? null : editing}
          onCancel={() => {
            setEditing(null);
            refresh();
          }}
          onSaved={(saved) => {
            if (editing === "new") {
              // 新建成功 → 无损转入编辑态（补传图片）
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
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
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
        <button
          type="button"
          data-testid="create-asset"
          onClick={() => setEditing("new")}
          className="ml-auto rounded-full bg-slate-800 px-3 py-1 text-xs font-medium text-white transition-colors duration-150 hover:bg-slate-700 dark:bg-slate-200 dark:text-slate-900 dark:hover:bg-white"
        >
          + 新建资产
        </button>
      </div>

      {formError ? (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50/80 p-3 text-xs dark:border-red-900 dark:bg-red-950/60">
          {formError}
        </div>
      ) : null}

      {loading ? (
        <p className="text-xs text-slate-500 dark:text-slate-400">加载中…</p>
      ) : visible.length === 0 ? (
        <p className="rounded-2xl bg-white/60 p-6 text-center text-sm text-slate-500 backdrop-blur dark:bg-slate-800/60 dark:text-slate-400">
          暂无{category ? `「${category}」` : ""}通用资产——点击右上角「+ 新建资产」创建。
        </p>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-3" data-testid="general-asset-grid">
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
                className="absolute right-2 top-2 rounded-lg bg-white/85 px-1.5 py-0.5 text-[10px] text-slate-600 opacity-0 shadow transition-opacity duration-150 hover:bg-white group-hover:opacity-100 dark:bg-slate-900/85 dark:text-slate-300"
              >
                编辑
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
