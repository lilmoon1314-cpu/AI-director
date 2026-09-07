/**
 * 工作台壳层（F11 路由化，DESIGN.md §4.3；F10 Agent 页签 + AgentDock 挂载）：
 * - 顶栏 = logo（返回项目首屏）+ 项目切换器 + 主导航「图谱 | 资产管理 | Agent」（NavLink，
 *   testid tab-graph/tab-assets/tab-agent，e2e 锚点契约）；
 * - 路由参数 :projectId 为项目上下文事实源：挂载/变化即同步 projectStore（校验存在性），
 *   叶子视图（GraphView/AssetLibrary/AgentHome）从 store 读当前项目并按变化重置换机；
 * - 无效项目 id → 三要素错误页 +「返回项目首屏」；
 * - AssetHtmlViewer 挂载于壳层——任一页签打开资产页均以全屏查看层呈现；
 * - AgentDock 挂载于壳层——图谱/资产/Agent 任一页签均可唤起侧边栏（同一会话池）。
 */

import { useEffect } from "react";
import { Link, NavLink, Outlet, useParams } from "react-router-dom";

import { AgentDock } from "../components/agent-panel/AgentDock";
import { AssetHtmlViewer } from "../components/assets/AssetHtmlViewer";
import { ProjectSwitcher } from "../components/projects/ProjectSwitcher";
import { GlassPanel } from "../components/ui/GlassPanel";
import { Button } from "../components/ui/Button";
import { useProjectStore } from "../stores/projectStore";

const TABS = [
  { key: "graph", label: "图谱", to: "graph" },
  { key: "assets", label: "资产管理", to: "assets" },
  { key: "agent", label: "Agent", to: "agent" },
] as const;

export function Workbench() {
  const { projectId } = useParams<{ projectId: string }>();
  const routeInvalid = useProjectStore((s) => s.routeInvalid);
  const syncRoute = useProjectStore((s) => s.syncRoute);

  // 路由参数 → 项目上下文（校验存在；列表缓存后同参跳过）
  useEffect(() => {
    if (projectId) void syncRoute(projectId);
  }, [projectId, syncRoute]);

  if (routeInvalid) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-slate-100 p-6 dark:bg-slate-950">
        <GlassPanel className="w-full max-w-md p-8 text-center">
          <h1 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            项目不存在
          </h1>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            地址中的项目可能已被删除或链接有误（id: {projectId}）
          </p>
          <div className="mt-5">
            <Link to="/projects">
              <Button>返回项目首屏</Button>
            </Link>
          </div>
        </GlassPanel>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-full flex-col gap-3 bg-slate-100 p-4 dark:bg-slate-950">
      {/* z-30：backdrop-blur 形成层叠上下文，需整体置于内容区之上（项目切换器下拉不被拦截） */}
      <GlassPanel className="z-30 flex shrink-0 items-center gap-4 px-4 py-2.5">
        <Link
          to="/projects"
          data-testid="logo-home"
          className="text-base font-semibold tracking-tight text-slate-900 transition-colors duration-150 hover:text-slate-600 dark:text-slate-100 dark:hover:text-slate-300"
          title="返回项目首屏"
        >
          ✦ 影视世界观工作台
        </Link>
        <ProjectSwitcher />
        <nav
          className="flex items-center gap-1 rounded-full bg-white/60 p-1 text-sm backdrop-blur dark:bg-slate-800/60"
          data-testid="main-nav"
        >
          {TABS.map(({ key, label, to }) => (
            <NavLink
              key={key}
              to={to}
              data-testid={`tab-${key}`}
              className={({ isActive }) =>
                `rounded-full px-4 py-1 transition-colors duration-150 ${
                  isActive
                    ? "bg-slate-800 font-medium text-white dark:bg-slate-200 dark:text-slate-900"
                    : "text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white"
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
      </GlassPanel>

      {/* key=项目 id：切换项目时整树重挂载，配合叶子视图的重置换机保证干净状态；
          context 渲染期同步供给 projectId——子组件挂载 effect 先于本组件 syncRoute
          effect 执行，显式传参避免图请求读到上一项目的旧值 */}
      <div key={projectId} className="flex min-h-0 flex-1 gap-3">
        <Outlet context={{ projectId: projectId ?? "" }} />
      </div>

      <AssetHtmlViewer />
      <AgentDock projectId={projectId ?? ""} />
    </div>
  );
}
