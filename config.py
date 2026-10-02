import os
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

BASE_DIR = Path(__file__).parent.resolve()


def parse_bool(value: Any, default: bool = False) -> bool:
    """Safely converts string/any to bool."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    val_str = str(value).strip().lower()
    if val_str in ("true", "1", "yes", "on"):
        return True
    if val_str in ("false", "0", "no", "off"):
        return False
    return default


DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
MAX_INPUT_CHARS = int(os.getenv("MAX_INPUT_CHARS", 200))
MAX_MEMORY_TOKENS = int(os.getenv("MAX_MEMORY_TOKENS", 5000))
MODEL_PATH = os.getenv("MODEL_PATH", "models/SmolLM2-360M-Instruct-Q4_K_M.gguf")

# RAM-related llama.cpp options
N_CTX = int(os.getenv("N_CTX", 4096))
N_BATCH = int(os.getenv("N_BATCH", 128))
N_UBATCH = int(os.getenv("N_UBATCH", 128))
N_THREADS = int(os.getenv("N_THREADS", 4))
USE_MMAP = parse_bool(os.getenv("USE_MMAP"), default=True)
USE_MLOCK = parse_bool(os.getenv("USE_MLOCK"), default=False)
CACHE_TYPE_K = os.getenv("CACHE_TYPE_K", "f16").strip().lower()
CACHE_TYPE_V = os.getenv("CACHE_TYPE_V", "f16").strip().lower()

MODELS_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "data"
MEMORY_FILE = DATA_DIR / "memory.txt"
PERSONA_FILE = BASE_DIR / "persona.txt"

TARGET_MEMORY_TOKENS = int(MAX_MEMORY_TOKENS * 0.8)  # Target ~4000 tokens when max is 5000


def ensure_directories_and_files():
    """Ensure required directories and initial files exist."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not MEMORY_FILE.exists():
        MEMORY_FILE.write_text("", encoding="utf-8")

    if not PERSONA_FILE.exists():
        PERSONA_FILE.write_text(
            "You are Vict, a casual, friendly, somewhat goofy conversational AI assistant. "
            "You enjoy chatting with users, joking around, and being helpful while maintaining a relaxed tone.",
            encoding="utf-8",
        )


def load_persona() -> str:
    """Load the persona description from persona.txt."""
    if PERSONA_FILE.exists():
        return PERSONA_FILE.read_text(encoding="utf-8").strip()
    return (
        "You are Vict, a casual, friendly, somewhat goofy conversational AI assistant."
    )
