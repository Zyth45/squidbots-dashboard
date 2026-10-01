"""Roleplay mode: every bot is a person in the world of Warcraft, with a life.

A bot gets a character the first time it is seen with its race and class (the worldserver module sends them): a calling that
suits its class and race, a temperament, a way of speaking, convictions, a goal, a few people in its life, a keepsake, a fear. The
same guid always rolls the same character. A model later writes the story out in full from those facts, and as the bot levels
it writes new chapters about what the person did in that stretch of life, so the story goes on growing and never contradicts
what came before. If no model is reachable, templates stand in, so the character is never blank.

What the model is shown each time a bot speaks (see `persona_block`): who it is, what its people believe and think of others,
its story so far, and where it is right now: the zone and its lore, what it is busy with and the errands in its log.

Everything here is plain data in lore.py and lore_names.py; this file holds the machinery.
"""
import json
import queue
import random
import re
import threading

from . import lore, lore_names

MODES = ("roleplay", "players")
CHANNEL_KINDS = ("say", "yell", "zone", "trade", "lfg", "world", "guild")

# What a calling suits, by what a class does. A calling that fits the class is chosen more often, never exclusively: a rogue who
# is a devout moon-priest's acolyte is a person worth talking to.
CLASS_FLAVOR = {
    "Warrior": "martial", "Paladin": "martial faith", "Hunter": "wild", "Rogue": "shadow", "Priest": "faith",
    "Death Knight": "martial shadow", "Shaman": "wild faith", "Mage": "arcane", "Warlock": "arcane shadow", "Druid": "wild",
    "Barbarian": "martial wild", "Witch Doctor": "wild arcane", "Felsworn": "martial shadow", "Witch Hunter": "martial shadow",
    "Stormbringer": "wild arcane", "Knight of Xoroth": "martial arcane", "Guardian": "martial", "Templar": "martial faith",
    "Bloodmage": "arcane", "Ranger": "wild", "Chronomancer": "arcane", "Necromancer": "arcane shadow", "Pyromancer": "arcane",
    "Cultist": "shadow arcane", "Starcaller": "wild faith arcane", "Sun Cleric": "faith", "Tinker": "craft arcane",
    "Venomancer": "shadow wild", "Reaper": "martial shadow", "Primalist": "wild", "Runemaster": "arcane martial",
}
CALLING_FLAVOR = {
    "knight-errant": "martial faith", "kirin-tor-scholar": "arcane", "forgeborn": "martial craft", "wildhammer": "wild martial",
    "grizzled-soldier": "martial", "tinker-engineer": "craft arcane", "gnomish-arcanist": "arcane", "tiny-hero": "martial shadow",
    "sentinel": "martial wild shadow", "druid-of-the-wild": "wild", "moon-devout": "faith", "vindicator": "martial faith",
    "naaru-priest": "faith", "azuremyst-scout": "wild shadow", "frostwolf-spirit": "wild faith", "blood-veteran": "martial",
    "warsong-grunt": "martial", "banshee-loyalist": "shadow martial arcane", "apothecary-minded": "arcane shadow",
    "scarlet-hunter": "martial shadow", "plainswalker": "wild", "earthmother-devout": "wild faith", "elder-seeker": "faith",
    "plains-protector": "martial", "voodoo-follower": "wild faith arcane", "echo-isles-warrior": "martial",
    "witch-doctor": "wild arcane shadow", "orgrimmar-hustler": "shadow", "magister-apprentice": "arcane",
    "farstrider": "wild martial", "blood-knight": "martial faith",
}

