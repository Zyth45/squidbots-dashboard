"""The roleplay line bank: prewritten in-character lines, based on Warcraft lore, for every race and calling.

It sits in the same table as the player-style bank (see bank.py) under its own archetype keys:

    rp:<Race>:<calling>   what one kind of character says in each situation (40 of them: four callings for each of ten races)
    rpz:<Race>            what a person of that race says about each zone they might be standing in (situation rp_zone:<Zone>)

A line is spoken aloud by someone living in the world, so none of them mentions levels, dungeon finders, servers or any of the
other words a player at a keyboard would use. They may use {player}, {zone}, {class}, {friend}, {link} and {mob} where the
situation allows, and nothing else.
"""
import collections
import re

from . import lore

MAX_CHARS = 150
PREFIX = "rp_"

# name -> (channels it suits, what the writer is asked for)
SITUATIONS = {
    "rp_idle_muse": ("say,guild", "a thought about the world, the age or the road, spoken aloud to nobody in particular; it makes sense with no context"),
    "rp_idle_homesick": ("say,guild", "a pang of memory for home, a smell, a song or a person left behind, without naming anyone; nothing is invented that needs explaining"),
    "rp_idle_creed": ("say,guild", "something your people or you believe, a proverb, an oath or a saying, said because it came to mind"),
    "rp_idle_work": ("say,guild", "a remark about the errand, the road or the work you are about, in general terms (never an objective, a target or a place only you can see)"),
    "rp_idle_scenery": ("say,guild", "a remark about the land around you, the weather, the hour or the sounds, using {zone} at most once; it stands alone"),
    "rp_idle_zone": ("say,guild", "something you know or have heard about {zone} (its dangers, folk, history or rumours), told to whoever is nearby; {zone} is written exactly once"),
    "rp_idle_others": ("say,guild", "a remark, fair or prejudiced as your people are, about the other peoples of the world"),
    "rp_idle_war": ("say,guild", "a worry, a grudge or a hope about the war: the Scourge, the Legion, the Alliance and the Horde"),
    "rp_idle_camp": ("say,guild", "food, drink, a fire or a bed: something a traveller says at an inn or a campfire"),
    "rp_idle_hail": ("say,yell", "hailing someone nearby: a greeting, a question about their road, or an offer of company; it makes sense with no context"),
    "rp_idle_question": ("say,guild", "asking those nearby for news or advice in the way of your people: the roads, rumours, a safe place to sleep, what is happening in the land"),
    "rp_idle_story": ("say,guild", "the opening line of a tale or a memory you are about to tell; it names a concrete thing and invites a question"),
    "rp_idle_humor": ("say,guild", "a dry or warm joke in your people's way, about yourself, the road or the world; kind, never at a stranger's expense"),
    "rp_idle_prayer": ("say,guild", "a short blessing, invocation or ritual phrase of your people, said quietly or aloud"),
    "rp_idle_friend": ("say,guild", "talking to a friend by name: {friend} is written exactly once, and you greet them, tease them or ask how they fare; it makes sense with no context"),
    "rp_idle_quest": ("say,guild", "you have just taken on a task or an errand and mention it; the task is written as {link} exactly once"),
    "rp_idle_loot": ("say,guild", "you have just found or been given something and react to it; the item is written as {link} exactly once"),
    "rp_idle_stronger": ("say,guild", "you feel stronger, steadier or more seasoned after a hard-won fight or a long road; no numbers and no mention of levels"),
    "rp_idle_farewell": ("say,guild", "saying you are about to rest, turn in for the night or go on your way"),
    "rp_reply_greeting": ("say,guild", "answering someone who has just greeted you or the company"),
    "rp_reply_question": ("say,guild", "answering, or failing to answer, a question put to you, as your character would"),
    "rp_reply_gripe": ("say,guild", "answering someone complaining about the road, the weather, the war or their luck: sympathy, a shrug or a worse story"),
    "rp_reply_joke": ("say,guild", "reacting to someone's joke or a laugh"),
    "rp_reply_brag": ("say,guild", "reacting to someone boasting of a deed, a kill or a find"),
    "rp_reply_agree": ("say,guild", "reacting to an opinion or a plain statement, agreeing, doubting or adding to it"),
    "rp_reply_lfg": ("say,guild", "answering someone looking for company for a dangerous errand or a journey: offering to go, hesitating or refusing"),
    "rp_reply_trade": ("say,guild", "answering someone offering or asking for goods: haggling, interest or a polite no"),
    "rp_reply_farewell": ("say,guild", "answering someone who says they are leaving or turning in"),
    "rp_reply_thanks": ("say,guild", "answering someone who has thanked you"),
    "rp_reply_banter": ("say,guild", "answering a tease or a mild insult in your people's way: a sharp retort, a laugh or a cold stare, never cruel"),
    "rp_reply_other": ("say,guild", "reacting to something you only half followed, as someone who does not want to be rude"),
    "rp_reply_friend": ("say,guild", "answering your friend {friend}, without knowing exactly what they said: {friend} is written exactly once, warm, teasing or curious, never giving facts"),
    "rp_reply_warning": ("say,guild", "answering someone who warns of a danger or asks for help against a threat: alarm, resolve or caution"),
    "rp_reply_sorrow": ("say,guild", "answering someone who is grieving, tired or low: comfort in your people's way"),
    "rp_combat_focus": ("party", "in the middle of a fight you call to your companions which foe to strike first; the foe is written as {mob} exactly once, and it is a quick shout, never a conversation"),
    "rp_combat_cc": ("party", "in the middle of a fight you call to your companions which foe is held at bay or should be left alone for now; the foe is written as {mob} exactly once, and it is a quick shout"),
}

