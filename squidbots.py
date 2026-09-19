"""
squidbots.py - a local dashboard for the bots of a Conquest of Azeroth server.

Serves a small web page on http://localhost:8088, reachable from this machine only:
  /            the page (index.html)
  /api/stats   the figures as JSON, worked out again at most every 20 seconds

The figures come from the server database, so they follow how often characters are saved
(PlayerSaveInterval, 15 minutes by default) rather than every kill as it happens.
"""
import datetime
import glob
import http.server
import json
import os
import re
import struct
import subprocess
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# Optional dashboard.json next to this file: {"repack": ..., "publishDir": ..., "uptimeSince": ...}.
# A second instance for another server can also set "mysqlArgs" (mysql.exe arguments instead of the repack's root
# login), "coaLog", "crashesDir" and "worldserverPath" (the worldserver.exe it follows), plus "port".
# "countFrom" ("YYYY-MM-DD HH:MM:SS") makes every figure start there instead of at the bots' creation: kills and
# quests since then, bot actions and crashes since then (a test run on a server that already has old bots).
# Without it the dashboard expects to sit in <repack>\Dashboard and publishes nothing.
SETTINGS_FILE = os.path.join(HERE, "dashboard.json")
SETTINGS = json.load(open(SETTINGS_FILE, encoding="utf-8")) if os.path.exists(SETTINGS_FILE) else {}
def find_repack():
    # <repack>\Dashboard or <repack>\CoA-Bots\Dashboard: the first parent holding the repack settings.
    folder = os.path.dirname(HERE)
    for _ in range(2):
        if os.path.exists(os.path.join(folder, "Settings", "database.json")):
            return folder
        folder = os.path.dirname(folder)
    return os.path.dirname(HERE)


ROOT = SETTINGS.get("repack") or find_repack()
BUILDS = next((p for p in (os.path.join(HERE, "coa-level-builds.json"), r"C:\CoA-Build\coa-level-builds.json")
               if os.path.exists(p)), os.path.join(HERE, "coa-level-builds.json"))
PORT = int(os.environ.get("COA_DASHBOARD_PORT") or SETTINGS.get("port") or 8088)
CACHE_SECONDS = 20
HISTORY_FILE = os.path.join(HERE, "history.json")
HISTORY_EVERY = 10 * 60        # one point every 10 minutes
HISTORY_KEEP = 7 * 24 * 3600   # a week of points
# Experience of every bot, once an hour, to work out who gains the most over a day.
XP_FILE = os.path.join(HERE, "xp-history.json")
LEVELS_FILE = os.path.join(HERE, "levels.json")
XP_EVERY = 3600
XP_KEEP = 25 * 3600
# Optional public copy: a folder a web server serves, on a NAS or anywhere else. The dashboard only
# writes files there, so nothing on this machine is reachable from outside. Unset: no copy.
PUBLISH_DIR = SETTINGS.get("publishDir")
PUBLISH_EVERY = 60
# Usage report of the CoA bot actions, written by the worldserver every 10 minutes (counts since its start).
COA_LOG = SETTINGS.get("coaLog") or os.path.join(ROOT, "Core", "Logs", "CoaBots.log")
USAGE_RE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) coa usage since start \(cast/tried\): (.*)$")
# Chat of the players and the bots, written by the worldserver when ChatLog.Enable = 1 and the
# chat.* loggers point at a Chat.log appender. Absent: the dashboard simply shows no talkers.
CHAT_LOG = SETTINGS.get("chatLog") or os.path.join(os.path.dirname(COA_LOG), "Chat.log")
CHAT_RE = re.compile(r"^(?:(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\s+)?Player (\S+) (.*)$")
CHAT_TAIL = 16 * 1024 * 1024   # only the end of the file is read: a day of chat is far smaller
SPELLS_RE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) coa (interrupt|dispel) spells: (.*)$")
COUNT_RE = re.compile(r"([a-z ]+?) (\d+)/(\d+)")
SPELL_RE = re.compile(r"\s*([^,]+?) \((\d+)\) x(\d+)")  # entries are separated by ", "


