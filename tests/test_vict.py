import os
import pytest
from pathlib import Path

import config
from brain import Brain, normalize_text
from memory import MemoryManager


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


def test_short_term_memory_limit(temp_memory_file):
    mgr = MemoryManager(memory_file_path=temp_memory_file)

    for i in range(1, 50):
        consolidate_triggered = mgr.add_message(
            user_id=123, username="testuser", content=f"Message {i}", role="user"
        )
        assert consolidate_triggered is False
        assert mgr.get_short_term_count() == i

    # Short-term context should contain at most 49 items
    ctx = mgr.get_short_term_context()
    assert len(ctx) == 49

    # Adding 50th message should trigger consolidation signal (True)
    trigger = mgr.add_message(
        user_id="vict", username="Vict", content="Message 50", role="assistant"
    )
    assert trigger is True
    assert mgr.get_short_term_count() == 50


def test_persistent_memory_atomic_save(temp_memory_file):
    mgr = MemoryManager(memory_file_path=temp_memory_file)
    assert mgr.get_persistent_memory() == "Existing persistent memory item."

    new_memory = "Updated persistent memory with new user facts."
    success = mgr.save_persistent_memory(new_memory)

    assert success is True
    assert mgr.get_persistent_memory() == new_memory
    assert temp_memory_file.read_text(encoding="utf-8") == new_memory


def test_short_term_batch_reset(temp_memory_file):
    mgr = MemoryManager(memory_file_path=temp_memory_file)
    mgr.add_message(user_id=101, username="alice", content="Hi")
    assert mgr.get_short_term_count() == 1

    mgr.reset_short_term_batch()
    assert mgr.get_short_term_count() == 0


def test_prompt_construction():
    brain = Brain(model_path="nonexistent.gguf")
    persona = "You are Vict, a goofy bot."
    persistent_mem = "User likes pizza."
    short_term_ctx = [
        {"user_id": "100", "username": "bob", "content": "Hello Vict", "role": "user"},
        {"user_id": "vict", "username": "Vict", "content": "Hey Bob!", "role": "assistant"},
    ]

    prompt = brain.build_talk_prompt(
        persona=persona,
        persistent_memory=persistent_mem,
        short_term_context=short_term_ctx,
        current_username="bob",
        current_user_input="How are you?",
    )

    assert "[SYSTEM]" in prompt
    assert persona in prompt
    assert "[PERSISTENT MEMORY]" in prompt
    assert "User likes pizza." in prompt
    assert "[RECENT CONVERSATION]" in prompt
    assert "@bob: Hello Vict" in prompt
    assert "Vict: Hey Bob!" in prompt
    assert "[CURRENT USER MESSAGE]" in prompt
    assert "@bob: How are you?" in prompt
    assert "Never use newline characters" in prompt


def test_brain_unloaded_model_fallback():
    brain = Brain(model_path="nonexistent.gguf")
    assert brain.is_ready() is False

    stream_output = list(
        brain.generate_talk_stream(
            persona="test",
            persistent_memory="test",
            short_term_context=[],
            current_username="alice",
            current_user_input="hello",
        )
    )
    assert stream_output == ["Local AI model is not loaded or unavailable."]

    consolidated = brain.consolidate_memory("Old memory", [])
    assert consolidated == "Old memory"


def test_max_input_chars_configuration():
    assert config.MAX_INPUT_CHARS == 150
    assert config.MAX_MEMORY_TOKENS == 5000
    assert config.TARGET_MEMORY_TOKENS == 4000
