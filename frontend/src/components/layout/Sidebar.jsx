import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  Check,
  LogOut,
  MessageSquarePlus,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { Spinner } from "../ui/Spinner";
import DocumentRow from "../documents/DocumentRow";
import { useAuth } from "../../context/AuthContext";

function SessionRow({ session, active, onSelect, onRename, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(session.title || "Untitled chat");

  function submitRename() {
    const trimmed = title.trim();
    if (trimmed && trimmed !== session.title) onRename(session.id, trimmed);
    setEditing(false);
  }

  return (
    <div
      onClick={() => !editing && onSelect(session.id)}
      className={`group flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-sm transition-colors ${
        active ? "bg-brand-50 text-brand-700" : "text-ink-600 hover:bg-ink-50"
      }`}
    >
      {editing ? (
        <input
          autoFocus
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onClick={(e) => e.stopPropagation()}
          onBlur={submitRename}
          onKeyDown={(e) => e.key === "Enter" && submitRename()}
          className="min-w-0 flex-1 rounded border border-brand-300 px-1.5 py-0.5 text-sm focus:outline-none"
        />
      ) : (
        <span className="min-w-0 flex-1 truncate">{session.title || "Untitled chat"}</span>
      )}
      <div className="hidden shrink-0 items-center gap-0.5 group-hover:flex">
        {editing ? (
          <button onClick={(e) => { e.stopPropagation(); submitRename(); }} className="rounded p-1 hover:bg-white">
            <Check className="h-3.5 w-3.5" />
          </button>
        ) : (
          <>
            <button onClick={(e) => { e.stopPropagation(); setEditing(true); }} className="rounded p-1 hover:bg-white">
              <Pencil className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(session.id); }}
              className="rounded p-1 text-red-500 hover:bg-white"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export default function Sidebar({
  isOpen,
  onToggle,
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onRenameSession,
  onDeleteSession,
  documents,
  onUpload,
  onRenameDocument,
  onDeleteDocument,
  uploadProgress,
}) {
  const { user, isGuest, logout } = useAuth();
  const fileInputRef = useRef(null);
  const [collapsed, setCollapsed] = useState(false);

  return (
    <>
      {isOpen && <div className="fixed inset-0 z-20 bg-ink-900/40 lg:hidden" onClick={onToggle} />}
      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-72 shrink-0 flex-col border-r border-ink-100 bg-white transition-all duration-200 lg:static ${
          isOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        } ${collapsed ? "lg:w-19" : "lg:w-72"}`}
      >
        <div className="flex items-center justify-between gap-2 border-b border-ink-100 p-3">
          <Link
            to="/"
            className={`flex items-center gap-2 font-semibold text-ink-900 ${collapsed ? "lg:hidden" : ""}`}
          >
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-ink-900 text-xs font-bold text-white">
              DM
            </div>
            <span className="font-display">DocuMind</span>
          </Link>
          <div className={`hidden h-7 w-7 items-center justify-center rounded-lg bg-ink-900 text-xs font-bold text-white ${collapsed ? "lg:flex" : ""}`}>
            DM
          </div>

          {/* Desktop collapse toggle — always visible, never hidden behind another action */}
          <button
            onClick={() => setCollapsed((v) => !v)}
            className="hidden rounded-md p-1.5 text-ink-400 hover:bg-ink-100 hover:text-ink-700 lg:inline-flex"
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </button>
          {/* Mobile close */}
          <button onClick={onToggle} className="rounded-md p-1.5 text-ink-400 hover:bg-ink-100 lg:hidden">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-3">
          <button
            onClick={onNewChat}
            title="New chat"
            className={`flex w-full items-center gap-2 rounded-lg border border-ink-200 px-3 py-2 text-sm font-medium text-ink-700 hover:bg-ink-50 ${
              collapsed ? "lg:justify-center lg:px-2" : ""
            }`}
          >
            <MessageSquarePlus className="h-4 w-4 shrink-0" />
            <span className={collapsed ? "lg:hidden" : ""}>New chat</span>
          </button>
        </div>

        <div className={`flex-1 space-y-0.5 overflow-y-auto px-2 ${collapsed ? "lg:hidden" : ""}`}>
          {sessions.length === 0 ? (
            <p className="px-2.5 py-2 text-xs text-ink-400">
              {isGuest ? "Guest chats aren't saved." : "No conversations yet."}
            </p>
          ) : (
            sessions.map((s) => (
              <SessionRow
                key={s.id}
                session={s}
                active={s.id === activeSessionId}
                onSelect={onSelectSession}
                onRename={onRenameSession}
                onDelete={onDeleteSession}
              />
            ))
          )}
        </div>
        {collapsed && <div className="hidden flex-1 lg:block" />}

        <div className={`border-t border-ink-100 p-3 ${collapsed ? "lg:hidden" : ""}`}>
          <div className="mb-1.5 flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-400">Documents</p>
            {isGuest && <span className="text-[11px] text-ink-400">Sign in to upload</span>}
          </div>

          {!isGuest && (
            <>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.docx,.txt"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files?.length) onUpload(e.target.files);
                  e.target.value = "";
                }}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadProgress !== null}
                className="mb-2 flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-ink-300 px-3 py-2 text-sm text-ink-600 hover:bg-ink-50 disabled:opacity-60"
              >
                {uploadProgress !== null ? (
                  <>
                    <Spinner className="h-3.5 w-3.5" /> Uploading {uploadProgress}%
                  </>
                ) : (
                  <>
                    <Upload className="h-4 w-4" /> Upload PDF, DOCX, TXT
                  </>
                )}
              </button>

              <div className="max-h-40 overflow-y-auto">
                {documents.length === 0 ? (
                  <p className="px-2 py-1.5 text-xs text-ink-400">No documents yet.</p>
                ) : (
                  documents.map((doc) => (
                    <DocumentRow key={doc.id} document={doc} onRename={onRenameDocument} onDelete={onDeleteDocument} />
                  ))
                )}
              </div>
            </>
          )}
        </div>

        <div className={`flex items-center gap-2.5 border-t border-ink-100 p-3 ${collapsed ? "lg:justify-center" : ""}`}>
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700">
            {isGuest ? "G" : (user?.full_name || user?.email || "U").slice(0, 2).toUpperCase()}
          </div>
          <div className={`min-w-0 flex-1 ${collapsed ? "lg:hidden" : ""}`}>
            <p className="truncate text-sm font-medium text-ink-800">{isGuest ? "Guest" : user?.full_name || user?.email}</p>
            <p className="text-xs text-ink-400">{isGuest ? "Not saving history" : "Signed in"}</p>
          </div>
          <button
            onClick={logout}
            className={`rounded p-1.5 text-ink-400 hover:bg-red-50 hover:text-red-600 ${collapsed ? "lg:hidden" : ""}`}
            title="Log out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </aside>
    </>
  );
}
