"""What a bot remembers: choosing what to recall, recording what was said, and reflecting on it.

Recording is cheap and needs no model: every exchange is stored as an "event". Reflection is the part that
turns events into lasting "fact" memories and moves the bot's feeling about the player; it costs one model
call every few exchanges and only runs when a profile is assigned to the "memory" lane.
"""
import json
import math
import re
import threading
import time

WORD = re.compile(r"[a-z0-9']{3,}")
# A player asking to be remembered, or telling the bot something about themselves, matters more than small talk.
IMPORTANT = re.compile(r"\b(remember|don'?t forget|my name|i'?m called|i am|promise|birthday|favou?rite|"
                       r"i play|i main|my guild|thank(s| you)|sorry)\b", re.I)
HALF_LIFE_DAYS = {"event": 14.0, "fact": 180.0, "summary": 180.0}
DAY = 86400.0


def tokens(text):
    return set(WORD.findall(text.lower()))


def _score(memory, query, now):
    """Salience faded by age (facts fade slowly), plus how many of the query's words the memory shares."""
    half = HALF_LIFE_DAYS.get(memory["kind"], 14.0)
    age_days = max(0.0, (now - memory["created_at"]) / DAY)
    fade = math.pow(0.5, age_days / half)
    overlap = len(query & tokens(memory["text"])) / max(1, len(query))
    return memory["salience"] * fade + 0.6 * overlap


def recall(store, bot_guid, player_guid, message, now=None):
    """The memories worth putting in front of the model for this message, oldest first."""
    now = now or time.time()
    count = int(store.setting("recall_count"))
    if count <= 0 or not player_guid:
        return []
    query = tokens(message)
    pool = store.memories(bot_guid, player_guid, limit=400)
    ranked = sorted(pool, key=lambda memory: _score(memory, query, now), reverse=True)[:count]
    store.touch_memories([memory["id"] for memory in ranked])
    return sorted(ranked, key=lambda memory: (memory["created_at"], memory["id"]))


def clip(text, limit):
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def record_exchange(store, bot_guid, player_guid, player_name, said, replied):
    """Store one exchange as an event. Returns True when it was stored (a resend within a minute is not)."""
    if not (bot_guid and player_guid and said and replied):
        return False
    latest = store.memories(bot_guid, player_guid, kinds=["event"], limit=1)
    line = '%s said: "%s" - you replied: "%s"' % (player_name or "they", clip(said, 200), clip(replied, 200))
    if latest and latest[0]["text"] == line and time.time() - latest[0]["created_at"] < 60:
        return False
    salience = 0.55 if IMPORTANT.search(said) else 0.25
    store.add_memory(bot_guid, player_guid, player_name, "event", line, salience)
    store.note_seen(bot_guid, player_guid, player_name)
    store.prune_events(bot_guid, player_guid, int(store.setting("memory_per_subject")))
    return True


# ---- reflection ----------------------------------------------------------------------------------------

REFLECT_SYSTEM = (
    "You keep the memory of a game character. You are given the character's recent conversation with one "
    "player, what the character already knows about them, and how they feel about them now. Reply with JSON "
    'only: {"facts": [{"text": "...", "salience": 0.0-1.0}], "affinity_change": -0.2..0.2, "reason": "..."}. '
    "Facts are short, lasting things worth remembering about the player or a promise made (their class, "
    "plans, what they asked for, how they treated the character), written from the character's point of "
    "view. Give at most three, none that repeat what is already known, and none for small talk. "
    "affinity_change is how the feeling moved; reason is a few words for it."
)


def parse_reflection(text):
    """The first JSON object in a model reply, cleaned up; None when there is nothing usable."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    facts = []
    for item in data.get("facts") or []:
        if isinstance(item, str):
            item = {"text": item}
        if isinstance(item, dict) and str(item.get("text", "")).strip():
            try:
                salience = float(item.get("salience", 0.6))
            except (TypeError, ValueError):
                salience = 0.6
            facts.append({"text": clip(item["text"], 200), "salience": max(0.1, min(1.0, salience))})
    try:
        change = max(-0.25, min(0.25, float(data.get("affinity_change", 0))))
    except (TypeError, ValueError):
        change = 0.0
    return {"facts": facts[:3], "affinity_change": change, "reason": clip(data.get("reason", ""), 120)}


def _similar(a, b):
    left, right = tokens(a), tokens(b)
    return bool(left and right) and len(left & right) / len(left | right) >= 0.7


def apply_reflection(store, bot_guid, player_guid, player_name, reflection):
    existing = store.memories(bot_guid, player_guid, kinds=["fact"], limit=100)
    for fact in reflection["facts"]:
        match = next((memory for memory in existing if _similar(memory["text"], fact["text"])), None)
        if match:
            store.update_memory(match["id"], bot_guid, match["text"], max(match["salience"], fact["salience"]))
        else:
            store.add_memory(bot_guid, player_guid, player_name, "fact", fact["text"], fact["salience"])
    relation = store.relationship(bot_guid, player_guid)
    if relation:
        store.set_affinity(bot_guid, player_guid, relation["affinity"] + reflection["affinity_change"],
                           reflection["reason"] or relation["reason"])


def reflection_prompt(store, bot_guid, player_guid, player_name, bot_name):
    events = list(reversed(store.memories(bot_guid, player_guid, kinds=["event"], limit=12)))
    facts = store.memories(bot_guid, player_guid, kinds=["fact"], limit=8)
    relation = store.relationship(bot_guid, player_guid)
    lines = ["Character: %s. Player: %s." % (bot_name or "the bot", player_name or "the player")]
    lines.append("Feeling now (-1 dislike .. 1 close friend): %.2f" % (relation["affinity"] if relation else 0))
    lines.append("Already known:" + ("".join("\n- " + f["text"] for f in facts) if facts else " nothing"))
    lines.append("Recent conversation:" + "".join("\n- " + e["text"] for e in events))
    return "\n".join(lines)


class Reflector:
    """Counts exchanges per bot and player and, every `reflect_every`, runs one reflection in the background.

    `call` is a function (system, user) -> reply text, or None when no profile is assigned to the memory lane.
    It is given in by the gateway so this module never talks to a provider itself.
    """

    def __init__(self, store, call):
        self.store = store
        self.call = call
        self.lock = threading.Lock()
        self.pending = {}
        self.running = set()

    def note(self, bot_guid, bot_name, player_guid, player_name):
        every = int(self.store.setting("reflect_every"))
        if every <= 0:
            return
        key = (bot_guid, player_guid)
        with self.lock:
            self.pending[key] = self.pending.get(key, 0) + 1
            if self.pending[key] < every or key in self.running:
                return
            self.pending[key] = 0
            self.running.add(key)
        threading.Thread(target=self._run, args=(key, bot_name, player_name), daemon=True).start()

    def _run(self, key, bot_name, player_name):
        bot_guid, player_guid = key
        try:
            user = reflection_prompt(self.store, bot_guid, player_guid, player_name, bot_name)
            reply = self.call(REFLECT_SYSTEM, user)
            reflection = parse_reflection(reply) if reply else None
            if reflection:
                apply_reflection(self.store, bot_guid, player_guid, player_name, reflection)
        except Exception as error:  # a failed reflection must never take a chat down with it
            print("Reflection failed for bot %d: %s" % (bot_guid, error), flush=True)
        finally:
            with self.lock:
                self.running.discard(key)