QUIRKS = [
    "hum when you think nobody can hear", "check your pack twice before every road", "talk to your weapon as though it listened",
    "never sit with your back to a door", "count your coins every night", "keep a small book of things you have seen",
    "cannot pass a stray animal without feeding it", "say a short blessing before you eat", "whittle when you are nervous",
    "laugh louder than the joke deserves", "tell the same three stories, and tell them well", "hate being thanked",
    "collect odd stones", "are superstitious about the number three", "rub an old scar when it rains",
    "stand a little too close when you talk", "name every road you walk", "keep a tally of the debts others owe you",
]
FEARS = [
    "fire", "being forgotten", "the dark under the earth", "turning back into what you once were", "the Scourge's rotting touch",
    "having already failed someone", "deep water", "growing old alone", "owing a debt you cannot repay", "crowded places",
    "the war never ending", "a quiet house", "your own temper",
]
KEEPSAKES = [
    "a chipped bone comb that was your mother's", "a small carved animal you cannot name", "a locket with a portrait too faded to read",
    "a single brass button from a uniform", "a dull coin with a hole through it", "a letter you have never opened",
    "a smooth river stone from home", "a bent ring you wear on a cord", "a scrap of banner cloth", "an old tin whistle",
    "a feather from a bird you never saw again", "a pressed flower in a small book",
]
MENTOR_STATUS = [
    "is long dead, and you carry what they taught you", "is still alive and still disappointed in you", "went away one winter and never came back",
    "is old now and lives quietly in {capital}", "was lost in the war, and you still argue with them in your head",
]
KIN_STATUS = [
    "waits for word from you in {home}", "has not written in years and you pretend not to mind", "is buried somewhere you cannot yet go back to",
    "is caught up in the war, and you worry", "thinks you should have stayed home",
]
RIVAL_STATUS = [
    "owes you a debt and knows it", "once shamed you in front of others and has never apologised", "took something of yours, which you mean to see returned",
    "was a friend once, and might be again", "is better than you at the thing you love most, and you cannot forgive it",
]
RELATIONS = [("sister", "female"), ("brother", "male"), ("mother", "female"), ("father", "male"), ("cousin", "any"),
             ("daughter", "female"), ("son", "male"), ("oldest friend", "any")]

# What a person knows and is at each stretch of life, so a character at level 5 does not talk like one at 75.
TIERS = [
    (9, "a raw beginner, newly out into the world, with everything still to learn"),
    (19, "a young adventurer who has seen a few real fights and is finding their feet"),
    (29, "an adventurer with some road behind them, no longer a novice"),
    (39, "a seasoned traveller whom locals have begun to ask for help"),
    (49, "a hardened veteran with real reputation"),
    (59, "a veteran whose name is known in more than one town"),
    (69, "one of the seasoned heroes of their people, who has walked through the Dark Portal or knows those who have"),
    (80, "a champion of their people, one of the heroes the war depends on, who has fought in Northrend"),
]

# One of these opens a chapter when a model cannot be asked. {z} is a zone from the right stretch of the road.
CHAPTER_OPENINGS = {
    0: ["You took your first steps as an adventurer in {z1}, and learned fast that the road is harder than any song made it.",
        "Your first season was spent in {z1}, doing small jobs for people who could not pay much and fighting things you were not ready for.",
        "You began in {z1}, with a borrowed pack, a head full of stories and no idea what you were doing."],
    1: ["You moved on to {z1} and {z2}, where the work was steadier and the dangers were not just animals.",
        "Around then you worked your way through {z1} and then {z2}, earning a little name for finishing what you were hired to do.",
        "{z1} was where you first lost a comrade, and {z2} was where you decided to keep going anyway."],
    2: ["You spent a hard stretch in {z1} and {z2}, long enough to stop feeling like a stranger there.",
        "In {z1} you made a friend, and in {z2} you made an enemy, and both of them still matter.",
        "The roads through {z1} and {z2} taught you which fights are worth taking and which are only pride."],
    3: ["In {z1} and {z2} you did work that mattered to real people, and some of them remembered you for it.",
        "You carried word and steel between {z1} and {z2}, and began to be known when you walked into an inn.",
        "{z1} nearly killed you once, and {z2} is where you recovered, with more patience than you came with."],
    4: ["You crossed {z1} and {z2}, places where the old wars still lie in the ground, and the weight of that stayed with you.",
        "In {z1} you saw something you do not speak of, and in {z2} you learned how to carry it.",
        "{z1} and {z2} gave you hard work and harder questions about what you are fighting for."],
    5: ["You fought through {z1} and {z2}, where the Scourge and the old horrors are never far, and you came out harder.",
        "In {z1} you stood where armies have stood, and in {z2} you buried someone you meant to protect.",
        "{z1} and {z2} are places you will not forget: you went in hopeful and came out clear-eyed."],
    6: ["You went through the Dark Portal and into {z1} and {z2}, a broken world that makes the old wars look small.",
        "In {z1} you met people who have lost everything and fight on anyway, and in {z2} you were tested for it.",
        "Outland, with {z1} and {z2}, changed how you see the war, and what you think the Burning Legion is capable of."],
    7: ["You sailed for Northrend and fought your way through {z1} and {z2}, in the cold shadow of the Lich King.",
        "In {z1} and {z2} you stood with the Argent Crusade and the Ebon Blade against the Scourge, and the dead did not stay quiet.",
        "Northrend taught you what fear is: {z1} and {z2} are places where the cold is almost the least of your worries."],
}

