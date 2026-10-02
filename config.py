import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

BASE_DIR = Path(__file__).parent.resolve()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
MAX_INPUT_CHARS = int(os.getenv("MAX_INPUT_CHARS", 150))
MAX_MEMORY_TOKENS = int(os.getenv("MAX_MEMORY_TOKENS", 5000))
MODEL_PATH = os.getenv("MODEL_PATH", "models/SmolLM2-360M-Instruct-Q4_K_M.gguf")

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
