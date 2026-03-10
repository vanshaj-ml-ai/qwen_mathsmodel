from rag.geometry import enrich_context_with_geometry, detect_geometry_requirement
from rag.answer import build_final_answer
from rag.llm_client import generate_step_by_step_fallback
from rag.vlm_client import extract_question_and_diagram_fallback
from rag.ocr import ocr_image
from rag.context import build_book_context
from rag.reranker import rerank
from rag.retriever import Retriever
from rag.embedder import embed_texts
from rag.db import connect, fetch_chunk
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, UploadFile, File, Form, Request
import os
import re
import tempfile
import base64
import logging
from uuid import uuid4

# ═══════════════════════════════════════════════════════════════════
# PRODUCTION GEOMETRY SOLVER
# ═══════════════════════════════════════════════════════════════════
try:
    from rag.geometry_solver import (
        route_question,
        extract_geometry_json,
        solve_geometry_problem,
        generate_explanation,
        generate_diagram_from_geometry,
        solve_geometry_question,
        QuestionType
    )
    GEOMETRY_SOLVER_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("✅ Production Geometry Solver loaded successfully")
except ImportError as e:
    GEOMETRY_SOLVER_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(f"⚠️ Production Geometry Solver not available: {e}")

# Keep legacy geometry solver for enrichment
try:
    from rag.geometry import EnhancedGeometrySolver
    LEGACY_GEOMETRY_AVAILABLE = True
except ImportError:
    LEGACY_GEOMETRY_AVAILABLE = False
    logger.warning("⚠️ Legacy Geometry Enrichment not available")

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"


# Setup logger
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="RD Sharma Tutor (RAG internal, tutor output only)")

app.mount("/static", StaticFiles(directory="/home/ec2-user/sarthak/rdsharma-rag/static"), name="static")

templates = Jinja2Templates(
    directory="/home/ec2-user/sarthak/rdsharma-rag/templates")


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ret = None


@app.on_event("startup")
def startup():
    global ret
    try:
        ret = Retriever()
        logger.info("Retriever initialized successfully")
    except Exception as e:
        logger.warning(
            f"Failed to initialize Retriever: {e}. Proceeding without RAG index. Run build scripts first.")
        ret = None


@app.get("/health")
def health():
    status = "ok" if ret else "indexing"
    features = {
        "rag": ret is not None,
        "geometry_solver": GEOMETRY_SOLVER_AVAILABLE
    }
    return {"status": status, "features": features}


# ═══════════════════════════════════════════════════════════════════
# NEW: Geometry Helper Functions
# ═══════════════════════════════════════════════════════════════════

def extract_labeled_points(text: str) -> list:
    """
    Extract coordinate points from text like A(1,2), B(3,4) or A = (1,2).
    Returns [(label, x, y), ...]
    """
    # Pattern: Label + optional = + (x, y)
    pattern = r'([A-Z])\s*[=\(]?\s*\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)'
    matches = re.findall(pattern, text.upper())

    if matches:
        return [(lbl, float(x), float(y)) for lbl, x, y in matches]

    # Fallback: unlabeled pairs
    pairs = re.findall(r'\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)', text)
    labels = "ABCDEFGHIJKLMNOP"
    return [(labels[i], float(x), float(y)) for i, (x, y) in enumerate(pairs[:8])]


