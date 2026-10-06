"""The routes squidbots.py serves for the Minds page, and the guarantee that the public copy never carries it."""
import http.client
import http.server
import json
import os
import sys
import tempfile
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import squidbots  # noqa: E402  (importing it starts nothing: the server only runs under __main__)


class RouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        config = os.path.join(cls.tmp.name, "dashboard.json")
        with open(config, "w") as handle:
            json.dump({"mind": {"port": 1}}, handle)          # nothing listens there: the service counts as stopped
        cls.saved = (squidbots.SETTINGS_FILE, squidbots.MIND_API, squidbots.resolve_character, squidbots.PORT)
        squidbots.SETTINGS_FILE, squidbots.MIND_API = config, None
        squidbots.resolve_character = lambda name: {"ann": (77, "Ann")}.get((name or "").lower())
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), squidbots.Handler)
        cls.server.daemon_threads = True
        cls.port = squidbots.PORT = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        squidbots.SETTINGS_FILE, squidbots.MIND_API, squidbots.resolve_character, squidbots.PORT = cls.saved
        cls.tmp.cleanup()

    def call(self, method, path, body=None, headers=None, host=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        merged = {"Host": host or "localhost:%d" % self.port}
        merged.update(headers or {})
        data = json.dumps(body) if body is not None else None
        connection.request(method, path, data, merged)
        response = connection.getresponse()
        text = response.read().decode("utf-8")
        try:
            return response.status, json.loads(text)
        except ValueError:
            return response.status, text

    def post(self, body, **headers):
        return self.call("POST", "/api/mind", body, dict({"Content-Type": "application/json",
                                                        "Origin": "http://localhost:%d" % self.port}, **headers))

    def test_overview_and_the_reads(self):
        for path in ("/api/mind", "/api/mind/cards", "/api/mind/analytics?days=7", "/api/mind/turns", "/api/mind/personas",
                     "/api/mind/export"):
            status, data = self.call("GET", path)
            self.assertEqual(status, 200, path)
            self.assertIsInstance(data, dict)
        self.assertFalse(self.call("GET", "/api/mind")[1]["service"]["running"])

    def test_writes_round_trip(self):
        status, data = self.post({"op": "profile.save", "name": "main", "base_url": "http://x/v1", "model": "m"})
        self.assertEqual((status, data), (200, {"ok": True, "name": "main"}))
        self.assertEqual(self.call("GET", "/api/mind")[1]["profiles"][0]["name"], "main")
        self.post({"op": "persona.save", "guid": 77, "name": "Ann", "archetype": "test"})
        self.assertEqual(self.call("GET", "/api/mind/bot?name=ann")[1]["persona"]["archetype"], "test")
        self.assertIn("Ann", self.call("GET", "/api/mind/cards")[1]["personas"])

    def test_errors_are_json_with_the_right_status(self):
        self.assertEqual(self.post({"op": "nope"})[0], 400)
        self.assertEqual(self.call("GET", "/api/mind/bot?name=Nobody")[0], 404)
        self.assertEqual(self.call("GET", "/api/mind/turns?limit=abc")[0], 400)
        self.assertEqual(self.call("GET", "/api/mind/turn?id=999999")[0], 404)
        self.assertEqual(self.call("GET", "/api/mind/whatever")[0], 404)

    def test_writes_must_come_from_the_dashboard_page(self):
        body = {"op": "setting.set", "key": "paused", "value": 1}
        no_origin_type = self.call("POST", "/api/mind", body, {"Content-Type": "text/plain"})
        self.assertEqual(no_origin_type[0], 415)                                            # a form cannot send JSON
        foreign = self.call("POST", "/api/mind", body, {"Content-Type": "application/json", "Origin": "http://evil.example"})
        self.assertEqual(foreign[0], 403)
        self.assertEqual(self.call("GET", "/api/mind", host="evil.example")[0], 403)          # DNS rebinding
        self.assertEqual(self.call("GET", "/api/mind")[1]["settings"]["paused"], "0")

    def test_the_public_copy_never_carries_the_minds_page(self):
        files = squidbots.public_files()                       # raises if private code is left in
        self.assertEqual([name for name in files if "mind" in name], [])
        page = files["index.html"].decode("utf-8")
        script = files["static/dashboard.js"].decode("utf-8")
        # Its markup, code and API are absent. (Its name may remain in the word tables, as Settings' does; the
        # PUBLIC filter on PAGES keeps it from being shown.)
        for needle in ('data-page="minds"', "static/minds", "mindSheet", "/api/mind", "botMindHtml", "mindDot", "botMindSheet",
                       'id="mind'):
            self.assertFalse(needle in page, "public index.html contains %r" % needle)
            self.assertFalse(needle in script, "public dashboard.js contains %r" % needle)
        self.assertIn('page !== "minds"', script)              # ... and the page list drops it in public mode

    def test_a_linux_worldserver_is_seen_as_running(self):
        import subprocess
        calls = []

        def fake_run(command, **kwargs):
            calls.append(command[0])
            out = {"pgrep": "4242\n", "ps": " 2500000\n"}.get(command[0], "")
            return subprocess.CompletedProcess(command, 0, stdout=out, stderr="")
        original = squidbots.subprocess.run
        squidbots.subprocess.run = fake_run
        try:
            if os.name == "nt":
                self.skipTest("the Linux branch")
            state = squidbots.server_state()
        finally:
            squidbots.subprocess.run = original
        self.assertEqual((state["running"], state["ramMo"], calls[:2]), (True, 2441, ["pgrep", "ps"]))

    def test_the_private_page_does_carry_it(self):
        with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as handle:
            page = handle.read()
        self.assertIn('data-page="minds"', page)
        self.assertIn("static/minds.js", page)


if __name__ == "__main__":
    unittest.main()

class JevStatusTests(unittest.TestCase):
    """The savings figures the Jev card shows, from stubbed audit rows and a temporary mind database."""

    def setUp(self):
        from mind import store as store_module
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = store_module.Store(os.path.join(self.tmp.name, "mind.sqlite"))
        self.api = type("A", (), {"store": self.store})()
        self.saved = (squidbots.mysql, squidbots.botconfig.read_settings)
        self.addCleanup(lambda: (setattr(squidbots, "mysql", self.saved[0]), setattr(squidbots.botconfig, "read_settings", self.saved[1])))
        squidbots.botconfig.read_settings = lambda directory: [
            {"key": "OllamaChat.Jev.Enable", "value": "1"}, {"key": "OllamaChat.Jev.Tactical.Enable", "value": "1"},
            {"key": "OllamaChat.Jev.Classifier.Enable", "value": "0"}]

    def log_llm_calls(self, count, cost):
        for _ in range(count):
            self.store.log_call("fast", 1, "p", "m", 3000, 20, cost, 1000, True)

    def test_jev_that_decides_cheaply_is_shown_as_a_saving(self):
        self.log_llm_calls(10, 0.00013)
        squidbots.mysql = lambda query: ([["jev", "60", "420", "126000"], ["llm", "40", "2100", "0"]] if "tactical" in query else [])
        report = squidbots.jev_status(self.api, 24)
        self.assertEqual(report["enabled"], {"jev": True, "tactical": True, "classifier": False})
        self.assertEqual(report["sites"]["tactical"]["jev"], {"calls": 60, "ms": 420, "tokens": 126000})
        self.assertEqual(report["jev_calls"], 60)
        self.assertAlmostEqual(report["jev_cost"], 126000 * 0.042 / 1e6)
        self.assertAlmostEqual(report["displaced_cost"], 60 * 0.00013)
        self.assertGreater(report["saved"], 0)

    def test_jev_that_costs_more_than_the_model_shows_a_loss_rather_than_hiding_it(self):
        self.log_llm_calls(5, 0.00001)
        squidbots.mysql = lambda query: ([["jev", "100", "400", "210000"]] if "tactical" in query else [])
        self.assertLess(squidbots.jev_status(self.api, 24)["saved"], 0)

    def test_no_audit_rows_or_a_database_error_gives_zeros_and_a_message_not_a_crash(self):
        squidbots.mysql = lambda query: []
        report = squidbots.jev_status(self.api, "banana")
        self.assertEqual((report["hours"], report["jev_calls"], report["saved"]), (24, 0, 0))
        def broken(query):
            raise RuntimeError("Table doesn't exist")
        squidbots.mysql = broken
        self.assertIn("error", squidbots.jev_status(self.api, 24)["sites"]["tactical"])

