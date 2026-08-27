import { Sparkles } from "lucide-react";


export default function EmptyState({ isGuest }) {
  return (
    <div
      className="
        flex
        h-full
        flex-col
        items-center
        justify-center
        px-6
        text-center
      "
    >

      {/* Icon */}

      <div
        className="
          mb-5
          flex
          h-12
          w-12
          items-center
          justify-center
          rounded-2xl
          bg-brand-500
          text-white
          shadow-panel
        "
      >
        <Sparkles className="h-6 w-6" />
      </div>


      {/* Heading */}

      <h2
        className="
          font-display
          text-xl
          font-medium
          text-ink-900
        "
      >
        Ask me anything
      </h2>


      {/* Description */}

      <p
        className="
          mt-2
          max-w-md
          text-sm
          leading-6
          text-ink-500
        "
      >
        {isGuest
          ? "Ask general questions and get useful AI-powered answers. Sign in when you want to upload documents and ask questions about their content."
          : "Ask a general question or upload a document when you want answers based on your own content."
        }
      </p>

    </div>
  );
}