# Subjects talk keeps returning to in a world like this: (what to look for in a line, what the writer is told the subject is).
TOPICS = {
    "war": (r"\b(war|wars|battle|battles|fight\w*|army|armies|soldier\w*|siege|blood|slain|warriors?)\b", "the war, battles and soldiering"),
    "scourge": (r"\b(scourge|undead|plague\w*|lich king|arthas|undeath|zombie\w*|ghoul\w*|northrend|naxxramas|death knights?)\b", "the Scourge, the plague and the Lich King"),
    "legion": (r"\b(legion|demons?|fel|outland|warlocks?|dark portal|illidan|kil'jaeden|felguard)\b", "the Burning Legion, demons and Outland"),
    "faith": (r"\b(light|holy|prayer|pray\w*|elune|earthmother|loa|ancestors?|spirits?|faith|gods?|blessing\w*|priests?)\b", "faith, the Light, the spirits and the ancestors"),
    "magic": (r"\b(magic|arcane|mages?|spells?|kirin tor|dalaran|sunwell|enchant\w*|runes?|wizards?|sorcer\w*)\b", "magic, mages and the arcane"),
    "home": (r"\b(home|homeland|family|kin|mother|father|sister|brother|village|hearth|childhood|born)\b", "home, family and where you came from"),
    "road": (r"\b(road|roads|travel\w*|journey|path|trail|wander\w*|inns?|innkeeper|ride|ships?|zeppelins?|boat|gryphons?|wyverns?|lost)\b", "the road, travel, inns and getting around the world"),
    "craft": (r"\b(forge|smith\w*|craft\w*|trade|merchants?|market|gold|coins?|silver|copper|mines?|mining|herbs?|herbalism|alchemy|tailor\w*|skinn\w*|prices?)\b", "crafts, trades, coin and the market"),
    "beasts": (r"\b(beasts?|wolf|wolves|boars?|bears?|hunt\w*|pets?|mounts?|horses?|rams?|kodos?|raptors?|animals?)\b", "beasts, hunting and mounts"),
    "honor": (r"\b(honou?r|oaths?|vows?|duty|loyal\w*|betray\w*|trust|promises?|glory|shame)\b", "honour, oaths, duty and trust"),
    "peace": (r"\b(peace|truce|treaty|alliance|horde|allies|enemy|enemies|rivals?|neighbou?rs?|kingdoms?)\b", "the Alliance, the Horde and whether peace can last"),
    "death": (r"\b(death|die|dead|died|graves?|buried|mourn\w*|ghosts?|funeral|lost someone)\b", "death, loss and remembering the dead"),
    "tavern": (r"\b(ale|beer|wine|mead|tavern|drinks?|drunk|feast|stew|bread|supper|campfire|camp)\b", "food, drink, fire and a bed at an inn"),
    "history": (r"\b(history|ancient|old days|legend\w*|lore|sundering|titans?|elders?|ruins?|relics?|archaeolog\w*)\b", "history, legends, ruins and the old days"),
    "weather": (r"\b(weather|rain|storm|snow|cold|wind|night|sunset|dawn|moon|stars?|season|winter|summer)\b", "the weather, the hour and the sky"),
    "danger": (r"\b(danger\w*|beware|bandits?|raiders?|monsters?|murlocs?|gnolls?|kobolds?|worgen|ogres?|threat\w*|wolves)\b", "the dangers of the road: bandits, beasts and worse"),
}
_TOPIC_PATTERNS = {name: re.compile(pattern, re.I) for name, (pattern, _) in TOPICS.items()}
TOPIC_SITUATIONS = ("rp_idle_topic", "rp_reply_topic")

