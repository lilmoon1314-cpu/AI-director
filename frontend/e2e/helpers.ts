import type { APIRequestContext, Page } from "@playwright/test";

/** 关键步骤截图存档（frontend/e2e-screenshots/，按文件名序即执行序；不入版本库）。 */
export async function shoot(page: Page, name: string): Promise<void> {
  await page.screenshot({ path: `e2e-screenshots/${name}.png`, fullPage: true });
}

/**
 * 清空库（先删关系再删实体，规避引用 409）——经 API 幂等清理，
 * 保证测试不依赖库初始状态（防残留 uvicorn 复用旧库时数据累积）。
 */
export async function resetWorld(request: APIRequestContext): Promise<void> {
  const relations = (await (await request.get("/api/relations")).json()) as { id: string }[];
  for (const r of relations) await request.delete(`/api/relations/${r.id}`);
  const entities = (await (await request.get("/api/entities")).json()) as { id: string }[];
  for (const e of entities) await request.delete(`/api/entities/${e.id}`);
}