NOT_IN_WORLD = re.compile(r"\b(?:levels?|quests?|xp|experience points|players?|servers?|mmo|game|ai|language model|npcs?|dungeon finder)\b", re.I)
SECOND_PERSON = [(re.compile(r"\bthemselves\b", re.I), "yourself"), (re.compile(r"\btheir\b", re.I), "your"),
                 (re.compile(r"\bthem\b", re.I), "you"), (re.compile(r"\bthey\b", re.I), "you")]

CONTEXT_LINE = re.compile(r"roleplay_context\s*=\s*(\{.*\})")


def first_name(name):
    """The name the character gives: a placeholder surname ("Alte Bot") is not part of it, and a real one ("Elorin Moonwhisper") is kept."""
    text = re.sub(r"\s+Bot$", "", (name or "").strip(), flags=re.I)
    return text or (name or "").strip()


def a_an(word):
    return "an" if word[:1].lower() in "aeiou" else "a"


def second_person(text):
    for pattern, replacement in SECOND_PERSON:
        text = pattern.sub(replacement, text)
    text = re.sub(r"^was\b", "were", text)
    return text


def _clip(value, limit):
    text = "".join(ch for ch in str(value or "") if ch >= " ").replace("[", "(").replace("]", ")").strip()
    return text[:limit]


def clean_context(raw):
    """The facts about where a bot is and what it is doing, from whatever the module sent: bounded, plain text, or {} when it says
    nothing usable. `race` and `klass` are the names lore.py knows; anything else is dropped."""
    if not isinstance(raw, dict):
        return {}
    ctx = {}
    race = _clip(raw.get("race"), 30)
    if race in lore.RACES:
        ctx["race"] = race
    klass = _clip(raw.get("klass") or raw.get("class"), 30)
    if klass:
        ctx["klass"] = klass
    gender = str(raw.get("gender") or "").lower()
    if gender in ("male", "female"):
        ctx["gender"] = gender
    elif gender in ("0", "1"):
        ctx["gender"] = "male" if gender == "0" else "female"
    try:
        ctx["level"] = max(0, min(80, int(raw.get("level") or 0)))
    except (TypeError, ValueError):
        ctx["level"] = 0
    for key in ("zone", "area", "doing"):
        if raw.get(key):
            ctx[key] = _clip(raw[key], 60)
    quests = raw.get("quests")
    if isinstance(quests, list):
        ctx["quests"] = [_clip(q, 70) for q in quests[:5] if _clip(q, 70)]
    if raw.get("zone_id") and not ctx.get("zone"):
        ctx["zone"] = lore.ZONE_IDS.get(int(raw["zone_id"]), "") if str(raw["zone_id"]).isdigit() else ""
    if not ctx.get("klass") and str(raw.get("class_id") or "").isdigit():
        ctx["klass"] = lore.CLASS_IDS.get(int(raw["class_id"]), "")
    return ctx


def context_from_text(text):
    """The roleplay context the module put in a system prompt (a `roleplay_context={...}` line), or {}."""
    found = CONTEXT_LINE.search(text or "")
    if not found:
        return {}
    try:
        return clean_context(json.loads(found.group(1)))
    except ValueError:
        return {}


def _fit(klass, calling):
    mine = set(CLASS_FLAVOR.get(klass, "").split())
    theirs = set(CALLING_FLAVOR.get(calling, "").split())
    return 2 if not theirs else 1 + 3 * len(mine & theirs)


def _pick(rng, options):
    return options[rng.randrange(len(options))]


