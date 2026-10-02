# Vict

Vict is a clean, lightweight, local-only Discord AI bot with persistent memory. It runs entirely on local hardware without using Ollama, OpenAI, or any cloud AI APIs.

---

## Key Features

- **100% Local Execution**: Runs locally using GGUF models via `llama-cpp-python`.
- **Low Memory Footprint**: Designed to stay well under ~2 GB RAM.
- **Persistent & Short-Term Memory**:
  - Retains the 49 most recent messages as short-term context.
  - Automatically consolidates context every 50 messages into `data/memory.txt`.
- **Live Near-Word-by-Word Streaming**: Streams response generation directly into Discord with a rate-limited edit queue to avoid API rate limits.
- **Strict Formatting & Layout Protection**:
  - Automatically wraps AI output in single backticks: `@username: [input]\n\n\`[response]\``.
  - Normalizes newlines and whitespace into single-line responses.
- **Permanent User Identity Keying**: Uses Discord user IDs for reliable long-term identity recognition across username/nickname changes.

---

## Project Structure

```text
Vict/
├── bot.py           # Discord client and slash commands (/check status, /talk)
├── brain.py         # Local GGUF model loader, prompt builder, single-line text normalizer
├── memory.py        # Short-term buffer & atomic persistent memory manager
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

## Setup Instructions

### 1. Requirements
- Python 3.10+
- A Discord Bot Token ([Discord Developer Portal](https://discord.com/developers/applications))

### 2. Installation
Clone the repository and install dependencies:

```bash
pip install -r requirements.txt
```

### 3. Model Setup
Download the default GGUF model (or another compatible GGUF model) into the `models/` folder:

- **Default Model**: `models/SmolLM2-360M-Instruct-Q4_K_M.gguf`

You can download it from Hugging Face:
```bash
mkdir -p models
curl -L -o models/SmolLM2-360M-Instruct-Q4_K_M.gguf https://huggingface.co/HuggingFaceTB/SmolLM2-360M-Instruct-GGUF/resolve/main/smollm2-360m-instruct-q4_k_m.gguf
```

### 4. Configuration
Copy `.env.example` to `.env` and insert your Discord Bot Token:

```bash
cp .env.example .env
```

Edit `.env`:
```env
DISCORD_TOKEN=your_actual_discord_bot_token
MAX_INPUT_CHARS=150
MAX_MEMORY_TOKENS=5000
MODEL_PATH=models/SmolLM2-360M-Instruct-Q4_K_M.gguf
```

---

## Running Vict

Start the bot:

```bash
python bot.py
```

---

## Available Commands

- `/check status`: Displays operational status, model availability, short-term message count, and persistent memory character size.
- `/talk [input]`: Main interaction command. Validates input length against `MAX_INPUT_CHARS` (150 default), generates response using local AI, and streams response word-by-word into Discord formatted as:

```text
@username: [input]

`[Vict single-line response]`
```

---

## Testing

Run unit tests with pytest:

```bash
PYTHONPATH=. pytest tests/
```
