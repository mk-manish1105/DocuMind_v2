"""
Chat endpoints.

Permanent document behavior
---------------------------
If no temporary file is attached:
    1. Search the user's permanent FAISS index.
    2. Use relevant permanent document chunks when found.
    3. If nothing relevant is found, answer using general LLM knowledge.

Temporary document behavior
---------------------------
If a file is attached:
    1. Receive the actual uploaded file.
    2. Save it only to a temporary OS file.
    3. Extract its text.
    4. Delete the temporary OS file immediately.
    5. Use ONLY that extracted text for this request.
    6. NEVER search permanent documents.
    7. NEVER create a Document database record.
    8. NEVER add anything to the permanent FAISS index.

Supported temporary files:
    PDF, DOCX, TXT
"""

import json
import logging
import re
import tempfile
from pathlib import Path
from typing import Optional

import faiss
import numpy as np

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional
from app.core.config import settings

from app.db.models import (
    ChatMessage,
    ChatSession,
    User,
)

from app.db.session import SessionLocal, get_db

from app.schemas.chat import (
    ChatSessionRenameRequest,
    ChatSessionResponse,
)

from app.services.embeddings import embedding_service

from app.services.extraction import (
    chunk_text,
    clean_text,
    extract_text_from_file,
)

from app.services.llm_client import (
    chat_completion,
    stream_chat_completion,
)

