import json
import os
import time
import unittest

from mind import filters, upstream
from tests.support import GatewayCase, chat, live_api, profile_fields


class FilterTests(unittest.TestCase):
    def test_markup_emoji_and_layout_are_removed(self):
        text = "**Well** met, _friend_!  😀\n\nCome `along`."
        self.assertEqual(filters.clean(text), "Well met, friend! Come along.")

    def test_the_bots_own_name_is_not_repeated_on_the_line(self):
        self.assertEqual(filters.clean("Brick: not today", bot_name="Brick"), "not today")
        self.assertEqual(filters.clean("[Brick] - not today", bot_name="Brick"), "not today")
        self.assertEqual(filters.clean("Bricks are heavy", bot_name="Brick"), "Bricks are heavy")

    def test_blocked_words_are_starred_whole_words_only(self):
        self.assertEqual(filters.clean("that was a Darn shame, darned thing", blocked=["darn"]),
                         "that was a **** shame, darned thing")

    def test_long_replies_are_cut_at_a_sentence(self):
        text = "First sentence here. " + "Second sentence goes on and on. " * 12
        cut = filters.clean(text, max_chars=120)
        self.assertTrue(cut.endswith("."))
        self.assertLessEqual(len(cut), 120)
        self.assertTrue(cut.startswith("First sentence here."))

    def test_a_reply_without_sentences_is_cut_at_a_word(self):
        cut = filters.clean("word " * 100, max_chars=50)
        self.assertLessEqual(len(cut), 51)
        self.assertTrue(cut.endswith("..."))

    def test_a_chat_line_is_cut_to_a_whole_sentence_however_short_that_leaves_it(self):
        text = "Welcome, John! Glad you're here. Every group needs a tank and a questionable plan, so you're already among the best."
        self.assertEqual(filters.clean(text, max_chars=110, whole_thought=True), "Welcome, John! Glad you're here.")
        # a long answer to be read keeps its substance: it is not shrunk to its first sentence
        self.assertTrue(filters.clean(text, max_chars=110).endswith("..."))

    def test_a_chat_line_of_one_long_sentence_is_cut_at_a_clause_not_in_the_middle_of_one(self):
        text = "hey john good to see you back, how is the cloak hunt going, did you ever find a good weapon or are you still on the starter sword"
        cut = filters.clean(text, max_chars=90, whole_thought=True)
        self.assertEqual(cut, "hey john good to see you back, how is the cloak hunt going.")

    def test_a_chat_line_with_nowhere_to_cut_still_ends_at_a_word(self):
        cut = filters.clean("word " * 100, max_chars=50, whole_thought=True)
        self.assertLessEqual(len(cut), 51)
        self.assertTrue(cut.endswith("..."))

    def test_snake_case_and_roleplay_actions_survive(self):
        self.assertEqual(filters.clean("try bot_follow, then *waves* and use speech_style"),
                         "try bot_follow, then *waves* and use speech_style")

    def test_headings_and_bullets_go(self):
        self.assertEqual(filters.clean("# Title\n- one\n- two"), "Title one two")

    def test_non_text_passes_through(self):
        self.assertIsNone(filters.clean(None))