def generate(guid, name, ctx):
    """A character for this guid, race and class: the same inputs always give the same one. None when the race is unknown."""
    race, klass = ctx.get("race"), ctx.get("klass")
    if race not in lore.RACES or not klass:
        return None
    rng = random.Random("rp:%d" % guid)
    info = lore.RACES[race]
    gender = ctx.get("gender") or _pick(rng, ["male", "female"])
    keys = list(lore.CALLINGS[race])
    calling = rng.choices(keys, weights=[_fit(klass, key) for key in keys])[0]
    label, who, traits, speech, convictions, events, goal = lore.CALLINGS[race][calling]
    home = _pick(rng, [info["start"], info["start"], info["capital"].split(" (")[0]])
    mentor = lore_names.person_name(race, _pick(rng, ["male", "female"]), rng)
    relation, relation_gender = _pick(rng, RELATIONS)
    kin = lore_names.person_name(race, relation_gender if relation_gender != "any" else _pick(rng, ["male", "female"]), rng)
    rival = lore_names.person_name(race, _pick(rng, ["male", "female"]), rng)
    for _ in range(10):
        if len({mentor, kin, rival, first_name(name)}) == 4:
            break
        rival = lore_names.person_name(race, _pick(rng, ["male", "female"]), rng)
        kin = lore_names.person_name(race, relation_gender if relation_gender != "any" else _pick(rng, ["male", "female"]), rng)
    fills = {"capital": info["capital"].split(" (")[0], "home": home}
    keepsake, fear, quirk = _pick(rng, KEEPSAKES), _pick(rng, FEARS), _pick(rng, QUIRKS)
    facts = [
        "You were born in %s." % home,
        " ".join("You %s." % second_person(event).rstrip(".") for event in events),
        "Your teacher was %s, who %s." % (mentor, _pick(rng, MENTOR_STATUS).format(**fills)),
        "%s is your %s, who %s." % (kin, relation, _pick(rng, KIN_STATUS).format(**fills)),
        "%s %s." % (rival, _pick(rng, RIVAL_STATUS)),
        "You carry %s." % keepsake,
        "You %s." % quirk,
        "You fear %s." % fear,
        "What you want most: %s." % second_person(goal),
    ]
    chosen_traits = rng.sample(traits, min(3, len(traits)))
    return {
        "name": name, "race": race, "klass": klass, "gender": gender, "calling": calling,
        "traits": ", ".join(chosen_traits), "speech": "%s; %s" % (info["speech"], speech),
        "convictions": "; ".join(convictions), "goal": second_person(goal), "quirk": quirk, "fear": fear, "keepsake": keepsake,
        "home": home, "facts": " ".join(facts), "story": "",
        "chattiness": rng.randint(35, 85),
    }


def archetype_of(character):
    """The line bank's key for this character: one per race and calling, which is what the bank is written for."""
    return "rp:%s:%s" % (character["race"], character["calling"])


def calling_label(race, calling):
    entry = lore.CALLINGS.get(race, {}).get(calling)
    return entry[0] if entry else calling


def tier_text(level):
    for limit, text in TIERS:
        if level <= limit:
            return text
    return TIERS[-1][1]


# Where each people's first two stretches of life are spent: their own starting land and the next one over.
EARLY_ZONES = {
    "Human": (["Elwynn Forest"], ["Westfall", "Redridge Mountains"]), "Dwarf": (["Dun Morogh"], ["Loch Modan", "Dun Morogh"]),
    "Gnome": (["Dun Morogh"], ["Loch Modan", "Dun Morogh"]), "Night Elf": (["Teldrassil"], ["Darkshore", "Teldrassil"]),
    "Draenei": (["Azuremyst Isle"], ["Bloodmyst Isle", "Azuremyst Isle"]), "Orc": (["Durotar"], ["The Barrens", "Durotar"]),
    "Troll": (["Durotar"], ["The Barrens", "Durotar"]), "Tauren": (["Mulgore"], ["The Barrens", "Mulgore"]),
    "Undead": (["Tirisfal Glades"], ["Silverpine Forest", "Tirisfal Glades"]), "Blood Elf": (["Eversong Woods"], ["Ghostlands", "Eversong Woods"]),
}
PEOPLE = {"Human": "humans", "Dwarf": "dwarves", "Gnome": "gnomes", "Night Elf": "night elves (the kaldorei)", "Draenei": "draenei",
          "Orc": "orcs", "Undead": "Forsaken", "Tauren": "tauren", "Troll": "Darkspear trolls", "Blood Elf": "blood elves (the quel'dorei)"}


