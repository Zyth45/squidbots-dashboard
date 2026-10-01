"""Shared test helpers: a stand-in LLM provider, and a gateway wired to a temporary database."""
import http.server
import json
import os
import tempfile
import threading
import unittest

from mind import gateway as gateway_module, store as store_module


class StubProvider:
    """An OpenAI-compatible endpoint that records every request and answers from a queue.

    Each queued answer is either a string (the reply text), a dict (sent as the whole JSON body), or an int
    (an HTTP error status). With the queue empty it answers "ok".
    """

    def __init__(self):
        self.requests = []
        self.answers = []
        provider = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
                provider.requests.append({"body": body, "headers": dict(self.headers.items()), "path": self.path})
                answer = provider.answers.pop(0) if provider.answers else "ok"
                if isinstance(answer, tuple):
                    payload = json.dumps(answer[1]).encode("utf-8")
                    self.send_response(answer[0])
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                if isinstance(answer, int):
                    self.send_response(answer)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if isinstance(answer, str):
                    answer = {"id": "x", "model": body.get("model"),
                              "choices": [{"index": 0, "message": {"role": "assistant", "content": answer},
                                           "finish_reason": "stop"}],
                              "usage": {"prompt_tokens": 100, "completion_tokens": 10}}
                payload = json.dumps(answer).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:%d/v1" % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def profile_fields(url, **overrides):
    fields = {"base_url": url, "model": "test-model", "api_key_env": "", "timeout_s": 5, "max_tokens": 0,
              "price_in": 0.0, "price_out": 0.0, "price_cached": 0.0, "max_calls_per_min": 0, "daily_budget_usd": 0.0,
              "fallback": "", "enabled": 1, "extra": ""}
    fields.update(overrides)
    return fields


def chat(bot_guid, bot_name, player_guid, player_name, text, extra_system=""):
    """A request shaped like the ones the worldserver module sends."""
    system = ("You are a bot.\n" + extra_system +
              "\nACTIVE WoW SESSION - your bot's identity is:\n"
              "- botGuid = %d, name = %s  (you, the bot character)\n"
              "- playerGuid = %d, name = %s  (the player talking to you)\n" % (
                  bot_guid, bot_name, player_guid, player_name))
    return {"model": "ignored", "user": "wow-bot-%d" % bot_guid,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": text}]}


def live_api(case, token=""):
    """An Api wired to a real mind HTTP server on this case's gateway. Returns (api, http_server)."""
    import time
    from mind import api as api_module, config, server
    http_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(case.gateway, token))
    http_server.daemon_threads = True
    threading.Thread(target=http_server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
    case.addCleanup(http_server.server_close)
    case.addCleanup(http_server.shutdown)
    status = os.path.join(case.tmp.name, "status.json")
    with open(status, "w") as handle:
        json.dump({"at": time.time(), "port": http_server.server_address[1], "keys": {}}, handle)
    characters = {"Ann": (77, "Ann"), "Brick": (20014, "Brick")}
    api = api_module.Api(case.store, dict(config.DEFAULTS, statusFile=status, token=token),
                         lambda name: characters.get(name.capitalize()))
    return api, http_server


class GatewayCase(unittest.TestCase):
    """A gateway on a temporary database, one profile "main" on both lanes pointing at a stub provider."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = store_module.Store(os.path.join(self.tmp.name, "mind.sqlite"))
        self.provider = StubProvider()
        self.addCleanup(self.provider.close)
        self.secrets_path = os.path.join(self.tmp.name, "secrets.json")
        self.gateway = gateway_module.Gateway(self.store, self.secrets_path)
        self.store.save_profile("main", profile_fields(self.provider.url))
        self.store.set_lane("smart", "main")
        self.store.set_lane("fast", "main")
        # These tests are about how a bot talks as a player; roleplay (the default) has its own tests in test_roleplay.py.
        self.store.set_setting("chat_mode", "players")

    def system_text(self, request_index=-1):
        return self.provider.requests[request_index]["body"]["messages"][0]["content"]