def enrich_answer_with_geometry(answer: str, question: str) -> str:
    """
    Auto-detect geometry in question and enrich answer with computed properties.

    Args:
        answer: The generated answer text
        question: Original user question

    Returns:
        Enhanced answer with geometry analysis appended
    """
    if not GEOMETRY_SOLVER_AVAILABLE:
        return answer

    try:
        # Extract vertices from question
        vertices = extract_labeled_points(question)

        if not vertices or len(vertices) < 2:
            return answer  # No geometry detected

        solver = EnhancedGeometrySolver()
        enrichment = "\n\n---\n### 📐 Geometric Analysis\n\n"
        added_analysis = False

        # Triangle analysis
        if len(vertices) == 3:
            geo = solver.solve_triangle(vertices)
            enrichment += "**Triangle Properties:**\n"
            enrichment += f"- Area: {geo['area']:.2f} square units"
            if geo.get('area_exact') and str(geo['area_exact']) != str(geo['area']):
                enrichment += f" (exact: {geo['area_exact']})"
            enrichment += "\n"
            enrichment += f"- Perimeter: {geo['perimeter']:.2f} units\n"

            # Classification
            triangle_type = (
                "Right Triangle" if geo['is_right'] else
                "Equilateral Triangle" if geo['is_equilateral'] else
                "Isosceles Triangle" if geo['is_isosceles'] else
                "Scalene Triangle"
            )
            enrichment += f"- Classification: {triangle_type}\n"
            enrichment += f"- Centroid: ({geo['centroid'][0]:.2f}, {geo['centroid'][1]:.2f})\n"
            enrichment += f"- Angles: {', '.join([f'{a:.1f}°' for a in geo['angles_deg']])}\n"

            # Pythagorean check for right triangles
            if geo.get("pythagorean_check"):
                enrichment += f"- Pythagorean Verification: {geo['pythagorean_check']}\n"

            # Formulas used
            if geo.get('formulas_used'):
                enrichment += f"\n**Formulas Applied:**\n"
                for formula in geo['formulas_used']:
                    enrichment += f"- {formula}\n"

            added_analysis = True

        # Distance between two points
        elif len(vertices) == 2:
            p1 = (vertices[0][1], vertices[0][2])
            p2 = (vertices[1][1], vertices[1][2])

            dist_data = solver.calculate_distance(p1, p2)
            mid_data = solver.calculate_midpoint(p1, p2)

            enrichment += "**Line Segment Analysis:**\n"
            enrichment += f"- Distance: {dist_data['distance']:.2f} units"
            if dist_data.get('distance_exact') and str(dist_data['distance_exact']) != str(dist_data['distance']):
                enrichment += f" (exact: {dist_data['distance_exact']})"
            enrichment += "\n"
            enrichment += f"- Midpoint: ({mid_data['midpoint'][0]:.2f}, {mid_data['midpoint'][1]:.2f})\n"
            enrichment += f"- Formula: {dist_data['formula']}\n"

            added_analysis = True

        # Circle analysis (check if question mentions circle/radius)
        q_lower = question.lower()
        if any(word in q_lower for word in ["circle", "radius", "circumference", "diameter"]):
            r_match = re.search(r'radius\s*[=:of]*\s*(\d+(?:\.\d+)?)', q_lower)
            if r_match:
                radius = float(r_match.group(1))
                circle_data = solver.solve_circle(center=(0, 0), radius=radius)

                enrichment += "\n**Circle Properties:**\n"
                enrichment += f"- Radius: {circle_data['radius']}\n"
                enrichment += f"- Diameter: {circle_data['diameter']:.2f}\n"
                enrichment += f"- Circumference: {circle_data['circumference']:.2f}"
                if circle_data.get('circumference_exact'):
                    enrichment += f" (exact: {circle_data['circumference_exact']})"
                enrichment += "\n"
                enrichment += f"- Area: {circle_data['area']:.2f}"
                if circle_data.get('area_exact'):
                    enrichment += f" (exact: {circle_data['area_exact']})"
                enrichment += "\n"

                added_analysis = True

        # Only append if we added analysis
        if added_analysis:
            logger.info(
                "[GeometrySolver] ✅ Enhanced answer with geometry analysis")
            return answer + enrichment
        else:
            return answer

    except Exception as e:
        logger.warning(f"[GeometrySolver] Error enriching answer: {e}")
        return answer


# ═══════════════════════════════════════════════════════════════════
# PRODUCTION GEOMETRY PIPELINE
# ═══════════════════════════════════════════════════════════════════

def process_question_with_geometry_pipeline(
    question: str,
    session_id: str = None,
    generate_diagram_flag: bool = True
) -> dict:
    """
    Route question through production geometry solver if applicable.

    Returns:
        {
            "use_geometry_pipeline": bool,
            "result": {...} or None
        }

    If geometry pipeline is used, returns complete solution with answer + diagram.
    If not geometry, returns None to fall through to RAG/LLM pipeline.
    """
    if not GEOMETRY_SOLVER_AVAILABLE:
        return {"use_geometry_pipeline": False, "result": None}

    try:
        # Step 1: Route question
        question_type = route_question(question)

        if question_type != QuestionType.GEOMETRY:
            logger.info(
                f"[Pipeline] Question routed to {question_type}, using standard RAG/LLM")
            return {"use_geometry_pipeline": False, "result": None}

        logger.info(f"[Pipeline] Question routed to GEOMETRY pipeline")

        # Step 2-5: Run complete geometry pipeline
        pipeline_result = solve_geometry_question(
            question=question,
            generate_diagram=generate_diagram_flag
        )

        if not pipeline_result.get("success"):
            logger.warning(
                f"[Pipeline] Geometry pipeline failed: {pipeline_result.get('error')}")
            return {"use_geometry_pipeline": False, "result": None}

        # Format result for API response
        explanation = pipeline_result.get("explanation", "")
        diagram_path = pipeline_result.get("diagram_path")
        solution = pipeline_result.get("solution", {})

        # Build answer text with diagram reference
        answer_text = explanation

        if diagram_path:
            diagram_url = f"/static/diagrams/{os.path.basename(diagram_path)}"
            answer_text += f"\n\n[Diagram available at: {diagram_url}]"

        # Return formatted result
        return {
            "use_geometry_pipeline": True,
            "result": {
                "answer": answer_text,
                "diagram_path": diagram_path,
                "solution_data": solution,
                "parsed_geometry": pipeline_result.get("parsed_geometry"),
                "verified": pipeline_result.get("verified", False),
                "pipeline": "geometry_solver",
                "errors": pipeline_result.get("errors", [])
            }
        }

    except Exception as e:
        logger.error(f"[Pipeline] Unexpected error in geometry routing: {e}")
        return {"use_geometry_pipeline": False, "result": None}


