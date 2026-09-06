import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./index.css";

// 应用入口：把 App 组件挂载到 index.html 的 #root 节点
// StrictMode：开发期双调用渲染函数，提前暴露不规范的组件写法
// BrowserRouter（F11 路由化，DESIGN.md §4）：URL 即状态——/projects 首屏 +
// /projects/:projectId/graph|assets 工作台；刷新/后退/深链可靠
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
