/**
 * 工作台测试装配（F11 路由化后集成测试共用）：
 * 在 MemoryRouter 中按生产路由结构挂载 Workbench（图谱/资产子路由），
 * 使 useParams/useNavigate/Outlet context 与运行时行为一致。
 * 各测试文件按需搭配自己的 MSW /api/projects 处理器（默认项目 id: project-default）。
 */

import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { DEFAULT_PROJECT_ID } from "../src/api/client";
import { AssetLibrary } from "../src/views/AssetLibrary";
import { GraphView } from "../src/views/GraphView";
import { Workbench } from "../src/views/Workbench"

// 测试装配文件与 React Fast Refresh 无关，转发共享常量供各测试文件统一导入
// eslint-disable-next-line react-refresh/only-export-components
export { DEFAULT_PROJECT_ID };

/** 在路由上下文中渲染工作台（默认落在图谱页）。 */
export function renderWorkbench(initialRoute = `/projects/${DEFAULT_PROJECT_ID}/graph`) {
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <Routes>
        <Route path="/projects/:projectId" element={<Workbench />}>
          <Route path="graph" element={<GraphView />} />
          <Route path="assets" element={<AssetLibrary />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}