# -------------------------------------------------
# HYBRID RAG + LLM LOGIC
# -------------------------------------------------
def retrieve_rd_sharma_context(question: str, top_k: int = 5) -> tuple[str, bool]:
    """
    Hybrid retrieval: Check if question is RAG-relevant.
    Uses the main retrieve_book_context function instead.

    Returns:
        (context: str, is_rag_relevant: bool)
        - If RAG relevant: returns formatted context + True
        - If not RAG relevant: returns "" + False
    """
    # Use the main function which has proper threshold checks
    context = retrieve_book_context(question)
    is_relevant = bool(context and context.strip())
    return context, is_relevant


# -------------------------------------------------
# Session Management (In-memory storage)
# -------------------------------------------------
sessions = {}


def load_session(session_id: str) -> list:
    """Load session history for a given session_id."""
    return sessions.get(session_id, [])


def update_session(session_id: str, question: str, answer: str):
    """Update session with new Q&A pair."""
    if session_id not in sessions:
        sessions[session_id] = []
    sessions[session_id].append({"question": question, "answer": answer})


def get_session_history(session_id: str) -> dict:
    """
    Return structured chat history for a session.

    This is useful for the frontend to render the complete
    conversation so far for a given user/session.
    """
    history = load_session(session_id)
    return {
        "session_id": session_id,
        "history": history,
    }


def build_chat_context(session: list) -> str:
    """Build context from session history"""
    if not session:
        return ""
    context = "\n\n".join([
        # Truncate for context
        f"Q: {item['question']}\nA: {item['answer'][:500]}"
        for item in session[-3:]  # Keep last 3 exchanges
    ])
    return context


def validate_context_relevance(question: str, context: str) -> bool:
    """
    Validate if retrieved context is relevant to the question.
    Returns True if context appears relevant, False otherwise.
    """
    if not context or not question:
        return False

    question_lower = question.lower()
    context_lower = context.lower()

    # Extract main keywords from question (longer words)
    kws = extract_keywords(question)
    if not kws:
        return False

    # Check if context has significant keyword overlap
    matching_keywords = sum(1 for k in kws if k in context_lower)
    coverage = matching_keywords / len(kws) if kws else 0

    # Require at least 40% keyword coverage for relevance
    is_relevant = coverage >= 0.4 and len(context) > 200

    logger.debug(
        f"[RAG Validation] Coverage: {coverage:.1%}, Relevant: {is_relevant}")
    return is_relevant


# -------------------------------------------------
# RD Sharma RAG retrieval helpers
# -------------------------------------------------

STOPWORDS = {
    "find", "the", "of", "a", "an", "and", "or", "to", "in", "on", "for",
    "with", "by", "is", "which", "that", "this", "these", "those", "from",
    "into", "at", "as", "it", "be", "are", "joining", "segment", "line",
    "point", "ratio", "internally", "externally", "divides", "divide",
    "dividing", "coordinates", "coordinate", "join", "joins", "between"
}


def normalize_minus(s: str) -> str:
    return (s or "").replace("−", "-").replace("–", "-").replace("—", "-")


def extract_numbers_signed(s: str):
    s = normalize_minus(s)
    return re.findall(r"(?<!\w)-?\d+", s)


def extract_keywords(s: str):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9\s:-]", " ", s)
    words = [w for w in s.split() if len(w) >= 4 and w not in STOPWORDS]
    seen = set()
    out = []
    for w in words:
        if w not in seen:
            seen.add(w)
            out.append(w)
    return out


def is_junk_chunk(title: str, page_end: int, query: str) -> bool:
    """
    Heuristic filter to avoid front-matter / contents pages unless explicitly asked.
    """
    q = (query or "").lower()
    t = (title or "").lower()

    # Filter early pages that look like contents unless the query asks for them
    if page_end <= 25:
        if (
            ("content" in t or t == "content")
            and not any(x in q for x in ("content", "preface", "isbn", "edition"))
        ):
            return True
        if any(x in q for x in ("isbn", "edition", "publisher")):
            return False
        if page_end <= 10:
            return True

    return False


