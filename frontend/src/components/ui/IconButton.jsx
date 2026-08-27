export function IconButton({ className = "", label, children, ...props }) {
  return (
    <button
      aria-label={label}
      title={label}
      className={`inline-flex items-center justify-center h-8 w-8 rounded-md text-ink-500 hover:bg-ink-100 hover:text-ink-800 transition-colors ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}