"""The regulars of the realm.

A busy realm has faces you come to know: the same handful of people are in chat every night, they have friends and running
jokes, and they remember you. The bots are anonymous by default, so a small cast of them is picked once and kept: it gets
a fuller character sheet, a few friendships with each other, and is preferred whenever the game needs someone to start
talking or to carry a conversation. Everyone else stays background.

The game tells us who is around (`sync`); we answer with who the regulars are. The cast is chosen so that the guilds the
players belong to are well represented (a guild that is all regulars is a guild that feels lived in), both factions have
some, and a regular stays a regular across restarts.
"""
import json
import random
import re
import threading
import time

from . import filters, personas, rp as rp_module

# Who the regulars tend to be: mostly ordinary and friendly, a few with an edge, and no more than one or two trolls.
CAST_MIX = {"friendly helper": 5, "regular": 4, "chill": 3, "lore nerd": 2, "gold goblin": 2, "returning player": 2,
            "quiet grinder": 2, "old-school roleplayer": 2, "overconfident newbie": 1, "try-hard min-maxer": 1,
            "meme lord": 1, "banter merchant": 1, "salty veteran": 1, "cynic": 1, "lurker": 1, "troll": 1}

BOND_KINDS = ("friends", "best friends", "rivals", "siblings", "old guildmates", "mentor and student", "running joke")
RP_BOND_KINDS = ("friends", "old comrades", "rivals", "siblings", "mentor and student", "fellow pilgrims", "bound by a shared oath")
FIELD_LIMITS = {"traits": 120, "speech_style": 220, "interests": 100, "backstory": 340, "opinions": 220}
BATCH = 10

SHEET_SYSTEM = (
    "You write character sheets for the regulars of a busy fantasy MMO realm's chat: the people who are always around. Each "
    "is a real-feeling player, not a hero: how long they have played, what they do in the game, a habit, a pet peeve, how "
    "they type. Most are friendly and easy to talk to; a few have an edge, but nobody is cruel. Keep each to the kind of "
    "person you are given. Answer with a JSON array, one object per person, each with: \"guid\" (as given), \"traits\" (three "
    "short adjectives, comma separated), \"speech_style\" (one sentence on how they type: case, length, slang, a tic), "
    "\"interests\" (two short things, comma separated), \"backstory\" (two short sentences about their life in this game, "
    "including a running joke or a habit other regulars would know), \"opinions\" (one or two short hot takes, separated by "
    "semicolons). No slurs or hate, nothing sexual, no real-world politics, no em dashes or en dashes, no quotation marks "
    "inside the text. Answer with the JSON array and nothing else.")

BOND_SYSTEM = (
    "You decide how the regulars of a fantasy MMO realm's chat know each other. You are given a roster (guid, name, kind of "
    "person, a line about them) and which of them are NEW. Give every new person two or three bonds with people from the roster, "
    "new or old, who would plausibly get on, or clash, given who they are. Each bond has a \"kind\" (one of: %s) and a \"note\": "
    "one short shared history or running joke that both would mention, under 100 characters, in plain words, no quotation "
    "marks. Answer with a JSON array of objects {\"a\": guid, \"b\": guid, \"kind\": ..., \"note\": ...} and nothing else."
    % ", ".join(BOND_KINDS))


RP_BOND_SYSTEM = (
    "You decide how the people of one corner of the world of Warcraft (the age of the Lich King) know each other. You are given a roster "
    "(guid, name, side, race and calling, a line about them) and which of them are NEW. Give every new person two or three bonds with "
    "people from the roster, new or old, of the SAME side, who would plausibly be drawn together or clash, given who they are. Each bond "
    "has a \"kind\" (one of: %s) and a \"note\": one short shared history both would mention, in the world's own terms (an old campaign, a "
    "debt, a road walked together), under 100 characters, plain words, no quotation marks, no mention of games, levels or players. "
    "Answer with a JSON array of objects {\"a\": guid, \"b\": guid, \"kind\": ..., \"note\": ...} and nothing else."
    % ", ".join(RP_BOND_KINDS))


def short_name(name):
    """'Flutki Bot' -> 'Flutki'; a character with a surname of its own ('Elorin Moonwhisper') goes by its first name."""
    name = re.sub(r"\s+bot$", "", str(name or ""), flags=re.I).strip()
    return name.split(" ")[0] if " " in name else name


