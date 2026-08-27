import { useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, Menu } from "lucide-react";

import MessageBubble from "./MessageBubble";
import Composer from "./Composer";
import EmptyState from "./EmptyState";

import { Spinner } from "../ui/Spinner";
import { Button } from "../ui/Button";


export default function ChatWindow({
  messages,
  onSend,
  isStreaming,
  onStop,
  loadingHistory,
  onOpenSidebar,
  isGuest,
  sessionTitle,

  attachedFile,
  onAttachFile,
  onRemoveAttachment,
}) {
  const bottomRef = useRef(null);

  const navigate = useNavigate();


  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages]);


  /*
   * Go back to the authentication page.
   *
   * We use React Router navigation instead of
   * window.history.back() so the user does not
   * accidentally leave the DocuMind application.
   */
  function handleBackToAuth() {
    navigate("/auth");
  }


  return (
    <div
      className="
        flex
        h-full
        min-w-0
        flex-1
        flex-col
        bg-paper-50
      "
    >

      {/* =================================================
          HEADER
      ================================================= */}

      <header
        className="
          flex
          items-center
          gap-3
          border-b
          border-ink-100
          bg-white/80
          px-4
          py-3
          backdrop-blur
        "
      >

        {/* =================================================
            DESKTOP BACK BUTTON

            Clicking this always goes to /auth.
        ================================================= */}

        <button
          type="button"
          onClick={handleBackToAuth}
          className="
            hidden
            rounded-md
            p-1.5
            text-ink-500
            transition-colors
            hover:bg-ink-100
            hover:text-ink-800
            lg:flex
            lg:items-center
            lg:justify-center
          "
          title="Back to sign in"
          aria-label="Back to sign in"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>


        {/* =================================================
            MOBILE SIDEBAR BUTTON

            On mobile this remains the sidebar button.
        ================================================= */}

        <button
          type="button"
          onClick={onOpenSidebar}
          className="
            rounded-md
            p-1.5
            text-ink-500
            transition-colors
            hover:bg-ink-100
            hover:text-ink-800
            lg:hidden
          "
          title="Open sidebar"
          aria-label="Open sidebar"
        >
          <Menu className="h-5 w-5" />
        </button>


        {/* =================================================
            CHAT TITLE
        ================================================= */}

        <p
          className="
            min-w-0
            flex-1
            truncate
            font-medium
            text-ink-800
          "
        >
          {sessionTitle || "New chat"}
        </p>


        {/* =================================================
            GUEST SIGN-UP
        ================================================= */}

        {isGuest && (
          <Link
            to="/auth?mode=register"
            className="shrink-0"
          >
            <Button
              size="sm"
              variant="secondary"
            >
              Sign up to save chats
            </Button>
          </Link>
        )}

      </header>


      {/* =================================================
          MESSAGES
      ================================================= */}

      <div
        className="
          flex-1
          overflow-y-auto
        "
      >

        {loadingHistory ? (

          <div
            className="
              flex
              h-full
              items-center
              justify-center
              text-ink-300
            "
          >
            <Spinner
              className="h-5 w-5"
            />
          </div>

        ) : messages.length === 0 ? (

          <EmptyState
            onSuggestionClick={onSend}
            isGuest={isGuest}
          />

        ) : (

          <div
            className="
              mx-auto
              w-full
              max-w-4xl
              space-y-6
              px-4
              py-6
              sm:px-6
            "
          >

            {messages.map(
              (message, index) => (
                <MessageBubble
                  key={index}
                  message={message}
                />
              )
            )}

            <div
              ref={bottomRef}
            />

          </div>
        )}

      </div>


      {/* =================================================
          COMPOSER
      ================================================= */}

      <Composer
        onSend={onSend}
        isStreaming={isStreaming}
        onStop={onStop}
        attachedFile={attachedFile}
        onAttachFile={onAttachFile}
        onRemoveAttachment={onRemoveAttachment}
      />

    </div>
  );
}