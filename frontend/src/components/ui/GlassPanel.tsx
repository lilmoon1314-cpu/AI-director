import type { HTMLAttributes } from "react";

/** 毛玻璃半透明面板（视觉基调锚点：backdrop-blur + 白色半透明底 + 对称圆角）。 */
export function GlassPanel({ className = "", ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`rounded-2xl border border-white/60 bg-white/55 shadow-sm backdrop-blur-xl ${className}`}
      {...rest}
    />
  );
}