def bracket_zones(race, bracket, rng):
    """One or two zones where a person of this race spends this stretch of life."""
    if bracket < 2 and race in EARLY_ZONES:
        return list(EARLY_ZONES[race][bracket])
    faction = lore.faction_of(race) or "Alliance"
    zones = lore.LEVEL_ZONES.get(faction, lore.LEVEL_ZONES["Alliance"]).get(bracket, [])
    return rng.sample(zones, min(2, len(zones)))


def chapter_fallback(character, bracket, rng=None):
    """A chapter written from templates: where this stretch of life was spent, and what it taught."""
    rng = rng or random.Random("chapter:%d:%d" % (character["bot_guid"], bracket))
    zones = bracket_zones(character["race"], bracket, rng)
    if not zones:
        return ""
    return _pick(rng, CHAPTER_OPENINGS[bracket]).format(z1=zones[0], z2=zones[-1])


def sheet(character):
    """The character's facts as plain lines, for the prompts that write more of the story."""
    race = character["race"]
    lines = ["Race: %s (%s)." % (race, lore.faction_of(race)),
             "Calling: %s, and by trade %s." % (calling_label(race, character["calling"]), lore.class_text(character["klass"]) or character["klass"]),
             "Temperament: %s." % character["traits"], "How they talk: %s." % character["speech"],
             "Convictions: %s." % character["convictions"], "Facts of their life: %s" % character["facts"]]
    if character.get("gender"):
        lines.insert(1, "Gender: %s." % character["gender"])
    return "\n".join(lines)


def story_request(character):
    system = ("You write the life story of one fictional person in the world of Warcraft, in the age of the Lich King. Use only what the "
              "world's lore supports; never name a famous hero as a friend or family member of this person. Write in the second person "
              "('You were...'), past tense, five to seven sentences and under 900 characters, as one paragraph with no heading. Use every "
              "fact you are given, keep their names and relationships exactly, and add texture: one specific scene from childhood or "
              "training, one regret, and what their home smelled or sounded like. Never mention levels, experience, quests, players, "
              "servers or a game. Never write the person's own name. Plain text only.")
    return {"messages": [{"role": "system", "content": system}, {"role": "user", "content": sheet(character)}], "temperature": 0.9,
            "max_tokens": 600}


