/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

// Vite 配置：构建行为 + 开发服务器 + 测试环境
// API 代理：开发期前端请求 /api/* 由 Vite 转发到后端 :8000，无需处理跨域
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/setupTests.ts",
    // L1/L2 用：指向 MSW 可匹配的绝对 base（Node fetch 不接受相对 URL）
    env: { VITE_API_BASE: "http://mock.local/api" },
    // e2e/*.spec.ts 归 Playwright（pnpm test:e2e），vitest 全量跑（pnpm test）时排除
    exclude: ["e2e/**", "node_modules/**", "dist/**"],
    // @antv/g6 测试桩：仅测试环境生效（jsdom 无 canvas）；构建走真实依赖。
    // 不用 vi.mock——与 @testing-library/react import 并存会触发转换期 TDZ（E06）
    alias: {
      "@antv/g6": fileURLToPath(new URL("./src/test-stubs/g6-stub.ts", import.meta.url)),
    },
  },
});
