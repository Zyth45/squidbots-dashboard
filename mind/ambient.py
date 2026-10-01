"""Ambient chat: one line from one bot, overheard in /say or a public channel, in its own voice.

A whitelisted player says "hi everyone" near some bots. The worldserver module picks the bots in earshot, and for each one
asks this service (POST /ambient) what it would say. Each bot answers from its own personality and memories, sees what the
others have already said in the same place, and may stay silent. The module staggers the answers and lets a bot answer
another bot's line a few times, so the street talks among itself and then goes quiet.

Nothing here touches the tools or the bot's remembered conversations: it is cheap, short, and forgotten.
"""
import collections
import random
import re
import threading
import time

from . import bank as bank_module, community as community_module, filters, identity, jev, memory, prompt, rp as rp_module, rp_bank

LINES_KEPT = 14              # per place: what a bot sees of the conversation so far
FORGET_AFTER = 15 * 60       # seconds without a word before a place's log is dropped
MAX_CHARS = 110             # what a bot is asked for
# What is let through. Models overshoot a character count, and a line cut at the number it was asked for ended mid-sentence
# ("...so you're already among..."), so a little over is fine; past this the line is shortened to a whole sentence.
CUT_CHARS = 160
RP_MAX_CHARS = 150          # roleplay lines run a little longer than chat lines: they are speech, not typing
RP_CUT_CHARS = 210
SCENE_WAIT = 12             # seconds a bot waits its turn to answer
SILENT = re.compile(r"^\W*\(?\s*(?:silent|nothing|no reply|\.\.\.)\s*\)?\W*$", re.I)

WHERE = {
    "say": "the /say chat: only people within about 30 yards can read it",
    "yell": "a /yell: everyone around, a hundred yards or so, can read it",
    "zone": "the zone channel: everyone in the zone can read it",
    "trade": "the Trade channel: mostly buying, selling and crafting talk",
    "lfg": "the Looking For Group channel: people finding groups for dungeons and quests",
    "world": "the realm-wide channel: everyone on the server can read it",
    "guild": "your guild chat: only your guildmates can read it, and you all know each other",
}

REWRITE_CHARS = 170
LINK = re.compile(r"\|c[0-9a-fA-F]{8}\|H.+?\|h\[.*?\]\|h\|r")

LINK_NAME = re.compile(r"\[([^\]]*)\]\|h")

REWRITE = ("YOUR LINE\n"
           "You were about to type this stock line in chat (the situation: %s):\n"
           "  \"%s\"\n"
           "Say the same thing the way YOU would: the same situation and facts, but your own words, attitude and voice. "
           "%s"
           "One line, casual, at most %d characters, no quotation marks around it, no markdown, never say you are an AI or a bot. "
           "Do not copy the stock wording.")

SITUATIONS = {
    "broadcast_looting_item_poor": "you looted a worthless grey item",
    "broadcast_looting_item_normal": "you looted an ordinary item",
    "broadcast_looting_item_uncommon": "you looted a decent green item",
    "broadcast_looting_item_rare": "you looted a rare blue item",
    "broadcast_looting_item_epic": "you looted an epic item",
    "broadcast_quest_accepted_generic": "you just accepted a quest",
    "broadcast_quest_turned_in": "you just turned a quest in",
    "broadcast_quest_update_add_item_objective_progress": "you are gathering items for a quest",
    "broadcast_quest_update_add_kill_objective_progress": "you are killing things for a quest",
    "broadcast_quest_update_add_item_objective_completed": "you finished gathering for a quest",
    "broadcast_quest_update_add_kill_objective_completed": "you finished the kills for a quest",
    "broadcast_quest_update_complete": "you completed every objective of a quest",
    "broadcast_levelup_generic": "you just levelled up",
    "broadcast_levelup_10x": "you just reached a round-number level",
    "broadcast_levelup_max_level": "you just reached the highest level",
    "broadcast_killed_normal": "you killed an ordinary enemy",
    "broadcast_killed_elite": "you killed an elite enemy",
    "broadcast_killed_rare": "you killed a rare enemy",
    "broadcast_killed_player": "you killed another player",
    "suggest_something": "you are making idle small talk in the channel",
    "suggest_something_toxic": "you are trash-talking in the channel",
    "suggest_faction": "you are wondering aloud about reputation with a faction",
    "suggest_instance": "you are looking for a group for a dungeon",
    "suggest_trade": "you are advertising that you want to trade something",
    "suggest_sell": "you are advertising an item for sale",
    "suggest_quest": "you are asking others to join you for a quest",
}


def situation(category):
    return SITUATIONS.get(category) or category.replace("broadcast_", "").replace("suggest_", "asking about ").replace("_", " ")


DEFAULT_VIBE = ("This is a busy realm's chat full of real players. Most of what people type is ordinary: a plain answer, a "
                "question, a small observation, something about what they are doing. Be a decent person to talk to: answer what "
                "was asked, help when you can, take an interest in the other person, and keep the conversation going by staying on "
                "what was just said and sometimes asking something back. People differ in how they sound (chatty, shy, dry, "
                "excitable), but nobody here is out to put the player down. Never be sarcastic at a player's expense, never mock a "
                "question and never brush someone off. Tease only when someone is clearly teasing first, and then lightly. Jokes "
                "are occasional, not every line. Mild swearing is fine when it comes naturally. Never use slurs or hate, nothing "
                "sexual, no real-world politics, and back off if someone is genuinely upset.")

# One nudge per line so that the same bot does not sound the same every time and a room does not fill with punchlines.
# (kind, weight, instruction). Weights are adjusted for jokers and for grumpy kinds in register().
REGISTERS = [
    ("plain", 34, "Answer plainly and literally, the way a normal person does. No joke, no flourish."),
    ("warm", 18, "Answer kindly and with a bit of interest in them, like someone who is glad to chat."),
    ("follow", 14, "Stay on the subject of the last few lines and add something of your own: an opinion, an example or a question."),
    ("brief", 12, "Reply in one to four words, like 'yeah', 'idk', 'nice one', 'same', 'nope'."),
    ("ask", 10, "Answer briefly, then ask something practical back, or just ask something."),
    ("gripe", 4, "Mention something small that is bugging you: the zone, lag, a quest, respawns, your gear."),
    ("aside", 4, "Half answer, then mention what you are actually doing right now."),
    ("rude", 1, "Be short and a bit blunt, the way a busy or tired person is. Not unkind."),
    ("joke", 4, "You have a light joke for this one, if it comes naturally. Keep it short and kind."),
]
JOKERS = {"troll", "banter merchant", "meme lord", "drama magnet"}
GRUMPS = {"impatient", "cynic", "salty veteran", "troll"}