def sql_numeric_candidates(con, query: str, limit: int = 30):
    """
    Fast numeric + keyword filter in SQLite to narrow down RD Sharma chunks.
    """
    nums = extract_numbers_signed(query)
    if not nums:
        return []

    kws = extract_keywords(query)

    where_nums = " AND ".join(["text LIKE ?"] * len(nums))
    params = [f"%{n}%" for n in nums]

    cur = con.execute(
        f"""
        SELECT id, title, page_start, page_end, chunk_type, text
        FROM chunks
        WHERE {where_nums}
        LIMIT {limit}
        """,
        params,
    )
    rows = cur.fetchall()

    out = []
    for r in rows:
        cid, title, ps, pe, ctype, text = r

        if is_junk_chunk(title, pe, query):
            continue

        # keyword filter: require at least 1 keyword match (if keywords exist)
        if kws:
            t = (text or "").lower()
            if not any(k in t for k in kws[:6]):
                continue

        out.append(
            {
                "chunk_id": cid,
                "title": title,
                "pages": [ps, pe],
                "chunk_type": ctype,
                "text": text,
            }
        )

    return out


def cap_context(ctx: str, max_chars: int = 4000) -> str:
    """Cap context to preserve complete examples (increased from 2500 to 4000)"""
    ctx = (ctx or "").strip()
    return ctx[:max_chars]


# Relevance thresholds for RAG mode selection (IMPROVED for higher quality)
# Minimum FAISS cosine similarity (increased from 0.25)
FAISS_RELEVANCE_THRESHOLD = 0.45
# Minimum rerank score (increased from 0.15 for stricter filtering)
RERANK_RELEVANCE_THRESHOLD = 0.35


def retrieve_book_context(query: str) -> str:
    """
    Try to retrieve RD Sharma book context for a question.

    If RELEVANT chunks are found (above threshold), returns a compact internal
    context string (used only as reference for the LLM). If nothing relevant is found,
    returns an empty string so the LLM answers from its own knowledge (Qwen).

    Auto-enriches context with geometry information when detected.
    """
    query = (query or "").strip()
    if not query:
        return ""

    con = connect()
    try:
        context = ""
        match_info = {"source": None, "score": 0.0}

        # 1) SQL numeric+keyword match first (fast, high precision)
        exact = sql_numeric_candidates(con, query, limit=30)
        if exact:
            # Require at least 2-3 keyword matches for higher relevance
            kws = extract_keywords(query)
            if len(kws) >= 2:
                # Check if chunks have sufficient keyword overlap (STRENGTHENED: need 3+ matches or 50% coverage)
                relevant_chunks = []
                for chunk in exact[:5]:
                    text_lower = (chunk.get("text", "") or "").lower()
                    kw_matches = sum(1 for k in kws if k in text_lower)
                    # Need at least 3 keyword matches OR 50%+ of keywords present
                    keyword_coverage = kw_matches / len(kws) if kws else 0
                    if kw_matches >= 3 or keyword_coverage >= 0.5:
                        relevant_chunks.append(chunk)

                if relevant_chunks:
                    context = cap_context(
                        build_book_context(relevant_chunks[:3]), 4000)
                    match_info = {"source": "SQL", "score": 1.0}
                    logger.info("[RAG] Using SQL RD Sharma context (kw_matches=%d) for query: %s",
                                kw_matches, query[:80])
            else:
                # Not enough keywords for reliable SQL match - skip to FAISS
                logger.info(
                    "[RAG] Skipping SQL match: only %d keywords found", len(kws))

        # 2) FAISS semantic retrieval + reranking (only if SQL didn't find relevant context)
        if not context and ret:
            qv = embed_texts([query])[0]
            hits = ret.search(qv, top_k=60)

            candidates = []
            seen = set()

            for h in hits:
                # Filter by FAISS similarity threshold
                if h["score"] < FAISS_RELEVANCE_THRESHOLD:
                    continue  # Skip low-similarity chunks early

                c = fetch_chunk(con, h["chunk_id"])
                if not c:
                    continue
                cid = c["id"]
                if cid in seen:
                    continue
                seen.add(cid)

                candidates.append(
                    {
                        "chunk_id": cid,
                        "title": c["title"],
                        "pages": [c["page_start"], c["page_end"]],
                        "chunk_type": c["chunk_type"],
                        "text": c["text"],
                        "faiss_score": h["score"],
                    }
                )

            # rerank small set for relevance
            candidates = candidates[:30]

            # OPTIMIZATION: Skip reranker if top FAISS score is already good (>= 0.50)
            # Reranker is slow on CPU - only use it for borderline cases
            top_faiss_score = candidates[0].get(
                "faiss_score", 0) if candidates else 0

            if top_faiss_score >= 0.50:
                # FAISS score is good enough - skip expensive reranking
                logger.info(
                    "[RAG] Skipping reranker (FAISS score %.4f >= 0.50)", top_faiss_score)
                top = candidates[:3]  # Use top 3 from FAISS directly
                relevant_top = top  # Accept all with good FAISS score
            else:
                # Borderline case - use reranker for better filtering
                top = rerank(query, candidates, top_n=3)
                # Filter by rerank score threshold
                relevant_top = [c for c in top if c.get(
                    "rerank_score", 0) >= RERANK_RELEVANCE_THRESHOLD]

            if relevant_top:
                top_score = relevant_top[0].get("rerank_score", 0)
                context = cap_context(build_book_context(relevant_top), 4000)
                match_info = {"source": "FAISS", "score": top_score}
                logger.info("[RAG] Using FAISS RD Sharma context (rerank_score=%.4f, threshold=%.2f) for query: %s",
                            top_score, RERANK_RELEVANCE_THRESHOLD, query[:80])
            else:
                logger.info("[RAG] FAISS candidates rejected: top rerank_score=%.4f < threshold=%.2f",
                            top[0].get("rerank_score", 0) if top else 0, RERANK_RELEVANCE_THRESHOLD)

        # Final check: Only use RAG if we have relevant context
        if not context:
            logger.info(
                "[RAG] ⚠️ NO relevant context - falling back to PURE LLM for query: %s", query[:80])
            return ""
        else:
            logger.info("[RAG] ✓ Using RAG context (source=%s, score=%.4f)",
                        match_info["source"], match_info["score"])

        # Enrich context with geometry information if this is a geometry question
        context = enrich_context_with_geometry(context, query)
        geometry_info = detect_geometry_requirement(query)
        if geometry_info["requires_geometry"]:
            logger.info("[RAG] Geometry detected: %s",
                        ", ".join(geometry_info["geometry_types"]))

        logger.info("[RAG] Match: source=%s, score=%.4f",
                    match_info["source"], match_info["score"])
        return context

    except Exception as e:
        logger.error("[RAG] Error while retrieving book context: %s", str(e))
        return ""
    finally:
        con.close()


