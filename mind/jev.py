"""A client for TypeSafe's Jev: typed decisions instead of generated text.

Jev takes a state and a few typed questions and answers each one with probabilities. It cannot write a chat line, but it
can say which of twelve prewritten lines fits the conversation best, and whether this person would speak at all. That is
what the line bank needs to feel like a conversation rather than lines said at random.

The key is read from the environment (JEV_API_KEY, or a file named by JEV_KEY_FILE), never stored in the database or in
a config file. A failing service opens a short breaker so a slow Jev never slows chat: the caller falls back to the local
picker.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"
TIMEOUT_S = 4.0
BREAKER_FAILURES = 3
BREAKER_PAUSE_S = 60.0
PRICE_PER_M_INPUT = 0.042      # TypeSafe's list price; output is free


class JevError(Exception):
    pass


def api_key():
    key = os.environ.get("JEV_API_KEY", "").strip()
    path = os.environ.get("JEV_KEY_FILE", "").strip()
    if not key and path:
        try:
            with open(path, encoding="utf-8") as handle:
                key = handle.read().strip()
        except OSError:
            key = ""
    return key


class Breaker:
    def __init__(self):
        self.lock = threading.Lock()
        self.failures = 0
        self.open_until = 0.0

    def allow(self):
        with self.lock:
            return time.monotonic() >= self.open_until

    def record(self, ok):
        with self.lock:
            if ok:
                self.failures = 0
                return
            self.failures += 1
            if self.failures >= BREAKER_FAILURES:
                self.open_until = time.monotonic() + BREAKER_PAUSE_S
                self.failures = 0


BREAKER = Breaker()
STATS = {"calls": 0, "failures": 0, "input_tokens": 0}


def available():
    return bool(api_key()) and BREAKER.allow()


def decide(state, questions, model=MODEL, endpoint=ENDPOINT, timeout=TIMEOUT_S):
    """{question name: answer} for the questions. Raises JevError; the caller falls back."""
    key = api_key()
    if not key:
        raise JevError("no Jev key in the environment")
    if not BREAKER.allow():
        raise JevError("Jev is paused after repeated failures")
    body = json.dumps({"model": model, "state": state, "questions": questions}).encode("utf-8")
    request = urllib.request.Request(endpoint, data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + key})
    STATS["calls"] += 1
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            answer = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as failure:
        STATS["failures"] += 1
        BREAKER.record(False)
        raise JevError("Jev call failed: %s" % failure)
    BREAKER.record(True)
    STATS["input_tokens"] += int((answer.get("usage") or {}).get("input_tokens") or 0)
    answers = answer.get("answers")
    if not isinstance(answers, dict):
        raise JevError("Jev answered without answers")
    return answers


def choice_question(instructions, options):
    """A `choice` over {option key: what it means}."""
    return {"type": "choice", "instructions": instructions, "criteria": dict(options)}


def yes_question(instructions):
    return {"type": "noul", "instructions": instructions}


def top_choice(answer, valid):
    """(key, probability) of the most likely option that is one of `valid`, or (None, 0)."""
    probabilities = (answer or {}).get("probabilities") or {}
    best, best_p = None, 0.0
    for key in valid:
        p = probabilities.get(key)
        if isinstance(p, (int, float)) and p > best_p:
            best, best_p = key, float(p)
    if best is None and (answer or {}).get("choice") in valid:
        return answer["choice"], float((answer or {}).get("confidence") or 0)
    return best, best_p


def spent_usd():
    return STATS["input_tokens"] * PRICE_PER_M_INPUT / 1e6