def _json_array(text):
    text = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        raise ValueError("the model did not return a JSON array")
    return json.loads(text[start:end + 1])


class Community:
    def __init__(self, gateway):
        self.gateway = gateway
        self.store = gateway.store
        self.lock = threading.Lock()
        self.job = {"running": False, "sheets": 0, "bonds": 0, "errors": 0, "last_error": ""}
        self.rng = random.Random()    # a test replaces it

    # ---- the ops the game and the dashboard ask for --------------------------------------------------

    def command(self, body):
        op = body.get("op")
        if op == "status":
            return self.status()
        if op == "sync":
            return self.sync(body)
        if op == "rank":
            return self.rank(body)
        if op == "mode":
            return self.mode()
        return {"ok": False, "error": "unknown cast op %r" % op}

    def mode(self):
        """How the bots should talk, for the game to follow: "roleplay" (characters in the lore, talking only where `channels` says)
        or "players" (the game's own channel list stays in charge)."""
        gateway = self.gateway
        channels = rp_module.parse_channels(self.store.setting("rp_channels"))
        return {"ok": True, "chat_mode": gateway.chat_mode(), "channels": channels if channels is not None else ["say", "yell", "guild"]}

    def status(self):
        store = self.store
        bonds = {}
        for bond in store.bonds():
            bonds.setdefault(bond["a"], []).append(bond)
        names = {member["bot_guid"]: member["name"] for member in store.cast()}
        members = []
        for member in store.cast():
            persona = store.persona(member["bot_guid"]) or {}
            character = store.rp_character(member["bot_guid"]) if self.gateway.roleplaying() else None
            if character:
                persona = {"archetype": "%s %s" % (character["race"], rp_module.calling_label(character["race"], character["calling"])),
                           "source": "roleplay", "backstory": (character["story"] or character["facts"])[:340]}
            members.append({
                "guid": member["bot_guid"], "name": member["name"], "team": member["team"], "guild_id": member["guild_id"],
                "class": member["klass"], "level": member["level"], "archetype": persona.get("archetype", ""),
                "source": persona.get("source", ""), "backstory": persona.get("backstory", ""),
                "friends": [{"guid": bond["b"], "name": names.get(bond["b"], ""), "kind": bond["kind"], "note": bond["note"]}
                            for bond in bonds.get(member["bot_guid"], ()) if bond["b"] in names]})
        with self.lock:
            job = dict(self.job)
        return {"ok": True, "size": len(members), "cast": members, "job": job, "chat_mode": self.gateway.chat_mode()}

    def sync(self, body):
        """{"op": "sync", "candidates": [{guid, name, team, guild_id, level, class}], "homes": [guild ids], "size": n}: who
        is around and which guilds the players are in; answers with the cast, after keeping the regulars who are still
        around and filling the rest. Writing the newcomers' sheets and friendships goes on in the background."""
        store = self.store
        try:
            size = int(body.get("size") or store.setting("cast_size"))
        except (TypeError, ValueError):
            size = 24
        size = max(4, min(size, 60))
        around = {}
        for item in body.get("candidates") or []:
            try:
                guid = int(item["guid"])
            except (KeyError, TypeError, ValueError):
                continue
            around[guid] = {"bot_guid": guid, "name": str(item.get("name") or "")[:40], "team": int(item.get("team") or 0),
                            "guild_id": int(item.get("guild_id") or 0), "klass": str(item.get("class") or "")[:20],
                            "level": int(item.get("level") or 0), "race": str(item.get("race") or "")[:20],
                            "gender": str(item.get("gender") or "")[:8]}
        homes = set()
        for guild in body.get("homes") or []:
            try:
                if int(guild) > 0:
                    homes.add(int(guild))
            except (TypeError, ValueError):
                continue
        current = store.cast()
        known = {row["bot_guid"] for row in current}
        # A list this short is a realm that has just started, not a realm whose bots are gone: keep everyone then.
        still = [row["bot_guid"] for row in current if row["bot_guid"] in around or len(around) < 30]
        chosen = []

        def take(guid):
            if guid not in chosen and len(chosen) < size:
                chosen.append(guid)

        # Guildmates of the players first: a guild that is all regulars is a guild that feels lived in.
        quota = -(-size * 65 // 100)
        at_home = sorted((guid for guid, member in around.items() if member["guild_id"] in homes),
                         key=lambda guid: (guid not in known, guid))
        for guid in at_home[:quota]:
            take(guid)
        for guid in still:                      # then the regulars already here, longest serving first
            take(guid)
        pool = {0: [], 1: []}
        for guid, member in around.items():
            if guid not in chosen:
                pool[member["team"] if member["team"] in (0, 1) else 0].append(guid)
        for team in pool:
            self.rng.shuffle(pool[team])
        side = 0
        while len(chosen) < size and (pool[0] or pool[1]):
            if pool[side]:
                take(pool[side].pop())
            side = 1 - side

        members = []
        previous = {row["bot_guid"]: row for row in current}
        for guid in chosen:
            members.append(around.get(guid) or {"bot_guid": guid, "name": previous[guid]["name"], "team": previous[guid]["team"],
                                                "guild_id": previous[guid]["guild_id"], "klass": previous[guid]["klass"],
                                                "level": previous[guid]["level"]})
        store.set_cast(members)
        newcomers = [guid for guid in chosen if guid not in known]
        roleplay = self.gateway.roleplaying()
        if roleplay:      # a regular is a person with a life from the start: the story is written before anyone asks about it
            for member in members:
                ctx = rp_module.clean_context({"race": member.get("race"), "klass": member.get("klass"), "gender": member.get("gender"),
                                               "level": member.get("level")})
                if ctx.get("race") and ctx.get("klass"):
                    self.gateway.rp.character(member["bot_guid"], member["name"], ctx)
        unwritten = [] if roleplay else [guid for guid in chosen if (store.persona(guid) or {}).get("source") != "cast"]
        if newcomers or unwritten:
            self._start_job(sorted(set(newcomers) | set(unwritten)))
        return self.status() | {"added": len(newcomers)}

    def rank(self, body):
        """{"op": "rank", "player_guid", "candidates": [guids]}: the candidates, those who know the player best first.
        Someone who has never met them comes last; that is who you would expect to say hello to a stranger."""
        try:
            player = int(body.get("player_guid"))
        except (TypeError, ValueError):
            return {"ok": False, "error": "player_guid is required"}
        scored = []
        for raw in body.get("candidates") or []:
            try:
                guid = int(raw)
            except (TypeError, ValueError):
                continue
            relation = self.store.relationship(guid, player)
            if relation:
                score = 1.0 + relation["affinity"] + min(relation["interactions"], 50) / 50.0
            else:
                score = 0.0
            scored.append((score + self.rng.random() * 0.3, guid, bool(relation)))
        scored.sort(reverse=True)
        return {"ok": True, "order": [guid for _, guid, _ in scored], "known": [guid for _, guid, known in scored if known]}

    # ---- bonds, read by the chat ---------------------------------------------------------------------

    def friends(self, guid):
        """[{guid, name, kind, note}] for a regular, with the friend's name."""
        names = {member["bot_guid"]: member["name"] for member in self.store.cast()}
        return [{"guid": bond["b"], "name": names.get(bond["b"], ""), "kind": bond["kind"], "note": bond["note"]}
                for bond in self.store.bonds_of(guid) if bond["b"] in names]

    def bond(self, a, b):
        return self.store.bond(a, b)

    # ---- writing the newcomers' sheets and friendships -----------------------------------------------

    def _start_job(self, guids):
        with self.lock:
            if self.job["running"]:
                return
            self.job = {"running": True, "sheets": 0, "bonds": 0, "errors": 0, "last_error": ""}
        threading.Thread(target=self._write, args=(guids,), daemon=True).start()

    def _dispatch(self, request):
        profile = self.store.profile_for("ambient", 0) or self.store.profile_for("fast", 0)
        if not profile:
            raise RuntimeError("no model is assigned to the ambient or quick-decisions lane")
        answer, _ = self.gateway._dispatch("bank", 0, profile, request, set())
        return ((answer.get("choices") or [{}])[0].get("message") or {}).get("content") or ""

    def _fail(self, error):
        with self.lock:
            self.job["errors"] += 1
            self.job["last_error"] = str(error)[:200]

    def _write(self, guids):
        try:
            by_guid = {member["bot_guid"]: member for member in self.store.cast()}
            roleplay = self.gateway.roleplaying()
            for start in range(0, 0 if roleplay else len(guids), BATCH):     # a roleplaying regular's sheet is its character: nothing to write
                batch = [guid for guid in guids[start:start + BATCH] if guid in by_guid]
                try:
                    self._write_sheets(batch, by_guid)
                except Exception as error:  # noqa: BLE001 - one batch failing must not stop the rest
                    self._fail(error)
            try:
                self._write_bonds(guids, by_guid)
            except Exception as error:  # noqa: BLE001
                self._fail(error)
        finally:
            with self.lock:
                self.job["running"] = False

    def _preset(self, guid, member):
        persona = self.store.persona(guid)
        if persona and persona.get("archetype"):
            return persona
        return dict(personas.generate(guid, member["name"], mix=CAST_MIX), name=member["name"])

    def _write_sheets(self, batch, by_guid):
        if not batch:
            return
        presets = {guid: self._preset(guid, by_guid[guid]) for guid in batch}
        lines = []
        for guid in batch:
            member, preset = by_guid[guid], presets[guid]
            lines.append("guid %d: %s, a level %s %s; kind of person: %s (%s); types: %s" % (
                guid, short_name(member["name"]), member["level"] or "?", member["klass"] or "adventurer",
                preset["archetype"], preset.get("traits", ""), preset.get("speech_style", "")))
        text = self._dispatch({"messages": [{"role": "system", "content": SHEET_SYSTEM},
                                            {"role": "user", "content": "\n".join(lines)}],
                               "temperature": 1.0, "max_tokens": 3000})
        written = 0
        for item in _json_array(text):
            try:
                guid = int(item["guid"])
            except (KeyError, TypeError, ValueError):
                continue
            if guid not in presets:
                continue
            fields = dict(presets[guid])
            for key, limit in FIELD_LIMITS.items():
                value = filters.plain_typography(str(item.get(key) or "")).replace('"', "").strip()
                if value:
                    fields[key] = value[:limit]
            fields["name"] = by_guid[guid]["name"]
            self.store.save_persona(guid, fields, "cast")
            written += 1
        with self.lock:
            self.job["sheets"] += written
        for guid in batch:      # a sheet the model skipped still makes that bot a regular, with the preset it was given
            if (self.store.persona(guid) or {}).get("source") != "cast":
                self.store.save_persona(guid, dict(presets[guid], name=by_guid[guid]["name"]), "cast")

    def _write_bonds(self, newcomers, by_guid):
        roleplay = self.gateway.roleplaying()
        roster = []
        for guid, member in by_guid.items():
            if roleplay:
                character = self.store.rp_character(guid)
                if not character:
                    continue       # not yet seen with a race and a class: no one to bond it with
                side = "Alliance" if member["team"] == 0 else "Horde"
                roster.append("guid %d: %s, %s, %s %s%s; %s" % (
                    guid, short_name(member["name"]), side, character["race"], rp_module.calling_label(character["race"], character["calling"]),
                    " (NEW)" if guid in newcomers else "", character["traits"][:110]))
                continue
            persona = self.store.persona(guid) or {}
            roster.append("guid %d: %s, %s%s; %s" % (
                guid, short_name(member["name"]), persona.get("archetype", "regular"),
                " (NEW)" if guid in newcomers else "", (persona.get("backstory") or persona.get("traits") or "")[:110]))
        if len(roster) < 2 or not newcomers:
            return
        text = self._dispatch({"messages": [{"role": "system", "content": RP_BOND_SYSTEM if roleplay else BOND_SYSTEM},
                                            {"role": "user", "content": "\n".join(roster)}],
                               "temperature": 1.0, "max_tokens": 4000})
        made = 0
        for item in _json_array(text):
            try:
                a, b = int(item["a"]), int(item["b"])
            except (KeyError, TypeError, ValueError):
                continue
            if a == b or a not in by_guid or b not in by_guid:
                continue
            if roleplay and by_guid[a]["team"] != by_guid[b]["team"]:
                continue       # the Alliance and the Horde are not old comrades
            kind = str(item.get("kind") or "friends").strip().lower()
            kind = kind if kind in (RP_BOND_KINDS if roleplay else BOND_KINDS) else "friends"
            note = filters.plain_typography(str(item.get("note") or "")).replace('"', "").strip()
            self.store.add_bond(a, b, kind, note)
            made += 1
        with self.lock:
            self.job["bonds"] += made
