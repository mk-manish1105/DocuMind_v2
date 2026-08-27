import { useState } from "react";
import { Check, FileText, Loader2, Pencil, Trash2, X, AlertCircle } from "lucide-react";

const STATUS_CONFIG = {
  processing: { label: "Processing", className: "text-amber-600 bg-amber-50" },
  ready: { label: "Ready", className: "text-emerald-600 bg-emerald-50" },
  failed: { label: "Failed", className: "text-red-600 bg-red-50" },
};

export default function DocumentRow({ document, onRename, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(document.title);
  const status = STATUS_CONFIG[document.status] || STATUS_CONFIG.ready;

  function submitRename() {
    const trimmed = title.trim();
    if (trimmed && trimmed !== document.title) onRename(document.id, trimmed);
    else setTitle(document.title);
    setEditing(false);
  }

  return (
    <div className="group flex items-center gap-2 rounded-lg px-2 py-2 hover:bg-ink-100">
      <FileText className="h-4 w-4 text-ink-400 shrink-0" />
      {editing ? (
        <input
          autoFocus
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onBlur={submitRename}
          onKeyDown={(e) => {
            if (e.key === "Enter") submitRename();
            if (e.key === "Escape") { setTitle(document.title); setEditing(false); }
          }}
          className="flex-1 min-w-0 rounded border border-brand-300 px-1.5 py-0.5 text-sm focus:outline-none"
        />
      ) : (
        <span className="flex-1 min-w-0 truncate text-sm text-ink-700" title={document.title}>
          {document.title}
        </span>
      )}

      {document.status === "processing" && <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-500 shrink-0" />}
      {document.status === "failed" && <AlertCircle className="h-3.5 w-3.5 text-red-500 shrink-0" />}

      {!editing && (
        <span className={`hidden sm:inline-block shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${status.className}`}>
          {status.label}
        </span>
      )}

      <div className="hidden group-hover:flex items-center gap-0.5 shrink-0">
        {editing ? (
          <>
            <button onClick={submitRename} className="p-1 text-emerald-600 hover:bg-emerald-50 rounded"><Check className="h-3.5 w-3.5" /></button>
            <button onClick={() => { setTitle(document.title); setEditing(false); }} className="p-1 text-ink-400 hover:bg-ink-200 rounded"><X className="h-3.5 w-3.5" /></button>
          </>
        ) : (
          <>
            <button onClick={() => setEditing(true)} className="p-1 text-ink-400 hover:text-ink-700 hover:bg-ink-200 rounded"><Pencil className="h-3.5 w-3.5" /></button>
            <button onClick={() => onDelete(document.id)} className="p-1 text-ink-400 hover:text-red-600 hover:bg-red-50 rounded"><Trash2 className="h-3.5 w-3.5" /></button>
          </>
        )}
      </div>
    </div>
  );
}