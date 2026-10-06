import http.client
import json
import os
import threading
import time
import unittest
import http.server

from mind import server
from tests.support import GatewayCase, chat, profile_fields


class GatewayTests(GatewayCase):
    def test_persona_is_added_in_front_of_the_modules_prompt_and_the_model_is_swapped(self):
        status, answer = self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "hello"))
        self.assertEqual(status, 200)
        self.assertEqual(answer["choices"][0]["message"]["content"], "ok")
        sent = self.provider.requests[0]["body"]
        self.assertEqual(sent["model"], "test-model")
        self.assertFalse(sent["stream"])
        text = sent["messages"][0]["content"]
        self.assertTrue(text.startswith("WHO YOU ARE"))
        self.assertIn("You are Brick.", text)
        self.assertIn("You are a bot.", text)                      # the module's own prompt is still there
        self.assertLess(text.index("WHO YOU ARE"), text.index("You are a bot."))

    def test_the_model_is_told_to_act_with_its_tools(self):
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "invite me"))
        text = self.system_text()
        self.assertIn("do it with your tools", text)
        self.assertIn("even when you are not in a group yet", text)

    def test_a_generated_persona_is_stable_and_saved(self):
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "hello"))
        first = self.store.persona(20014)
        self.assertEqual(first["source"], "generated")
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "hello again"))
        self.assertEqual(self.store.persona(20014)["archetype"], first["archetype"])

    def test_a_written_persona_is_used_and_never_regenerated(self):
        self.store.save_persona(20014, {"name": "Brick", "archetype": "Dwarf tavern-keeper", "traits": "gruff",
                                        "speech_style": "growls", "backstory": "Lost a bet to a gnome."}, "manual")
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "hello"))
        self.assertIn("Lost a bet to a gnome.", self.system_text())
        self.assertEqual(self.store.persona(20014)["source"], "manual")

    def test_a_disabled_persona_leaves_the_prompt_alone(self):
        self.store.save_persona(20014, {"name": "Brick", "archetype": "x", "enabled": 0}, "manual")
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "hello"))
        self.assertNotIn("WHO YOU ARE", self.system_text())

    def test_the_second_conversation_remembers_the_first(self):
        self.provider.answers = ["Nice to meet you, Ann."]
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "remember that I main a paladin"))
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "what do you know about my paladin?"))
        text = self.system_text()
        self.assertIn("WHAT YOU REMEMBER", text)
        self.assertIn("main a paladin", text)

    def test_memory_is_private_to_each_player(self):
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "remember my secret is xyzzy"))
        self.gateway.handle("smart", chat(20014, "Brick", 88, "Bob", "tell me a secret xyzzy"))
        self.assertNotIn("xyzzy", self.system_text())

    def test_tool_rounds_pass_through_and_are_not_remembered(self):
        tool_answer = {"id": "t", "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
            "role": "assistant", "content": None,
            "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "get_inventory", "arguments": "{}"}}]}}]}
        self.provider.answers = [tool_answer]
        request = chat(20014, "Brick", 77, "Ann", "what is in your bags?")
        request["tools"] = [{"type": "function", "function": {"name": "get_inventory"}}]
        status, answer = self.gateway.handle("smart", request)
        self.assertEqual(status, 200)
        self.assertEqual(answer["choices"][0]["message"]["tool_calls"][0]["function"]["name"], "get_inventory")
        self.assertEqual(self.provider.requests[0]["body"]["tools"], request["tools"])
        self.assertEqual(self.store.memories(20014, 77), [])

    def test_a_request_that_names_no_bot_is_routed_untouched(self):
        body = {"messages": [{"role": "system", "content": "plain"}, {"role": "user", "content": "hi"}]}
        status, _ = self.gateway.handle("smart", body)
        self.assertEqual(status, 200)
        self.assertEqual(self.system_text(), "plain")
        self.assertEqual(self.store.counts()["persona"], 0)

    def test_the_callers_request_is_not_modified(self):
        request = chat(20014, "Brick", 77, "Ann", "hello")
        before = json.dumps(request)
        self.gateway.handle("smart", request)
        self.assertEqual(json.dumps(request), before)

    def test_the_fast_lane_gets_a_voice_but_no_memory(self):
        body = {"user": "wow-bot-20014", "messages": [{"role": "system", "content": "pick one action as JSON"},
                                                      {"role": "user", "content": "{}"}]}
        status, _ = self.gateway.handle("fast", body)
        self.assertEqual(status, 200)
        text = self.system_text()
        self.assertTrue(text.startswith("pick one action as JSON"))
        self.assertIn("When you speak, speak as", text)
        self.assertEqual(self.store.counts()["memory"], 0)

    def test_a_bot_can_have_its_own_model(self):
        self.store.save_profile("big", profile_fields(self.provider.url, model="big-model"))
        self.store.set_route(20014, "smart", "big")
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "hello"))
        self.gateway.handle("smart", chat(20015, "Raz", 77, "Ann", "hello"))
        self.assertEqual([r["body"]["model"] for r in self.provider.requests], ["big-model", "test-model"])

    def test_no_profile_on_the_lane_is_a_clear_error(self):
        self.store.set_lane("smart", "")
        status, answer = self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "hello"))
        self.assertEqual(status, 503)
        self.assertIn("smart lane", answer["error"]["message"])

    def test_the_api_key_comes_from_the_environment_then_the_secrets_file(self):
        self.store.save_profile("main", profile_fields(self.provider.url, api_key_env="MIND_TEST_KEY"))
        os.environ["MIND_TEST_KEY"] = "from-env"
        self.addCleanup(os.environ.pop, "MIND_TEST_KEY", None)
        self.gateway.handle("smart", chat(1, "A", 2, "B", "hi"))
        self.assertEqual(self.provider.requests[-1]["headers"]["Authorization"], "Bearer from-env")
        del os.environ["MIND_TEST_KEY"]
        with open(self.secrets_path, "w") as handle:
            json.dump({"main": "from-file"}, handle)
        self.gateway.handle("smart", chat(1, "A", 2, "B", "hi"))
        self.assertEqual(self.provider.requests[-1]["headers"]["Authorization"], "Bearer from-file")

    def test_a_failing_profile_falls_back_once(self):
        self.store.save_profile("backup", profile_fields(self.provider.url, model="backup-model"))
        self.store.save_profile("main", profile_fields(self.provider.url, fallback="backup"))
        self.provider.answers = [500, "from the backup"]
        status, answer = self.gateway.handle("smart", chat(1, "A", 2, "B", "hi"))
        self.assertEqual(status, 200)
        self.assertEqual(answer["choices"][0]["message"]["content"], "from the backup")
        self.assertEqual(self.provider.requests[-1]["body"]["model"], "backup-model")
        failed = [row for row in self.store.recent_errors(0)]
        self.assertEqual(len(failed), 1)

    def test_fallbacks_that_point_at_each_other_do_not_loop(self):
        self.store.save_profile("a", profile_fields(self.provider.url, fallback="b"))
        self.store.save_profile("b", profile_fields(self.provider.url, fallback="a"))
        self.store.set_lane("smart", "a")
        self.provider.answers = [500, 500, 500]
        status, _ = self.gateway.handle("smart", chat(1, "A", 2, "B", "hi"))
        self.assertEqual(status, 502)
        self.assertEqual(len(self.provider.requests), 2)

    def test_calls_per_minute_are_capped(self):
        self.store.save_profile("main", profile_fields(self.provider.url, max_calls_per_min=2))
        codes = [self.gateway.handle("smart", chat(1, "A", 2, "B", "hi %d" % i))[0] for i in range(3)]
        self.assertEqual(codes, [200, 200, 429])
        self.assertEqual(len(self.provider.requests), 2)

    def test_the_daily_budget_stops_spending(self):
        self.store.save_profile("main", profile_fields(self.provider.url, price_in=10000.0, daily_budget_usd=0.5))
        first = self.gateway.handle("smart", chat(1, "A", 2, "B", "hi"))[0]      # 100 tokens * $10k/M = $1
        second = self.gateway.handle("smart", chat(1, "A", 2, "B", "again"))
        self.assertEqual(first, 200)
        self.assertEqual(second[0], 429)
        self.assertIn("budget", second[1]["error"]["message"])

    def test_a_reused_guid_does_not_inherit_the_old_characters_past(self):
        self.store.save_persona(20014, {"name": "Brick", "archetype": "x"}, "generated")
        self.store.add_memory(20014, 77, "Ann", "fact", "Ann owes Brick 5 gold", 0.9)
        self.gateway.handle("smart", chat(20014, "Somebodyelse", 77, "Ann", "hi"))
        self.assertFalse([m for m in self.store.memories(20014) if "owes" in m["text"]])
        self.assertEqual(self.store.persona(20014)["name"], "Somebodyelse")

    def test_reflection_turns_exchanges_into_facts_and_feelings(self):
        self.store.save_profile("thinker", profile_fields(self.provider.url, model="thinker-model"))
        self.store.set_lane("memory", "thinker")
        self.store.set_setting("reflect_every", 2)
        self.provider.answers = ["hi Ann", "welcome back",
                                 '{"facts": [{"text": "Ann plays a healer", "salience": 0.7}],'
                                 ' "affinity_change": 0.2, "reason": "friendly"}']
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "hello, I play a healer"))
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "back again"))
        deadline = time.time() + 20
        while time.time() < deadline and not self.store.memories(20014, 77, kinds=["fact"]):
            time.sleep(0.05)
        facts = self.store.memories(20014, 77, kinds=["fact"])
        self.assertEqual([f["text"] for f in facts], ["Ann plays a healer"])
        self.assertAlmostEqual(self.store.relationship(20014, 77)["affinity"], 0.2)
        self.assertEqual(self.provider.requests[-1]["body"]["model"], "thinker-model")

    def test_bad_requests(self):
        self.assertEqual(self.gateway.handle("smart", {"nope": 1})[0], 400)
        self.assertEqual(self.gateway.handle("smart", [])[0], 400)


