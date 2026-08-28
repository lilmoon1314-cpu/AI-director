import { existsSync, rmSync } from "node:fs";

// Playwright globalSetup：删除后端 e2e 临时库，保证每次 e2e 从空库起步
// （真实路径由后端 DATABASE_URL=sqlite+aiosqlite:///data/e2e_test.db 决定）
export default function globalSetup(): void {
  const dbFile = new URL("../backend/data/e2e_test.db", import.meta.url);
  if (existsSync(dbFile)) {
    rmSync(dbFile);
  }
}
