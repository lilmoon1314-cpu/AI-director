/**
 * e2e 验收辅助：关键步骤截图存档。
 * 输出 frontend/e2e-screenshots/（.gitignore，不入版本库）；
 * 文件名带序号前缀，按名排序即执行顺序，便于人工核对前端视觉效果。
 */

import type { Page } from "@playwright/test";

export async function shoot(page: Page, name: string): Promise<void> {
  await page.screenshot({ path: `e2e-screenshots/${name}.png`, fullPage: true });
}
