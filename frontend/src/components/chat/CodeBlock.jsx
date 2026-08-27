import { useRef, useState } from "react";
import { Check, Copy } from "lucide-react";

export default function CodeBlock({ children }) {
  const codeRef = useRef(null);
  const [copied, setCopied] = useState(false);

  const codeElement = Array.isArray(children) ? children[0] : children;

  const className = codeElement?.props?.className || "";
  const languageMatch = /language-([\w-]+)/.exec(className);
  const language = languageMatch ? languageMatch[1] : "code";

  async function handleCopy() {
    const text = codeRef.current?.textContent || "";

    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);

      setTimeout(() => {
        setCopied(false);
      }, 1500);
    } catch (error) {
      console.error("Failed to copy code:", error);
    }
  }

  return (
    <div className="not-prose my-5 w-full min-w-0 overflow-hidden rounded-xl border border-ink-800 bg-ink-900 shadow-panel">
      {/* Code header */}
      <div className="flex items-center justify-between border-b border-white/10 bg-ink-900 px-4 py-2.5">
        <span className="font-mono text-[11px] font-medium uppercase tracking-wider text-ink-400">
          {language}
        </span>

        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium text-ink-300 transition-colors hover:bg-white/10 hover:text-white"
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5 text-emerald-400" />
              Copied
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" />
              Copy
            </>
          )}
        </button>
      </div>

      {/* Code */}
      <pre
        className="m-0 w-full max-w-full overflow-x-auto px-4 py-4"
        style={{
          background: "transparent",
        }}
      >
        <code
          ref={codeRef}
          className={`${className} block min-w-max font-mono text-[13px] leading-6`}
        >
          {codeElement?.props?.children}
        </code>
      </pre>
    </div>
  );
}