def register(persona, rng, player=False):
    """The instruction for this one line, drawn so that jokers joke more often and grumps snap more often.

    `player`: the line answers a person who spoke to the room, who is never snapped at, unless the bot is a grump by nature."""
    kind = str(persona.get("archetype") or "")
    weights = []
    for name, weight, _ in REGISTERS:
        if name == "joke" and kind in JOKERS:
            weight += 20
        if name == "rude" and kind in GRUMPS:
            weight += 6
        if name in ("plain", "brief", "warm") and kind in JOKERS:
            weight = max(weight - 10, 5)
        if player and name in ("rude", "gripe", "aside") and kind not in GRUMPS:
            weight = 0
        weights.append(weight)
    pick = rng() * sum(weights)
    for (name, _, text), weight in zip(REGISTERS, weights):
        pick -= weight
        if pick <= 0:
            return text
    return REGISTERS[0][2]


HOW = ("HOW TO REPLY\n"
       "Write ONE chat line, the way a real player types it: casual, usually under 12 words, at most %d characters. "
       "Reply to what was just said and keep the conversation going: stay on its subject, answer any question you were asked "
       "(briefly and honestly, and if you do not know, say so), and now and then add something of your own or ask something back. "
       "Only the first to answer a hello welcomes the player: if someone already has, do not greet again, say something of your own "
       "or talk to the other character instead. Vary how you start (not every line is Hey or Hi), and do not repeat what others said. "
       "You may address someone by name. "
       "No narration, no quotation marks around the line, no markdown, and never say you are an AI or a bot. "
       "If you truly have nothing to add, or the line is not for you, answer exactly (silent).")