# Openers are said out of nothing to people who have read nothing: a second model reads them before they are kept.
OPENERS = {"rp_idle_muse", "rp_idle_homesick", "rp_idle_creed", "rp_idle_work", "rp_idle_scenery", "rp_idle_zone", "rp_idle_others",
           "rp_idle_war", "rp_idle_camp", "rp_idle_hail", "rp_idle_question", "rp_idle_story", "rp_idle_humor", "rp_idle_friend",
           "rp_zone"}
REVIEWED = OPENERS | {"rp_idle_topic", "rp_idle_prayer"}
LINK_SITUATIONS = {"rp_idle_quest", "rp_idle_loot"}
MOB_SITUATIONS = {"rp_combat_focus", "rp_combat_cc"}
FRIEND_SITUATIONS = {"rp_idle_friend", "rp_reply_friend"}
SELF_ONLY = {"rp_idle_loot", "rp_idle_stronger"}
# What no person in this world would say: the words of a player at a keyboard.
META = re.compile(r"\b(levels?|level-up|xp|servers?|mmo|npcs?|dungeon finder|dps|aggro|cooldowns?|respawn\w*|nerf\w*|patch\w*|laggy?|"
                  r"afk|brb|lol|lmao|rofl|gg|wts|wtb|lfg|lfm|ooc|irl|bots?|ai|ping|fps|hitbox|spawn\w*|mobs?|gear score)\b", re.I)

# Places, peoples and events from after the age of the Lich King: nobody in this world has heard of them, and a model that knows the later game
# leaks them now and then.
ANACHRONISM = re.compile(r"\b(pandaria|pandaren|garrosh|cataclysm|shadowlands|maldraxxus|revendreth|ardenweald|boralus|azerite|dracthyr|evokers?|"
                         r"dragon isles|nazjatar|zuldazar|warlords of draenor|mists of pandaria|battle for azeroth|dragonflight expansion)\b", re.I)

# An action about oneself ("*tightens her cloak*") would be wrong half the time: the same line is said by men and women.
SELF_GENDERED = re.compile(r"\*[^*]*\b(?:she|he|her|his|hers|him|herself|himself)\b[^*]*\*", re.I)

REVIEW = ("You review lines of in-character speech for characters in the world of Warcraft, typed into a chat window. Each line is said "
          "out of nowhere: nobody spoke before it and the people reading it have seen nothing else. Flag every line a stranger could NOT make "
          "sense of: it refers to something the reader cannot know (an unnamed errand, person, place, object, or 'it', 'that', 'this' with "
          "nothing to point at), answers or reacts to something unseen, or is a fragment. Also flag any line that talks like a player at a "
          "keyboard rather than a person in the world (mentioning levels, servers, dungeon finders, cooldowns, bots). Lines about the world in "
          "general, that name a concrete thing, or ask something anyone could answer are fine. Placeholders such as {zone}, {class} and {friend} "
          'are filled in later, so they are fine. Reply with a JSON object {"confusing": [line numbers]} and nothing else.')


def topic_of(lines):
    """The subject the last few lines are about, or '' when none stands out. Newer lines count for more."""
    scores = collections.Counter()
    for age, text in enumerate(reversed([t for t in lines if t][-4:])):
        for name, pattern in _TOPIC_PATTERNS.items():
            hits = len(pattern.findall(text))
            if hits:
                scores[name] += hits * (4 - age)
    return scores.most_common(1)[0][0] if scores else ""


def is_rp_archetype(archetype):
    return str(archetype).startswith("rp:") or str(archetype).startswith("rpz:")


def archetypes():
    """Every roleplay archetype key, one per race and calling."""
    return ["rp:%s:%s" % (race, calling) for race in lore.RACES for calling in lore.CALLINGS[race]]


