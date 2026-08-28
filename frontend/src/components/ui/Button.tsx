import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "ghost" | "danger";

const VARIANT_CLASSES: Record<Variant, string> = {
  primary:
    "bg-slate-800 text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white",
  ghost:
    "border border-slate-300 bg-white/40 text-slate-800 hover:bg-white/70 dark:border-slate-600 dark:bg-slate-800/40 dark:text-slate-200 dark:hover:bg-slate-700/60",
  danger:
    "border border-red-300 bg-red-50 text-red-700 hover:bg-red-100 dark:border-red-900 dark:bg-red-950/50 dark:text-red-400 dark:hover:bg-red-900/40",
};

/** 按钮（动效克制：颜色过渡 150ms，≤200ms 上限）。 */
export function Button({
  variant = "primary",
  className = "",
  type = "button",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      type={type}
      className={`rounded-xl px-4 py-2 text-sm font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50 ${VARIANT_CLASSES[variant]} ${className}`}
      {...rest}
    />
  );
}
