/**
 * 居中 modal 遮罩（F12，DESIGN.md §5.3.1/OQ-3）：全屏毛玻璃遮罩 + 居中 GlassPanel。
 * - 用于「表单不替换列表」的编辑场景（新建/编辑通用资产等）；
 * - 不自带 Esc 关闭（表单含未保存输入，防误触丢失；显式取消按钮为唯一出口）；
 * - 层级 z-50（与全屏查看器同级，互斥打开无叠压）；panelClassName 支持大面板
 *   覆写（F13 DocEditor max-w-5xl 三栏）。
 */

import type { ReactNode } from "react";

import { GlassPanel } from "./GlassPanel";

export function Modal({
  title,
  children,
  testId,
  panelClassName = "",
}: {
  title: string;
  children: ReactNode;
  testId?: string;
  /** 面板尺寸覆写（如 DocEditor 大弹窗 max-w-5xl；默认 max-w-2xl）。 */
  panelClassName?: string;
}) {
  return (
    <div
      role="dialog"
      aria-label={title}
      data-testid={testId}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-200/70 p-4 backdrop-blur-sm dark:bg-slate-900/70"
    >
      <GlassPanel className={`max-h-full w-full max-w-2xl overflow-y-auto p-6 ${panelClassName}`}>
        <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">{title}</h2>
        <div className="mt-4">{children}</div>
      </GlassPanel>
    </div>
  );
}