def zone_archetypes():
    return ["rpz:%s" % race for race in lore.RACES]


def situation_names():
    return sorted(SITUATIONS) + list(TOPIC_SITUATIONS) + ["rp_zone"]


def valid_situation(situation):
    base, _, detail = str(situation).partition(":")
    if base in TOPIC_SITUATIONS:
        return detail in TOPICS
    if base == "rp_zone":
        return detail in lore.ZONES
    return base in SITUATIONS and not detail


def cells(kinds=None, situations=None, topics=None):
    """[(archetype, situation)] to write. `situations` may name 'rp_idle_topic' or 'rp_reply_topic' (every topic), 'rp_zone' (every zone,
    written once per race), or a single one such as 'rp_zone:Westfall'; nothing means everything."""
    chosen = list(kinds) if kinds else archetypes() + zone_archetypes()
    asked = list(situations) if situations else sorted(SITUATIONS) + list(TOPIC_SITUATIONS) + ["rp_zone"]
    out = []
    for kind in chosen:
        if kind.startswith("rpz:"):
            for name in asked:
                if name == "rp_zone":
                    out.extend((kind, "rp_zone:%s" % zone) for zone in lore.ZONES)
                elif name.startswith("rp_zone:") and valid_situation(name):
                    out.append((kind, name))
            continue
        if not kind.startswith("rp:") or kind.count(":") != 2:
            continue
        for name in asked:
            if name in TOPIC_SITUATIONS:
                out.extend((kind, "%s:%s" % (name, topic)) for topic in (topics or sorted(TOPICS)) if topic in TOPICS)
            elif valid_situation(name) and not name.startswith("rp_zone"):
                out.append((kind, name))
    return out


def _calling_sheet(archetype):
    _, race, calling = archetype.split(":")
    info = lore.RACES[race]
    label, who, traits, speech, convictions, events, goal = lore.CALLINGS[race][calling]
    return "\n".join([
        "RACE: %s (%s). Capital: %s. Homeland: %s." % (race, info["faction"], info["capital"], info["homeland"]),
        "CALLING: %s, %s." % (label, who),
        "TEMPERAMENT: %s." % ", ".join(traits),
        "HOW THEY SPEAK: %s; %s." % (info["speech"], speech),
        "BELIEFS: %s Convictions: %s." % (info["beliefs"], "; ".join(convictions)),
        "WHAT THEY LOVE OF HOME: %s." % ", ".join(info["culture"]),
        "HOW THEIR PEOPLE SEE OTHERS: %s." % "; ".join("%s: %s" % item for item in info["views"].items()),
        "THEY FIGHT: %s." % ", ".join(info["enemies"])])