# -------------------------------------------------
# GET AVAILABLE METHODS FOR A QUESTION
# -------------------------------------------------
@app.post("/chat/methods")
def get_methods(question: str = Form(...)):
    """Generate available solution methods for a question"""
    question = (question or "").strip()
    if not question:
        return {"error": True, "methods": []}

    logger.info(f"[Methods] Generating methods for: {question[:50]}")

    try:
        # Generate methods using LLM
        from rag.llm_client import generate_methods_fallback
        methods = generate_methods_fallback(question)

        logger.info(f"[Methods] Generated {len(methods)} methods")
        return {
            "error": False,
            "question": question,
            "methods": methods
        }
    except Exception as e:
        logger.error(f"[Methods] Error: {str(e)}")
        return {
            "error": True,
            "methods": ["Approach 1", "Approach 2"],
            "message": str(e)
        }


# -------------------------------------------------
# TEXT CHAT WITH METHOD SELECTION + GEOMETRY
# -------------------------------------------------
@app.post("/chat/text")
def chat_text(
    question: str = Form(...),
    session_id: str = Form(None),
    method: str = Form(None)
):
    question = (question or "").strip()
    if not question:
        return {"answer": "Type a question."}

    if not session_id:
        session_id = str(uuid4())

    # ═══════════════════════════════════════════════════════════════════
    # NEW: Try production geometry solver first (deterministic routing)
    # ═══════════════════════════════════════════════════════════════════
    if GEOMETRY_SOLVER_AVAILABLE:
        geometry_result = process_question_with_geometry_pipeline(
            question=question,
            session_id=session_id,
            generate_diagram_flag=True
        )

        if geometry_result.get("use_geometry_pipeline"):
            result = geometry_result.get("result", {})
            final_answer = result.get("answer", "")

            # Update session with geometry answer
            update_session(session_id, question, final_answer)

            return {
                "answer": final_answer,
                "session_id": session_id,
                "method_used": "geometry_solver",
                "mode": "Geometry Solver (Verified)",
                "geometry_enhanced": True,
                "pipeline": "geometry_solver",
                "verified": result.get("verified", False),
                "diagram_path": result.get("diagram_path"),
                "history": load_session(session_id),
            }

    # ═══════════════════════════════════════════════════════════════════
    # FALLBACK: Standard RAG + LLM pipeline (for non-geometry questions)
    # ═══════════════════════════════════════════════════════════════════

    # Load session memory
    session = load_session(session_id)
    chat_context = build_chat_context(session)

    # Try to fetch RD Sharma book context (RAG).
    # If none is found, this will be an empty string and the LLM (Qwen)
    # will answer from its own knowledge.
    try:
        raw_book_context = retrieve_book_context(question)
        # Validate context is truly relevant before using
        if raw_book_context and validate_context_relevance(question, raw_book_context):
            book_context = raw_book_context
        else:
            book_context = ""
            logger.info(
                "[Chat/Text] Context failed relevance validation, using pure LLM mode")
    except Exception as e:
        logger.warning(
            f"Failed to retrieve book context: {e}. Falling back to pure LLM.")
        book_context = ""

    is_rag_mode = bool(book_context and book_context.strip())
    source_label = "RD SHARMA (RAG)" if is_rag_mode else "QWEN (Pure LLM)"
    logger.info(
        "[Chat/Text] session=%s mode=%s",
        session_id,
        source_label,
    )

    # Generate raw LLM answer (method hint goes in diagram_description if needed)
    raw_answer = generate_step_by_step_fallback(
        user_question=question,
        book_context=book_context,
        chat_context=chat_context,
        diagram_description=f"Use method: {method}" if method else ""
    )

    # CBSE formatted answer
    final_answer = build_final_answer(
        book_context=book_context,
        step_by_step=raw_answer
    )

    # Auto-enhance with legacy geometry analysis
    final_answer = enrich_answer_with_geometry(final_answer, question)

    # Save formatted answer to session
    update_session(session_id, question, final_answer)

    return {
        "answer": final_answer,
        "session_id": session_id,
        "method_used": method,
        "mode": "RAG (RD Sharma)" if is_rag_mode else "LLM (Qwen)",
        "geometry_enhanced": LEGACY_GEOMETRY_AVAILABLE,
        "pipeline": "rag_llm",
        # Full chat history for this session so the UI
        # can show the ongoing conversation.
        "history": load_session(session_id),
    }


