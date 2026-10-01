"""What the dashboard's Minds page reads and writes. squidbots.py only routes to here.

Everything a browser sends is validated before it reaches the store, and the store only takes parameters.
API keys are never accepted or returned: a profile names an environment variable (or an entry in the
secrets file) and this module can say whether a key was found, never what it is.
"""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from . import ambient as ambient_module, bank as bank_module, gateway as gateway_module, memory as memory_module, personas, rp as rp_module, rp_bank, store as store_module, upstream

LANES = gateway_module.LANES
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.\-]{0,39}$")
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
SERVICE_FRESH_S = 20


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _text(value, field, limit, required=False):
    text = "".join(ch for ch in str(value if value is not None else "") if ch == "\n" or ch >= " ").strip()
    if required and not text:
        raise ApiError("%s is required" % field)
    if len(text) > limit:
        raise ApiError("%s is longer than %d characters" % (field, limit))
    return text


def _number(value, field, low, high, integer=False):
    try:
        number = int(value) if integer else float(value)
    except (TypeError, ValueError):
        raise ApiError("%s must be a number" % field)
    if not low <= number <= high:
        raise ApiError("%s must be between %s and %s" % (field, low, high))
    return number


def _flag(value):
    return 1 if value in (1, True, "1", "true", "on") else 0


