import { defineConfig } from "@playwright/test";

// 负载验收专用配置（与主验收 playwright.config.ts 隔离）：
// - 只收集 *.load.spec.ts（主验收经 testIgnore 排除本类文件）；
// - 后端用独立端口 8010 + 独立临时库 data/load_test.db（load-global-setup 每轮
//   清理残留进程与库文件），vite 代理目标经 VITE_API_PROXY_TARGET 指向 8010——
//   与主验收端口(8000)及任何残留进程完全隔离；
// - 超时放宽（播种 400 个请求 + 力导布局收敛均耗时）。
// 运行: pnpm test:e2e:load
export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.load.spec.ts",
  globalSetup: "./e2e/load-global-setup.ts",
  fullyParallel: false,
  retries: 0,
  timeout: 600_000,
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
    channel: "chromium",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: [
    {
      // 前置 taskkill：此时本轮 uvicorn 尚未启动，杀全部 uvicorn 安全
      // （Windows 下残留 uvicorn 进程会占端口与库文件；/T 树杀 shim+python 进程链）
      command:
        "taskkill /F /T /IM uvicorn.exe 2>nul & cd ../backend && uv run alembic upgrade head && uv run uvicorn app.main:app --port 8010",
      url: "http://localhost:8010/api/entities",
      reuseExistingServer: false,
      timeout: 90_000,
      env: { DATABASE_URL: "sqlite+aiosqlite:///data/load_test.db" },
    },
    {
      command: "pnpm dev",
      url: "http://localhost:5173",
      reuseExistingServer: false,
      timeout: 60_000,
      env: { VITE_API_PROXY_TARGET: "http://localhost:8010" },
    },
  ],
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
});