# -------------------------------------------------
# SESSION HISTORY ENDPOINT
# -------------------------------------------------
@app.post("/chat/history")
def chat_history(session_id: str = Form(...)):
    """
    Return the full chat history for a given session_id.

    The frontend can call this when a page loads (with a
    stored session_id) to restore the conversation for
    returning users.
    """
    session_id = (session_id or "").strip()
    if not session_id:
        return {"error": True, "message": "session_id is required"}

    return {
        "error": False,
        **get_session_history(session_id),
    }


# -------------------------------------------------
# IMAGE EXTRACTION (Extract text first, then show methods)
# -------------------------------------------------
@app.post("/chat/image/extract")
async def extract_image(
    file: UploadFile = File(...),
    session_id: str = Form(None)
):
    if not session_id:
        session_id = str(uuid4())

    try:
        content = await file.read()
        image_b64 = base64.b64encode(content).decode("utf-8")

        logger.info(
            f"[{session_id}] Image received: {file.filename} ({len(content)} bytes)")

        # Step 1: Try VLM extraction
        logger.info(f"[{session_id}] Step 1: Attempting VLM extraction")
        extracted = extract_question_and_diagram_fallback(image_b64=image_b64)
        qtext = (extracted.get("question_text") or "").strip()
        diag = (extracted.get("diagram_description") or "").strip()

        logger.info(
            f"[{session_id}] VLM result - qtext: {'✓' if qtext else '✗'}, diag: {'✓' if diag else '✗'}")

        # Step 2: Fallback to OCR if VLM failed
        if not qtext:
            logger.info(
                f"[{session_id}] Step 2: VLM extraction empty, using OCR fallback")
            suffix = "." + (file.filename.split(".")
                            [-1] if "." in file.filename else "png")
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            logger.info(f"[{session_id}] OCR processing: {tmp_path}")
            qtext = (ocr_image(tmp_path) or "").strip()
            logger.info(
                f"[{session_id}] OCR result: {'✓' if qtext else '✗'} ({len(qtext)} chars)")

            # Cleanup
            try:
                os.unlink(tmp_path)
            except:
                pass

        # Step 3: Final validation
        if not qtext:
            logger.error(f"[{session_id}] Failed to extract text from image")
            return {
                "error": True,
                "message": (
                    "I couldn't automatically extract text from the image. "
                    "Troubleshooting:\n"
                    "1. Ensure the image is clear and well-lit\n"
                    "2. Make sure the question text is visible and not cropped\n"
                    "3. Try uploading a JPEG or PNG file\n"
                    "4. Type the question manually if issues persist"
                ),
                "session_id": session_id
            }

        logger.info(f"[{session_id}] Successfully extracted: {qtext[:100]}...")

        # Now get available methods for this extracted question
        from rag.llm_client import generate_methods_fallback
        try:
            methods = generate_methods_fallback(qtext)
            logger.info(f"[{session_id}] Generated {len(methods)} methods")
        except Exception as e:
            logger.warning(
                f"[{session_id}] Could not generate methods: {str(e)}")
            methods = ["Approach 1", "Approach 2"]

        return {
            "error": False,
            "extracted_question": qtext,
            "diagram_description": diag,
            "methods": methods,
            "session_id": session_id
        }

    except Exception as e:
        logger.error(
            f"[{session_id}] Unexpected error in /chat/image/extract: {str(e)}", exc_info=True)
        return {
            "error": True,
            "message": f"Error processing image: {str(e)}",
            "session_id": session_id
        }


