import type { HTMLAttributes } from "react";

/** 毛玻璃半透明面板（视觉基调锚点：backdrop-blur + 半透明底 + 对称圆角；深浅双主题）。 */
export function GlassPanel({ className = "", ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`rounded-2xl border border-white/60 bg-white/55 shadow-sm backdrop-blur-xl dark:border-slate-700/60 dark:bg-slate-900/55 ${className}`}
      {...rest}
    />
  );
}