def write_request(archetype, situation, count):
    """The chat request that asks a model for `count` lines for one kind of character in one situation."""
    base, _, detail = situation.partition(":")
    extra = ""
    if archetype.startswith("rpz:"):
        race = archetype.split(":", 1)[1]
        info = lore.RACES[race]
        entry = lore.ZONES[detail]
        holder = entry[2]
        home = {"Alliance": "Alliance", "Horde": "Horde"}.get(holder)
        place = "%s: %s" % (detail, lore.zone_text(detail))
        stance = ""
        if home and home != info["faction"]:
            stance = "This land is held by the other side, so they are wary and hostile in it. "
        elif home == info["faction"]:
            stance = "This land is held by their own side, so they feel at home or protective of it. "
        user = ("RACE: %s (%s). Capital: %s.\nHOW THEY SPEAK: %s.\nBELIEFS: %s\nTHEY FIGHT: %s.\n\nPLACE: %s\n\nSITUATION: standing in %s and saying "
                "something aloud about it, to whoever is near.\nCHANNEL: say" % (
                    race, info["faction"], info["capital"], info["speech"], info["beliefs"], ", ".join(info["enemies"]), place, detail))
        extra = ("Every line is clearly about this place and could only be said here: name real landmarks, folk, creatures or history from "
                 "its lore (the ones in PLACE and others you are sure belong to it), or a rumour, a memory or a grumble about it. You may "
                 "write {zone} for the zone's name. %sNever mention an errand, an objective or a target, and never invent a person's name. " % stance)
        who = "one kind of person from this people"
    else:
        wanted_text = ""
        if base in TOPIC_SITUATIONS:
            subject = TOPICS[detail][1]
            wanted_text = ("starting a conversation about " if base == "rp_idle_topic" else "answering or reacting to someone who is talking about ") + subject
            if base == "rp_idle_topic":
                extra = ("Every line is clearly about the subject (%s) and starts a talk from nothing, so it makes complete sense on its own: "
                         "an opinion, a question, a worry or an observation. About half invite an answer. " % subject)
            else:
                extra = ("Every line reacts to what someone just said about the subject (%s) without knowing exactly what it was: agree, doubt, "
                         "share a similar memory or ask a follow-up; never give directions, numbers or facts that could be wrong. " % subject)
        else:
            _, wanted_text = SITUATIONS[situation]
        channels = "say" if base not in SITUATIONS else SITUATIONS[base][0].split(",")[0]
        user = "%s\n\nSITUATION: %s\nCHANNEL: %s" % (_calling_sheet(archetype), wanted_text, channels)
        who = "one kind of character"
        if situation in LINK_SITUATIONS:
            extra = "Every line must contain {link} exactly once, where you would name it. Never write the thing's name yourself. "
        elif situation in MOB_SITUATIONS:
            extra = ("Every line must contain {mob} exactly once, where you would name the foe. Never write a foe's name yourself. Each is a "
                     "shout of 3 to 9 words in your own voice: urgent, never a question. You do not know what trade you follow in this fight: "
                     "never claim a role or an ability for yourself ('I'll heal', 'my shield'). ")
        elif situation in FRIEND_SITUATIONS:
            extra = ""
        elif situation == "rp_idle_stronger":
            extra = "Never write a number. "
        if situation.startswith("rp_reply_") and base not in TOPIC_SITUATIONS:
            extra += ("These answer something another person just said, and you do not know exactly what it was, so react to its kind only: "
                      "never give directions, facts, numbers, names or answers that could be wrong; agree, doubt, shrug, tease or say you do "
                      "not know. ")
        if base in OPENERS | {"rp_idle_topic"}:
            extra += ("The line is said to a room that has read nothing before it: never point at something only you can see ('the objective', "
                      "'that hill', 'it' with nothing named); name a concrete thing or keep it about the world in general. ")
    if not archetype.startswith("rpz:") and base not in ("rp_idle_zone", "rp_idle_scenery"):
        extra += ("You do not know where you are standing: never say or hint where you are right now, and name a place only as part of the "
                  "world in general (a homeland, a famous city, a road everyone knows), never as 'here'. ")
    extra += "No single word or phrase may appear in more than four lines. "
    system = (
        "You write lines of in-character speech for the people of the world of Warcraft in the age of the Lich King, typed into a chat "
        "window by someone roleplaying them. You are given %s and one situation, and you write %d different lines that person could say "
        "aloud. Speak as a person of this world and this people, in their voice, with their beliefs, dialect and prejudices, never as a player "
        "at a keyboard: no levels, experience, servers, dungeon finders, cooldowns, bots, addons, chat slang or the word 'quest' as a game term "
        "(say errand, task, bounty or duty). Warcraft lore is welcome (places, gods, peoples, wars, creatures) where the situation allows, "
        "but only what a person like this would know and never an invented famous name. Most lines are under 20 words and none is over %d "
        "characters; vary the length, the first word and the mood, and about one line in four carries a brief *action* in asterisks, "
        "at its start or end (*tightens a cloak*). The same line is said by men and women, so never use he, she, his or her in an action "
        "and never say 'milord' or 'milady'; address people as 'friend', 'traveller' or in your people's own words. No emoji, no quotation marks around a line, no em dashes or en dashes, no curly quotes, no hashtags. No slurs "
        "or hate, nothing sexual, no real-world politics. A line may be blunt, grumpy or prejudiced as the character is, but it never "
        "mocks or brushes off the person it answers. You may use these placeholders where natural, and only these: {player} (the person being "
        "spoken to), {zone}, {class}, {friend} (a friend you know by name), {link}, {mob}. %s"
        "Answer with a JSON array of %d strings and nothing else." % (who, count, MAX_CHARS, extra, count))
    return {"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "temperature": 1.0, "max_tokens": 2400}


def review_request(lines):
    numbered = "\n".join("%d. %s" % (number, line) for number, line in enumerate(lines, 1))
    return {"messages": [{"role": "system", "content": REVIEW}, {"role": "user", "content": numbered}], "temperature": 0, "max_tokens": 400}
