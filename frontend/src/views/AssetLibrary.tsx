/**
 * 资产管理页壳层（F08，F12 路由化重构，DESIGN.md §5.3/§4.1）：
 * - 二级胶囊「通用参考库 | 项目资产」为 NavLink（section-general/section-project testid 沿用），
 *   分区状态入 URL：/assets/general（默认落点，OQ-6）| /assets/project（类型库墙）
 *   | /assets/project/:entityType（类型库详情），刷新/后退/深链天然可靠；
 * - 挂载即懒加载两类卡片列表（store 缓存，重复进入不重拉）；
 * - 通用参考库 = 全局层（跨项目共享）；项目资产 = 随项目的实体资产两级钻取。
 */

import { useEffect } from "react";
import { NavLink, Outlet, useOutletContext } from "react-router-dom";

import { useAssetStore } from "../stores/assetStore";
import { useProjectId } from "../stores/projectStore";

const SECTIONS = [
  { key: "general", label: "通用参考库", to: "general" },
  { key: "project", label: "项目资产", to: "project" },
] as const;

export function AssetLibrary() {
  const projectId = useProjectId();
  const loadGeneral = useAssetStore((s) => s.loadGeneral);
  const loadEntityCards = useAssetStore((s) => s.loadEntityCards);
  // 嵌套 Outlet 不自动继承 context（F12）：回传 Workbench 供给的 projectId，
  // 否则深层路由（类型库详情）的 useProjectId 在 store 同步前读到 undefined
  const outletContext = useOutletContext<{ projectId?: string }>();

  useEffect(() => {
    // 错误在 store 内部消化为三要素错误态（F12），由分区组件呈现错误条 + 重试
    void loadGeneral();
    void loadEntityCards(projectId);
  }, [loadGeneral, loadEntityCards, projectId]);

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col gap-4 overflow-y-auto rounded-2xl p-5">
      <div className="flex items-center gap-1 rounded-full bg-white/60 p-1 text-sm backdrop-blur w-fit dark:bg-slate-800/60">
        {SECTIONS.map(({ key, label, to }) => (
          <NavLink
            key={key}
            to={to}
            data-testid={`section-${key}`}
            className={({ isActive }) =>
              `rounded-full px-4 py-1.5 transition-colors duration-150 ${
                isActive
                  ? "bg-slate-800 font-medium text-white dark:bg-slate-200 dark:text-slate-900"
                  : "text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white"
              }`
            }
          >
            {label}
          </NavLink>
        ))}
      </div>

      <div className="min-h-0 flex-1">
        <Outlet context={outletContext} />
      </div>
    </div>
  );
}
