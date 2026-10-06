"""Who is talking to whom, read from the request the worldserver module sent.

The module tells the model who it is in the system prompt ("botGuid = 123, name = Bob", "playerGuid = 45,
name = Ann") and names the caller in the OpenAI `user` field and, when session persistence is on, in the
session-key header. Any of them will do; the system prompt is preferred because it also carries the names.
A request that names no bot is passed through untouched.
"""
import re

# Conquest of Azeroth names take two words ("Alte Bot"), so a name runs to the "(" or the end of its line, not to the
# first space.
BOT = re.compile(r"botGuid\s*=\s*(\d+)(?:\s*,\s*name\s*=\s*([^\n(,]+?)\s*(?=\(|,|\n|$))?")
PLAYER = re.compile(r"playerGuid\s*=\s*(\d+)(?:\s*,\s*name\s*=\s*([^\n(,]+?)\s*(?=\(|,|\n|$))?")
USER_FIELD = re.compile(r"-(\d+)$")
SESSION_KEY = re.compile(r"(\d+)-(\d+)$")
# The fast lane (tactical ticks) carries a JSON snapshot rather than the system prompt above.
SNAPSHOT_BOT = re.compile(r'"?bot_?[gG]uid"?\s*[:=]\s*"?(\d+)')

SESSION_HEADER = "x-synthiq-session-key"


class Identity:
    def __init__(self, bot_guid=0, bot_name="", player_guid=0, player_name=""):
        self.bot_guid = bot_guid
        self.bot_name = bot_name
        self.player_guid = player_guid
        self.player_name = player_name

    def __repr__(self):
        return "Identity(bot=%s/%s, player=%s/%s)" % (self.bot_guid, self.bot_name, self.player_guid,
                                                      self.player_name)


def _text(content):
    """The text of a message whether `content` is a string or a list of OpenAI content parts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""


def identify(body, headers=None, lane="smart"):
    ident = Identity()
    messages = body.get("messages") or []
    system_text = "\n".join(_text(m.get("content")) for m in messages
                            if isinstance(m, dict) and m.get("role") == "system")

    # The bot's guid comes from the `user` field the module sets itself, not from prompt text: a
    # player's chat line can end up in a system prompt, and must not be able to pick whose memory is used.
    found = USER_FIELD.search(str(body.get("user") or ""))
    if found:
        ident.bot_guid = int(found.group(1))
    session = SESSION_KEY.search((headers or {}).get(SESSION_HEADER, ""))
    if session and not ident.bot_guid:
        ident.bot_guid = int(session.group(1))

    for found in BOT.finditer(system_text):
        if not ident.bot_guid or int(found.group(1)) == ident.bot_guid:
            ident.bot_guid, ident.bot_name = int(found.group(1)), found.group(2) or ""
            break
    found = PLAYER.search(system_text)
    if found:
        ident.player_guid, ident.player_name = int(found.group(1)), found.group(2) or ""
    elif session and int(session.group(1)) == ident.bot_guid:
        ident.player_guid = int(session.group(2))

    if not ident.bot_guid and lane == "fast":
        every = "\n".join(_text(m.get("content")) for m in messages if isinstance(m, dict))
        found = SNAPSHOT_BOT.search(every)
        if found:
            ident.bot_guid = int(found.group(1))
    return ident


def last_user_text(body):
    """What the player just said: the last user message, or "" when there is none."""
    for message in reversed(body.get("messages") or []):
        if isinstance(message, dict) and message.get("role") == "user":
            return _text(message.get("content")).strip()
    return ""
