import type { ReactNode } from "react";
import type { UseFormRegisterReturn } from "react-hook-form";
import { cn } from "@/lib/utils";

/** Shared, design-system form primitives used across features. */

export interface SelectOption {
  value: string;
  label: string;
}

export const controlClass =
  "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground shadow-sm outline-none transition placeholder:text-muted-foreground/60 focus:border-ring focus:ring-2 focus:ring-ring/25 aria-[invalid=true]:border-destructive aria-[invalid=true]:ring-destructive/20";

interface FieldShellProps {
  label: string;
  htmlFor?: string;
  required?: boolean;
  error?: string;
  hint?: string;
  children: ReactNode;
}

export function FieldShell({ label, htmlFor, required, error, hint, children }: FieldShellProps) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="flex items-center gap-1 text-xs font-medium text-muted-foreground">
        {label}
        {required && <span className="text-destructive">*</span>}
      </label>
      {children}
      {error ? (
        <p className="text-xs font-medium text-destructive">{error}</p>
      ) : hint ? (
        <p className="text-[11px] text-muted-foreground/70">{hint}</p>
      ) : null}
    </div>
  );
}

interface TextInputProps {
  label: string;
  registration: UseFormRegisterReturn;
  required?: boolean;
  error?: string;
  hint?: string;
  placeholder?: string;
}

export function TextInput({ label, registration, required, error, hint, placeholder }: TextInputProps) {
  return (
    <FieldShell label={label} htmlFor={registration.name} required={required} error={error} hint={hint}>
      <input
        id={registration.name}
        type="text"
        placeholder={placeholder}
        aria-invalid={!!error}
        className={controlClass}
        {...registration}
      />
    </FieldShell>
  );
}

interface NumberInputProps extends TextInputProps {
  min?: number;
  max?: number;
  step?: number;
  prefix?: string;
}

export function NumberInput({
  label,
  registration,
  required,
  error,
  hint,
  placeholder,
  min,
  max,
  step,
  prefix,
}: NumberInputProps) {
  return (
    <FieldShell label={label} htmlFor={registration.name} required={required} error={error} hint={hint}>
      <div className="relative">
        {prefix && (
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-xs font-medium text-muted-foreground">
            {prefix}
          </span>
        )}
        <input
          id={registration.name}
          type="number"
          inputMode="decimal"
          min={min}
          max={max}
          step={step ?? "any"}
          placeholder={placeholder}
          aria-invalid={!!error}
          className={cn(controlClass, prefix && "pl-7")}
          {...registration}
        />
      </div>
    </FieldShell>
  );
}

interface SelectInputProps {
  label: string;
  registration: UseFormRegisterReturn;
  options: SelectOption[];
  required?: boolean;
  error?: string;
  hint?: string;
}

export function SelectInput({ label, registration, options, required, error, hint }: SelectInputProps) {
  return (
    <FieldShell label={label} htmlFor={registration.name} required={required} error={error} hint={hint}>
      <select id={registration.name} aria-invalid={!!error} className={controlClass} {...registration}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </FieldShell>
  );
}
