import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import bot as bot_module
import config


@pytest.fixture(autouse=True)
def reset_bot_queue_state():
    """Resets the bot queue state before and after each test on the current event loop."""
    bot_module.generation_queue = asyncio.Queue()
    bot_module.is_generating = False
    if bot_module.queue_worker_task and not bot_module.queue_worker_task.done():
        bot_module.queue_worker_task.cancel()
    bot_module.queue_worker_task = None
    yield
    bot_module.is_generating = False
    if bot_module.queue_worker_task and not bot_module.queue_worker_task.done():
        bot_module.queue_worker_task.cancel()
    bot_module.queue_worker_task = None


@pytest.mark.asyncio
async def test_queue_fifo_order_and_concurrency():
    """Tests that requests are processed strictly in FIFO order (A -> B -> C) and only one runs concurrently."""
    processed_order = []
    active_generators_count = 0
    max_concurrent_generators = 0

    async def mock_process_queue_item(item):
        nonlocal active_generators_count, max_concurrent_generators
        active_generators_count += 1
        if active_generators_count > max_concurrent_generators:
            max_concurrent_generators = active_generators_count

        processed_order.append(item.user_id)
        await asyncio.sleep(0.05)  # Simulate generation delay

        active_generators_count -= 1

    mock_msg_a = MagicMock(edit=AsyncMock())
    dest_a = MagicMock(send=AsyncMock(return_value=mock_msg_a))

    mock_msg_b = MagicMock(edit=AsyncMock())
    dest_b = MagicMock(send=AsyncMock(return_value=mock_msg_b))

    mock_msg_c = MagicMock(edit=AsyncMock())
    dest_c = MagicMock(send=AsyncMock(return_value=mock_msg_c))

    with patch("bot.process_queue_item", side_effect=mock_process_queue_item):
        # Enqueue User A
        await bot_module.process_chat_response(
            destination=dest_a, user_id="user_A", username="Alice", display_input="hey vict msg A", semantic_input="msg A"
        )
        # Enqueue User B
        await bot_module.process_chat_response(
            destination=dest_b, user_id="user_B", username="Bob", display_input="hey vict msg B", semantic_input="msg B"
        )
        # Enqueue User C
        await bot_module.process_chat_response(
            destination=dest_c, user_id="user_C", username="Charlie", display_input="hey vict msg C", semantic_input="msg C"
        )

        # Wait for all queued tasks to finish
        await bot_module.generation_queue.join()

    # FIFO Order Check
    assert processed_order == ["user_A", "user_B", "user_C"]
    # Single concurrent generation check
    assert max_concurrent_generators == 1


@pytest.mark.asyncio
async def test_talk_and_hey_vict_share_same_queue():
    """Tests that both /talk and 'hey vict' add requests to the same global queue in arrival order."""
    processed_sources = []

    async def mock_process_queue_item(item):
        processed_sources.append(item.source_type)
        await asyncio.sleep(0.02)

    dest_1 = MagicMock(send=AsyncMock(return_value=MagicMock(edit=AsyncMock())))

    dest_2 = MagicMock(spec=bot_module.discord.Interaction)
    dest_2.response = MagicMock(send_message=AsyncMock())
    dest_2.original_response = AsyncMock(return_value=MagicMock(edit=AsyncMock()))

    with patch("bot.process_queue_item", side_effect=mock_process_queue_item):
        # 1. hey vict interaction
        await bot_module.process_chat_response(
            destination=dest_1, user_id="1", username="Alice", display_input="hey vict hi", semantic_input="hi", source_type="hey_vict"
        )
        # 2. /talk slash command
        await bot_module.process_chat_response(
            destination=dest_2, user_id="2", username="Bob", display_input="hello", semantic_input="hello", source_type="talk"
        )

        await bot_module.generation_queue.join()

    assert processed_sources == ["hey_vict", "talk"]


@pytest.mark.asyncio
async def test_failed_request_does_not_stop_queue():
    """Tests that a failure during one request does not crash the worker or stop subsequent requests."""
    processed_items = []

    async def mock_process_queue_item(item):
        if item.user_id == "user_fail":
            processed_items.append("user_fail")
            raise ValueError("Simulated model error")
        processed_items.append(item.user_id)

    dest_1 = MagicMock(send=AsyncMock(return_value=MagicMock(edit=AsyncMock())))
    dest_2 = MagicMock(send=AsyncMock(return_value=MagicMock(edit=AsyncMock())))

    with patch("bot.process_queue_item", side_effect=mock_process_queue_item):
        await bot_module.process_chat_response(
            destination=dest_1, user_id="user_fail", username="FailUser", display_input="hey vict fail", semantic_input="fail"
        )
        await bot_module.process_chat_response(
            destination=dest_2, user_id="user_pass", username="PassUser", display_input="hey vict pass", semantic_input="pass"
        )

        await bot_module.generation_queue.join()

    assert processed_items == ["user_fail", "user_pass"]


@pytest.mark.asyncio
async def test_queued_items_retain_correct_context():
    """Tests that queued items retain their specific user_id, username, display_input, semantic_input, and message."""
    captured_items = []

    async def mock_process_queue_item(item):
        captured_items.append(item)

    mock_msg = MagicMock(edit=AsyncMock())
    dest = MagicMock(send=AsyncMock(return_value=mock_msg))

    with patch("bot.process_queue_item", side_effect=mock_process_queue_item):
        await bot_module.process_chat_response(
            destination=dest, user_id="999", username="nastyboy000", display_input="hey vict, what is 2+2?", semantic_input="what is 2+2?"
        )
        await bot_module.generation_queue.join()

    assert len(captured_items) == 1
    item = captured_items[0]
    assert item.user_id == "999"
    assert item.username == "nastyboy000"
    assert item.clean_display == "hey vict, what is 2+2?"
    assert item.clean_semantic == "what is 2+2?"
    assert item.message == mock_msg


@pytest.mark.asyncio
async def test_queue_status_reporting():
    """Tests that /check status correctly reports AI status and waiting queue count."""
    interaction = MagicMock(spec=bot_module.discord.Interaction)
    interaction.response = MagicMock(send_message=AsyncMock())

    # Case 1: Idle
    bot_module.is_generating = False
    with patch.object(bot_module.brain, "is_ready", return_value=True):
        await bot_module.check_status.callback(interaction)
        args, kwargs = interaction.response.send_message.call_args
        status_text = args[0]
        assert "• AI/Model: Ready" in status_text
        assert "• Queue Waiting: 0" in status_text

    # Case 2: Generating with items in queue
    bot_module.is_generating = True
    # Add 2 items to waiting queue
    dummy_item = bot_module.QueueItem("1", "user", "input", "input", MagicMock())
    await bot_module.generation_queue.put(dummy_item)
    await bot_module.generation_queue.put(dummy_item)

    interaction.response.send_message.reset_mock()
    with patch.object(bot_module.brain, "is_ready", return_value=True):
        await bot_module.check_status.callback(interaction)
        args, kwargs = interaction.response.send_message.call_args
        status_text = args[0]
        assert "• AI/Model: Generating" in status_text
        assert "• Queue Waiting: 2" in status_text


def test_model_instance_not_duplicated():
    """Ensures Brain is a single instance in bot module."""
    assert bot_module.brain is not None
    assert isinstance(bot_module.brain, bot_module.Brain)
