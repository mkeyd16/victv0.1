import re
from typing import List, Dict, Optional, Tuple, Any

# Case-insensitive trigger match with word boundaries
TRIGGER_REGEX = re.compile(r"\bhey\s+vict\b", re.IGNORECASE)

# Yggdrasil speaker line regex
# Matches: [1.] **username** [:emoji:](http...) message
YGG_SPEAKER_REGEX = re.compile(
    r"^\s*(?:\d+\.\s*)?\*\*(?P<username>[^\*\n]+)\*\*\s*(?:\[:(?P<emoji>[^\]]+):\]\((?P<emoji_url>[^\)]+)\))?\s*(?P<text>.*)$"
)

# Heading regex (e.g. ### YggdrasilAPP5:18 PM or ### Yggdrasil...)
YGG_HEADING_REGEX = re.compile(r"^\s*#{1,6}\s+.*$")

# Emoji pattern check
YGG_EMOJI_PATTERN = re.compile(r"\[:[^\]]+:\]\([^\)]+\)")


def has_hey_vict_trigger(text: str) -> bool:
    """Checks if the text contains the 'hey vict' trigger phrase with proper word boundaries."""
    if not text:
        return False
    return TRIGGER_REGEX.search(text) is not None


def extract_trigger_input(text: str) -> str:
    """
    Removes 'hey vict' trigger phrase from input text and cleans up leftover whitespace/punctuation.
    """
    if not text:
        return ""
    # Remove trigger phrase
    cleaned = TRIGGER_REGEX.sub("", text)
    # Clean leading punctuation like comma, colon, dash, period, exclamation, question mark and spaces
    cleaned = re.sub(r"^\s*[,:\-\.\!\?]+\s*", "", cleaned)
    # Collapse whitespace and trim
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def is_yggdrasil_message(content: str, author_is_bot: bool = False, author_name: str = "") -> bool:
    """
    Determines if a message string matches Yggdrasil transcript format.
    Only returns True if message has Yggdrasil structure/markers or comes from a bot.
    """
    if not content or not content.strip():
        return False

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return False

    has_ygg_heading = any(
        YGG_HEADING_REGEX.match(line) and "yggdrasil" in line.lower()
        for line in lines
    ) or any(YGG_HEADING_REGEX.match(line) for line in lines if "yggdrasil" in line.lower())

    has_ygg_emoji = YGG_EMOJI_PATTERN.search(content) is not None
    is_ygg_author = author_is_bot or "yggdrasil" in author_name.lower()

    # If it has no Yggdrasil bot author, no Yggdrasil heading, and no Yggdrasil emoji pattern, it's not a Yggdrasil transcript.
    if not (is_ygg_author or has_ygg_heading or has_ygg_emoji):
        return False

    # Filter out heading lines
    non_heading_lines = [line for line in lines if not YGG_HEADING_REGEX.match(line)]
    if not non_heading_lines:
        return False

    # Verify all non-heading lines match the Yggdrasil speaker pattern
    matched_count = sum(1 for line in non_heading_lines if YGG_SPEAKER_REGEX.match(line))
    return matched_count == len(non_heading_lines)


def parse_yggdrasil_transcript(content: str) -> List[Dict[str, str]]:
    """
    Parses a Yggdrasil transcript into a list of parsed speaker entries:
    [{"username": "nastyboy000", "text": "lmao"}, ...]
    Preserves the order of appearance.
    """
    entries = []
    lines = [line.strip() for line in content.splitlines() if line.strip()]

    for line in lines:
        if YGG_HEADING_REGEX.match(line):
            continue
        match = YGG_SPEAKER_REGEX.match(line)
        if match:
            username = match.group("username").strip()
            text = match.group("text").strip()
            entries.append({
                "username": username,
                "text": text
            })

    return entries


def resolve_yggdrasil_user(guild: Any, raw_username: str) -> Tuple[str, str]:
    """
    Attempts to resolve raw_username against guild members.
    Returns (user_id, username_handle).
    """
    clean_username = raw_username.lstrip("@").strip()
    if guild and hasattr(guild, "members"):
        for member in guild.members:
            if getattr(member, "name", "").lower() == clean_username.lower():
                return str(member.id), member.name

    return f"unresolved:{clean_username}", clean_username
