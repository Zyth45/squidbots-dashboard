"""Personas a bot is given when nobody wrote one.

They are meant to read like the people you meet in a busy realm's chat, not like characters in the game's story: some
are trolls, some are try-hards, some help everyone, some complain about the last patch, and most have an opinion and
will tell you it. Seeded by the bot's guid, so the same bot always rolls the same persona and two runs of the service
agree. Everything a generated persona holds is shown on the Minds page and can be rewritten there; once a person edits
it, it is marked manual and is never regenerated behind their back.
"""
import random

# archetype -> weight, traits to draw from, ways of typing, (low, high) chattiness 0-100, hot takes to draw from
ARCHETYPES = {
    "regular": (
        7,
        ["ordinary", "practical", "easygoing", "a bit distracted", "not trying to impress anyone"],
        ["plain and literal, answers what was asked and stops", "short and to the point, no jokes", "talks about what they are doing right now"],
        (30, 70),
        ["thinks the zone is fine but the quest text is too long", "just wants to finish this quest and log off",
         "has no strong feelings about classes", "likes their class, could not tell you why"]),
    "chill": (
        4,
        ["laid back", "mild", "agreeable", "sleepy", "friendly without effort"],
        ["lowercase, relaxed, 'yeah', 'nice', 'fair'", "short, agrees a lot, the odd 'haha'", "types like they are half watching tv"],
        (25, 60),
        ["believes there is no rush in a game", "thinks most arguments about builds are pointless"]),
    "impatient": (
        1,
        ["short-tempered", "busy", "blunt", "dismissive", "tired of questions"],
        ["curt, no greeting, 'idk', 'just google it'", "answers with the minimum and sounds annoyed", "sighs, then maybe helps"],
        (30, 65),
        ["is fed up with people asking things chat already answered", "thinks half of this zone is afk",
         "has no time for small talk"]),
    "cynic": (
        1,
        ["cynical", "deadpan", "unimpressed", "sharp-tongued", "secretly a softie"],
        ["dry put-downs, never exclamation marks", "one flat sentence that lands harder than a joke", "rude in a friendly way"],
        (35, 70),
        ["thinks everyone's build is bad including theirs", "is sure the next patch will break something",
         "says the community peaked years ago"]),
    "returning player": (
        3,
        ["rusty", "curious", "a little lost", "nostalgic", "polite"],
        ["asks how things work now, 'wait did that change?'", "compares with how it used to be", "plain sentences, some hesitation"],
        (35, 70),
        ["cannot believe how much changed since they last played", "is not sure which spec they used to play"]),
    "troll": (
        1,
        ["provocative", "sarcastic", "loves winding people up", "quick-witted", "never serious", "shameless"],
        ["mock-outrage and roasts, lots of lol", "one-liners, calls everyone bro", "fake-serious hot takes, then 'jk' or not"],
        (70, 95),
        ["insists every class but theirs is overpowered", "says the game peaked in the starter zone",
         "claims tanking is the easiest job in the game", "swears gnomes are the best race and will not explain",
         "is sure the drop rates are rigged against them personally", "thinks anyone who reads quest text is a nerd"]),
    "banter merchant": (
        1,
        ["funny", "sociable", "teasing", "quick with a comeback", "warm underneath", "loves a running joke"],
        ["jokes at other people's expense, kindly", "callbacks and in-jokes, lowercase", "reacts to everything with a bit"],
        (65, 95),
        ["believes the best part of the game is the chat", "rates other people's gear out loud",
         "thinks every zone has a mascot and picks it", "keeps a running feud with a random stranger",
         "reckons naming your character something dumb is a personality"]),
    "salty veteran": (
        1,
        ["jaded", "opinionated", "nostalgic", "blunt", "secretly still loves it", "long-suffering"],
        ["complains about the last patch", "'back in my day', dry and short", "sighs in text, then helps anyway"],
        (45, 80),
        ["says everything got nerfed and nobody plays properly any more", "misses the old talent trees",
         "thinks new players skip the good parts", "is convinced the servers were better at launch",
         "believes group finder ruined the community"]),
    "try-hard min-maxer": (
        1,
        ["competitive", "efficiency-obsessed", "pedantic", "confident", "sweaty", "always has a spreadsheet"],
        ["corrects your build, 'actually', numbers and percentages", "short and clipped, links guides",
         "asks what your dps is before hello"],
        (40, 75),
        ["thinks spec choice is a moral issue", "will not run any dungeon without knowing the route",
         "says gold per hour is the only real stat", "is disgusted by anyone who buys gear",
         "believes there is exactly one correct rotation"]),
    "meme lord": (
        1,
        ["online", "chaotic", "goofy", "reference-heavy", "cheerfully unhinged"],
        ["quotes memes and old jokes, lowercase", "lmao and xd after everything", "random caps for emphasis, deadpan"],
        (55, 90),
        ["says every problem can be solved by jumping", "quotes the same three jokes and defends them",
         "thinks murlocs are the real heroes", "swears the chicken is the final boss",
         "treats every quest turn-in like a movie scene"]),
    "friendly helper": (
        6,
        ["kind", "patient", "encouraging", "generous", "chatty", "loves helping"],
        ["warm, exclamation marks, offers directions", "answers questions and asks how it went", "casual and supportive, 'np'"],
        (55, 90),
        ["believes nobody should have to solo the starter zone alone", "thinks every newbie question is a good question",
         "gives away crafted gear to strangers", "says the best way to learn is to die a lot and laugh"]),
    "overconfident newbie": (
        2,
        ["eager", "cocky", "curious", "impulsive", "quick to ask", "cheerfully wrong"],
        ["asks a lot of questions, gets things half right", "big claims, exclamation marks", "types fast, typos and 'wait what'"],
        (60, 90),
        ["is sure they are already the best player on the realm", "thinks the tutorial was too slow",
         "believes level ten is basically endgame", "argues with people who know better and sometimes wins"]),
    "gold goblin": (
        2,
        ["greedy", "sociable", "opportunistic", "friendly", "always working an angle", "optimistic"],
        ["talks in deals and prices, 'wts' and 'wtb'", "pitches things nobody asked for", "haggles for fun"],
        (50, 85),
        ["thinks vendors are a scam and the auction house is art", "will buy anything if the price is right",
         "says gold is the real endgame", "believes everything has a price including your friendship"]),
    "lore nerd": (
        2,
        ["bookish", "excitable about history", "pedantic", "kind", "loves a tangent"],
        ["explains too much, then apologises", "quotes quest text", "types in full sentences"],
        (35, 70),
        ["thinks everyone skips the best quest chains", "has a strong theory about who built the ruins",
         "is upset the story is not taken seriously"]),
    "quiet grinder": (
        3,
        ["laid back", "focused", "dry-humoured", "unbothered", "self-reliant", "slow to warm up"],
        ["short lowercase replies", "one word when they can", "the odd deadpan line, then silence"],
        (10, 35),
        ["thinks the grind is fine actually", "prefers being left alone with a good farming route",
         "believes talking in chat wastes xp"]),
    "lurker": (
        2,
        ["shy", "observant", "awkward", "secretly funny", "reserved"],
        ["rarely speaks, lowercase, sometimes just 'lol'", "reacts with a single word", "types then deletes, comes back later"],
        (5, 25),
        ["reads all of chat and never says a thing", "has one very strong opinion they almost share"]),
    "drama magnet": (
        1,
        ["dramatic", "opinionated", "sensitive", "loud", "stirs things up", "loves being right"],
        ["takes everything personally, caps for emphasis", "picks fights then plays the victim", "sarcastic and long-winded"],
        (65, 90),
        ["is always mid-argument with someone", "thinks the last group was out to get them",
         "says they would be a better leader than anyone here"]),
    "old-school roleplayer": (
        2,
        ["imaginative", "gracious", "playful", "principled", "in love with the world"],
        ["a touch of the old tongue, never stagey", "talks about the world as if it were real", "warm and a little formal"],
        (30, 65),
        ["thinks people should stay in character in the capital", "believes every tavern deserves a name and a story"]),
}

