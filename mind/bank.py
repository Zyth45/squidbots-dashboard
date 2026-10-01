"""A bank of prewritten chat lines, so a busy realm can talk without an LLM call per line.

Lines are written once, in bulk, by a model: every kind of person (see personas.py) times every situation a player meets
in chat, some of them idle ("lfg dungeon", "wts cloth", a gripe about the zone) and some replies to a kind of line (a
greeting, a question, a joke). Choosing one at runtime costs nothing when done locally, and about $0.00002 when Jev picks
among a dozen candidates so that the answer fits what was just said.

A line may hold placeholders that are filled in when it is said: {player} {zone} {class} {level} {link}. {link} is the
item or quest the game already named in the stock line, so loot and quest situations stay accurate.
"""
import collections
import concurrent.futures
import json
import random
import re
import threading
import time

from . import filters, personas, rp_bank

PLACEHOLDER = re.compile(r"\{(player|zone|class|level|link|price|friend|mob)\}")
FRIEND_SITUATIONS = {"idle_friend", "reply_friend"}
LINK_SITUATIONS = {"idle_quest", "idle_loot", "idle_sell"}
# Said in party chat mid-fight when the game's combat director picks a target: the enemy's name goes where {mob} is.
MOB_SITUATIONS = {"combat_focus", "combat_cc"}
# A line about the bot's OWN loot or level is not a remark to somebody else's: "you got {link}!", "grats on {level}" would be said about a
# player who did nothing. Dropped for these two situations (idle_quest keeps "you": offering help is natural there).
SELF_ONLY = {"idle_loot", "idle_levelup"}
ADDRESSES_SOMEONE = re.compile(r"\byou(?:'re|'ve|'ll|'d|rs?|rself)?\b|\b(?:grats|congrats|congratulations|gratz)\b", re.I)
# The speaker is whichever bot the game picked, whatever it is: a call that claims a role or an ability for "me" would be wrong coming
# from most of them ("I'll heal through!" from a rogue). Talk about the group or the enemy, never about what I do.
ROLE_CLAIM = re.compile(r"\b(?:i|i'll|i'm|i am|i will|my)\b[^.!?]*\b(?:heal\w*|tank\w*|taunt\w*|cast\w*|spell\w*|mana|buff\w*|stun\w*|shield\w*|pet|dps|control\w*|sheep\w*|polymorph\w*|freez\w*|trap\w*|banish\w*|root\w*|interrupt\w*|kick\w*)\b"
                        r"|\bwhile i (?:heal|tank|cast|dps)\b", re.I)
OPENERS = {"idle_general", "idle_gripe", "idle_brag", "idle_question", "idle_friend"}     # lines that must stand on their own
MAX_CHARS = 110
# Said to a room that has read nothing before it, so each must make sense alone: a second model reads them before they are kept.
REVIEWED = OPENERS | {"idle_topic", "idle_lfg"}
# "The next objective" is the word that most often points at something only the writer can see. Unless a quest link names the
# quest it belongs to, no line keeps it.
OBJECTIVE = re.compile(r"\bobjectives?\b", re.I)

REVIEW = ("You review lines for the public chat of a fantasy MMO, typed by players. Each line is said out of nowhere: nobody spoke "
          "before it and the people reading it have seen nothing else. Flag every line a stranger could NOT make sense of: it "
          "refers to something the reader cannot know (an unnamed objective, quest, boss, target, person, spot, item, or 'it', "
          "'that', 'this', 'the next one' with nothing to point at), it answers or reacts to something unseen, or it is a fragment. "
          "Lines about the game in general, that name a concrete thing, or ask something anyone could answer are fine. "
          "Placeholders such as {zone}, {class}, {level} and {friend} will be filled in with real values, so they are fine. "
          'Reply with a JSON object {"confusing": [line numbers]} and nothing else.')

