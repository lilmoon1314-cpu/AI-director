import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

// 应用入口：把 App 组件挂载到 index.html 的 #root 节点
// StrictMode：开发期双调用渲染函数，提前暴露不规范的组件写法
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
