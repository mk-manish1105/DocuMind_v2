import { useState } from "react";

import {
  ArrowRight,
  Brain,
  Eye,
  EyeOff,
  FileText,
  MessageSquare,
  Search,
  ShieldCheck,
  Upload,
} from "lucide-react";

import {
  Link,
  useNavigate,
  useSearchParams,
} from "react-router-dom";

import { Button } from "../ui/Button";

import { useAuth } from "../../context/AuthContext";

import { useToast } from "../ui/ToastProvider";

import { extractErrorMessage } from "../../api/client";


const FIELD_CLASS =
  "w-full rounded-lg border border-ink-200 bg-white px-3.5 py-3 text-sm text-ink-900 placeholder:text-ink-400 transition-colors focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500";


const CAPABILITIES = [
  {
    icon: Brain,
    title: "General questions",
    description:
      "Ask about anything and get an AI-powered answer.",
  },
  {
    icon: FileText,
    title: "Your documents",
    description:
      "Upload files and ask questions about their content.",
  },
  {
    icon: MessageSquare,
    title: "Natural follow-ups",
    description:
      "Continue the conversation without repeating yourself.",
  },
];


const STEPS = [
  {
    number: "01",
    icon: Upload,
    title: "Ask",
  },
  {
    number: "02",
    icon: Search,
    title: "Understand",
  },
  {
    number: "03",
    icon: MessageSquare,
    title: "Answer",
  },
];


