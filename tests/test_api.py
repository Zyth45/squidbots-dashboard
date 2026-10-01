import http.server
import json
import os
import threading
import time
import unittest

from mind import api as api_module, config, server
from tests.support import GatewayCase, chat, profile_fields


class ApiTests(GatewayCase):
    def setUp(self):
        super().setUp()
        self.characters = {"Ann": (77, "Ann"), "Brick": (20014, "Brick")}
        self.settings = dict(config.DEFAULTS, statusFile=os.path.join(self.tmp.name, "status.json"), token="")
        self.api = api_module.Api(self.store, self.settings, lambda name: self.characters.get(name.capitalize()))

    def op(self, **body):
        return self.api.apply(body)

    def fails(self, **body):
        with self.assertRaises(api_module.ApiError) as raised:
            self.api.apply(body)
        return str(raised.exception)

    def test_profile_validation(self):
        good = dict(op="profile.save", name="cloud", base_url="https://api.example.com/v1", model="m")
        self.assertIn("http", self.fails(**dict(good, base_url="file:///etc/passwd")))
        self.assertIn("NAME", self.fails(**dict(good, api_key_env="sk-abcdef123456")))
        self.assertIn("no profile", self.fails(**dict(good, fallback="ghost")))
        self.assertIn("own fallback", self.fails(**dict(good, fallback="cloud")))
        self.assertIn("between", self.fails(**dict(good, timeout_s=0)))
        self.assertIn("required", self.fails(**dict(good, model="  ")))
        self.assertIn("letters", self.fails(**dict(good, name="../x")))
        self.op(**dict(good, api_key_env="OPENAI_API_KEY", price_in="0.15", daily_budget_usd=2))
        saved = self.store.profile("cloud")
        self.assertEqual((saved["api_key_env"], saved["price_in"], saved["daily_budget_usd"]),
                         ("OPENAI_API_KEY", 0.15, 2.0))

    def test_deleting_a_profile_removes_the_routes_that_used_it(self):
        self.op(op="profile.save", name="other", base_url="http://x/v1", model="m", fallback="main")
        self.op(op="route.set", guid=1, lane="smart", profile="other")
        self.op(op="lane.set", lane="memory", profile="other")
        self.op(op="profile.delete", name="main")
        self.assertEqual(self.store.profile("other")["fallback"], "")
        self.assertNotIn("smart", self.store.lanes())
        self.op(op="profile.delete", name="other")
        self.assertEqual(self.store.routes(1), {})
        self.assertNotIn("memory", self.store.lanes())

    def test_lanes_and_routes_only_accept_known_lanes_and_profiles(self):
        self.assertIn("lane must be", self.fails(op="lane.set", lane="loud", profile="main"))
        self.assertIn("no profile", self.fails(op="lane.set", lane="smart", profile="ghost"))
        self.op(op="lane.set", lane="smart", profile="")
        self.assertNotIn("smart", self.store.lanes())

    def test_a_persona_can_be_written_rerolled_and_removed(self):
        self.op(op="persona.save", guid=20014, name="Brick", archetype="Dwarf", traits="gruff",
                speech_style="growls", backstory="Lost a bet.", enabled=1)
        self.assertEqual(self.store.persona(20014)["source"], "manual")
        before = self.store.persona(20014)["archetype"]
        self.op(op="persona.roll", guid=20014)
        rolled = self.store.persona(20014)
        self.assertEqual(rolled["backstory"], "Lost a bet.")
        self.assertNotEqual(rolled["archetype"] + rolled["traits"], before + "gruff")
        self.op(op="persona.delete", guid=20014)
        self.assertIsNone(self.store.persona(20014))

    def test_opinions_and_chattiness_are_saved_exported_and_imported(self):
        self.op(op="persona.save", guid=20014, name="Brick", archetype="troll", opinions="gnomes rule; tanking is easy",
                chattiness=85)
        saved = self.store.persona(20014)
        self.assertEqual((saved["opinions"], saved["chattiness"]), ("gnomes rule; tanking is easy", 85))
        self.assertIn("chattiness must be between", self.fails(op="persona.save", guid=20014, chattiness=101))
        exported = self.api.export()["personas"][0]
        self.assertEqual((exported["opinions"], exported["chattiness"]), ("gnomes rule; tanking is easy", 85))
        self.op(op="persona.delete", guid=20014)
        self.op(op="persona.import", personas=[exported])
        self.assertEqual(self.store.persona(20014)["chattiness"], 85)

    def test_a_roll_gives_opinions_and_a_chattiness(self):
        self.op(op="persona.roll", guid=20014)
        rolled = self.store.persona(20014)
        self.assertTrue(rolled["opinions"])
        self.assertTrue(0 <= rolled["chattiness"] <= 100)

    def test_rerolling_all_clears_generated_personalities_only_and_keeps_mutes(self):
        self.store.save_persona(1, {"name": "Auto"}, "generated")
        self.store.save_persona(2, {"name": "Mine"}, "manual")
        self.store.save_persona(3, {"name": "Muted"}, "generated")
        self.store.set_muted(3, True)
        self.assertEqual(self.op(op="persona.reroll_all")["cleared"], 1)
        self.assertIsNone(self.store.persona(1))
        self.assertIsNotNone(self.store.persona(2))
        self.assertIsNotNone(self.store.persona(3))

    def test_a_bot_can_be_rolled_as_a_chosen_kind_of_person(self):
        self.op(op="persona.roll", guid=20014, archetype="lurker")
        self.assertEqual(self.store.persona(20014)["archetype"], "lurker")
        self.assertIn("not a kind of person", self.fails(op="persona.roll", guid=20014, archetype="knight"))

    def test_named_bots_can_be_given_a_personality_in_bulk(self):
        result = self.op(op="persona.assign", names="Ann, Brick, Nobody", archetype="troll")
        self.assertEqual([a["archetype"] for a in result["assigned"]], ["troll", "troll"])
        self.assertEqual(result["unknown"], ["Nobody"])
        self.assertEqual(self.store.persona(20014)["source"], "manual")
        self.assertEqual(self.store.persona(77)["archetype"], "troll")
        self.assertIn("between 1 and 100", self.fails(op="persona.assign", names=" , "))

    def test_bulk_assignment_without_a_kind_follows_the_mix_and_keeps_the_backstory(self):
        self.op(op="setting.set", key="personality_mix", value="lurker: 1")
        self.store.save_persona(20014, {"name": "Brick", "backstory": "Lost a bet."}, "manual")
        self.op(op="persona.assign", names="Brick")
        self.assertEqual((self.store.persona(20014)["archetype"], self.store.persona(20014)["backstory"]), ("lurker", "Lost a bet."))

    def test_the_personality_mix_is_validated_when_saved_and_used_for_new_bots(self):
        self.assertIn("not a kind", self.fails(op="setting.set", key="personality_mix", value="dragon: 3"))
        self.op(op="setting.set", key="personality_mix", value="troll: 1")
        self.gateway.handle("smart", chat(20016, "Zed", 77, "Ann", "hello"))
        self.assertEqual(self.store.persona(20016)["archetype"], "troll")
        self.assertEqual(self.api.overview()["defaults"]["personality_mix"].split(",")[0], "banter merchant: 1")
        self.assertIn("lurker", self.api.overview()["archetypes"])

    def test_control_characters_are_stripped_and_length_is_limited(self):
        self.op(op="persona.save", guid=1, name="Bo\x00b\x07", archetype="x")
        self.assertEqual(self.store.persona(1)["name"], "Bob")
        self.assertIn("longer", self.fails(op="persona.save", guid=1, backstory="x" * 1501))
        self.assertIn("guid", self.fails(op="persona.save", guid="abc"))

    def test_planting_a_memory_by_character_name(self):
        self.op(op="memory.add", guid=20014, subject_name="ann", text="Ann is my sworn friend", salience=0.9)
        fact = self.store.memories(20014, 77)[0]
        self.assertEqual((fact["kind"], fact["text"], fact["subject_name"]), ("fact", "Ann is my sworn friend", "Ann"))
        self.assertIn("no character", self.fails(op="memory.add", guid=20014, subject_name="Nobody", text="x"))

    def test_the_bot_view_finds_a_bot_by_name(self):
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "remember my name is Ann"))
        view = self.api.bot(name="Brick")
        self.assertEqual(view["guid"], 20014)
        self.assertEqual(view["persona"]["source"], "generated")
        self.assertEqual(len(view["memories"]), 1)
        self.assertEqual(view["relationships"][0]["other_name"], "Ann")
        with self.assertRaises(api_module.ApiError):
            self.api.bot(name="Nobody")

    def test_the_overview_counts_what_happened(self):
        self.store.save_profile("main", profile_fields(self.provider.url, price_in=1000.0))
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "hello"))
        overview = self.api.overview()
        self.assertEqual(overview["today"]["calls"], 1)
        self.assertAlmostEqual(overview["today"]["cost"], 0.1)
        self.assertEqual([bot["name"] for bot in overview["awake"]], ["Brick"])
        self.assertEqual(overview["profiles"][0]["calls_24h"], 1)
        self.assertFalse(overview["service"]["running"])

    def test_settings(self):
        self.op(op="setting.set", key="recall_count", value=3)
        self.op(op="setting.set", key="auto_persona", value=0)
        self.assertEqual(self.store.setting("recall_count"), "3")
        self.assertEqual(self.store.setting("auto_persona"), "0")
        self.assertIn("unknown", self.fails(op="setting.set", key="drop_table", value=1))
        self.assertIn("number", self.fails(op="setting.set", key="recall_count", value="lots"))

    def test_unknown_operations(self):
        self.assertIn("unknown operation", self.fails(op="rm -rf"))
        self.assertIn("unknown operation", self.fails())
        with self.assertRaises(api_module.ApiError):
            self.api.apply([])


