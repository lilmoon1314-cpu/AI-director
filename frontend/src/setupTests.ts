// Vitest 全局 setup：注册 @testing-library/jest-dom 的断言扩展
// （如 toBeInTheDocument / toHaveTextContent），全部测试文件共用。
// @antv/g6 的测试桩经 vite.config.ts 的 test.alias 替换（jsdom 无 canvas），
// 不用 vi.mock：测试文件内 import @testing-library/react 与 vi.mock 提升并存
// 会触发 vitest 转换的 TDZ 崩溃（error.jsonl E06）。
import "@testing-library/jest-dom/vitest";
