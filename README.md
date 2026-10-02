# Vict v2

Vict is a clean, lightweight, local-only Discord AI bot with persistent memory. It runs entirely on local hardware without using Ollama, OpenAI, or any cloud AI APIs.

---

## Key Features

- **100% Local Execution**: Runs locally using GGUF models via `llama-cpp-python`. No cloud AI APIs or Ollama required.
- **Low Memory Footprint**: Designed to stay well under ~2 GB RAM.
- **Global FIFO AI Generation Queue**:
  - Uses a single local GGUF model instance to keep RAM usage low.
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
├── .env             # Environment variables (Discord token, limits)
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
MAX_INPUT_CHARS=150
MAX_MEMORY_TOKENS=5000
MODEL_PATH=models/SmolLM2-360M-Instruct-Q4_K_M.gguf
```

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

## Global FIFO Generation Queue Architecture

Vict operates on low-resource hardware (~2 GB RAM) with a single local GGUF model instance.

To prevent concurrent inference conflicts, race conditions, or elevated memory usage, Vict implements a single global asynchronous FIFO queue (`asyncio.Queue` + background worker):

- Requests from `/talk` and passive `hey vict` triggers are placed into the shared queue upon receipt.
- Requests are processed sequentially in strict arrival order (A → B → C).
- Model generation runs asynchronously in a worker thread (`asyncio.to_thread`) to ensure Discord's event loop remains fully responsive.
- Operating status can be monitored using `/check status` (reports `AI/Model: Ready` vs `Generating` and `Queue Waiting: X`).

---

## Interaction Methods

### 1. Passive Trigger (`hey vict`)
Vict responds to normal messages **only when they start with `hey vict`** (case-insensitive).

- **Triggers**: `hey vict`, `HEY VICT`, `Hey Vict, what are you doing?`, `hey vict what color is the sky?`
- **Does NOT trigger**: `yo hey vict`, `well hey vict`, `heyy vict`, `heyvict`, `hey victory`

### 2. Slash Commands
- `/check status`: Displays operational status, AI status (`Ready` / `Generating`), waiting queue length, short-term message count, persistent memory size, and configured limits.
- `/talk [input]`: Explicit slash command interaction with full input validation and rate-limited response streaming.

---

## Testing

Run unit tests with pytest:

```bash
python3 -m pytest tests/
```