class UpstreamCompatTests(GatewayCase):
    def test_openai_hosts_get_max_completion_tokens(self):
        payload = upstream.build_payload({"base_url": "https://api.openai.com/v1", "model": "m", "max_tokens": 50},
                                         {"messages": []})
        self.assertEqual(payload["max_completion_tokens"], 50)
        self.assertNotIn("max_tokens", payload)

    def test_extra_parameters_are_merged_but_routing_fields_are_protected(self):
        payload = upstream.build_payload(
            {"base_url": "http://x/v1", "model": "real", "max_tokens": 0,
             "extra": json.dumps({"reasoning_effort": "low", "model": "evil", "stream": True, "tools": []})},
            {"messages": [], "tools": [1]})
        self.assertEqual((payload["reasoning_effort"], payload["model"], payload["stream"], payload["tools"]),
                         ("low", "real", False, [1]))

    def test_a_refused_parameter_is_fixed_and_retried_once(self):
        self.provider.answers = [
            (400, {"error": {"message": "Unsupported parameter: 'max_tokens' is not supported with this model. "
                                        "Use 'max_completion_tokens' instead."}}),
            "fine"]
        request = chat(1, "A", 2, "B", "hi")
        request["max_tokens"] = 30
        status, answer = self.gateway.handle("smart", request)
        self.assertEqual(status, 200)
        self.assertEqual(len(self.provider.requests), 2)
        self.assertNotIn("max_tokens", self.provider.requests[1]["body"])
        self.assertEqual(self.provider.requests[1]["body"]["max_completion_tokens"], 30)

    def test_a_refused_temperature_is_dropped(self):
        self.provider.answers = [(400, {"error": {"message": "Unsupported value: 'temperature' does not support 0.2"}}), "ok"]
        request = chat(1, "A", 2, "B", "hi")
        request["temperature"] = 0.2
        self.assertEqual(self.gateway.handle("smart", request)[0], 200)
        self.assertNotIn("temperature", self.provider.requests[1]["body"])

    def test_reasoning_effort_is_sent_as_configured_and_fixed_when_a_model_refuses_it(self):
        profile = {"base_url": "https://api.openai.com/v1", "model": "m", "max_tokens": 0, "extra": '{"reasoning_effort":"low"}'}
        self.assertEqual(upstream.build_payload(profile, {"messages": [], "tools": [1]})["reasoning_effort"], "low")

    def test_a_model_that_wants_none_with_tools_is_given_none(self):
        payload = {"reasoning_effort": "low"}
        self.assertTrue(upstream._adjust(payload, "Function tools with reasoning_effort are not supported for gpt-5.4-mini in "
                                                  "/v1/chat/completions. To use function tools, use /v1/responses or set reasoning_effort to 'none'."))
        self.assertEqual(payload["reasoning_effort"], "none")

    def test_a_model_that_refuses_none_is_given_the_lowest_effort_it_lists(self):
        payload = {"reasoning_effort": "none"}
        self.assertTrue(upstream._adjust(payload, "Unsupported value: 'reasoning_effort' does not support 'none' with this model. "
                                                  "Supported values are: 'minimal', 'low', 'medium', and 'high'."))
        self.assertEqual(payload["reasoning_effort"], "minimal")

    def test_a_model_with_no_such_setting_loses_it(self):
        payload = {"reasoning_effort": "low"}
        self.assertTrue(upstream._adjust(payload, "Unrecognized request argument supplied: reasoning_effort"))
        self.assertNotIn("reasoning_effort", payload)

    def test_the_effort_fix_is_learned_and_a_gpt5_style_model_works_end_to_end(self):
        upstream._LEARNED.clear()
        self.store.save_profile("main", profile_fields(self.provider.url, extra='{"reasoning_effort":"none"}'))
        self.provider.answers = [(400, {"error": {"message": "Unsupported value: 'reasoning_effort' does not support 'none' with this "
                                                             "model. Supported values are: 'minimal', 'low', 'medium', and 'high'."}}), "ok", "ok"]
        request = chat(1, "A", 2, "B", "hi")
        self.assertEqual(self.gateway.handle("smart", request)[0], 200)
        self.assertEqual(self.gateway.handle("smart", request)[0], 200)
        efforts = [r["body"].get("reasoning_effort") for r in self.provider.requests]
        self.assertEqual(efforts, ["none", "minimal", "minimal"])              # refused once, then remembered
        upstream._LEARNED.clear()

    def test_a_key_echoed_by_the_provider_is_not_kept(self):
        self.provider.answers = [(401, {"error": {"message": "Incorrect API key provided: sk-proj-AbC123456789xyzWXYZ. "
                                                             "You can find it at https://example.com; Authorization: Bearer sk-live-SECRETSECRET"}})]
        status, answer = self.gateway.handle("smart", chat(1, "A", 2, "B", "hi"))
        self.assertEqual(status, 502)
        kept = answer["error"]["message"] + " " + self.store.recent_errors(0)[0]["error"]
        self.assertNotIn("AbC123456789", kept)
        self.assertNotIn("SECRETSECRET", kept)
        self.assertIn("Incorrect API key provided", kept)

    def test_what_a_model_refused_is_remembered_so_the_next_call_does_not_fail(self):
        upstream._LEARNED.clear()
        self.provider.answers = [(400, {"error": {"message": "Unsupported value: 'temperature' does not support 0.2"}}), "ok", "ok"]
        request = chat(1, "A", 2, "B", "hi")
        request["temperature"] = 0.2
        self.gateway.handle("smart", request)
        self.gateway.handle("smart", request)
        self.assertEqual(len(self.provider.requests), 3)                     # 2 for the first call, 1 (no retry) for the second
        self.assertNotIn("temperature", self.provider.requests[2]["body"])
        upstream._LEARNED.clear()

    def test_other_400s_are_not_retried(self):
        self.provider.answers = [(400, {"error": {"message": "your prompt is bad"}})]
        self.assertEqual(self.gateway.handle("smart", chat(1, "A", 2, "B", "hi"))[0], 502)
        self.assertEqual(len(self.provider.requests), 1)


