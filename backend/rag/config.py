# from pathlib import Path
# import os

# BASE_DIR = Path(__file__).resolve().parents[1]
# DATA_DIR = BASE_DIR / "data"

# RAW_DIR = DATA_DIR / "raw"
# PAGES_DIR = DATA_DIR / "pages"
# OCR_DIR = DATA_DIR / "ocr"
# DB_DIR = DATA_DIR / "db"
# FAISS_DIR = DATA_DIR / "faiss"

# SQLITE_PATH = DB_DIR / "chunks.sqlite"
# FAISS_INDEX_PATH = FAISS_DIR / "index.faiss"
# FAISS_META_PATH = FAISS_DIR / "meta.json"

# # Embeddings (CPU-safe)
# EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"

# OCR_LANG = "en"
# RENDER_DPI = 220

# # Ollama config (local)
# LLM_URL = os.getenv("LLM_URL", "http://127.0.0.1:11434")
# LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b-instruct")
# # LLM_MODEL = os.getenv("LLM_MODEL", "qwen3")
# VLM_URL = os.getenv("VLM_URL", "http://127.0.0.1:9001/vlm")



from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

RAW_DIR = DATA_DIR / "raw"
PAGES_DIR = DATA_DIR / "pages"
OCR_DIR = DATA_DIR / "ocr"
DB_DIR = DATA_DIR / "db"
FAISS_DIR = DATA_DIR / "faiss"

SQLITE_PATH = DB_DIR / "chunks.sqlite"
FAISS_INDEX_PATH = FAISS_DIR / "index.faiss"
FAISS_META_PATH = FAISS_DIR / "meta.json"

# -------------------------
# Embeddings
# -------------------------
EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"

OCR_LANG = "en"
RENDER_DPI = 220

# -------------------------
# Ollama / VLM
# -------------------------
LLM_URL = os.getenv("LLM_URL", "http://127.0.0.1:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b-instruct")
# LLM_MODEL = os.getenv("LLM_MODEL", "qwen3")

VLM_URL = os.getenv("VLM_URL", "http://127.0.0.1:9001/vlm")

# ==================================================
# SESSION / CHAT MEMORY
# ==================================================
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
SESSION_TTL = 1800   # 30 minutes
MAX_TURNS = 5        # last 5 Q&A only
