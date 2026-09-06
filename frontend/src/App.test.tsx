// F01 冒烟测试：验证 React 渲染链路 + Tailwind 样式引入 + 测试基建可用。
// @antv/g6 桩由 vite.config test.alias 全局替换（jsdom 无 canvas，见 g6-stub.ts）；
// F11 路由化：App 需路由上下文——冒烟锚点分两条路由：项目首屏主标题（同步渲染）、
// 工作台顶栏毛玻璃容器（同步渲染）；数据请求失败由各 store 捕获为错误条（不白屏）。
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import App from "./App";

function renderApp(initialEntry: string) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <App />
    </MemoryRouter>,
  );
}

// F01 冒烟测试：验证 React 渲染链路 + Tailwind 样式引入 + 测试基建可用
describe("App 冒烟测试（F01）", () => {
  it("渲染应用主标题（项目首屏）", () => {
    // 问题: 页面未渲染主标题「影视世界观工作台」
    // 原因: App 组件损坏 / main.tsx 挂载失败 / Vitest 环境未初始化
    // 修复: 检查 src/App.tsx 与 src/views/ProjectPicker.tsx，重新运行 pnpm test
    renderApp("/projects");
    expect(
      screen.getByRole("heading", { level: 1, name: /影视世界观工作台/ }),
    ).toBeInTheDocument();
  });

  it("渲染毛玻璃卡片容器（视觉基调锚点）", () => {
    // 问题: 未找到带 backdrop-blur 的卡片容器
    // 原因: App 布局类名被误改，违反 frontend/CONSTRAINTS.md「视觉」约束
    // 修复: 恢复 GlassPanel 的 backdrop-blur-xl 类名（Workbench 顶栏/ProjectPicker）
    renderApp("/projects/project-default/graph");
    const card = document.querySelector(".backdrop-blur-xl");
    expect(card).not.toBeNull();
  });
});
