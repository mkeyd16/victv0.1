import os
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
from pathlib import Path

import config
from brain import Brain, normalize_text
from memory import MemoryManager
from parser import (
    has_hey_vict_trigger,
    extract_trigger_input,
    is_yggdrasil_message,
    parse_yggdrasil_transcript,
    resolve_yggdrasil_user,
)
import bot as bot_module


@pytest.fixture
def temp_memory_file(tmp_path):
    mem_file = tmp_path / "memory.txt"
    mem_file.write_text("Existing persistent memory item.", encoding="utf-8")
    return mem_file


def test_text_normalization():
    raw = "Hello\r\nworld!\n  This is   `Vict`.  "
    normalized = normalize_text(raw)
    assert normalized == "Hello world! This is Vict."
    assert "\n" not in normalized
    assert "`" not in normalized


def test_trigger_detection_and_extraction():
    # Case insensitive trigger matching
    assert has_hey_vict_trigger("hey vict") is True
    assert has_hey_vict_trigger("HEY VICT") is True
    assert has_hey_vict_trigger("Hey Vict") is True
    assert has_hey_vict_trigger("hey vict, what color is the sky?") is True
    assert has_hey_vict_trigger("yo hey vict what is happening") is True

    # Near matches should fail
    assert has_hey_vict_trigger("heyy vict") is False
    assert has_hey_vict_trigger("heyvict") is False
    assert has_hey_vict_trigger("hey victory") is False

    # Trigger extraction
    assert extract_trigger_input("hey vict, what color is the sky?") == "what color is the sky?"
    assert extract_trigger_input("hey vict") == ""
    assert extract_trigger_input("hey vict!") == ""
    assert extract_trigger_input("yo hey vict whats up") == "yo whats up"


def test_yggdrasil_parsing_and_speakers():
    sample_ygg = (
        "### YggdrasilAPP5:18 PM\n"
        "**nastyboy000** [:userphone:](https://cdn.discordapp.com/emojis/1311268018625576971.webp?size=56) lmao\n"
        "**mike** yo i gotta dip\n"
        "**nastyboy000** [:userphone:](...) bye"
    )

    assert is_yggdrasil_message(sample_ygg) is True

    parsed = parse_yggdrasil_transcript(sample_ygg)
    assert len(parsed) == 3
    assert parsed[0]["username"] == "nastyboy000"
    assert parsed[0]["text"] == "lmao"
    assert parsed[1]["username"] == "mike"
    assert parsed[1]["text"] == "yo i gotta dip"
    assert parsed[2]["username"] == "nastyboy000"
    assert parsed[2]["text"] == "bye"


def test_yggdrasil_user_resolution():
    class MockMember:
        def __init__(self, user_id, name):
            self.id = user_id
            self.name = name

    class MockGuild:
        def __init__(self, members):
            self.members = members

    guild = MockGuild([MockMember(12345, "nastyboy000")])

    # Resolved user
    uid, uname = resolve_yggdrasil_user(guild, "nastyboy000")
    assert uid == "12345"
    assert uname == "nastyboy000"

    # Unresolved user
    uid_unres, uname_unres = resolve_yggdrasil_user(guild, "unknown_person")
    assert uid_unres == "unresolved:unknown_person"
    assert uname_unres == "unknown_person"


def test_short_term_memory_and_50th_consolidation(temp_memory_file):
    mgr = MemoryManager(memory_file_path=temp_memory_file)

    for i in range(1, 50):
        trig = mgr.add_message(user_id=100 + i, username=f"user{i}", content=f"msg {i}", role="user")
        assert trig is False
        assert mgr.get_short_term_count() == i

    ctx = mgr.get_short_term_context()
    assert len(ctx) == 49

    # 50th message
    trig_50 = mgr.add_message(user_id="vict", username="Vict", content="msg 50", role="assistant")
    assert trig_50 is True
    assert mgr.get_short_term_count() == 50

    # Verify 50th message is preserved in full batch prior to reset
    full_batch = mgr.get_full_batch()
    assert len(full_batch) == 50
    assert full_batch[-1]["content"] == "msg 50"

    # Atomic save & reset
    mgr.save_persistent_memory("Consolidated persistent memory")
    mgr.reset_short_term_batch()
    assert mgr.get_short_term_count() == 0
    assert mgr.get_persistent_memory() == "Consolidated persistent memory"