class ServerTests(GatewayCase):
    def setUp(self):
        super().setUp()
        self.http = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(self.gateway, "secret"))
        self.http.daemon_threads = True
        threading.Thread(target=self.http.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
        self.addCleanup(self.http.server_close)
        self.addCleanup(self.http.shutdown)
        self.port = self.http.server_address[1]

    def post(self, path, body, token="secret"):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        connection.request("POST", path, json.dumps(body), headers)
        response = connection.getresponse()
        return response.status, response.read().decode("utf-8"), response.getheader("Content-Type")

    def test_requires_the_token(self):
        self.assertEqual(self.post("/v1/chat/completions", chat(1, "A", 2, "B", "hi"), token="")[0], 401)
        self.assertEqual(self.post("/v1/chat/completions", chat(1, "A", 2, "B", "hi"), token="wrong")[0], 401)
        self.assertEqual(len(self.provider.requests), 0)

    def test_answers_on_both_lanes(self):
        for path in ("/v1/chat/completions", "/fast/v1/chat/completions"):
            status, text, _ = self.post(path, chat(1, "A", 2, "B", "hi"))
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(text)["choices"][0]["message"]["content"], "ok")

    def test_streaming_callers_get_the_reply_as_one_event_stream(self):
        body = chat(1, "A", 2, "B", "hi")
        body["stream"] = True
        status, text, kind = self.post("/v1/chat/completions", body)
        self.assertEqual(status, 200)
        self.assertEqual(kind, "text/event-stream")
        events = [line[6:] for line in text.splitlines() if line.startswith("data: ")]
        self.assertEqual(events[-1], "[DONE]")
        self.assertEqual(json.loads(events[0])["choices"][0]["delta"]["content"], "ok")

    def test_unknown_paths_and_garbage(self):
        self.assertEqual(self.post("/v2/whatever", {})[0], 404)
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        connection.request("POST", "/v1/chat/completions", "not json",
                           {"Authorization": "Bearer secret", "Content-Type": "application/json"})
        self.assertEqual(connection.getresponse().status, 400)

    def test_health_needs_no_token(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        connection.request("GET", "/health")
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertTrue(json.loads(response.read())["ok"])


if __name__ == "__main__":
    unittest.main()
