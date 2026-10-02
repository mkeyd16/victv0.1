import asyncio
import logging
import sys
import discord
from discord import app_commands
from discord.ext import commands

import config
from brain import Brain, normalize_text
from memory import MemoryManager

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
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        """Called when the bot is setting up. Registers app commands."""
        logger.info("Registering Discord slash commands...")
        # Sync slash commands with Discord
        await self.tree.sync()
        logger.info("Slash commands synced successfully.")


bot = VictBot()
check_group = app_commands.Group(name="check", description="Check Vict's operational status")


@check_group.command(name="status", description="Show Vict status and memory stats")
async def check_status(interaction: discord.Interaction):
    """Public status command showing AI, short-term memory count, and persistent memory size."""
    ai_status = "Online (Model loaded)" if brain.is_ready() else "Offline (Model not loaded)"
    st_count = memory_mgr.get_short_term_count()
    pm_size = memory_mgr.get_persistent_memory_size()

    status_text = (
        f"**Vict Status**\n"
        f"• AI/Model: {ai_status}\n"
        f"• Short-term Memory: {st_count}/49 messages\n"
        f"• Persistent Memory Size: {pm_size} characters"
    )

    await interaction.response.send_message(status_text, ephemeral=False)


bot.tree.add_command(check_group)


@bot.tree.command(name="talk", description="Talk to Vict")
@app_commands.describe(input="Your message to Vict")
async def talk(interaction: discord.Interaction, input: str):
    """Main interaction command for Vict."""
    # 1. Validate input character count against MAX_INPUT_CHARS
    if len(input) > config.MAX_INPUT_CHARS:
        await interaction.response.send_message(
            f"max chars exceeded.\nmaximum allowed: {config.MAX_INPUT_CHARS} characters.",
            ephemeral=False,
        )
        return

    # User handle/identity handling
    username = interaction.user.name  # @username/handle without nickname
    user_id = interaction.user.id  # Stable numeric user ID

    # Clean and normalize input string for layout safety
    normalized_input = normalize_text(input)

    # 2. Defer or initial response
    # Format message header
    header = f"@{username}: {normalized_input}\n\n`"
    initial_text = f"{header}...`"

    await interaction.response.send_message(initial_text, ephemeral=False)
    message = await interaction.original_response()

    # Load persona and persistent memory
    persona = config.load_persona()
    persistent_mem = memory_mgr.get_persistent_memory()
    short_term_ctx = memory_mgr.get_short_term_context()

    # Rate limited edit queue parameters
    last_edit_time = 0.0
    MIN_EDIT_INTERVAL = 0.8  # Edit at most every 0.8s to respect Discord rate limits
    latest_response_text = "..."

    final_generated_text = ""

    # Stream generation in background loop
    loop = asyncio.get_running_loop()

    # Helper function to run sync generator in threadpool
    def sync_generator():
        return list(
            brain.generate_talk_stream(
                persona=persona,
                persistent_memory=persistent_mem,
                short_term_context=short_term_ctx,
                current_username=username,
                current_user_input=normalized_input,
            )
        )

    # We run the generator yielding steps
    # To provide visible streaming, we process stream tokens in a thread executor
    def fetch_stream_tokens():
        return brain.generate_talk_stream(
            persona=persona,
            persistent_memory=persistent_mem,
            short_term_context=short_term_ctx,
            current_username=username,
            current_user_input=normalized_input,
        )

    try:
        # Obtain generator
        token_stream = await loop.run_in_executor(None, fetch_stream_tokens)

        # Iterate over streamed partials safely
        while True:
            # Get next chunk in executor to not block event loop
            chunk = await loop.run_in_executor(None, lambda: next(token_stream, None))
            if chunk is None:
                break

            latest_response_text = chunk
            final_generated_text = chunk

            now = loop.time()
            if now - last_edit_time >= MIN_EDIT_INTERVAL:
                updated_content = f"@{username}: {normalized_input}\n\n`{latest_response_text}`"
                try:
                    await message.edit(content=updated_content)
                    last_edit_time = now
                except discord.HTTPException as e:
                    logger.error(f"Discord API edit error: {e}")

    except Exception as e:
        logger.error(f"Error during Vict reply processing: {e}")
        if not final_generated_text:
            final_generated_text = "Sorry, I ran into an error generating a reply."

    # Final edit ensuring full response is displayed with proper backticks
    final_content = f"@{username}: {normalized_input}\n\n`{final_generated_text}`"
    try:
        await message.edit(content=final_content)
    except discord.HTTPException as e:
        logger.error(f"Final message edit failed: {e}")

    # Record messages into short-term buffer
    # 1) User message
    user_trigger_consolidate = memory_mgr.add_message(
        user_id=user_id, username=username, content=normalized_input, role="user"
    )
    # 2) Vict response
    vict_trigger_consolidate = memory_mgr.add_message(
        user_id="vict", username="Vict", content=final_generated_text, role="assistant"
    )

    # Check if 50 messages threshold reached
    if user_trigger_consolidate or vict_trigger_consolidate:
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
