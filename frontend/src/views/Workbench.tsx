/**
 * 工作台壳层（F08 起）：顶部主导航「图谱 | 资产管理」+ 页签内容。
 * - 「图谱」= 原工作台主视图（画布/操作栏/详情面板，见 GraphView）；
 * - 「资产管理」= HTML 资产库管理页（通用资产 + 项目资产，见 AssetLibrary）；
 * - AssetHtmlViewer 挂载于壳层——任一页签打开资产页均以全屏查看层呈现。
 * 既有 e2e 断言依赖的 testid（sidebar/graph-stats/entity-panel 等）随内容迁入
 * GraphView，层级变化不影响选择器。
 */

import { useState } from "react";

import { AssetHtmlViewer } from "../components/assets/AssetHtmlViewer";
import { GlassPanel } from "../components/ui/GlassPanel";
import { AssetLibrary } from "./AssetLibrary";
import { GraphView } from "./GraphView";

type Tab = "graph" | "assets";

const TABS: { key: Tab; label: string }[] = [
  { key: "graph", label: "图谱" },
  { key: "assets", label: "资产管理" },
];

export function Workbench() {
  const [tab, setTab] = useState<Tab>("graph");

  return (
    <div className="flex h-screen w-full flex-col gap-3 bg-slate-100 p-4 dark:bg-slate-950">
      <GlassPanel className="flex shrink-0 items-center gap-4 px-4 py-2.5">
        <h1 className="text-base font-semibold tracking-tight text-slate-900 dark:text-slate-100">
          影视世界观工作台
        </h1>
        <nav className="flex items-center gap-1 rounded-full bg-white/60 p-1 text-sm backdrop-blur dark:bg-slate-800/60" data-testid="main-nav">
          {TABS.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              data-testid={`tab-${key}`}
              aria-pressed={tab === key}
              onClick={() => setTab(key)}
              className={`rounded-full px-4 py-1 transition-colors duration-150 ${
                tab === key
                  ? "bg-slate-800 font-medium text-white dark:bg-slate-200 dark:text-slate-900"
                  : "text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white"
              }`}
            >
              {label}
            </button>
          ))}
        </nav>
      </GlassPanel>

      <div className="flex min-h-0 flex-1 gap-3">
        {tab === "graph" ? <GraphView /> : <AssetLibrary />}
      </div>

      <AssetHtmlViewer />
    </div>
  );
}
