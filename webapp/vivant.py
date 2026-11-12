"""The living world of CoA Bots 3.0: what the bots do, read from the files SquidBot writes (docs: LIAISON-3.0.md).

SquidBot writes world.json, economy.json, groups.json and monde.json (CoA Monde) in <logs>/squidbot/, each wrapped as
{schema, at, every, build_us, data}, and only while someone looks: the dashboard rewrites watch.json there
every half minute while this page is open. Until the module writes them, each missing topic is answered with
made-up figures marked "demo", so the page can be built and shown before the module exists.
"""
import json
import math
import os
import random
import threading
import time

TOPICS = ("world", "economy", "monde")
MAJOR = 1           # schema version this page understands: squidbot.<topic>/1
WATCH_EVERY = 30    # seconds between two writes of watch.json
HISTORY_EVERY = 15 * 60
HISTORY_KEEP = 48 * 3600
WORLD_EVERY = 5 * 60
WORLD_KEEP = 6 * 3600
RAMP_SHARE = .95    # the bots are "all in" from 95 % of the number asked for...
RAMP_AFTER = 300    # ...and the tick is counted from 5 minutes later (the user, 09/11: ignore the start-up)


class Vivant:
    def __init__(self, ctx, query=None, squidbot_dir=None, demo=False):
        self.ctx, self.query = ctx, query
        self.items = {}     # item entry -> (name, quality), read once from item_template
        # The module sends the auction count of the moment: the dashboard keeps the curve (a point per 15 min, 48 h).
        self.history_file = ctx.file("vivant-history.json")
        try:
            self.history = json.load(open(self.history_file, encoding="utf-8"))
        except (OSError, ValueError):
            self.history = []
        self.demo = demo            # made-up figures for a missing file: the dashboard's test realm only
        # Tick and bots online, a point per 5 min over 6 h, kept on disk so a restart of the dashboard keeps the curves.
        self.world_file = ctx.file("vivant-world.json")
        try:
            self.world_history = [p for p in json.load(open(self.world_file, encoding="utf-8"))
                                  if isinstance(p, dict) and time.time() - p.get("ts", 0) < WORLD_KEEP]
        except (OSError, ValueError):
            self.world_history = []
        self.ramp = {"start": None, "done": None}   # this server start, and when its bots were all in
        self.target = (0, None)                     # (read at, bots asked for in playerbots.conf)
        # The module's AiPlayerbot.CoaDataDir, by default <LogsDir>/squidbot: the folder of the realm's CoaBots.log.
        self.dir = (ctx.realm.key == "coa" and squidbot_dir) or os.path.join(os.path.dirname(ctx.coa_log), "squidbot")
        self.lock = threading.Lock()
        self.cache = {}
        self.watched = 0.0
        self.wanted = {}        # topic -> when a page last asked for it (the Server page wants world.json only)
        self.asked = 0.0        # last call of get(): the page polls every 15 s while it is shown
        self.resumed = 0.0      # when the watch began again after a pause

    def watch_world(self):
        """The Server page shows SquidBot's tick and players when the world console is off: keep world.json written."""
        with self.lock:
            self._watch(("world",))

    def live_figures(self):
        """Tick and players from a fresh world.json, for the server monitor; None when stale or absent."""
        with self.lock:
            world = self._read("world")
        if not world or world.get("error") or not world.get("at") or time.time() - float(world["at"]) > 3 * float(world.get("every") or 10):
            return None
        tick = ((world.get("health") or {}).get("tick_ms") or {}).get("avg")
        everyone = (world.get("everyone") or {}).get("total") or {}
        return {"tick": tick, "players": everyone.get("players", world.get("players"))}

    def _watch(self, topics):
        """Tell the module someone looks. The module makes its folder only when it writes, and writes only once watched:
        so the folder is made here, but only inside a logs folder that exists (never a stray path)."""
        now = time.time()
        for topic in topics:
            self.wanted[topic] = now
        topics = sorted(t for t, at in self.wanted.items() if now - at < 90)     # every page that looks, together
        if now - self.watched < WATCH_EVERY or not os.path.isdir(os.path.dirname(self.dir)):
            return
        self.watched = now
        try:
            os.makedirs(self.dir, exist_ok=True)
        except OSError:
            return
        tmp = os.path.join(self.dir, "watch.json.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump({"at": int(now), "topics": list(topics)}, handle)
            os.replace(tmp, os.path.join(self.dir, "watch.json"))
        except OSError:
            pass

    def _read(self, topic):
        path = os.path.join(self.dir, topic + ".json")
        try:
            stat = os.stat(path)
        except OSError:
            return None
        key = (stat.st_mtime_ns, stat.st_size)
        hit = self.cache.get(topic)
        if hit and hit[0] == key:
            return hit[1]
        # The module renames a new copy over the file; on Windows an open landing in that swap is refused: once more.
        for attempt in (0, 1):
            try:
                with open(path, "rb") as handle:
                    doc = json.loads(handle.read().decode("utf-8", errors="replace"))
                break
            except PermissionError as error:
                if attempt:
                    return {"error": "%s.json unreadable: %s" % (topic, error)}
                time.sleep(0.1)
            except (OSError, ValueError) as error:
                return {"error": "%s.json unreadable: %s" % (topic, error)}
        schema = str(doc.get("schema", ""))
        try:
            major = int(schema.rsplit("/", 1)[1].split(".")[0])
        except (IndexError, ValueError):
            major = -1
        if major != MAJOR:
            answer = {"error": "%s.json: schema %r is not one this dashboard reads (squidbot.%s/%d)" % (topic, schema, topic, MAJOR)}
        else:
            every = float(doc.get("every") or 10)
            answer = dict(doc.get("data") or {}, at=doc.get("at"), every=every, buildUs=doc.get("build_us"),
                          serverStart=doc.get("server_start"), module=doc.get("module"))
            if isinstance(doc.get("features"), dict) and "features" not in answer:
                answer["features"] = doc["features"]      # CoA Economy 3.0.1: beside server_start, what is on
        self.cache[topic] = (key, answer)
        return answer

    def get(self):
        with self.lock:
            now = time.time()
            # The modules write only while watch.json is under 90 s old. After a pause (page closed or hidden) the files
            # are old until each module writes again: not "stale" before it had 3 x every to do so.
            if now - self.asked > 90:
                self.resumed = now
            self.asked = now
            self._watch(TOPICS)
            out = {"demo": [], "stale": [], "missing": []}
            for topic in TOPICS:
                data = self._read(topic)
                if data is None:
                    if self.demo:
                        data = DEMO[topic](now)
                        out["demo"].append(topic)
                    else:
                        data = {}
                        out["missing"].append(topic)
                elif data.get("at") and now - float(data["at"]) > 3 * data.get("every", 10) and now - self.resumed > 3 * data.get("every", 10) + WATCH_EVERY:
                    out["stale"].append(topic)
                out[topic] = data
            if "economy" not in out["demo"] and not out["economy"].get("error"):
                self._name_items(out["economy"], ("top_sales_24h", "crafts_24h", "orders", "smelt_24h", "disenchant_24h", "prospect_24h"))
                out["economy"] = dict(out["economy"], categories=by_class(out["economy"].get("categories") or []))
                out["economy"] = dict(out["economy"], history=self._remember(out["economy"]))
            if "monde" not in out["demo"] and not out["monde"].get("error"):
                self._name_items(out["monde"], ("guild_orders",))
            if "world" not in out["demo"] and not out["world"].get("error"):
                world = out["world"]
                self._name_items(world, ("guild_orders",))
                health = dict(world.get("health") or {})
                world["ramp"] = self._ramp(world)
                health.setdefault("history", self._remember_world(world))
                out["world"] = dict(world, health=health)
            events = self._events()
            if events is None and self.demo:
                events = _demo_events(now)
                out["demo"].append("events")
            elif events is None:
                events = []
                out["missing"].append("events")
            out["events"] = events
            out["log"] = tail_text(self.ctx.coa_log, 120)
            out["groups"] = self._groups(out, now)
            return out

    def _groups(self, out, now):
        """Groups and dungeons, from three writers (LIAISON-3.0 §13): CoA SquidBot's world.json "groups" (real instance runs,
        null before the first), CoA World's monde.json "dungeon_sim" and "bg_sim" (null when off), Dungeon Clear's runs.jsonl."""
        world_on = "world" not in out["demo"] + out["missing"] and not out["world"].get("error")
        monde_on = "monde" not in out["demo"] + out["missing"] and not out["monde"].get("error")
        dc = self._last_runs()
        if not world_on and not monde_on and dc is None:
            if self.demo:
                out["demo"].append("groups")
                return _demo_groups(now)
            out["missing"].append("groups")
            return {}
        return {"real": out["world"].get("groups") if world_on else None, "worldOn": world_on,
                "sim": out["monde"].get("dungeon_sim") if monde_on else None,
                "bg": out["monde"].get("bg_sim") if monde_on else None, "mondeOn": monde_on, "dc": dc or []}

    def _remember(self, economy):
        at, auctions = economy.get("at"), economy.get("auctions")
        if at and auctions is not None and (not self.history or at - self.history[-1]["ts"] >= HISTORY_EVERY):
            self.history = [p for p in self.history if at - p["ts"] < HISTORY_KEEP] + [{"ts": int(at), "auctions": int(auctions)}]
            try:
                tmp = self.history_file + ".tmp"
                with open(tmp, "w", encoding="utf-8") as handle:
                    json.dump(self.history, handle)
                os.replace(tmp, self.history_file)
            except OSError:
                pass
        return self.history

    def _asked(self):
        """The random bots asked for: AiPlayerbot.MinRandomBots of the realm's playerbots.conf (read once a minute)."""
        now = time.time()
        if now - self.target[0] > 60:
            value = None
            folder = getattr(self.ctx, "config_dir", None)
            if folder:
                from webapp import realms
                raw = realms.conf_value(os.path.join(folder, "playerbots.conf"), "AiPlayerbot.MinRandomBots")
                try:
                    value = int(raw) if raw else None
                except ValueError:
                    value = None
            self.target = (now, value)
        return self.target[1]

    def _ramp(self, world):
        """Start-up: until the bots online reach 95 % of the number asked for, and 5 minutes more, the tick says nothing
        of the server at cruise. The module's own "ramp" wins ({target, done_at}); else playerbots.conf gives the number."""
        at, online = world.get("at"), world.get("online") or 0
        given = (world.get("health") or {}).get("ramp")
        if isinstance(given, dict) and "done_at" in given:
            # CoA SquidBot: tick_ms is null until done_at + after_s, then measured from there (its max included).
            # Without random bots (target 0) done_at is set at the module's first check: the same 300 s, then the tick.
            done, after = given.get("done_at"), int(given.get("after_s") or RAMP_AFTER)
            return {"target": given.get("target"), "online": online, "doneAt": done, "until": done + after if done else None,
                    "ramping": not done or (at or 0) < done + after, "source": "module"}
        target = self._asked()
        start = world.get("serverStart")
        if start != self.ramp["start"]:
            self.ramp = {"start": start, "done": None}
            self.world_history = []
        if not target or not at:
            return {"target": target, "online": online, "doneAt": None, "until": None, "ramping": False, "source": None}
        if self.ramp["done"] is None and online >= RAMP_SHARE * target:
            # Seen full for the first time: just now, unless this dashboard came long after the start (then it is over).
            self.ramp["done"] = at if not start or at - start < 2 * RAMP_AFTER else at - RAMP_AFTER
        done = self.ramp["done"]
        return {"target": target, "online": online, "doneAt": done, "until": done + RAMP_AFTER if done else None,
                "ramping": done is None or at < done + RAMP_AFTER, "source": "conf"}

    def _remember_world(self, world):
        at = world.get("at")
        tick = ((world.get("health") or {}).get("tick_ms") or {}).get("avg")
        if (world.get("ramp") or {}).get("ramping"):
            tick = None     # the curve keeps the bots online, not the start-up's tick
        if at and (not self.world_history or at - self.world_history[-1]["ts"] >= WORLD_EVERY):
            self.world_history = [p for p in self.world_history if at - p["ts"] < WORLD_KEEP] + [{"ts": int(at), "tick": tick, "online": world.get("online")}]
            try:
                tmp = self.world_file + ".tmp"
                with open(tmp, "w", encoding="utf-8") as handle:
                    json.dump(self.world_history, handle)
                os.replace(tmp, self.world_file)
            except OSError:
                pass
        return self.world_history

    def _name_items(self, doc, keys):
        """The modules give item entries only: add their name and quality (one query for the entries not seen yet)."""
        rows = [r for key in keys for r in doc.get(key) or [] if isinstance(r, dict) and r.get("item")]
        wanted = sorted({int(r["item"]) for r in rows} - set(self.items))
        if wanted and self.query:
            try:
                for entry, name, quality in self.query("SELECT entry, name, Quality FROM %s.item_template WHERE entry IN (%s)"
                                                      % (self.ctx.db["world"], ",".join(map(str, wanted)))):
                    self.items[int(entry)] = (name, int(quality))
            except Exception:  # noqa: BLE001  names are a comfort: the page shows the entry instead
                pass
        for r in rows:
            name, quality = self.items.get(int(r["item"]), (None, None))
            r.setdefault("name", name)
            if r.get("quality") is None:
                r["quality"] = quality

    def _last_runs(self, keep=8):
        """Dungeon Clear's finished runs (runs.jsonl, dc-3.0 ff66c98), newest first; None without the file.
        After a wipe a new `dc on` in the same instance starts a new line whose bossesKilled counts from there only: the
        lines of one instance make one run here (bosses and wipes added, first start, last end and result)."""
        path = os.path.join(self.dir, "runs.jsonl")
        rows = tail_jsonl(path, keep * 4)
        if rows is None:
            return None
        if len(rows) < keep * 4:
            rows += tail_jsonl(path + ".1", keep * 4 - len(rows)) or []     # just after a rotation (5 MB)
        runs, by_instance = [], {}
        for row in rows:                    # newest first
            key = row.get("instance")
            run = by_instance.get(key) if key is not None else None
            if run is None:
                run = dict(row, parts=1)
                runs.append(run)
                if key is not None:
                    by_instance[key] = run
                continue
            run["parts"] += 1
            run["bossesKilled"] = (run.get("bossesKilled") or 0) + (row.get("bossesKilled") or 0)
            if run.get("bossesTotal"):
                run["bossesKilled"] = min(run["bossesKilled"], run["bossesTotal"])
            run["wipes"] = (run.get("wipes") or 0) + (row.get("wipes") or 0)
            run["durationS"] = (run.get("durationS") or 0) + (row.get("durationS") or 0)
            if row.get("startedAtMs"):
                run["startedAtMs"] = min(run.get("startedAtMs") or row["startedAtMs"], row["startedAtMs"])
            run["bossTimeline"] = (row.get("bossTimeline") or []) + (run.get("bossTimeline") or [])
        return runs[:keep]

    def _events(self, keep=200):
        """The newest lines of events.jsonl, newest first, topped up from events.jsonl.1 just after a rotation;
        None when the module writes none (AiPlayerbot.CoaWorld.Events.Enable off)."""
        path = os.path.join(self.dir, "events.jsonl")
        rows = tail_jsonl(path, keep)
        if rows is not None and len(rows) < keep:
            rows += tail_jsonl(path + ".1", keep - len(rows)) or []
        return rows


def tail_jsonl(path, keep, span=256 * 1024):
    """The last `keep` well-formed lines of a JSON-lines journal, newest first, reading only its last `span` bytes."""
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            start = max(0, handle.tell() - span)
            handle.seek(start)
            lines = handle.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return None
    if start:
        lines = lines[1:]   # cut in the middle of a line
    rows = []
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
            if len(rows) == keep:
                break
    return rows


def tail_text(path, keep, span=64 * 1024):
    """The last `keep` lines of a text log (CoaBots.log), oldest first, reading only its last `span` bytes; None without it."""
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            start = max(0, handle.tell() - span)
            handle.seek(start)
            lines = handle.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return None
    if start:
        lines = lines[1:]
    return [line for line in lines if line.strip()][-keep:]


def by_class(categories):
    """The module counts per item class and subclass (Armor/Cloth, Armor/Plate…): one row per class here, prices
    weighted by auctions, a null price staying null when no subclass of the class has one."""
    rows = {}
    for c in categories:
        if not isinstance(c, dict) or "class" not in c:
            continue
        row = rows.setdefault(c["class"], {"class": c["class"], "subs": 0, "auctions": 0, "volume_24h": 0, "_w": {}})
        row["subs"] += 1
        n = int(c.get("auctions") or 0)
        row["auctions"] += n
        row["volume_24h"] += int(c.get("volume_24h") or 0)
        for key in ("avg", "low", "usual", "high"):
            if c.get(key) is not None:
                total, weight = row["_w"].get(key, (0, 0))
                row["_w"][key] = (total + c[key] * max(n, 1), weight + max(n, 1))
    out = []
    for row in rows.values():
        weights = row.pop("_w")
        for key in ("avg", "low", "usual", "high"):
            total, weight = weights.get(key, (0, 0))
            row[key] = round(total / weight) if weight else None
        out.append(row)
    return sorted(out, key=lambda r: -r["auctions"])


# ------------------------------------------------------------------ made-up figures ----
# Stable within a minute so the page does not jump at every refresh, moving slowly over the day.
def _rng(now, salt):
    return random.Random(int(now // 60) * 7 + salt)


ZONES = [(1519, "Stormwind City", True), (1637, "Orgrimmar", True), (1537, "Ironforge", True), (1638, "Thunder Bluff", True),
         (1657, "Darnassus", True), (1497, "Undercity", True), (12, "Elwynn Forest", False), (14, "Durotar", False),
         (40, "Westfall", False), (17, "The Barrens", False), (11, "Wetlands", False), (33, "Stranglethorn Vale", False),
         (45, "Arathi Highlands", False), (440, "Tanaris", False), (361, "Felwood", False), (139, "Eastern Plaguelands", False)]
DUNGEONS = [("dm", 36, "The Deadmines", 5), ("wc", 43, "Wailing Caverns", 8), ("rfk", 47, "Razorfen Kraul", 6), ("sm-cath", 189, "Scarlet Monastery", 4),
            ("zf", 209, "Zul'Farrak", 8), ("mara", 349, "Maraudon", 7), ("brd", 230, "Blackrock Depths", 15), ("strat", 329, "Stratholme", 10)]
NAMES = ["Arwen", "Thorgal", "Brienne", "Kaelis", "Morwen", "Drakkar", "Ysolde", "Grimbald", "Lyria", "Barok", "Seraphine", "Torvald"]


def _demo_world(now):
    r = _rng(now, 1)
    online = 480 + int(20 * math.sin(now / 3600)) + r.randint(-5, 5)
    weights = [r.uniform(.4, 1.6) * (3 if cap else 1) for _, _, cap in ZONES]
    total = sum(weights)
    zones = [{"zone": z, "name": n, "capital": cap, "bots": max(1, round(online * w / total))} for (z, n, cap), w in zip(ZONES, weights)]
    for z in zones:
        horde = z["zone"] in (1637, 1638, 1497, 14, 17) and .9 or z["zone"] in (1519, 1537, 1657, 12, 40) and .05 or r.uniform(.3, .7)
        z["faction"] = {"alliance": z["bots"] - round(z["bots"] * horde), "horde": round(z["bots"] * horde)}
    zones.sort(key=lambda z: -z["bots"])
    acts = {"quest": .36, "grind": .1, "camp": .03, "city": .15, "wander_random": .04, "wander_npc": .03, "flight": .05, "rest": .03,
            "fish": .02, "gather": .04, "pvp": .05, "dungeon": .07, "idle": .03}
    stuck = [{"name": r.choice(NAMES), "zone": r.choice(ZONES)[1], "since": int(now - r.randint(60, 900)),
              "why": r.choice(["no path", "falling", "loop on a quest giver", "inside a wall"])} for _ in range(r.randint(0, 3))]
    tick = r.randint(32, 48)
    return {"online": online, "players": r.randint(0, 3), "zones": zones,
            "activities": {k: round(online * v * r.uniform(.85, 1.15)) for k, v in acts.items()},
            "souls": {"lazy": round(online * .18), "quester": round(online * .34), "wanderer": round(online * .2),
                      "trader": round(online * .16), "pvp": round(online * .12)},
            "surname": {"mode": 2, "list_size": 64, "top": [{"name": n, "bots": r.randint(6, 14)} for n in
                        ("Stormhand", "Ashvale", "Ironbrook", "Duskmantle", "Emberfall", "Greywater", "Thornfield", "Brightwood")]},
            "health": {"tick_ms": {"avg": tick, "p95": tick + r.randint(15, 30), "max": tick + r.randint(60, 120)},
                       "bots_us_per_tick": {"avg": online * 19, "p95": online * 32},
                       "by_strategy_us": [{"name": n, "us": u} for n, u in
                                          [("rpg", 3100), ("travel", 1900), ("combat", 1700), ("city life", 900), ("loot", 600), ("economy", 400)]],
                       "stuck": stuck,
                       "history": [{"ts": int(now - i * 300), "tick": 36 + 8 * math.sin((now - i * 300) / 2400) + _rng(now - i * 300, 9).uniform(-3, 3),
                                    "online": round(online * (1 + .05 * math.sin((now - i * 300) / 3000)))} for i in range(72, -1, -1)]},
            "at": int(now), "every": 10, "buildUs": 410}


ITEMS = [(14047, "Runecloth", 1, 640000), (12359, "Thorium Bar", 1, 410000), (13444, "Major Mana Potion", 1, 380000),
         (8836, "Arthas' Tears", 1, 205000), (14344, "Large Brilliant Shard", 3, 190000), (12804, "Powerful Mojo", 2, 150000),
         (4338, "Mageweave Cloth", 1, 120000), (13464, "Golden Sansam", 1, 95000)]
CATEGORIES = [("Trade goods", 7, 1200, 2350), ("Consumables", 0, 820, 1800), ("Armor", 4, 640, 14500), ("Weapons", 2, 210, 22800),
              ("Recipes", 9, 120, 6400), ("Gems", 3, 75, 9800), ("Containers", 1, 64, 12000)]


def _demo_economy(now):
    r = _rng(now, 2)
    cats = []
    for name, cls, auctions, avg in CATEGORIES:
        a = round(avg * r.uniform(.9, 1.1))
        cats.append({"name": name, "class": cls, "auctions": round(auctions * r.uniform(.9, 1.1)), "avg": a,
                     "low": round(a * .45), "usual": round(a * .9), "high": round(a * 2.1), "volume_24h": round(auctions * r.uniform(.6, 1.2))})
    return {"auctions": sum(c["auctions"] for c in cats), "gold_circulating": 18450000 + r.randint(-90000, 90000),
            "gold_bots": 16200000 + r.randint(-90000, 90000), "categories": cats,
            "top_sales_24h": [{"item": i, "name": n, "quality": q, "count": r.randint(20, 220), "gold": round(g * r.uniform(.8, 1.2))} for i, n, q, g in ITEMS],
            "crafts_24h": [{"skill": 197, "name": "Runecloth Bag", "quality": 1, "count": 31, "profit": 52000},
                           {"skill": 171, "name": "Major Healing Potion", "quality": 1, "count": 64, "profit": 38000},
                           {"skill": 164, "name": "Thorium Belt", "quality": 2, "count": 6, "profit": 27000},
                           {"skill": 333, "name": "Large Brilliant Shard", "quality": 3, "count": 18, "profit": 21000}],
            "orders": [{"id": 77, "buyer": "Squid", "bot": "Thorgal", "name": "Arcanite Reaper", "quality": 4, "price": 1250000, "state": "mailed", "at": int(now - 1800)},
                       {"id": 78, "buyer": "Squid", "bot": "Lyria", "name": "Robe of the Void", "quality": 4, "price": 640000, "state": "busy", "at": int(now - 5400)},
                       {"id": 74, "buyer": "Nimue", "bot": "Grimbald", "name": "Thorium Shield Spike", "quality": 2, "price": 85000, "state": "refused", "at": int(now - 86000)}],
            "smelt_24h": [{"item": 12359, "name": "Thorium Bar", "quality": 1, "count": 140}, {"item": 6037, "name": "Truesilver Bar", "quality": 2, "count": 22},
                          {"item": 3860, "name": "Mithril Bar", "quality": 1, "count": 61}],
            "disenchant_24h": [{"item": 14344, "name": "Large Brilliant Shard", "quality": 3, "count": 18, "from": 18},
                               {"item": 16204, "name": "Illusion Dust", "quality": 1, "count": 96, "from": 41},
                               {"item": 16203, "name": "Greater Eternal Essence", "quality": 2, "count": 12, "from": 30}],
            "prospect_24h": [{"item": 1705, "name": "Lesser Moonstone", "quality": 2, "count": 9, "from": 40}],
            "clock": {"enabled": 1, "offline_added_s": 7200, "resumed": 2810, "expired_24h": r.randint(300, 420), "sold_24h": r.randint(800, 1100), "relisted_24h": None},
            "ahbot_24h": {"listed": r.randint(2400, 2800), "bought": r.randint(500, 700), "gold_in": 4100000, "gold_out": 3650000},
            "history": [{"ts": int(now - i * 3600), "auctions": 3000 + 300 * math.sin((now - i * 3600) / 20000)} for i in range(48, -1, -1)],
            "at": int(now), "every": 60, "buildUs": 1250}


def _demo_groups(now):
    """Made-up groups in the shape the page reads: CoA SquidBot's world.json "groups" (real instance runs), CoA World's
    monde.json "dungeon_sim" and "bg_sim" (bots logged out while simulated), Dungeon Clear's runs.jsonl lines."""
    r = _rng(now, 3)
    since = int(now // 86400 * 86400)
    running = []
    for key, map_id, name, bosses in r.sample(DUNGEONS, 2):
        running.append({"instance": r.randint(100, 999), "map": map_id, "dungeon": None, "dungeonName": name, "kind": "dungeon",
                        "difficulty": r.choice([0, 0, 1]), "players": r.choice([0, 1]), "alts": r.choice([0, 4]), "bots": r.randint(1, 5),
                        "leader": r.choice(NAMES), "startedAt": int(now - r.randint(300, 2400)), "bossesKilled": r.randint(0, bosses - 1),
                        "bossesTotal": bosses, "wipes": r.choice([0, 0, 1]), "dc": None})
    by = [{"map": m, "dungeon": None, "dungeonName": n, "runs": r.randint(1, 6), "cleared": 0, "wipes": r.randint(0, 3),
           "medianS": b * 240 + r.randint(-120, 300), "bestS": b * 200} for _, m, n, b in DUNGEONS[:5]]
    for row in by:
        row["cleared"] = max(0, row["runs"] - r.randint(0, 2))
    last = []
    for i in range(6):
        _, map_id, name, bosses = r.choice(DUNGEONS)
        end = int(now - i * 900 - r.randint(0, 600))
        result = r.choice(["clear", "clear", "wipe", "left"])
        last.append({"instance": 900 - i, "map": map_id, "dungeon": None, "dungeonName": name, "difficulty": 0, "startedAt": end - r.randint(900, 2600),
                     "endedAt": end, "result": result, "bossesKilled": bosses if result == "clear" else r.randint(0, bosses - 1), "bossesTotal": bosses,
                     "wipes": r.randint(0, 2), "players": r.choice([0, 1]), "alts": r.choice([0, 4]), "bots": r.randint(1, 5), "dc": None})
    real = {"running": running, "byDungeon": by, "last": last,
            "today": {"since": since, "runs": sum(b["runs"] for b in by), "cleared": sum(b["cleared"] for b in by),
                      "wipes": sum(b["wipes"] for b in by), "bossKills": sum(b["cleared"] for b in by) * 5}}
    sim = {"running": [{"dungeon": 209, "dungeonName": "Zul'Farrak", "faction": "horde", "level": 46, "bots": 5, "phase": "inside",
                        "startedAt": int(now - 600), "endsAt": int(now + 1200), "bosses": 6},
                       {"dungeon": 36, "dungeonName": "The Deadmines", "faction": "alliance", "level": 19, "bots": 5, "phase": "gathering",
                        "startedAt": int(now - 120), "endsAt": None, "bosses": 0}],
           "today": {"since": since, "runs": r.randint(8, 20), "bossKills": r.randint(40, 90), "items": r.randint(30, 80)},
           "last": [{"dungeon": 47, "dungeonName": "Razorfen Kraul", "bots": 5, "durationS": 1500, "bossesKilled": 5, "at": int(now - 1800)}]}
    bg = {"running": [{"bg": 489, "bgName": "Warsong Gulch", "levelMin": 50, "levelMax": 59, "alliance": 10, "horde": 10, "phase": "playing",
                       "startedAt": int(now - 500), "endsAt": int(now + 700)}],
          "today": {"since": since, "matches": r.randint(5, 15), "allianceWins": r.randint(2, 7), "hordeWins": r.randint(2, 7),
                    "honor": r.randint(20000, 60000), "purchases": r.randint(1, 9)},
          "last": [{"bg": 529, "bgName": "Arathi Basin", "levelMin": 50, "levelMax": 59, "bots": 30, "winner": "alliance", "durationS": 1320,
                    "honor": 9400, "at": int(now - 2600)}]}
    dc = [{"runId": 9001, "instance": 901, "dungeon": "sfk", "dungeonName": "Shadowfang Keep", "difficulty": 0, "startedAtMs": int((now - 4000) * 1000),
           "endedAtMs": int((now - 2600) * 1000), "durationS": 1400, "result": "clear", "bossesKilled": 6, "bossesTotal": 6, "wipes": 0,
           "comp": [{"name": n} for n in NAMES[:5]], "players": ["Squid"]}]
    return {"real": real, "sim": sim, "bg": bg, "dc": dc, "worldOn": True, "mondeOn": True}


def _demo_monde(now):
    """CoA Monde's state of the moment (proposed 09/11): invasions, rushes, guilds and their orders, server firsts."""
    r = _rng(now, 5)
    return {"invasions": [{"zone": 10, "map": 0, "name": "Duskwood", "kind": "scourge", "site": "Darkshire", "state": "running", "level": 25, "wave": 2,
                           "since": int(now - 1500), "starts": None, "ends": int(now + 2100), "bots": r.randint(12, 30)}],
            "rushes": [{"what": "gathering nodes", "zone": 33, "map": 0, "name": "Stranglethorn Vale", "area": "Mizjah Ruins", "level": 40, "nodes": 14,
                        "since": int(now - 900), "ends": int(now + 900), "bots": 9}],
            "guilds": [{"id": 1, "name": "Iron Tide", "members": 48, "bots": 46, "online": r.randint(18, 30), "bank_gold": 12500000, "orders_open": None},
                       {"id": 2, "name": "Moonwhisper", "members": 37, "bots": 37, "online": r.randint(10, 22), "bank_gold": 8400000, "orders_open": None},
                       {"id": 3, "name": "Blood of Ashenvale", "members": 29, "bots": 28, "online": r.randint(8, 16), "bank_gold": None, "orders_open": None}],
            "guild_orders": [{"id": 12, "guild": "Iron Tide", "item": 13444, "name": "Major Mana Potion", "quality": 1, "count": 20, "state": "crafted", "by": "Lyria", "at": int(now - 3000)},
                             {"id": 11, "guild": "Moonwhisper", "item": 14047, "name": "Runecloth", "quality": 1, "count": 60, "state": "shared", "by": "Thorgal", "at": int(now - 9000)}],
            "server_firsts": [{"what": "level 60 (the Alliance)", "by": "Kaelis", "guild": "Iron Tide", "at": int(now - 20000)},
                              {"what": "Onyxia (the Horde)", "by": "Grimbald", "guild": "Moonwhisper", "at": int(now - 50000)}],
            "recovery_24h": {"stuck": r.randint(8, 20), "unstuck": r.randint(6, 18)},
            "at": int(now), "every": 30, "buildUs": 60}


def _demo_events(now):
    r = _rng(now, 4)
    lines = [("invasion", "", "The Scourge invades Darkshire: guards and bots rally at the town hall."),
             ("rush", "", "Rush on Zul'Farrak: 4 groups of bots heading there."),
             ("server_first", "Kaelis", "Server first: Kaelis reaches level 60."),
             ("guild", "Grimbald", "<Iron Tide> Grimbald dings 42."),
             ("guild", "Lyria", "<Moonwhisper> Lyria loots [Robe of the Archmage]."),
             ("stuck", "Arwen", "Stuck in Westfall (no path) for 3 min."),
             ("unstuck", "Arwen", "Freed: teleported to the nearest graveyard."),
             ("boss", "Thorgal", "Group of Thorgal kills Edwin VanCleef (The Deadmines)."),
             ("wipe", "Brienne", "Group of Brienne wipes on Gahz'rilla (Zul'Farrak)."),
             ("order", "Thorgal", "Thorgal mails [Arcanite Reaper] to Squid."),
             ("error", "", "CoA Economy: cannot write economy.json.tmp")]
    out, at = [], now
    for _ in range(40):
        kind, bot, text = r.choice(lines)
        at -= r.randint(20, 400)
        out.append({"at": int(at), "kind": kind, "bot": bot, "text": text})
    return out


DEMO = {"world": _demo_world, "economy": _demo_economy, "monde": _demo_monde}
