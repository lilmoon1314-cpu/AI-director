import { Navigate, Route, Routes } from "react-router-dom";

import { AgentHome } from "./components/agent-panel/AgentHome";
import { EntityTypeAssets } from "./components/assets/EntityTypeAssets";
import { GeneralAssetSection } from "./components/assets/GeneralAssetSection";
import { ProjectTypeWall } from "./components/assets/ProjectTypeWall";
import { AssetLibrary } from "./views/AssetLibrary";
import { GraphView } from "./views/GraphView";
import { ProjectPicker } from "./views/ProjectPicker";
import { Workbench } from "./views/Workbench";

/**
 * 根组件：路由表（F11 路由化，DESIGN.md §4.1；F12 资产页两级钻取子路由，§5.3；
 * F10 Agent 路由：agent（主页）| agent/s/:sessionId（会话视图，URL 即状态））。
 * - /projects：项目首屏（选择/新建/管理项目）；
 * - /projects/:projectId/graph|assets|agent：工作台壳层；
 * - 资产页分区即子路由：assets → general（默认落点，OQ-6）| project（类型库墙）
 *   | project/:entityType（类型库详情），URL 即状态（刷新/后退/深链可靠）；
 * - / 重定向到 /projects；无效项目 id 由 Workbench 渲染错误页（路由参数为项目上下文事实源）。
 */
function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/projects" replace />} />
      <Route path="/projects" element={<ProjectPicker />} />
      <Route path="/projects/:projectId" element={<Workbench />}>
        <Route index element={<Navigate to="graph" replace />} />
        <Route path="graph" element={<GraphView />} />
        <Route path="assets" element={<AssetLibrary />}>
          <Route index element={<Navigate to="general" replace />} />
          <Route path="general" element={<GeneralAssetSection />} />
          <Route path="project" element={<ProjectTypeWall />} />
          <Route path="project/:entityType" element={<EntityTypeAssets />} />
        </Route>
        <Route path="agent" element={<AgentHome />} />
        <Route path="agent/s/:sessionId" element={<AgentHome />} />
      </Route>
      <Route path="*" element={<Navigate to="/projects" replace />} />
    </Routes>
  );
}

export default App;
