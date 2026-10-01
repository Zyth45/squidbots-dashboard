#!/usr/bin/env python3
"""Which model should write roleplay lines? Replay a fixed set of in-character situations against candidate OpenAI models and score them.

    OPENAI_API_KEY=... python3 tests/bench_roleplay.py [--models gpt-6-luna,gpt-4o-mini] [--reps 2] [--judge gpt-6-luna]

Each situation is a character (race, calling, class, zone, errands, events), a scene (/say, guild) and what was just said. The prompt is exactly
what the ambient lane sends (`Ambient._rp_system`). A judge model scores every answer against a rubric (in character, lore, brevity, no player talk,
engagement), and the run prints latency, cost and the average score per model. It is a bench, not a test: it costs a few cents and needs a key.
"""
import argparse
import concurrent.futures
import json
import os
import re
import statistics
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mind import gateway as gateway_module, identity, rp, rp_bank, store as store_module, upstream  # noqa: E402

BASE = "https://api.openai.com/v1"
# USD per million tokens (input, output).
PRICES = {"gpt-5-nano": (0.05, 0.40, True), "gpt-4.1-nano": (0.10, 0.40, False), "gpt-6-luna": (0.10, 0.50, True), "gpt-4o-mini": (0.15, 0.60, False),
          "gpt-4.1-mini": (0.40, 1.60, False), "gpt-5.4-nano": (0.20, 1.25, True), "gpt-5-mini": (0.25, 2.00, True)}

CHARACTERS = [
    ("Night Elf", "Hunter", "female", 34, "Ashenvale", "Astranaar", ["The Zoram Strand Report"], [{"k": "death", "t": "was struck down by a satyr and raised again", "ago": 900}]),
    ("Orc", "Barbarian", "male", 22, "The Barrens", "The Crossroads", ["Raptor Thieving"], []),
    ("Dwarf", "Runemaster", "female", 48, "Tanaris", "Gadgetzan", [], [{"k": "levelup", "t": "came into a new stretch of life", "ago": 300}]),
    ("Undead", "Necromancer", "male", 12, "Tirisfal Glades", "Brill", ["Graverobbers"], []),
    ("Human", "Templar", "female", 62, "Hellfire Peninsula", "Honor Hold", ["Fel Orc Scouts"], []),
    ("Troll", "Witch Doctor", "male", 18, "Durotar", "Sen'jin Village", ["Hidden Enemies"], []),
]
LINES = [
    ("say", "Well met, friend. A fine evening."), ("say", "What brings you out this far?"), ("say", "Are you an AI?"), ("say", "What level are you?"),
    ("guild", "Does anyone know a safe road to the coast?"), ("say", "You look like you have seen better days."), ("say", "Tell me about your homeland."),
    ("say", "I think the Horde and Alliance should make peace."),
]
RUBRIC = ("You judge one line spoken by a character in a Warcraft roleplay (the age of the Lich King), answering what was just said. Score each from the "
          "given scale and answer with JSON only: {\"in_character\": 0-2 (a person of that race and calling, not a game bot), \"lore\": 0-2 (no wrong or "
          "anachronistic lore, no invented famous names), \"brief\": 0-1 (one to two short sentences), \"no_player_talk\": 0-1 (no levels, servers, "
          "bots, AI, game words), \"engaging\": 0-2 (answers what was said and gives the other person something to answer)}.")


