import { Navigate, Route, Routes } from "react-router-dom";

import { EntityTypeAssets } from "./components/assets/EntityTypeAssets";
import { GeneralAssetSection } from "./components/assets/GeneralAssetSection";
import { ProjectTypeWall } from "./components/assets/ProjectTypeWall";
import { AssetLibrary } from "./views/AssetLibrary";
import { GraphView } from "./views/GraphView";
import { ProjectPicker } from "./views/ProjectPicker";
import { Workbench } from "./views/Workbench";

/**
 * 根组件：路由表（F11 路由化，DESIGN.md §4.1；F12 资产页两级钻取子路由，§5.3）。
 * - /projects：项目首屏（选择/新建/管理项目）；
 * - /projects/:projectId/graph|assets：工作台壳层（图谱页 / 资产管理页）；
 * - 资产页分区即子路由：assets → general（默认落点，OQ-6）| project（类型库墙）
 *   | project/:entityType（类型库详情），URL 即状态（刷新/后退/深链可靠）；
 * - Agent 页签随 F10 落地（DESIGN.md §5.4，本批不含）；
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
      </Route>
      <Route path="*" element={<Navigate to="/projects" replace />} />
    </Routes>
  );
}

export default App;
