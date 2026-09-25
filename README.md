# SquidBots

A dashboard for a server running a thousand bots, and the watchman that goes with it.

![The dashboard](docs/squidbots.png)

It reads an [AzerothCore](https://github.com/azerothcore/azerothcore-wotlk) database and the
worldserver's logs, and shows what the bots are doing: where they are, what they kill, which ones
are stuck, what they say and find, and whether the server crashed while you slept. Built for
[Conquest of Azeroth](https://github.com/jealous-sound/azerothcore-wotlk-coa) with
[mod-playerbots](https://github.com/Zyth45/mod-playerbots/tree/coa); a plain AzerothCore realm
works too.

English and French. Dark theme only. No framework, no build step, no packages, no outside request
(the Cinzel font is bundled under the SIL Open Font License, `static/fonts/OFL.txt`).

## Pages

| Page | What is on it |
|---|---|
| World | six headline figures, a map of each continent with the bots on it (click a zone for its own map, a bot for its card), and the bot you follow |
| Bots | every bot online, sortable and filterable, beside the followed bot's card |
| Stats | hunting pace, factions, roles, busiest zones, today against yesterday, dead bots, level spread, stuck bots and crashes, experience per hour, leaderboard, spells cast, class ranking |
| Chat & Loot | the live chat feed (searchable, refreshed every 5 s; private version only), the most talkative bots, and the epics they find |
| Settings | private version only: the bot settings that matter, explained, with a warning when another setting cancels one out, and one-click recipes |

Any bot name opens its sheet, as does the search box.

## Install

Needs Python 3.9 or later and the `mysql` client binary.

1. Copy `squidbots.py`, `botconfig.py`, `index.html`, `worldmap.json`, `static/` and
   `dashboard.example.json` into a folder.
2. Rename the example to `dashboard.json` and fill in your paths. **Keep your database password
   out of it**: point `mysqlArgs` at a MySQL client file, or drop the folder inside a repack that
   has `Settings/database.json`.
3. Run `python squidbots.py` and open http://localhost:8088.

## Two versions: private and public

**Private** is the dashboard itself, on `http://localhost`. It has everything: Settings, the live
chat feed with every channel, memory, crashes and the watch journal. The server listens on
127.0.0.1 only, answers only requests addressed to that name (so a web page cannot rebind its own
name onto it), and accepts a write only as JSON from its own page (so another site cannot post a
form to it).

**Public** is what `publishDir` receives once a minute for a web server to serve: plain files
(`index.html`, `static/`, `worldmap.json`, `stats.json`) and no process anyone can reach. It is
built, not filtered:

- `stats.json` carries only the keys listed in `PUBLIC_KEYS` in `squidbots.py`. A figure added
  later stays private until it is listed there.
- Never public: what real players say (no line of chat at all; "most talkative" counts bots only),
  memory, crashes, the watch journal, paths, configuration, errors.
- Never public either: the extracted maps.
- The page's private code sits between `private:start` and `private:end` markers and is removed
  from the public files, not hidden. Publishing stops if anything private is left in them.

## Logs some cards need

Add these to `worldserver.conf` and restart; until then the cards stay empty and say so.

Spells cast, and rare finds (both need [mod-playerbots on the `coa` branch](https://github.com/Zyth45/mod-playerbots/tree/coa)):

```ini
Appender.CoaBots = 2,4,1,CoaBots.log,a
Logger.playerbots.coa = 4,CoaBots
Appender.BotLoot = 2,4,1,BotLoot.log,a
Logger.playerbots.loot = 4,BotLoot
```

Chat feed and most talkative (stock AzerothCore):

```ini
ChatLog.Enable = 1
Appender.Chat = 2,4,1,Chat.log,a
Logger.chat.say = 4,Chat
Logger.chat.yell = 4,Chat
Logger.chat.emote = 4,Chat
Logger.chat.channel = 4,Chat
Logger.chat.whisper = 4,Chat
Logger.chat.party = 4,Chat
Logger.chat.raid = 4,Chat
Logger.chat.guild = 4,Chat
```

## The Settings page

It changes values in the module `.conf` files (`playerbots.conf`, `dynamicxp.conf`, and
`mod_bot_minds.conf` when [mod-bot-minds](https://github.com/vedicveko/mod-bot-minds) is
installed). It edits values in place, never adds or reorders lines, and backs the whole file up to
`config-backups/` first. Each setting says when a change takes effect. The server reads these
files at startup, so it is easiest to use with the server stopped. Writes are accepted from the
machine itself only, from the dashboard's own page. The dashboard never writes to the game database.

## Map

`worldmap.json` (rebuilt by `tools/gen_worldmap.py`) gives the map its zones out of the box: each
zone is a rectangle in world coordinates, with the bots as dots.

For the real continent and zone maps, press **Extract maps** (above the map, or under Settings) and
give your game client folder. In about two minutes they are written to `maps/` (about 70 MB),
with nothing to install. The same from a terminal:

```bash
python tools/gen_art.py --client C:\my-client --dbc C:\my-server\server\data\dbc
```

The maps are Blizzard's: they stay on your machine, are git-ignored, and are never published. The
public copy draws the zone rectangles only. No other game art (interface, frames, icons) is used.

Bots are placed from their last character save. For live positions, and for what each bot is doing
on its card (health, power, task, group, quests), let mod-playerbots write a `bot-status.json` every
few seconds and point `botStatusFile` in `dashboard.json` at it:

```ini
# configs/modules/playerbots.conf
AiPlayerbot.CoaStatusFile = "C:/my-server/server/logs/bot-status.json"
AiPlayerbot.CoaStatusIntervalSeconds = 5
```

It is off by default. With 1000 bots online a snapshot costs under a millisecond of the world
update, and the disk write runs on a thread of its own. A file older than 60 s is treated as stale
(the server has stopped writing it).

## The watchman

`watch-and-restart.ps1` checks the worldserver every minute and restarts it after a crash or a
freeze (a log untouched for five minutes), capturing thread stacks before killing a frozen one.

```powershell
powershell -ExecutionPolicy Bypass -File watch-and-restart.ps1 -Server C:\my-server\server
```

Its journal shows in the Stats page (`incidentsLog`). Once an hour it trims `Chat.log` in place to
the last 24 hours (`-TrimLogs`, `-TrimHours`, `-TrimEveryMinutes`). Discord alerts are opt-in: put
a webhook URL in `alerte-discord.txt` next to the script.

## Notes

- Figures follow `PlayerSaveInterval`: a kill shows when the character is saved. Rates use a
  sliding half hour for that reason.
- `baseline.json`, `history.json` and `xp-history.json` are written next to the script; delete
  `baseline.json` to restart the "gained since" figures.
- `footer` in the settings replaces the page's footer line; `""` removes it.

## Credits

- [jealous-sound](https://github.com/jealous-sound/azerothcore-wotlk-coa) for Conquest of Azeroth
- [mod-playerbots](https://github.com/mod-playerbots/mod-playerbots) for the bots
- [Sass42](https://github.com/Sass42) for the pages, the map, the chat feed and the Settings page
- Written with [Claude Code](https://claude.com/claude-code); reviewed, tested and run on a real
  server with a thousand bots.