class ProfileTestButton(GatewayCase):
    def test_the_test_goes_through_the_running_service_with_the_named_profile(self):
        self.store.save_profile("other", profile_fields(self.provider.url, model="other-model"))
        http_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(self.gateway, "tok"))
        http_server.daemon_threads = True
        threading.Thread(target=http_server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
        self.addCleanup(http_server.server_close)
        self.addCleanup(http_server.shutdown)
        status = os.path.join(self.tmp.name, "status.json")
        with open(status, "w") as handle:
            json.dump({"at": time.time(), "port": http_server.server_address[1], "keys": {"other": "none"}}, handle)
        api = api_module.Api(self.store, dict(config.DEFAULTS, statusFile=status, token="tok"), lambda name: None)

        result = api.apply({"op": "profile.test", "name": "other"})

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["reply"], "ok")
        self.assertEqual(self.provider.requests[-1]["body"]["model"], "other-model")

    def test_a_stopped_service_is_reported_not_guessed_at(self):
        api = api_module.Api(self.store, dict(config.DEFAULTS, statusFile=os.path.join(self.tmp.name, "none.json"),
                                              token=""), lambda name: None)
        with self.assertRaises(api_module.ApiError) as raised:
            api.apply({"op": "profile.test", "name": "main"})
        self.assertIn("not running", str(raised.exception))

    def test_a_provider_error_comes_back_as_text(self):
        http_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(self.gateway, ""))
        http_server.daemon_threads = True
        threading.Thread(target=http_server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
        self.addCleanup(http_server.server_close)
        self.addCleanup(http_server.shutdown)
        status = os.path.join(self.tmp.name, "status.json")
        with open(status, "w") as handle:
            json.dump({"at": time.time(), "port": http_server.server_address[1]}, handle)
        api = api_module.Api(self.store, dict(config.DEFAULTS, statusFile=status, token=""), lambda name: None)
        self.provider.answers = [401]
        result = api.apply({"op": "profile.test", "name": "main"})
        self.assertFalse(result["ok"])
        self.assertIn("401", result["error"])


if __name__ == "__main__":
    unittest.main()
