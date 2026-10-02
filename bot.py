import asyncio
import logging
import sys
from dataclasses import dataclass
from typing import Optional, Any
import discord
from discord import app_commands
from discord.ext import commands

import config
from brain import Brain, normalize_text
from memory import MemoryManager
from parser import has_hey_vict_trigger, extract_trigger_input

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("Vict.Bot")

# Ensure required directories and files exist at startup
config.ensure_directories_and_files()

# Initialize core modules
memory_mgr = MemoryManager()
brain = Brain()


def get_ram_usage_str() -> str:
    """Returns formatted RAM usage string of the current process (MB or GB)."""
    try:
        import psutil
        process = psutil.Process()
        mem_bytes = process.memory_info().rss
        mem_mb = mem_bytes / (1024 * 1024)
        if mem_mb >= 1024:
            return f"{mem_mb / 1024:.1f} GB"
        return f"{mem_mb:.1f} MB"
    except Exception:
        pass

    try:
        import resource
        mem_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
        if mem_mb >= 1024:
            return f"{mem_mb / 1024:.1f} GB"
        return f"{mem_mb:.1f} MB"
    except Exception:
        pass

    return "Unknown"


@dataclass
class QueueItem:
    user_id: str
    username: str
    clean_display: str
    clean_semantic: str
    message: Any  # discord.Message or mock message
    source_type: str = "chat"  # "talk" or "hey_vict"


# Global FIFO AI Generation Queue State
generation_queue: asyncio.Queue = asyncio.Queue()
is_generating: bool = False
queue_worker_task: Optional[asyncio.Task] = None


async def queue_worker():
    """Background worker processing AI generation requests sequentially in FIFO order."""
    global is_generating
    logger.info("Global AI generation queue worker started.")
    while True:
        try:
            item: QueueItem = await generation_queue.get()
            is_generating = True
            try:
                await process_queue_item(item)
            except Exception as e:
                logger.error(f"Unhandled error processing queue item: {e}")
            finally:
                is_generating = False
                generation_queue.task_done()
        except asyncio.CancelledError:
            logger.info("Queue worker task cancelled.")
            break
        except Exception as e:
            logger.error(f"Unexpected error in queue worker loop: {e}")
            await asyncio.sleep(0.1)


def ensure_queue_worker_running():
    """Ensures the single global queue worker task is active."""
    global queue_worker_task
    if queue_worker_task is None or queue_worker_task.done():
        try:
            loop = asyncio.get_running_loop()
            queue_worker_task = loop.create_task(queue_worker())
        except RuntimeError:
            pass


async def process_queue_item(item: QueueItem):
    """Executes local AI generation and streaming for a single queued request."""
    loop = asyncio.get_running_loop()

    persona = config.load_persona()
    persistent_mem = memory_mgr.get_persistent_memory()
    short_term_ctx = memory_mgr.get_short_term_context()

    last_edit_time = 0.0
    MIN_EDIT_INTERVAL = 0.8
    latest_response_text = "..."
    final_generated_text = ""

    def fetch_stream_tokens():
        return brain.generate_talk_stream(
            persona=persona,
            persistent_memory=persistent_mem,
            short_term_context=short_term_ctx,
            current_username=item.username,
            current_user_input=item.clean_semantic,
        )

    try:
        # Use run_in_executor / threadpool to not block event loop during synchronous llama-cpp inference
        token_stream = await loop.run_in_executor(None, fetch_stream_tokens)

        while True:
            chunk = await loop.run_in_executor(None, lambda: next(token_stream, None))
            if chunk is None:
                break

            latest_response_text = chunk
            final_generated_text = chunk

            now = loop.time()
            if now - last_edit_time >= MIN_EDIT_INTERVAL:
                updated_content = f"@{item.username.lstrip('@')}: {item.clean_display}\n\n`{latest_response_text}`"
                try:
                    await item.message.edit(content=updated_content)
                    last_edit_time = now
                except discord.HTTPException as e:
                    logger.error(f"Discord API edit error: {e}")
                except Exception as e:
                    logger.warning(f"Message edit error: {e}")

    except Exception as e:
        logger.error(f"Error during Vict reply generation for user {item.username}: {e}")
        if not final_generated_text:
            final_generated_text = "Sorry, I ran into an error generating a reply."

    final_content = f"@{item.username.lstrip('@')}: {item.clean_display}\n\n`{final_generated_text}`"
    try:
        await item.message.edit(content=final_content)
    except discord.HTTPException as e:
        logger.error(f"Final message edit failed: {e}")
    except Exception as e:
        logger.warning(f"Final edit error: {e}")

    # Record user message and Vict response into short-term memory
    u_trig = memory_mgr.add_message(
        user_id=item.user_id, username=item.username, content=item.clean_display, role="user"
    )
    v_trig = memory_mgr.add_message(
        user_id="vict", username="Vict", content=final_generated_text, role="assistant"
    )

    # Check 50-message consolidation threshold
    if u_trig or v_trig:
        logger.info("Short-term memory reached 50 messages! Triggering memory consolidation...")

        def run_consolidation():
            full_batch = memory_mgr.get_full_batch()
            existing_mem = memory_mgr.get_persistent_memory()
            return brain.consolidate_memory(
                existing_memory=existing_mem, full_batch=full_batch
            )

        new_memory = await loop.run_in_executor(None, run_consolidation)

        try:
            memory_mgr.save_persistent_memory(new_memory)
            memory_mgr.reset_short_term_batch()
            logger.info("Persistent memory updated successfully and batch reset.")
        except Exception as e:
            logger.error(f"Failed to save consolidated persistent memory: {e}")


