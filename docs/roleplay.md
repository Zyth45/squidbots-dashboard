# Roleplay mode: bots that are people in the world of Warcraft

Out of the box a bot talks like a player at a keyboard (banter, hot takes, LFG and Trade adverts). **Roleplay mode, the default,
makes every bot a character in the lore instead:** a person of its race and calling, with a backstory that grows as it levels, who
knows the zone it is standing in and what it is doing there, who talks in character in `/say`, `/yell` and guild chat and stays out
of the realm channel, General, Trade and Looking For Group. You can talk to them, roleplay with them, and they stay in character.

Switch it on the **Minds page, Chat style**: *Roleplay* or *Fake players*. The game follows within a few seconds, with no restart.
Nothing of the fake-player side is removed: its personalities, line bank and settings are kept, and switching back restores them.

This needs the game module's roleplay support (`synthiqbots`, `docs/roleplay.md`): it tells the service each bot's race, class,
gender, level, zone and open errands, and it keeps the bots quiet in the channels a character would not use. A bot the game has not yet
described to the service simply talks as a player until it has.

## What a character is

The first time the service is told a bot's race and class it makes a character, deterministically from the bot's guid (so a bot is the
same person after a restart, and two runs agree):

- **A calling** that suits its race and class: four per race, forty in all. A human may be a knight-errant, a plague refugee, a
  farmstead child or a Kirin Tor scholar; a night elf a Sentinel, a druid of the Cenarion Circle, a devotee of Elune or a long-memoried
  elder; an orc a spirit-walker, a veteran of the Dark Portal wars, a Durotar-born warrior or a Warsong grunt. A paladin is more likely
  a knight-errant than a farm child, never certainly.
- **A temperament, a way of speaking, convictions and a goal**, from the calling and the people's own voice (a dwarf's "lad" and "by
  me beard", a troll's "mon", a Forsaken's dry remarks about being dead).
- **A life**: where they were born, three formative events, a teacher, a relative, a rival (named, with names that suit the race), a
  keepsake, a habit, a fear. These are the *facts*, which the story and every chapter must agree with.
- **A story and chapters.** A model writes the backstory in full from the facts, and as the bot levels it writes a new chapter for each
  stretch of life (levels 1-9, 10-19, 20-29, ... 70-80): where they were, what happened, what changed in them, consistent with
  everything before. Until a model has written a piece (or with no model at all) a template stands in, so a prompt is never
  short of a life. A bot first seen at level 45 gets chapters for every stretch up to 45.
- **A race-suited name** (optional): see *Names* below.

Everything in the character is shown on the bot's sheet (Minds page, *A bot's mind*), where you can rewrite any of it. A character
you edit is marked *written by you* and is never rewritten behind your back.

## The Conquest of Azeroth crafts in the lore

The realm's twenty-one extra classes (ids 12 to 32: Barbarian, Witch Doctor, Felsworn, Witch Hunter, Stormbringer, Knight of Xoroth,
Guardian, Templar, Bloodmage, Ranger, Chronomancer, Necromancer, Pyromancer, Cultist, Starcaller, Sun Cleric, Tinker, Venomancer, Reaper,
Primalist, Runemaster) are written into the world rather than left as game terms (`CLASS_LORE` in `mind/lore.py`). Each has what the
craft does, where it comes from and who teaches it, and how ordinary people see it: a Necromancer practises the Scourge's art taken up
by the living and the Forsaken, and is shunned in Stormwind and merely avoided in Undercity; a Runemaster carries the rune-lore of the
dwarves and their Earthen forebears; a Chronomancer studied beside the Bronze Dragonflight's mortal students. Any race may follow any of
them. A character is told its own craft's origin and reputation, and (in the full prompt) one line on each of the others it may meet on
the road, so bots can talk about each other's crafts in the world's terms. These are our own tie-ins between the classes and
Warcraft's established peoples and places, not canon; edit the table to change them.

## What the model is shown

