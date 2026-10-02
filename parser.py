import re

# Strict start-of-message trigger match (case-insensitive, allows leading whitespace)
STRICT_TRIGGER_REGEX = re.compile(r"^\s*hey\s+vict\b", re.IGNORECASE)


def has_hey_vict_trigger(text: str) -> bool:
    """
    Checks if the message starts with 'hey vict' (case-insensitive) after trimming leading whitespace.
    """
    if not text:
        return False
    return STRICT_TRIGGER_REGEX.search(text) is not None


def extract_trigger_input(text: str) -> str:
    """
    Removes ONLY the leading 'hey vict' phrase from the message and cleans up leftover whitespace/punctuation.
    """
    if not text:
        return ""
    # Remove leading trigger phrase
    cleaned = STRICT_TRIGGER_REGEX.sub("", text, count=1)
    # Clean leading punctuation like comma, colon, dash, period, exclamation, question mark and spaces
    cleaned = re.sub(r"^\s*[,:\-\.\!\?]+\s*", "", cleaned)
    # Collapse whitespace and trim
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned
