import asyncio
import logging
import sys
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


class VictBot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # Enable Message Content intent for listening to ordinary messages
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        """Called when the bot is setting up. Registers app commands."""
        logger.info("Registering Discord slash commands...")
        await self.tree.sync()
        logger.info("Slash commands synced successfully.")

    async def on_message(self, message: discord.Message):
        """Handles incoming messages for strict 'hey vict' start triggers."""
        # Ignore all bot messages (including Vict's own messages and Yggdrasil)
        if message.author.bot:
            return

        # Ordinary user message check for start-of-message 'hey vict'
        if has_hey_vict_trigger(message.content):
            # Use real Discord username/handle as identity, Discord user ID as stable key
            username = message.author.name  # username/handle, not nickname/display name
            user_id = str(message.author.id)
            semantic_input = extract_trigger_input(message.content)

            await process_chat_response(
                destination=message.channel,
                user_id=user_id,
                username=username,
                display_input=message.content,
                semantic_input=semantic_input,
            )


bot = VictBot()
check_group = app_commands.Group(name="check", description="Check Vict's operational status")


@check_group.command(name="status", description="Show Vict status and memory stats")
async def check_status(interaction: discord.Interaction):
    """Public status command showing AI, short-term memory count, persistent memory size, and configured limits."""
    ai_status = "Online (Model loaded)" if brain.is_ready() else "Offline (Model not loaded)"
    st_count = memory_mgr.get_short_term_count()
    pm_size = memory_mgr.get_persistent_memory_size()

    status_text = (
        f"**Vict Status**\n"
        f"• AI/Model: {ai_status}\n"
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
    )


async def process_chat_response(
    destination,
    user_id: str,
    username: str,
    display_input: str,
    semantic_input: str,
):
    """
    Validates input, sends formatted header, streams AI generation, and saves into short-term/persistent memory.
    destination can be a discord.Interaction or a discord.abc.Messageable (TextChannel, Thread, etc.).
    """
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

    persona = config.load_persona()
    persistent_mem = memory_mgr.get_persistent_memory()
    short_term_ctx = memory_mgr.get_short_term_context()

    last_edit_time = 0.0
    MIN_EDIT_INTERVAL = 0.8
    latest_response_text = "..."
    final_generated_text = ""

    loop = asyncio.get_running_loop()

    def fetch_stream_tokens():
        return brain.generate_talk_stream(
            persona=persona,
            persistent_memory=persistent_mem,
            short_term_context=short_term_ctx,
            current_username=username,
            current_user_input=clean_semantic,
        )

    try:
        token_stream = await loop.run_in_executor(None, fetch_stream_tokens)

        while True:
            chunk = await loop.run_in_executor(None, lambda: next(token_stream, None))
            if chunk is None:
                break

            latest_response_text = chunk
            final_generated_text = chunk

            now = loop.time()
            if now - last_edit_time >= MIN_EDIT_INTERVAL:
                updated_content = f"@{username.lstrip('@')}: {clean_display}\n\n`{latest_response_text}`"
                try:
                    await message.edit(content=updated_content)
                    last_edit_time = now
                except discord.HTTPException as e:
                    logger.error(f"Discord API edit error: {e}")

    except Exception as e:
        logger.error(f"Error during Vict reply processing: {e}")
        if not final_generated_text:
            final_generated_text = "Sorry, I ran into an error generating a reply."

    final_content = f"@{username.lstrip('@')}: {clean_display}\n\n`{final_generated_text}`"
    try:
        await message.edit(content=final_content)
    except discord.HTTPException as e:
        logger.error(f"Final message edit failed: {e}")

    # Record user message and Vict response into memory
    u_trig = memory_mgr.add_message(
        user_id=user_id, username=username, content=clean_display, role="user"
    )
    v_trig = memory_mgr.add_message(
        user_id="vict", username="Vict", content=final_generated_text, role="assistant"
    )

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


@bot.event
async def on_ready():
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
