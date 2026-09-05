/**
 * 资产管理页（F08）：通用资产 / 项目资产 两个分区（二级切换）。
 * - 挂载即懒加载两类卡片列表（store 缓存，重复进入不重拉）；
 * - 通用资产区 = 可复用参考素材的 CRUD；项目资产区 = 主库实体按类型分组的只读卡片。
 */

import { useEffect, useState } from "react";

import { GeneralAssetSection } from "../components/assets/GeneralAssetSection";
import { ProjectAssetSection } from "../components/assets/ProjectAssetSection";
import { useAssetStore } from "../stores/assetStore";

type Section = "general" | "project";

export function AssetLibrary() {
  const loadGeneral = useAssetStore((s) => s.loadGeneral);
  const loadEntityCards = useAssetStore((s) => s.loadEntityCards);
  const [section, setSection] = useState<Section>("general");

  useEffect(() => {
    loadGeneral().catch(() => {});
    loadEntityCards().catch(() => {});
  }, [loadGeneral, loadEntityCards]);

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col gap-4 overflow-y-auto rounded-2xl p-5">
      <div className="flex items-center gap-1 rounded-full bg-white/60 p-1 text-sm backdrop-blur w-fit dark:bg-slate-800/60">
        <button
          type="button"
          data-testid="section-general"
          aria-pressed={section === "general"}
          onClick={() => setSection("general")}
          className={`rounded-full px-4 py-1.5 transition-colors duration-150 ${
            section === "general"
              ? "bg-slate-800 font-medium text-white dark:bg-slate-200 dark:text-slate-900"
              : "text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white"
          }`}
        >
          通用资产
        </button>
        <button
          type="button"
          data-testid="section-project"
          aria-pressed={section === "project"}
          onClick={() => setSection("project")}
          className={`rounded-full px-4 py-1.5 transition-colors duration-150 ${
            section === "project"
              ? "bg-slate-800 font-medium text-white dark:bg-slate-200 dark:text-slate-900"
              : "text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white"
          }`}
        >
          项目资产
        </button>
      </div>

      <div className="min-h-0 flex-1">
        {section === "general" ? <GeneralAssetSection /> : <ProjectAssetSection />}
      </div>
    </div>
  );
}