# -------------------------------------------------
# IMAGE ANSWER (Generate answer with selected method + GEOMETRY)
# -------------------------------------------------
@app.post("/chat/image/answer")
def answer_image(
    question: str = Form(...),
    session_id: str = Form(None),
    method: str = Form(None),
    diagram_description: str = Form(None)
):
    question = (question or "").strip()
    if not question:
        return {"error": True, "answer": "No question provided"}

    if not session_id:
        session_id = str(uuid4())

    try:
        # ═══════════════════════════════════════════════════════════════════
        # NEW: Try production geometry solver first (deterministic routing)
        # ═══════════════════════════════════════════════════════════════════
        if GEOMETRY_SOLVER_AVAILABLE:
            geometry_result = process_question_with_geometry_pipeline(
                question=question,
                session_id=session_id,
                generate_diagram_flag=True
            )

            if geometry_result.get("use_geometry_pipeline"):
                result = geometry_result.get("result", {})
                final_answer = result.get("answer", "")

                # Update session with geometry answer
                update_session(session_id, question, final_answer)

                return {
                    "error": False,
                    "answer": final_answer,
                    "session_id": session_id,
                    "method_used": "geometry_solver",
                    "mode": "Geometry Solver (Verified)",
                    "geometry_enhanced": True,
                    "pipeline": "geometry_solver",
                    "verified": result.get("verified", False),
                    "diagram_path": result.get("diagram_path"),
                    "history": load_session(session_id),
                }

        # ═══════════════════════════════════════════════════════════════════
        # FALLBACK: Standard RAG + LLM pipeline (for non-geometry questions)
        # ═══════════════════════════════════════════════════════════════════

        # Load session memory
        session = load_session(session_id)
        chat_context = build_chat_context(session)

        # RAG: fetch RD Sharma context for the extracted/typed question
        try:
            raw_book_context = retrieve_book_context(question)
            # Validate context is truly relevant before using
            if raw_book_context and validate_context_relevance(question, raw_book_context):
                book_context = raw_book_context
            else:
                book_context = ""
                logger.info(
                    "[Chat/Image/Answer] Context failed relevance validation, using pure LLM mode")
        except Exception as e:
            logger.warning(
                f"Failed to retrieve book context: {e}. Falling back to pure LLM.")
            book_context = ""

        is_rag_mode = bool(book_context and book_context.strip())
        source_label = "RD SHARMA (RAG)" if is_rag_mode else "QWEN (Pure LLM)"
        logger.info(
            "[Chat/Image/Answer] session=%s mode=%s",
            session_id,
            source_label,
        )

        # Generate raw LLM answer (pass method and diagram hints via diagram_description parameter)
        diagram_hint = ""
        if method:
            diagram_hint += f"Use method: {method}. "
        if diagram_description:
            diagram_hint += f"Diagram info: {diagram_description}"

        raw_answer = generate_step_by_step_fallback(
            user_question=question,
            book_context=book_context,
            chat_context=chat_context,
            diagram_description=diagram_hint.strip() if diagram_hint else ""
        )

        # CBSE formatted answer
        final_answer = build_final_answer(
            book_context=book_context,
            step_by_step=raw_answer
        )

        # Auto-enhance with legacy geometry analysis
        final_answer = enrich_answer_with_geometry(final_answer, question)

        # Save formatted answer to session
        update_session(session_id, question, final_answer)

        logger.info(
            f"[{session_id}] Image answer generated successfully with method: {method}")

        return {
            "error": False,
            "answer": final_answer,
            "session_id": session_id,
            "method_used": method,
            "mode": "RAG (RD Sharma)" if is_rag_mode else "LLM (Qwen)",
            "geometry_enhanced": LEGACY_GEOMETRY_AVAILABLE,
            "pipeline": "rag_llm",
            # Full chat history so UI can render conversation
            "history": load_session(session_id),
        }

    except Exception as e:
        logger.error(
            f"[{session_id}] Unexpected error in /chat/image/answer: {str(e)}", exc_info=True)
        return {
            "error": True,
            "answer": f"Error generating answer: {str(e)}",
            "session_id": session_id
        }