Every time a bot speaks, the model gets one system prompt (`mind/rp.py`, `persona_block`): who the bot is; its people's history,
beliefs, view of the other peoples and enemies; its story so far; a few lines of its own bank as examples of how it sounds; and **right now**:
the zone and its lore (`mind/lore.py` holds 70 zones), the area, what it is doing, the time of day and any holiday being kept (Brewfest is
on right now on the test realm), the errands in its log (told as tasks and commissions, never as "quests", each with a one-line description
a model wrote once from the quest's own aim), what has happened to it lately (below), and how seasoned it is for its level, so a level-5
does not talk like a level-75. Then the rules (editable on the page): stay in character, never mention
levels, servers or the game, know only what someone of this age and place would know, be vague rather than invent a fact, answer
out-of-character `(( ))` briefly and then go back to the scene, but only when the other person writes `(( ))` or `ooc` first: an odd question ("are you an AI?") is put to the person being played and answered in character.

The lore is Warcraft as of Wrath of the Lich King, which is what the realm runs, and every character lives in that age: nothing
later is known. Conversation uses the same memory as before (what each player said, how the bot feels about them), so a bot
remembers you and can become a friend or a rival.

Short remarks use a compact version of the prompt, so a line costs about as much as before.

## Where bots speak up

- **Always answered, in every channel:** whispers, party chat, a player talking to a bot by name, and anything a bot is asked to do.
- **Speaking up by themselves:** only in the channels ticked on the page (default `/say`, `/yell` and guild). A character near a
  whitelisted player says something in `/say` now and then; the people around may answer, in character, a few lines deep, then it goes
  quiet. Some remarks (default 40%) are written from what the bot is doing: the zone it stands in, its errands, its story. The rest
  come from the bank, free, and may be about the very zone it is in.
- **Stock playerbots chatter** (loot brags, LFG and Trade adverts) in a channel a character would not use is not said at all. In
  `/say`, `/yell` and guild it is said in the character's own words.
- The regulars (the cast) still start most of the talk. Their friendships are written in the world's own terms (old comrades, a shared
  oath, mentor and student), only between members of the same side.

## A life that follows what happened

The module keeps a small journal of every bot: level-ups, a new zone, a finished errand, a fall in battle, a dungeon boss or a notorious foe
brought down, a rare find. It goes to the service with the bot's context, which keeps it (`rp_event`) and shows the last few to the model as
"what has happened to you lately". When a bot enters a new stretch of life the chapter it has just finished is **rewritten around what really
happened in it** (two or more events), so the story is the bot's own and not a template. Times are in the world's terms: no numbers, no
levels.

## Presence

Things the module does so that a bot is a person in the world and not a chat source (`docs/roleplay.md` in synthiqbots has the keys):

- **Companions.** A bot in a party with a whitelisted player remarks on a moment of the road in party chat: a new zone, a great foe down, a
  fall, a rare find, a new stretch of its life, now and then an idle thought on a quiet road. Written by the model (`mode: companion`), at
  most one remark per party per 75 s.
- **Greetings.** A bot that knows a player says hello when they walk up to it (`welcome` with `proximity`); strangers are mostly ignored.
- **Emotes.** A bow, wave, thank or laugh aimed at a bot (or near one) is answered with an emote back and, often, a line from the bank (free).
- **The people of the world.** An innkeeper, guard, trainer, vendor or flight master near a whitelisted player answers in character when
  spoken to in `/say`: with them selected, or by name or title (`mode: npc`). They are civil to your side and curt to the other, know the
  zone's lore, and remember the last few lines of the talk. Real innkeepers answer with a warm bed "by the hearth at Tarren Mill".
- **Sides.** The two factions cannot read each other (the game shows gibberish), so a character does not answer the other side, and
  speaks up in `/say` only for those who can understand it, unless the realm allows two-side chat.
- **Quicker speech.** A character talks, it does not type: shorter pauses before and while it answers, and a thinking gesture when it is
  spoken to by name.
- **Bots do not stay on one subject for ever.** After six lines in a row about the same thing, with no player in the talk, it is let go.

## Responsiveness

Measured on the test realm, whispers to a roleplaying bot:

| | before | now |
|---|---|---|
| prompt per whisper | 6,700 tokens | about 3,000 |
| cost per whisper | $0.00024 to $0.00046 | $0.0001 |
| model time | 1.5 to 1.9 s | about the same: the model's own time |

