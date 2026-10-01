import http.client
import json
import unittest

from mind import server
from mind.ambient import CUT_CHARS
from tests.support import GatewayCase, profile_fields


def hello(**overrides):
    request = {"bot_guid": 20014, "bot_name": "Brick", "level": 22, "class": "Warrior", "race": "Dwarf",
               "zone": "Loch Modan", "area": "Thelsamar", "speaker_guid": 77, "speaker_name": "Ann",
               "speaker_is_bot": False, "channel": "say", "message": "hi everyone!", "scene": "0:1:say"}
    request.update(overrides)
    return request


class AmbientTests(GatewayCase):
    def setUp(self):
        super().setUp()
        self.gateway.ambient.rng = lambda: 0.0      # nobody is too quiet to answer unless a test says so

    def user_text(self, index=-1):
        return self.provider.requests[index]["body"]["messages"][1]["content"]

    def test_a_bot_answers_a_hello_in_its_own_voice_without_tools(self):
        self.store.save_persona(20014, {"name": "Brick", "archetype": "Dwarf tavern-keeper", "traits": "gruff",
                                        "speech_style": "growls short sentences", "backstory": "Lost a bet."}, "manual")
        self.provider.answers.append("Aye, evenin' Ann.")
        answer = self.gateway.ambient.handle(hello())
        self.assertEqual(answer["text"], "Aye, evenin' Ann.")
        sent = self.provider.requests[0]["body"]
        system = sent["messages"][0]["content"]
        self.assertIn("growls short sentences", system)
        self.assertIn("level 22 Dwarf Warrior", system)
        self.assertIn("Thelsamar, in Loch Modan", system)
        self.assertIn("/say", system)
        self.assertNotIn("do it with your tools", system)          # a chat line, not an order
        self.assertNotIn("tools", sent)
        self.assertIn("[Ann] hi everyone!", self.user_text())

    def test_a_bot_sees_what_the_others_already_said_and_the_replies_are_kept_for_the_next_bot(self):
        self.provider.answers.extend(["hey Ann!", "morning all"])
        self.gateway.ambient.handle(hello())
        self.gateway.ambient.handle(hello(bot_guid=20015, bot_name="Nym"))
        second = self.user_text()
        self.assertIn("[Ann] hi everyone!", second)
        self.assertIn("[Brick] hey Ann!", second)
        self.assertEqual(second.count("[Ann] hi everyone!"), 1)     # one player line, however many bots heard it

    def test_a_bot_answering_a_bot_is_not_told_the_line_twice(self):
        self.provider.answers.extend(["hey Ann!", "lol yes"])
        self.gateway.ambient.handle(hello())
        # The module then offers Brick's own line to the next bot.
        self.gateway.ambient.handle(hello(bot_guid=20015, bot_name="Nym", speaker_guid=20014, speaker_name="Brick",
                                          speaker_is_bot=True, message="hey Ann!", depth=2))
        self.assertEqual(self.user_text().count("hey Ann!"), 1)

    def chained(self, message, **overrides):
        """Nym is offered Brick's line, in the place where Ann (a player) spoke to begin with."""
        return self.gateway.ambient.handle(hello(bot_guid=20015, bot_name="Nym", speaker_guid=20014, speaker_name="Brick",
                                                 speaker_is_bot=True, message=message, depth=2, **overrides))

    def test_a_bot_answering_a_bot_is_told_the_talk_is_with_the_player_who_started_it(self):
        self.provider.answers.extend(["level 5 here, deadmines is a hike", "21 and in"])
        self.gateway.ambient.handle(hello(message="Deadmines tonight? I'm 20, what are you lot?"))
        self.chained("level 5 here, deadmines is a hike")
        asked = self.user_text()
        self.assertIn("this chat is with Ann, a real player", asked)
        self.assertIn("Deadmines tonight? I'm 20, what are you lot?", asked)
        self.assertIn("answer what they asked for yourself", asked)
        self.assertNotIn("Answer THEM directly", asked)

    def test_a_bot_is_told_not_to_ask_a_second_question_when_the_last_line_was_one(self):
        self.provider.answers.extend(["sure, which dungeon?", "same", "ok"])
        self.gateway.ambient.handle(hello(message="anyone up for a dungeon?"))
        self.chained("sure, which dungeon?")
        self.assertIn("do not ask another", self.user_text())
        self.chained("sounds good to me")
        self.assertNotIn("do not ask another", self.user_text())

    def test_a_bot_that_already_answered_the_player_is_told_not_to_answer_again(self):
        self.provider.answers.extend(["hunter is a comfy start, pet does the work", "agreed, what do you enjoy playing?", "same here"])
        self.gateway.ambient.handle(hello(bot_guid=20015, bot_name="Nym", message="best class for a newcomer?"))
        self.chained("healers are always wanted too")
        asked = self.user_text()
        self.assertIn('You already answered Ann ("hunter is a comfy start, pet does the work")', asked)
        self.assertIn("answer exactly (silent)", asked)
        # Another bot has said nothing yet, so it is not told that.
        self.gateway.ambient.handle(hello(bot_guid=20016, bot_name="Pim", speaker_guid=20014, speaker_name="Brick",
                                          speaker_is_bot=True, message="healers are always wanted too", depth=2))
        self.assertNotIn("already answered", self.user_text())

    def test_with_no_player_in_the_talk_a_bot_just_answers_the_bot_before_it(self):
        self.provider.answers.append("lol yes")
        self.chained("nice weather")
        self.assertIn("The line you are answering is the last one, from Brick. Answer THEM directly.", self.user_text())

    def test_a_players_line_from_long_ago_is_not_the_talk_any_more(self):
        self.provider.answers.extend(["hey Ann!", "lol yes"])
        self.gateway.ambient.handle(hello())
        self.gateway.ambient.player_at["0:1:say"] -= self.gateway.ambient.PLAYER_LIVE_S + 1
        self.chained("hey Ann!")
        self.assertNotIn("a real player", self.user_text())

    def test_bots_that_ask_at_the_same_moment_answer_one_at_a_time_and_the_second_sees_the_first(self):
        import threading
        self.provider.answers.extend(["which quest?", "the one in the north?"])
        results = []
        threads = [threading.Thread(target=lambda guid=guid: results.append(self.gateway.ambient.handle(hello(bot_guid=guid, bot_name="Bot%d" % guid))))
                   for guid in (20014, 20015)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(20)
        self.assertEqual(len(results), 2)
        later = self.provider.requests[1]["body"]["messages"][1]["content"]
        self.assertIn("which quest?", later)

    def test_the_prompt_asks_for_real_player_banter_and_carries_the_bots_opinions(self):
        self.store.save_persona(20014, {"name": "Brick", "archetype": "troll", "traits": "sarcastic",
                                        "speech_style": "lowercase, roasts people", "opinions": "gnomes are the best race",
                                        "chattiness": 90}, "manual")
        self.provider.answers.append("lol nice try gnome hater")
        self.gateway.ambient.handle(hello())
        system = self.provider.requests[0]["body"]["messages"][0]["content"]
        self.assertIn("THE VIBE", system)
        self.assertIn("Be a decent person to talk to", system)
        self.assertIn("Never use slurs", system)
        self.assertIn("gnomes are the best race", system)
        self.assertIn("You are chatty", system)

    def test_a_line_answering_a_player_is_never_told_to_snap_at_them(self):
        from mind import ambient
        rude = {text for name, _, text in ambient.REGISTERS if name in ("rude", "gripe", "aside")}
        for archetype in ("regular", "friendly helper", "chill"):
            for step in range(200):
                draw = (step + 0.5) / 200
                self.assertNotIn(ambient.register({"archetype": archetype}, lambda draw=draw: draw, player=True), rude)

    def test_the_vibe_can_be_rewritten_from_the_dashboard(self):
        self.store.set_setting("ambient_vibe", "Everyone here is unfailingly polite and formal.")
        self.provider.answers.append("Good evening.")
        self.gateway.ambient.handle(hello())
        system = self.provider.requests[0]["body"]["messages"][0]["content"]
        self.assertIn("unfailingly polite and formal", system)
        self.assertNotIn("decent person to talk to", system)

    def test_a_quiet_bot_usually_lets_another_bots_line_go_by_and_costs_nothing(self):
        self.store.save_persona(20014, {"name": "Brick", "archetype": "lurker", "chattiness": 5}, "manual")
        self.gateway.ambient.rng = lambda: 0.9
        answer = self.gateway.ambient.handle(hello(speaker_is_bot=True, speaker_guid=20099, speaker_name="Nym"))
        self.assertEqual((answer["text"], answer["reason"]), ("", "quiet"))
        self.assertEqual(self.provider.requests, [])

    def test_a_player_who_speaks_is_answered_even_by_a_quiet_bot(self):
        self.store.save_persona(20014, {"name": "Brick", "archetype": "lurker", "chattiness": 0}, "manual")
        self.gateway.ambient.rng = lambda: 0.99
        self.provider.answers.append("hey")
        self.assertEqual(self.gateway.ambient.handle(hello())["text"], "hey")

    def test_a_chatty_bot_nearly_always_joins_in(self):
        self.store.save_persona(20014, {"name": "Brick", "archetype": "banter merchant", "chattiness": 95}, "manual")
        self.gateway.ambient.rng = lambda: 0.9
        self.provider.answers.append("haha yes")
        self.assertEqual(self.gateway.ambient.handle(hello())["text"], "haha yes")

    def test_a_bot_can_choose_to_stay_silent(self):
        for reply in ("(silent)", "(Silent)", "silent", ""):
            self.provider.answers.append(reply)
            self.assertEqual(self.gateway.ambient.handle(hello())["text"], "")

    def test_the_line_is_cleaned_and_kept_short(self):
        self.provider.answers.append('"**Brick:** hello there \U0001F600 ' + "and so on " * 30 + '"')
        text = self.gateway.ambient.handle(hello())["text"]
        self.assertLessEqual(len(text), CUT_CHARS + 1)
        self.assertNotIn("**", text)
        self.assertNotIn("\U0001F600", text)
        self.assertFalse(text.startswith('"'))

    def test_a_line_a_little_over_the_asked_length_is_said_whole_and_not_cut_mid_sentence(self):
        line = "Welcome, John! Glad you're here. Every group needs a tank and a questionable plan, so you're already among the best."
        self.assertGreater(len(line), 110)      # 110 is what the model is asked for, 160 what is let through
        self.provider.answers.append(line)
        self.assertEqual(self.gateway.ambient.handle(hello())["text"], line)

    def test_a_line_far_over_is_shortened_to_a_whole_sentence_not_an_ellipsis(self):
        self.provider.answers.append("Ann, good to see you. " + "And then I went on about the weather for a very long time. " * 6)
        text = self.gateway.ambient.handle(hello())["text"]
        self.assertTrue(text.endswith("time."), text)
        self.assertLessEqual(len(text), CUT_CHARS)

    def test_a_paused_service_muted_bot_or_missing_model_says_nothing_and_calls_nothing(self):
        self.store.set_setting("paused", "1")
        self.assertEqual(self.gateway.ambient.handle(hello())["text"], "")
        self.store.set_setting("paused", "0")
        self.store.set_muted(20014, True)
        self.assertEqual(self.gateway.ambient.handle(hello())["text"], "")
        self.store.set_muted(20014, False)
        self.store.set_lane("fast", "")
        self.assertIn("no model", self.gateway.ambient.handle(hello())["reason"])
        self.assertEqual(self.provider.requests, [])

    def test_the_ambient_lane_can_have_its_own_model_and_falls_back_to_quick_decisions(self):
        self.provider.answers.append("hello")
        self.gateway.ambient.handle(hello())
        self.assertEqual(self.provider.requests[-1]["body"]["model"], "test-model")
        self.store.save_profile("chatty", profile_fields(self.provider.url, model="chatty-model"))
        self.store.set_lane("ambient", "chatty")
        self.gateway.ambient.handle(hello())
        self.assertEqual(self.provider.requests[-1]["body"]["model"], "chatty-model")

    def test_it_is_logged_as_its_own_lane_with_the_cost(self):
        self.provider.answers.append("hello")
        self.gateway.ambient.handle(hello())
        with self.store.conn() as db:
            row = db.execute("SELECT lane FROM call_log ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual(row["lane"], "ambient")

    def test_a_request_without_a_bot_or_a_message_is_refused_politely(self):
        self.assertEqual(self.gateway.ambient.handle({"message": "hi"})["text"], "")
        self.assertEqual(self.gateway.ambient.handle({"bot_guid": 5})["text"], "")
        self.assertEqual(self.gateway.ambient.handle({"bot_guid": "abc", "message": "x"})["text"], "")

    def test_the_http_route_answers_json_and_never_a_stack_trace(self):
        import http.server
        import threading
        http_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(self.gateway, ""))
        http_server.daemon_threads = True
        threading.Thread(target=http_server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
        self.addCleanup(http_server.server_close)
        self.addCleanup(http_server.shutdown)
        self.provider.answers.append("hi Ann")
        connection = http.client.HTTPConnection("127.0.0.1", http_server.server_address[1], timeout=10)
        connection.request("POST", "/ambient", json.dumps(hello()), {"Content-Type": "application/json"})
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.read())["text"], "hi Ann")
        connection.request("POST", "/ambient", "not json", {"Content-Type": "application/json"})
        self.assertEqual(connection.getresponse().status, 400)