class SafetyTests(GatewayCase):
    def test_pausing_refuses_everything_without_calling_a_model(self):
        self.store.set_setting("paused", 1)
        status, answer = self.gateway.handle("smart", chat(1, "A", 2, "B", "hi"))
        self.assertEqual((status, answer["error"]["type"]), (503, "paused"))
        self.assertEqual(self.gateway.handle("fast", {"messages": [{"role": "user", "content": "{}"}]})[0], 503)
        self.assertEqual(self.provider.requests, [])

    def test_the_playground_still_works_while_paused_and_forgets_by_default(self):
        self.store.set_setting("paused", 1)
        headers = {"x-mind-playground": "1"}
        self.assertEqual(self.gateway.handle("smart", chat(1, "A", 2, "B", "remember this"), headers)[0], 200)
        self.assertEqual(self.store.memories(1, 2), [])
        headers["x-mind-remember"] = "1"
        self.gateway.handle("smart", chat(1, "A", 2, "B", "remember this"), headers)
        self.assertEqual(len(self.store.memories(1, 2)), 1)

    def test_a_refused_request_writes_nothing(self):
        self.store.set_setting("paused", 1)
        self.gateway.handle("smart", chat(55, "Newcomer", 2, "B", "hi"))
        self.assertIsNone(self.store.persona(55))
        self.assertEqual(self.store.counts()["persona"], 0)

    def test_a_muted_bot_gets_no_model_calls_and_others_do(self):
        self.store.set_muted(1, True, "A")
        status, answer = self.gateway.handle("smart", chat(1, "A", 2, "B", "hi"))
        self.assertEqual((status, answer["error"]["type"]), (503, "muted"))
        self.assertEqual(self.gateway.handle("smart", chat(3, "C", 2, "B", "hi"))[0], 200)
        self.assertEqual(len(self.provider.requests), 1)
        self.store.set_muted(1, False)
        self.assertEqual(self.gateway.handle("smart", chat(1, "A", 2, "B", "hi"))[0], 200)

    def test_muting_survives_a_persona_edit(self):
        self.store.set_muted(1, True, "A")
        self.store.save_persona(1, {"name": "A", "archetype": "x"}, "manual")
        self.assertTrue(self.store.is_muted(1))

    def test_the_global_daily_cap_covers_every_profile(self):
        self.store.save_profile("main", profile_fields(self.provider.url, price_in=10000.0))
        self.store.save_profile("other", profile_fields(self.provider.url, price_in=10000.0))
        self.store.set_setting("daily_cap_usd", 1.5)
        self.assertEqual(self.gateway.handle("smart", chat(1, "A", 2, "B", "one"))[0], 200)       # $1
        self.store.set_lane("smart", "other")
        self.assertEqual(self.gateway.handle("smart", chat(1, "A", 2, "B", "two"))[0], 200)       # $2 in total
        status, answer = self.gateway.handle("smart", chat(1, "A", 2, "B", "three"))
        self.assertEqual((status, answer["error"]["type"]), (429, "daily_cap"))

    def test_smart_replies_are_cleaned_but_fast_lane_json_is_left_alone(self):
        self.provider.answers = ["**Aye**, 😀 friend.\nWelcome.", '{"action": "bot_say", "text": "**hi**"}']
        smart = self.gateway.handle("smart", chat(1, "Brick", 2, "B", "hi"))[1]
        self.assertEqual(smart["choices"][0]["message"]["content"], "Aye, friend. Welcome.")
        fast = self.gateway.handle("fast", {"user": "wow-bot-1", "messages": [{"role": "user", "content": "{}"}]})[1]
        self.assertEqual(fast["choices"][0]["message"]["content"], '{"action": "bot_say", "text": "**hi**"}')

    def test_replies_respect_the_length_and_blocked_word_settings(self):
        self.store.set_setting("max_reply_chars", 60)
        self.store.set_setting("blocked_words", "frak, gorp")
        self.provider.answers = ["Frak that, this is a much longer reply than the limit allows so it must be cut short."]
        text = self.gateway.handle("smart", chat(1, "A", 2, "B", "hi"))[1]["choices"][0]["message"]["content"]
        self.assertTrue(text.startswith("**** that"))
        self.assertLessEqual(len(text), 61)

    def test_the_guard_is_in_the_prompt_and_can_be_switched_off(self):
        self.gateway.handle("smart", chat(1, "A", 2, "B", "hi"))
        self.assertIn("never say you are an AI", self.system_text())
        self.store.set_setting("guard", 0)
        self.gateway.handle("smart", chat(1, "A", 2, "B", "hi again"))
        self.assertNotIn("never say you are an AI", self.system_text())

    def test_a_paused_service_does_not_reflect(self):
        self.store.set_lane("memory", "main")
        self.store.set_setting("paused", 1)
        self.assertIsNone(self.gateway._reflect_call("s", "u"))
        self.assertEqual(self.provider.requests, [])


