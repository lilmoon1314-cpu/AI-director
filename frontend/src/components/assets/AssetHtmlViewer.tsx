/**
 * 资产 HTML 内嵌查看器（F08）：全屏毛玻璃遮罩 + 顶栏（返回/标题）+ iframe。
 * - 由 assetStore.viewer 驱动（任意页签均可打开——挂载于 Workbench 壳层）；
 * - iframe 加载后端 text/html 资产页（自包含 HTML，图片走 /static/assets）。
 */

import { useEffect } from "react";

import { useAssetStore } from "../../stores/assetStore";
import { Button } from "../ui/Button";

export function AssetHtmlViewer() {
  const viewer = useAssetStore((s) => s.viewer);
  const closeViewer = useAssetStore((s) => s.closeViewer);

  // Esc 关闭（挂载期间监听，卸载即移除）
  useEffect(() => {
    if (!viewer) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeViewer();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [viewer, closeViewer]);

  if (!viewer) return null;

  return (
    <div
      data-testid="asset-viewer"
      className="fixed inset-0 z-50 flex flex-col bg-slate-200/70 backdrop-blur-sm dark:bg-slate-900/70"
    >
      <div className="flex items-center gap-3 px-5 py-3">
        <Button variant="ghost" onClick={closeViewer} aria-label="返回资产列表">
          ◀ 返回
        </Button>
        <span className="text-sm font-medium text-slate-800 dark:text-slate-100">{viewer.title}</span>
        <a
          href={viewer.url}
          target="_blank"
          rel="noreferrer"
          className="ml-auto text-xs text-slate-500 underline decoration-dotted hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
        >
          新标签页打开
        </a>
      </div>
      <iframe
        title={viewer.title}
        src={viewer.url}
        data-testid="asset-viewer-frame"
        className="mx-auto mb-4 w-full max-w-5xl flex-1 rounded-2xl border border-white/40 bg-white shadow-xl dark:border-slate-700"
      />
    </div>
  );
}
