import {
  useCallback,
  useEffect,
  useState,
} from "react";

import Sidebar from "../components/layout/Sidebar";
import ChatWindow from "../components/chat/ChatWindow";

import { useAuth } from "../context/AuthContext";
import { useToast } from "../components/ui/ToastProvider";

import { useChatStream } from "../hooks/useChatStream";

import { extractErrorMessage } from "../api/client";

import {
  deleteSession as apiDeleteSession,
  fetchHistory,
  listSessions,
  renameSession as apiRenameSession,
} from "../api/chat";

import {
  deleteDocument as apiDeleteDocument,
  listDocuments,
  renameDocument as apiRenameDocument,
  uploadDocuments,
} from "../api/documents";


export default function ChatPage() {
  const {
    isGuest,
  } = useAuth();

  const {
    showToast,
  } = useToast();


  /* ======================================================
     UI STATE
  ====================================================== */

  const [
    sidebarOpen,
    setSidebarOpen,
  ] = useState(false);


  /* ======================================================
     PERMANENT CHAT SESSIONS
  ====================================================== */

  const [
    sessions,
    setSessions,
  ] = useState([]);


  const [
    activeSessionId,
    setActiveSessionId,
  ] = useState(null);


  const [
    messages,
    setMessages,
  ] = useState([]);


  /* ======================================================
     PERMANENT DOCUMENT LIBRARY
     
     These documents are:
       - stored permanently
       - shown in Sidebar
       - indexed in FAISS
       - searchable across chats
  ====================================================== */

  const [
    documents,
    setDocuments,
  ] = useState([]);


  /* ======================================================
     TEMPORARY DOCUMENT
     
     IMPORTANT:
     
     This is NOT the same as `documents`.
     
     This File object:
       - lives only in browser memory
       - is not uploaded to /documents/upload
       - is not saved in DB
       - is not indexed in FAISS
       - is sent directly to /chat
  ====================================================== */

  const [
    attachedFile,
    setAttachedFile,
  ] = useState(null);


  /* ======================================================
     OTHER STATE
  ====================================================== */

  const [
    loadingHistory,
    setLoadingHistory,
  ] = useState(false);


  const [
    uploadProgress,
    setUploadProgress,
  ] = useState(null);


  /* ======================================================
     LOAD PERMANENT SESSIONS
  ====================================================== */

  const refreshSessions =
    useCallback(
      async () => {
        if (isGuest) {
          return;
        }

        try {
          const data =
            await listSessions();

          setSessions(data);

        } catch (err) {
          showToast(
            extractErrorMessage(
              err,
              "Couldn't load your chats."
            )
          );
        }
      },
      [
        isGuest,
        showToast,
      ]
    );


  /* ======================================================
     LOAD PERMANENT DOCUMENTS
  ====================================================== */

  const refreshDocuments =
    useCallback(
      async () => {
        if (isGuest) {
          return;
        }

        try {
          const data =
            await listDocuments();

          setDocuments(data);

        } catch (err) {
          showToast(
            extractErrorMessage(
              err,
              "Couldn't load your documents."
            )
          );
        }
      },
      [
        isGuest,
        showToast,
      ]
    );


  /* ======================================================
     INITIAL LOAD
  ====================================================== */

  /* eslint-disable react-hooks/set-state-in-effect */

  useEffect(() => {
    refreshSessions();
    refreshDocuments();
  }, [
    refreshSessions,
    refreshDocuments,
  ]);

  /* eslint-enable react-hooks/set-state-in-effect */


  /* ======================================================
     POLL PERMANENT DOCUMENT PROCESSING
  ====================================================== */

  useEffect(() => {
    if (isGuest) {
      return;
    }

    const hasProcessing =
      documents.some(
        (document) =>
          document.status ===
          "processing"
      );

    if (!hasProcessing) {
      return;
    }

    const interval =
      setInterval(
        refreshDocuments,
        3000
      );

    return () =>
      clearInterval(
        interval
      );

  }, [
    documents,
    isGuest,
    refreshDocuments,
  ]);


  /* ======================================================
     SELECT EXISTING CHAT
  ====================================================== */

  async function handleSelectSession(
    id
  ) {
    setActiveSessionId(id);

    setSidebarOpen(false);

    setLoadingHistory(true);

    /*
     * Temporary attachments never belong
     * to an existing conversation.
     */
    setAttachedFile(null);

    try {
      const history =
        await fetchHistory(id);

      setMessages(history);

    } catch (err) {
      showToast(
        extractErrorMessage(
          err,
          "Couldn't load that conversation."
        )
      );

    } finally {
      setLoadingHistory(
        false
      );
    }
  }


  /* ======================================================
     NEW CHAT
  ====================================================== */

  function handleNewChat() {
    setActiveSessionId(
      null
    );

    setMessages([]);

    setAttachedFile(
      null
    );

    setSidebarOpen(
      false
    );
  }


  /* ======================================================
     TEMPORARY FILE
  ====================================================== */

  function handleAttachFile(
    file
  ) {
    /*
     * Replace any existing temporary
     * attachment.
     *
     * This does NOT upload anything.
     */
    setAttachedFile(
      file
    );
  }


  function handleRemoveAttachment() {
    setAttachedFile(
      null
    );
  }


  function handleTemporaryAttachmentConsumed() {
    /*
     * Called by useChatStream after
     * the temporary request finishes.
     */
    setAttachedFile(
      null
    );
  }


  /* ======================================================
     RENAME CHAT
  ====================================================== */

  async function handleRenameSession(
    id,
    title
  ) {
    setSessions(
      (prev) =>
        prev.map(
          (session) =>
            session.id === id
              ? {
                  ...session,
                  title,
                }
              : session
        )
    );

    try {
      await apiRenameSession(
        id,
        title
      );

    } catch (err) {
      showToast(
        extractErrorMessage(
          err,
          "Couldn't rename that chat."
        )
      );

      refreshSessions();
    }
  }


  /* ======================================================
     DELETE CHAT
  ====================================================== */

  async function handleDeleteSession(
    id
  ) {
    const previous =
      sessions;

    setSessions(
      (prev) =>
        prev.filter(
          (session) =>
            session.id !== id
        )
    );

    if (
      activeSessionId === id
    ) {
      handleNewChat();
    }

    try {
      await apiDeleteSession(
        id
      );

    } catch (err) {
      showToast(
        extractErrorMessage(
          err,
          "Couldn't delete that chat."
        )
      );

      setSessions(
        previous
      );
    }
  }


  /* ======================================================
     PERMANENT DOCUMENT UPLOAD
     
     IMPORTANT:
     
     This is completely separate from the
     temporary Composer attachment.
  ====================================================== */

  async function handleUpload(
    files
  ) {
    setUploadProgress(
      0
    );

    try {
      await uploadDocuments(
        files,
        setUploadProgress
      );

      showToast(
        `${files.length} file(s) uploaded — processing now.`,
        "success"
      );

      await refreshDocuments();

    } catch (err) {
      showToast(
        extractErrorMessage(
          err,
          "Upload failed."
        )
      );

    } finally {
      setUploadProgress(
        null
      );
    }
  }


  /* ======================================================
     RENAME PERMANENT DOCUMENT
  ====================================================== */

  async function handleRenameDocument(
    id,
    title
  ) {
    setDocuments(
      (prev) =>
        prev.map(
          (document) =>
            document.id === id
              ? {
                  ...document,
                  title,
                }
              : document
        )
    );

    try {
      await apiRenameDocument(
        id,
        title
      );

    } catch (err) {
      showToast(
        extractErrorMessage(
          err,
          "Couldn't rename that document."
        )
      );

      refreshDocuments();
    }
  }


  /* ======================================================
     DELETE PERMANENT DOCUMENT
  ====================================================== */

  async function handleDeleteDocument(
    id
  ) {
    const previous =
      documents;

    setDocuments(
      (prev) =>
        prev.filter(
          (document) =>
            document.id !== id
        )
    );

    try {
      await apiDeleteDocument(
        id
      );

    } catch (err) {
      showToast(
        extractErrorMessage(
          err,
          "Couldn't delete that document."
        )
      );

      setDocuments(
        previous
      );
    }
  }


  /* ======================================================
     CHAT STREAM
  ====================================================== */

  const {
    sendMessage,
    stopStreaming,
    isStreaming,
  } = useChatStream({
    setMessages,
    sessionId:
      activeSessionId,

    onSessionCreated:
      (id) => {
        setActiveSessionId(
          id
        );

        refreshSessions();
      },

    onTemporaryAttachmentConsumed:
      handleTemporaryAttachmentConsumed,
  });


  /* ======================================================
     ACTIVE SESSION
  ====================================================== */

  const activeSession =
    sessions.find(
      (session) =>
        session.id ===
        activeSessionId
    );


  /* ======================================================
     RENDER
  ====================================================== */

  return (
    <div
      className="
        flex
        h-screen
        overflow-hidden
        bg-paper-50
      "
    >

      {/* ==================================================
          SIDEBAR

          Contains ONLY permanent documents.
      ================================================== */}

      <Sidebar
        isOpen={
          sidebarOpen
        }

        onToggle={() =>
          setSidebarOpen(
            (value) =>
              !value
          )
        }

        sessions={
          sessions
        }

        activeSessionId={
          activeSessionId
        }

        onSelectSession={
          handleSelectSession
        }

        onNewChat={
          handleNewChat
        }

        onRenameSession={
          handleRenameSession
        }

        onDeleteSession={
          handleDeleteSession
        }

        documents={
          documents
        }

        onUpload={
          handleUpload
        }

        onRenameDocument={
          handleRenameDocument
        }

        onDeleteDocument={
          handleDeleteDocument
        }

        uploadProgress={
          uploadProgress
        }
      />


      {/* ==================================================
          MAIN CHAT
      ================================================== */}

      <ChatWindow
        messages={
          messages
        }

        onSend={
          sendMessage
        }

        isStreaming={
          isStreaming
        }

        onStop={
          stopStreaming
        }

        loadingHistory={
          loadingHistory
        }

        onOpenSidebar={() =>
          setSidebarOpen(
            true
          )
        }

        isGuest={
          isGuest
        }

        sessionTitle={
          activeSession?.title
        }

        attachedFile={
          attachedFile
        }

        onAttachFile={
          handleAttachFile
        }

        onRemoveAttachment={
          handleRemoveAttachment
        }
      />

    </div>
  );
}