def key():
    if os.environ.get("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"]
    for line in open(os.path.expanduser("~/dev/devhub-private/dashboard/.env.local"), encoding="utf-8"):
        if line.startswith("AI_API_KEY="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("no OPENAI_API_KEY")


def profile(model, effort):
    return {"name": model, "base_url": BASE, "model": model, "max_tokens": 160, "timeout_s": 60,
            "extra": json.dumps({"reasoning_effort": effort}) if effort else ""}


def effort_for(model, secret):
    if not PRICES[model][2]:
        return None
    for effort in ("none", "minimal", "low"):
        try:
            upstream.complete(profile(model, effort), {"messages": [{"role": "user", "content": "Say ok."}]}, secret)
            return effort
        except upstream.UpstreamError:
            continue
    return "low"


def scenarios():
    directory = tempfile.mkdtemp()
    gateway = gateway_module.Gateway(store_module.Store(os.path.join(directory, "mind.sqlite")), os.path.join(directory, "secrets.json"))
    out = []
    for number, (race, klass, gender, level, zone, area, quests, events) in enumerate(CHARACTERS):
        ctx = rp.clean_context({"race": race, "class": klass, "gender": gender, "level": level, "zone": zone, "area": area, "quests": quests,
                                "events": events, "doing": "walking the road", "time": "dusk"})
        character = gateway.rp.character(1000 + number, "Test%d" % number, ctx)
        for channel, line in LINES:
            body = {"channel": channel, "zone": zone, "area": area}
            system = gateway.ambient._rp_system(character, body, identity.Identity(1000 + number, "Test%d" % number, 7, "Ann"), line, False, False, (), "", None, "Ann", ctx)
            out.append({"who": "%s %s" % (race, klass), "line": line, "channel": channel,
                        "messages": [{"role": "system", "content": system}, {"role": "user", "content": "[Ann] %s\nWrite Test%d's line now." % (line, number)}]})
    return out


def one(model, effort, secret, scenario):
    try:
        answer, latency = upstream.complete(profile(model, effort), {"messages": scenario["messages"], "temperature": 0.9}, secret)
    except upstream.UpstreamError as error:
        return {"error": str(error)}
    message = (answer.get("choices") or [{}])[0].get("message") or {}
    usage = answer.get("usage") or {}
    price = PRICES[model]
    return {"text": (message.get("content") or "").strip(), "ms": latency,
            "cost": ((usage.get("prompt_tokens") or 0) * price[0] + (usage.get("completion_tokens") or 0) * price[1]) / 1e6}


def judge(model, effort, secret, scenario, text):
    body = {"messages": [{"role": "system", "content": RUBRIC},
                         {"role": "user", "content": "Character: %s, in the %s channel. Just said to them: %s\nTheir answer: %s" % (scenario["who"], scenario["channel"], scenario["line"], text)}],
            "temperature": 0}
    try:
        reply, _ = upstream.complete(profile(model, effort), body, secret)
        content = ((reply.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        scores = json.loads(re.search(r"\{.*\}", content, re.S).group(0))
        return sum(float(scores.get(name, 0)) for name in ("in_character", "lore", "brief", "no_player_talk", "engaging"))
    except Exception:  # noqa: BLE001 - an unreadable verdict counts as nothing
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", default="gpt-6-luna,gpt-4o-mini,gpt-5-nano,gpt-4.1-nano,gpt-4.1-mini,gpt-5.4-nano")
    parser.add_argument("--judge", default="gpt-6-luna")
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    secret = key()
    jury = effort_for(args.judge, secret)
    cases = scenarios()
    print("%d situations x %d reps" % (len(cases), args.reps), flush=True)
    rows = []
    for model in args.models.split(","):
        effort = effort_for(model, secret)
        with concurrent.futures.ThreadPoolExecutor(args.workers) as pool:
            results = list(pool.map(lambda case: one(model, effort, secret, case), cases * args.reps))
        pairs = [(case, result) for case, result in zip(cases * args.reps, results) if result.get("text")]
        with concurrent.futures.ThreadPoolExecutor(args.workers) as pool:
            scores = list(pool.map(lambda pair: judge(args.judge, jury, secret, pair[0], pair[1]["text"]), pairs))
        scored = [score for score in scores if score is not None]
        latencies = sorted(result["ms"] for _, result in pairs)
        meta = sum(1 for _, result in pairs if rp_bank.META.search(result["text"]) or rp_bank.ANACHRONISM.search(result["text"]))
        rows.append((model, effort or "-", len(pairs), len(results) - len(pairs), statistics.mean(scored) if scored else 0,
                     latencies[len(latencies) // 2] if latencies else 0, latencies[int(len(latencies) * 0.9)] if latencies else 0,
                     sum(result["cost"] for _, result in pairs) / max(1, len(pairs)), meta, pairs[0][1]["text"] if pairs else ""))
        print("%-14s effort=%-8s ok=%d failed=%d score=%.2f/8  p50=%dms p90=%dms  $%.5f/line  slips=%d" % rows[-1][:9], flush=True)
        print("    e.g. %s" % rows[-1][9][:140], flush=True)


if __name__ == "__main__":
    main()