class Ambient:
    def __init__(self, gateway):
        self.gateway = gateway
        self.lock = threading.Lock()
        self.places = {}     # scene key -> deque of (time, name, text)
        self.turns = {}      # scene key -> lock: one bot answers at a time in a place
        self.topics = {}     # scene key -> (what the talk there is about, when it was noticed)
        self.player_at = {}  # scene key -> when a player last spoke there
        self.player_said = {}  # scene key -> (who, what) of that player's last line
        self.rng = random.random   # a test replaces it

    # ---- what has been said here ---------------------------------------------------------------------

    def hear(self, key, name, text):
        now = time.time()
        with self.lock:
            for stale in [k for k, log in self.places.items() if log and now - log[-1][0] > FORGET_AFTER]:
                del self.places[stale]
            log = self.places.setdefault(key, collections.deque(maxlen=LINES_KEPT))
            # Several bots hear the same line, and each asks for its answer: keep it once.
            if not any((who, said) == (name, text) and now - at < 10 for at, who, said in log):
                log.append((now, name, text))

    def recent(self, key):
        with self.lock:
            return list(self.places.get(key, ()))

    # ---- the request ---------------------------------------------------------------------------------

    def handle(self, body):
        """{"text": the line ("" for none), and how it went}. Never raises for a bad request.

        Bots that heard the same line ask at almost the same moment. In one place they answer one at a time, so each sees what
        the one before it said instead of all three saying "which quest?".
        """
        if isinstance(body, dict) and body.get("mode") == "start":
            return self._start(body)
        if isinstance(body, dict) and body.get("mode") == "welcome":
            return self._welcome(body)
        if isinstance(body, dict) and body.get("mode") == "combat":
            return self._combat(body)
        if not isinstance(body, dict) or body.get("mode") == "rewrite":
            return self._handle(body if isinstance(body, dict) else {})
        key = str(body.get("scene") or body.get("channel") or "say")
        with self.lock:
            place = self.turns.setdefault(key, threading.Lock())
        if not place.acquire(timeout=SCENE_WAIT):
            return {"text": "", "reason": "another bot is still answering here"}
        try:
            return self._handle(body)
        finally:
            place.release()

    def _handle(self, body):
        gateway, store = self.gateway, self.gateway.store
        try:
            guid = int(body.get("bot_guid") or 0)
        except (TypeError, ValueError):
            guid = 0
        message = str(body.get("message") or "").strip()
        if not guid or not message:
            return {"text": "", "reason": "bot_guid and message are required"}
        bot_name = str(body.get("bot_name") or "")[:40]
        speaker = str(body.get("speaker_name") or "someone")[:40]
        channel = str(body.get("channel") or "say")
        key = str(body.get("scene") or "%s" % channel)
        speaker_is_bot = bool(body.get("speaker_is_bot"))
        addressed = bool(body.get("addressed"))
        try:
            speaker_guid = int(body.get("speaker_guid") or 0)
        except (TypeError, ValueError):
            speaker_guid = 0
        bond = self.gateway.community.bond(guid, speaker_guid) if speaker_is_bot and speaker_guid else None
        if not speaker_is_bot and body.get("mode") != "rewrite":
            with self.lock:
                self.player_at[key] = time.time()
                self.player_said[key] = (speaker, message[:200])

        ident = identity.Identity(guid, bot_name, speaker_guid, speaker)
        refusal = gateway._refuse(ident)
        if refusal:
            return {"text": "", "reason": refusal[1].get("error", {}).get("type", "refused")}
        context = rp_module.clean_context(body)
        persona = gateway._persona(ident, context, "ambient")
        if not persona:
            return {"text": "", "reason": "no persona"}
        name = store.profile_for("ambient", guid) or store.profile_for("fast", guid)
        if body.get("mode") != "rewrite" and speaker_is_bot and not addressed:
            # A quiet bot mostly lets another bot's line go by (and costs nothing); a chatty one nearly always joins in. A player
            # who speaks is always answered by the bots the game picked: it would feel like being ignored.
            chattiness = persona.get("chattiness")
            chattiness = chattiness if isinstance(chattiness, int) else 50
            if self.rng() > 0.35 + 0.65 * chattiness / 100.0:
                return {"text": "", "reason": "quiet"}
        banked = self._from_bank(body, persona, ident, key, speaker, speaker_is_bot, bond=bond)
        if banked is not None:
            return banked
        if not name:
            return {"text": "", "reason": "no model is assigned to the ambient or quick-decisions lane"}

        rewrite = body.get("mode") == "rewrite"
        if rewrite:
            # The bot's own stock line, put in its own words. Nobody spoke to it, so there is no conversation to read.
            links = LINK.findall(message)
            shown = message
            for number, link in enumerate(links, 1):
                shown = shown.replace(link, "[[%d]]" % number, 1)
            system = self._system(persona, body, ident, shown, True, rewrite=True, links=links, context=context)
            lines = ["Write %s's line now." % (bot_name or "your")]
        else:
            self.hear(key, speaker, message)
            history = self.recent(key)
            topic = self._topic_here(key, [text for _, _, text in history], persona.get("rp"))
            system = self._system(persona, body, ident, message, speaker_is_bot, topic=topic, bond=bond, speaker=speaker, context=context)
            lines = ["Recent chat here:"] + ["[%s] %s" % (who, text) for _, who, text in history[-10:]]
            if speaker_is_bot:
                lines.append(self._answering_a_bot(key, speaker, message, bot_name))
            elif addressed:
                lines.append("%s is talking to you directly, in this channel. Answer them, in your own voice." % speaker)
            lines.append("Write %s's line now." % (bot_name or "your"))
        request = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": "\n".join(lines)}],
                   "temperature": 0.9}
        turn = {"lane": "ambient", "bot_guid": guid, "bot_name": bot_name, "player_guid": speaker_guid,
                "player_name": speaker, "said": (("[%s] stock line: %s" % (channel, message)) if body.get("mode") == "rewrite"
                         else ("[%s] %s: %s" % (channel, speaker, message)))[:1000],
                "tools_offered": "", "mind": "", "system_prompt": system[:gateway_prompt_kept()]}
        try:
            answer, meta = gateway._dispatch("ambient", guid, name, request, set())
        except Exception as failure:  # noqa: BLE001 - Limited and UpstreamError: the bot simply says nothing
            gateway._log_turn(turn, dict(profile=name, ok=0, error=str(failure)), force=False)
            return {"text": "", "reason": str(failure)[:200]}
        raw = ((answer.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        roleplay = bool(persona.get("rp"))
        text = filters.clean(raw, (RP_CUT_CHARS if roleplay else REWRITE_CHARS) if rewrite else (RP_CUT_CHARS if roleplay else CUT_CHARS),
                             filters.blocked_list(store.setting("blocked_words")), bot_name, whole_thought=True)
        text = text.strip().strip('"“”').strip()
        if rewrite and text:
            # The links went in as [[1]], [[2]]: put each back where the model wrote it, once. A model that lost one or wrote
            # its own gets the stock line instead of a broken link.
            if sorted(int(n) for n in re.findall(r"\[\[(\d+)\]\]", text)) != list(range(1, len(links) + 1)) or "[[" in re.sub(r"\[\[\d+\]\]", "", text):
                gateway._log_turn(turn, dict(meta, reply="(links changed) " + text, tool_calls="", ok=1), force=True)
                return {"text": "", "reason": "links changed", "latency_ms": meta["latency_ms"]}
            for number, link in enumerate(links, 1):
                text = text.replace("[[%d]]" % number, link)
        if not text or SILENT.match(text):
            gateway._log_turn(turn, dict(meta, reply="(silent)", tool_calls="", ok=1), force=True)
            if not rewrite and not speaker_is_bot:      # a player spoke: any fitting banked line beats being ignored
                banked = self._from_bank(body, persona, ident, key, speaker, speaker_is_bot, force=True)
                if banked is not None:
                    return banked
            return {"text": "", "reason": "silent", "latency_ms": meta["latency_ms"]}
        self.hear(key, bot_name or "?", text)
        gateway._log_turn(turn, dict(meta, reply=text, tool_calls="", ok=1), force=True)
        return {"text": text, "latency_ms": meta["latency_ms"], "cost_usd": meta["cost_usd"]}

    def _answering_a_bot(self, key, bot, message, me=""):
        """What a bot (`me`) is told about the line it answers when that line is another bot's. With a player in the talk the talk is
        with the player: told only to answer the last line, the bots reply to each other, and the person who spoke drops out."""
        with self.lock:
            since = self.player_at.get(key, 0)
            live = time.time() - since < self.PLAYER_LIVE_S
            player = self.player_said.get(key) if live else None
            # Said by this bot since the player last spoke: without it, a bot that has answered the player is handed another bot's
            # line, sees the player's question still standing, and answers it a second time.
            already = [text for at, who, text in self.places.get(key, ()) if who == me and at >= since] if player and me else []
        if not player:
            return "The line you are answering is the last one, from %s. Answer THEM directly." % bot
        who, said = player
        note = ("The last line is from %s, but this chat is with %s, a real player, who said: \"%s\". You may react to %s, but say "
                "something %s gets something out of: answer what they asked for yourself, give your own take, or add something new."
                % (bot, who, said, bot, who))
        if message.rstrip().endswith("?"):
            note += " %s just asked a question, so do not ask another one." % bot
        if already:
            note += (" You already answered %s (\"%s\"), so do not answer them again or repeat yourself: react to %s in a few words, "
                     "add something new, or answer exactly (silent)." % (who, already[-1][:120], bot))
        return note

    # ---- a bot that starts talking -------------------------------------------------------------------

    START_TOPICS = {
        "say": (("idle_topic", 5), ("idle_general", 3), ("idle_question", 2), ("idle_gripe", 2), ("idle_brag", 1)),
        "yell": (("idle_general", 1),),
        "zone": (("idle_topic", 5), ("idle_general", 3), ("idle_question", 3), ("idle_gripe", 2), ("idle_brag", 1)),
        "world": (("idle_topic", 5), ("idle_general", 3), ("idle_question", 2), ("idle_gripe", 2), ("idle_brag", 1)),
        "trade": (("idle_sell", 1),),
        "guild": (("idle_topic", 4), ("idle_general", 3), ("idle_question", 2), ("idle_brag", 1), ("idle_gripe", 1)),
        "lfg": (("idle_lfg", 1),),
    }

    def _start(self, body):
        """{"mode": "start"}: nobody spoke, the game asks a bot for something to say. Only ever from the line bank: a model
        call for a remark nobody is waiting for would cost the most for the least. Silence when the bank has nothing."""
        gateway = self.gateway
        try:
            guid = int(body.get("bot_guid") or 0)
        except (TypeError, ValueError):
            guid = 0
        if not guid:
            return {"text": "", "reason": "bot_guid is required"}
        channel = str(body.get("channel") or "zone")
        topics = self.START_TOPICS.get(channel)
        if not topics:
            return {"text": "", "reason": "no topics for this channel"}
        listing = body.get("listing") if isinstance(body.get("listing"), dict) else {}
        if channel == "trade" and not (listing.get("link") and listing.get("price")):
            return {"text": "", "reason": "nothing to sell: an advert names something the bot really carries"}
        ident = identity.Identity(guid, str(body.get("bot_name") or "")[:40], 0, "")
        if gateway._refuse(ident):
            return {"text": "", "reason": "refused"}
        context = rp_module.clean_context(body)
        persona = gateway._persona(ident, context, "ambient")
        if not persona:
            return {"text": "", "reason": "no persona"}
        key = str(body.get("scene") or channel)
        if persona.get("rp"):
            return self._start_rp(body, persona, ident, channel, key, context)
        total = sum(weight for _, weight in topics)
        roll, order = self.rng() * total, []
        for situation, weight in topics:
            roll -= weight
            if roll < 0 and not order:
                order.append(situation)
        order.extend(situation for situation, _ in topics if situation not in order)
        started = time.monotonic()
        recent = [text for _, _, text in self.recent(key)]
        topics = sorted(bank_module.TOPICS)
        order = [("idle_topic:" + topics[int(self.rng() * len(topics)) % len(topics)]) if name == "idle_topic" else name
                 for name in order]
        # A regular whose friend is around often talks to them by name, and the friend is expected to answer.
        friends = [item for item in (body.get("friends") or []) if isinstance(item, dict) and item.get("name") and item.get("guid")]
        friend = None
        if friends and channel != "trade" and self.rng() < 0.5:
            friend = friends[int(self.rng() * len(friends)) % len(friends)]
            order = ["idle_friend"] + order
        for situation in order[:2]:
            rows = gateway.bank.candidates(str(persona.get("archetype") or ""), [situation], guid, avoid=recent, limit=12, rng=self.rng)
            if rows:
                break
        else:
            return {"text": "", "reason": "the bank has no opening line for this kind of person"}
        chosen = rows[int(self.rng() * len(rows)) % len(rows)]
        if bank_module.needs(chosen["text"], "level") and not body.get("level"):
            return {"text": "", "reason": "no level to say"}
        to_friend = friend if friend and chosen["situation"] == "idle_friend" else None
        text = bank_module.fill(chosen["text"], zone=str(body.get("zone") or ""), klass=str(body.get("class") or ""),
                                level=body.get("level") or "", link=str(listing.get("link") or ""),
                                price=str(listing.get("price") or ""),
                                friend=community_module.short_name(to_friend["name"]) if to_friend else "")
        if not text or "{" in text:
            return {"text": "", "reason": "the line needed something we do not have"}
        gateway.bank.used(guid, chosen["id"])
        self.hear(key, ident.bot_name or "?", text)
        if ":" in chosen["situation"]:      # the others will be answering something about this
            with self.lock:
                self.topics[key] = (chosen["situation"].split(":", 1)[1], time.time())
        self._log_bank({"channel": channel, "message": "(nobody spoke: this bot started talking)"}, ident, "", text, "bank",
                       started, 0.0, key, chosen["situation"], True)
        answer = {"text": text, "latency_ms": int((time.monotonic() - started) * 1000), "cost_usd": 0.0, "source": "bank"}
        if to_friend:
            answer["addressed_guid"] = int(to_friend["guid"])
        return answer

    # ---- a bot tells its party what the fight is about -------------------------------------------------

    COMBAT_SITUATIONS = {"focus": "combat_focus", "cc": "combat_cc"}

    def _combat(self, body):
        """{"mode": "combat", "kind": "focus"|"cc", "mob": "Defias Conjurer"}: the game's combat director has picked a target and this
        bot says so in party chat. From the line bank only (a model call in the middle of a fight would arrive after it), so it
        costs nothing and answers at once; silence, and the game says its own plain line, when the bank has nothing for this bot."""
        gateway = self.gateway
        try:
            guid = int(body.get("bot_guid") or 0)
        except (TypeError, ValueError):
            guid = 0
        situation = self.COMBAT_SITUATIONS.get(str(body.get("kind") or ""))
        mob = " ".join(str(body.get("mob") or "").split())[:60]
        if not guid or not situation or not mob or "{" in mob or "}" in mob:
            return {"text": "", "reason": "bot_guid, a kind (focus or cc) and the enemy's name are required"}
        ident = identity.Identity(guid, str(body.get("bot_name") or "")[:40], 0, "")
        if gateway._refuse(ident):
            return {"text": "", "reason": "refused"}
        persona = gateway._persona(ident, rp_module.clean_context(body), "ambient")
        if not persona:
            return {"text": "", "reason": "no persona"}
        if persona.get("rp"):
            situation = rp_bank.PREFIX + situation
        started = time.monotonic()
        rows = gateway.bank.candidates(str(persona.get("archetype") or ""), [situation], guid, limit=12, rng=self.rng)
        if not rows:
            return {"text": "", "reason": "the bank has no call for this kind of person"}
        chosen = rows[int(self.rng() * len(rows)) % len(rows)]
        text = bank_module.fill(chosen["text"], mob=mob)
        if not text or "{" in text:
            return {"text": "", "reason": "the line needed something we do not have"}
        gateway.bank.used(guid, chosen["id"])
        self._log_bank({"channel": "party", "message": "(combat: %s %s)" % (body.get("kind"), mob)}, ident, "", text, "bank",
                       started, 0.0, "party", situation, True)
        return {"text": text, "latency_ms": int((time.monotonic() - started) * 1000), "cost_usd": 0.0, "source": "bank"}

    # ---- a regular greets a player who has just logged in ----------------------------------------------

    WELCOME = ("WELCOME\n%s has just logged in and you are glad to see them. Write ONE short line, one or two short sentences and at most %d characters, the way "
               "you would greet someone you know who is back: by name, warm, in your own voice. If you remember something about "
               "them or your last chat, mention it lightly; if you do not know them yet, a plain friendly hello. Ask at most "
               "one thing. No quotation marks, no markdown, never say you are an AI or a bot.")

    JOINED = ("WELCOME\n%s has just joined your guild. Welcome them in ONE short line, one or two short sentences and at most %d characters: by name, warm, in "
              "your own voice, the way a guildmate would. No quotation marks, no markdown, never say you are an AI or a bot.")

    RP_WELCOME = ("A FAMILIAR FACE\n%s has just arrived, and you are glad to see them. Say ONE short line aloud, one or two short sentences and at "
                  "most %d characters, the way you greet someone you know who has come back: by name, warm, in your own voice and your people's "
                  "way. If you remember something about them, mention it lightly; if you do not know them, a plain friendly greeting. Ask at most "
                  "one thing. No quotation marks, no markdown, never mention an AI, a bot or a game.")

    RP_JOINED = ("A NEW FELLOW\n%s has just joined your guild. Welcome them in ONE short line, one or two short sentences and at most %d "
                 "characters: by name, warm, in your own voice and your people's way, as a guild-fellow would. No quotation marks, no markdown, "
                 "never mention an AI, a bot or a game.")

    def _welcome(self, body):
        """{"mode": "welcome", bot_guid, bot_name, player_guid, player_name, channel}: one greeting line, written by the
        model, for a player who just came online."""
        gateway, store = self.gateway, self.gateway.store
        try:
            guid = int(body.get("bot_guid") or 0)
            player_guid = int(body.get("player_guid") or 0)
        except (TypeError, ValueError):
            guid = player_guid = 0
        player = str(body.get("player_name") or "")[:40]
        if not guid or not player_guid or not player:
            return {"text": "", "reason": "bot_guid, player_guid and player_name are required"}
        bot_name = str(body.get("bot_name") or "")[:40]
        channel = str(body.get("channel") or "world")
        ident = identity.Identity(guid, bot_name, player_guid, player)
        if gateway._refuse(ident):
            return {"text": "", "reason": "refused"}
        context = rp_module.clean_context(body)
        persona = gateway._persona(ident, context, "ambient")
        name = store.profile_for("ambient", guid) or store.profile_for("fast", guid)
        if not persona or not name:
            return {"text": "", "reason": "no persona or no model"}
        roleplay = bool(persona.get("rp"))
        if roleplay:
            parts = [gateway.rp.block(persona, context, store.setting("rp_rules"), "", False, True, prompt.TYPING_RULE, "", RP_MAX_CHARS),
                     "WHERE YOU ARE\nYou are %s." % rp_module.WHERE.get(channel, rp_module.WHERE["say"])]
        else:
            parts = [prompt.persona_block(persona, store.setting("style_rules"), "", actions=False),
                     "WHERE YOU ARE\nYou are %s. You are reading %s." % (bot_name or persona.get("name") or "a character",
                                                                          WHERE.get(channel, WHERE["world"])),
                     "THE VIBE\n" + (store.setting("ambient_vibe").strip() or DEFAULT_VIBE)]
        block = prompt.memory_block(player, memory.recall(store, guid, player_guid, "")[:3], store.relationship(guid, player_guid))
        if block:
            parts.append(block)
        if roleplay:
            parts.append((self.RP_JOINED if body.get("joined") else self.RP_WELCOME) % (player, RP_MAX_CHARS))
        else:
            parts.append((self.JOINED if body.get("joined") else self.WELCOME) % (player, MAX_CHARS))
        request = {"messages": [{"role": "system", "content": "\n\n".join(parts)},
                                {"role": "user", "content": "Write %s's greeting now." % (bot_name or "your")}],
                   "temperature": 0.9}
        turn = {"lane": "ambient", "bot_guid": guid, "bot_name": bot_name, "player_guid": player_guid, "player_name": player,
                "said": "[%s] (%s logged in)" % (channel, player), "tools_offered": "", "mind": "welcome",
                "system_prompt": parts[-1][:gateway_prompt_kept()]}
        try:
            answer, meta = gateway._dispatch("ambient", guid, name, request, set())
        except Exception as failure:  # noqa: BLE001 - no greeting is better than a broken one
            gateway._log_turn(turn, dict(profile=name, ok=0, error=str(failure)), force=False)
            return {"text": "", "reason": str(failure)[:200]}
        raw = ((answer.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        text = filters.clean(raw, RP_CUT_CHARS if roleplay else CUT_CHARS, filters.blocked_list(store.setting("blocked_words")), bot_name,
                             whole_thought=True).strip().strip('"“”').strip()
        if not text or SILENT.match(text):
            return {"text": "", "reason": "silent"}
        store.note_seen(guid, player_guid, player)
        gateway._log_turn(turn, dict(meta, reply=text, tool_calls="", ok=1), force=True)
        return {"text": text, "latency_ms": meta["latency_ms"], "cost_usd": meta["cost_usd"]}

    # ---- the line bank -------------------------------------------------------------------------------

    def _share(self, rewrite, speaker_is_bot, player_speaker, roleplay=False):
        store = self.gateway.store
        if rewrite or speaker_is_bot:
            return int(store.setting("bank_share_bots"))
        if not player_speaker:
            return int(store.setting("bank_share_bots"))
        return int(store.setting("rp_bank_share_player" if roleplay else "bank_share_player"))

    # A stock line is one of playerbots' own ("Took [quest]", "Where to?"): what it says is a category of remark, so a banked line
    # of that category says as much. Anything not in a known category is left to the model.
    REWRITE_FROM_BANK = frozenset(bank_module.CATEGORY_SITUATION.values())
    # The in-character bank has no adverts, and a stock remark about a kill or a quest is a boast or an errand to someone living in the world.
    RP_REWRITE = {"idle_loot": "rp_idle_loot", "idle_quest": "rp_idle_quest", "idle_levelup": "rp_idle_stronger", "idle_brag": "rp_idle_stronger",
                  "idle_general": "rp_idle_muse", "idle_gripe": "rp_idle_work", "idle_question": "rp_idle_question"}
    NO_FIT = "0"

    def _from_bank(self, body, persona, ident, key, speaker, speaker_is_bot, force=False, bond=None):
        """A prewritten line for this moment, or None to let the model write one. Costs no model call.

        `force`: the model had nothing to say to a player, so any fitting line is better than silence."""
        gateway = self.gateway
        store, bank = gateway.store, gateway.bank
        rewrite = body.get("mode") == "rewrite"
        roleplay = bool(persona.get("rp"))
        pre = rp_bank.PREFIX if roleplay else ""
        if not rewrite and not force and not self._bankable(body, key, speaker_is_bot):
            return None
        use_jev = not rewrite and store.setting("bank_picker") == "jev" and jev.available()
        # With Jev choosing, it also says when nothing banked fits, so a player's line is not left to chance; without it a share
        # of the lines go to the model as before.
        if not force and not (use_jev and not speaker_is_bot) and self.rng() * 100 >= self._share(rewrite, speaker_is_bot, not speaker_is_bot, roleplay):
            return None
        kind = str(persona.get("archetype") or "")
        message = str(body.get("message") or "").strip()
        started = time.monotonic()
        links = LINK.findall(message) if rewrite else []
        if rewrite:
            situation = bank_module.situation_for_category(body.get("category"))
            if situation not in self.REWRITE_FROM_BANK or (situation in bank_module.LINK_SITUATIONS and not links):
                return None
            if roleplay:
                situation = self.RP_REWRITE.get(situation)
                if not situation:
                    return None
            rows = bank.candidates(kind, [situation], ident.bot_guid, limit=12, rng=self.rng)
            history = []
        else:
            self.hear(key, speaker, message)
            history = self.recent(key)[-6:]
            avoid = [text for _, _, text in history]
            intents = bank_module.intents_of(message)
            wanted = intents[:2] + [bank_module.NO_INTENT] if intents[0] != bank_module.NO_INTENT else intents
            rows, seen = [], set()
            topic = self._topic_here(key, [text for _, _, text in history], roleplay)
            if bond:        # a friend's line is answered like a friend's: by name, and before anything generic
                for row in bank.candidates(kind, [pre + "reply_friend"], ident.bot_guid, avoid=avoid, limit=6, rng=self.rng):
                    seen.add(row["id"])
                    rows.append(row)
            if topic:       # lines about the subject first: they are what makes a reply sound like it was listening
                for row in bank.candidates(kind, [pre + "reply_topic:" + topic], ident.bot_guid, avoid=avoid, limit=8, rng=self.rng):
                    seen.add(row["id"])
                    rows.append(row)
            for intent in wanted:       # a few from each, so Jev can choose between kinds of answer and not only between lines
                for row in bank.candidates(kind, [pre + "reply_" + intent], ident.bot_guid, avoid=avoid, limit=6, rng=self.rng):
                    if row["id"] not in seen:
                        seen.add(row["id"])
                        rows.append(row)
        if not rows:
            return None

        def fill(text):
            return bank_module.fill(text, player=speaker if speaker != "someone" else "", zone=str(body.get("zone") or ""),
                                    klass=str(body.get("class") or ""), level=body.get("level") or "",
                                    link=links[0] if links else "", friend=community_module.short_name(speaker))
        chosen, picker, cost = rows[0], "bank", 0.0
        if use_jev and not force:
            try:
                picked, joins = self._jev_pick(rows, fill, persona, body, history, speaker, speaker_is_bot)
                picker = "bank+jev"
                cost = jev.PRICE_PER_M_INPUT * 700 / 1e6
                if picked is None:
                    if speaker_is_bot:
                        self._log_bank(body, ident, speaker, "(passed)", picker, started, cost, key, "", rewrite)
                        return {"text": "", "reason": "jev: this bot would let it pass (%.0f%%)" % (joins * 100)}
                    return None     # nothing banked fits what the player said: the model answers it
                chosen = picked
            except jev.JevError:
                chosen = rows[0]
        if bank_module.needs(chosen["text"], "level") and not body.get("level"):
            return None       # "grats on {level}" with no level to say
        text = fill(chosen["text"])
        if not text:
            return None
        bank.used(ident.bot_guid, chosen["id"])
        if not rewrite:
            self.hear(key, ident.bot_name or "?", text)
        self._log_bank(body, ident, speaker, text, picker, started, cost, key, chosen["situation"], rewrite)
        return {"text": text, "latency_ms": int((time.monotonic() - started) * 1000), "cost_usd": cost, "source": picker}

    # What a player says that a canned line can answer: hellos, thanks, goodbyes, a laugh. Anything else (a question, a story, a
    # follow-up) needs an answer to what was actually said, which only the model can write.
    SMALL_TALK = frozenset({"greeting", "farewell", "thanks", "joke"})
    PLAYER_LIVE_S = 150

    def _bankable(self, body, key, speaker_is_bot):
        """Whether a canned line may answer this one. A player's small talk, and a bot's answer deep in a chain or in a place where
        nobody has typed lately, can come from the bank for free; a real conversation is written, so it stays on its subject."""
        message = str(body.get("message") or "")
        if body.get("addressed"):
            return False       # somebody spoke to this bot by name: it answers them, it does not pick a line off a shelf
        if not speaker_is_bot:
            return "?" not in message and bank_module.intents_of(message)[0] in self.SMALL_TALK
        try:
            depth = int(body.get("depth") or 0)
        except (TypeError, ValueError):
            depth = 0
        with self.lock:
            talked = time.time() - self.player_at.get(key, 0) < self.PLAYER_LIVE_S
        return not (talked and depth <= int(self.gateway.store.setting("bank_llm_depth")))

    TOPIC_FRESH_S = 150

    def _topic_here(self, key, lines, roleplay=False):
        """What the talk in this place is about: read from the last few lines, else what it was a moment ago."""
        now = time.time()
        topic = (rp_bank.topic_of if roleplay else bank_module.topic_of)(lines)
        with self.lock:
            if topic:
                self.topics[key] = (topic, now)
                return topic
            known = self.topics.get(key)
            if known and now - known[1] < self.TOPIC_FRESH_S:
                return known[0]
        return ""

    def _jev_pick(self, rows, fill, persona, body, history, speaker, speaker_is_bot):
        """(the row that fits the conversation best, or None; the chance this person would speak).

        None means: another bot's line this person would let pass, or a player's line none of the banked lines answers."""
        options = {str(number): fill(row["text"]) for number, row in enumerate(rows, 1)}
        options[self.NO_FIT] = "None of these fits: what was just said is too specific or unusual for any of them"
        state = {"person": {"kind": persona.get("archetype"), "traits": persona.get("traits"), "speech": persona.get("speech_style")},
                 "channel": str(body.get("channel") or "say"),
                 "chat": ["[%s] %s" % (who, text) for _, who, text in history] or ["[%s] %s" % (speaker, body.get("message"))]}
        questions = {
            "pick": jev.choice_question(
                "`chat` is the recent public chat, the last line being what is answered. `person` is who is about to type. Which "
                "of these lines would this person most plausibly type next, so that the chat reads as one conversation? Prefer a "
                "line that answers what was actually said, fits how this person talks, and does not repeat what someone just said. "
                "Choose 0 when no line really answers it: a wrong-sounding reply is worse than none.",
                options),
        }
        if speaker_is_bot:       # a player who speaks is always answered; two bots talking need not be
            questions["join"] = jev.yes_question(
                "Would this person type anything at all in reply to the last line right now, rather than let it pass? Lines "
                "addressed to the room, greetings and questions are often answered; replies to an exchange between two others "
                "are less often.")
        answers = jev.decide(state, questions)
        join = float((answers.get("join") or {}).get("noul") or 1) if speaker_is_bot else 1.0
        if speaker_is_bot and join * 100 < int(self.gateway.store.setting("bank_join_min")):
            return None, join
        picked, _ = jev.top_choice(answers.get("pick"), list(options))
        if picked is None or picked == self.NO_FIT:
            return None, join
        return rows[int(picked) - 1], join

    def _log_bank(self, body, ident, speaker, text, picker, started, cost, key, situation, rewrite):
        gateway = self.gateway
        channel = str(body.get("channel") or "say")
        said = (("[%s] stock line: %s" % (channel, body.get("message"))) if rewrite
                else ("[%s] %s: %s" % (channel, speaker, body.get("message"))))
        turn = {"lane": "ambient", "bot_guid": ident.bot_guid, "bot_name": ident.bot_name, "player_guid": ident.player_guid,
                "player_name": speaker, "said": said[:1000], "tools_offered": "", "mind": situation,
                "system_prompt": "(line bank%s: %s)" % (", picked by Jev" if picker == "bank+jev" else "", situation)}
        outcome = {"profile": picker, "model": "", "latency_ms": int((time.monotonic() - started) * 1000), "prompt_tokens": 0,
                   "completion_tokens": 0, "cached_tokens": 0, "cost_usd": cost, "reply": text, "tool_calls": "", "ok": 1}
        gateway._log_turn(turn, outcome, force=True)

    def _system(self, persona, body, ident, message, speaker_is_bot, rewrite=False, links=(), topic="", bond=None, speaker="", context=None):
        store = self.gateway.store
        if persona.get("rp"):
            return self._rp_system(persona, body, ident, message, speaker_is_bot, rewrite, links, topic, bond, speaker, context or {})
        parts = [prompt.persona_block(persona, store.setting("style_rules"), "", actions=False)]
        where = WHERE.get(str(body.get("channel") or "say"), WHERE["say"])
        place = str(body.get("zone") or "").strip()
        area = str(body.get("area") or "").strip()
        if area and area != place:
            place = "%s, in %s" % (area, place) if place else area
        who = "You are %s" % (ident.bot_name or persona.get("name") or "a character")
        details = " ".join(part for part in (str(body.get("race") or ""), str(body.get("class") or "")) if part)
        if body.get("level"):
            who += ", a level %s %s" % (body["level"], details or "adventurer")
        elif details:
            who += ", a %s" % details
        parts.append("WHERE YOU ARE\n%s%s. You are reading %s." % (who, (" in " + place) if place else "", where))
        parts.append("THE VIBE\n" + (store.setting("ambient_vibe").strip() or DEFAULT_VIBE))
        if rewrite:
            if links:
                names = "; ".join("[[%d]] is \"%s\"" % (number, (LINK_NAME.search(link) or [None, "an item or quest"])[1])
                                   for number, link in enumerate(links, 1))
                keep = ("The line has placeholders (%s). Keep each placeholder exactly once, where you would name it; it "
                        "becomes a clickable link, so never also write the name itself. " % names)
            else:
                keep = ""
            parts.append(REWRITE % (situation(str(body.get("category") or "")), message, keep, REWRITE_CHARS))
            return "\n\n".join(parts)
        if not speaker_is_bot and ident.player_guid:
            recalled = memory.recall(store, ident.bot_guid, ident.player_guid, message)[:2]
            relation = store.relationship(ident.bot_guid, ident.player_guid)
            block = prompt.memory_block(ident.player_name, recalled, relation)
            if block:
                parts.append(block)
        if bond and speaker:
            parts.append("BETWEEN YOU\n%s and you are %s%s. Talk like people who know each other." % (
                community_module.short_name(speaker), bond["kind"], (": " + bond["note"].rstrip(".")) if bond.get("note") else ""))
        parts.append(HOW % MAX_CHARS)
        if topic in bank_module.TOPICS:
            parts.append("THE SUBJECT\nThe talk here is about %s. Stay with it unless the last line changed the subject."
                         % bank_module.TOPICS[topic][1])
        parts.append("THIS TIME\n" + register(persona, self.rng, player=not speaker_is_bot))
        return "\n\n".join(parts)


    def _rp_system(self, persona, body, ident, message, speaker_is_bot, rewrite, links, topic, bond, speaker, context):
        """The same as `_system` for a character in the lore: who they are, their story and what they are doing, then the scene."""
        store = self.gateway.store
        parts = [self.gateway.rp.block(persona, context, store.setting("rp_rules"), "", False, True, prompt.TYPING_RULE, "", RP_MAX_CHARS)]
        parts.append("WHERE YOU ARE\nYou are %s." % rp_module.WHERE.get(str(body.get("channel") or "say"), rp_module.WHERE["say"]))
        if rewrite:
            if links:
                names = "; ".join("[[%d]] is \"%s\"" % (number, (LINK_NAME.search(link) or [None, "a thing"])[1])
                                   for number, link in enumerate(links, 1))
                keep = ("The line has placeholders (%s). Keep each placeholder exactly once, where you would name it; it "
                        "becomes a clickable link, so never also write the name itself. " % names)
            else:
                keep = ""
            parts.append(rp_module.REWRITE % (situation(str(body.get("category") or "")), message, keep, RP_MAX_CHARS))
            return "\n\n".join(parts)
        if not speaker_is_bot and ident.player_guid:
            recalled = memory.recall(store, ident.bot_guid, ident.player_guid, message)[:2]
            block = prompt.memory_block(ident.player_name, recalled, store.relationship(ident.bot_guid, ident.player_guid))
            if block:
                parts.append(block)
        if bond and speaker:
            parts.append("BETWEEN YOU\n%s and you are %s%s. Speak as people who know each other." % (
                community_module.short_name(speaker), bond["kind"], (": " + bond["note"].rstrip(".")) if bond.get("note") else ""))
        parts.append(rp_module.HOW % RP_MAX_CHARS)
        if topic in rp_bank.TOPICS:
            parts.append("THE SUBJECT\nThe talk here is about %s. Stay with it unless the last line changed the subject." % rp_bank.TOPICS[topic][1])
        parts.append("THIS TIME\n" + rp_module.register(self.rng))
        return "\n\n".join(parts)

    # ---- a character who speaks up unprompted ------------------------------------------------------------

    START_RP = {
        "say": (("rp_idle_topic", 4), ("rp_idle_muse", 3), ("rp_idle_scenery", 3), ("rp_idle_work", 3), ("rp_idle_hail", 3), ("rp_idle_zone", 3),
                ("rp_idle_story", 2), ("rp_idle_question", 2), ("rp_idle_camp", 2), ("rp_idle_humor", 2), ("rp_idle_homesick", 1),
                ("rp_idle_creed", 1), ("rp_idle_others", 1), ("rp_idle_war", 1), ("rp_idle_prayer", 1)),
        "yell": (("rp_idle_hail", 3), ("rp_idle_war", 1)),
        "guild": (("rp_idle_topic", 4), ("rp_idle_muse", 3), ("rp_idle_camp", 3), ("rp_idle_story", 3), ("rp_idle_homesick", 2),
                  ("rp_idle_humor", 3), ("rp_idle_work", 2), ("rp_idle_question", 2), ("rp_idle_war", 1), ("rp_idle_prayer", 1)),
    }
    START_RP["zone"] = START_RP["world"] = START_RP["say"]   # a person who lets these channels on talks the same way in them
    START_RP["lfg"] = (("rp_idle_question", 1),)
    ZONE_LINE_CHANCE = 0.35

    SPEAK_UP = ("HOW TO SPEAK UP\nNobody has spoken to you; you decide to say something aloud, as a person does when something crosses their "
                "mind. It comes from what you are doing or where you are right now (the place, the weather, an errand, a memory it stirs, "
                "something you know about this land) or from your own story. Do not recite your errands like a list or announce them like a "
                "chore: mention at most one, in your own words. Say ONE thing, one or two short sentences, at most %d characters, no "
                "quotation marks, no markdown, never mention an AI, a bot or a game. A brief *action* is fine now and then. It must make sense "
                "to someone who knows nothing of what you are doing.")

    def _start_rp(self, body, persona, ident, channel, key, context):
        """A roleplaying bot speaks up on its own: sometimes written from what it is doing here and now (its errands, the zone), the
        rest from the in-character bank, where it may say something about the very zone it stands in."""
        gateway, store = self.gateway, self.gateway.store
        guid = ident.bot_guid
        topics = self.START_RP.get(channel)
        if not topics:
            return {"text": "", "reason": "a person in the world does not advertise: no remark for this channel"}
        started = time.monotonic()
        recent = [text for _, _, text in self.recent(key)]
        name = store.profile_for("ambient", guid) or store.profile_for("fast", guid)
        live = int(store.setting("rp_start_llm"))
        if name and live and (context.get("quests") or context.get("zone")) and self.rng() * 100 < live:
            text = self._start_written(persona, ident, channel, key, context, name, recent, started)
            if text:
                return text
        friends = [item for item in (body.get("friends") or []) if isinstance(item, dict) and item.get("name") and item.get("guid")]
        total = sum(weight for _, weight in topics)
        roll, order = self.rng() * total, []
        for situation_name, weight in topics:
            roll -= weight
            if roll < 0 and not order:
                order.append(situation_name)
        order.extend(situation_name for situation_name, _ in topics if situation_name not in order)
        subjects = sorted(rp_bank.TOPICS)
        order = [("rp_idle_topic:" + subjects[int(self.rng() * len(subjects)) % len(subjects)]) if item == "rp_idle_topic" else item for item in order]
        friend = None
        if friends and self.rng() < 0.5:
            friend = friends[int(self.rng() * len(friends)) % len(friends)]
            order = ["rp_idle_friend"] + order
        kind, race, zone = str(persona.get("archetype") or ""), persona.get("race"), context.get("zone") or ""
        rows = []
        if race and zone in rp_module.lore.ZONES and self.rng() < self.ZONE_LINE_CHANCE:
            rows = gateway.bank.candidates("rpz:" + race, ["rp_zone:" + zone], guid, avoid=recent, limit=12, rng=self.rng)
        for situation_name in ([] if rows else order[:2]):
            rows = gateway.bank.candidates(kind, [situation_name], guid, avoid=recent, limit=12, rng=self.rng)
            if rows:
                break
        if not rows:
            return {"text": "", "reason": "the roleplay bank has no opening line for this kind of person"}
        chosen = rows[int(self.rng() * len(rows)) % len(rows)]
        to_friend = friend if friend and chosen["situation"] == "rp_idle_friend" else None
        text = bank_module.fill(chosen["text"], zone=zone, klass=str(context.get("klass") or ""),
                                friend=community_module.short_name(to_friend["name"]) if to_friend else "")
        if not text or "{" in text:
            return {"text": "", "reason": "the line needed something we do not have"}
        gateway.bank.used(guid, chosen["id"])
        self.hear(key, ident.bot_name or "?", text)
        if ":" in chosen["situation"] and chosen["situation"].startswith("rp_idle_topic"):
            with self.lock:
                self.topics[key] = (chosen["situation"].split(":", 1)[1], time.time())
        self._log_bank({"channel": channel, "message": "(nobody spoke: this bot started talking)"}, ident, "", text, "bank",
                       started, 0.0, key, chosen["situation"], True)
        answer = {"text": text, "latency_ms": int((time.monotonic() - started) * 1000), "cost_usd": 0.0, "source": "bank"}
        if to_friend:
            answer["addressed_guid"] = int(to_friend["guid"])
        return answer

    def _start_written(self, persona, ident, channel, key, context, name, recent, started):
        """A model writes the remark from the character, where it is and what it is busy with. {} when it had nothing to say."""
        gateway, store = self.gateway, self.gateway.store
        system = "\n\n".join([
            gateway.rp.block(persona, context, store.setting("rp_rules"), "", False, True, prompt.TYPING_RULE, "", RP_MAX_CHARS),
            "WHERE YOU ARE\nYou are %s." % rp_module.WHERE.get(channel, rp_module.WHERE["say"]),
            self.SPEAK_UP % RP_MAX_CHARS])
        lines = ["Recent talk here:"] + ["[%s] %s" % (who, text) for _, who, text in self.recent(key)[-6:]] if recent else []
        lines.append("Say your line now.")
        request = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": "\n".join(lines)}], "temperature": 0.95}
        turn = {"lane": "ambient", "bot_guid": ident.bot_guid, "bot_name": ident.bot_name, "player_guid": 0, "player_name": "",
                "said": "[%s] (nobody spoke: this bot started talking)" % channel, "tools_offered": "", "mind": "roleplay start",
                "system_prompt": system[:gateway_prompt_kept()]}
        try:
            answer, meta = gateway._dispatch("ambient", ident.bot_guid, name, request, set())
        except Exception as failure:  # noqa: BLE001 - nothing said is better than something broken; the bank is tried next
            gateway._log_turn(turn, dict(profile=name, ok=0, error=str(failure)), force=False)
            return None
        raw = ((answer.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        text = filters.clean(raw, RP_CUT_CHARS, filters.blocked_list(store.setting("blocked_words")), ident.bot_name,
                             whole_thought=True).strip().strip('"“”').strip()
        if not text or SILENT.match(text) or rp_bank.META.search(text) or rp_bank.ANACHRONISM.search(text):
            gateway._log_turn(turn, dict(meta, reply=text or "(silent)", tool_calls="", ok=1), force=True)
            return None
        self.hear(key, ident.bot_name or "?", text)
        gateway._log_turn(turn, dict(meta, reply=text, tool_calls="", ok=1), force=True)
        return {"text": text, "latency_ms": int((time.monotonic() - started) * 1000), "cost_usd": meta["cost_usd"], "source": "written"}


def gateway_prompt_kept():
    from . import gateway
    return gateway.PROMPT_KEPT