# name -> (channels it suits, what the writer is asked for)
SITUATIONS = {
    "idle_general": ("say,zone,world", "small talk to nobody in particular: something you noticed, wondered, or felt about the game"),
    "idle_gripe": ("say,zone,world", "a small complaint: lag, respawns, a quest, drop luck, gear, the zone, a class"),
    "idle_brag": ("say,zone,world", "a brag or a bit of good news about what you just did or got, saying what it was (a level, a "
                                     "profession skill, a dungeon cleared, a piece of gear)"),
    "idle_question": ("zone,world,say", "asking chat something practical about the game in general: how a system works, which class, "
                                        "profession or zone suits something, whether anyone knows a trick or wants to group up"),
    "idle_lfg": ("lfg,world", "calling for a group for a dungeon or a quest chain, the way lfg spam is typed (no real dungeon names)"),
    "idle_trade": ("trade", "a trade-channel advert: wts or wtb of crafting mats, gear or bags, with a price or 'pm me'"),
    "idle_friend": ("say,zone,world", "talking to a friend by name: {friend} is written exactly once, and you greet them, poke fun at "
                                      "them, ask how they are or ask them something; it makes sense with no context"),
    "reply_friend": ("say,zone,world", "answering something your friend {friend} just said, without knowing exactly what it was: "
                                        "{friend} is written exactly once, warm, teasing or curious, never giving facts"),
    "idle_sell": ("trade", "a trade-channel advert for one item you really have: the item (with its stack size) is {link} exactly "
                           "once, the asking price is {price} exactly once, and you say how to buy, such as 'pm me' or 'whisper me'"),
    "idle_quest": ("say,zone", "you just took or handed in a quest and mention it; the quest is written as {link} exactly once"),
    "idle_loot": ("say,zone", "you just looted an item and react to it; the item is written as {link} exactly once"),
    "idle_levelup": ("say,zone,world", "you just gained a level; the level is written as {level} exactly once"),
    "idle_farewell": ("say,zone,world", "saying you are about to go afk, log off, or leave for a while"),
    "reply_greeting": ("say,zone,world", "answering someone who just said hi to the room"),
    "reply_question": ("say,zone,world", "answering (or failing to answer) a question someone asked in chat, in your own style"),
    "reply_gripe": ("say,zone,world", "reacting to someone complaining about the game"),
    "reply_joke": ("say,zone,world", "reacting to someone's joke or a lol"),
    "reply_brag": ("say,zone,world", "reacting to someone bragging about a level, a kill or a drop"),
    "reply_agree": ("say,zone,world", "reacting to someone's opinion or a plain statement, agreeing or not"),
    "reply_lfg": ("lfg,zone,world", "answering someone who is looking for a group"),
    "reply_trade": ("trade,zone,world", "answering someone advertising a sale or a purchase"),
    "reply_farewell": ("say,zone,world", "answering someone who says they are leaving or going afk"),
    "reply_thanks": ("say,zone,world", "answering someone who thanked you or the room"),
    "reply_banter": ("say,zone,world", "answering a tease or a mild insult from another player"),
    "reply_other": ("say,zone,world", "reacting to a line that fits nothing else, a remark you half followed"),
    "combat_focus": ("party", "in the middle of a fight you tell your party which enemy to kill first; the enemy is written as {mob} "
                              "exactly once, and it is a quick call or order, not a chat"),
    "combat_cc": ("party", "in the middle of a fight you tell your party which enemy is being crowd-controlled or should be left "
                           "alone for now; the enemy is written as {mob} exactly once, and it is a quick call or order"),
}

