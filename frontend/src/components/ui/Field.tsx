import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

const CONTROL_CLASSES =
  "w-full rounded-xl border border-slate-300 bg-white/70 px-3 py-2 text-sm text-slate-900 transition-colors duration-150 focus:border-slate-500 focus:outline-none";

function FieldShell({
  label,
  error,
  htmlFor,
  children,
}: {
  label: string;
  error?: string;
  htmlFor?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={htmlFor} className="text-xs font-medium text-slate-700">
        {label}
      </label>
      {children}
      {error ? (
        <p role="alert" className="text-xs text-red-600">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function TextInput({
  label,
  error,
  id,
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string }) {
  return (
    <FieldShell label={label} error={error} htmlFor={id}>
      <input id={id} className={CONTROL_CLASSES} {...rest} />
    </FieldShell>
  );
}

export function TextArea({
  label,
  error,
  id,
  ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string; error?: string }) {
  return (
    <FieldShell label={label} error={error} htmlFor={id}>
      <textarea id={id} className={CONTROL_CLASSES} rows={3} {...rest} />
    </FieldShell>
  );
}

export function SelectInput({
  label,
  error,
  id,
  options,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  error?: string;
  options: readonly string[];
}) {
  return (
    <FieldShell label={label} error={error} htmlFor={id}>
      <select id={id} className={CONTROL_CLASSES} {...rest}>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </FieldShell>
  );
}

export function CheckboxInput({
  label,
  id,
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <label htmlFor={id} className="flex items-center gap-2 text-sm text-slate-700">
      <input id={id} type="checkbox" className="size-4 accent-slate-800" {...rest} />
      {label}
    </label>
  );
}
