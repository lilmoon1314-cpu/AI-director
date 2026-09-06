/**
 * 三要素错误条（F12，DESIGN.md §5.3 状态矩阵 error 态）：什么出了问题 + 怎么修 + 重试按钮。
 * 分区数据加载失败时呈现（不再吞成空态误导）；重试触发调用方传入的 force 重载。
 */

import { Button } from "./Button";

export function ErrorStrip({
  problem,
  fix,
  onRetry,
  testId,
}: {
  problem: string;
  fix: string;
  onRetry: () => void;
  testId: string;
}) {
  return (
    <div
      role="alert"
      data-testid={testId}
      className="flex flex-wrap items-center gap-3 rounded-xl border border-red-200 bg-red-50/80 p-3 text-xs dark:border-red-900 dark:bg-red-950/60"
    >
      <div className="min-w-0 flex-1">
        <p className="font-medium text-red-700 dark:text-red-400">{problem}</p>
        <p className="mt-0.5 text-red-600 dark:text-red-400">修复：{fix}</p>
      </div>
      <Button variant="ghost" onClick={onRetry} className="px-3 py-1 text-xs">
        重试
      </Button>
    </div>
  );
}