# Subjects chat keeps coming back to: (what to look for in a line, what the writer is told the subject is). A reply or an opener
# written for a subject is clearly about it, which is what stops a room of prewritten lines from sounding like it is not listening.
TOPICS = {
    "mining": (r"\b(copper|tin|iron|mithril|ore|mining|miner|vein|node|smelt\w*|prospect\w*)\b", "mining ore and metal, veins, smelting"),
    "herbalism": (r"\b(herb|herbs|herbalism|herbalist|flower|flowers|peacebloom|silverleaf)\b", "gathering herbs and flowers"),
    "fishing": (r"\b(fish|fishing|fisher\w*|lure|bobber|angler)\b", "fishing"),
    "cooking": (r"\b(cook|cooking|recipe|recipes|food|bandage|bandages|first aid)\b", "cooking, food and bandages"),
    "crafting": (r"\b(blacksmith\w*|enchant\w*|engineer\w*|tailor\w*|alchemy|alchemist|professions?|crafting|forge|potions?|leatherwork\w*)\b", "crafting professions and what they make"),
    "dungeons": (r"\b(dungeons?|instances?|boss|bosses|tank|tanks|healer|healers|dps|lfg|lfm|raid|raids|run)\b", "running dungeons and groups: tanks, healers, bosses"),
    "pvp": (r"\b(pvp|battlegrounds?|bgs?|duel\w*|arena|gank\w*|honou?r|world pvp)\b", "pvp, duels, battlegrounds and getting ganked"),
    "classes": (r"\b(mage|warrior|priest|rogue|druid|hunter|warlock|shaman|paladin|class|classes|spec|build|talents?|rotation)\b", "classes, specs and builds"),
    "gold": (r"\b(gold|silver|price|prices|auction|ah|sell|selling|buying|wts|wtb|expensive|cheap|broke|money|gold sink)\b", "gold, prices and the auction house"),
    "gear": (r"\b(gear|loot|looted|drop|drops|armou?r|weapon|weapons|epic|rare|upgrade|upgrades|item|items|bag|bags)\b", "gear, drops and upgrades"),
    "quests": (r"\b(quest|quests|turn in|objective|objectives|marker|chain)\b", "quests and quest chains"),
    "leveling": (r"\b(level|levels|leveling|levelling|xp|exp|grind|grinding|ding|dinged)\b", "levelling up and grinding"),
    "travel": (r"\b(flight|flight path|mount|mounts|ride|portal|boat|zeppelin|travel|map|lost|far|walk|run across)\b", "getting around: flight paths, mounts, maps, getting lost"),
    "lag": (r"\b(lag|laggy|latency|ping|disconnect\w*|server|servers|crash\w*|fps|rubber\w*|stutter\w*)\b", "lag, disconnects and the server"),
    "bugs": (r"\b(bug|bugs|bugged|patch|patches|update|nerf|nerfed|buff|buffed|broken|fix|fixed)\b", "bugs, patches and balance changes"),
    "mobs": (r"\b(mob|mobs|kill|killing|pull|pulling|aggro|elite|respawn\w*|camp|camping|farm|farming)\b", "mobs, pulling, respawns and camping spots"),
    "pets": (r"\b(pet|pets|companion|companions|minion)\b", "pets and companions"),
    "guilds": (r"\b(guild|guilds|friend|friends|invite|recruit\w*|social)\b", "guilds, friends and finding people to play with"),
    "life": (r"\b(tired|late|work|sleep|tonight|weekend|afk|brb|dinner|coffee|tea|bed|tomorrow)\b", "real life getting in the way: tiredness, work, dinner, bedtime"),
    "scenery": (r"\b(view|scenery|night|rain|pretty|music|graphics|beautiful|sunset|weather|zone)\b", "how the zone looks and sounds"),
    "newbies": (r"\b(new|noob|noobs|newbie|newbies|starter|beginner|first time|first day|tutorial)\b", "being new to the game and helping newcomers"),
    "factions": (r"\b(horde|alliance|faction|orc|orcs|elf|elves|dwarf|dwarves|human|humans|troll|trolls|undead|tauren|gnome|gnomes)\b", "the two factions and the races"),
}
_TOPIC_PATTERNS = {name: re.compile(pattern, re.I) for name, (pattern, _) in TOPICS.items()}
TOPIC_SITUATIONS = ("idle_topic", "reply_topic")


def topic_of(lines):
    """The subject the last few lines are about, or '' when none stands out. Newer lines count for more."""
    scores = collections.Counter()
    for age, text in enumerate(reversed([t for t in lines if t][-4:])):
        for name, pattern in _TOPIC_PATTERNS.items():
            hits = len(pattern.findall(text))
            if hits:
                scores[name] += hits * (4 - age)
    return scores.most_common(1)[0][0] if scores else ""


def base_situation(situation):
    """'reply_topic:mining' -> 'reply_topic'."""
    return str(situation).split(":", 1)[0]


def valid_situation(situation):
    base, _, topic = str(situation).partition(":")
    if base in TOPIC_SITUATIONS:
        return topic in TOPICS
    return base in SITUATIONS and not topic