class TurnLogTests(GatewayCase):
    def test_a_conversation_turn_records_what_was_said_and_what_the_model_saw(self):
        self.store.save_profile("main", profile_fields(self.provider.url, price_in=100.0))
        self.provider.answers = ["hello Ann"]
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "hi Brick"))
        turn = self.store.turns(20014)[0]
        self.assertEqual((turn["said"], turn["reply"], turn["player_name"], turn["lane"], turn["ok"]),
                         ("hi Brick", "hello Ann", "Ann", "smart", 1))
        full = self.store.turn(turn["id"])
        self.assertIn("WHO YOU ARE", full["system_prompt"])
        self.assertIn("WHO YOU ARE", full["mind"])
        self.assertGreater(full["cost_usd"], 0)

    def test_the_tools_offered_to_the_model_are_recorded(self):
        request = chat(1, "A", 2, "B", "invite me")
        request["tools"] = [{"type": "function", "function": {"name": "social"}}, {"type": "function", "function": {"name": "core"}}]
        self.gateway.handle("smart", request)
        self.assertNotIn("tools_offered", self.store.turns(1)[0])         # the list view leaves the bulky fields out ...
        self.assertEqual(self.store.turn(self.store.turns(1)[0]["id"])["tools_offered"], "social,core")

    def test_tool_rounds_are_logged_with_the_tools_asked_for(self):
        self.provider.answers = [{"id": "t", "choices": [{"index": 0, "message": {"role": "assistant", "content": None, "tool_calls": [
            {"id": "c", "type": "function", "function": {"name": "get_inventory", "arguments": "{}"}}]}}]}]
        self.gateway.handle("smart", chat(1, "A", 2, "B", "what is in your bags?"))
        self.assertEqual(self.store.turns(1)[0]["tool_calls"], "get_inventory")

    def test_failures_are_logged_and_fast_ticks_are_not_unless_they_fail(self):
        tick = {"user": "wow-bot-1", "messages": [{"role": "user", "content": "{}"}]}
        self.gateway.handle("fast", tick)
        self.assertEqual(self.store.turns(), [])
        self.provider.answers = [500]
        self.gateway.handle("fast", tick)
        failed = self.store.turns(only_problems=True)
        self.assertEqual((len(failed), failed[0]["lane"]), (1, "fast"))
        self.assertIn("500", failed[0]["error"])

    def test_very_long_lines_are_bounded_in_the_log(self):
        self.provider.answers = ["y" * 5000]
        self.store.set_setting("max_reply_chars", 255)
        self.gateway.handle("smart", chat(1, "A", 2, "B", "x" * 5000))
        turn = self.store.turns(1)[0]
        self.assertLessEqual(len(turn["said"]), 1000)
        self.assertLessEqual(len(turn["reply"]), 2000)

    def test_logging_can_be_switched_off_and_is_capped(self):
        self.store.set_setting("turn_log_keep", 3)
        for index in range(6):
            self.gateway.handle("smart", chat(1, "A", 2, "B", "line %d" % index))
        self.assertEqual([t["said"] for t in self.store.turns(1)], ["line 5", "line 4", "line 3"])
        self.store.set_setting("log_turns", 0)
        self.gateway.handle("smart", chat(1, "A", 2, "B", "unlogged"))
        self.assertEqual(self.store.turns(1)[0]["said"], "line 5")

    def test_a_name_stored_short_is_completed_not_treated_as_a_different_character(self):
        self.store.save_persona(19, {"name": "Zuwe", "archetype": "x"}, "manual")            # what an older parse stored
        self.store.add_memory(19, 5, "Ann", "fact", "Ann owes 5 gold", 0.9)
        self.gateway.handle("smart", chat(19, "Zuwe Bot", 5, "Ann", "hi"))
        self.assertEqual(self.store.persona(19)["name"], "Zuwe Bot")
        self.assertTrue([m for m in self.store.memories(19) if "owes" in m["text"]])         # memory kept

    def test_a_dashboard_tryout_does_not_make_a_bot_look_awake_but_is_counted_in_usage(self):
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "just testing"), {"x-mind-playground": "1"})
        self.assertEqual(self.store.awake(600), [])
        self.assertEqual([row["lane"] for row in self.store.usage_summary(0)], ["playground"])
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "a real player"))
        self.assertEqual([bot["bot_guid"] for bot in self.store.awake(600)], [20014])

    def test_utility_calls_that_name_no_bot_are_not_conversation_turns(self):
        body = {"messages": [{"role": "user", "content": "Reply with the single word: OK"}]}
        self.assertEqual(self.gateway.handle("smart", body, {"x-mind-playground": "1"})[0], 200)
        self.assertEqual(self.store.turns(), [])
        self.provider.answers = [500]
        self.gateway.handle("smart", body, {"x-mind-playground": "1"})
        self.assertEqual(len(self.store.turns(only_problems=True)), 1)          # but a failure is worth seeing

    def test_the_debug_header_describes_what_was_added(self):
        self.gateway.handle("smart", chat(1, "A", 2, "B", "remember I like fishing"))
        status, answer = self.gateway.handle("smart", chat(1, "A", 2, "B", "fishing?"), {"x-mind-debug": "1"})
        self.assertEqual(status, 200)
        self.assertEqual(answer["mind"]["recalled"], 1)
        self.assertIn("WHAT YOU REMEMBER", answer["mind"]["mind_block"])
        self.assertEqual(answer["mind"]["profile"], "main")