def action_usage(hours=24):
    """Casts and tries of each bot action over the last `hours`, from CoaBots.log.

    Counts in the log restart at every worldserver start: the gain between two reports of the
    same run is added up, and a report whose counts went down starts a new run.
    """
    if not os.path.exists(COA_LOG):
        return None
    since = time.time() - hours * 3600
    totals, previous, first = {}, None, None
    runs, spells = [], {}
    for raw in open(COA_LOG, encoding="utf-8", errors="replace"):
        line = raw.strip()
        match = USAGE_RE.match(line)
        if match:
            stamp = time.mktime(time.strptime(match.group(1), "%Y-%m-%d %H:%M:%S"))
            counts = {name.strip(): (int(cast), int(tried)) for name, cast, tried in COUNT_RE.findall(match.group(2))}
            restarted = previous is None or any(counts.get(name, (0, 0))[1] < tried
                                                for name, (_, tried) in previous.items())
            if restarted and spells:
                runs.append(spells)
                spells = {}
            if stamp >= since:
                first = first or stamp
                for name, (cast, tried) in counts.items():
                    base_cast, base_tried = (0, 0) if restarted else previous.get(name, (0, 0))
                    total = totals.setdefault(name, [0, 0])
                    total[0] += max(0, cast - base_cast)
                    total[1] += max(0, tried - base_tried)
            previous = counts
            continue
        match = SPELLS_RE.match(line)
        if match and time.mktime(time.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")) >= since:
            # The latest list of a run holds that run's totals.
            spells[match.group(2)] = {name: int(n) for name, _, n in SPELL_RE.findall(match.group(3))}
    if spells:
        runs.append(spells)

    def top(kind):
        merged = {}
        for run in runs:
            for name, n in run.get(kind, {}).items():
                merged[name] = merged.get(name, 0) + n
        return [{"name": name, "count": n} for name, n in sorted(merged.items(), key=lambda kv: kv[1], reverse=True)[:8]]

    return {
        "hours": hours,
        "since": round(first) if first else None,
        "rows": [{"key": name, "cast": cast, "tried": tried} for name, (cast, tried) in totals.items()],
        "interrupts": top("interrupt"),
        "dispels": top("dispel"),
    }

def chat_stats(hours=24, limit=12):
    """Who talked and how much over the last `hours`, from Chat.log.

    Lines look like "Player Name says (language 0): ..." or "Player Name tells channel Zone: ...".
    A line with no date is kept: the appender writes one, and an old file simply reads as recent.
    """
    if not os.path.exists(CHAT_LOG):
        return None
    since = time.time() - hours * 3600
    talkers, kinds, first = {}, {}, None
    with open(CHAT_LOG, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        handle.seek(max(0, handle.tell() - CHAT_TAIL))
        raw = handle.read().decode("utf-8", "replace")
    for line in raw.splitlines()[1:]:               # the first line may be cut in half
        match = CHAT_RE.match(line.strip())
        if not match:
            continue
        stamp, name, rest = match.groups()
        if stamp:
            when = time.mktime(time.strptime(stamp, "%Y-%m-%d %H:%M:%S"))
            if when < since:
                continue
            first = when if first is None else min(first, when)
        kind = ("channel" if rest.startswith("tells channel ") else "whisper" if rest.startswith("tells ")
                else "say" if rest.startswith("says") else "yell" if rest.startswith("yells")
                else "emote" if rest.startswith("emotes") else "group")
        talker = talkers.setdefault(name, {"name": name, "messages": 0, "channel": 0})
        talker["messages"] += 1
        if kind == "channel":
            talker["channel"] += 1
        kinds[kind] = kinds.get(kind, 0) + 1
    ordered = sorted(talkers.values(), key=lambda t: t["messages"], reverse=True)
    return {
        "hours": hours,
        "since": round(first) if first else None,
        "messages": sum(kinds.values()),
        "talkers": len(talkers),
        "kinds": [{"kind": k, "count": n} for k, n in sorted(kinds.items(), key=lambda kv: kv[1], reverse=True)],
        "top": ordered[:limit],
    }


# Zone names, from the worldserver's own AreaTable.dbc: characters.zone holds an area id.
DBC_DIR = SETTINGS.get("dbcDir") or next(
    (p for p in (os.path.join(ROOT, "data", "dbc"), os.path.join(ROOT, "Core", "data", "dbc")) if os.path.isdir(p)),
    os.path.join(ROOT, "Core", "data", "dbc"))


def zone_names():
    path = os.path.join(DBC_DIR, "AreaTable.dbc")
    if not os.path.exists(path):
        return {}
    raw = open(path, "rb").read()
    magic, records, fields, size, _ = struct.unpack("<4siiii", raw[:20])
    if magic != b"WDBC" or fields < 12:
        return {}
    body, block = raw[20:20 + records * size], raw[20 + records * size:]
    names = {}
    for i in range(records):
        row = struct.unpack_from("<%dI" % fields, body, i * size)
        end = block.index(b"\0", row[11])          # field 11 is the English name
        name = block[row[11]:end].decode("utf-8", "replace")
        if name:
            names[row[0]] = name
    return names


# Rare finds, written by the bot module when worldserver.conf points "playerbots.loot" at an appender.
LOOT_LOG = SETTINGS.get("lootLog") or os.path.join(os.path.dirname(COA_LOG), "BotLoot.log")
LOOT_RE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\s+(\S+) \(class (\d+) level (\d+)\) looted "
                     r"(.+?) \((\d+)\) quality (\d+) ilvl (\d+) x(\d+)$")


def loot_feed(limit=12, hours=48):
    """The last epic (or better) items the bots brought back, most recent first."""
    if not os.path.exists(LOOT_LOG):
        return None
    since = time.time() - hours * 3600
    found = []
    with open(LOOT_LOG, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        handle.seek(max(0, handle.tell() - 2 * 1024 * 1024))
        raw = handle.read().decode("utf-8", "replace")
    for line in raw.splitlines()[1:]:
        match = LOOT_RE.match(line.strip())
        if not match:
            continue
        stamp, name, cls, level, item, item_id, quality, ilvl, count = match.groups()
        when = time.mktime(time.strptime(stamp, "%Y-%m-%d %H:%M:%S"))
        if when < since:
            continue
        found.append({"ts": round(when), "bot": name, "cls": int(cls), "level": int(level), "item": item,
                      "itemId": int(item_id), "quality": int(quality), "ilvl": int(ilvl), "count": int(count)})
    return {"hours": hours, "total": len(found), "rows": found[::-1][:limit]}


# Journal of the watcher (Surveiller-Et-Relancer.ps1): restarts and freezes, most recent first.
INCIDENTS_FILE = SETTINGS.get("incidentsLog")


def incidents(limit=6):
    if not INCIDENTS_FILE or not os.path.exists(INCIDENTS_FILE):
        return None
    lines = []
    for raw in open(INCIDENTS_FILE, encoding="utf-8", errors="replace"):
        line = raw.strip()
        if not line or "surveillance demarree" in line:
            continue
        lines.append(line)
    out = []
    for line in lines[-limit:][::-1]:
        when, _, what = line.partition("  ")
        out.append({"at": when.strip(), "what": what.strip()})
    return out


# Server uptime is counted from this date (on this PC: the switch to 1000 bots), else from the first start.
UPTIME_SINCE = SETTINGS.get("uptimeSince", "2000-01-01 00:00:00")
COUNT_FROM = time.mktime(time.strptime(SETTINGS["countFrom"], "%Y-%m-%d %H:%M:%S")) if SETTINGS.get("countFrom") else None

# Human, Dwarf, Night Elf, Gnome, Draenei; every other race is Horde.
ALLIANCE_RACES = {1, 3, 4, 7, 11}

HEAL = {6, 31, 37, 40, 43, 51, 98, 101}
TANK = {9, 17, 21, 22, 48, 52, 57, 60, 96, 97, 99, 100}


def mysql(query):
    if SETTINGS.get("mysqlArgs"):
        exe = SETTINGS.get("mysqlExe", "C:/Program Files/MySQL/MySQL Server 8.4/bin/mysql.exe")
        login = list(SETTINGS["mysqlArgs"])
    else:
        password = json.load(open(os.path.join(ROOT, "Settings", "database.json"), encoding="utf-8"))["rootPassword"]
        exe = next(glob.iglob(os.path.join(ROOT, "**", "mysql.exe"), recursive=True))
        repack = os.path.join(ROOT, "Settings", "repack.json")
        port = json.load(open(repack, encoding="utf-8-sig")).get("mysqlPort", 3307) if os.path.exists(repack) else 3307
        login = ["--host=127.0.0.1", "--port=%d" % port, "-uroot", "-p" + password]
    out = subprocess.run([exe] + login + ["-N", "-B", "-e", query],
                         capture_output=True, text=True, encoding="utf-8", timeout=30)
    if out.returncode:
        raise RuntimeError(out.stderr.strip())
    return [line.split("\t") for line in out.stdout.splitlines() if line]


def role_of(spec):
    if not spec:
        return "none"
    return "heal" if spec in HEAL else "tank" if spec in TANK else "dps"


def server_state():
    state = {"running": False, "ramMo": None, "crashes24h": 0, "lastCrash": None}
    try:
        if SETTINGS.get("worldserverPath"):
            # Several worldservers run on this PC: follow the one at that path.
            out = subprocess.run(["powershell", "-NoProfile", "-Command",
                                  "Get-Process worldserver -ErrorAction SilentlyContinue | Where-Object Path -eq '%s' | "
                                  "ForEach-Object { [int]($_.WorkingSet64 / 1MB) }" % SETTINGS["worldserverPath"]],
                                 capture_output=True, text=True, timeout=15).stdout.split()
            if out:
                state["running"], state["ramMo"] = True, int(out[0])
            raise StopIteration
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq worldserver.exe", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, timeout=10).stdout
        for line in out.splitlines():
            if line.lower().startswith('"worldserver.exe"'):
                state["running"] = True
                memory = line.rsplit('","', 1)[-1]
                digits = re.sub(r"\D", "", memory)
                if digits:
                    state["ramMo"] = int(digits) // 1024
    except (OSError, subprocess.SubprocessError, StopIteration, ValueError):
        pass
    since = COUNT_FROM or time.time() - 24 * 3600
    # The worldserver writes crash reports under the folder it runs in: Core, or CoA-Bots\Core with CoA Bots.
    folders = [SETTINGS["crashesDir"]] if SETTINGS.get("crashesDir") else [os.path.join(ROOT, "Core", "Crashes"),
                                                                        os.path.join(ROOT, "CoA-Bots", "Core", "Crashes")]
    crashes = [f for folder in folders
               for f in glob.glob(os.path.join(glob.escape(folder), "*.txt")) if os.path.getmtime(f) > since]
    state["crashes24h"] = len(crashes)
    if crashes:
        state["lastCrash"] = datetime.datetime.fromtimestamp(max(os.path.getmtime(f) for f in crashes)).strftime("%d/%m %H:%M")
    return state


class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.cached_at = 0.0
        self.data = None
        self.baseline = None
        self.level_ups = json.load(open(LEVELS_FILE, encoding="utf-8")) if os.path.exists(LEVELS_FILE) else {}
        self.specs = {}
        self.classes = {}
        self.xp_levels = {}
        self.zones = None
        self.history = json.load(open(HISTORY_FILE, encoding="utf-8")) if os.path.exists(HISTORY_FILE) else []
        self.xp_history = json.load(open(XP_FILE, encoding="utf-8")) if os.path.exists(XP_FILE) else []

    def load_names(self):
        if not self.specs:
            for key, build in json.load(open(BUILDS, encoding="utf-8")).items():
                self.specs[key] = build["spec"]
        if not self.classes:
            for cls, name in mysql("SELECT class, client_name FROM acore_world.ascension_custom_class"):
                self.classes[int(cls)] = name
        if self.zones is None:
            self.zones = zone_names()
        if not self.xp_levels:
            # Experience needed to reach each level, so that levels and experience compare as one number.
            total = 0
            for level, needed in mysql("SELECT Level, Experience FROM acore_world.player_xp_for_level ORDER BY Level"):
                self.xp_levels[int(level)] = total
                total += int(needed)
            self.xp_levels[max(self.xp_levels) + 1] = total

    def get(self):
        with self.lock:
            if self.data is None or time.time() - self.cached_at > CACHE_SECONDS:
                try:
                    self.data = self.collect()
                except Exception as error:  # keep the last good data, report the problem
                    data = dict(self.data or {})
                    data["error"] = str(error)
                    self.data = data
                self.cached_at = time.time()
            return self.data

    def collect(self):
        self.load_names()
        rows = mysql(
            "SELECT c.name, c.class, c.level, c.xp, c.online, TRIM(IFNULL(s.data, '0')), IFNULL(k.counter, 0), "
            "IFNULL(q.n, 0), c.totaltime, c.race, c.money, c.health, c.zone "
            "FROM acore_characters.characters c JOIN acore_auth.account a ON a.id = c.account "
            "LEFT JOIN acore_characters.character_settings s ON s.guid = c.guid AND s.source = 'core.ascension_active_spec' "
            "LEFT JOIN acore_characters.character_achievement_progress k ON k.guid = c.guid AND k.criteria = 5529 "
            "LEFT JOIN (SELECT guid, COUNT(*) n FROM acore_characters.character_queststatus_rewarded GROUP BY guid) q "
            "ON q.guid = c.guid "
            "WHERE a.username LIKE 'RNDBOT%'")
        bots = []
        for name, cls, level, xp, online, spec, kills, quests, totaltime, race, money, health, zone in rows:
            cls, spec, level, xp = int(cls), int(spec or 0), int(level), int(xp)
            bots.append({
                "name": name, "cls": self.classes.get(cls, str(cls)), "level": level, "xp": xp,
                "online": online == "1", "spec": self.specs.get("%d:%d" % (cls, spec), "") if spec else "",
                "role": role_of(spec), "kills": int(kills), "quests": int(quests), "hours": int(totaltime) / 3600.0,
                "faction": "alliance" if int(race) in ALLIANCE_RACES else "horde",
                "totalXp": self.xp_levels.get(level, 0) + xp,
                "gold": int(money) / 10000.0, "dead": int(health) == 0, "zone": int(zone),
            })

        online = [b for b in bots if b["online"]]
        totals = {
            "bots": len(bots),
            "online": len(online),
            "avgLevelOnline": round(sum(b["level"] for b in online) / len(online), 2) if online else 0,
            "maxLevel": max((b["level"] for b in bots), default=0),
            "lvl10": sum(1 for b in bots if b["level"] >= 10),
            "kills": sum(b["kills"] for b in bots),
            "quests": sum(b["quests"] for b in bots),
            "hours": round(sum(b["hours"] for b in bots)),
        }
        # Starting point of the "gains since" figures, kept on disk so restarting the dashboard does not reset it.
        # Delete baseline.json to start a new session.
        baseline_file = os.path.join(HERE, "baseline.json")
        if self.baseline is None and os.path.exists(baseline_file):
            self.baseline = json.load(open(baseline_file, encoding="utf-8"))
        if self.baseline is None:
            self.baseline = {"at": datetime.datetime.now().strftime("%d/%m %H:%M"), "ts": time.time(),
                             "kills": totals["kills"], "quests": totals["quests"],
                             "levels": sum(b["level"] for b in bots)}
            json.dump(self.baseline, open(baseline_file, "w", encoding="utf-8"))
        session = {
            "since": self.baseline["at"],
            "hours": round((time.time() - self.baseline["ts"]) / 3600.0, 3),
            "kills": totals["kills"] - self.baseline["kills"],
            "quests": totals["quests"] - self.baseline["quests"],
            "levels": sum(b["level"] for b in bots) - self.baseline["levels"],
        }
        if COUNT_FROM:
            # Test run: the big figures are the gains since the baseline, not the bots' whole lives.
            totals["kills"], totals["quests"] = session["kills"], session["quests"]

        # Hours the worldserver ran since the 1000-bot setup, from AzerothCore's own uptime table. The
        # table is written every 10 minutes: the running start is counted up to now instead.
        starts = mysql("SELECT starttime, uptime FROM acore_auth.uptime "
                       "WHERE starttime >= UNIX_TIMESTAMP('%s') ORDER BY starttime" % UPTIME_SINCE)
        uptime_seconds = sum(int(up) for _, up in starts)
        if starts and server_state()["running"]:
            started, recorded = int(starts[-1][0]), int(starts[-1][1])
            uptime_seconds += max(0, int(time.time()) - started - recorded)
        uptime = {"hours": round(uptime_seconds / 3600.0, 1)}

        # Levels gained since the worldserver started, added up one level-up at a time: the sum of the
        # bots' levels also moves when level brackets send bots down, or far up, which is not play.
        server_start = int(starts[-1][0]) if starts else 0
        if self.level_ups.get("start") != server_start:
            self.level_ups = {"start": server_start, "gained": 0, "last": {}}
        last = self.level_ups["last"]
        for b in bots:
            before = last.get(b["name"])
            if before is not None and 0 < b["level"] - before <= 3:
                self.level_ups["gained"] += b["level"] - before
            last[b["name"]] = b["level"]
        json.dump(self.level_ups, open(LEVELS_FILE, "w", encoding="utf-8"))
        session["levels"] = self.level_ups["gained"]
        session["levelHours"] = round((time.time() - server_start) / 3600.0, 3) if server_start else 0

        # Points for the curves, kept on disk so they survive a restart of the dashboard.
        now = time.time()
        if not self.history or now - self.history[-1]["ts"] >= HISTORY_EVERY:
            self.history.append({"ts": round(now), "kills": totals["kills"], "quests": totals["quests"],
                                 "levels": sum(b["level"] for b in bots), "avg": totals["avgLevelOnline"],
                                 "online": totals["online"],
                                 "dead": sum(1 for b in online if b["dead"])})
            self.history = [p for p in self.history if now - p["ts"] <= HISTORY_KEEP]
            json.dump(self.history, open(HISTORY_FILE, "w", encoding="utf-8"))

        # Experience of every bot once an hour: the gain over the last day is what the ranking uses.
        if not self.xp_history or now - self.xp_history[-1]["ts"] >= XP_EVERY:
            self.xp_history.append({"ts": round(now), "xp": {b["name"]: b["totalXp"] for b in bots}})
            self.xp_history = [p for p in self.xp_history if now - p["ts"] <= XP_KEEP]
            json.dump(self.xp_history, open(XP_FILE, "w", encoding="utf-8"))

        gains, stuck, oldest = [], None, self.xp_history[0] if self.xp_history else None
        if oldest and now - oldest["ts"] >= 600:      # under ten minutes the rate means nothing yet
            span = (now - oldest["ts"]) / 3600.0
            for b in bots:
                before = oldest["xp"].get(b["name"])
                if before is None or b["totalXp"] <= before:
                    continue
                gains.append({"name": b["name"], "cls": b["cls"], "spec": b["spec"], "role": b["role"],
                              "level": b["level"], "online": b["online"], "faction": b["faction"],
                              "xpPerHour": round((b["totalXp"] - before) / span)})
            gains.sort(key=lambda g: g["xpPerHour"], reverse=True)
            # A bot that is logged in, under the level cap and has not earned a single point of
            # experience over that whole span is stuck on something: that is what to go and look at.
            # Under an hour the figure means nothing - a bot can simply be walking to its next fight.
            if now - oldest["ts"] >= 3600:
                stuck = [b for b in bots if b["online"] and b["level"] < 60
                         and oldest["xp"].get(b["name"]) == b["totalXp"]]

        zone_counts = {}
        for b in online:
            zone_counts[b["zone"]] = zone_counts.get(b["zone"], 0) + 1

        # The last 24 hours against the 24 before them, from the same curve the page draws.
        def between(start, end, key):
            inside = [p for p in self.history if start <= p["ts"] <= end]
            return (inside[-1][key] - inside[0][key]) if len(inside) > 1 else None

        compare = {}
        for key in ("kills", "quests", "levels"):
            today, before = between(now - 24 * 3600, now, key), between(now - 48 * 3600, now - 24 * 3600, key)
            compare[key] = {"today": today, "before": before}

        def top(key, extra=None):
            ordered = sorted(bots, key=key, reverse=True)[:10]
            return [{k: b[k] for k in ("name", "cls", "spec", "role", "level", "xp", "kills", "quests", "online")}
                    for b in ordered]

        by_class = {}
        for b in bots:
            c = by_class.setdefault(b["cls"], {"name": b["cls"], "bots": 0, "levels": 0, "kills": 0, "best": None})
            c["bots"] += 1
            c["levels"] += b["level"]
            c["kills"] += b["kills"]
            c.setdefault("members", []).append(b)
            if c["best"] is None or (b["level"], b["xp"]) > (c["best"]["level"], c["best"]["xp"]):
                c["best"] = {"name": b["name"], "level": b["level"], "xp": b["xp"]}
        for c in by_class.values():
            # The three highest of the class, experience included so equal levels still separate.
            c["podium"] = [{"name": m["name"], "level": m["level"], "xp": m["xp"], "spec": m["spec"],
                            "role": m["role"], "online": m["online"], "faction": m["faction"]}
                           for m in sorted(c.pop("members"), key=lambda m: (m["level"], m["xp"]), reverse=True)[:3]]
        classes = sorted(({"name": c["name"], "bots": c["bots"], "avgLevel": round(c["levels"] / c["bots"], 2),
                           "kills": c["kills"], "best": c["best"], "podium": c["podium"]} for c in by_class.values()),
                         key=lambda c: c["avgLevel"], reverse=True)

        levels = {}
        for b in online:
            levels[b["level"]] = levels.get(b["level"], 0) + 1
        specs = {}
        for b in bots:
            if b["spec"]:
                k = (b["cls"], b["spec"], b["role"])
                specs[k] = specs.get(k, 0) + 1

        return {
            "generatedAt": datetime.datetime.now().strftime("%H:%M:%S"),
            "generatedTs": round(time.time()),
            "server": server_state(),
            "totals": totals,
            "session": session,
            "uptime": uptime,
            "history": self.history,
            "actions": action_usage((time.time() - COUNT_FROM) / 3600.0) if COUNT_FROM else action_usage(),
            "top": {
                "xp": top(lambda b: (b["level"], b["xp"])),
                "kills": top(lambda b: b["kills"]),
                "quests": top(lambda b: b["quests"]),
            },
            "roles": {r: sum(1 for b in online if b["role"] == r) for r in ("tank", "heal", "dps", "none")},
            "factions": {
                "online": {f: sum(1 for b in online if b["faction"] == f) for f in ("alliance", "horde")},
                "all": {f: sum(1 for b in bots if b["faction"] == f) for f in ("alliance", "horde")},
                "levelOnline": {f: round(sum(b["level"] for b in online if b["faction"] == f) /
                                         max(1, sum(1 for b in online if b["faction"] == f)), 1)
                                for f in ("alliance", "horde")},
            },
            "xpRate": {"hours": round((now - oldest["ts"]) / 3600.0, 1) if oldest else 0, "top": gains[:10]},
            "chat": chat_stats(),
            "watch": {
                "deadNow": sum(1 for b in online if b["dead"]),
                "stuck": None if stuck is None else len(stuck),
                "stuckNames": None if stuck is None else [b["name"] for b in sorted(
                    stuck, key=lambda b: b["level"])[:8]],
                "incidents": incidents(),
            },
            "zones": [{"name": self.zones.get(zone, "Zone %d" % zone), "count": n,
                       "alliance": sum(1 for b in online if b["zone"] == zone and b["faction"] == "alliance")}
                      for zone, n in sorted(zone_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]],
            "compare": compare,
            # "footer" in dashboard.json replaces the page's own line, and "" removes it: a server
            # that shares its page before it is ready may not want to point at its sources yet.
            "footer": SETTINGS.get("footer"),
            "classNames": {str(k): v for k, v in self.classes.items()},
            "bots": [{"n": b["name"], "c": b["cls"], "s": b["spec"], "r": b["role"], "l": b["level"],
                      "k": b["kills"], "q": b["quests"], "g": round(b["gold"], 1), "o": b["online"],
                      "f": b["faction"], "z": self.zones.get(b["zone"], ""), "h": round(b["hours"], 1)}
                     for b in bots],
            "loot": loot_feed(),
            "classes": classes,
            "levels": [{"level": lvl, "count": levels[lvl]} for lvl in sorted(levels)],
            "specs": [{"cls": c, "spec": s, "role": r, "count": n}
                      for (c, s, r), n in sorted(specs.items(), key=lambda item: item[1], reverse=True)],
        }


STATS = Stats()


def write_atomic(path, body):
    # Visitors never read a half-written file: write aside, then swap.
    temporary = path + ".tmp"
    with open(temporary, "wb") as handle:
        handle.write(body)
    os.replace(temporary, path)


def public_copy(data):
    """Stats for the public page: whether the server runs, no memory, crash or error details."""
    public = dict(data)
    public["server"] = {"running": bool(data.get("server", {}).get("running"))}
    public.pop("error", None)
    return public


def publish_loop():
    while True:
        try:
            data = STATS.get()
            os.makedirs(PUBLISH_DIR, exist_ok=True)
            write_atomic(os.path.join(PUBLISH_DIR, "stats.json"),
                         json.dumps(public_copy(data), ensure_ascii=False).encode("utf-8"))
            page = open(os.path.join(HERE, "index.html"), encoding="utf-8").read()
            page = page.replace('const API = "/api/stats";', 'const API = "stats.json";') \
                       .replace("const PUBLIC = false;", "const PUBLIC = true;")
            write_atomic(os.path.join(PUBLISH_DIR, "index.html"), page.encode("utf-8"))
        except Exception as error:  # the NAS may be asleep or unreachable: retry next minute
            print("Public copy failed (NAS asleep or unreachable):", error, flush=True)
        time.sleep(PUBLISH_EVERY)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] == "/api/stats":
            body = json.dumps(STATS.get(), ensure_ascii=False).encode("utf-8")
            content_type = "application/json; charset=utf-8"
        elif self.path in ("/", "/index.html"):
            body = open(os.path.join(HERE, "index.html"), "rb").read()
            content_type = "text/html; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("SquidBots dashboard: http://localhost:%d  (Ctrl+C to stop)" % PORT, flush=True)
    if PUBLISH_DIR:
        threading.Thread(target=publish_loop, daemon=True).start()
        print("Public copy refreshed every minute in %s" % PUBLISH_DIR, flush=True)
    server.serve_forever()