# The stock playerbots text names (ai_playerbot_texts.name) that map onto an idle situation.
CATEGORY_SITUATION = {
    "broadcast_looting": "idle_loot", "broadcast_quest": "idle_quest", "broadcast_levelup": "idle_levelup",
    "broadcast_killed": "idle_brag", "suggest_something": "idle_general", "suggest_something_toxic": "idle_gripe",
    "suggest_faction": "idle_question", "suggest_instance": "idle_lfg", "suggest_trade": "idle_trade",
    "suggest_sell": "idle_trade", "suggest_quest": "idle_lfg",
}

# What a line said in chat is doing, read with plain rules: enough to find a reply that fits, and Jev refines the pick.
INTENT_RULES = [
    ("greeting", re.compile(r"^\W*(hi+|hey+|hello+|yo+|sup|hiya|howdy|o/|good (morning|evening|day)|how (is|are) (everyone|you|all)|hows? everyone)\b", re.I)),
    ("farewell", re.compile(r"\b(bye+|cya|gtg|brb|afk|later all|logging (off|out)|goodnight|gn all|going to bed)\b", re.I)),
    ("thanks", re.compile(r"\b(thanks?|thx|ty|cheers|appreciate it)\b", re.I)),
    ("lfg", re.compile(r"\b(lfg|lfm|need (a )?(tank|heal|healer|dps)|looking for (a )?(group|more)|anyone (up for|want to) (a )?(dungeon|run|group))\b", re.I)),
    ("trade", re.compile(r"\b(wts|wtb|selling|buying|for sale|pst|pm me)\b", re.I)),
    ("banter", re.compile(r"\b(noob|scrub|trash|git gud|bad at|you suck|u suck|loser|clown)\b", re.I)),
    ("brag", re.compile(r"\b(just (got|killed|finished|hit|reached|looted)|finally|dinged|level \d+|got the|first try)\b", re.I)),
    ("gripe", re.compile(r"\b(lag|laggy|nerf|nerfed|broken|bugged|bug|hate|annoying|stuck|rigged|ugh|wtf|ffs|worst|unfair)\b", re.I)),
    ("joke", re.compile(r"\b(lol|lmao|rofl|haha+|xd|kek)\b", re.I)),
    ("question", re.compile(r"(\?|^\W*(how|what|where|who|why|when|anyone|does|is|can|do you|which)\b)", re.I)),
]
NO_INTENT = "other"


def intents_of(text):
    """The intents of a line, most specific first; always ends with 'other'."""
    found = [name for name, pattern in INTENT_RULES if pattern.search(text or "")]
    if "question" in found and len(found) > 1:
        found.remove("question")
        found.append("question")
    return found + [NO_INTENT] if NO_INTENT not in found else found


def situation_for_category(category):
    """The idle situation for a stock text name such as broadcast_looting_item_rare, or '' when we have none."""
    name = str(category or "")
    for prefix in sorted(CATEGORY_SITUATION, key=len, reverse=True):
        if name.startswith(prefix):
            return CATEGORY_SITUATION[prefix]
    return ""


SCHEMA = """
CREATE TABLE IF NOT EXISTS bank (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    archetype TEXT NOT NULL,
    situation TEXT NOT NULL,
    text      TEXT NOT NULL,
    uses      INTEGER NOT NULL DEFAULT 0,
    UNIQUE (archetype, situation, text)
);
CREATE INDEX IF NOT EXISTS bank_lookup ON bank (archetype, situation);
"""


