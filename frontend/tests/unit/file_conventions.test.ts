/**
 * F05 L1：测试文件约定检查（error.jsonl E06 的自动化转化）。
 * 规则: 测试文件不得同时使用 vi.mock 与 import @testing-library/react——
 * 该组合触发 vitest 转换期的 TDZ 崩溃（"Cannot access '__vi_import_x__' before
 * initialization"）；G6 等外部依赖替换统一走 vite.config 的 test.alias 测试桩。
 * 若未来确需 vi.mock，须先修订本检查并验证 vitest 版本行为。
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

function collectTestFiles(root: string, acc: string[] = []): string[] {
  for (const name of readdirSync(root)) {
    const path = join(root, name);
    if (statSync(path).isDirectory()) {
      if (name === "node_modules" || name === "dist" || name === "e2e") continue;
      collectTestFiles(path, acc);
    } else if (/\.test\.(ts|tsx)$/.test(name)) {
      acc.push(path);
    }
  }
  return acc;
}

describe("测试文件约定（E06 防复发）", () => {
  it("vi.mock 不得与 @testing-library/react 共存于同一测试文件", () => {
    // 拼接规避自指：本文件源码包含该调用样式字符串
    const mockCall = "vi" + ".mock(";
    const offenders: string[] = [];
    for (const root of ["src", "tests"]) {
      for (const path of collectTestFiles(root)) {
        const source = readFileSync(path, "utf-8");
        if (source.includes(mockCall) && source.includes("@testing-library/react")) {
          offenders.push(path);
        }
      }
    }
    expect(offenders).toEqual([]);
  });
});
