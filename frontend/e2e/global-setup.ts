import { existsSync, rmSync } from "node:fs";
import { resolve } from "node:path";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// 验收 globalSetup：尝试删除后端 e2e 临时库（主配置 DATABASE_URL=
// sqlite+aiosqlite:///data/e2e_test.db）。
// 注意：此时本轮 webServer 的 uvicorn 已启动并占用该库文件，Windows 上删除
// 大概率 EPERM——失败无害，真正的兜底是各 spec 内经 API 的 resetWorld 逐删
// （残留 uvicorn 占端口复用旧库时，resetWorld 保证数据仍被清干净）。
// 此处严禁 taskkill：Playwright 先起 webServer 再跑 globalSetup，杀 uvicorn
// 会误杀本轮后端。
export default async function globalSetup(): Promise<void> {
  const dbFile = resolve(process.cwd(), "../backend/data/e2e_test.db");
  for (let attempt = 0; attempt < 3 && existsSync(dbFile); attempt++) {
    try {
      rmSync(dbFile);
    } catch {
      await sleep(300);
    }
  }
}