class VictBot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # Enable Message Content intent for listening to ordinary messages
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        """Called when the bot is setting up. Registers app commands and starts queue worker."""
        logger.info("Registering Discord slash commands...")
        await self.tree.sync()
        logger.info("Slash commands synced successfully.")
        ensure_queue_worker_running()

    async def on_message(self, message: discord.Message):
        """Handles incoming messages for strict 'hey vict' start triggers."""
        # Ignore all bot messages (including Vict's own messages)
        if message.author.bot:
            return

        # Ordinary user message check for start-of-message 'hey vict'
        if has_hey_vict_trigger(message.content):
            username = message.author.name  # username/handle, not nickname/display name
            user_id = str(message.author.id)
            semantic_input = extract_trigger_input(message.content)

            await process_chat_response(
                destination=message.channel,
                user_id=user_id,
                username=username,
                display_input=message.content,
                semantic_input=semantic_input,
                source_type="hey_vict",
            )


bot = VictBot()
check_group = app_commands.Group(name="check", description="Check Vict's operational status")


@check_group.command(name="status", description="Show Vict status, RAM, and memory stats")
async def check_status(interaction: discord.Interaction):
    """Public status command showing AI status, RAM usage, context size, queue count, short-term memory count, and persistent memory size."""
    if not brain.is_ready():
        ai_status = "Offline (Model not loaded)"
    elif is_generating:
        ai_status = "Generating"
    else:
        ai_status = "Ready"

    ram_str = get_ram_usage_str()
    waiting_queue_count = generation_queue.qsize()
    st_count = memory_mgr.get_short_term_count()
    pm_size = memory_mgr.get_persistent_memory_size()

    status_text = (
        f"**Vict Status**\n"
        f"• AI/Model: {ai_status}\n"
        f"• RAM Usage: {ram_str}\n"
        f"• Context Size: {config.N_CTX}\n"
        f"• Queue Waiting: {waiting_queue_count}\n"
        f"• Short-term Memory: {st_count}/49 messages\n"
        f"• Persistent Memory Size: {pm_size} characters\n"
        f"• Configured Limits: MAX_INPUT_CHARS={config.MAX_INPUT_CHARS}, MAX_MEMORY_TOKENS={config.MAX_MEMORY_TOKENS}"
    )

    await interaction.response.send_message(status_text, ephemeral=False)


bot.tree.add_command(check_group)


@bot.tree.command(name="talk", description="Talk to Vict")
@app_commands.describe(input="Your message to Vict")
async def talk(interaction: discord.Interaction, input: str):
    """Main interaction command for Vict."""
    username = interaction.user.name
    user_id = str(interaction.user.id)

    await process_chat_response(
        destination=interaction,
        user_id=user_id,
        username=username,
        display_input=input,
        semantic_input=input,
        source_type="talk",
    )


async def process_chat_response(
    destination,
    user_id: str,
    username: str,
    display_input: str,
    semantic_input: str,
    source_type: str = "chat",
):
    """
    Validates input, sends initial Discord message header, and enqueues request into global FIFO queue.
    """
    ensure_queue_worker_running()

    # Enforce MAX_INPUT_CHARS on semantic input
    effective_input = semantic_input if semantic_input else display_input
    if len(effective_input) > config.MAX_INPUT_CHARS:
        err_msg = f"max chars exceeded.\nmaximum allowed: {config.MAX_INPUT_CHARS} characters."
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(err_msg, ephemeral=False)
        else:
            await destination.send(err_msg)
        return

    clean_display = normalize_text(display_input)
    clean_semantic = normalize_text(semantic_input) if semantic_input else clean_display

    header = f"@{username.lstrip('@')}: {clean_display}\n\n`"
    initial_text = f"{header}...`"

    if isinstance(destination, discord.Interaction):
        await destination.response.send_message(initial_text, ephemeral=False)
        message = await destination.original_response()
    else:
        message = await destination.send(initial_text)

    item = QueueItem(
        user_id=user_id,
        username=username,
        clean_display=clean_display,
        clean_semantic=clean_semantic,
        message=message,
        source_type=source_type,
    )

    await generation_queue.put(item)


@bot.event
async def on_ready():
    ensure_queue_worker_running()
    logger.info("========================================")
    logger.info(f"Vict connected as @{bot.user} (ID: {bot.user.id})")
    logger.info(f"Model path: {config.MODEL_PATH}")
    logger.info(f"Model ready: {brain.is_ready()}")
    logger.info("Startup complete. Vict is running!")
    logger.info("========================================")


def main():
    if not config.DISCORD_TOKEN or config.DISCORD_TOKEN == "your_discord_bot_token_here":
        logger.error("Invalid or missing DISCORD_TOKEN in .env. Please configure a valid token.")
        sys.exit(1)

    bot.run(config.DISCORD_TOKEN)


if __name__ == "__main__":
    main()