LINK = "|cff9d9d9d|Hitem:2881:0:0:0:0:0:0:0|h[Runed Copper Breastplate]|h|r"


def stock(**overrides):
    request = hello(mode="rewrite", speaker_guid=20014, speaker_name="Brick", speaker_is_bot=True,
                    message="Why do I keep getting %s... did I anger RNG?" % LINK, category="broadcast_looting_item_poor")
    request.update(overrides)
    return request


class RewriteTests(GatewayCase):
    def setUp(self):
        super().setUp()
        self.gateway.ambient.rng = lambda: 0.999    # a rewrite is never held back for being quiet
    def test_a_stock_line_is_put_in_the_bots_own_voice_and_the_link_comes_back_where_the_model_put_it(self):
        self.store.save_persona(20014, {"name": "Brick", "archetype": "Dwarf tavern-keeper", "speech_style": "growls"}, "manual")
        self.provider.answers.append("Grey junk again: [[1]]. Typical.")
        answer = self.gateway.ambient.handle(stock())
        self.assertEqual(answer["text"], "Grey junk again: %s. Typical." % LINK)
        system = self.provider.requests[0]["body"]["messages"][0]["content"]
        self.assertIn("growls", system)
        self.assertIn("you looted a worthless grey item", system)
        self.assertIn("did I anger RNG", system)                    # the stock line, to be paraphrased
        self.assertIn("[[1]]", system)                              # the link is a placeholder the model cannot mangle
        self.assertNotIn("|Hitem", system)
        self.assertIn('[[1]] is "Runed Copper Breastplate"', system)
        self.assertNotIn("Recent chat here", self.provider.requests[0]["body"]["messages"][1]["content"])

    def test_a_rewrite_that_loses_repeats_or_invents_a_link_is_dropped_so_the_stock_line_goes_out(self):
        self.provider.answers.extend(["ugh, grey junk again", "[[1]] and [[1]]", "[[1]] then [[2]]", "raw |cff9d9d9d|Hitem:1:0:0:0:0:0:0:0|h[Other]|h|r"])
        for _ in range(4):
            answer = self.gateway.ambient.handle(stock())
            self.assertEqual(answer["text"], "")
            self.assertEqual(answer["reason"], "links changed")

    def test_a_line_with_two_links_gets_both_back(self):
        two = "Working on %s for %s" % (LINK, LINK.replace("2881", "9").replace("Runed Copper Breastplate", "Cycle of Rebirth"))
        self.provider.answers.append("[[2]] again, so [[1]] it is.")
        text = self.gateway.ambient.handle(stock(message=two))["text"]
        self.assertTrue(text.startswith("|cff9d9d9d|Hitem:9:"))
        self.assertIn("Hitem:2881", text)

    def test_a_rewrite_may_be_longer_than_a_chat_reply_but_not_endless(self):
        self.provider.answers.append(("word " * 80).strip())
        text = self.gateway.ambient.handle(stock(message="Just grabbed something, wow"))["text"]
        self.assertLessEqual(len(text), 171)
        self.assertGreater(len(text), 111)

    def test_only_the_rewritten_line_joins_the_conversation_log_for_the_bots_that_answer_it(self):
        self.provider.answers.append("grey junk again")
        self.gateway.ambient.handle(stock(message="Why do I keep getting junk", category="x"))
        self.assertEqual([(who, text) for _, who, text in self.gateway.ambient.recent("0:1:say")], [("Brick", "grey junk again")])


if __name__ == "__main__":
    unittest.main()
