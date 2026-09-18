import { useRef, useState } from "react";

import {
  ArrowUp,
  FileText,
  Paperclip,
  Square,
  X,
} from "lucide-react";

import { useAutoResizeTextarea } from "../../hooks/useAutoResizeTextarea";


const MAX_FILE_SIZE_MB = 20;

const ALLOWED_EXTENSIONS = [
  ".pdf",
  ".docx",
  ".txt",
  ".png",
  ".jpg",
  ".jpeg",
  ".webp",
];


export default function Composer({
  onSend,
  isStreaming,
  onStop,
  attachedFile,
  onAttachFile,
  onRemoveAttachment,
}) {
  const [value, setValue] =
    useState("");

  const fileInputRef =
    useRef(null);

  const textareaRef =
    useAutoResizeTextarea(
      value
    );


  function handleFileChange(
    event
  ) {
    const file =
      event.target.files?.[0];

    if (!file) {
      return;
    }

    const extension =
      "." +
      file.name
        .split(".")
        .pop()
        .toLowerCase();

    if (
      !ALLOWED_EXTENSIONS.includes(
        extension
      )
    ) {
      alert(
        "Only PDF, DOCX and TXT files are supported."
      );

      event.target.value =
        "";

      return;
    }

    const maxBytes =
      MAX_FILE_SIZE_MB *
      1024 *
      1024;

    if (
      file.size >
      maxBytes
    ) {
      alert(
        `File must be smaller than ${MAX_FILE_SIZE_MB} MB.`
      );

      event.target.value =
        "";

      return;
    }

    /*
     * IMPORTANT:
     *
     * This does NOT upload the file.
     *
     * It only stores the browser File object
     * in React state.
     */
    onAttachFile(file);

    /*
     * Allows selecting the same file again.
     */
    event.target.value =
      "";
  }


  function handleSubmit(
    event
  ) {
    event.preventDefault();

    if (isStreaming) {
      return;
    }

    const trimmed =
      value.trim();

    /*
     * Do not send an empty message
     * unless a document is attached.
     */
    if (
      !trimmed &&
      !attachedFile
    ) {
      return;
    }

    /*
     * If user attaches only a document,
     * automatically ask the backend to
     * analyze it.
     */
    const question =
      trimmed ||
      "Please analyze and summarize this document.";

    /*
     * Send:
     *
     * question
     * +
     * actual File object
     */
    onSend(
      question,
      attachedFile
    );

    setValue("");
  }


  return (
    <form
      onSubmit={handleSubmit}
      className="
        border-t
        border-ink-100
        bg-white
        p-3
        sm:p-4
      "
    >
      <div
        className="
          mx-auto
          max-w-3xl
          overflow-hidden
          rounded-2xl
          border
          border-ink-200
          bg-paper-50
          shadow-sm
          transition-shadow
          focus-within:border-brand-400
          focus-within:ring-2
          focus-within:ring-brand-100
        "
      >

        {/* =================================================
            TEMPORARY ATTACHMENT PREVIEW
        ================================================= */}

        {attachedFile && (
          <div
            className="
              flex
              items-center
              gap-3
              border-b
              border-ink-100
              bg-white
              px-4
              py-3
            "
          >

            <div
              className="
                flex
                h-9
                w-9
                shrink-0
                items-center
                justify-center
                rounded-lg
                bg-brand-100
                text-brand-600
              "
            >
              <FileText
                className="h-4 w-4"
              />
            </div>


            <div
              className="
                min-w-0
                flex-1
              "
            >
              <p
                className="
                  truncate
                  text-sm
                  font-medium
                  text-ink-800
                "
              >
                {attachedFile.name}
              </p>

              <p
                className="
                  text-xs
                  text-ink-400
                "
              >
                Temporary attachment ·
                not saved to Documents
              </p>
            </div>


            <button
              type="button"
              onClick={
                onRemoveAttachment
              }
              disabled={
                isStreaming
              }
              title="Remove attachment"
              className="
                rounded-md
                p-1.5
                text-ink-400
                transition-colors
                hover:bg-ink-100
                hover:text-ink-700
                disabled:opacity-50
              "
            >
              <X
                className="h-4 w-4"
              />
            </button>

          </div>
        )}


        {/* =================================================
            INPUT ROW
        ================================================= */}

        <div
          className="
            flex
            items-end
            gap-2
            px-3.5
            py-2.5
          "
        >

          {/* Hidden temporary file input */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.txt,.png,.jpg,.jpeg,.webp"
            className="hidden"
            onChange={
              handleFileChange
            }
          />


          {/* =================================================
              PLUS / ATTACHMENT BUTTON
          ================================================= */}

          <button
            type="button"
            onClick={() =>
              fileInputRef.current?.click()
            }
            disabled={
              isStreaming
            }
            title="Attach temporary document"
            aria-label="Attach temporary document"
            className="
              flex
              h-9
              w-9
              shrink-0
              items-center
              justify-center
              rounded-full
              border
              border-ink-200
              bg-white
              text-ink-500
              transition-colors
              hover:border-brand-300
              hover:bg-brand-50
              hover:text-brand-600
              disabled:cursor-not-allowed
              disabled:opacity-50
            "
          >
            <Paperclip
              className="h-4 w-4"
            />
          </button>


          {/* =================================================
              TEXT INPUT
          ================================================= */}

          <textarea
            ref={textareaRef}
            rows={1}
            value={value}
            onChange={(event) =>
              setValue(
                event.target.value
              )
            }
            onKeyDown={(event) => {
              if (
                event.key ===
                  "Enter" &&
                !event.shiftKey
              ) {
                event.preventDefault();

                handleSubmit(
                  event
                );
              }
            }}
            placeholder={
              attachedFile
                ? "Ask something about this document..."
                : "Ask a question about your documents..."
            }
            className="
              max-h-48
              flex-1
              resize-none
              bg-transparent
              py-1.5
              text-sm
              leading-6
              text-ink-900
              placeholder:text-ink-400
              focus:outline-none
            "
          />


          {/* =================================================
              SEND / STOP
          ================================================= */}

          {isStreaming ? (
            <button
              type="button"
              onClick={
                onStop
              }
              title="Stop generating"
              className="
                flex
                h-9
                w-9
                shrink-0
                items-center
                justify-center
                rounded-full
                bg-ink-800
                text-white
                transition-colors
                hover:bg-ink-900
              "
            >
              <Square
                className="h-3.5 w-3.5"
                fill="currentColor"
              />
            </button>
          ) : (
            <button
              type="submit"
              disabled={
                !value.trim() &&
                !attachedFile
              }
              title="Send message"
              className="
                flex
                h-9
                w-9
                shrink-0
                items-center
                justify-center
                rounded-full
                bg-brand-500
                text-white
                transition-colors
                hover:bg-brand-600
                disabled:cursor-not-allowed
                disabled:bg-ink-200
                disabled:text-ink-400
              "
            >
              <ArrowUp
                className="h-4 w-4"
              />
            </button>
          )}

        </div>
      </div>


      {/* =================================================
          HELP TEXT
      ================================================= */}

      <p
        className="
          mx-auto
          mt-2
          max-w-3xl
          text-center
          text-[11px]
          text-ink-400
        "
      >
        📎 Attach a temporary document
        · Enter to send
        · Shift + Enter for a new line
      </p>

    </form>
  );
}