class Bank:
    def __init__(self, store):
        self.store = store
        with store.conn() as db:
            db.executescript(SCHEMA)
        self.lock = threading.Lock()
        self.recent = collections.defaultdict(lambda: collections.deque(maxlen=40))   # bot guid -> line ids it said
        self.job = {"running": False, "done": 0, "total": 0, "added": 0, "dropped": 0, "unreviewed": 0, "errors": 0, "last_error": "",
                    "cost_usd": 0.0}

    # ---- what is in the bank -------------------------------------------------------------------------

    def stats(self):
        with self.store.conn() as db:
            rows = db.execute("SELECT archetype, situation, COUNT(*) n FROM bank GROUP BY archetype, situation").fetchall()
            total = db.execute("SELECT COUNT(*) FROM bank").fetchone()[0]
        by_kind, by_situation, by_topic = collections.Counter(), collections.Counter(), collections.Counter()
        rp_race, rp_situation, rp_zone = collections.Counter(), collections.Counter(), collections.Counter()
        for row in rows:
            if rp_bank.is_rp_archetype(row["archetype"]):
                rp_race[row["archetype"].split(":")[1]] += row["n"]
                rp_situation[base_situation(row["situation"])] += row["n"]
                if row["situation"].startswith("rp_zone:"):
                    rp_zone[row["situation"].split(":", 1)[1]] += row["n"]
                continue
            by_kind[row["archetype"]] += row["n"]
            by_situation[base_situation(row["situation"])] += row["n"]
            if ":" in row["situation"]:
                by_topic[row["situation"].split(":", 1)[1]] += row["n"]
        rp_total = sum(rp_race.values())
        return {"total": total - rp_total, "by_kind": dict(by_kind), "by_situation": dict(by_situation), "by_topic": dict(by_topic),
                "situations": sorted(SITUATIONS) + list(TOPIC_SITUATIONS), "topics": sorted(TOPICS), "job": dict(self.job),
                "roleplay": {"total": rp_total, "by_race": dict(rp_race), "by_situation": dict(rp_situation), "by_zone": dict(rp_zone),
                             "situations": rp_bank.situation_names(), "topics": sorted(rp_bank.TOPICS)}}

    def samples(self, archetype, situation, limit=12):
        with self.store.conn() as db:
            rows = db.execute("SELECT text FROM bank WHERE archetype = ? AND situation = ? ORDER BY RANDOM() LIMIT ?",
                              (archetype, situation, int(limit))).fetchall()
        return [row["text"] for row in rows]

    def clear(self):
        with self.store.conn() as db:
            db.execute("DELETE FROM bank")

    def add_lines(self, archetype, situation, lines):
        added = 0
        with self.store.conn() as db:
            for text in lines:
                cursor = db.execute("INSERT OR IGNORE INTO bank (archetype, situation, text) VALUES (?, ?, ?)",
                                    (archetype, situation, text))
                added += cursor.rowcount
        return added

    # ---- writing the lines ---------------------------------------------------------------------------

    def start_generation(self, dispatch, profile, archetypes=None, situations=None, per_cell=30, workers=6, topics=None, mode="players"):
        """Fill the bank in the background. `dispatch(profile, request)` -> the model's text. Returns the job status.
        `mode` "roleplay" writes the in-character bank (see rp_bank.py) instead of the player-style one."""
        with self.lock:
            if self.job["running"]:
                return dict(self.job)
            if mode == "roleplay":
                # Safe to repeat, and to resume after a stop: a cell that already holds a fair share of lines is left as it is.
                with self.store.conn() as db:
                    have = {(row["archetype"], row["situation"]): row["n"]
                            for row in db.execute("SELECT archetype, situation, COUNT(*) n FROM bank WHERE archetype LIKE 'rp%' GROUP BY archetype, situation")}
                enough = max(1, int(int(per_cell) * 0.3))
                cells = [cell for cell in rp_bank.cells(archetypes, situations, topics) if have.get(cell, 0) < enough]
            else:
                kinds = [k for k in (archetypes or sorted(personas.ARCHETYPES)) if k in personas.ARCHETYPES]
                asked = situations or (sorted(SITUATIONS) + list(TOPIC_SITUATIONS))
                wanted = []
                for name in asked:        # "reply_topic" stands for every topic; "reply_topic:mining" for one
                    if base_situation(name) in TOPIC_SITUATIONS and ":" not in name:
                        wanted.extend("%s:%s" % (name, topic) for topic in (topics or sorted(TOPICS)) if topic in TOPICS)
                    elif valid_situation(name):
                        wanted.append(name)
                cells = [(k, s) for k in kinds for s in wanted]
            self.job = {"running": True, "done": 0, "total": len(cells), "added": 0, "dropped": 0, "unreviewed": 0, "errors": 0,
                        "last_error": "",
                        "cost_usd": 0.0}
        threading.Thread(target=self._run, args=(dispatch, profile, cells, int(per_cell), int(workers)), daemon=True).start()
        return dict(self.job)

    def _run(self, dispatch, profile, cells, per_cell, workers):
        def one(cell):
            kind, situation = cell
            write = rp_bank.write_request if rp_bank.is_rp_archetype(kind) else write_request
            try:
                try:
                    lines = parse_lines(dispatch(profile, write(kind, situation, per_cell)), situation)
                except ValueError:
                    # A small model now and then answers in prose or is cut off mid-array: one more try is cheaper than a gap.
                    lines = parse_lines(dispatch(profile, write(kind, situation, per_cell)), situation)
                added = self.add_lines(kind, situation, self._followable(dispatch, profile, situation, lines))
                with self.lock:
                    self.job["added"] += added
            except Exception as failure:  # noqa: BLE001 - one bad cell must not stop the run; it is counted and shown
                with self.lock:
                    self.job["errors"] += 1
                    self.job["last_error"] = str(failure)[:200]
            finally:
                with self.lock:
                    self.job["done"] += 1
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
                list(pool.map(one, cells))
        finally:
            with self.lock:
                self.job["running"] = False

    def _followable(self, dispatch, profile, situation, lines):
        """The lines a stranger can follow. A model reads the opening lines once more and the ones it cannot make sense of are
        dropped. A reply that is not a verdict keeps them all (and is counted): the bank should not stop filling for it."""
        base = base_situation(situation)
        if not lines or base not in (REVIEWED | rp_bank.REVIEWED):
            return lines
        review = rp_bank.review_request if base in rp_bank.REVIEWED else review_request
        flagged = unclear(dispatch(profile, review(lines)), len(lines))
        with self.lock:
            if flagged is None:
                self.job["unreviewed"] += len(lines)
            else:
                self.job["dropped"] += len(flagged)
        return lines if flagged is None else [line for number, line in enumerate(lines) if number not in flagged]

    # ---- choosing a line -----------------------------------------------------------------------------

    def candidates(self, archetype, situations, bot_guid, avoid=(), limit=12, rng=random.random):
        """Up to `limit` rows for these situations (in order of preference), least used first, none this bot said lately."""
        said = set(self.recent[bot_guid])
        avoid_texts = {a.strip().lower() for a in avoid}
        chosen, seen = [], set()
        with self.store.conn() as db:
            for situation in situations:
                rows = db.execute("SELECT id, text, situation, uses FROM bank WHERE archetype = ? AND situation = ? "
                                  "ORDER BY uses ASC, RANDOM() LIMIT 200", (archetype, situation)).fetchall()
                pool = [r for r in rows if r["id"] not in said and r["text"].strip().lower() not in avoid_texts
                        and r["id"] not in seen]
                # the least-used tier, shuffled, so that two bots with the same persona do not say the same thing
                rng_shuffle(pool, rng)
                for row in pool[:max(limit - len(chosen), 0)]:
                    chosen.append(row)
                    seen.add(row["id"])
                if len(chosen) >= limit:
                    break
        return chosen

    def used(self, bot_guid, line_id):
        self.recent[bot_guid].append(line_id)
        with self.store.conn() as db:
            db.execute("UPDATE bank SET uses = uses + 1 WHERE id = ?", (line_id,))


