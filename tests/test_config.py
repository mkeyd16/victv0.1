import pytest
from unittest.mock import patch, MagicMock

import config
from brain import Brain, get_ggml_type
import bot as bot_module


def test_config_ram_defaults():
    assert config.N_CTX == 4096
    assert config.N_BATCH == 128
    assert config.N_UBATCH == 128
    assert config.N_THREADS == 4
    assert config.USE_MMAP is True
    assert config.USE_MLOCK is False
    assert config.CACHE_TYPE_K == "f16"
    assert config.CACHE_TYPE_V == "f16"
    assert config.MAX_INPUT_CHARS == 200


def test_parse_bool():
    assert config.parse_bool("true", False) is True
    assert config.parse_bool("1", False) is True
    assert config.parse_bool("yes", False) is True
    assert config.parse_bool("false", True) is False
    assert config.parse_bool("0", True) is False
    assert config.parse_bool("no", True) is False
    assert config.parse_bool(None, True) is True


def test_get_ggml_type():
    assert get_ggml_type("f16") == 1
    assert get_ggml_type("f32") == 0
    assert get_ggml_type("q8_0") == 8
    assert get_ggml_type("q4_0") == 2


def test_brain_initializes_with_low_memory_config(tmp_path):
    fake_model = tmp_path / "fake.gguf"
    fake_model.write_text("dummy gguf content", encoding="utf-8")

    with patch("brain.Llama") as mock_llama_class:
        brain = Brain(model_path=str(fake_model))

        mock_llama_class.assert_called_once_with(
            model_path=str(fake_model),
            n_ctx=config.N_CTX,
            n_batch=config.N_BATCH,
            n_ubatch=config.N_UBATCH,
            n_threads=config.N_THREADS,
            use_mmap=config.USE_MMAP,
            use_mlock=config.USE_MLOCK,
            type_k=1,
            type_v=1,
            verbose=False,
        )


def test_get_ram_usage_str_mb():
    mock_process = MagicMock()
    mock_process.memory_info.return_value = MagicMock(rss=778051584)  # 742 MB

    with patch("psutil.Process", return_value=mock_process):
        ram_str = bot_module.get_ram_usage_str()
        assert ram_str == "742 MB"


def test_get_ram_usage_str_gb():
    mock_process = MagicMock()
    mock_process.memory_info.return_value = MagicMock(rss=1342177280)  # 1.25 GB

    with patch("psutil.Process", return_value=mock_process):
        ram_str = bot_module.get_ram_usage_str()
        assert ram_str == "1.25 GB"


def test_get_ram_usage_str_failure_returns_unavailable():
    with patch("psutil.Process", side_effect=RuntimeError("psutil error")):
        ram_str = bot_module.get_ram_usage_str()
        assert ram_str == "Unavailable"
