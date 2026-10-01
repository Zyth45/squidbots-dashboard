"""The HTTP face of the mind service: an OpenAI-compatible chat endpoint for the worldserver module.

    POST /v1/chat/completions        the smart lane (a player is talking to a bot)
    POST /fast/v1/chat/completions   the fast lane (tactical ticks, classifiers)
    POST /ambient                    one line of overheard chat from one bot (see ambient.py)
    POST /cast                       the realm's regulars: who they are, their friendships (see community.py)
    GET  /health                     {"ok": true}

Point the module at it with OllamaChat.Gateway.Url and OllamaChat.Tactical.Url (see docs/minds.md).
"""
import hmac
import http.server
import json
import os
import threading
import time

from . import config, gateway as gateway_module, jev, store as store_module

MAX_BODY = 4 * 1024 * 1024
ROUTES = {"/v1/chat/completions": "smart", "/fast/v1/chat/completions": "fast", "/ambient": "ambient", "/bank": "bank",
          "/cast": "cast"}
HEARTBEAT_EVERY = 5


def write_atomic(path, body):
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(body)
    os.replace(temporary, path)


def sse_chunks(answer):
    """The one-piece 'stream' for a caller that asked for streaming: the whole reply in a single delta."""
    choice = (answer.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    delta = {"role": "assistant"}
    if message.get("content"):
        delta["content"] = message["content"]
    if message.get("tool_calls"):
        delta["tool_calls"] = [dict(call, index=index) for index, call in enumerate(message["tool_calls"])]
    base = {"id": answer.get("id", "mind"), "object": "chat.completion.chunk",
            "created": answer.get("created", int(time.time())), "model": answer.get("model", "")}
    first = dict(base, choices=[{"index": 0, "delta": delta, "finish_reason": None}])
    last = dict(base, choices=[{"index": 0, "delta": {}, "finish_reason": choice.get("finish_reason") or "stop"}])
    return ("data: %s\n\n" % json.dumps(first), "data: %s\n\n" % json.dumps(last), "data: [DONE]\n\n")


def make_handler(gateway, token):
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _send(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorised(self):
            if not token:
                return True
            given = (self.headers.get("Authorization") or "")[len("Bearer "):]
            return hmac.compare_digest(given.encode("utf-8"), token.encode("utf-8"))

        def do_GET(self):
            if self.path.split("?")[0] == "/health":
                self._send(200, {"ok": True, "inflight": gateway.inflight})
            else:
                self._send(404, gateway_module.error_answer("not found", "not_found"))

        def do_POST(self):
            lane = ROUTES.get(self.path.split("?")[0])
            if not lane:
                self.close_connection = True  # the body was not read; do not reuse the connection
                self._send(404, gateway_module.error_answer("not found", "not_found"))
                return
            if not self._authorised():
                self.close_connection = True
                self._send(401, gateway_module.error_answer("bad or missing bearer token", "unauthorised"))
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if length <= 0 or length > MAX_BODY:
                self.close_connection = True
                self._send(413 if length > MAX_BODY else 400,
                           gateway_module.error_answer("body missing or larger than %d bytes" % MAX_BODY))
                return
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except ValueError:
                self._send(400, gateway_module.error_answer("body is not JSON"))
                return
            headers = {key.lower(): value for key, value in self.headers.items()}
            if lane == "bank":
                try:
                    answer = gateway.bank_command(body if isinstance(body, dict) else {})
                except Exception as error:  # noqa: BLE001 - a bad request must not end the service
                    answer = {"ok": False, "error": "%s: %s" % (type(error).__name__, error)}
                self._send(200, answer)
                return
            if lane == "cast":
                try:
                    answer = gateway.community.command(body if isinstance(body, dict) else {})
                except Exception as error:  # noqa: BLE001 - a bad request must not end the service
                    print("Cast request failed: %s: %s" % (type(error).__name__, error), flush=True)
                    answer = {"ok": False, "error": "%s: %s" % (type(error).__name__, error)}
                self._send(200, answer)
                return
            if lane == "ambient":
                try:
                    answer = gateway.ambient.handle(body if isinstance(body, dict) else {})
                except Exception as error:  # noqa: BLE001 - one bad request must not end the service
                    print("Ambient request failed: %s: %s" % (type(error).__name__, error), flush=True)
                    answer = {"text": "", "reason": "%s: %s" % (type(error).__name__, error)}
                self._send(200, answer)
                return
            try:
                status, answer = gateway.handle(lane, body, headers)
            except Exception as error:  # noqa: BLE001 - one bad request must not end the service
                print("Request failed: %s: %s" % (type(error).__name__, error), flush=True)
                status, answer = 500, gateway_module.error_answer("%s: %s" % (type(error).__name__, error))
            if status == 200 and isinstance(body, dict) and body.get("stream"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()
                for chunk in sse_chunks(answer):
                    self.wfile.write(chunk.encode("utf-8"))
                self.close_connection = True
                return
            self._send(status, answer)

        def log_message(self, *args):
            pass

    return Handler


def heartbeat_loop(settings, gateway, started):
    while True:
        try:
            write_atomic(settings["statusFile"], json.dumps({
                "schema": 1, "at": time.time(), "started": started, "pid": os.getpid(),
                "port": settings["port"], "inflight": gateway.inflight, "keys": gateway.key_states(),
                "noPlayer": gateway.no_player,
                "jev": {"key": bool(jev.api_key()), "calls": jev.STATS["calls"], "failures": jev.STATS["failures"],
                        "spentUsd": jev.spent_usd(), "paused": not jev.BREAKER.allow()}}))
            gateway.store.prune_call_log()
        except OSError as error:
            print("Could not write the status file: %s" % error, flush=True)
        time.sleep(HEARTBEAT_EVERY)


def serve(settings=None):
    settings = settings or config.load()
    store = store_module.Store(settings["db"])
    gateway = gateway_module.Gateway(store, settings["secretsFile"])
    server = http.server.ThreadingHTTPServer((settings["host"], settings["port"]),
                                             make_handler(gateway, settings["token"]))
    server.daemon_threads = True
    threading.Thread(target=heartbeat_loop, args=(settings, gateway, time.time()), daemon=True).start()
    print("SquidBots mind: http://%s:%d/v1/chat/completions  (Ctrl+C to stop)" % (
        settings["host"], settings["port"]), flush=True)
    if not settings["token"] and settings["host"] not in ("127.0.0.1", "localhost", "::1"):
        print("WARNING: listening on %s with no token; anyone who can reach this port can spend your LLM "
              "budget. Set mind.token in dashboard.json." % settings["host"], flush=True)
    server.serve_forever()