class CaptureTests(GatewayCase):
    def test_capture_writes_each_outgoing_request_and_is_off_by_default(self):
        self.assertEqual(self.gateway.capture_path, "")
        self.gateway.handle("smart", chat(1, "A", 2, "B", "hi"))
        path = os.path.join(self.tmp.name, "capture.jsonl")
        self.gateway.capture_path = path
        self.gateway.handle("smart", chat(1, "A", 2, "B", "hello again"))
        self.gateway.handle("smart", chat(1, "A", 2, "B", "playground"), {"x-mind-playground": "1"})
        lines = [json.loads(line) for line in open(path, encoding="utf-8")]
        self.assertEqual(len(lines), 1)                                       # not the playground, not the first
        self.assertEqual((lines[0]["lane"], lines[0]["bot"], lines[0]["player"]), ("smart", "A", "B"))
        self.assertIn("WHO YOU ARE", lines[0]["body"]["messages"][0]["content"])   # what the model actually got


class DashboardFeatureTests(GatewayCase):
    def setUp(self):
        super().setUp()
        self.api, _ = live_api(self)

    def test_the_playground_talks_as_a_real_player_and_shows_what_it_added(self):
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "remember I main a paladin"))
        self.provider.answers = ["your paladin, sure"]
        result = self.api.apply({"op": "chat.try", "guid": 20014, "name": "Brick", "player": "Ann", "text": "what do I main?"})
        self.assertEqual(result["reply"], "your paladin, sure")
        self.assertIn("main a paladin", result["mind"]["mind_block"])
        self.assertEqual(result["mind"]["recalled"], 1)
        self.assertEqual(len(self.store.memories(20014, 77)), 1)        # the try-out was not remembered
        self.assertEqual(self.store.turns(20014)[0]["lane"], "playground")

    def test_the_playground_can_remember_and_can_use_another_model(self):
        self.store.save_profile("big", profile_fields(self.provider.url, model="big-model"))
        self.api.apply({"op": "chat.try", "guid": 20014, "player": "Ann", "text": "I love mining", "remember": True,
                        "profile": "big"})
        self.assertEqual(self.provider.requests[-1]["body"]["model"], "big-model")
        self.assertEqual(len(self.store.memories(20014, 77)), 1)

    def test_the_persona_writer_returns_a_persona_without_saving_it(self):
        self.provider.answers = ['Here you go: {"archetype": "Dwarven brewer", "traits": "jolly, loud, generous", '
                                 '"speech_style": "booming and warm", "interests": "ale, mining", "backstory": "Runs a stall."}']
        result = self.api.apply({"op": "persona.write", "guid": 20014, "hint": "loves beer",
                                 "facts": {"name": "Brick", "class": "Reaper", "level": 42, "zone": "Ironforge"}})
        self.assertEqual(result["persona"]["archetype"], "Dwarven brewer")
        self.assertIn("Reaper", self.provider.requests[-1]["body"]["messages"][1]["content"])
        self.assertIn("loves beer", self.provider.requests[-1]["body"]["messages"][1]["content"])
        self.assertIsNone(self.store.persona(20014))

    def test_the_persona_writer_keeps_the_models_text_whole_and_accepts_list_traits(self):
        long_backstory = "She grew up in a small farming village and never wanted to leave it. " * 8
        self.provider.answers = [json.dumps({"archetype": "Nervous healer", "traits": ["gentle", "anxious", "dutiful"],
                                              "speech_style": "soft and hesitant", "interests": ["herbs", "hymns"],
                                              "backstory": long_backstory})]
        persona = self.api.apply({"op": "persona.write", "guid": 1, "facts": {"name": "Mira"}})["persona"]
        self.assertEqual(persona["traits"], "gentle, anxious, dutiful")
        self.assertEqual(persona["interests"], "herbs, hymns")
        self.assertGreater(len(persona["backstory"]), 250)          # not cut like a chat line

    def test_the_persona_writer_reports_a_useless_answer(self):
        self.provider.answers = ["I would rather not"]
        with self.assertRaises(Exception) as raised:
            self.api.apply({"op": "persona.write", "guid": 1, "facts": {}})
        self.assertIn("try again", str(raised.exception))

    def test_export_and_import_round_trip(self):
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "remember my name is Ann"))
        self.store.save_persona(20014, {"name": "Brick", "archetype": "Dwarf", "backstory": "story"}, "manual")
        document = self.api.export(full=True)
        self.assertEqual(document["personas"][0]["backstory"], "story")
        self.assertEqual(len(document["memories"]), 1)

        self.store.delete_persona(20014)
        self.store.clear_memories(20014)
        result = self.api.apply(dict(document, op="persona.import"))
        self.assertEqual((result["added"], result["memories"]), (1, 1))
        self.assertEqual(self.store.persona(20014)["archetype"], "Dwarf")
        again = self.api.apply(dict(document, op="persona.import"))
        self.assertEqual((again["added"], again["skipped"], again["memories"]), (0, 1, 0))
        self.assertEqual(self.api.apply(dict(document, op="persona.import", overwrite=1))["added"], 1)

    def test_import_resolves_names_and_counts_the_unknown(self):
        result = self.api.apply({"op": "persona.import", "personas": [
            {"name": "Ann", "archetype": "x"}, {"name": "Ghost", "archetype": "y"}, "junk"]})
        self.assertEqual((result["added"], result["unknown"], result["skipped"]), (1, 1, 1))
        self.assertEqual(self.store.persona(77)["name"], "Ann")

    def test_muting_from_the_dashboard(self):
        self.api.apply({"op": "bot.mute", "guid": 20014, "muted": True, "name": "Brick"})
        self.assertTrue(self.api.bot(guid=20014)["muted"])
        self.assertEqual(self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "hi"))[0], 503)

    def test_extra_parameters_are_validated_and_stored_compactly(self):
        good = {"op": "profile.save", "name": "gpt", "base_url": "http://x/v1", "model": "m"}
        self.api.apply(dict(good, extra='{ "reasoning_effort" : "low" }'))
        self.assertEqual(self.store.profile("gpt")["extra"], '{"reasoning_effort":"low"}')
        for bad in ("not json", "[1]", '{"model": "x"}'):
            with self.assertRaises(Exception):
                self.api.apply(dict(good, extra=bad))

    def test_new_settings_are_validated(self):
        self.api.apply({"op": "setting.set", "key": "paused", "value": True})
        self.assertEqual(self.store.setting("paused"), "1")
        self.api.apply({"op": "setting.set", "key": "daily_cap_usd", "value": "2.5"})
        self.assertEqual(self.store.setting("daily_cap_usd"), "2.5")
        for key, value in (("max_reply_chars", 5), ("max_reply_chars", 999), ("daily_cap_usd", -1)):
            with self.assertRaises(Exception):
                self.api.apply({"op": "setting.set", "key": key, "value": value})

    def test_analytics_fills_every_day_and_reports_latency_and_spenders(self):
        self.store.save_profile("main", profile_fields(self.provider.url, price_in=1000.0))
        for guid, name in ((1, "A"), (1, "A"), (3, "C")):
            self.gateway.handle("smart", chat(guid, name, 2, "B", "hi %f" % time.time()))
        report = self.api.analytics(days=7)
        self.assertEqual(len(report["daily"]), 7)
        self.assertEqual(report["daily"][-1]["calls"], 3)
        self.assertEqual(report["total_calls"], 3)
        self.assertGreater(report["total_cost"], 0)
        self.assertEqual(report["by_bot"][0]["bot_guid"], 1)
        self.assertGreaterEqual(report["latency"]["p95"], report["latency"]["p50"])
        self.assertEqual(self.api.analytics(days=999)["days"], 60)

    def test_the_turns_list_filters_by_bot_player_and_problems(self):
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "one"))
        self.gateway.handle("smart", chat(3, "Cog", 88, "Bob", "two"))
        self.assertEqual([t["said"] for t in self.api.turns(bot="Brick")["turns"]], ["one"])
        self.assertEqual(len(self.api.turns()["turns"]), 2)
        self.assertEqual(self.api.turns(player="Ann")["turns"][0]["bot_guid"], 20014)
        self.assertEqual(self.api.turns(problems=True)["turns"], [])
        turn_id = self.api.turns()["turns"][0]["id"]
        self.assertIn("system_prompt", self.api.turn(turn_id))


if __name__ == "__main__":
    unittest.main()
