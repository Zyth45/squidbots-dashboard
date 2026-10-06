# Minds: personalities, memory and AI chat for the bots

Bots stay exactly what mod-playerbots makes them (they fight, follow, loot). **Minds** adds a voice: a bot you
whisper, name in a channel or invite into your group wakes up as itself, answers in character, remembers you the
next time, and can look at its own bags, gear and quests and act (invite you, follow, sell junk) because the
worldserver module gives the model real game tools. Everyone else is an ordinary playerbot and costs nothing.

```
you ── chat ──►  worldserver + mod-ollama-chat (SquidBots fork)
                        │  OpenAI-style requests, plus the tool loop
                        ▼
                mind service  (python run-mind.py)            ◄── the Minds page in this dashboard
        personality · memory · relationships · which model · budget
                        │
                        ▼
      OpenAI · Anthropic · DeepSeek · OpenRouter · a local Ollama · anything OpenAI-compatible
```

The worldserver module is the fork at <https://github.com/jmcelreavey/synthiqbots> (branch `coa`), an AzerothCore
module. The mind service is in this repository (`mind/`), in Python, standard library only: it runs on the repack's
own Python with nothing to install. Its data is one SQLite file, `mind.sqlite`, next to `dashboard.json`.

## Set it up

1. **Build the module into your core** (see the fork's `docs/coa.md`): clone it into `modules/mod-ollama-chat`
   next to `mod-playerbots`, rebuild, copy `conf/mod_ollama_chat.conf.dist` to `etc/modules/mod_ollama_chat.conf`.
2. **Start the mind service** from this folder: `python run-mind.py`. It listens on `127.0.0.1:18800`.
3. **Open Minds** in the dashboard. Under *Language models* press **Add a model**, pick a preset, give it a
   model name, and press **Test**. Assign it to the *Conversation* lane (a capable model), and if you like a
   cheaper one to *Quick decisions* and *Memory*.
   - **API keys are not typed into the dashboard.** A model names an environment variable (`OPENAI_API_KEY`),
     which the mind service reads from its own environment. On Windows without setting variables, put
     `{"<model name>": "<key>"}` in `mind-secrets.json` (git-ignored). The Minds page says whether a key was found,
     never what it is.
4. **Point the server at it**: on the *Settings* page apply the **Minds on** recipe, then set
   *Accounts that can wake bots* to your account id (`acore_auth.account.id`). Type `.ollama reload` in game.
5. **Talk to a bot**: whisper any bot in the world, or say its name in party, guild, say or General.
6. *Optional, for fights:* apply the **Combat director** recipe (it needs a TypeSafe key for Jev: the module's `docs/jev.md`).
   While your party fights, Jev picks the enemy to kill first (a skull appears on it) and a companion says so in its own voice.
   The settings are under *Minds*; the module's `docs/director.md` has the details.

Only accounts on the whitelist can wake a bot, because every wake costs model calls. A bot you whisper answers for
ten minutes after your last word; a bot in your group stays awake until you remove it.

## What the Minds page shows

| Section | What it is for |
|---|---|
| **Mind service** | Running or not, bots awake now, calls and spend today against your cap, and a **Pause all AI** switch. |
| **Language models** | Which model answers what (three lanes), key status, limits, a fallback, **Test**. |
| **Usage** | Calls and spend per day, per model and per bot, typical and slow answer times. |
| **Conversations** | Every turn a bot had: what the player said, what it answered, tools it asked for, and on click the exact prompt the model was shown, so you can see why a bot said something. |
| **A bot's mind** | Its personality (edit it, roll a random one, or **write one with AI**), a **Talk to this bot** chat that tries the personality without logging in, its memories (delete or add), its relationships, a mute switch, and a model of its own. |
| **Behaviour and safety** | Memory settings, the reply filter, blocked words, the daily spending cap, the conversation log. Export or import personalities (and, from a full export, memories). |

The existing pages show it too: the bot roster marks bots that are awake or have a personality, the bot card
and the bot sheet name the personality, and the sheet has a button that opens the bot's mind.

## Roleplay or fake players

Two ways for the bots to talk, switched on the Minds page (*Chat style*): **Roleplay**, the default, makes every bot a person of its
race and calling with a backstory that grows as it levels, who knows the lore and the zone it stands in and talks in character, and
who stays out of the realm channel, General, Trade and LFG; **Fake players** is everything in the next section. See
[roleplay.md](roleplay.md).

## Bots that chat like players

Everything above wakes one bot by name. Two more things make a street of bots feel like a server, and both need only the
whitelisted player to be nearby:

- **Say hello and they answer.** Say "hi everyone" in /say, /yell, the zone channel, Trade or LFG without naming anyone and
  the bots in earshot answer, each in its own voice, one short line, staggered like people typing. Another bot may answer that
  answer (up to two replies deep, at most 8 lines in a minute or so), so they talk among themselves and then go quiet. A bot
  sees what the others already said and is told not to greet twice. Naming a bot, whispering it or grouping with it works as
  before. The lines come from the **Ambient chat** model (Quick decisions until you pick one): about $0.00005 a line.
- **Their stock chatter gets a voice.** The ready-made lines playerbots posts ("Took [quest]. Time to dive in.", "WTS Cloth")
  come from a table of about a thousand templates that every bot shares. With *Bots say their stock chatter in their own
  words* on, a bot with a whitelisted player within 250 yards holds the stock line back and says the same thing as itself,
  item and quest links kept. If the mind service is down the stock line goes out a moment late; with nobody near, nothing
  changes at all.

**Who they are.** Generated personalities are meant to read like people in a busy realm's chat, not characters from the game's
story: trolls, banter merchants, salty veterans, try-hards, memers, helpful souls, newbies, gold goblins, quiet grinders and
lurkers. Each has traits, a way of typing (lowercase, slang, typos, caps when excited), interests, **strong opinions and
running jokes** they bring up and argue for, and a **chattiness** from 0 to 100 (a lurker joins in rarely and costs nothing;
a troll nearly always does). Chat lines are told to banter, tease, exaggerate, disagree with each other instead of agreeing
with everything, and top each other's jokes, while staying good-natured: no slurs, no hate, nothing sexual, no real-world
politics, and back off from someone who seems upset. All of it is editable on a bot's page (*Opinions and running jokes*,
*Chattiness*), and *Write one with AI* writes in the same spirit. *Re-roll all generated personalities* (Behaviour and safety)
throws away the automatic ones so they are made again from the current archetypes; personalities you wrote or edited stay.

The Conversations page lists these as the `ambient` lane, with the exact prompt. The switches are on Settings under Minds
(*Bots answer a hello nearby*, *Most bots that answer one line*, *Chance a bot answers another bot's line*, and so on).

Not done with a per-bot bank of pre-written lines or with Jev: at these prices a fresh line costs about as much as looking one
up, and Jev picks between options but cannot write text.

## The line bank: a lively world that costs almost nothing

Asking a model for every line a bot says is what makes a busy realm expensive. The line bank moves that cost to a one-off:
a model writes some tens of thousands of short chat lines once, for every kind of person (`troll`, `regular`, `lurker`...) in every
situation (a hello, a question, a gripe, looting something, levelling up...), and bots then say those.

- **Where lines come from.** The Minds page, Line bank card, "Write more lines" (or `POST /bank {"op":"generate"}` on the
  service). Lines that break a rule (em dashes, an invented placeholder, "as an AI", a missing item link) are dropped, not
  patched. Placeholders `{player} {zone} {class} {level} {link} {mob}` are filled when the bot speaks. A cell that fails is counted;
  run it again and only new lines are added. About 12,000 lines cost roughly 15 to 30 cents with a small model.
- **When the bank is used.** For stock playerbots chatter (loot, quest, level-up, suggestions), for small talk (a hello, thanks, a
  goodbye, a laugh) and for bots answering each other once a conversation is going on without a player in it. Anything a player
  really says, a question, a story or a follow-up, is written by the model from the last ten lines and the subject of the
  talk, so a reply answers what was asked and stays on topic. While a player is in the talk, the bots' first `bank_llm_depth`
  (3) answers to each other are written too; deeper in the chain they come from the bank. `bank_share_bots` is the percentage
  of the remaining bank-eligible lines taken from the bank. Direct whispers, party talk and anything that needs a real answer
  (trades, questions with tools) never use it.
- **Fight calls.** Two situations, `combat_focus` and `combat_cc`, hold the short orders a bot gives its party when the game's combat
  director picks a target ("focus {mob}, this fight used to be easier"). The worldserver asks for one with
  `POST /ambient {"mode": "combat", "kind": "focus"|"cc", "bot_guid", "bot_name", "mob"}`; the answer comes from the bank, never a
  model call (it would arrive after the fight), and an empty `text` means the game says its own plain line.
- **Tone.** The shared prompt ("the vibe") asks for ordinary, decent players: answer what was asked, take an interest, never be
  sarcastic at a player's expense. Personality still decides how each bot sounds, but the mix is weighted to friendly and plain
  kinds, and a line that answers a player is never told to snap at them unless the bot is a grump by nature (troll, cynic,
  impatient, salty veteran). The bank writer is told the same: dry and blunt about the game is fine, mocking the listener is not.
- **Who picks the line.** `Local` picks at random among lines that fit what was said and are not ones this bot used lately.
  `Jev` (TypeSafe's typed-decision model, no text generation) is given the recent chat and up to 12 candidate lines and
  returns which one answers the last line best, plus whether this person would have spoken at all. That is what makes a scene
  read as a conversation rather than everyone talking across each other. If Jev is slow or down, three failures pause it for
  a minute and the local pick is used. Jev's key is read from `JEV_API_KEY` or a file named by `JEV_KEY_FILE`, never stored.
- **Nothing fits.** Jev is also offered "none of these lines fits" (option 0). When it picks that for a player's line, the
  line goes to the model instead; when another bot's line gets a low chance of a reply, the bot stays quiet. A player who
  speaks is always answered (the model's "(silent)" falls back to the best banked line). Stock lines that need a fitting
  answer are not a problem any more: playerbots' own chatter is only ever a category of remark, so it is rewritten from the
  bank too (subject to `bank_share_bots`).
- **Topics.** Chat is not generic: someone mentions copper, lag or a tank and the next reply should be about that. The bank
  holds `reply_topic:<topic>` and `idle_topic:<topic>` lines for 22 subjects (mining, dungeons, gold, lag, pets, real life...),
  per kind of person. The topic is read from the last few lines (newer lines weigh more) and remembered for the place for
  two and a half minutes, so "lol same" still gets a reply about fishing. Topic lines are offered to the picker first, then
  the general reply lines. Conversation starters are a topic opener about a third of the time, and set the topic for everyone
  who answers. Write them with `{"op":"generate","situations":["idle_topic","reply_topic"]}` (optionally `"topics": [...]`).
- **Starting a conversation.** The game asks `POST /ambient {"mode": "start"}` when it wants a bot to say something with
  nobody having spoken (module setting `OllamaChat.Ambient.StarterIntervalSec`). The answer is always a banked opening line;
  the bots that hear it answer like any other line. Conversations in the realm, Trade and LFG channels are tracked as one
  scene each, because the whole realm hears them.
- **Cost.** Writing the bank runs on its own lane (`bank`) so it shows apart from chat in the cost view. Bank answers cost nothing; a Jev pick is about 600 input tokens, so a hundred picks cost under a cent. Bank turns
  show in Conversations as profile `bank` or `bank+jev`.

## Selling in the Trade channel

The Trade channel's conversation starters are adverts for something the bot really carries, written from the `idle_sell` bank
situation (`{link}` for the item and stack size, `{price}` for the asking price, exactly once each). The module
picks the item and price and sends them with the start request (`listing`); without one the bot says nothing, so the bank has no
generic "WTS bags and mats" lines any more. Buying is a whisper or an answer to the bot: its context says what it is selling
and for how much, and it mails the item cash on delivery with the `bot_sell_by_mail` tool. Write the adverts with
`{"op":"generate","situations":["idle_sell"]}`.

## Trading with a bot

A bot only trades with its master or a member of its group: playerbots cancels every other trade the moment the window opens
("I'm kind of busy now"). The trade tool now says so up front, and the bot offers to invite you first. It remembers what it just
did with its tools for half an hour (which item it put in the trade), so "I don't see the sword?" is answered with the real item.

## How a bot remembers

- Every exchange with a player is stored. When that player talks to the bot again, the most relevant lines (by
  importance, freshness and shared words) go in front of the model.
- Every few exchanges (*Reflect on memory every N exchanges*) a cheap model reads the recent conversation and
  writes down lasting **facts** about the player and how the bot now **feels** about them (close friend,
  acquaintance, dislikes). Facts never fade quickly; small talk does.
- Memories are private to each player: what Ann told Brick is not what Brick tells Bob.
- If a guid is reused by a different character (bots deleted and created again), the old memories are dropped.

## Safety and cost

- **Pause all AI** makes every request fail fast; bots go back to being plain playerbots. Nothing else changes.
- The **daily cap** covers every model together; a model can also have its own calls-per-minute limit and daily
  budget, and a fallback model to try when it fails or is over budget.
- Replies are cut to one plain line of at most 250 characters (a chat line holds 255), stripped of markdown and
  emoji, with your blocked words starred out.
- The prompt tells the model that players' words are conversation and never orders, and not to reveal its
  instructions. A determined player can still try; the dashboard's Conversations view shows what happened, and
  **Mute this bot** or **Pause all AI** stop it at once.
- The tools a bot may call are controlled by the worldserver module (`OllamaChat.Gateway.AllowedTools`,
  `Mcp.AllowActionTools`), not by this service. Keep the whitelist short.

## Bots that are not awake

Nothing changes for them. The module only acts for whitelisted players and bots they wake, and with
`OllamaChat.Gateway.Enable = 0` (or the service stopped) the realm behaves exactly like one without the module.
Bots keep every behaviour of mod-playerbots, the CoA classes and rotations included.

## Which model, and what it costs

Tested by replaying 79 real requests from the game (33 conversation, 46 quick-decision) against each model, several times,
and then in the game itself. Prices are dollars per million tokens (input / cached input / output).

| Model | Price | Conversation (tools, memory, invites) | Quick decisions | Verdict |
|---|---|---|---|---|
| **gpt-6-luna** | 0.10 / 0.01 / 0.50 | 160 of 165 (invites 25 of 25) | valid JSON 230 of 230, best agreement | **use this** |
| gpt-4o-mini | 0.15 / 0.075 / 0.60 | 165 of 165 | valid, good | fine, and a good fallback |
| gpt-5.4-nano | 0.20 / 0.02 / 1.25 | 164 of 165 (invites 8 of 10, then 25 of 25) | valid | works, dearer than luna |
| gpt-4.1-nano | 0.10 / 0.025 / 0.40 | invites **2 of 10** | valid | cannot "do things" |
| gpt-5-nano | 0.05 / 0.005 / 0.40 | invites **0 of 10** | valid | cheapest, cannot "do things" |
| gpt-5.4-mini | 0.75 / 0.075 / 4.50 | 66 of 66 | valid | about 7 times luna's price for no visible gain |
| gpt-6-sol | 2.00 / 0.20 / 10.00 | 66 of 66 | valid, top agreement | about 20 times luna's price |

(A "miss" for luna on recall was the model choosing to look the player up in the game instead of answering from memory.)

**Measured in the game with gpt-6-luna on every lane:**

- a conversation call: about 6,300 tokens in (42% cached) and 25 out, **$0.0004**, about 1.4 s
- a quick-decision call: about 2,500 tokens in (58% cached), **$0.00013**, about 1.3 s
- one delivered reply, including its quick-decision call, tool round and memory share: **about $0.0009**
- an awake bot in your party makes one quick-decision call about every ten seconds: **about $0.05 an hour each**

| A session | Roughly |
|---|---|
| Logged in, no bot awake | nothing (no calls are made) |
| One hour, 60 messages, one companion | **$0.10** |
| An evening: three hours, 150 messages, a party of four | **$0.70** |
| A heavy day: eight hours, 400 messages, five companions | **$2.20** |

Without any prompt caching these are up to about twice as much. Set the *Daily spending cap* on the Minds page for a hard
ceiling; every call is refused for the rest of the day once it is reached.

**The number of bots online does not change the bill.** Measured with 200 bots online: no whitelisted player logged in,
0 calls in 10 minutes; a whitelisted player standing among 16 to 23 bots, 21 calls in 6.8 minutes (about $0.03 an hour),
from only 5 distinct bots, because a nearby bot is only enrolled for tactical ticks up to `Tactical.NearbyBotMax` (5).
Two config-only ways to spend less: `Tactical.HeartbeatMs` (10000 to 20000 halves the tick cost), and
`Tactical.AutoEnrollNearbyBots = 0` (nearby bots stay plain playerbots until you whisper or group them).

## Things that are not obvious

- **Two-word names.** Conquest of Azeroth names a bot "First Bot". The service, the dashboard and the module all handle
  that; if you write your own tools around it, do not split names on spaces.
- **Follow-ups need a beat.** The module drops a message that arrives less than *Least seconds between your messages to
  one bot* after your last one to the same bot (2 s with the recipe). It says nothing when it does.
- **A bot in a fight still answers** a whisper or its name (*A bot you speak to answers even in a fight*); upstream
  ignores it, and a bot that is hunting is in combat almost all the time.
- **"Why did it not do it?"** Open the conversation on the Conversations page: it lists the tools the model was offered and
  the ones it asked for.

## Files and endpoints

| | |
|---|---|
| `run-mind.py`, `mind/` | the service (`python -m mind` also works outside the repack) |
| `mind.sqlite` | personalities, memories, relationships, models, the call and conversation logs |
| `mind-status.json` | the service's heartbeat (the dashboard reads it) |
| `mind-secrets.json` | optional API keys by model name; never commit it |
| `POST /v1/chat/completions` | conversations (what the module calls) |
| `POST /fast/v1/chat/completions` | quick decisions |
| `POST /cast` | the regulars, and `{"op":"mode"}`: how the bots should talk (see roleplay.md) |
| `GET /health` | `{"ok": true}` |

## Tests

```bash
python -m unittest discover -s tests -t .             # 100+ tests, no network
OPENAI_API_KEY=sk-... python -m unittest tests.live_openai -v   # optional, a few cents
```
