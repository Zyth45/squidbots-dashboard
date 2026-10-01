"""The gateway: takes the module's chat request, gives the bot its mind, and forwards it to an LLM.

`Gateway.handle` is a plain function from (lane, request body, headers) to (HTTP status, JSON answer), so
everything here is testable without a socket.

Lanes:
    smart   a player is talking to the bot. Persona and memory are added; the exchange is remembered.
    fast    the cheap, frequent calls (tactical ticks, intent classifier). Routed and budgeted, and given the
            bot's voice when it has one, but nothing is remembered.
    memory  reflection calls made by this service itself.
    ambient bots answering a hello in /say or a public channel, and each other (see ambient.py). Uses the fast lane's
            model until it is given one of its own.
"""
import copy
import json
import os
import threading
import time

from . import ambient, bank, community, filters, identity, memory, personas, prompt, rp as rp_module, upstream

LANES = ("smart", "fast", "memory", "ambient")
PROFILE_HEADER = "x-mind-profile"        # use this profile instead of the lane's (the dashboard's Test button)
PLAYGROUND_HEADER = "x-mind-playground"  # "1": a try-out from the dashboard: allowed while paused, not remembered
REMEMBER_HEADER = "x-mind-remember"      # "1" with the playground: remember the exchange after all
DEBUG_HEADER = "x-mind-debug"            # "1": the answer carries a "mind" object describing what was added
PROMPT_KEPT = 6000                       # characters of the system prompt kept in the conversation log
ACTIONS_KEPT = 8                         # game actions remembered per bot and player
ACTIONS_TTL = 30 * 60                    # seconds a bot remembers having done them


def error_answer(message, kind="mind_error"):
    return {"error": {"message": message, "type": kind}}


class Limited(Exception):
    """A profile is over its calls-per-minute or its daily budget."""