What changed: a whisper that asks nothing of the bot (no invite, follow, trade, gear and the like) is answered **without the tool list**, which was
most of the prompt (14 tools, about 5,000 tokens); anything that could be a request keeps the tools (`plain_chat_no_tools`). The prompt is
ordered for the provider's cache, which keeps everything but the last message: the sheet and the module's own text come first and stay
identical from turn to turn, and what changes (the module's state snapshot, where the bot is, what it remembers of this player) is put in
front of the player's words in the last message. Cached input is a tenth of the price: **cached tokens went from 0 to about 80% of the prompt**.
A reply that slips out of the world ("level 50", a later-game name) is said again once, in character, unless the player asked for it out of
character. The service's heartbeat counts both (`plainChats`, `roleplayRetries`).

### Which model for the ambient lane

`tests/bench_roleplay.py` replays 48 situations (six characters, eight lines) against candidate models and has a judge score each answer
(in character, lore, brevity, no player talk, engaging), at about a cent a model:

| model | score /8 | median | p90 | cost per line | slips (of 48) |
|---|---|---|---|---|---|
| gpt-6-luna | 7.73 | 1.26 s | 1.56 s | $0.00014 | 4 |
| gpt-4o-mini | 7.81 | 0.92 s | 1.04 s | $0.00020 | 7 |
| gpt-5-nano | 7.62 | 1.00 s | 1.30 s | $0.00008 | 3 |
| gpt-4.1-nano | 7.60 | 0.75 s | 0.91 s | $0.00013 | 5 |
| gpt-4.1-mini | 7.69 | 0.88 s | 1.00 s | $0.00053 | 4 |
| **gpt-5.4-nano** | 7.75 | 0.87 s | 1.04 s | $0.00029 | **1** |

The scores are all within the judge's noise, so the choice is speed and slips: the test realm's ambient lane runs on gpt-5.4-nano (a third
quicker than gpt-6-luna, one slip in 48); conversation stays on gpt-6-luna, which does the tool work.

## The roleplay line bank

Like the fake-player bank (38,700 lines), but in character and twice its size: **3,440 cells** of up to 24 lines each, **77,500 lines**
written on the test realm. Every cell is one race and calling in one situation:

- 40 callings x 35 situations (small talk that stands alone, memories of home, a creed, a remark about the road, the weather, the
  other peoples, the war, a prayer, hailing a stranger, a friend by name, taking on an errand, finding something, battle shouts, and
  fourteen kinds of reply) plus 32 subjects (the Scourge, the Legion, faith, magic, honour, the road ...) as openers and as replies
- 10 peoples x 72 zones: what a person of that race says about Westfall, or Tanaris, or the Storm Peaks, in their own voice and with
  that side's feelings about whose land it is

Lines are filtered before they are kept: nothing that sounds like a player (levels, servers, dungeon finders, bots), no
actions that give the speaker a gender (the same line is said by both), no invented placeholders, battle shouts that claim a role
("I'll heal") dropped, and a second model reads every opening line to drop any that a stranger could not make sense of.

Write it from the Minds page (*Line bank*, **Write roleplay lines**; the model is the ambient lane's, and the whole bank cost $1.75 on
gpt-6-luna and took about an hour), or ask the service directly:

```
curl -s -X POST localhost:18800/bank -d '{"op":"generate","mode":"roleplay","per_cell":24}'
curl -s -X POST localhost:18800/bank -d '{"op":"status"}'
```

Narrow it with `archetypes` (`rp:Night Elf:sentinel`, `rpz:Dwarf`) and `situations` (`rp_idle_muse`, `rp_zone:Westfall`). Lines
already there are kept; a run is safe to repeat.

## Names

Playerbots names a Conquest of Azeroth bot "Alte Bot". `tools/rename_bots.py` renames the random bots to two-word names that suit their
race and gender: **Elorin Moonwhisper** (night elf), **Baldrin Ironbeard** (dwarf), **Fizzle Cogspinner** (gnome), **Gorgrim Skullcleaver**
(orc). It is a **dry run unless you pass `--apply`**, and applying needs the worldserver stopped (the realm caches names in memory).
It writes a rollback script first, renames in one transaction, and can update the mind's database so stories, memories and
friendships follow the new names:

```
python3 tools/rename_bots.py --defaults-file ~/.config/coa-dev/client.cnf \
    --characters-db coa_test_minds_characters --auth-db coa_test_minds_auth --mind-db ~/src/coa-minds/mind.sqlite          # look
python3 tools/rename_bots.py ... --apply                                                                                    # do it
```

Two-word names are left alone by playerbots' own startup rename (`AiPlayerbot.CoaBotSurname` stays on). The module calls a bot by its
first name too ("Elorin, hello"): `Promotion::ShortName` takes the first word of a two-word name, as it took "Alte" from "Alte Bot".

`tools/rename_guilds.py` does the same for guilds a bot leads (dry run unless `--apply`, needs the worldserver stopped, writes a rollback script):
"Elite Guard" becomes "Stormwind Vanguard" or "Orgrimmar Wolfriders" by the leader's side, with a message of the day and an info text in the
same voice. The cost is that nothing on a
nameplate says "bot" any more: that is the point for roleplay, and a reason to leave it undone if you want bots recognisable. Bots made
later are named from playerbots' own list; run the tool again for them. The same guid always gets the same name.

## Settings (Minds page, Chat style)

| Setting | Default | Meaning |
|---|---|---|
| Chat style (`chat_mode`) | `roleplay` | `roleplay` or `players` |
| Where characters speak up (`rp_channels`) | `say,yell,guild` | any of `say, yell, zone, world, trade, lfg, guild` |
| Answers taken from the bank (`rp_bank_share_player`) | 25 % | unnamed lines said near a character; the rest are written. Questions are always written |
| Remarks written from what the bot is doing (`rp_start_llm`) | 40 % | the rest come from the bank |
| Models write backstories and chapters (`rp_ai_story`) | on | off keeps plain templates |
| How characters behave (`rp_rules`) | built in | the rules every character is told |

The game module has its own switch, `OllamaChat.Roleplay.Mode = auto | roleplay | players`, to force a mode without asking this service.

## What it costs

A character's backstory is one model call per bot, ever (about 0.05 cent); a chapter is one call per bot per ten levels. A written
reply to a player is a little dearer than before (the sheet is longer), a bank line is free. Measured on the test realm (28 characters
met so far): every backstory and all 102 chapters written by the model for under a cent in total.

## Verified

- `python -m unittest discover -s tests -t .` (366 tests, no network; `tests/test_roleplay.py`, `tests/test_rename_bots.py` and
  `tests/test_rename_guilds.py` are the new ones).
- On the test realm with the roleplay module (`tools/e2e/roleplay_run.py` in synthiqbots, R1 to R11, all pass): a whisper is answered by a
  character with its sheet, race, calling and story shown to the model; the answer names the zone and the sub-area the bot really stands in;
  "are you an AI?" is answered in character; four minutes among a crowd of bots produced no line in the realm channel or General, and a bot
  spoke aloud in `/say`; a GM level-up reaches the service as a journal event and is shown to the model; a bow is answered with an emote; an
  innkeeper answers in character; a bot that knows the player greets them on walking up; a grouped bot remarks in party chat.
- Not tried: the Windows launcher, the Docker stack, a player of the other faction, a multi-day soak, the thinking gesture and the quicker speech
  pauses (built and deployed, not measured). The weather is not sent: the core keeps a zone's weather state private.

## Files and endpoints

| | |
|---|---|
| `mind/lore.py` | races, callings, classes, 70 zones, level stretches: the data |
| `mind/lore_names.py` | first names and surnames per race, and the generator that never runs out |
| `mind/rp.py` | characters, chapters, the prompt, the story writer |
| `mind/rp_bank.py` | the roleplay situations, subjects and the writer's prompts |
| `tools/rename_bots.py` | race-suited names (dry run by default) |
| tables `rp_character`, `rp_chapter` | in `mind.sqlite`; bank rows share the `bank` table (`rp:<Race>:<calling>`, `rpz:<Race>`) |
| `POST /cast {"op":"mode"}` | what the game polls: `{"chat_mode", "channels"}` |
| dashboard ops | `setting.set chat_mode`, `rp.save`, `rp.reset_story`, `rp.reset_all`, `bank.generate` with `"mode":"roleplay"` |
| `GET /api/mind/rp`, `/api/mind/rp/character?name=` | the characters and one sheet |

`tests/test_roleplay.py` and `tests/test_rename_bots.py` cover it offline.

## Not done, and things to know

- Nothing here makes a model good at lore it was not trained on; the sheet and the zone text steer it and the rules tell it to stay
  vague rather than invent, but it can still be wrong about a detail.
- A character's chapters follow the bot's level, which playerbots changes as it plays; a bot that is levelled by a GM command jumps
  and gets every missing chapter at once.
- Fake-player memories and relationships are shared: a bot that has talked to you remembers you in both modes.
- The Windows launcher and the Docker stack were not touched or tried.