def rng_shuffle(items, rng):
    for i in range(len(items) - 1, 0, -1):
        j = int(rng() * (i + 1))
        items[i], items[j] = items[j], items[i]


def fill(text, player="", zone="", klass="", level="", link="", price="", friend="", mob=""):
    """The line with its placeholders filled. A placeholder with nothing to fill it is cut out and the gap closed."""
    values = {"player": player, "zone": zone, "class": klass, "level": str(level or ""), "link": link, "price": price, "friend": friend,
              "mob": mob}

    def swap(match):
        return values.get(match.group(1), "")
    out = PLACEHOLDER.sub(swap, text)
    out = re.sub(r"\s+([,.!?])", r"\1", out)
    out = re.sub(r"\s{2,}", " ", out)
    return out.strip(" ,")


def needs(text, what):
    return ("{%s}" % what) in text


def write_request(archetype, situation, count):
    """The chat request that asks a model for `count` lines for one kind of person in one situation."""
    kind = personas.ARCHETYPES[archetype]
    _, traits, styles, _, takes = kind
    base, _, topic = situation.partition(":")
    if base in TOPIC_SITUATIONS:
        subject = TOPICS[topic][1]
        if base == "idle_topic":
            channels, wanted = "say,zone,world", "starting a conversation about " + subject
        else:
            channels, wanted = "say,zone,world", "answering or reacting to someone who is talking about " + subject
    else:
        channels, wanted = SITUATIONS[situation]
    extra = ""
    if base in TOPIC_SITUATIONS:
        extra = ("Every line is clearly about this subject: %s. You may name the subject in plain words (ore, dungeon, mage, "
                 "gold, lag and the like) but not real places or characters. " % TOPICS[topic][1])
        if base == "idle_topic":
            extra += ("Each line starts a conversation from nothing and must make complete sense on its own: an opinion, a "
                      "question, a complaint or an observation about the subject. About half invite an answer. ")
        else:
            extra += ("Each line reacts to what someone just said about the subject without knowing exactly what it was: agree, "
                      "disagree, tease, share a similar experience or ask a follow-up; never give directions, numbers or facts "
                      "that could be wrong. ")
    if situation == "idle_sell":
        extra = ("Every line must contain {link} exactly once, where you would name the item (it already includes how many), and "
                 "{price} exactly once, where you would say what you want for it. Never write an item name or an amount yourself. "
                 "Add how to buy it ('pm me', 'whisper me', 'msg me'), and sound like whoever is typing: terse, friendly, hopeful. ")
    elif situation in LINK_SITUATIONS:
        extra = "Every line must contain {link} exactly once, where you would name it. "
    elif situation in MOB_SITUATIONS:
        extra = ("Every line must contain {mob} exactly once, where you would name the enemy. Never write an enemy's name yourself. "
                 "Each is a quick call to your party in the middle of a fight: 3 to 9 words, urgent, in your own voice, never a "
                 "question and never a conversation. You do not know what class you are in this fight: never say what you will do or "
                 "claim a role or ability for yourself ('I'll heal', 'my taunt', 'while I cast'). ")
    elif situation == "idle_levelup":
        extra = "Every line must contain {level} exactly once. "
    if situation in OPENERS:
        extra += ("These start a conversation out of nothing, so every line must make complete sense to someone who has read "
                  "nothing before it: a full thought, an opinion, a question or something you noticed. Never a reaction to "
                  "something unseen ('nice', 'quietly impressed', 'the text says east'), never an answer, never a fragment. "
                  "About half should be a question or a take that invites someone to answer. ")
    if base in REVIEWED:
        extra += ("Never point at something only you can see or know: no 'the objective', 'the next step', 'this quest', 'that "
                  "hill', 'it' with nothing named. Name a concrete thing, or keep it about the game in general. ")
    if situation.startswith("reply_") and base not in TOPIC_SITUATIONS:
        extra += ("These are replies to something another player just typed, and you do not know exactly what it was, so react "
                  "to its kind only: never give directions, facts, numbers, names or answers that could be wrong; agree, "
                  "shrug, tease, deflect or say you do not know. ")
    extra += ("Do not lean on one pet word or catchphrase: no single word or phrase may appear in more than four lines. ")
    system = (
        "You write chat lines for the public chat of a busy fantasy MMO realm, typed by real players. "
        "You will be given one kind of person and one situation, and you write %d different lines that person could type. "
        "Sound like a real player on a keyboard: casual, often lowercase, sometimes a typo, most lines under 12 words and none "
        "over %d characters. Vary the length, the first word and the mood; do not make every line a joke. Be decent: a line "
        "may be blunt, dry or grumpy about the game, but it never mocks, insults or brushes off the person it answers, and "
        "sarcasm is never aimed at them. No emoji, no quotation marks around a line, no em dashes or en dashes, no curly quotes, no hashtags. "
        "No slurs or hate, nothing sexual, no real-world politics. Do not name real dungeons, places or NPCs; keep it "
        "generic so it fits any zone. You may use these placeholders where natural, and only these: {player} (the person being "
        "answered), {zone}, {class}, {level}, {link}, {friend} (a friend you know by name), {mob} (an enemy). %s"
        "Answer with a JSON array of %d strings and nothing else." % (count, MAX_CHARS, extra, count))
    user = ("KIND OF PERSON: %s\nTRAITS: %s\nHOW THEY TYPE: %s\nTHEIR TAKES: %s\n\nSITUATION: %s\nCHANNEL: %s"
            % (archetype, ", ".join(traits), "; ".join(styles), "; ".join(takes), wanted, channels.split(",")[0]))
    return {"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "temperature": 1.0, "max_tokens": 2000}


def review_request(lines):
    """The chat request that asks a model which of these opening lines a stranger could not make sense of."""
    numbered = "\n".join("%d. %s" % (number, line) for number, line in enumerate(lines, 1))
    return {"messages": [{"role": "system", "content": REVIEW}, {"role": "user", "content": numbered}],
            "temperature": 0, "max_tokens": 400}


def unclear(reply, count):
    """Zero-based positions of the lines the reviewer flagged, or None when its reply is not a verdict at all."""
    found = re.search(r"\{.*\}", reply or "", re.S)
    try:
        flagged = json.loads(found.group(0))["confusing"] if found else None
    except (ValueError, KeyError, TypeError):
        return None
    if not isinstance(flagged, list):
        return None
    return {number - 1 for number in flagged if isinstance(number, int) and 1 <= number <= count}


def parse_lines(text, situation):
    """Clean lines from a model's JSON array. Anything that breaks a rule is dropped, never patched into a bad line."""
    roleplay = situation.startswith(rp_bank.PREFIX)
    limit = rp_bank.MAX_CHARS if roleplay else MAX_CHARS
    link_situations, mob_situations = (rp_bank.LINK_SITUATIONS, rp_bank.MOB_SITUATIONS) if roleplay else (LINK_SITUATIONS, MOB_SITUATIONS)
    friend_situations, self_only = (rp_bank.FRIEND_SITUATIONS, rp_bank.SELF_ONLY) if roleplay else (FRIEND_SITUATIONS, SELF_ONLY)
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start, end = text.find("["), text.rfind("]")
    if start >= 0 and end <= start:
        # Cut off mid-array (the reply hit its length limit): keep the strings that were finished.
        last = text.rfind('",')
        if last > start:
            text, end = text[:last + 1] + "]", last + 1
    if start < 0 or end <= start:
        raise ValueError("the model did not return a JSON array")
    items = json.loads(text[start:end + 1] if text.rstrip().endswith("]") else text[start:] + "]")
    lines, seen = [], set()
    for item in items:
        if not isinstance(item, str):
            continue
        line = filters.clean(item, limit).strip().strip('"').strip()
        if len(line) < 2 or line.lower() in seen:
            continue
        if re.search(r"\b(as an ai|language model|i am a bot|i'm a bot)\b", line, re.I):
            continue
        if roleplay and (rp_bank.META.search(PLACEHOLDER.sub("", line)) or "level" in PLACEHOLDER.findall(line)
                         or rp_bank.SELF_GENDERED.search(line)):
            continue      # a person in the world does not talk about levels, servers or bots, and any gender may say the line
        found = PLACEHOLDER.findall(line)
        if "link" not in found and OBJECTIVE.search(line):
            continue
        if situation in link_situations:
            if found.count("link") != 1:
                continue
        elif "link" in found:
            continue
        if situation == "idle_sell":
            if found.count("price") != 1:
                continue
        elif "price" in found:
            continue
        if situation in friend_situations:
            if found.count("friend") != 1:
                continue
        elif "friend" in found:
            continue
        if situation in self_only and ADDRESSES_SOMEONE.search(line):
            continue
        if situation in mob_situations:
            if found.count("mob") != 1 or ROLE_CLAIM.search(line):
                continue
        elif "mob" in found:
            continue
        if situation == "idle_levelup" and found.count("level") != 1:
            continue
        if re.search(r"\{[^}]*\}", PLACEHOLDER.sub("", line)):
            continue      # an invented placeholder would be said out loud
        seen.add(line.lower())
        lines.append(line)
    return lines
