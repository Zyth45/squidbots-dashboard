"""Cleaning what a model says before a bot says it in game chat.

Models write for a screen: markdown, emoji, several paragraphs. A WoW chat line is plain text of at most 255
characters, and a bot that types `**bold**` or an essay stops sounding like a player.
"""
import re

# What a chat client cannot draw: bold and strikethrough, inline code, headings and bullets. A single *action*
# is how players roleplay in chat and stays; so does snake_case.
MARKDOWN = [
    (re.compile(r"\*\*(.+?)\*\*"), r"\1"),
    (re.compile(r"(?<!\w)__(.+?)__(?!\w)"), r"\1"),
    (re.compile(r"~~(.+?)~~"), r"\1"),
    (re.compile(r"(?<!\w)_(?=\S)(.+?)(?<=\S)_(?!\w)"), r"\1"),
    (re.compile(r"`+"), ""),
    (re.compile(r"^\s{0,3}#{1,6}\s+", re.M), ""),
    (re.compile(r"^\s*[-*\u2022]\s+", re.M), ""),
]
# Emoji and pictographs: the client draws them as boxes.
PICTOGRAPHS = re.compile("[\U0001F000-\U0001FFFF\U00002600-\U000027BF\U0000FE0F\U0000200D]")
SENTENCE_END = re.compile(r"[.!?…](?=\s|$)")
CLAUSE_BREAK = re.compile(r"[,;:](?=\s)")
# The least a chat line may be cut down to: "Welcome, John!" is a line, "Hmm." in front of a long answer is not.
WHOLE_MIN = 12
# Typographic characters that give away a model: real players type on a keyboard, so no em or en dashes, curly quotes
# or the single-character ellipsis. A dash becomes a comma, the way people actually break a sentence in chat.
DASHES = re.compile(r"\s*[\u2014\u2013\u2015]\s*")
TYPOGRAPHY = [
    (re.compile("[\u2018\u2019\u201B]"), "'"),
    (re.compile("[\u201C\u201D]"), '"'),
    (re.compile("\u2026"), "..."),
]


def plain_typography(text):
    text = DASHES.sub(", ", text)
    for pattern, replacement in TYPOGRAPHY:
        text = pattern.sub(replacement, text)
    return text.replace(",,", ",").replace(", ,", ",").replace(",.", ".").replace(", .", ".")


def _star_out(text, words):
    for word in words:
        text = re.sub(r"\b%s\b" % re.escape(word), lambda match: "*" * len(match.group(0)), text, flags=re.I)
    return text


def blocked_list(csv):
    return [word.strip() for word in csv.split(",") if word.strip()]


def clean(text, max_chars=250, blocked=(), bot_name="", whole_thought=False):
    """One plain line, without markup or emoji, starred where blocked, cut at a sentence when too long.

    `whole_thought` is for a line someone reads in chat as a person's: a shorter complete line beats a longer one that stops
    mid-sentence, so it is cut at the last whole sentence, else the last clause, and only then at a word."""
    if not isinstance(text, str):
        return text
    for pattern, replacement in MARKDOWN:
        text = pattern.sub(replacement, text)
    text = PICTOGRAPHS.sub("", text)
    text = plain_typography(text)
    # Models like to answer "Brick: hello". The bot's name is already on the line in game.
    if bot_name:
        text = re.sub(r"^\s*(?:\[?%s\]?\s*[:\-]\s*)" % re.escape(bot_name), "", text, flags=re.I)
    text = " ".join(text.split())
    if blocked:
        text = _star_out(text, blocked)
    if max_chars and len(text) > max_chars:
        head = text[:max_chars]
        ends = [match.end() for match in SENTENCE_END.finditer(head)]
        if ends and ends[-1] >= (WHOLE_MIN if whole_thought else max_chars * 0.4):
            text = head[:ends[-1]]
        else:
            clauses = [match.start() for match in CLAUSE_BREAK.finditer(head)] if whole_thought else []
            if clauses and clauses[-1] >= WHOLE_MIN:
                text = head[:clauses[-1]].rstrip() + "."
            else:
                # Three characters of ellipsis must still fit inside the limit.
                head = text[:max(max_chars - 3, 1)]
                text = head.rsplit(" ", 1)[0].rstrip(",;:-") + "..."
    return text.strip()
