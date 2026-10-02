# Vict v2

Vict is a clean, lightweight, local-only Discord AI bot with persistent memory. It runs entirely on local hardware without using Ollama, OpenAI, or any cloud AI APIs.

---

## Key Features

- **100% Local Execution**: Runs locally using GGUF models via `llama-cpp-python`. No cloud AI APIs or Ollama required.
- **Low Memory Footprint (~2 GB RAM Target)**:
  - Uses one single shared local GGUF model instance across chat requests and memory consolidation.
  - Persistent memory remains strictly disk-backed (`data/memory.txt`) to avoid unnecessary RAM duplication.
  - Low-memory llama-cpp-python settings (`N_CTX=4096`, `USE_MMAP=true`, `USE_MLOCK=false`, `N_BATCH=128`, `CACHE_TYPE_K/V=f16`).
- **Global FIFO AI Generation Queue**:
  - Processes incoming `/talk` commands and passive `hey vict` triggers sequentially in first-in, first-out (FIFO) order.
  - Simultaneous requests wait cleanly in queue without blocking Discord's event loop or causing race conditions.
- **Passive Trigger (`hey vict`)**: Listens to ordinary Discord messages and responds when the message **starts with** `hey vict` (case-insensitive).
- **Persistent & Short-Term Memory**:
  - Retains the 49 most recent messages as active short-term context.
  - Automatically consolidates context every 50 messages into `data/memory.txt`.
- **Live Near-Word-by-Word Streaming**: Streams response generation directly into Discord with a rate-limited edit queue to avoid API rate limits.
- **Strict Formatting & Layout Protection**:
  - Wraps AI output in backticks: `@username: [input]\n\n\`[Vict response]\``.
  - Enforces single-line output by stripping newlines, extra whitespace, and backticks.
- **Permanent User Identity Keying**: Uses Discord user IDs for reliable long-term identity recognition across username/nickname changes.
- **Slash Commands**: `/talk [input]` and `/check status`.

---

## Project Structure

```text
Vict/
├── START.bat        # Windows launcher (verifies Python 3.14, dependencies, model, and runs Vict)
├── bot.py           # Discord client, on_message handler, global FIFO queue, and slash commands
├── brain.py         # Local GGUF model loader, prompt builder, single-line text normalizer
├── memory.py        # Short-term buffer & atomic persistent memory manager
├── parser.py        # 'hey vict' start-of-message trigger detection & extraction
├── config.py        # Environment configuration and file setup
├── persona.txt      # Editable bot personality file
├── .env             # Environment variables (Discord token, limits, RAM options)
├── .env.example     # Example environment configuration
├── requirements.txt # Python dependencies
├── README.md        # Documentation
├── models/          # Folder for GGUF model storage
└── data/
    └── memory.txt   # Persistent memory text file
```

---

## Setup & Running Instructions

### 1. Requirements
- Python 3.14 (system-installed on Windows)
- A Discord Bot Token ([Discord Developer Portal](https://discord.com/developers/applications))

### 2. Discord Developer Portal Configuration
Enable the **Message Content Intent** in your bot settings:
1. Go to [Discord Developer Portal](https://discord.com/developers/applications).
2. Select your application -> **Bot**.
3. Under **Privileged Gateway Intents**, turn ON **Message Content Intent**.
4. Save Changes.

### 3. Local GGUF Model Placement
Ensure the GGUF model is inside the `models/` directory:

- **Default Model**: `models/SmolLM2-360M-Instruct-Q4_K_M.gguf`

```bash
mkdir -p models
curl -L -o models/SmolLM2-360M-Instruct-Q4_K_M.gguf https://huggingface.co/HuggingFaceTB/SmolLM2-360M-Instruct-GGUF/resolve/main/smollm2-360m-instruct-q4_k_m.gguf
```

### 4. Environment Configuration
Copy `.env.example` to `.env` and set your variables:

```bash
cp .env.example .env
```

`.env` configuration options:
```env
DISCORD_TOKEN=your_actual_discord_bot_token
MAX_INPUT_CHARS=200
MAX_MEMORY_TOKENS=5000
MODEL_PATH=models/SmolLM2-360M-Instruct-Q4_K_M.gguf

N_CTX=4096
N_BATCH=128
N_UBATCH=128
N_THREADS=4
USE_MMAP=true
USE_MLOCK=false
CACHE_TYPE_K=f16
CACHE_TYPE_V=f16
```

---

## RAM Optimization & Architecture

Vict is optimized to run comfortably within a **~2 GB RAM** footprint:

- **Single Model Instance**: Exactly one shared local GGUF model instance is initialized at startup and reused for chat responses and memory consolidation.
- **Global FIFO Generation Queue**: Guarantees only 1 active inference operation runs at a time, preventing memory spikes and context conflicts.
- **Disk-Backed Persistent Memory**: Persistent memory lives in `data/memory.txt` and is loaded on-demand per request rather than stored as an unconstrained in-memory duplicate.
- **Configurable Context & Batch Sizes**:
  - `N_CTX=4096`: Default context window limit.
  - `N_BATCH=128`, `N_UBATCH=128`: Modest prompt processing batch sizes.
  - `USE_MMAP=true`, `USE_MLOCK=false`: Memory mapping enabled; mlock disabled so the model is not forced into physical RAM.
  - `CACHE_TYPE_K=f16`, `CACHE_TYPE_V=f16`: F16 KV cache precision.
  - `N_THREADS=4`: Default CPU thread count.

---

## Running Vict

### On Windows
Run `START.bat` directly:
- Checks system Python 3.14 (`py -3.14`).
- Verifies `discord.py` and `llama-cpp-python` imports.
- Verifies model existence at `models/SmolLM2-360M-Instruct-Q4_K_M.gguf`.
- Launches `bot.py` with `py -3.14`.

### On Linux / macOS
```bash
python3 bot.py
```

---

## Interaction Methods

### 1. Passive Trigger (`hey vict`)
Vict responds to normal messages **only when they start with `hey vict`** (case-insensitive).

- **Triggers**: `hey vict`, `HEY VICT`, `Hey Vict, what are you doing?`, `hey vict what color is the sky?`
- **Does NOT trigger**: `yo hey vict`, `well hey vict`, `heyy vict`, `heyvict`, `hey victory`

### 2. Slash Commands
- `/check status`: Displays operational status, RAM usage, model loaded state, context size, waiting queue length, short-term message count, persistent memory size, and configured limits.
- `/talk [input]`: Explicit slash command interaction with full input validation and rate-limited response streaming.

---

## Testing

Run unit tests with pytest:

```bash
python3 -m pytest tests/
```
