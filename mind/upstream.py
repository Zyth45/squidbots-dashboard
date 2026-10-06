"""One call to an OpenAI-compatible chat endpoint (Ollama, OpenAI, OpenRouter, LiteLLM, DeepSeek, ...)."""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


# Providers sometimes echo (part of) the key back in an error: "Incorrect API key provided: sk-proj-****wxyz".
# Errors are kept in the call log and shown in the dashboard, so anything key-shaped is cut short first.
KEYLIKE = re.compile(r"\b((?:sk|pk|rk|key|ak)-[A-Za-z0-9_\-]{0,4})[A-Za-z0-9_\-\*\.\u2026]{4,}", re.I)
BEARER = re.compile(r"(Bearer\s+)\S+", re.I)


def redact(text):
    return BEARER.sub(r"\1***", KEYLIKE.sub(r"\1***", text))


class UpstreamError(Exception):
    """The provider did not give an answer; `status` is its HTTP status, 0 when it never answered."""

    def __init__(self, message, status=0):
        super().__init__(message)
        self.status = status


def endpoint(base_url):
    """`http://host:11434/v1` and `http://host/v1/chat/completions` both mean the same thing."""
    url = base_url.strip().rstrip("/")
    return url if url.endswith("/chat/completions") else url + "/chat/completions"


def api_key(profile_name, env_name, secrets):
    """The key for a profile: the environment variable it names, else its entry in the secrets file."""
    if env_name and os.environ.get(env_name):
        return os.environ[env_name]
    return str(secrets.get(profile_name, "")) if secrets else ""


# What a profile's "extra parameters" may never override: they would break the request or the routing.
PROTECTED = ("model", "messages", "stream", "tools", "tool_choice", "user")


def _is_openai(url):
    return (urllib.parse.urlsplit(url).hostname or "").endswith("openai.com")


# What a (endpoint, model) has refused before, so the fix is applied up front from then on instead of failing every call:
# {(base_url, model): {parameter: replacement}} where a replacement of None means "leave the parameter out".
_LEARNED = {}
_LEARNED_LOCK = threading.Lock()


def _learn(profile, before, after):
    changes = {key: after.get(key) for key in set(before) | set(after) if before.get(key) != after.get(key)}
    changes.pop("stream", None)
    if changes:
        with _LEARNED_LOCK:
            _LEARNED.setdefault((profile["base_url"], profile["model"]), {}).update(changes)


def build_payload(profile, body):
    """The request for this provider: our model, no streaming, the profile's limits and extra parameters."""
    payload = _build_payload(profile, body)
    with _LEARNED_LOCK:
        learned = dict(_LEARNED.get((profile["base_url"], profile["model"]), {}))
    for key, value in learned.items():
        if value is None:
            payload.pop(key, None)
        elif key in payload or key in ("max_completion_tokens", "max_tokens", "reasoning_effort"):
            payload[key] = value
    return payload


def _build_payload(profile, body):
    payload = dict(body)
    payload["model"] = profile["model"]
    payload["stream"] = False
    if profile["max_tokens"] and "max_tokens" not in payload and "max_completion_tokens" not in payload:
        payload["max_tokens"] = profile["max_tokens"]
    if profile.get("extra"):
        try:
            extra = json.loads(profile["extra"])
        except ValueError:
            extra = {}
        payload.update({key: value for key, value in extra.items() if key not in PROTECTED})
    if _is_openai(profile["base_url"]):
        # OpenAI's current models take max_completion_tokens and refuse max_tokens.
        if "max_tokens" in payload:
            payload["max_completion_tokens"] = payload.pop("max_tokens")
    return payload


def _adjust(payload, message):
    """Change the payload to fix what the provider complained about; False when there is nothing to change.

    Providers differ on small things: some refuse a temperature, some want max_completion_tokens instead of
    max_tokens (or the reverse). One retry with the offending parameter fixed is cheaper than a profile setting
    for each quirk, and the message says which one it was.
    """
    lowered = message.lower()
    if "temperature" in payload and "temperature" in lowered:
        del payload["temperature"]
        return True
    if "reasoning_effort" in payload and "reasoning_effort" in lowered:
        # Models differ: gpt-5.4 and later take function tools only with effort "none"; gpt-5 and gpt-5-mini refuse "none"
        # and take "minimal" or "low"; others have no such setting. The error says which, so follow it.
        supported = re.findall(r"'([a-z]+)'", message.split("Supported values are:", 1)[1]) if "Supported values are:" in message else []
        current = payload["reasoning_effort"]
        if supported:
            pick = next((value for value in ("none", "minimal", "low") if value in supported), supported[0])
            if pick == current:
                del payload["reasoning_effort"]
            else:
                payload["reasoning_effort"] = pick
        elif "'none'" in lowered and current != "none":
            payload["reasoning_effort"] = "none"
        else:
            del payload["reasoning_effort"]
        return True
    if "max_tokens" in payload and "max_tokens" in lowered:
        payload["max_completion_tokens"] = payload.pop("max_tokens")
        return True
    if "max_completion_tokens" in payload and "max_completion_tokens" in lowered:
        payload["max_tokens"] = payload.pop("max_completion_tokens")
        return True
    return False


def complete(profile, body, key):
    """POST `body` to the profile's endpoint. Returns (answer dict, latency in ms). Raises UpstreamError."""
    payload = build_payload(profile, body)
    first = dict(payload)
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    started = time.monotonic()
    for attempt in range(3):
        request = urllib.request.Request(endpoint(profile["base_url"]), data=json.dumps(payload).encode("utf-8"),
                                         headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=profile["timeout_s"] or 60) as response:
                raw = response.read()
            if attempt:
                _learn(profile, first, payload)
            break
        except urllib.error.HTTPError as error:
            detail = error.read()[:400].decode("utf-8", "replace")
            if error.code == 400 and attempt < 2 and _adjust(payload, detail):
                continue
            raise UpstreamError("HTTP %d from %s: %s" % (error.code, profile["name"], redact(detail)[:300]), error.code)
        except (urllib.error.URLError, OSError) as error:
            raise UpstreamError("%s unreachable: %s" % (profile["name"], getattr(error, "reason", error)))
    latency = int((time.monotonic() - started) * 1000)
    try:
        answer = json.loads(raw.decode("utf-8"))
    except ValueError:
        raise UpstreamError("%s did not return JSON" % profile["name"])
    if not isinstance(answer, dict) or not answer.get("choices"):
        # Some providers answer HTTP 200 with {"error": {...}}.
        error = answer.get("error") if isinstance(answer, dict) else None
        message = error.get("message") if isinstance(error, dict) else error
        raise UpstreamError("%s: %s" % (profile["name"], message or "no choices in the answer"))
    return answer, latency
