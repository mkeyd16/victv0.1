import pytest
from parser import has_hey_vict_trigger, extract_trigger_input


def test_strict_has_hey_vict_trigger():
    # Valid triggers (must start with 'hey vict', case-insensitive, optional leading whitespace)
    assert has_hey_vict_trigger("hey vict") is True
    assert has_hey_vict_trigger("HEY VICT") is True
    assert has_hey_vict_trigger("Hey Vict, hello") is True
    assert has_hey_vict_trigger("   hey vict, what color is the sky?") is True
    assert has_hey_vict_trigger("\they vict what is 2+2?") is True

    # Invalid triggers (trigger not at start, or invalid word boundaries)
    assert has_hey_vict_trigger("yo hey vict") is False
    assert has_hey_vict_trigger("well hey vict") is False
    assert has_hey_vict_trigger("something hey vict") is False
    assert has_hey_vict_trigger("heyy vict") is False
    assert has_hey_vict_trigger("heyvict") is False
    assert has_hey_vict_trigger("hey victory") is False


def test_extract_trigger_input():
    assert extract_trigger_input("hey vict, what are you doing?") == "what are you doing?"
    assert extract_trigger_input("HEY VICT what is 2+2?") == "what is 2+2?"
    assert extract_trigger_input("hey vict") == ""
    assert extract_trigger_input("hey vict!") == ""
    assert extract_trigger_input("  hey vict: how are you?") == "how are you?"
