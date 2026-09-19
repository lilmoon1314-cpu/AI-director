import { defineConfig } from "@playwright/test";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

// Isolated R1 journey: never kill a user's server or reuse the development databases.
const root = mkdtempSync(join(tmpdir(), "ai-director-workspace-"));
const sqlite = (name: string) => `sqlite+aiosqlite:///${join(root, name).replaceAll("\\", "/")}`;
const python = process.platform === "win32" ? '".venv\\Scripts\\python.exe"' : ".venv/bin/python";
export default defineConfig({
  testDir: "./e2e",
  testMatch: ["workspace.spec.ts", "projects.spec.ts"],
  workers: 1,
  retries: 0,
  timeout: 30_000,
  use: { baseURL: "http://127.0.0.1:5187", channel: "chromium", trace: "retain-on-failure" },
  reporter: "list",
  webServer: [
    {
      cwd: resolve("../backend"),
      command: `${python} -m alembic upgrade head && ${python} -m uvicorn app.main:app --host 127.0.0.1 --port 8017`,
      url: "http://127.0.0.1:8017/api/health",
      reuseExistingServer: false,
      env: { DATABASE_URL: sqlite("app.db"), ASSET_DB_URL: sqlite("assets.db"), ASSET_DIR: join(root, "assets"), LOG_DIR: join(root, "logs") },
    },
    {
      command: "node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5187 --strictPort",
      url: "http://127.0.0.1:5187",
      reuseExistingServer: false,
      env: { VITE_API_PROXY_TARGET: "http://127.0.0.1:8017" },
    },
  ],
});
