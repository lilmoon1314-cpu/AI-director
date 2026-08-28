import { defineConfig } from "@playwright/test";

// L3 端到端配置（docs/testing.md §3 frontend/e2e/）：
// webServer 依次拉起后端（临时 SQLite + 迁移）与前端 dev server，
// 前端经 Vite 代理 /api → :8000 访问后端，无需处理跨域。
export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  // 负载验收走独立配置（pnpm test:e2e:load → playwright.load.config.ts）
  testIgnore: "**/*.load.spec.ts",
  // 单 worker：各 spec 共用同一后端库，并行会互踩数据（reset/播种交错致断言恒 9/5）
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 30_000,
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
    // 用完整版 chromium（含 headless=new）；避免额外下载 chromium-headless-shell
    channel: "chromium",
    // 失败自动截图/录屏留证（test-results/，成功路径的存档截图见 e2e/helpers.ts shoot()）
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  reporter: [
    ["list"],
    // 终端跑完执行 `pnpm exec playwright show-report` 可看带截图/步骤的交互式报告
    ["html", { open: "never", outputFolder: "playwright-report" }],
  ],
  webServer: [
    {
      // 前置 taskkill：彼时本轮 uvicorn 尚未启动，杀全部 uvicorn 安全
      // （Windows 下残留进程链会占 8000 端口与库文件，致轮询误命中旧库——同 load 配置）
      command:
        "taskkill /F /T /IM uvicorn.exe 2>nul & cd ../backend && uv run alembic upgrade head && uv run uvicorn app.main:app --port 8000",
      url: "http://localhost:8000/api/entities",
      reuseExistingServer: false,
      timeout: 90_000,
      env: {
        // e2e 专用临时库，与开发库 data/app.db 隔离
        DATABASE_URL: "sqlite+aiosqlite:///data/e2e_test.db",
      },
    },
    {
      command: "pnpm dev",
      url: "http://localhost:5173",
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