class Gateway:
    def __init__(self, store, secrets_file=""):
        self.store = store
        self.secrets_file = secrets_file
        self._secrets_cache = (None, {})
        self.reflector = memory.Reflector(store, self._reflect_call)
        self.bank = bank.Bank(store)
        self.ambient = ambient.Ambient(self)
        self.community = community.Community(self)
        self.rp = rp_module.Rp(store, self._story_writer)
        self.actions = {}      # (bot, player) -> the last things the bot did with its tools, so a follow-up can use them
        self.lock = threading.Lock()
        self.inflight = 0
        # Conversation requests that named a bot but no player: nothing can be remembered for those. Automatic
        # ticks are always like that; a player talking to a bot never should be, so the dashboard shows the count.
        self.no_player = 0
        # A debugging aid: MIND_CAPTURE=<file> appends every request that leaves for a model (after the personality is
        # added) as a JSON line, so real traffic can be replayed against another model. Off unless the variable is set.
        self.capture_path = os.environ.get("MIND_CAPTURE", "")
        self._capture_lock = threading.Lock()

    # ---- secrets -------------------------------------------------------------------------------------

    def secrets(self):
        """The secrets file, re-read only when it changes."""
        path = self.secrets_file
        try:
            stamp = os.path.getmtime(path) if path else None
        except OSError:
            stamp = None
        if stamp != self._secrets_cache[0]:
            data = {}
            if stamp is not None:
                try:
                    with open(path, encoding="utf-8-sig") as handle:
                        loaded = json.load(handle)
                    data = loaded if isinstance(loaded, dict) else {}
                except (OSError, ValueError) as error:
                    print("Could not read %s: %s" % (path, error), flush=True)
            self._secrets_cache = (stamp, data)
        return self._secrets_cache[1]

    def key_states(self):
        """{profile: 'env' | 'file' | 'missing' | 'none'}: where each profile's key comes from, never the key."""
        secrets = self.secrets()
        states = {}
        for profile in self.store.profiles():
            env = profile["api_key_env"]
            if env and os.environ.get(env):
                states[profile["name"]] = "env"
            elif secrets.get(profile["name"]):
                states[profile["name"]] = "file"
            else:
                states[profile["name"]] = "missing" if env else "none"
        return states

    # ---- the request ---------------------------------------------------------------------------------

    def handle(self, lane, body, headers=None):
        headers = headers or {}
        if not isinstance(body, dict) or not isinstance(body.get("messages"), list):
            return 400, error_answer("expected a chat completion request with a messages list")
        playground = headers.get(PLAYGROUND_HEADER) == "1"
        ident = identity.identify(body, headers, lane)
        if not playground:
            # Refuse before anything is written: a paused service or a muted bot should not even make a persona.
            refusal = self._refuse(ident)
            if refusal:
                return refusal
        context = rp_module.context_from_text(_system_text(body)) if lane == "smart" else {}
        persona = self._persona(ident, context, lane) if ident.bot_guid else None
        if lane == "smart" and ident.bot_guid:
            self._note_actions(body, ident)
        prepared, mind_block, recalled = self._prepare(lane, body, ident, persona, context)
        if lane == "smart":
            self._limit_tool_rounds(prepared)
        if self.capture_path and not playground:
            self._capture(lane, ident, prepared)

        # The dashboard's Test button names a profile outright, so that it tries exactly what the service would.
        name = headers.get(PROFILE_HEADER) or self.store.profile_for(lane, ident.bot_guid)
        if not name:
            return 503, error_answer("no LLM profile is assigned to the %s lane; set one on the Minds page" % lane,
                                     "not_configured")
        said = identity.last_user_text(body)
        # Only a bot's conversation is a turn. Utility calls (the Test button, the persona writer) name no bot and
        # would just be noise in the log unless they fail.
        conversation = (lane == "smart" or playground) and bool(ident.bot_guid)
        turn = {"lane": "playground" if playground else lane, "bot_guid": ident.bot_guid, "bot_name": ident.bot_name,
                "player_guid": ident.player_guid, "player_name": ident.player_name, "said": said[:1000],
                "tools_offered": _tool_names(body)[:600],
                "mind": mind_block[:3000], "system_prompt": _system_text(prepared)[:PROMPT_KEPT]}
        with self.lock:
            self.inflight += 1
        try:
            # A try-out from the dashboard is logged as its own lane: it costs money and belongs in the usage
            # figures, but it must not make the bot look awake in game.
            answer, meta = self._dispatch("playground" if playground else lane, ident.bot_guid, name, prepared, set())
        except (Limited, upstream.UpstreamError) as failure:
            limited = isinstance(failure, Limited)
            self._log_turn(turn, dict(profile=name, ok=0, error=str(failure)), force=conversation)
            if limited:
                return 429, error_answer(str(failure), "rate_limited")
            return 502, error_answer(str(failure), "upstream_error")
        finally:
            with self.lock:
                self.inflight -= 1

        message = (answer.get("choices") or [{}])[0].get("message") or {}
        # Only a bot talking is cleaned. A request that names no bot (the dashboard's persona writer, a test) wants
        # its text exactly as the model wrote it.
        if lane == "smart" and ident.bot_guid and isinstance(message.get("content"), str) \
                and not message.get("tool_calls"):
            cleaned = filters.clean(message["content"], int(self.store.setting("max_reply_chars")),
                                    filters.blocked_list(self.store.setting("blocked_words")), ident.bot_name)
            message["content"] = cleaned
        tools = ",".join((call.get("function") or {}).get("name", "") for call in message.get("tool_calls") or [])
        self._log_turn(turn, dict(meta, reply=(message.get("content") or "")[:2000], tool_calls=tools, ok=1), force=conversation)

        remember = lane == "smart" and (not playground or headers.get(REMEMBER_HEADER) == "1")
        if remember and ident.bot_guid:
            if not ident.player_guid and said:
                self.no_player += 1
            self._remember(body, ident, answer)
        if headers.get(DEBUG_HEADER) == "1":
            answer["mind"] = {"persona": bool(persona), "mind_block": mind_block, "recalled": recalled,
                              "system": _system_text(prepared), "profile": meta["profile"], "model": meta["model"],
                              "latency_ms": meta["latency_ms"], "cost_usd": meta["cost_usd"],
                              "tool_calls": tools}
        return 200, answer

    def _capture(self, lane, ident, prepared):
        try:
            line = json.dumps({"ts": time.time(), "lane": lane, "bot_guid": ident.bot_guid, "bot": ident.bot_name,
                               "player": ident.player_name, "body": prepared}, ensure_ascii=False)
            with self._capture_lock, open(self.capture_path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError as error:
            print("Could not capture a request: %s" % error, flush=True)

    def _refuse(self, ident):
        """(status, answer) when this request must not reach a model right now, else None."""
        store = self.store
        if store.setting("paused") == "1":
            return 503, error_answer("the mind service is paused from the dashboard", "paused")
        if ident.bot_guid and store.is_muted(ident.bot_guid):
            return 503, error_answer("this bot is muted from the dashboard", "muted")
        cap = float(store.setting("daily_cap_usd"))
        if cap > 0 and store.spend_since(_midnight()) >= cap:
            return 429, error_answer("the daily cap of $%.2f across all models has been reached" % cap, "daily_cap")
        return None

    def _log_turn(self, turn, outcome, force):
        """Record a conversation turn for the dashboard. Ticks of the fast lane are not turns; their errors are."""
        if self.store.setting("log_turns") != "1" or not (force or not outcome.get("ok", 1)):
            return
        try:
            self.store.log_turn(dict(turn, **outcome), int(self.store.setting("turn_log_keep")))
        except Exception as error:  # noqa: BLE001 - the log is a convenience; it must never fail a chat
            print("Could not log a turn: %s" % error, flush=True)

    # ---- the line bank -------------------------------------------------------------------------------

    def bank_command(self, body):
        """{"op": "status"} or {"op": "generate", "profile", "archetypes", "situations", "per_cell"}: the bank's job runs here,
        in the service, because this is the process that holds the provider keys."""
        op = body.get("op")
        if op == "status":
            return dict(self.bank.stats(), ok=True)
        if op != "generate":
            return {"ok": False, "error": "unknown bank op %r" % op}
        profile = str(body.get("profile") or "") or self.store.profile_for("ambient", 0) or self.store.profile_for("fast", 0)
        if not profile or not self.store.profile(profile):
            return {"ok": False, "error": "no model to write the lines: assign one to the ambient lane or pick a profile"}
        per_cell = max(5, min(int(body.get("per_cell") or 30), 60))

        def dispatch(name, request):
            answer, _ = self._dispatch("bank", 0, name, request, set())
            return ((answer.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        mode = "roleplay" if body.get("mode") == "roleplay" else "players"
        workers = max(1, min(int(body.get("workers") or 6), 16))
        job = self.bank.start_generation(dispatch, profile, body.get("archetypes"), body.get("situations"), per_cell, workers=workers,
                                         topics=body.get("topics"), mode=mode)
        return {"ok": True, "job": job}

    # ---- the mind ------------------------------------------------------------------------------------

    def chat_mode(self):
        """"roleplay" (bots are characters in the world's lore) or "players" (bots chat like players at a keyboard)."""
        mode = self.store.setting("chat_mode")
        return mode if mode in rp_module.MODES else rp_module.MODES[0]

    def roleplaying(self):
        return self.chat_mode() == "roleplay"

    def _rp_persona(self, ident, context, lane):
        """The bot as a character in the lore, or None when the game has not said what race and class it is (an older module): it then
        talks as a player until it does. A bot switched off on the dashboard stays switched off."""
        stored = self.store.persona(ident.bot_guid)
        if stored and not stored["enabled"]:
            return None
        if lane == "fast" and not self.store.rp_character(ident.bot_guid):
            return None
        return self.rp.character(ident.bot_guid, ident.bot_name, context)

    def _story_writer(self, request):
        """Ask a model for a bot's backstory or a new chapter of it. The memory lane's model when it has one, else a quicker lane's."""
        profile = next((p for p in (self.store.profile_for(lane, 0) for lane in ("memory", "ambient", "fast", "smart")) if p), None)
        if not profile or self._refuse(identity.Identity()):
            return None
        answer, _ = self._dispatch("memory", 0, profile, request, set())
        return ((answer.get("choices") or [{}])[0].get("message") or {}).get("content")

    def _persona(self, ident, context=None, lane="smart"):
        """The bot's persona, made on first sight when nobody wrote one. None when it is switched off."""
        store, guid = self.store, ident.bot_guid
        if self.roleplaying():
            character = self._rp_persona(ident, context, lane)
            if character or lane == "fast":
                return character
        persona = store.persona(guid)
        if persona and ident.bot_name and persona["name"] and not _same_name(persona["name"], ident.bot_name):
            # The guid now belongs to a different character (bots deleted and created again): the old
            # memories are someone else's. A written persona is kept, a generated one is rolled again.
            store.clear_memories(guid)
            if persona["source"] == "generated":
                store.delete_persona(guid)
                persona = None
            else:
                store.save_persona(guid, dict(persona, name=ident.bot_name), "manual")
                persona = store.persona(guid)
        if persona is None and store.setting("auto_persona") == "1":
            store.save_persona(guid, personas.generate(guid, ident.bot_name, mix=self._mix()), "generated")
            persona = store.persona(guid)
        elif persona and ident.bot_name and persona["name"] != ident.bot_name:
            # Not stored yet, or stored short (an older parse cut "Alte Bot" to "Alte"): keep the full name.
            store.save_persona(guid, dict(persona, name=ident.bot_name), persona["source"])
            persona = store.persona(guid)
        return persona if persona and persona["enabled"] else None

    def _mix(self):
        """How common each kind of generated personality is, from the dashboard's setting (the defaults when it is empty or bad)."""
        try:
            return personas.parse_mix(self.store.setting("personality_mix"))
        except ValueError:
            return personas.default_mix()

    def _limit_tool_rounds(self, body):
        """The module runs the tool loop and stops with an empty answer at its own limit, which the player sees as a bot
        that ignored them. Past our limit the model is given no tools, so its next message is words, never another call."""
        try:
            limit = int(self.store.setting("max_tool_rounds"))
        except (TypeError, ValueError):
            return
        messages = body.get("messages") or []
        last_user = max((i for i, m in enumerate(messages) if isinstance(m, dict) and m.get("role") == "user"), default=-1)
        rounds = sum(1 for m in messages[last_user + 1:] if isinstance(m, dict) and m.get("role") == "assistant" and m.get("tool_calls"))
        if limit > 0 and rounds >= limit:
            body.pop("tools", None)
            body.pop("tool_choice", None)

    def _prepare(self, lane, body, ident, persona, context=None):
        """(a copy of the request with the mind added, the text that was added, memories recalled)."""
        prepared = copy.deepcopy(body)
        if not persona or lane == "memory":
            return prepared, "", 0
        if lane == "fast":
            line = rp_module.voice_line(persona["row"]) if persona.get("rp") else prompt.voice_line(persona)
            return (_add_to_system(prepared, "", line) if line else prepared), line, 0
        guard = prompt.GUARD if self.store.setting("guard") == "1" else ""
        if persona.get("rp"):
            parts = [self.rp.block(persona, context or {}, self.store.setting("rp_rules"), guard, True, False, prompt.TYPING_RULE,
                                   prompt.ACTION_RULE, int(self.store.setting("max_reply_chars")))]
        else:
            parts = [prompt.persona_block(persona, self.store.setting("style_rules"), guard)]
        said = identity.last_user_text(body)
        recalled = memory.recall(self.store, ident.bot_guid, ident.player_guid, said)
        relation = self.store.relationship(ident.bot_guid, ident.player_guid) if ident.player_guid else None
        block = prompt.memory_block(ident.player_name, recalled, relation)
        if block:
            parts.append(block)
        done = prompt.actions_block(self._recent_actions(ident))
        if done:
            parts.append(done)
        text = "\n\n".join(parts)
        return _add_to_system(prepared, text, ""), text, len(recalled)

    # ---- what the bot just did -----------------------------------------------------------------------

    def _note_actions(self, body, ident):
        """Keep the game actions this bot took with its tools (with their results) for the next few minutes.

        The module runs the tool loop itself and sends only text back to the player, so a follow-up such as "I don't see
        the sword" reaches the model with no memory of which item it had just put in the trade. The tool rounds of the
        current request are in `messages`: read the finished ones here.
        """
        if not ident.player_guid:
            return
        calls = {}
        for message in body.get("messages") or []:
            if not isinstance(message, dict):
                continue
            if message.get("role") == "assistant":
                for call in message.get("tool_calls") or []:
                    if isinstance(call, dict) and call.get("id"):
                        calls[call["id"]] = call.get("function") or {}
            elif message.get("role") == "tool" and message.get("tool_call_id") in calls:
                line = _action_line(calls[message["tool_call_id"]], identity._text(message.get("content")))
                if line:
                    self._remember_action(ident, message["tool_call_id"], line)

    def _remember_action(self, ident, call_id, line):
        key = (ident.bot_guid, ident.player_guid)
        with self.lock:
            done = self.actions.setdefault(key, [])
            if any(entry[2] == call_id for entry in done):
                return
            done.append((time.time(), line, call_id))
            del done[:-ACTIONS_KEPT]
            if len(self.actions) > 500:   # drop the oldest pairs; this is a convenience, not a record
                for stale in sorted(self.actions, key=lambda k: self.actions[k][-1][0])[:100]:
                    del self.actions[stale]

    def _recent_actions(self, ident):
        with self.lock:
            done = self.actions.get((ident.bot_guid, ident.player_guid), [])
            return [(at, line) for at, line, _ in done if time.time() - at < ACTIONS_TTL]

    def _remember(self, body, ident, answer):
        message = (answer.get("choices") or [{}])[0].get("message") or {}
        reply = message.get("content")
        if message.get("tool_calls") or not isinstance(reply, str) or not reply.strip():
            return  # a tool round, not yet an answer
        if not ident.player_guid:
            return  # a synthetic tick with no player: nobody to remember
        said = identity.last_user_text(body)
        if memory.record_exchange(self.store, ident.bot_guid, ident.player_guid, ident.player_name, said, reply):
            self.reflector.note(ident.bot_guid, ident.bot_name, ident.player_guid, ident.player_name)

    def _reflect_call(self, system, user):
        name = self.store.lanes().get("memory")
        if not name or self._refuse(identity.Identity()):
            return None
        body = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": 0.2}
        answer, _ = self._dispatch("memory", 0, name, body, set())
        return ((answer.get("choices") or [{}])[0].get("message") or {}).get("content")

    # ---- the provider --------------------------------------------------------------------------------

    def _dispatch(self, lane, bot_guid, name, body, tried):
        """Call `name`; when it is limited or fails, its fallback (once each, so a loop cannot form)."""
        tried.add(name)
        profile = self.store.profile(name)
        if not profile or not profile["enabled"]:
            raise upstream.UpstreamError("profile %r is missing or switched off" % name)
        try:
            self._check_limits(profile)
            key = upstream.api_key(name, profile["api_key_env"], self.secrets())
            try:
                answer, latency = upstream.complete(profile, body, key)
            except upstream.UpstreamError as error:
                self.store.log_call(lane, bot_guid, name, profile["model"], 0, 0, 0, 0, False, str(error))
                raise
        except (Limited, upstream.UpstreamError) as failure:
            fallback = profile["fallback"]
            if fallback and fallback not in tried:
                return self._dispatch(lane, bot_guid, fallback, body, tried)
            raise failure
        usage = answer.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        # Providers that cache the start of a prompt (OpenAI does, for prompts over 1,024 tokens) bill the cached part at
        # a fraction. A profile with no cached price bills those tokens as ordinary input.
        cached = min(prompt_tokens, int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0))
        cached_price = profile["price_cached"] or profile["price_in"]
        cost = ((prompt_tokens - cached) * profile["price_in"] + cached * cached_price
                + completion_tokens * profile["price_out"]) / 1e6
        self.store.log_call(lane, bot_guid, name, profile["model"], prompt_tokens, completion_tokens, cost,
                            latency, True, cached_tokens=cached)
        return answer, {"profile": name, "model": profile["model"], "latency_ms": latency,
                        "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                        "cached_tokens": cached, "cost_usd": cost}

    def _check_limits(self, profile):
        name = profile["name"]
        if profile["max_calls_per_min"] and \
                self.store.calls_since(time.time() - 60, name) >= profile["max_calls_per_min"]:
            raise Limited("%s is at its limit of %d calls a minute" % (name, profile["max_calls_per_min"]))
        if profile["daily_budget_usd"] and \
                self.store.spend_since(_midnight(), name) >= profile["daily_budget_usd"]:
            raise Limited("%s has spent its $%.2f budget for today" % (name, profile["daily_budget_usd"]))


def _action_line(function, result):
    """'economy.bot_trade_give(item_id=1, ...) -> {"ok":true,...}' for a finished game action, else ''.

    Looking things up and asking how a tool works are not worth remembering; doing them, and being refused, are.
    """
    name = str(function.get("name") or "")
    try:
        args = json.loads(function.get("arguments") or "{}")
    except ValueError:
        return ""
    if not isinstance(args, dict) or args.get("describe"):
        return ""
    action = str(args.get("action") or name)
    if action.split("_")[0] in ("get", "list", "find", "read", "search", "check", "describe") or action.startswith("bot_get"):
        return ""
    params = args.get("params") if isinstance(args.get("params"), dict) else {k: v for k, v in args.items() if k != "action"}
    shown = ", ".join("%s=%s" % (key, json.dumps(value, ensure_ascii=False)) for key, value in params.items()
                      if key not in ("botGuid", "playerGuid"))
    result = " ".join(result.split())
    if not result:
        return ""
    return "%s(%s) -> %s" % (action, shown[:140], result[:260])


def _same_name(stored, seen):
    """Same character: equal ignoring case, or one is the other's first word(s) (a name once stored cut short)."""
    a, b = stored.lower().split(), seen.lower().split()
    n = min(len(a), len(b))
    return n > 0 and a[:n] == b[:n]


def _tool_names(body):
    """The tools the caller offered the model, as a comma list: the first thing to look at when a bot 'did not do it'."""
    names = []
    for tool in body.get("tools") or []:
        function = tool.get("function") if isinstance(tool, dict) else None
        if isinstance(function, dict) and function.get("name"):
            names.append(str(function["name"]))
    return ",".join(names)


def _system_text(body):
    """The first system message as the model sees it."""
    for message in body.get("messages") or []:
        if isinstance(message, dict) and message.get("role") == "system" and isinstance(message.get("content"), str):
            return message["content"]
    return ""


def _midnight():
    now = time.localtime()
    return time.mktime((now.tm_year, now.tm_mon, now.tm_mday, 0, 0, 0, 0, 0, -1))


def _add_to_system(body, before, after):
    """Put text before and/or after the first system message (or make one if the request has none)."""
    messages = body["messages"]
    for message in messages:
        if isinstance(message, dict) and message.get("role") == "system" and isinstance(message.get("content"), str):
            message["content"] = "\n\n".join(part for part in (before, message["content"], after) if part)
            return body
    messages.insert(0, {"role": "system", "content": "\n\n".join(part for part in (before, after) if part)})
    return body
