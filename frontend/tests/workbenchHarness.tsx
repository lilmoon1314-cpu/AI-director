/**
 * 工作台测试装配（F11 路由化后集成测试共用）：
 * 在 MemoryRouter 中按生产路由结构挂载 Workbench（图谱 / 资产子路由，F12 镜像
 * App.tsx 的资产三级子路由），使 useParams/useNavigate/Outlet context 与运行时一致。
 * 各测试文件按需搭配自己的 MSW /api/projects 处理器（默认项目 id: project-default）。
 */

import { render } from "@testing-library/react";
import { MemoryRouter, Navigate, Route, Routes } from "react-router-dom";

import { EntityTypeAssets } from "../src/components/assets/EntityTypeAssets";
import { GeneralAssetSection } from "../src/components/assets/GeneralAssetSection";
import { ProjectTypeWall } from "../src/components/assets/ProjectTypeWall";
import { DEFAULT_PROJECT_ID } from "../src/api/client";
import { AssetLibrary } from "../src/views/AssetLibrary";
import { GraphView } from "../src/views/GraphView";
import { Workbench } from "../src/views/Workbench"

// 测试装配文件与 React Fast Refresh 无关，导出装配函数与共享常量供各测试文件统一导入
export { DEFAULT_PROJECT_ID };

/** 在路由上下文中渲染工作台（默认落在图谱页）。 */
// eslint-disable-next-line react-refresh/only-export-components
export function renderWorkbench(initialRoute = `/projects/${DEFAULT_PROJECT_ID}/graph`) {
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <Routes>
        <Route path="/projects/:projectId" element={<Workbench />}>
          <Route path="graph" element={<GraphView />} />
          <Route path="assets" element={<AssetLibrary />}>
            <Route index element={<Navigate to="general" replace />} />
            <Route path="general" element={<GeneralAssetSection />} />
            <Route path="project" element={<ProjectTypeWall />} />
            <Route path="project/:entityType" element={<EntityTypeAssets />} />
          </Route>
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}
