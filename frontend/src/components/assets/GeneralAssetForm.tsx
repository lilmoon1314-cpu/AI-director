/**
 * 通用资产编辑表单（F08）：标题/分类/描述/自定义属性（键值行）/多图上传。
 * - 新建：提交即创建（无图），成功后自动进入编辑态补传图片；
 * - 编辑：字段更新 + 图片上传/删除/设封面；attributes 为自由 JSON
 *   （DECISIONS 2026-09-05：表单按字符串键值编辑，存库即字符串值）。
 */

import { useRef, useState } from "react";

import { api, ApiError, type AssetRead } from "../../api/client";
import { Button } from "../ui/Button";
import { TextArea, TextInput } from "../ui/Field";

interface AttributeRow {
  key: string;
  value: string;
}

function toRows(attributes: Record<string, unknown>): AttributeRow[] {
  return Object.entries(attributes).map(([key, value]) => [key, String(value ?? "")]).map(
    ([key, value]) => ({ key, value }),
  );
}

export function GeneralAssetForm({
  asset,
  onSaved,
  onCancel,
  onDelete,
}: {
  /** null = 新建态；非 null = 编辑态（含图片管理）。 */
  asset: AssetRead | null;
  onSaved: (saved: AssetRead) => void;
  onCancel: () => void;
  /** 编辑态删除成功回调（新建态不显示删除）。 */
  onDelete?: () => void;
}) {
  const [title, setTitle] = useState(asset?.title ?? "");
  const [category, setCategory] = useState(asset?.category ?? "");
  const [description, setDescription] = useState(asset?.description ?? "");
  const [rows, setRows] = useState<AttributeRow[]>(() => toRows(asset?.attributes ?? {}));
  const [images, setImages] = useState(asset?.images ?? []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ problem: string; fix: string } | null>(null);
  const [current, setCurrent] = useState<AssetRead | null>(asset);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const attributes = (): Record<string, string> => {
    const out: Record<string, string> = {};
    for (const { key, value } of rows) {
      const k = key.trim();
      if (k) out[k] = value;
    }
    return out;
  };

  const save = async () => {
    if (!title.trim()) {
      setError({ problem: "标题不能为空", fix: "填写资产标题后保存" });
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const payload = {
        title: title.trim(),
        category: category.trim(),
        description: description.trim(),
        attributes: attributes(),
      };
      const saved = current
        ? await api.updateGeneralAsset(current.id, payload)
        : await api.createGeneralAsset(payload);
      setCurrent(saved);
      onSaved(saved);
    } catch (cause) {
      const err = cause instanceof ApiError ? cause : null;
      setError({ problem: err?.problem ?? "保存失败", fix: err?.fix ?? "稍后重试" });
    } finally {
      setBusy(false);
    }
  };

  const uploadFiles = async (files: FileList | null) => {
    if (!current || !files || files.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      for (const file of Array.from(files)) {
        await api.uploadImage("general", current.id, file);
      }
      const fresh = await api.updateGeneralAsset(current.id, {});
      setImages(fresh.images);
      setCurrent(fresh);
      onSaved(fresh);
    } catch (cause) {
      const err = cause instanceof ApiError ? cause : null;
      setError({ problem: err?.problem ?? "图片上传失败", fix: err?.fix ?? "确认文件为图片后重试" });
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const removeImage = async (imageId: string) => {
    setBusy(true);
    try {
      await api.deleteImage(imageId);
      setImages((prev) => prev.filter((img) => img.id !== imageId));
    } catch (cause) {
      const err = cause instanceof ApiError ? cause : null;
      setError({ problem: err?.problem ?? "图片删除失败", fix: err?.fix ?? "稍后重试" });
    } finally {
      setBusy(false);
    }
  };

  const setCover = async (imageId: string) => {
    if (!current) return;
    setBusy(true);
    try {
      const saved = await api.setAssetCover(current.id, imageId);
      setCurrent(saved);
      onSaved(saved);
    } catch (cause) {
      const err = cause instanceof ApiError ? cause : null;
      setError({ problem: err?.problem ?? "封面设置失败", fix: err?.fix ?? "稍后重试" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-3" data-testid="general-asset-form">
      {error ? (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50/80 p-3 text-xs dark:border-red-900 dark:bg-red-950/60">
          <p className="font-medium text-red-700 dark:text-red-400">{error.problem}</p>
          <p className="mt-1 text-red-600 dark:text-red-400">修复：{error.fix}</p>
        </div>
      ) : null}

      <TextInput
        id="asset-title"
        label="标题 *"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
      />
      <TextInput
        id="asset-category"
        label="分类（自由标签，如：表情参考 / 风格参考 / 植被参考）"
        value={category}
        onChange={(e) => setCategory(e.target.value)}
      />
      <TextArea
        id="asset-description"
        label="描述"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />

      <div>
        <p className="mb-1 text-xs font-medium text-slate-500 dark:text-slate-400">
          自定义属性（键值对；如：类型=愤怒、提示词·眉毛=紧蹙、强度=3）
        </p>
        <div className="flex flex-col gap-1.5">
          {rows.map((row, index) => (
            <div key={index} className="flex items-center gap-1.5">
              <input
                aria-label={`属性名 ${index + 1}`}
                placeholder="属性名"
                value={row.key}
                onChange={(e) =>
                  setRows((prev) => prev.map((r, i) => (i === index ? { ...r, key: e.target.value } : r)))
                }
                className="w-28 rounded-lg border border-slate-200 bg-white/70 px-2 py-1 text-xs text-slate-800 outline-none focus:border-slate-400 dark:border-slate-700 dark:bg-slate-800/70 dark:text-slate-200"
              />
              <input
                aria-label={`属性值 ${index + 1}`}
                placeholder="属性值"
                value={row.value}
                onChange={(e) =>
                  setRows((prev) => prev.map((r, i) => (i === index ? { ...r, value: e.target.value } : r)))
                }
                className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white/70 px-2 py-1 text-xs text-slate-800 outline-none focus:border-slate-400 dark:border-slate-700 dark:bg-slate-800/70 dark:text-slate-200"
              />
              <Button
                variant="ghost"
                aria-label={`删除属性 ${row.key || index + 1}`}
                onClick={() => setRows((prev) => prev.filter((_, i) => i !== index))}
              >
                ×
              </Button>
            </div>
          ))}
          <Button variant="ghost" onClick={() => setRows((prev) => [...prev, { key: "", value: "" }])}>
            + 添加属性
          </Button>
        </div>
      </div>

      {current ? (
        <div data-testid="asset-images">
          <p className="mb-1 text-xs font-medium text-slate-500 dark:text-slate-400">
            图片（{images.length} 张；首图默认为封面）
          </p>
          <div className="mb-1.5 flex flex-wrap gap-2">
            {images.map((img) => (
              <div
                key={img.id}
                className="relative h-14 w-14 overflow-hidden rounded-lg ring-1 ring-black/10 dark:ring-white/20"
              >
                <img src={img.url} alt={img.filename_orig} className="h-full w-full object-cover" />
                {current.cover_image_id === img.id ? (
                  <span className="absolute inset-x-0 bottom-0 bg-black/50 text-center text-[9px] text-white">
                    封面
                  </span>
                ) : (
                  <button
                    type="button"
                    aria-label={`设为封面 ${img.filename_orig}`}
                    onClick={() => setCover(img.id)}
                    className="absolute inset-x-0 bottom-0 bg-black/40 text-center text-[9px] text-white opacity-0 transition-opacity duration-150 hover:opacity-100"
                  >
                    设封面
                  </button>
                )}
                <button
                  type="button"
                  aria-label={`删除图片 ${img.filename_orig}`}
                  onClick={() => removeImage(img.id)}
                  className="absolute right-0 top-0 h-4 w-4 rounded-bl bg-black/50 text-[10px] leading-4 text-white"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
          <input
            ref={fileRef}
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            multiple
            aria-label="上传图片"
            data-testid="asset-image-input"
            onChange={(e) => uploadFiles(e.target.files)}
            className="w-full text-xs text-slate-500 dark:text-slate-400"
          />
        </div>
      ) : (
        <p className="text-xs text-slate-400 dark:text-slate-500">保存后可上传图片。</p>
      )}

      <div className="flex gap-2">
        <Button onClick={save} disabled={busy}>
          保存
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          取消
        </Button>
        {current && onDelete ? (
          confirmingDelete ? (
            <>
              <span className="self-center text-xs text-red-600 dark:text-red-400">
                确认删除该资产及其图片？
              </span>
              <Button
                variant="danger"
                data-testid="confirm-delete-asset"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    await api.deleteGeneralAsset(current.id);
                    onDelete();
                  } catch (cause) {
                    const err = cause instanceof ApiError ? cause : null;
                    setError({ problem: err?.problem ?? "删除失败", fix: err?.fix ?? "稍后重试" });
                    setBusy(false);
                  }
                }}
              >
                确认删除
              </Button>
              <Button variant="ghost" onClick={() => setConfirmingDelete(false)}>
                取消
              </Button>
            </>
          ) : (
            <Button variant="danger" data-testid="delete-asset" onClick={() => setConfirmingDelete(true)}>
              删除
            </Button>
          )
        ) : null}
      </div>
    </div>
  );
}
