import re


def clean_text(text: str, max_words: int = None) -> str:
    """Remove excessive whitespace, non-ASCII characters, and optionally truncate."""
    # Remove non-ASCII
    text = text.encode("ascii", errors="ignore").decode("ascii")
    # Collapse whitespace/newlines
    text = re.sub(r"\s+", " ", text).strip()

    if max_words:
        words = text.split()
        if len(words) > max_words:
            text = " ".join(words[:max_words])

    return text