from app.services.vector_store import (
    search_document_chunks,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are DocuMind, an intelligent AI assistant that helps users
understand documents and answer questions.

ANSWER STYLE:
- Give clear, accurate and useful answers.
- Prefer short paragraphs, headings and bullet points when useful.
- Be concise but sufficiently detailed.
- Never invent information.
- Never claim information came from a document unless that
  information is present in the supplied document context.

TEMPORARY ATTACHMENT RULES:
- If an ATTACHED DOCUMENT is supplied, it is the ONLY document
  you may use for that request.
- NEVER use the user's permanent document library when an
  attached document is supplied.
- The attached document is temporary request-only context.
- Do not assume information from previous documents.
- Do not search or refer to unrelated documents.

PERMANENT DOCUMENT RULES:
- Permanent document context may be supplied when no temporary
  attachment exists.
- Use permanent document context only when it is relevant.
- If permanent document context does not contain the answer,
  do not fabricate information.

SUMMARY / ANALYSIS RULE:
- If the user asks to summarize, explain, review, analyze,
  outline, describe, or give an overview of an attached document,
  use the attached document as the primary and only source.
- Understand natural variations such as:
  "summarise this document",
  "summarize my resume",
  "give me a summary",
  "what is this document about?",
  "explain this file",
  "tell me the main points",
  "what are the key takeaways?",
  "give me an overview",
  "what skills are mentioned?",
  "explain the second project".

IMPORTANT:
- Never mix temporary attachment context with permanent
  document context.
- Never claim that information exists in a document when
  it does not.
"""


# ============================================================
# HELPERS
# ============================================================

def _derive_title(question: str) -> str:
    raw = question.strip()

    first_line = next(
        (
            line.strip()
            for line in raw.splitlines()
            if line.strip()
        ),
        "",
    )

    first_line = re.sub(
        r"```[\s\S]*?```",
        "",
        first_line,
    )

    first_line = re.sub(
        r"[`*_>#~-]+",
        "",
        first_line,
    )

    return re.sub(
        r"\s+",
        " ",
        first_line,
    ).strip()[:60]


# ============================================================
# SAME-SESSION CONVERSATION CONTEXT
# ============================================================

# Only recent messages from the current session are used.
#
# 4 messages = approximately 2 user/assistant turns.
#
# This deliberately does NOT load the complete chat history.
SESSION_CONTEXT_MESSAGE_LIMIT = 4

# Prevent very large previous answers from consuming
# unnecessary LLM tokens.
SESSION_MESSAGE_CHAR_LIMIT = 1500


def _get_recent_session_messages(
    db: Session,
    session_id: Optional[int],
    user_id: Optional[int],
) -> list:
    """
    Get only the most recent messages from the CURRENT
    authenticated chat session.

    Important:
        - Messages are filtered by session_id.
        - Messages are filtered by user_id.
        - Complete chat history is NOT loaded.
    """

    if not session_id or not user_id:
        return []

    messages = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.session_id == session_id,
            ChatMessage.user_id == user_id,
        )
        .order_by(
            ChatMessage.created_at.desc()
        )
        .limit(
            SESSION_CONTEXT_MESSAGE_LIMIT
        )
        .all()
    )

    # Database returns newest first.
    # Reverse them so the LLM sees normal conversation order.
    messages.reverse()

    result = []

    for message in messages:

        content = (
            message.content
            or ""
        ).strip()

        if not content:
            continue

        # Prevent one enormous previous answer from
        # consuming the entire context window.
        content = content[
            :SESSION_MESSAGE_CHAR_LIMIT
        ]

        result.append(
            {
                "role": message.role,
                "content": content,
            }
        )

    return result


# ============================================================
# GUEST CONVERSATION CONTEXT
# ============================================================

def _parse_guest_history(
    guest_history: Optional[str],
) -> list:
    """
    Parse the frontend-supplied conversation history for
    guest users.

    IMPORTANT:
        - This is ONLY ever used when current_user is None.
        - Nothing here is persisted to the database.
        - The result is trimmed to the same limits used for
          authenticated session history, so guests cannot use
          this to inflate the LLM context window.
    """

    if not guest_history:
        return []

    try:
        parsed = json.loads(guest_history)

    except (json.JSONDecodeError, TypeError):

        logger.warning(
            "Failed to parse guest_history; ignoring."
        )

        return []

    if not isinstance(parsed, list):
        return []

    trimmed = []

    for item in parsed[-SESSION_CONTEXT_MESSAGE_LIMIT:]:

        if not isinstance(item, dict):
            continue

        role = item.get("role")

        content = (
            item.get("content")
            or ""
        ).strip()

        if role not in ("user", "assistant"):
            continue

        if not content:
            continue

        trimmed.append(
            {
                "role": role,
                "content": content[
                    :SESSION_MESSAGE_CHAR_LIMIT
                ],
            }
        )

    return trimmed


def _looks_like_follow_up(
    question: str,
    recent_messages: list,
) -> bool:
    """
    Lightweight heuristic to determine whether the current
    question probably depends on the previous conversation.

    We do NOT call the LLM for every question.

    This saves tokens and reduces Groq TPM usage.

    Examples that should be detected:

        "Why did they choose it?"
        "What is it used for?"
        "What about caching?"
        "And AWS?"
        "Why?"
        "How does that work?"
    """

    if not recent_messages:
        return False

    normalized = (
        question
        .strip()
        .lower()
    )

    # Very short conversational questions are often follow-ups.
    # Do not classify every short factual question as a follow-up.

    short_follow_up_patterns = [
        r"^why\??$",
        r"^how\??$",
        r"^what about\b.*",
        r"^how about\b.*",
        r"^and why\??$",
        r"^and how\??$",
        r"^and what about\b.*",
        r"^what does that\b.*",
        r"^what is that\b.*",
        r"^how does that\b.*",
    ]

    if any(
        re.search(
            pattern,
            normalized,
        )
        for pattern in short_follow_up_patterns
    ):
        return True
    

    follow_up_patterns = [
        r"\bit\b",
        r"\bits\b",
        r"\bthey\b",
        r"\bthem\b",
        r"\btheir\b",
        r"\bthis\b",
        r"\bthat\b",
        r"\bthese\b",
        r"\bthose\b",
        r"\bthe same\b",
        r"\bwhat about\b",
        r"\bhow about\b",
        r"\band what\b",
        r"\band why\b",
        r"\band how\b",
        r"\bwhy did they\b",
        r"\bwhy does it\b",
        r"\bwhy do they\b",
        r"\bhow does it\b",
        r"\bhow do they\b",
        r"\bwhat does it\b",
        r"\bwhat is it\b",
        r"\bwhich one\b",
        r"\bwhich of these\b",
        r"\bthe previous\b",
        r"\babove\b",
        r"\bmentioned earlier\b",
    ]

    return any(
        re.search(
            pattern,
            normalized,
        )
        for pattern in follow_up_patterns
    )


def _format_recent_conversation(
    recent_messages: list,
) -> str:
    """
    Convert recent session messages into a compact text
    representation for the LLM.
    """

    if not recent_messages:
        return ""

    lines = []

    for message in recent_messages:

        role = message["role"]

        if role == "user":
            label = "User"
        else:
            label = "Assistant"

        lines.append(
            f"{label}: {message['content']}"
        )

    return "\n\n".join(lines)


def _rewrite_follow_up_question(
    question: str,
    recent_messages: list,
) -> str:
    """
    Convert a contextual follow-up question into a standalone
    question suitable for semantic retrieval.

    Example:

        Previous:
        User: What database does Nexora use?
        Assistant: Nexora uses PostgreSQL.

        Current:
        Why did they choose it?

        Rewritten:
        Why did Nexora choose PostgreSQL as its database?
    """

    conversation = _format_recent_conversation(
        recent_messages
    )

    if not conversation:
        return question

    rewrite_messages = [
        {
            "role": "system",
            "content": (
                "You rewrite follow-up questions into "
                "standalone search queries for a document "
                "retrieval system.\n\n"

                "Rules:\n"
                "1. Resolve pronouns such as it, they, "
                "them, this and that using the conversation.\n"
                "2. Preserve the user's exact intent.\n"
                "3. Add missing names, products, technologies "
                "or entities from the recent conversation "
                "when necessary.\n"
                "4. Do not answer the question.\n"
                "5. Do not add new information.\n"
                "6. Return ONLY the rewritten question.\n"
                "7. Keep it concise."
            ),
        },
        {
            "role": "user",
            "content": (
                "RECENT CONVERSATION\n"
                "===================\n"
                f"{conversation}\n\n"

                "CURRENT QUESTION\n"
                "================\n"
                f"{question}\n\n"

                "Rewrite the current question as a "
                "standalone retrieval question."
            ),
        },
    ]

    rewritten = chat_completion(
        rewrite_messages,
        max_tokens=100,
        temperature=0.0,
    )

    if not rewritten:
        logger.warning(
            "Follow-up question rewriting failed. "
            "Using original question."
        )

        return question

    # Remove accidental quotation marks.
    rewritten = rewritten.strip(
        "`\"'"
    )

    if not rewritten:
        return question

    logger.info(
        "FOLLOW-UP QUESTION DETECTED"
    )

    logger.info(
        "Original question: %s",
        question,
    )

    logger.info(
        "Rewritten retrieval question: %s",
        rewritten,
    )

    return rewritten


# ============================================================
# PERMANENT DOCUMENT RETRIEVAL
# ============================================================

def _retrieve_permanent_context(
    user_id: int,
    question: str,
) -> str:
    """
    Search the user's permanent document chunks
    using Supabase PostgreSQL + pgvector.
    """

    try:

        query_embedding = embedding_service.embed_query(
            question
        )

        query_embedding = np.asarray(
            query_embedding,
            dtype="float32",
        )

        results = search_document_chunks(
            user_id=user_id,
            query_embedding=query_embedding,
            top_k=settings.RETRIEVAL_TOP_K,
            min_similarity=(
                settings.RETRIEVAL_CHUNK_SCORE_THRESHOLD
            ),
        )

        if not results:

            logger.info(
                "RAG: No relevant permanent chunks found."
            )

            return ""

        logger.info(
            "RAG: %d permanent chunks retrieved.",
            len(results),
        )

        selected = []

        for rank, result in enumerate(
            results,
            start=1,
        ):

            similarity = float(
                result.get(
                    "similarity",
                    0.0,
                )
            )

            logger.info(
                "Rank %d | document_id=%s | "
                "similarity=%.4f",
                rank,
                result.get("document_id"),
                similarity,
            )

            selected.append(
                result["text"]
            )

        context = "\n\n".join(
            selected
        )

        context = context[
            :settings.CHAT_CONTEXT_CHAR_BUDGET
        ]

        logger.info(
            "RAG RESULT: %d characters",
            len(context),
        )

        return context

    except Exception:

        logger.exception(
            "Permanent document retrieval failed."
        )

        return ""


#============================================================
# TEMPORARY DOCUMENT CONTEXT
# ============================================================

def _build_temporary_context(
    extracted_text: str,
    question: str,
) -> str:
    """
    Build context ONLY from the currently attached file.

    Important:
        - Nothing is written to permanent storage.
        - Nothing is added to the user's permanent FAISS index.
        - No permanent document retrieval occurs.

    For small documents such as resumes, the complete document
    is returned. This is much better for summary requests.

    For larger documents, semantic retrieval is performed
    against an in-memory FAISS index.
    """

    cleaned = clean_text(
        extracted_text
    )

    if not cleaned:
        return ""

    chunks = chunk_text(
        cleaned,
        chunk_size=settings.CHUNK_SIZE_TOKENS,
        overlap=settings.CHUNK_OVERLAP_TOKENS,
    )

    if not chunks:
        return ""

    # --------------------------------------------------------
    # Broad document requests
    # --------------------------------------------------------

    broad_request = bool(
        re.search(
            r"""
            \b(
                summar(y|ize|ise)|
                summary|
                overview|
                key\s+points?|
                main\s+(points?|ideas?)|
                takeaways?|
                important\s+points?|
                what\s+is\s+this|
                what\s+does\s+this|
                explain\s+this|
                explain\s+the\s+(document|file|resume)|
                describe\s+this|
                analyze\s+this|
                analyse\s+this|
                review\s+this|
                give\s+me\s+an?\s+overview
            )\b
            """,
            question.lower(),
            re.VERBOSE,
        )
    )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # For a small document, always send the entire document.
    #
    # This makes:
    #
    # "Summarise my resume"
    #
    # work reliably.
    # --------------------------------------------------------

    direct_document_limit = max(
        settings.CHAT_CONTEXT_CHAR_BUDGET,
        12000,
    )

    if len(cleaned) <= direct_document_limit:
        return cleaned

    # For broad requests on large documents, use as much
    # document text as the configured context budget allows.
    if broad_request:
        return cleaned[:direct_document_limit]

    # --------------------------------------------------------
    # Large document + specific question
    #
    # Build an IN-MEMORY FAISS index.
    # --------------------------------------------------------

    try:
        embeddings = embedding_service.embed_texts(
            chunks
        )

        embeddings = np.asarray(
            embeddings,
            dtype="float32",
        )

        if embeddings.ndim != 2:
            return ""

        faiss.normalize_L2(
            embeddings
        )

        temporary_index = faiss.IndexFlatIP(
            embeddings.shape[1]
        )

        temporary_index.add(
            embeddings
        )

        query_embedding = embedding_service.embed_query(
            question
        )

        query_embedding = np.asarray(
            query_embedding,
            dtype="float32",
        )

        faiss.normalize_L2(
            query_embedding
        )

        top_k = min(
            settings.RETRIEVAL_TOP_K,
            len(chunks),
        )

        scores, indices = temporary_index.search(
            query_embedding,
            top_k,
        )

    except Exception:
        logger.exception(
            "Temporary document retrieval failed."
        )
        return ""

    selected = []

    for score, idx in zip(
        scores[0],
        indices[0],
    ):
        if (
            idx >= 0
            and idx < len(chunks)
            and float(score)
            >= settings.RETRIEVAL_CHUNK_SCORE_THRESHOLD
        ):
            selected.append(
                chunks[idx]
            )

    if not selected:
        return ""

    return "\n\n".join(
        selected
    )[
        : settings.CHAT_CONTEXT_CHAR_BUDGET
    ]


# ============================================================
# TEMPORARY FILE EXTRACTION
# ============================================================

async def _extract_temporary_file(
    uploaded_file: UploadFile,
) -> str:
    """
    Extract text from a temporary upload.

    The file is:
        browser
            ↓
        FastAPI UploadFile
            ↓
        temporary OS file
            ↓
        extraction
            ↓
        temporary OS file deleted

    It is NEVER stored in the permanent document system.
    """

    filename = uploaded_file.filename or ""

    extension = Path(
        filename
    ).suffix.lower()

    allowed_extensions = {
        ".pdf",
        ".docx",
        ".txt",
    }

    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=(
                "Only PDF, DOCX and TXT files "
                "are supported."
            ),
        )

    contents = await uploaded_file.read()

    max_bytes = (
        settings.MAX_UPLOAD_MB
        * 1024
        * 1024
    )

    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File is too large. Maximum size "
                f"is {settings.MAX_UPLOAD_MB} MB."
            ),
        )

    if not contents:
        raise HTTPException(
            status_code=400,
            detail="The attached file is empty.",
        )

    temporary_path: Optional[Path] = None

    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=extension,
        ) as temp_file:

            temp_file.write(contents)

            temporary_path = Path(
                temp_file.name
            )

        logger.info(
            "Extracting temporary file: %s",
            filename,
        )

        # IMPORTANT:
        #
        # Pass the Path object itself.
        # Some extraction implementations expect
        # a Path rather than a string.
        extracted_text = extract_text_from_file(
            temporary_path
        )

        if extracted_text is None:
            extracted_text = ""

        return extracted_text

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception(
            "Failed to extract temporary file %s",
            filename,
        )

        raise HTTPException(
            status_code=400,
            detail=(
                "Could not read the attached "
                "document. Please make sure the "
                "PDF, DOCX or TXT file contains "
                "readable text."
            ),
        ) from exc

    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(
                    missing_ok=True
                )

                logger.info(
                    "Deleted temporary file: %s",
                    temporary_path,
                )

            except Exception:
                logger.warning(
                    "Could not delete temporary file: %s",
                    temporary_path,
                )

        try:
            await uploaded_file.close()
        except Exception:
            pass


# ============================================================
# CHAT ENDPOINT
# ============================================================
@router.post("")
async def send_message(
    question: str = Form(...),

    session_id: Optional[int] = Form(
        None
    ),

    file: Optional[UploadFile] = File(
        None
    ),

    guest_history: Optional[str] = Form(
        None
    ),

    max_tokens: int = Form(700),

    current_user: Optional[User] = Depends(
        get_current_user_optional
    ),

    db: Session = Depends(get_db),
):

    question = question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty.",
        )

    max_tokens = min(
        max_tokens or 700,
        settings.LLM_MAX_TOKENS_CAP,
    )

    persisted_session_id = None
    persisted_user_id = None

    # ========================================================
    # SAME-SESSION CONTEXT
    # ========================================================

    recent_messages = []

    # This is the question that will actually be sent to
    # the FAISS retrieval system.
    #
    # Normally it is identical to `question`.
    #
    # For follow-up questions it becomes a standalone question.
    retrieval_question = question


    # ========================================================
    # GUEST CONVERSATION CONTEXT
    #
    # Guests have no persisted ChatMessage rows, so the
    # frontend sends its own in-memory recent messages.
    #
    # This is ONLY ever used when there is no authenticated
    # user. An authenticated request's history always comes
    # from the database below, never from this field.
    # ========================================================

    if not current_user:

        recent_messages = _parse_guest_history(
            guest_history
        )

        if recent_messages:
            logger.info(
                "Guest: using %d client-supplied recent "
                "messages for conversation context.",
                len(recent_messages),
            )


    # ========================================================
    # FOLLOW-UP QUESTION REWRITING
    #
    # Applies to both authenticated users and guests, using
    # whichever recent_messages was populated above.
    # ========================================================

    if _looks_like_follow_up(
        question,
        recent_messages,
    ):

        retrieval_question = (
            _rewrite_follow_up_question(
                question,
                recent_messages,
            )
        )

    else:

        retrieval_question = question


    # ========================================================
    # AUTHENTICATED CHAT SESSION
    # ========================================================


    if current_user:

        persisted_user_id = current_user.id

        session = None

        # ====================================================
        # FIND EXISTING SESSION
        # ====================================================

        if session_id is not None:

            session = (
                db.query(ChatSession)
                .filter(
                    ChatSession.id == session_id,
                    ChatSession.user_id == current_user.id,
                )
                .first()
            )

        # ====================================================
        # CREATE NEW SESSION
        # ====================================================

        if not session:

            session = ChatSession(
                user_id=current_user.id,
                title="",
            )

            db.add(session)
            db.commit()
            db.refresh(session)

        persisted_session_id = session.id

        # ====================================================
        # LOAD ONLY RECENT MESSAGES
        # ====================================================

        recent_messages = (
            _get_recent_session_messages(
                db=db,
                session_id=persisted_session_id,
                user_id=persisted_user_id,
            )
        )

        logger.info(
            "Session %s: loaded %d recent messages "
            "for conversation context.",
            persisted_session_id,
            len(recent_messages),
        )

        # ====================================================
        # FOLLOW-UP QUESTION REWRITING
        #
        # Re-evaluated here using the authoritative DB-sourced
        # history, overriding whatever the pre-auth block above
        # computed (which only applies to guests).
        # ====================================================

        if _looks_like_follow_up(
            question,
            recent_messages,
        ):

            retrieval_question = (
                _rewrite_follow_up_question(
                    question,
                    recent_messages,
                )
            )

        else:

            retrieval_question = question

        # ====================================================
        # SAVE ORIGINAL USER QUESTION
        # ====================================================

        # IMPORTANT:
        #
        # We store the ORIGINAL question.
        #
        # We do NOT store the rewritten retrieval query.
        #
        # Therefore the UI/history remains natural:
        #
        # User: Why did they choose it?
        #
        # instead of:
        #
        # User: Why did Nexora choose PostgreSQL?
        #

        db.add(
            ChatMessage(
                session_id=persisted_session_id,
                user_id=persisted_user_id,
                role="user",
                content=question,
            )
        )

        db.commit()

        # ====================================================
        # SESSION TITLE
        # ====================================================

        if not (
            session.title
            and session.title.strip()
        ):

            title = _derive_title(
                question
            )

            if title:

                session.title = title

                db.commit()


    # ========================================================
    # DOCUMENT CONTEXT
    # ========================================================

    context_text = ""

    # ========================================================
    # TEMPORARY ATTACHMENT MODE
    #
    # Available to BOTH authenticated users and guests.
    #
    # Nothing is persisted:
    #   - no Document record
    #   - no Supabase Storage upload
    #   - no permanent chunks or embeddings
    #
    # The file is extracted from a temporary OS file which is
    # deleted immediately after extraction.
    # ========================================================

    if file is not None:

        logger.info(
            "Temporary document attached: %s",
            file.filename,
        )

        extracted_text = await _extract_temporary_file(
            file
        )


        cleaned_text = clean_text(
            extracted_text
        )

        if not cleaned_text:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Could not extract readable "
                    "text from the attached document. "
                    "If this is a scanned PDF, OCR may "
                    "be required."
                ),
            )

        logger.info(
            "Temporary document extracted successfully: "
            "%s characters",
            len(cleaned_text),
        )

        # ----------------------------------------------------
        # IMPORTANT
        # ----------------------------------------------------
        # Only the currently attached document is searched.
        #
        # Permanent documents are NEVER searched here.
        #
        # If no relevant context is found, _build_temporary_context()
        # returns an empty string.
        #
        # We DO NOT raise an error in that case.
        #
        # The LLM will then answer using general knowledge.
        # ----------------------------------------------------

        context_text = _build_temporary_context(
            cleaned_text,
            retrieval_question,
        )

        if context_text.strip():
            logger.info(
                "Temporary document context selected: %d characters",
                len(context_text),
            )
        else:
            logger.info(
                "No sufficiently relevant temporary-document "
                "context found. LLM will use general knowledge."
            )

    # ========================================================
    # PERMANENT DOCUMENT MODE
    # ========================================================

    elif current_user:

        # Reached only when there is NO temporary attachment.

        context_text = _retrieve_permanent_context(
            current_user.id,
            retrieval_question,
        )

        if context_text.strip():
            logger.info(
                "Permanent document context selected: %d characters",
                len(context_text),
            )
        else:
            logger.info(
                "No sufficiently relevant permanent-document "
                "context found. LLM will use general knowledge."
            )

    # ========================================================
    # BUILD LLM MESSAGES
    # ========================================================

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]



    # ========================================================
    # SAME-SESSION CONVERSATION CONTEXT
    # ========================================================

    if recent_messages:

        messages.append(
            {
                "role": "system",
                "content": (
                    "RECENT CONVERSATION FROM THE CURRENT "
                    "CHAT SESSION\n"
                    "========================================\n"
                    f"{_format_recent_conversation(recent_messages)}\n\n"

                    "CONVERSATION RULES\n"
                    "==================\n"
                    "- This conversation belongs only to the "
                    "current chat session.\n"
                    "- Use it to understand follow-up questions "
                    "and references such as 'it', 'they', "
                    "'that', 'this' or 'the previous one'.\n"
                    "- Prefer the current user's question when "
                    "there is any conflict.\n"
                    "- Do not treat previous assistant statements "
                    "as authoritative document facts unless the "
                    "same information is supported by the "
                    "currently supplied document context.\n"
                    "- Do not mention this internal conversation "
                    "context to the user."
                ),
            }
        )





    # ========================================================
    # TEMPORARY DOCUMENT
    # ========================================================

    if file is not None:

        document_name = (
            file.filename
            or "temporary attached document"
        )

        # ----------------------------------------------------
        # CASE 1:
        # Relevant context was retrieved
        # ----------------------------------------------------

        if context_text.strip():

            messages.append(
                {
                    "role": "user",
                    "content": (
                        "ATTACHED DOCUMENT\n"
                        "=================\n"
                        f"Filename: {document_name}\n\n"

                        "RETRIEVED DOCUMENT CONTEXT\n"
                        "===========================\n"
                        f"{context_text}\n\n"

                        "USER QUESTION\n"
                        "=============\n"
                        f"{question}\n\n"

                        "IMPORTANT INSTRUCTIONS\n"
                        "======================\n"

                        "The retrieved context comes from "
                        "the currently attached document.\n\n"

                        "It is candidate context retrieved "
                        "using semantic search. Do NOT assume "
                        "it is relevant merely because it was "
                        "retrieved.\n\n"

                        "First determine whether the retrieved "
                        "context is actually relevant to the "
                        "user's question.\n\n"

                        "IF THE CONTEXT IS RELEVANT:\n"
                        "- Use the document information to "
                        "answer the question.\n"
                        "- Prefer information explicitly "
                        "present in the document.\n"
                        "- Do not invent document facts.\n\n"

                        "IF THE CONTEXT IS NOT RELEVANT:\n"
                        "- Completely ignore the retrieved "
                        "document context.\n"
                        "- Answer the question using your "
                        "general knowledge.\n"
                        "- Do not force document information "
                        "into the answer.\n"
                        "- Do not mention that irrelevant "
                        "document context was retrieved.\n\n"

                        "DOCUMENT ISOLATION:\n"
                        "- Use only the currently attached "
                        "document as document context.\n"
                        "- Never use the user's permanent "
                        "document library.\n"
                        "- Never use information from previous "
                        "uploaded documents."
                    ),
                }
            )

        # ----------------------------------------------------
        # CASE 2:
        # No relevant document context
        # ----------------------------------------------------

        else:

            messages.append(
                {
                    "role": "user",
                    "content": (
                        "ATTACHED DOCUMENT\n"
                        "=================\n"
                        f"Filename: {document_name}\n\n"

                        "No sufficiently relevant information "
                        "from the attached document was found "
                        "for this question.\n\n"

                        "USER QUESTION\n"
                        "=============\n"
                        f"{question}\n\n"

                        "INSTRUCTION\n"
                        "===========\n"
                        "Answer the user's question using "
                        "your general knowledge.\n\n"

                        "Do NOT use the user's permanent "
                        "document library.\n"
                        "Do NOT use information from previous "
                        "documents.\n"
                        "Do NOT pretend that the answer came "
                        "from the attached document."
                    ),
                }
            )

    # ========================================================
    # PERMANENT DOCUMENT
    # ========================================================

    elif context_text.strip():

        messages.append(
            {
                "role": "user",
                "content": (
                    "RETRIEVED DOCUMENT CANDIDATES\n"
                    "=============================\n\n"
                    f"{context_text}\n\n"

                    "USER QUESTION\n"
                    "=============\n"
                    f"{question}\n\n"

                    "IMPORTANT INSTRUCTIONS\n"
                    "======================\n"

                    "The above text was retrieved from "
                    "the user's permanent document library "
                    "using semantic search.\n\n"

                    "The retrieved context is NOT guaranteed "
                    "to be relevant.\n\n"

                    "First determine whether the retrieved "
                    "context actually relates to the user's "
                    "question.\n\n"

                    "IF THE CONTEXT IS RELEVANT:\n"
                    "- Use the document information to "
                    "answer the question.\n"
                    "- Prefer explicit information from "
                    "the document.\n"
                    "- Do not invent facts.\n\n"

                    "IF THE CONTEXT IS NOT RELEVANT:\n"
                    "- Completely ignore the retrieved "
                    "context.\n"
                    "- Answer using your general knowledge.\n"
                    "- Do not force the document into "
                    "the answer.\n"
                    "- Do not mention the irrelevant "
                    "retrieved context.\n"
                ),
            }
        )

    # ========================================================
    # GENERAL LLM
    # ========================================================

    else:

        messages.append(
            {
                "role": "user",
                "content": (
                    "USER QUESTION\n"
                    "=============\n"
                    f"{question}\n\n"

                    "Answer the question using your "
                    "general knowledge."
                ),
            }
        )

    # ========================================================
    # STREAM RESPONSE
    # ========================================================

    def event_stream():
        assistant_text = ""

        try:
            for token in stream_chat_completion(
                messages,
                max_tokens=max_tokens,
            ):
                assistant_text += token

                yield (
                    json.dumps(
                        {
                            "content": token
                        }
                    )
                    + "\n"
                )

        finally:

            if (
                persisted_session_id
                and persisted_user_id
                and assistant_text
            ):
                db2 = SessionLocal()

                try:
                    db2.add(
                        ChatMessage(
                            session_id=persisted_session_id,
                            user_id=persisted_user_id,
                            role="assistant",
                            content=assistant_text,
                        )
                    )

                    db2.commit()

                finally:
                    db2.close()

    headers = {}

    if persisted_session_id:
        headers["X-Session-Id"] = str(
            persisted_session_id
        )

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers=headers,
    )
# ============================================================
# SESSION ENDPOINTS
# ============================================================

@router.get(
    "/sessions",
    response_model=list[ChatSessionResponse],
)
def list_sessions(
    current_user: Optional[User] = Depends(
        get_current_user_optional
    ),
    db: Session = Depends(get_db),
):
    if not current_user:
        return []

    return (
        db.query(ChatSession)
        .filter(
            ChatSession.user_id
            == current_user.id
        )
        .order_by(
            ChatSession.created_at.desc()
        )
        .all()
    )


@router.patch(
    "/sessions/{session_id}",
    response_model=ChatSessionResponse,
)
def rename_session(
    session_id: int,
    data: ChatSessionRenameRequest,
    current_user: Optional[User] = Depends(
        get_current_user_optional
    ),
    db: Session = Depends(get_db),
):
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
        )

    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.user_id
            == current_user.id,
        )
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Chat session not found",
        )

    session.title = data.title.strip()

    db.commit()
    db.refresh(session)

    return session


@router.delete(
    "/sessions/{session_id}"
)
def delete_session(
    session_id: int,
    current_user: Optional[User] = Depends(
        get_current_user_optional
    ),
    db: Session = Depends(get_db),
):
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
        )

    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.user_id
            == current_user.id,
        )
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Chat session not found",
        )

    db.delete(session)
    db.commit()

    return {
        "message": "Chat deleted"
    }


@router.get(
    "/history/{session_id}"
)
def get_history(
    session_id: int,
    limit: int =
        settings.CHAT_HISTORY_DEFAULT_LIMIT,
    current_user: Optional[User] = Depends(
        get_current_user_optional
    ),
    db: Session = Depends(get_db),
):
    if not current_user:
        return []

    messages = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.session_id
            == session_id,
            ChatMessage.user_id
            == current_user.id,
        )
        .order_by(
            ChatMessage.created_at
        )
        .limit(limit)
        .all()
    )

    return [
        {
            "role": message.role,
            "content": message.content,
            "created_at": message.created_at,
        }
        for message in messages
    ]