def test_prompt_construction_multiple_speakers():
    brain = Brain(model_path="nonexistent.gguf")
    short_term_ctx = [
        {"user_id": "1", "username": "nastyboy000", "content": "lmao", "role": "user"},
        {"user_id": "2", "username": "mike", "content": "yo i gotta dip", "role": "user"},
        {"user_id": "1", "username": "nastyboy000", "content": "bye", "role": "user"},
    ]

    prompt = brain.build_talk_prompt(
        persona="Vict persona",
        persistent_memory="Persistent mem",
        short_term_context=short_term_ctx,
        current_username="nastyboy000",
        current_user_input="what color is the sky?",
    )

    assert "[SYSTEM]" in prompt
    assert "[PERSISTENT MEMORY]" in prompt
    assert "[RECENT CONVERSATION]" in prompt
    assert "@nastyboy000: lmao" in prompt
    assert "@mike: yo i gotta dip" in prompt
    assert "@nastyboy000: bye" in prompt
    assert "[CURRENT USER MESSAGE]" in prompt
    assert "@nastyboy000: what color is the sky?" in prompt


@pytest.mark.asyncio
async def test_bot_ignores_self():
    bot_instance = bot_module.VictBot()
    bot_user = MagicMock(id=999)

    msg = MagicMock()
    msg.author = bot_user
    msg.author.id = 999
    msg.content = "hey vict, what are you doing?"

    with patch.object(bot_module.VictBot, "user", new_callable=PropertyMock, return_value=bot_user):
        with patch("bot.process_chat_response", new_callable=AsyncMock) as mock_process:
            await bot_instance.on_message(msg)
            mock_process.assert_not_called()


@pytest.mark.asyncio
async def test_bot_ignores_unrelated_bots():
    bot_instance = bot_module.VictBot()
    bot_user = MagicMock(id=999)

    author = MagicMock()
    author.id = 555
    author.name = "MEE6"
    author.bot = True

    msg = MagicMock()
    msg.author = author
    msg.content = "hey vict, say something"
    msg.guild = None

    with patch.object(bot_module.VictBot, "user", new_callable=PropertyMock, return_value=bot_user):
        with patch("bot.process_chat_response", new_callable=AsyncMock) as mock_process:
            await bot_instance.on_message(msg)
            mock_process.assert_not_called()


@pytest.mark.asyncio
async def test_bot_processes_ordinary_hey_vict():
    bot_instance = bot_module.VictBot()
    bot_user = MagicMock(id=999)

    author = MagicMock()
    author.id = 888
    author.name = "nastyboy000"
    author.display_name = "Some Nickname"
    author.bot = False

    msg = MagicMock()
    msg.author = author
    msg.content = "hey vict, what color is the sky?"
    msg.guild = None

    with patch.object(bot_module.VictBot, "user", new_callable=PropertyMock, return_value=bot_user):
        with patch("bot.process_chat_response", new_callable=AsyncMock) as mock_process:
            await bot_instance.on_message(msg)
            mock_process.assert_called_once()
            args, kwargs = mock_process.call_args
            assert kwargs["user_id"] == "888"
            assert kwargs["username"] == "nastyboy000"  # Username handle used, not display name
            assert kwargs["display_input"] == "hey vict, what color is the sky?"
            assert kwargs["semantic_input"] == "what color is the sky?"


@pytest.mark.asyncio
async def test_bot_processes_yggdrasil_hey_vict():
    bot_instance = bot_module.VictBot()
    bot_user = MagicMock(id=999)

    author = MagicMock()
    author.id = 777
    author.name = "YggdrasilAPP"
    author.bot = True

    msg = MagicMock()
    msg.author = author
    msg.content = (
        "### YggdrasilAPP5:18 PM\n"
        "**nastyboy000** [:userphone:](https://...) lmao\n"
        "**mike** yo i gotta dip\n"
        "**nastyboy000** [:userphone:](...) hey vict, what color is the sky?"
    )
    msg.guild = None

    with patch.object(bot_module.VictBot, "user", new_callable=PropertyMock, return_value=bot_user):
        with patch("bot.process_chat_response", new_callable=AsyncMock) as mock_process:
            await bot_instance.on_message(msg)
            mock_process.assert_called_once()
            args, kwargs = mock_process.call_args
            assert kwargs["username"] == "nastyboy000"  # Speaker extracted from Yggdrasil, NOT YggdrasilAPP
            assert kwargs["display_input"] == "hey vict, what color is the sky?"
            assert kwargs["semantic_input"] == "what color is the sky?"


@pytest.mark.asyncio
async def test_max_input_chars_exceeded():
    destination = MagicMock()
    destination.send = AsyncMock()

    long_input = "a" * (config.MAX_INPUT_CHARS + 10)

    await bot_module.process_chat_response(
        destination=destination,
        user_id="123",
        username="alice",
        display_input=f"hey vict, {long_input}",
        semantic_input=long_input,
    )

    destination.send.assert_called_once_with(
        f"max chars exceeded.\nmaximum allowed: {config.MAX_INPUT_CHARS} characters."
    )
