import { Navigate, Route, Routes } from "react-router-dom";

import { AssetLibrary } from "./views/AssetLibrary";
import { GraphView } from "./views/GraphView";
import { ProjectPicker } from "./views/ProjectPicker";
import { Workbench } from "./views/Workbench";

/**
 * 根组件：路由表（F11 路由化，DESIGN.md §4.1）。
 * - /projects：项目首屏（选择/新建/管理项目）；
 * - /projects/:projectId/graph|assets：工作台壳层（图谱页 / 资产管理页）；
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
        <Route path="assets" element={<AssetLibrary />} />
      </Route>
      <Route path="*" element={<Navigate to="/projects" replace />} />
    </Routes>
  );
}

export default App;