# -------------------------------------------------
# IMAGE CHAT (Legacy - Direct Answer + GEOMETRY)
# -------------------------------------------------
@app.post("/chat/image")
async def chat_image(
    file: UploadFile = File(...),
    session_id: str = Form(None)
):
    if not session_id:
        session_id = str(uuid4())

    try:
        content = await file.read()
        image_b64 = base64.b64encode(content).decode("utf-8")

        logger.info(
            f"[{session_id}] Image received: {file.filename} ({len(content)} bytes)")

        # Step 1: Try VLM extraction
        logger.info(f"[{session_id}] Step 1: Attempting VLM extraction")
        extracted = extract_question_and_diagram_fallback(image_b64=image_b64)
        qtext = (extracted.get("question_text") or "").strip()
        diag = (extracted.get("diagram_description") or "").strip()

        logger.info(
            f"[{session_id}] VLM result - qtext: {'✓' if qtext else '✗'}, diag: {'✓' if diag else '✗'}")

        # Step 2: Fallback to OCR if VLM failed
        if not qtext:
            logger.info(
                f"[{session_id}] Step 2: VLM extraction empty, using OCR fallback")
            suffix = "." + (file.filename.split(".")
                            [-1] if "." in file.filename else "png")
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            logger.info(f"[{session_id}] OCR processing: {tmp_path}")
            qtext = (ocr_image(tmp_path) or "").strip()
            logger.info(
                f"[{session_id}] OCR result: {'✓' if qtext else '✗'} ({len(qtext)} chars)")

            # Cleanup
            try:
                os.unlink(tmp_path)
            except:
                pass

        # Step 3: Final validation
        if not qtext:
            logger.error(f"[{session_id}] Failed to extract text from image")
            return {
                "error": True,
                "answer": (
                    "I couldn't automatically extract text from the image. "
                    "Troubleshooting:\n"
                    "1. Ensure the image is clear and well-lit\n"
                    "2. Make sure the question text is visible and not cropped\n"
                    "3. Try uploading a JPEG or PNG file\n"
                    "4. Type the question manually if issues persist"
                ),
                "session_id": session_id
            }

        logger.info(f"[{session_id}] Successfully extracted: {qtext[:100]}...")

        # ═══════════════════════════════════════════════════════════════════
        # NEW: Try production geometry solver first (deterministic routing)
        # ═══════════════════════════════════════════════════════════════════
        if GEOMETRY_SOLVER_AVAILABLE:
            geometry_result = process_question_with_geometry_pipeline(
                question=qtext,
                session_id=session_id,
                generate_diagram_flag=True
            )

            if geometry_result.get("use_geometry_pipeline"):
                result = geometry_result.get("result", {})
                final_answer = result.get("answer", "")

                # Update session with geometry answer
                update_session(session_id, qtext, final_answer)

                logger.info(
                    f"[{session_id}] Answer generated successfully using geometry pipeline")

                return {
                    "error": False,
                    "answer": final_answer,
                    "session_id": session_id,
                    "geometry_enhanced": True,
                    "pipeline": "geometry_solver",
                    "verified": result.get("verified", False),
                    "diagram_path": result.get("diagram_path"),
                    "history": load_session(session_id),
                }

        # ═══════════════════════════════════════════════════════════════════
        # FALLBACK: Standard RAG + LLM pipeline (for non-geometry questions)
        # ═══════════════════════════════════════════════════════════════════

        # Load session memory
        session = load_session(session_id)
        chat_context = build_chat_context(session)

        # RAG: fetch RD Sharma context if this looks like a book question
        try:
            book_context = retrieve_book_context(qtext)
        except Exception as e:
            logger.warning(
                f"Failed to retrieve book context: {e}. Falling back to pure LLM.")
            book_context = ""

        logger.info(
            "[Chat/Image] session=%s source=%s",
            session_id,
            "rd_sharma_rag" if book_context else "llm_generic",
        )

        # Generate raw LLM answer
        raw_answer = generate_step_by_step_fallback(
            user_question=qtext,
            book_context=book_context,
            chat_context=chat_context,
            diagram_description=diag
        )

        # CBSE formatted answer
        final_answer = build_final_answer(
            book_context=book_context,
            step_by_step=raw_answer
        )

        # Auto-enhance with legacy geometry analysis
        final_answer = enrich_answer_with_geometry(final_answer, qtext)

        # Save formatted answer to session
        update_session(session_id, qtext, final_answer)

        logger.info(f"[{session_id}] Answer generated successfully")

        return {
            "error": False,
            "answer": final_answer,
            "session_id": session_id,
            "geometry_enhanced": LEGACY_GEOMETRY_AVAILABLE,
            "pipeline": "rag_llm",
            # Full chat history so UI can render conversation
            "history": load_session(session_id),
        }

    except Exception as e:
        logger.error(
            f"[{session_id}] Unexpected error in /chat/image: {str(e)}", exc_info=True)
        return {
            "error": True,
            "answer": f"Error processing image: {str(e)}",
            "session_id": session_id
        }
