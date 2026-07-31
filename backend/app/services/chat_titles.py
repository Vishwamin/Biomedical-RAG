"""
Local auto-title generation for new chats — explicitly NOT an LLM call.

Approach: strip leading question/stopwords, drop a small set of generic
filler words, title-case what's left, cap length. This is a genuine
keyword-extraction heuristic, not just truncation, but it is still a
heuristic — it will not always produce an editorially perfect title the
way a human or an LLM summarizing intent would (e.g. reordering words for
readability). That's an accepted, documented trade-off for the
requirement of zero extra LLM round-trips per chat.
"""

import re

_LEADING_STOPWORDS = {
    "what", "how", "why", "when", "where", "who", "whom", "which", "whose",
    "is", "are", "was", "were", "do", "does", "did", "can", "could", "should",
    "would", "will", "explain", "describe", "tell", "show", "give", "please",
    "me", "us", "about", "regarding", "according",
}

_FILLER_WORDS = {
    "the", "a", "an", "of", "for", "in", "on", "to", "and", "or", "with",
    "that", "this", "these", "those", "there", "exist", "exists", "existing",
}

_MAX_TITLE_WORDS = 6
_MAX_TITLE_CHARS = 48


def generate_chat_title(first_message: str) -> str:
    text = first_message.strip().rstrip("?!.").strip()
    if not text:
        return "New Chat"

    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-]*", text)
    if not words:
        return "New Chat"

    # Drop leading question/stopwords (only from the front — "what" mid-sentence
    # is meaningful, "what" as the first word usually isn't).
    i = 0
    while i < len(words) and words[i].lower() in _LEADING_STOPWORDS:
        i += 1
    remaining = words[i:] or words  # never end up with nothing

    keywords = [w for w in remaining if w.lower() not in _FILLER_WORDS] or remaining

    title_words = keywords[:_MAX_TITLE_WORDS]
    title = " ".join(w if w[0].isupper() or "'" in w else w.capitalize() for w in title_words)

    if len(title) > _MAX_TITLE_CHARS:
        title = title[:_MAX_TITLE_CHARS].rsplit(" ", 1)[0].rstrip() + "…"

    return title or "New Chat"
