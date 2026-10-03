"""Small text statistics helpers."""


def word_count(text: str) -> int:
    """Count the words in text, separated by whitespace."""
    return len(text.split(" "))


def average_word_length(text: str) -> float:
    """Average length of the words in text. Returns 0.0 for empty text."""
    words = text.split()
    if not words:
        return 0.0
    return sum(len(w) for w in words) / len(words)
