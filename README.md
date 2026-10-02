# Vict v2

Vict is a clean, lightweight, local-only Discord AI bot with persistent memory. It runs entirely on local hardware without using Ollama, OpenAI, or any cloud AI APIs.

---

## Key Features

- **100% Local Execution**: Runs locally using GGUF models via `llama-cpp-python`. No cloud AI APIs or Ollama required.
- **Low Memory Footprint**: Designed to stay well under ~2 GB RAM.
- **Passive Trigger (`hey vict`)**: Listens to ordinary Discord messages and responds when triggered by `hey vict` (case-insensitive with word boundaries).
- **Yggdrasil Transcript Compatibility**:
  - Parses Yggdrasil bridge transcripts to extract real human speakers instead of attributing messages to Yggdrasil.
  - Resolves Yggdrasil usernames against guild members to obtain stable Discord user IDs.
  - Supports custom emoji Markdown and multi-speaker Yggdrasil transcripts.
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
├── bot.py           # Discord client, on_message handler, and slash commands (/check status, /talk)
├── brain.py         # Local GGUF model loader, prompt builder, single-line text normalizer
├── memory.py        # Short-term buffer & atomic persistent memory manager
├── parser.py        # Yggdrasil transcript parser & 'hey vict' trigger extraction
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

### 2. Discord Developer Portal Configuration
Enable the **Message Content Intent** in your bot settings:
1. Go to [Discord Developer Portal](https://discord.com/developers/applications).
2. Select your application -> **Bot**.
3. Under **Privileged Gateway Intents**, turn ON **Message Content Intent**.
4. Save Changes.

### 3. Installation
Clone the repository and install dependencies:

```bash
pip install -r requirements.txt
```

### 4. Local GGUF Model Placement
Download the default GGUF model into the `models/` folder:

- **Default Model**: `models/SmolLM2-360M-Instruct-Q4_K_M.gguf`

```bash
mkdir -p models
curl -L -o models/SmolLM2-360M-Instruct-Q4_K_M.gguf https://huggingface.co/HuggingFaceTB/SmolLM2-360M-Instruct-GGUF/resolve/main/smollm2-360m-instruct-q4_k_m.gguf
```

### 5. Environment Configuration
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

Start the bot:

```bash
python bot.py
```

---

## Interaction Methods

### 1. Passive Trigger (`hey vict`)
Vict actively listens to channel messages containing `hey vict` (case-insensitive).
- Trigger examples: `hey vict`, `HEY VICT`, `hey vict, what color is the sky?`, `yo hey vict what is happening`
- Non-triggers: `heyy vict`, `heyvict`, `hey victory`

### 2. Yggdrasil Transcript Compatibility
When a message arrives from Yggdrasil (or matching Yggdrasil transcript format), Vict extracts the embedded human speakers rather than attributing the message to Yggdrasil.

Example:
```text
### YggdrasilAPP5:18 PM
**nastyboy000** [:userphone:](https://cdn.discordapp.com/emojis/1311268018625576971.webp?size=56) hey vict, what color is the sky?
```

Vict interprets this as:
- **Speaker**: `@nastyboy000` (NOT `@YggdrasilAPP`)
- **Semantic Input**: `what color is the sky?`
- **Formatted Response**:
```text
@nastyboy000: hey vict, what color is the sky?

`[Vict response]`
```

If a Yggdrasil transcript contains multiple speaker lines:
```text
**nastyboy000** [:userphone:](...) lmao
**mike** yo i gotta dip
**nastyboy000** [:userphone:](...) hey vict, what color is the sky?
```
Vict preserves `@nastyboy000: lmao` and `@mike: yo i gotta dip` as prior context in conversation memory and processes the latest `hey vict` entry.

### 3. Slash Commands
- `/check status`: Displays operational status, local model availability, short-term message count, persistent memory size, and configured limits.
- `/talk [input]`: Explicit slash command interaction with full input validation and rate-limited response streaming.

---

## Testing

Run unit tests with pytest:

```bash
python3 -m pytest tests/
```