export default function AuthCard() {
  const [searchParams] = useSearchParams();

  const initialMode =
    searchParams.get("mode") === "register"
      ? "register"
      : "login";

  const [mode, setMode] =
    useState(initialMode);

  const [email, setEmail] =
    useState("");

  const [password, setPassword] =
    useState("");

  const [confirmPassword, setConfirmPassword] =
    useState("");

  const [fullName, setFullName] =
    useState("");

  const [showPassword, setShowPassword] =
    useState(false);

  const [submitting, setSubmitting] =
    useState(false);

  const {
    login,
    register,
    continueAsGuest,
  } = useAuth();

  const {
    showToast,
  } = useToast();

  const navigate =
    useNavigate();


  async function handleSubmit(e) {
    e.preventDefault();

    if (
      mode === "register" &&
      password !== confirmPassword
    ) {
      showToast(
        "Passwords don't match."
      );

      return;
    }

    setSubmitting(true);

    try {
      if (mode === "login") {
        await login(
          email,
          password
        );
      } else {
        await register(
          email,
          password,
          fullName
        );
      }

      navigate("/chat");

    } catch (err) {
      showToast(
        extractErrorMessage(
          err,
          "Authentication failed."
        )
      );

    } finally {
      setSubmitting(false);
    }
  }


  function handleGuest() {
    continueAsGuest();
    navigate("/chat");
  }


  function switchMode() {
    setMode(
      mode === "login"
        ? "register"
        : "login"
    );
  }


  return (
    <div className="min-h-screen bg-paper-50">

      {/* ================================================= */}
      {/* HEADER                                            */}
      {/* ================================================= */}

      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-5 py-5 sm:px-8">

        <Link
          to="/auth"
          className="flex items-center gap-2.5"
        >

          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-ink-900 text-xs font-bold text-white">
            DM
          </div>

          <span className="font-display text-lg font-semibold text-ink-900">
            DocuMind
          </span>

        </Link>


        <div className="hidden items-center gap-2 text-xs text-ink-400 sm:flex">

          <ShieldCheck className="h-3.5 w-3.5" />

          Private workspace

        </div>

      </header>


      {/* ================================================= */}
      {/* MAIN                                              */}
      {/* ================================================= */}

      <main className="mx-auto w-full max-w-6xl px-4 pb-8 pt-4 sm:px-8 sm:pt-8 lg:pb-14">

        <div className="grid overflow-hidden rounded-2xl border border-ink-200 bg-white shadow-panel lg:grid-cols-[1.15fr_0.85fr]">


          {/* ============================================= */}
          {/* PRODUCT SIDE                                  */}
          {/* ============================================= */}

          <section className="bg-ink-900 px-6 py-9 text-white sm:px-10 sm:py-11 lg:px-12 lg:py-14">

            <div className="max-w-xl">

              {/* Small introduction */}

              <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-400">
                AI assistant
              </p>


              {/* Main heading */}

              <h1 className="mt-4 max-w-lg font-display text-4xl font-medium leading-[1.08] tracking-tight sm:text-5xl">

                Ask questions.
                <br />

                <span className="text-highlight-400">
                  Get useful answers.
                </span>

              </h1>


              {/* Description */}

              <p className="mt-5 max-w-lg text-sm leading-6 text-ink-300 sm:text-[15px]">

                DocuMind is an adaptive AI assistant for
                everyday questions and document-based work.
                Ask normally, or give it a document when you
                need answers from your own content.

              </p>


              {/* ========================================= */}
              {/* CAPABILITIES                               */}
              {/* ========================================= */}

              <div className="mt-9 border-y border-white/10">

                {CAPABILITIES.map(
                  ({
                    icon: Icon,
                    title,
                    description,
                  }) => (

                    <div
                      key={title}
                      className="flex gap-4 border-b border-white/10 py-4 last:border-b-0"
                    >

                      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/10 text-ink-200">

                        <Icon className="h-4 w-4" />

                      </div>


                      <div>

                        <p className="text-sm font-medium text-white">
                          {title}
                        </p>

                        <p className="mt-1 text-xs leading-5 text-ink-400">
                          {description}
                        </p>

                      </div>

                    </div>

                  )
                )}

              </div>


              {/* ========================================= */}
              {/* HOW IT WORKS                               */}
              {/* ========================================= */}

              <div className="mt-9">

                <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-500">
                  How it works
                </p>


                <div className="mt-4 flex flex-wrap items-center gap-2">

                  {STEPS.map(
                    ({
                      number,
                      icon: Icon,
                      title,
                    }) => (

                      <div
                        key={number}
                        className="flex items-center"
                      >

                        <div className="flex items-center gap-2 rounded-lg bg-white/[0.06] px-3 py-2">

                          <span className="font-mono text-[10px] text-ink-500">
                            {number}
                          </span>

                          <Icon className="h-3.5 w-3.5 text-ink-300" />

                          <span className="text-xs font-medium text-ink-200">
                            {title}
                          </span>

                        </div>


                        {number !== "03" && (
                          <span className="mx-1.5 text-ink-600">
                            →
                          </span>
                        )}

                      </div>

                    )
                  )}

                </div>

              </div>


              {/* ========================================= */}
              {/* SIMPLE PRIVACY NOTE                        */}
              {/* ========================================= */}

              <div className="mt-9 flex items-start gap-2.5 border-t border-white/10 pt-5">

                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-ink-400" />

                <p className="text-xs leading-5 text-ink-400">

                  Your documents remain associated with your
                  account, while temporary attachments are
                  used only for the current request.

                </p>

              </div>

            </div>

          </section>


          {/* ============================================= */}
          {/* AUTH SIDE                                     */}
          {/* ============================================= */}

          <section className="bg-paper-50 px-5 py-9 sm:px-10 sm:py-11 lg:px-10 lg:py-14">

            <div className="mx-auto w-full max-w-sm">


              {/* Form heading */}

              <div>

                <p className="text-xs font-medium uppercase tracking-[0.14em] text-brand-600">
                  {mode === "login"
                    ? "Sign in"
                    : "Get started"}
                </p>


                <h2 className="mt-2 font-display text-3xl font-medium tracking-tight text-ink-900">

                  {mode === "login"
                    ? "Welcome back."
                    : "Create your account."}

                </h2>


                <p className="mt-2 text-sm leading-6 text-ink-500">

                  {mode === "login"
                    ? "Continue to your DocuMind workspace."
                    : "Start asking questions and working with your documents."}

                </p>

              </div>


              {/* ========================================= */}
              {/* FORM                                      */}
              {/* ========================================= */}

              <form
                className="mt-7 space-y-4"
                onSubmit={handleSubmit}
              >

                {/* Full name */}

                {mode === "register" && (

                  <div>

                    <label
                      htmlFor="full-name"
                      className="mb-1.5 block text-xs font-medium text-ink-700"
                    >
                      Full name
                    </label>

                    <input
                      id="full-name"
                      type="text"
                      placeholder="Your name"
                      value={fullName}
                      onChange={(e) =>
                        setFullName(
                          e.target.value
                        )
                      }
                      className={FIELD_CLASS}
                    />

                  </div>

                )}


                {/* Email */}

                <div>

                  <label
                    htmlFor="email"
                    className="mb-1.5 block text-xs font-medium text-ink-700"
                  >
                    Email address
                  </label>

                  <input
                    id="email"
                    type="email"
                    required
                    placeholder="you@example.com"
                    autoComplete="email"
                    value={email}
                    onChange={(e) =>
                      setEmail(
                        e.target.value
                      )
                    }
                    className={FIELD_CLASS}
                  />

                </div>


                {/* Password */}

                <div>

                  <label
                    htmlFor="password"
                    className="mb-1.5 block text-xs font-medium text-ink-700"
                  >
                    Password
                  </label>


                  <div className="relative">

                    <input
                      id="password"
                      type={
                        showPassword
                          ? "text"
                          : "password"
                      }
                      required
                      minLength={6}
                      placeholder="Enter your password"
                      autoComplete={
                        mode === "login"
                          ? "current-password"
                          : "new-password"
                      }
                      value={password}
                      onChange={(e) =>
                        setPassword(
                          e.target.value
                        )
                      }
                      className={`${FIELD_CLASS} pr-11`}
                    />


                    <button
                      type="button"
                      onClick={() =>
                        setShowPassword(
                          (value) =>
                            !value
                        )
                      }
                      aria-label={
                        showPassword
                          ? "Hide password"
                          : "Show password"
                      }
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-400 transition-colors hover:text-ink-700"
                    >

                      {showPassword ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}

                    </button>

                  </div>

                </div>


                {/* Confirm password */}

                {mode === "register" && (

                  <div>

                    <label
                      htmlFor="confirm-password"
                      className="mb-1.5 block text-xs font-medium text-ink-700"
                    >
                      Confirm password
                    </label>

                    <input
                      id="confirm-password"
                      type={
                        showPassword
                          ? "text"
                          : "password"
                      }
                      required
                      minLength={6}
                      placeholder="Confirm your password"
                      autoComplete="new-password"
                      value={confirmPassword}
                      onChange={(e) =>
                        setConfirmPassword(
                          e.target.value
                        )
                      }
                      className={FIELD_CLASS}
                    />

                  </div>

                )}


                {/* Submit */}

                <Button
                  type="submit"
                  className="w-full"
                  size="lg"
                  loading={submitting}
                >

                  {mode === "login"
                    ? "Sign in"
                    : "Create account"}

                  <ArrowRight className="h-4 w-4" />

                </Button>


                {/* Guest */}

                <div className="relative py-1">

                  <div className="absolute inset-0 flex items-center">

                    <div className="w-full border-t border-ink-200" />

                  </div>


                  <div className="relative flex justify-center">

                    <span className="bg-paper-50 px-3 text-[11px] text-ink-400">
                      or
                    </span>

                  </div>

                </div>


                <Button
                  type="button"
                  variant="secondary"
                  size="lg"
                  className="w-full"
                  onClick={handleGuest}
                >

                  Continue as guest

                </Button>

              </form>


              {/* ========================================= */}
              {/* SWITCH MODE                                */}
              {/* ========================================= */}

              <div className="mt-7 text-center">

                <p className="text-sm text-ink-500">

                  {mode === "login"
                    ? "Don't have an account?"
                    : "Already have an account?"}

                  {" "}

                  <button
                    type="button"
                    onClick={switchMode}
                    className="font-medium text-brand-600 hover:text-brand-700 hover:underline"
                  >

                    {mode === "login"
                      ? "Create one"
                      : "Sign in"}

                  </button>

                </p>

              </div>


              {/* ========================================= */}
              {/* SMALL GUEST NOTE                          */}
              {/* ========================================= */}

              <p className="mt-6 text-center text-[11px] leading-5 text-ink-400">

                Guest access supports general AI
                conversations. Sign in to upload and manage
                your personal documents.

              </p>

            </div>

          </section>

        </div>

      </main>


      {/* Small footer */}

      <footer className="mx-auto max-w-6xl px-5 pb-6 sm:px-8">

        <p className="text-center text-[11px] text-ink-400">
          DocuMind · Adaptive AI assistant
        </p>

      </footer>

    </div>
  );
}