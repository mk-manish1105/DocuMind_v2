import { Spinner } from "./Spinner";

const VARIANTS = {
  primary: "bg-brand-500 text-white hover:bg-brand-600 shadow-panel disabled:hover:bg-brand-500",
  secondary: "bg-white text-ink-700 border border-ink-200 hover:bg-ink-50",
  outline: "bg-transparent text-ink-900 border border-ink-900/15 hover:bg-ink-900/5",
  ghost: "text-ink-600 hover:bg-ink-100",
  danger: "text-red-600 hover:bg-red-50",
  dark: "bg-ink-900 text-white hover:bg-ink-800 shadow-panel",
};

const SIZES = {
  sm: "px-3 py-1.5 text-sm",
  md: "px-4 py-2.5 text-sm",
  lg: "px-6 py-3.5 text-base",
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  className = "",
  children,
  disabled,
  ...props
}) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:opacity-60 disabled:cursor-not-allowed";

  return (
    <button
      className={`${base} ${SIZES[size]} ${VARIANTS[variant]} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Spinner className="h-4 w-4" />}
      {children}
    </button>
  );
}
