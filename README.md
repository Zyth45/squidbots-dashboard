# SquidBots

A dashboard for a server running a thousand bots, and the watchman that goes with it.

![The dashboard, dark theme](docs/squidbots.png)

It reads an [AzerothCore](https://github.com/azerothcore/azerothcore-wotlk) database and the
worldserver's own logs, and shows what the bots are actually doing: where they are, what they
kill, which ones are stuck, what they find, and whether the server crashed while you slept.
Built for [Conquest of Azeroth](https://github.com/jealous-sound/azerothcore-wotlk-coa) with
[mod-playerbots](https://github.com/Zyth45/mod-playerbots/tree/coa), but nothing stops it from
watching a plain AzerothCore realm.

English by default, French one click away. Dark and light. No framework, no build step, no
external request: one Python file, one HTML page.

## What it shows

| Card | What it answers |
|---|---|
| Six figures | bots online, average level, kills, quests, levels gained, server uptime |
| Hunting pace | kills per hour, measured over a sliding half hour so the saves don't make it a sawtooth |
| Factions | Alliance against Horde, online only, with each side's average level |
| Roles | tanks, healers, damage |
| Where the bots are | the busiest zones, named from the server's own `AreaTable.dbc` |
| Today and yesterday | 24 hours against the 24 before, in percent |
| Bots on the floor | how many are dead, read every ten minutes |
| Watch post | dead now, **stuck bots** (logged in, under the cap, not one point of experience in an hour), crashes, and the watchman's own journal |
| Level spread | the population by ten-level bands |
| Best experience gains | who actually progresses, per hour, over the last day |
| Most talkative | who talks, and how much |
| Class ranking | every class by average level, with its podium |
| Leaderboard | the ten best by experience, kills or quests |
| Spells cast | what the bots cast and how often it goes off |
| Rare finds | the epics the bots bring back, as they drop |

Any bot name is clickable, and the search box opens the same sheet: class, specialization, role,
zone, level, kills, quests, time played, experience per hour.

## Install

Needs Python 3.9 or later (no packages to install) and the `mysql` client binary.

1. Copy `squidbots.py`, `index.html` and `dashboard.example.json` into a folder.
2. Rename the example to `dashboard.json` and fill in your paths. **Keep your database password
   out of it**: point `mysqlArgs` at a MySQL client file that holds the credentials, or drop the
   folder inside a repack that already has `Settings/database.json`.
3. Run it:

```bash
python squidbots.py
```

Then open http://localhost:8088. The page refreshes itself every twenty seconds.

With `publishDir` set, the dashboard also writes `index.html` and `stats.json` into that folder
once a minute, for a web server to serve. That copy hides the memory and crash details: it only
says whether the server runs.

## Three cards need the worldserver to write a log

They stay empty, and say so, until you add these to `worldserver.conf` and restart the server.

**Spells cast** — needs [mod-playerbots on the `coa` branch](https://github.com/Zyth45/mod-playerbots/tree/coa):

```ini
Appender.CoaBots = 2,4,1,CoaBots.log,a
Logger.playerbots.coa = 4,CoaBots
```

**Most talkative** — stock AzerothCore, chat logging off by default:

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

**Rare finds** — needs the `coa` branch again, which logs one line per epic a bot loots:

```ini
Appender.BotLoot = 2,4,1,BotLoot.log,a
Logger.playerbots.loot = 4,BotLoot
```

## The watchman

`watch-and-restart.ps1` checks the worldserver every minute. It restarts it after a crash, and
after a freeze — a world that stops updating keeps its process alive and writes nothing more, so
a log untouched for five minutes is the tell. Before killing a frozen server it captures the
thread stacks, which is usually what tells you why it froze.

```powershell
powershell -ExecutionPolicy Bypass -File watch-and-restart.ps1 -Server C:\my-server\server
```

It writes one line per event, and the dashboard shows that journal in the watch post card
(`incidentsLog` in the settings).

**It also keeps the chat log short.** A thousand bots write about a megabyte an hour and nothing
ever shortens it, so once an hour the watchman rewrites `Chat.log` in place, keeping the last 24
hours (`-TrimLogs`, `-TrimHours`, `-TrimEveryMinutes`). It rewrites rather than renames on purpose:
the worldserver holds the file open, and a rename would leave it writing into a file no one can
see any more.

**Discord alerts are opt-in.** Put a webhook URL in `alerte-discord.txt` next to the script and
incidents are announced there; with no file, nothing is ever sent anywhere.

## Notes

- `footer` in the settings replaces the line at the foot of the page, and `""` removes it along
  with its links: handy while showing the page around before the sources are ready.

- Figures follow `PlayerSaveInterval`: a kill shows up when the character is saved, not the
  second it happens. Rates are measured over a sliding half hour for that reason.
- `baseline.json`, `history.json` and `xp-history.json` are written next to the script. Delete
  `baseline.json` to start the "gained since" figures over.
- Experience per hour needs an hour of readings, and "today against yesterday" needs two days.
  Both say so while they wait.
- Everything is read-only: the dashboard never writes to the game database.

## Credits

- [jealous-sound](https://github.com/jealous-sound/azerothcore-wotlk-coa) for Conquest of Azeroth
- [mod-playerbots](https://github.com/mod-playerbots/mod-playerbots) for the bots
- Written with [Claude Code](https://claude.com/claude-code); reviewed, tested and run on a real
  server with a thousand bots.
