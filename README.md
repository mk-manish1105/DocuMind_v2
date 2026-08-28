# DocuMind

DocuMind is a document assistant I built to solve a pretty specific annoyance: most "chat with your PDF" tools either dump your entire document into a prompt (expensive, slow, and bad once files get long) or lose track of documents between sessions. DocuMind splits the difference — it extracts, chunks, and embeds your documents into a proper vector store, then retrieves only the relevant pieces when you ask a question, so the answers stay grounded and the app stays fast even as your document library grows.

It's also adaptive rather than strictly RAG-only — not every question is about your documents, so the assistant figures out whether a question needs document context or is just general knowledge, and routes it accordingly instead of forcing every query through retrieval. Ask "what's in my contract" and it pulls from your files; ask "what's a NDA" and it just answers from the model directly.

You can either upload documents permanently (they get processed, embedded, and stored so you can ask about them anytime) or drop one into a chat as a one-off attachment for quick analysis without it ever touching your permanent library. Both flows are handled completely separately under the hood.

**Live demo:** https://documind-lemon.vercel.app/

---

## What it does

- Upload and manage PDF, DOCX, and TXT documents
- Adaptive query routing — automatically decides whether a question needs your document context or is just general knowledge, instead of always forcing retrieval
- Ask questions about your documents and get streamed, context-aware answers
- Attach a document directly in chat for a quick one-off summary/analysis — it's discarded after the request and never added to your library
- Persistent chat sessions with history, auto-generated titles, rename/delete
- Follow-up questions get rewritten internally for retrieval (so "why did they choose it?" still pulls the right context) without touching what's actually shown in the conversation
- Guest mode if you just want to try it without signing up

## How it's put together

```
React (Vite) — Vercel            FastAPI — Render
     │                                 │
     └───────────── REST/HTTPS ────────┘
                                        │
                          ┌─────────────┴─────────────┐
                          │                            │
                   Supabase Storage           Supabase Postgres + pgvector
                    (permanent files)            (chunks + embeddings)
                                        │
                          ┌─────────────┴─────────────┐
                          │                            │
                    Hugging Face                    Groq
                   (embeddings)                (LLM, streamed)
```

The main design decision I care about here: nothing permanent lives on Render's filesystem. Uploaded files pass through a temporary `/tmp` path just long enough to get extracted and embedded, and the actual persistent state — files and vectors — lives in Supabase. That means redeploys and restarts on Render don't cost you any data.

**Frontend** — React 19, Vite, Tailwind, React Router, Axios, react-markdown + rehype-highlight for rendering assistant responses (tables, code blocks, etc. all work).

**Backend** — FastAPI, SQLAlchemy, JWT auth (bcrypt via Passlib), PyMuPDF for PDF extraction, python-docx for Word files, background tasks for the processing pipeline so uploads don't block.

**AI layer** — embeddings via `BAAI/bge-small-en-v1.5` (384-dim, called through a Hugging Face inference endpoint rather than loaded locally — keeps Render lightweight), completions via Groq's OpenAI-compatible API (`gpt-oss-20b`), streamed token-by-token back to the client.

## The document pipeline

When you upload a permanent document:

1. File goes to Supabase Storage, a DB record is created with `status: processing`
2. Backend pulls it into a temp file, extracts text (extraction method depends on file type)
3. Text gets cleaned and chunked (~500 tokens per chunk, 80-token overlap so context doesn't get cut off mid-thought)
4. Each chunk gets embedded and the vectors go into Postgres via pgvector
5. Status flips to `ready`, temp file gets deleted

From there, asking a question triggers a similarity search scoped to *your* documents only — retrieval is always filtered by `user_id`, so there's no risk of one user's question pulling context from someone else's files.

Temporary attachments skip all of this — they get extracted, chunked, and indexed into an in-memory FAISS index that only exists for the duration of that one request, then it's gone.

## Running it locally

```bash
# backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

# frontend
cd frontend
npm install
npm run dev
```

You'll need your own Supabase project (Postgres + pgvector extension enabled, plus a storage bucket), a Groq API key, and a Hugging Face inference endpoint for embeddings. Copy `.env.example` to `.env` in both folders and fill in the keys.

## Notes on scope

This isn't trying to be a general-purpose RAG framework — it's opinionated toward the "personal document library + chat" use case, which is why things like the permanent/temporary split and per-user isolation are baked into the architecture rather than left as configuration. If you're looking to extend it, the extraction, chunking, and embedding steps are each isolated into their own service module so swapping out a piece (a different embedding model, OCR for scanned PDFs, etc.) shouldn't require touching the rest of the pipeline.