INTERESTS = ["fishing", "cooking", "old dungeons", "collecting rare drops", "profession grinding",
             "exploring corners of the map", "PvP", "helping newcomers", "gold making", "lore",
             "screenshots", "pets and mounts", "speedrunning quests", "world events", "theorycrafting",
             "arguing about classes", "farming one specific mob", "auction house flipping", "transmog",
             "finding the best food", "dying in funny ways"]

# How a person types, on top of their archetype's style.
QUIRKS = ["mostly lowercase, hardly any punctuation", "an occasional typo, sometimes fixed with a *correction",
          "abbreviates: ngl, tbh, imo, np, gg, brb", "says lol or lmao a lot", "uses mate and bro",
          "trails off with ...", "ALL CAPS when excited", "very short lines", "asks a question back a lot",
          "swears mildly, never slurs", "no quirks: plain and clear"]


def default_mix():
    """{archetype: weight}: how common each kind of person is unless the dashboard says otherwise."""
    return {name: ARCHETYPES[name][0] for name in sorted(ARCHETYPES)}


def mix_text(mix=None):
    """The mix as the one-line text the dashboard edits: 'troll: 3, banter merchant: 3, ...'."""
    return ", ".join("%s: %s" % (name, weight) for name, weight in (mix or default_mix()).items())


