import pytest
from parser import (
    has_hey_vict_trigger,
    extract_trigger_input,
    is_yggdrasil_message,
    parse_yggdrasil_transcript,
    resolve_yggdrasil_user,
)


def test_has_hey_vict_trigger():
    assert has_hey_vict_trigger("hey vict") is True
    assert has_hey_vict_trigger("HEY VICT") is True
    assert has_hey_vict_trigger("Hey Vict") is True
    assert has_hey_vict_trigger("hey vict, what are you doing?") is True
    assert has_hey_vict_trigger("yo hey vict what the fuck is happening") is True

    # Should NOT trigger
    assert has_hey_vict_trigger("heyy vict") is False
    assert has_hey_vict_trigger("heyvict") is False
    assert has_hey_vict_trigger("hey victory") is False


def test_extract_trigger_input():
    assert extract_trigger_input("hey vict, what are you doing?") == "what are you doing?"
    assert extract_trigger_input("yo hey vict what the fuck is happening") == "yo what the fuck is happening"
    assert extract_trigger_input("hey vict") == ""
    assert extract_trigger_input("hey vict!") == ""


def test_is_yggdrasil_message():
    sample_ygg = (
        "### YggdrasilAPP5:18 PM\n"
        "**nastyboy000** [:userphone:](https://cdn.discordapp.com/emojis/1311268018625576971.webp?size=56) wht project"
    )
    assert is_yggdrasil_message(sample_ygg) is True

    normal_bold = "**Look at this** cool thing"
    assert is_yggdrasil_message(normal_bold, author_is_bot=False) is False


def test_parse_yggdrasil_transcript():
    sample_multi = (
        "### YggdrasilAPP5:18 PM\n"
        "**nastyboy000** [:userphone:](https://...) lmao\n"
        "**mike** yo i gotta dip\n"
        "**nastyboy000** [:userphone:](...) bye"
    )
    entries = parse_yggdrasil_transcript(sample_multi)
    assert len(entries) == 3
    assert entries[0] == {"username": "nastyboy000", "text": "lmao"}
    assert entries[1] == {"username": "mike", "text": "yo i gotta dip"}
    assert entries[2] == {"username": "nastyboy000", "text": "bye"}


class MockMember:
    def __init__(self, user_id, name):
        self.id = user_id
        self.name = name


class MockGuild:
    def __init__(self, members):
        self.members = members


def test_resolve_yggdrasil_user():
    guild = MockGuild([MockMember(999, "nastyboy000")])
    uid, uname = resolve_yggdrasil_user(guild, "nastyboy000")
    assert uid == "999"
    assert uname == "nastyboy000"

    uid_unres, uname_unres = resolve_yggdrasil_user(guild, "unknown_user")
    assert uid_unres == "unresolved:unknown_user"
    assert uname_unres == "unknown_user"