def chapter_request(character, bracket, previous, zones):
    low, high = lore.LEVEL_BRACKETS[bracket]
    where = "; ".join(lore.zone_text(zone) or zone for zone in zones)
    system = ("You write one chapter of the life of a fictional person in the world of Warcraft, in the age of the Lich King. Write in the "
              "second person ('You...'), past tense, two or three sentences and under 420 characters, plain text. Describe what happened "
              "to them during this stretch of their life: one concrete event involving a place or kind of person from the zones given, "
              "and one thing that changed in them. It must follow from their story so far and never contradict it. Do not resolve "
              "their life's goal. Never mention levels, experience, quests, players, servers or a game, and never write their own name.")
    stage = {0: "just beginning as an adventurer", 1: "a young adventurer", 2: "an adventurer with some road behind them",
             3: "a seasoned traveller", 4: "a hardened veteran", 5: "a famed veteran", 6: "a hero, now beyond the Dark Portal",
             7: "a champion of their people, now in Northrend"}[bracket]
    user = "%s\n\nTHEIR STORY SO FAR:\n%s\n\nTHIS STRETCH OF LIFE (they are %s, roughly ages of %d to %d of their adventuring):\n%s" % (
        sheet(character), "\n".join(previous) or "(nothing yet: this is the first chapter)", stage, low, high, where or "the road")
    return {"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "temperature": 0.9, "max_tokens": 300}


def usable_text(text, limit):
    """A model's paragraph that may become part of a person's story: whole, in the world, within the limit. Otherwise ''."""
    text = " ".join(str(text or "").split()).strip().strip('"')
    if len(text) < 40 or NOT_IN_WORLD.search(text):
        return ""
    if len(text) > limit:
        head = text[:limit]
        stops = [match.end() for match in re.finditer(r"[.!?](?=\s|$)", head)]
        if not stops:
            return ""
        text = head[:stops[-1]]
    return text


# ----------------------------------------------------------------------------------------------------------------------
# What a model is shown
# ----------------------------------------------------------------------------------------------------------------------

def _views(race):
    views = lore.RACES[race]["views"]
    return "; ".join("%s: %s" % (other, view) for other, view in views.items())


def story_text(character, chapters, compact=False):
    parts = []
    if character.get("story"):
        parts.append(character["story"])
    elif character.get("facts"):
        parts.append(character["facts"])
    if character.get("story") and character.get("facts") and not compact:
        parts.append("Facts you never contradict: %s" % character["facts"])
    shown = chapters[-3:] if compact else chapters
    for chapter in shown:
        parts.append(chapter["text"])
    return "\n".join(parts)


def now_text(character, ctx, level_known=True):
    lines = []
    level = ctx.get("level") or character.get("level") or 0
    if level and level_known:
        lines.append("In your own life you are %s." % tier_text(level))
    zone = ctx.get("zone") or character.get("zone") or ""
    text = lore.zone_text(zone, ctx.get("area") or "") if zone else ""
    if text:
        lines.append("You are in %s" % text)
    elif zone:
        lines.append("You are in %s%s." % (zone, (", near " + ctx["area"]) if ctx.get("area") and ctx["area"] != zone else ""))
    if ctx.get("doing"):
        lines.append("Right now you are %s." % ctx["doing"])
    if ctx.get("quests"):
        lines.append("The errands you have taken on, in your own life (speak of them as tasks, commissions or duties, never as 'quests'): %s."
                     % "; ".join(ctx["quests"]))
    return "\n".join(lines)


def persona_block(character, ctx, chapters, rules, guard="", actions=True, compact=False, typing="", action_rule="", max_chars=0):
    """The system text that makes a model this person. `compact` is for the short ambient lines, where the full world would cost
    more than the answer."""
    race, info = character["race"], lore.RACES[character["race"]]
    name = first_name(character["name"])
    label = calling_label(race, character["calling"])
    gender = {"male": " man", "female": " woman"}.get(character.get("gender"), "")
    klass = lore.class_text(character["klass"])
    out = ["WHO YOU ARE (you are a living person in the world of Warcraft, never a player at a keyboard)"]
    out.append("You are %s, %s %s%s: %s. By trade you are %s%s." % (
        name or "a traveller", a_an(race), race, gender, label, a_an(character["klass"]) + " " + character["klass"],
        (", " + klass) if klass else ""))
    origin, seen = lore.class_lore(character["klass"])
    if origin:
        out.append("Where your craft comes from: %s. How people see it: %s." % (origin, seen))
    out.append("Your people: the %s of the %s, whose capital is %s and whose ruler is %s." % (PEOPLE[race], info["faction"], info["capital"], info["ruler"]))
    out.append("Temperament: %s." % character["traits"])
    out.append("How you talk: %s." % character["speech"])
    out.append("What you believe: %s Your own convictions: %s." % (info["beliefs"], character["convictions"]))
    out.append("What you want most: %s" % character["goal"])
    if not compact:
        out.append("A habit of yours: you %s. You fear %s. You carry %s." % (character["quirk"], character["fear"], character["keepsake"]))
        out.append("")
        out.append("THE WORLD AS YOU KNOW IT")
        out.append(lore.ERA)
        out.append("What your people have been through: %s" % " ".join(info["history"]))
        out.append("Your homeland: %s. What you love of home: %s." % (info["homeland"], ", ".join(info["culture"][:4])))
        out.append("How your people see others: %s." % _views(race))
        out.append("Those your people fight: %s." % ", ".join(info["enemies"]))
        out.append("Sayings you might use: %s" % " / ".join(info["sayings"]))
        out.append("Crafts you may meet on the road, besides the old ones: %s." % lore.crafts_note())
    story = story_text(character, chapters, compact)
    if story:
        out.append("")
        out.append("YOUR STORY SO FAR (this is your life; draw on it, never contradict it)")
        out.append(story)
    now = now_text(character, ctx)
    if now:
        out.append("")
        out.append("RIGHT NOW")
        out.append(now)
    out.append("")
    out.append("HOW YOU SPEAK AND ACT")
    out.append(rules.replace("{max}", str(max_chars or 250)))
    if typing:
        out.append(typing)
    if actions and action_rule:
        out.append(action_rule + " Say it in your own words and in character when you do.")
    if guard:
        out.append(guard)
    return "\n".join(out)


def voice_line(character):
    """One line for the fast lane, where the model only picks an action and, sometimes, a short remark."""
    return ("When you speak, speak as %s, %s %s, in the voice of this person: %s. Keep battle talk short and in the world, never "
            "mentioning a game." % (first_name(character["name"]) or "this person", a_an(character["race"]), character["race"],
                                    character["speech"]))


RP_REGISTERS = [
    ("plain", 30, "Answer plainly, the way a person of your people would, in character."),
    ("warm", 16, "Answer warmly, glad of company, in character."),
    ("curious", 14, "Show real curiosity about the other person or their road, and ask one thing back, in character."),
    ("wry", 10, "Answer with a dry remark that only someone of your temperament would make."),
    ("guarded", 8, "Be a little guarded, as your people are with strangers, but not rude."),
    ("story", 8, "Let one small detail of your own past or homeland slip into the answer."),
    ("lore", 8, "Mention something your people believe or know about the place or the matter at hand."),
    ("brief", 8, "Reply in a few words, in character: 'Aye.', 'Well met.', 'So it goes.'"),
]


def register(rng):
    pick = rng() * sum(weight for _, weight, _ in RP_REGISTERS)
    for _, weight, text in RP_REGISTERS:
        pick -= weight
        if pick <= 0:
            return text
    return RP_REGISTERS[0][2]


WHERE = {
    "say": "speaking aloud: only those within about thirty yards can hear you",
    "yell": "shouting: everyone around, a hundred yards or so, can hear you",
    "zone": "calling out across the whole land",
    "trade": "the market's call-board",
    "lfg": "the call-board where travellers find company",
    "world": "a shout carried to every corner of the world",
    "guild": "the fireside talk of your guild-fellows: only they can hear you, and you all know one another",
}

HOW = ("HOW TO REPLY\n"
       "Say ONE thing aloud, in character, at most %d characters: usually one or two short sentences. Answer what was just said and "
       "keep the scene going: stay on its subject, answer any question (briefly and honestly, and if you do not know, say so as "
       "your character would), and now and then add something of your own or ask something back. Only the first to answer a "
       "greeting welcomes the newcomer; if someone already has, say something of your own or speak to the other person instead. "
       "Vary how you begin and never repeat what others said. You may address someone by name. A brief *action* in asterisks is "
       "allowed now and then. No quotation marks around the line, no markdown, and never mention an AI, a bot or a game. If you truly have "
       "nothing to add, or the line is not for you, answer exactly (silent).")


REWRITE = ("YOUR LINE\nYou were about to say this stock line aloud (the situation: %s):\n  \"%s\"\n"
           "Say the same thing the way YOU would, as this person living in the world: the same facts, but in your own words, attitude "
           "and voice, using the world's own words (an errand, not a quest). %s"
           "One line, at most %d characters, no quotation marks, no markdown, never mention an AI, a bot or a game. "
           "Do not copy the stock wording.")


class Rp:
    """Makes characters, remembers them and keeps their stories growing. `writer(request)` -> text or None asks a model."""

    def __init__(self, store, writer=None, background=True):
        self.store = store
        self.writer = writer
        self.background = background
        self.lock = threading.Lock()
        self.jobs = queue.Queue()
        self.pending = set()
        self.worker = None
        self.stats = {"stories": 0, "chapters": 0, "failures": 0}

    # ---- the character -------------------------------------------------------------------------------

    def character(self, guid, name, ctx):
        """The bot's character: made when first seen with a race and a class, updated with where it is now. None when the game has
        not said what it is (an older module) and nothing is stored."""
        ctx = ctx or {}
        row = self.store.rp_character(guid)
        if row is None:
            made = generate(guid, name, ctx)
            if made is None:
                return None
            self.store.save_rp_character(guid, made, "generated", made["chattiness"], ctx.get("level", 0), ctx.get("zone", ""))
            row = self.store.rp_character(guid)
        elif name and row["name"] != name:
            # Renamed (to something that suits its race, say): the story is about the person, not the name on the character.
            self.store.set_rp_field(guid, "name", name)
            row["name"] = name
        elif ctx.get("klass") and row["klass"] != ctx["klass"] and row["source"] == "generated":
            self.store.set_rp_field(guid, "klass", ctx["klass"])
            row["klass"] = ctx["klass"]
        if ctx.get("level") or ctx.get("zone"):
            level = ctx.get("level") or row["level"]
            zone = ctx.get("zone") or row["zone"]
            if level != row["level"] or zone != row["zone"]:
                self.store.set_rp_state(guid, level, zone)
                row["level"], row["zone"] = level, zone
        self._grow(row)
        return self.as_persona(row)

    def as_persona(self, row):
        """A persona-shaped dict, so the rest of the service (the bank, the dashboard's lists, memory) treats it like any other bot."""
        return {"rp": True, "bot_guid": row["bot_guid"], "name": row["name"], "archetype": archetype_of(row), "traits": row["traits"],
                "speech_style": row["speech"], "interests": "", "opinions": "", "backstory": row["story"] or row["facts"],
                "chattiness": row["chattiness"], "source": row["source"], "enabled": 1, "muted": 0, "race": row["race"],
                "klass": row["klass"], "calling": row["calling"], "gender": row["gender"], "level": row["level"], "zone": row["zone"],
                "row": row}

    # ---- the story ------------------------------------------------------------------------------------

    def _grow(self, row):
        """Make sure the story has every chapter the bot's level calls for, and the full backstory. Templates first, so a prompt is
        never short; a model's version replaces a template when it arrives."""
        guid, level = row["bot_guid"], int(row["level"] or 0)
        if not level:
            return
        current = lore.bracket_of(level)
        if row["chapters_to"] < current:
            have = {chapter["bracket"] for chapter in self.store.rp_chapters(guid)}
            for bracket in range(0, current + 1):
                if bracket in have:
                    continue
                text = chapter_fallback(row, bracket)
                if text:
                    self.store.save_rp_chapter(guid, bracket, lore.LEVEL_BRACKETS[bracket][0], text, "template")
                    self._schedule(("chapter", guid, bracket))
            self.store.set_rp_chapters_to(guid, current)
        if not row["story"] and row["source"] == "generated":
            self._schedule(("story", guid, 0))

    def _schedule(self, job):
        if self.writer is None or self.store.setting("rp_ai_story") != "1":
            return
        with self.lock:
            if job in self.pending or len(self.pending) > 400:
                return
            self.pending.add(job)
        if not self.background:
            self._run(job)
            return
        self.jobs.put(job)
        with self.lock:
            if self.worker is None or not self.worker.is_alive():
                self.worker = threading.Thread(target=self._work, daemon=True)
                self.worker.start()

    def _work(self):
        while True:
            try:
                job = self.jobs.get(timeout=30)
            except queue.Empty:
                return
            self._run(job)

    def _run(self, job):
        kind, guid, bracket = job
        try:
            row = self.store.rp_character(guid)
            if not row:
                return
            if kind == "story":
                text = usable_text(self.writer(story_request(row)), 900)
                if text and self.store.rp_character(guid)["source"] == "generated":
                    self.store.set_rp_field(guid, "story", text)
                    self.stats["stories"] += 1
                else:
                    self.stats["failures"] += 1
            else:
                chapters = self.store.rp_chapters(guid)
                previous = [c["text"] for c in chapters if c["bracket"] < bracket]
                zones = bracket_zones(row["race"], bracket, random.Random("chapter:%d:%d" % (guid, bracket)))
                text = usable_text(self.writer(chapter_request(row, bracket, [row["story"] or row["facts"]] + previous, zones)), 420)
                if text:
                    self.store.save_rp_chapter(guid, bracket, lore.LEVEL_BRACKETS[bracket][0], text, "ai")
                    self.stats["chapters"] += 1
                else:
                    self.stats["failures"] += 1
        except Exception as failure:  # noqa: BLE001 - the template stays; a failed model call must never reach a player
            self.stats["failures"] += 1
            print("Roleplay story job failed: %s: %s" % (type(failure).__name__, failure), flush=True)
        finally:
            with self.lock:
                self.pending.discard(job)

    def chapters(self, guid):
        return self.store.rp_chapters(guid)

    def block(self, persona, ctx, rules, guard="", actions=True, compact=False, typing="", action_rule="", max_chars=0):
        row = persona["row"]
        return persona_block(row, ctx, self.store.rp_chapters(row["bot_guid"]), rules, guard, actions, compact, typing, action_rule, max_chars)


def parse_channels(text):
    """The channel kinds in a comma list, in a fixed order, or None when it names something that is not a channel."""
    kinds = [part.strip().lower() for part in str(text or "").split(",") if part.strip()]
    if any(kind not in CHANNEL_KINDS for kind in kinds):
        return None
    return [kind for kind in CHANNEL_KINDS if kind in kinds]