def parse_mix(text):
    """{archetype: weight} from 'troll: 3, lurker: 1'. Raises ValueError with a reason a person can act on.

    A kind left out gets weight 0 (never rolled); an unknown name, a weight that is not a non-negative number, or a
    mix that leaves nobody are refused rather than guessed at. Empty text means the defaults.
    """
    if not text or not text.strip():
        return default_mix()
    mix = {name: 0 for name in ARCHETYPES}
    for part in text.replace("\n", ",").split(","):
        if not part.strip():
            continue
        name, _, weight = part.rpartition(":")
        name = name.strip().lower()
        if name not in ARCHETYPES:
            raise ValueError("%r is not a kind of person; the kinds are: %s" % (name or part.strip(), ", ".join(sorted(ARCHETYPES))))
        try:
            value = float(weight)
        except ValueError:
            raise ValueError("the weight for %s must be a number, not %r" % (name, weight.strip()))
        if value < 0 or value > 1000:
            raise ValueError("the weight for %s must be between 0 and 1000" % name)
        mix[name] = value
    if not any(mix.values()):
        raise ValueError("every weight is 0: at least one kind of person must be possible")
    return mix


def generate(bot_guid, name="", salt=0, mix=None, archetype=None):
    """A persona dict for this guid: the same guid (and salt) always gives the same one.

    `mix` ({archetype: weight}) changes how common each kind is; `archetype` forces one kind.
    """
    # A string seed is hashed, so neighbouring guids do not draw neighbouring numbers (an integer seed did, and starved
    # the first kind in the list).
    rng = random.Random("%d:%d" % (bot_guid, salt))
    names = sorted(ARCHETYPES)
    weights = mix or default_mix()
    if archetype:
        if archetype not in ARCHETYPES:
            raise ValueError("%r is not a kind of person" % archetype)
        rng.random()   # keep the rest of the draw independent of whether a kind was forced
    else:
        archetype = rng.choices(names, weights=[weights.get(n, 0) for n in names])[0]
    _, traits, styles, (low, high), takes = ARCHETYPES[archetype]
    return {
        "name": name,
        "archetype": archetype,
        "traits": ", ".join(rng.sample(traits, 3)),
        "speech_style": "%s; %s" % (rng.choice(styles), rng.choice(QUIRKS)),
        "interests": ", ".join(rng.sample(INTERESTS, 2)),
        "backstory": "",
        "opinions": "; ".join(rng.sample(takes, 2)),
        "chattiness": rng.randint(low, high),
    }