class Api:
    """`resolve(name)` -> (guid, canonical name) or None: how the dashboard turns a character name into the
    guid the database is keyed on. It is given in so this package never talks to the game database."""

    def __init__(self, store, settings, resolve):
        self.store = store
        self.settings = settings
        self.resolve = resolve

    # ---- reads ---------------------------------------------------------------------------------------

    def service(self):
        try:
            with open(self.settings["statusFile"], encoding="utf-8") as handle:
                beat = json.load(handle)
        except (OSError, ValueError):
            return {"running": False, "age": None, "keys": {}}
        age = time.time() - beat.get("at", 0)
        return {"running": age < SERVICE_FRESH_S, "age": round(age), "port": beat.get("port"),
                "pid": beat.get("pid"), "inflight": beat.get("inflight", 0), "keys": beat.get("keys", {}),
                "noPlayer": beat.get("noPlayer", 0), "plainChats": beat.get("plainChats", 0), "roleplayRetries": beat.get("roleplayRetries", 0),
                "jev": beat.get("jev") or {},
                "started": beat.get("started")}

    def overview(self):
        store = self.store
        settings = store.settings()
        since_day = time.time() - 86400
        profiles = store.profiles()
        usage = {(row["profile"], row["lane"]): row for row in store.usage_summary(since_day)}
        keys = self.service()["keys"]
        for profile in profiles:
            profile["key"] = keys.get(profile["name"], "unknown")
            profile["calls_24h"] = sum(row["calls"] for (name, _), row in usage.items() if name == profile["name"])
            profile["cost_24h"] = sum(row["cost_usd"] or 0 for (name, _), row in usage.items()
                                      if name == profile["name"])
        return {
            "service": self.service(),
            "counts": store.counts(),
            "settings": settings,
            "archetypes": sorted(personas.ARCHETYPES),
            "defaults": {"personality_mix": personas.mix_text(), "ambient_vibe": ambient_module.DEFAULT_VIBE,
                         "rp_rules": store_module.SETTING_DEFAULTS["rp_rules"]},
            "roleplay": dict(store.rp_stats(), channel_kinds=list(rp_module.CHANNEL_KINDS)),
            "lanes": store.lanes(),
            "profiles": profiles,
            "awake": store.awake(int(settings["awake_window_s"])),
            "usage": list(usage.values()),
            "errors": store.recent_errors(since_day),
            "today": {"calls": store.calls_since(gateway_module._midnight()),
                      "cost": store.spend_since(gateway_module._midnight())},
        }

    def bot(self, name=None, guid=None):
        if guid is None:
            found = self.resolve(name or "")
            if not found:
                raise ApiError("no character called %r" % name, 404)
            guid, name = found
        guid = _number(guid, "guid", 1, 2 ** 40, integer=True)
        persona = self.store.persona(guid)
        return {
            "guid": guid,
            "name": (persona or {}).get("name") or name or "",
            "persona": persona,
            "rp": self._rp_view(guid),
            "routes": self.store.routes(guid),
            "memories": self.store.memories(guid, limit=200),
            "relationships": self.store.relationships(guid),
            "muted": bool((persona or {}).get("muted")),
            "turns": self.store.turns(guid, limit=25),
            "usage": next((row for row in self.store.usage_by_bot(time.time() - 86400, limit=100000)
                           if row["bot_guid"] == guid), None),
        }

    def _rp_view(self, guid):
        character = self.store.rp_character(guid)
        if not character:
            return None
        return {"character": character, "chapters": self.store.rp_chapters(guid), "events": self.store.rp_events(guid, 12),
                "calling": rp_module.calling_label(character["race"], character["calling"])}

    def cards(self):
        """What the existing bot cards and roster need, in one small answer: who has a persona, who is awake."""
        window = int(self.store.setting("awake_window_s"))
        return {"personas": self.store.persona_cards(),
                "awake": {row["name"]: row["last_ts"] for row in self.store.awake(window) if row["name"]},
                "paused": self.store.setting("paused") == "1", "running": self.service()["running"]}

    def turns(self, bot=None, player=None, before=None, limit=50, problems=False):
        def guid(name):
            if not name:
                return None
            found = self.resolve(name)
            if not found:
                raise ApiError("no character called %r" % name, 404)
            return found[0]
        rows = self.store.turns(guid(bot), guid(player), int(before) if before else None,
                                max(1, min(int(limit), 200)), bool(problems))
        return {"turns": rows}

    def turn(self, turn_id):
        row = self.store.turn(int(turn_id))
        if not row:
            raise ApiError("no such turn", 404)
        return row

    def analytics(self, days=14):
        days = max(1, min(int(days), 60))
        midnight = gateway_module._midnight()
        since = midnight - (days - 1) * 86400
        by_day = {row["day"]: row for row in self.store.daily_usage(since)}
        daily = []
        for offset in range(days):
            day = time.strftime("%Y-%m-%d", time.localtime(since + offset * 86400 + 3600))
            row = by_day.get(day) or {}
            daily.append({"day": day, "calls": row.get("calls", 0), "errors": row.get("errors") or 0,
                          "cost_usd": row.get("cost_usd") or 0.0,
                          "tokens": (row.get("prompt_tokens") or 0) + (row.get("completion_tokens") or 0)})
        latencies = sorted(self.store.latencies(since))
        pick = lambda fraction: latencies[min(len(latencies) - 1, int(len(latencies) * fraction))] if latencies else 0  # noqa: E731
        return {"days": days, "daily": daily, "by_profile": self.store.usage_summary(since),
                "by_bot": self.store.usage_by_bot(since), "latency": {"p50": pick(0.5), "p95": pick(0.95), "n": len(latencies)},
                "total_cost": sum(day["cost_usd"] for day in daily), "total_calls": sum(day["calls"] for day in daily),
                "total_errors": sum(day["errors"] for day in daily)}

    def export(self, full=False):
        """Every persona (and with `full` every memory and relationship) as one JSON document."""
        store = self.store
        personas_out = []
        for row in store.personas(limit=100000):
            persona = store.persona(row["bot_guid"])
            personas_out.append({key: persona[key] for key in ("bot_guid", "name", "archetype", "traits", "speech_style",
                                                                "interests", "backstory", "opinions", "chattiness", "enabled")} | {"guid": persona["bot_guid"]})
        document = {"version": 1, "exported_at": time.time(), "personas": personas_out}
        if full:
            with store.conn() as db:
                document["memories"] = [dict(row) for row in db.execute("SELECT bot_guid, subject_guid, subject_name, kind, text, salience, created_at FROM memory")]
                document["relationships"] = [dict(row) for row in db.execute("SELECT * FROM relationship")]
        return document

    def personas(self, query=""):
        return {"personas": self.store.personas(query[:40])}

    def rp_characters(self, query=""):
        return {"characters": self.store.rp_characters(query[:40])}

    def rp_character(self, name=None, guid=None):
        """One roleplaying bot: its character, story, chapters and what it remembers."""
        if guid is None:
            found = self.resolve(name or "")
            if not found:
                raise ApiError("no character called %r" % name, 404)
            guid = found[0]
        guid = _number(guid, "guid", 1, 2 ** 40, integer=True)
        character = self.store.rp_character(guid)
        if not character:
            raise ApiError("this bot has no roleplay character yet: it is made the first time the game says its race and class", 404)
        return {"character": character, "chapters": self.store.rp_chapters(guid),
                "archetype": rp_module.archetype_of(character),
                "calling": rp_module.calling_label(character["race"], character["calling"]),
                "events": self.store.rp_events(guid, 20), "memories": self.store.memories(guid, limit=50), "relationships": self.store.relationships(guid)}

    # ---- writes --------------------------------------------------------------------------------------

    def apply(self, body):
        if not isinstance(body, dict):
            raise ApiError("expected a JSON object")
        handler = getattr(self, "op_" + str(body.get("op", "")).replace(".", "_"), None)
        if not handler:
            raise ApiError("unknown operation %r" % body.get("op"))
        return handler(body)

    def _guid(self, body):
        return _number(body.get("guid"), "guid", 1, 2 ** 40, integer=True)

    def _profile_name(self, value, must_exist=True):
        name = _text(value, "profile", 40, required=True)
        if not NAME.match(name):
            raise ApiError("a profile name is letters, digits, spaces and - _ . (at most 40)")
        if must_exist and not self.store.profile(name):
            raise ApiError("no profile called %r" % name, 404)
        return name

    def op_profile_save(self, body):
        name = self._profile_name(body.get("name"), must_exist=False)
        url = _text(body.get("base_url"), "base URL", 300, required=True)
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ApiError("base URL must start with http:// or https://")
        env = _text(body.get("api_key_env"), "key variable", 64)
        if env and not ENV_NAME.match(env):
            raise ApiError("the key variable is an environment variable NAME such as OPENAI_API_KEY, not the key")
        fallback = _text(body.get("fallback"), "fallback", 40)
        if fallback:
            if fallback == name:
                raise ApiError("a profile cannot be its own fallback")
            if not self.store.profile(fallback):
                raise ApiError("no profile called %r to fall back to" % fallback)
        fields = {
            "extra": self._extra(body.get("extra")),
            "base_url": url,
            "model": _text(body.get("model"), "model", 120, required=True),
            "api_key_env": env,
            "timeout_s": _number(body.get("timeout_s", 60), "timeout", 1, 600, integer=True),
            "max_tokens": _number(body.get("max_tokens", 0), "max tokens", 0, 100000, integer=True),
            "price_in": _number(body.get("price_in", 0), "input price", 0, 10000),
            "price_out": _number(body.get("price_out", 0), "output price", 0, 10000),
            "price_cached": _number(body.get("price_cached", 0), "cached input price", 0, 10000),
            "max_calls_per_min": _number(body.get("max_calls_per_min", 0), "calls per minute", 0, 100000,
                                         integer=True),
            "daily_budget_usd": _number(body.get("daily_budget_usd", 0), "daily budget", 0, 100000),
            "fallback": fallback,
            "enabled": _flag(body.get("enabled", 1)),
        }
        self.store.save_profile(name, fields)
        return {"ok": True, "name": name}

    @staticmethod
    def _extra(value):
        """Extra request parameters as a compact JSON object ('' for none). The routing fields stay ours."""
        text = _text(value, "extra parameters", 500)
        if not text:
            return ""
        try:
            data = json.loads(text)
        except ValueError:
            raise ApiError("extra parameters must be a JSON object such as {\"reasoning_effort\": \"low\"}")
        if not isinstance(data, dict):
            raise ApiError("extra parameters must be a JSON object such as {\"reasoning_effort\": \"low\"}")
        forbidden = [key for key in data if key in upstream.PROTECTED]
        if forbidden:
            raise ApiError("extra parameters may not set %s: the mind service controls those" % ", ".join(forbidden))
        return json.dumps(data, separators=(",", ":"))

    def op_profile_delete(self, body):
        name = self._profile_name(body.get("name"))
        self.store.delete_profile(name)
        return {"ok": True}

    def _service_call(self, messages, headers, timeout, max_tokens=None, user=None):
        """One chat request through the running mind service. Returns the parsed answer; raises ApiError.

        Going through the service (rather than calling a provider from here) means a test uses exactly the
        environment variables, secrets file and network that real bot conversations use.
        """
        service = self.service()
        if not service["running"]:
            raise ApiError("the mind service is not running, so nothing can be tried (start it with: "
                           "python run-mind.py)", 409)
        body = {"messages": messages}
        if max_tokens:
            body["max_tokens"] = max_tokens
        if user:
            body["user"] = user
        request = urllib.request.Request(
            "http://127.0.0.1:%d/v1/chat/completions" % service["port"], data=json.dumps(body).encode("utf-8"),
            headers=dict({"Content-Type": "application/json"}, **headers,
                         **({"Authorization": "Bearer " + self.settings["token"]} if self.settings["token"] else {})),
            method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            try:
                message = json.loads(error.read().decode("utf-8"))["error"]["message"]
            except (ValueError, KeyError, TypeError):
                message = "HTTP %d" % error.code
            raise ApiError(message, 502)
        except (urllib.error.URLError, OSError, ValueError) as error:
            raise ApiError(str(getattr(error, "reason", error)), 502)

    def op_profile_test(self, body):
        """Send a tiny request through the running service, naming the profile, and report what came back."""
        name = self._profile_name(body.get("name"))
        profile = self.store.profile(name)
        started = time.monotonic()
        try:
            answer = self._service_call([{"role": "user", "content": "Reply with the single word: OK"}],
                                        {gateway_module.PROFILE_HEADER: name, gateway_module.PLAYGROUND_HEADER: "1"},
                                        (profile["timeout_s"] or 60) + 5, max_tokens=64)
        except ApiError as error:
            if error.status == 409:
                raise
            return {"ok": False, "error": str(error)}
        reply = ((answer.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        if not reply.strip():
            return {"ok": False, "error": "the model answered with nothing. A reasoning model can spend a small token "
                                          "limit thinking: raise Longest reply, or set reasoning_effort in Extra parameters"}
        return {"ok": True, "reply": reply.strip()[:80], "ms": int((time.monotonic() - started) * 1000)}

    def op_chat_try(self, body):
        """The playground: say something to a bot as a player and get its answer, without logging in to the game.

        Built like the module's own requests (same identity block), so the persona, the memories and the guard
        come out exactly as they would in game. The exchange is forgotten unless `remember` is set.
        """
        guid = self._guid(body)
        text = _text(body.get("text"), "message", 400, required=True)
        bot_name = _text(body.get("name"), "bot name", 32)
        player_name = _text(body.get("player"), "player", 12)
        player_guid = 0
        if player_name:
            found = self.resolve(player_name)
            if not found:
                raise ApiError("no character called %r to talk as" % player_name, 404)
            player_guid, player_name = found
        facts = _text(body.get("facts"), "facts", 300)
        character = self.store.rp_character(guid)
        if character:       # a roleplaying bot is tried out as the module would present it: with its race, class and where it is
            facts += ("\n" if facts else "") + "roleplay_context=" + json.dumps({
                "race": character["race"], "class": character["klass"], "gender": character["gender"],
                "level": character["level"] or 1, "zone": character["zone"]})
        system = ("You are a World of Warcraft player character controlled by a bot, talking in game chat.\n"
                  "ACTIVE WoW SESSION - your bot's identity is:\n"
                  "- botGuid = %d%s  (you, the bot character)\n" % (guid, ", name = %s" % bot_name if bot_name else "")
                  + ("- playerGuid = %d, name = %s  (the player talking to you)\n" % (player_guid, player_name)
                     if player_guid else "") + (facts + "\n" if facts else ""))
        messages = [{"role": "system", "content": system}]
        for line in (body.get("history") or [])[-10:]:
            if isinstance(line, dict) and line.get("role") in ("user", "assistant"):
                messages.append({"role": line["role"], "content": _text(line.get("content"), "history", 600)})
        messages.append({"role": "user", "content": text})
        headers = {gateway_module.PLAYGROUND_HEADER: "1", gateway_module.DEBUG_HEADER: "1"}
        if _flag(body.get("remember")):
            headers[gateway_module.REMEMBER_HEADER] = "1"
        profile = _text(body.get("profile"), "profile", 40)
        if profile:
            headers[gateway_module.PROFILE_HEADER] = self._profile_name(profile)
        answer = self._service_call(messages, headers, 120, user="wow-bot-%d" % guid)
        message = (answer.get("choices") or [{}])[0].get("message") or {}
        return {"ok": True, "reply": message.get("content") or "", "mind": answer.get("mind") or {}}

    def op_persona_write(self, body):
        """Ask a model to invent a persona for this bot from what the dashboard knows about it. Not saved."""
        facts = body.get("facts") if isinstance(body.get("facts"), dict) else {}
        described = ", ".join("%s: %s" % (key, _text(facts.get(key), key, 60))
                              for key in ("name", "race", "class", "spec", "level", "faction", "zone") if facts.get(key))
        hint = _text(body.get("hint"), "hint", 200)
        messages = [
            {"role": "system", "content": (
                "You write chat personalities for characters in a busy online game, played by computer-controlled "
                "players. They must read like the real people in a realm's chat, not like heroes of legend: a mix of "
                "trolls, banter merchants, salty veterans, try-hards, helpful souls, memers, newbies and quiet grinders, "
                "each with opinions and running jokes. Reply with JSON only, keys: archetype (2 to 4 words), traits "
                "(three adjectives, comma separated), speech_style (how they type in chat: case, slang, quirks, under "
                "20 words), interests (two things they enjoy, comma separated), opinions (two strong, specific hot takes "
                "or running jokes about the game, classes, dungeons or other players, separated by semicolons), backstory "
                "(one or two sentences grounded in the race, class and place given), chattiness (a number from 0, says "
                "almost nothing, to 100, never stops). Trolling must stay good-natured: no slurs, no hate, nothing sexual, "
                "no real-world politics, nothing from the real world. No destiny, no quest-giver tone.")},
            {"role": "user", "content": "Character: %s.%s" % (described or "unknown", " Guidance: " + hint if hint else "")}]
        headers = {gateway_module.PLAYGROUND_HEADER: "1"}
        profile = _text(body.get("profile"), "profile", 40)
        lane_profile = profile or self.store.lanes().get("smart")
        if not lane_profile:
            raise ApiError("no model is assigned to the Conversation lane yet")
        headers[gateway_module.PROFILE_HEADER] = self._profile_name(lane_profile)
        answer = self._service_call(messages, headers, 120)
        text = ((answer.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        start, end = text.find("{"), text.rfind("}")
        try:
            data = json.loads(text[start:end + 1]) if start >= 0 else None
        except ValueError:
            data = None
        if not isinstance(data, dict):
            raise ApiError("the model did not answer with a persona; try again")
        limits = {"archetype": 80, "traits": 200, "speech_style": 200, "interests": 200, "backstory": 1500, "opinions": 300}
        def plain(value):
            # Models sometimes return traits as a list.
            if isinstance(value, (list, tuple)):
                return ", ".join(str(item) for item in value)
            return "" if isinstance(value, dict) or value is None else str(value)
        persona = {key: memory_module.clip(plain(data.get(key)), limit) for key, limit in limits.items()}
        try:
            persona["chattiness"] = max(0, min(100, int(float(data.get("chattiness")))))
        except (TypeError, ValueError):
            persona["chattiness"] = 50
        return {"ok": True, "persona": persona}

    def op_lane_set(self, body):
        lane = body.get("lane")
        if lane not in LANES:
            raise ApiError("lane must be one of %s" % ", ".join(LANES))
        name = _text(body.get("profile"), "profile", 40)
        if name:
            self._profile_name(name)
        self.store.set_lane(lane, name)
        return {"ok": True}

    def op_route_set(self, body):
        lane = body.get("lane")
        if lane not in LANES:
            raise ApiError("lane must be one of %s" % ", ".join(LANES))
        name = _text(body.get("profile"), "profile", 40)
        if name:
            self._profile_name(name)
        self.store.set_route(self._guid(body), lane, name)
        return {"ok": True}

    def op_persona_save(self, body):
        guid = self._guid(body)
        fields = {
            "name": _text(body.get("name"), "name", 32),
            "archetype": _text(body.get("archetype"), "type", 80),
            "traits": _text(body.get("traits"), "personality", 200),
            "speech_style": _text(body.get("speech_style"), "how they talk", 200),
            "interests": _text(body.get("interests"), "interests", 200),
            "backstory": _text(body.get("backstory"), "story", 1500),
            "opinions": _text(body.get("opinions"), "opinions", 300),
            "chattiness": int(_number(body.get("chattiness", 50), "chattiness", 0, 100)),
            "enabled": _flag(body.get("enabled", 1)),
        }
        self.store.save_persona(guid, fields, "manual")
        return {"ok": True, "persona": self.store.persona(guid)}

    def op_persona_roll(self, body):
        """A new random persona for this bot, in place of the current one."""
        guid = self._guid(body)
        current = self.store.persona(guid) or {}
        kind = self._archetype(body)
        fields = personas.generate(guid, current.get("name", ""), salt=int(time.time()), mix=self._mix(), archetype=kind)
        fields["backstory"] = current.get("backstory", "")
        self.store.save_persona(guid, fields, "manual")
        return {"ok": True, "persona": self.store.persona(guid)}

    def _archetype(self, body):
        """The kind of person the caller asked for ('' or missing: any, by the mix)."""
        kind = _text(body.get("archetype"), "type", 40).lower()
        if kind and kind not in personas.ARCHETYPES:
            raise ApiError("%r is not a kind of person; the kinds are: %s" % (kind, ", ".join(sorted(personas.ARCHETYPES))))
        return kind or None

    def _mix(self):
        try:
            return personas.parse_mix(self.store.setting("personality_mix"))
        except ValueError:
            return personas.default_mix()

    def op_persona_assign(self, body):
        """Give the named bots a personality: of one kind if `archetype` is given, else drawn from the mix. Marked as
        written by a person, so it is never regenerated. Names are separated by commas or new lines."""
        names = [name.strip() for name in re.split(r"[,\n]", str(body.get("names") or "")) if name.strip()]
        if not names or len(names) > 100:
            raise ApiError("give between 1 and 100 bot names, separated by commas")
        kind = self._archetype(body)
        assigned, unknown = [], []
        for name in names:
            found = self.resolve(name)
            if not found:
                unknown.append(name)
                continue
            guid, full = found
            current = self.store.persona(guid) or {}
            fields = personas.generate(guid, full, salt=int(time.time() * 1000) % 1000003, mix=self._mix(), archetype=kind)
            fields["backstory"] = current.get("backstory", "")
            self.store.save_persona(guid, fields, "manual")
            assigned.append({"name": full, "archetype": fields["archetype"]})
        return {"ok": True, "assigned": assigned, "unknown": unknown}

    def op_bot_mute(self, body):
        """A muted bot gets no model calls at all: it stays an ordinary playerbot."""
        self.store.set_muted(self._guid(body), _flag(body.get("muted")), _text(body.get("name"), "name", 32))
        return {"ok": True}

    def op_persona_import(self, body):
        """Load personas (and, from a full export, memories and relationships) from a file made by export()."""
        entries = body.get("personas")
        if not isinstance(entries, list) or len(entries) > 5000:
            raise ApiError("expected a list of at most 5000 personas")
        overwrite = _flag(body.get("overwrite"))
        added = skipped = unknown = 0
        by_name = {}
        for entry in entries:
            if not isinstance(entry, dict):
                skipped += 1
                continue
            guid = entry.get("guid")
            if not isinstance(guid, int) or guid <= 0:
                found = self.resolve(str(entry.get("name", "")))
                if not found:
                    unknown += 1
                    continue
                guid = found[0]
            by_name[guid] = str(entry.get("name", ""))
            if self.store.persona(guid) and not overwrite:
                skipped += 1
                continue
            fields = {"name": _text(entry.get("name"), "name", 32), "archetype": _text(entry.get("archetype"), "type", 80),
                      "traits": _text(entry.get("traits"), "personality", 200),
                      "speech_style": _text(entry.get("speech_style"), "how they talk", 200),
                      "interests": _text(entry.get("interests"), "interests", 200),
                      "backstory": _text(entry.get("backstory"), "story", 1500),
                      "opinions": _text(entry.get("opinions"), "opinions", 300),
                      "chattiness": int(_number(entry.get("chattiness", 50), "chattiness", 0, 100)),
                      "enabled": _flag(entry.get("enabled", 1))}
            self.store.save_persona(guid, fields, "manual")
            added += 1
        restored = 0
        for memory in body.get("memories") or []:
            if isinstance(memory, dict) and isinstance(memory.get("bot_guid"), int) and memory.get("kind") in ("event", "fact", "summary"):
                text = _text(memory.get("text"), "memory", 400)
                if text and not any(m["text"] == text for m in
                                    self.store.memories(memory["bot_guid"], memory.get("subject_guid"), limit=500)):
                    self.store.add_memory(memory["bot_guid"], memory.get("subject_guid"),
                                          _text(memory.get("subject_name"), "name", 32), memory["kind"], text,
                                          _number(memory.get("salience", 0.5), "importance", 0.1, 1.0))
                    restored += 1
        return {"ok": True, "added": added, "skipped": skipped, "unknown": unknown, "memories": restored}

    def op_bank_stats(self, body):
        """What the line bank holds, the writing job's progress and whether Jev can be used."""
        stats = bank_module.Bank(self.store).stats()
        service = self.service()
        if service["running"]:
            try:
                stats["job"] = self._bank_call({"op": "status"}).get("job", stats["job"])
            except ApiError:
                pass
        stats["jev"] = service.get("jev") or {}
        stats["picker"] = self.store.setting("bank_picker")
        return {"ok": True, "bank": stats}

    def op_bank_generate(self, body):
        """Start writing lines (in the service, which holds the model keys). Lines already there are kept."""
        request = {"op": "generate", "per_cell": _number(body.get("per_cell", 30), "per_cell", 5, 60, integer=True)}
        if body.get("mode") not in (None, "", "players", "roleplay"):
            raise ApiError("mode must be players or roleplay")
        if body.get("mode") == "roleplay":
            request["mode"] = "roleplay"
        if body.get("profile"):
            request["profile"] = self._profile_name(body["profile"])
        for field in ("archetypes", "situations"):
            if body.get(field):
                if not isinstance(body[field], list) or len(body[field]) > 100:
                    raise ApiError("%s must be a list" % field)
                request[field] = [_text(item, field, 60) for item in body[field]]
        answer = self._bank_call(request)
        if not answer.get("ok"):
            raise ApiError(answer.get("error") or "the mind service refused")
        return {"ok": True, "job": answer["job"]}

    RP_EDITABLE = {"traits": 160, "speech": 400, "convictions": 300, "goal": 200, "quirk": 120, "fear": 80, "keepsake": 120,
                   "facts": 1500, "story": 1200}

    def op_rp_save(self, body):
        """Rewrite parts of a roleplaying bot's character. An edited character is marked manual and is never rewritten behind your back."""
        guid = self._guid(body)
        if not self.store.rp_character(guid):
            raise ApiError("no roleplay character for this bot", 404)
        changed = 0
        for field, limit in self.RP_EDITABLE.items():
            if field in body:
                self.store.set_rp_field(guid, field, _text(body[field], field, limit))
                changed += 1
        if not changed:
            raise ApiError("nothing to change")
        self.store.mark_rp_manual(guid)
        return {"ok": True, "character": self.store.rp_character(guid)}

    def op_rp_chapter_save(self, body):
        guid = self._guid(body)
        if not self.store.rp_character(guid):
            raise ApiError("no roleplay character for this bot", 404)
        bracket = _number(body.get("bracket"), "bracket", 0, len(rp_module.lore.LEVEL_BRACKETS) - 1, integer=True)
        text = _text(body.get("text"), "chapter", 500, required=True)
        self.store.save_rp_chapter(guid, bracket, rp_module.lore.LEVEL_BRACKETS[bracket][0], text, "manual")
        return {"ok": True}

    def op_rp_reset_story(self, body):
        """Throw away a bot's written story and chapters; they are written again from its facts the next time it speaks."""
        self.store.reset_rp_story(self._guid(body))
        return {"ok": True}

    def op_rp_reset_all(self, body):
        """The same for every generated character (not the ones you edited)."""
        return {"ok": True, "cleared": self.store.reset_all_rp_stories()}

    def op_rp_delete(self, body):
        """Forget a character entirely. It is made again from the same seed, so this is for after a change to the lore tables."""
        self.store.delete_rp_character(self._guid(body))
        return {"ok": True}

    def op_bank_samples(self, body):
        kind, situation = _text(body.get("archetype"), "archetype", 40, True), _text(body.get("situation"), "situation", 40, True)
        return {"ok": True, "lines": bank_module.Bank(self.store).samples(kind, situation, 12)}

    def op_bank_clear(self, body):
        bank_module.Bank(self.store).clear()
        return {"ok": True}

    def op_cast_status(self, body):
        """The realm's regulars: who they are, how they know each other, and whether their sheets are still being written."""
        return self._bank_call({"op": "status"}, "/cast")

    def _bank_call(self, body, route="/bank"):
        service = self.service()
        if not service["running"]:
            raise ApiError("the mind service is not running (start it with: python run-mind.py)", 409)
        request = urllib.request.Request(
            "http://127.0.0.1:%d%s" % (service["port"], route), data=json.dumps(body).encode("utf-8"),
            headers=dict({"Content-Type": "application/json"},
                         **({"Authorization": "Bearer " + self.settings["token"]} if self.settings["token"] else {})),
            method="POST")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as error:
            raise ApiError(str(getattr(error, "reason", error)), 502)

    def op_persona_reroll_all(self, body):
        """Throw away every generated personality (not the ones a person wrote or edited, not mutes): each is made again,
        from the current archetypes, the next time its bot speaks."""
        with self.store.conn() as db:
            cursor = db.execute("DELETE FROM persona WHERE source = 'generated' AND muted = 0")
            count = cursor.rowcount
        return {"ok": True, "cleared": count}

    def op_persona_delete(self, body):
        self.store.delete_persona(self._guid(body))
        return {"ok": True}

    def op_memory_delete(self, body):
        self.store.delete_memory(_number(body.get("id"), "id", 1, 2 ** 40, integer=True), self._guid(body))
        return {"ok": True}

    def op_memory_clear(self, body):
        subject = body.get("subject_guid")
        self.store.clear_memories(self._guid(body),
                                  _number(subject, "subject", 1, 2 ** 40, integer=True) if subject else None)
        return {"ok": True}

    def op_memory_add(self, body):
        """Tell a bot something to remember about someone: a fact it will bring up when it fits."""
        guid = self._guid(body)
        found = self.resolve(_text(body.get("subject_name"), "player", 12, required=True))
        if not found:
            raise ApiError("no character called %r" % body.get("subject_name"), 404)
        text = _text(body.get("text"), "memory", 200, required=True)
        salience = _number(body.get("salience", 0.8), "importance", 0.1, 1.0)
        self.store.add_memory(guid, found[0], found[1], "fact", text, salience)
        self.store.note_seen(guid, found[0], found[1])
        return {"ok": True}

    SETTING_KINDS = {"auto_persona": "flag", "plain_chat_no_tools": "flag", "guard": "flag", "log_turns": "flag", "paused": "flag",
                     "style_rules": ("text", 600), "blocked_words": ("text", 300), "personality_mix": ("text", 600),
                     "ambient_vibe": ("text", 900), "chat_mode": ("choice", rp_module.MODES), "rp_channels": ("text", 80),
                     "rp_rules": ("text", 2400), "rp_bank_share_player": ("int", 0, 100), "rp_start_llm": ("int", 0, 100),
                     "rp_ai_story": "flag",
                     "daily_cap_usd": ("number", 0, 100000), "max_reply_chars": ("int", 40, 255),
                     "max_tool_rounds": ("int", 1, 200), "bank_share_player": ("int", 0, 100),
                     "bank_share_bots": ("int", 0, 100), "bank_join_min": ("int", 0, 100), "bank_llm_depth": ("int", 0, 10),
                     "bank_picker": ("choice", ("local", "jev"))}

    def op_setting_set(self, body):
        key = body.get("key")
        if key not in store_module.SETTING_DEFAULTS:
            raise ApiError("unknown setting %r" % key)
        kind = self.SETTING_KINDS.get(key, ("int", 0, 100000))
        if kind == "flag":
            value = str(_flag(body.get("value")))
        elif kind[0] == "choice":
            value = str(body.get("value"))
            if value not in kind[1]:
                raise ApiError("%s must be one of: %s" % (key, ", ".join(kind[1])))
        elif kind[0] == "text":
            value = _text(body.get("value"), key, kind[1])
        elif kind[0] == "number":
            value = str(_number(body.get("value"), key, kind[1], kind[2]))
        else:
            value = str(_number(body.get("value"), key, kind[1], kind[2], integer=True))
        if key == "personality_mix":
            try:
                personas.parse_mix(value)
            except ValueError as error:
                raise ApiError(str(error))
        if key == "rp_channels":
            kinds = rp_module.parse_channels(value)
            if kinds is None:
                raise ApiError("rp_channels is a comma list of: %s" % ", ".join(rp_module.CHANNEL_KINDS))
            value = ",".join(kinds)
        self.store.set_setting(key, value)
        return {"ok": True}
