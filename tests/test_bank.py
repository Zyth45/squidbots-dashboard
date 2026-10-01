import json
import time
import unittest
from unittest import mock

from mind import bank, jev, personas
from tests.support import GatewayCase
from tests.test_ambient import hello


class IntentTests(unittest.TestCase):
    def test_what_was_said_maps_to_situations(self):
        self.assertIn("lfg", bank.intents_of("need a tank for a dungeon"))
        self.assertIn("greeting", bank.intents_of("hello everyone"))
        self.assertEqual(bank.intents_of("zzzz")[-1], "other")

    def test_stock_broadcasts_map_to_idle_situations(self):
        self.assertEqual(bank.situation_for_category("broadcast_looting_x"), "idle_loot")
        self.assertEqual(bank.situation_for_category(""), "")


class FillTests(unittest.TestCase):
    def test_placeholders_are_filled(self):
        self.assertEqual(bank.fill("hey {player}, {zone} sucks", player="Ann", zone="Duskwood"), "hey Ann, Duskwood sucks")

    def test_an_empty_placeholder_is_cut_and_the_gap_closed(self):
        self.assertEqual(bank.fill("hey {player}, hi", player=""), "hey, hi")


class ParseTests(unittest.TestCase):
    def test_bad_lines_are_dropped_not_patched(self):
        text = json.dumps(["nice one", "nice one", "as an AI i cannot", "use {bogus} here", "x", "fine — really", "ok {link}"])
        lines = bank.parse_lines(text, "idle_general")
        self.assertEqual(lines[0], "nice one")
        self.assertNotIn("nice one", lines[1:])
        self.assertFalse(any("bogus" in line or "AI" in line or "{link}" in line or "—" in line for line in lines))

    def test_link_situations_need_exactly_one_link(self):
        lines = bank.parse_lines(json.dumps(["got {link} finally", "no link here"]), "idle_loot")
        self.assertEqual(lines, ["got {link} finally"])

    def test_a_remark_about_my_own_loot_or_level_does_not_address_somebody_else(self):
        loot = bank.parse_lines(json.dumps(["got {link}, finally", "you got {link}! keep going", "nice, {link} at last", "what will you do with {link}?"]),
                                "idle_loot")
        self.assertEqual(loot, ["got {link}, finally", "nice, {link} at last"])
        level = bank.parse_lines(json.dumps(["finally {level}", "grats on {level}!", "you hit {level}, awesome", "{level} at last"]), "idle_levelup")
        self.assertEqual(level, ["finally {level}", "{level} at last"])
        # a quest line may still offer help
        quest = bank.parse_lines(json.dumps(["took {link}, shout if you are stuck"]), "idle_quest")
        self.assertEqual(quest, ["took {link}, shout if you are stuck"])

    def test_lfg_openers_are_reviewed_like_the_other_openers(self):
        self.assertIn("idle_lfg", bank.REVIEWED)
        request = bank.write_request("regular", "idle_lfg", 10)
        self.assertIn("Never point at something only you can see", request["messages"][0]["content"])

    def test_a_combat_call_needs_exactly_one_enemy(self):
        text = json.dumps(["focus the {mob}", "kill it first", "{mob} then {mob}", "get the {mob} down"])
        self.assertEqual(bank.parse_lines(text, "combat_focus"), ["focus the {mob}", "get the {mob} down"])

    def test_a_combat_call_never_claims_a_role_for_the_speaker(self):
        text = json.dumps(["focus {mob} while i heal", "aim for {mob}, I'll heal through!", "my taunt is on {mob}", "get {mob} off the healer",
                           "I'll control {mob} for now", "my sheep is on {mob}",
                           "kill {mob}, tanks have it easy", "burn {mob} down"])
        self.assertEqual(bank.parse_lines(text, "combat_focus"), ["get {mob} off the healer", "kill {mob}, tanks have it easy", "burn {mob} down"])

    def test_no_other_situation_may_name_an_enemy(self):
        self.assertEqual(bank.parse_lines(json.dumps(["kill the {mob}", "fine"]), "idle_general"), ["fine"])

    def test_a_combat_call_is_written_for_party_chat_with_the_enemy_left_blank(self):
        for situation in bank.MOB_SITUATIONS:
            request = bank.write_request("regular", situation, 10)
            self.assertIn("{mob} exactly once", request["messages"][0]["content"])
            self.assertIn("party", request["messages"][1]["content"])

    def test_a_sale_advert_needs_exactly_one_item_and_one_price(self):
        text = json.dumps(["wts {link} for {price}, pm me", "wts {link}, pm me", "wts mats for {price}",
                           "wts {link} {link} for {price}", "wts {link} for {price} {price}"])
        self.assertEqual(bank.parse_lines(text, "idle_sell"), ["wts {link} for {price}, pm me"])

    def test_a_price_is_only_allowed_in_a_sale_advert(self):
        self.assertEqual(bank.parse_lines(json.dumps(["that costs {price}", "fine"]), "idle_general"), ["fine"])

    def test_a_reply_cut_off_mid_array_keeps_the_finished_lines(self):
        self.assertEqual(bank.parse_lines('[\n "first good line",\n "second good line",\n "thi', "idle_general"),
                         ["first good line", "second good line"])

    def test_a_reply_that_is_not_json_is_an_error(self):
        with self.assertRaises(ValueError):
            bank.parse_lines("sure! here are some lines", "idle_general")


    def test_a_line_about_an_objective_is_dropped_unless_a_quest_link_names_it(self):
        text = json.dumps(["anyone know where the next objective is?", "which class heals best early?"])
        self.assertEqual(bank.parse_lines(text, "idle_question"), ["which class heals best early?"])
        self.assertEqual(bank.parse_lines(json.dumps(["took {link}, what does the objective mean?"]), "idle_quest"),
                         ["took {link}, what does the objective mean?"])
        self.assertEqual(bank.parse_lines(json.dumps(["objectively the best zone"]), "idle_general"), ["objectively the best zone"])

    def test_the_writer_is_told_not_to_point_at_what_only_it_can_see(self):
        for situation in ("idle_question", "idle_brag", "idle_topic:quests"):
            system = bank.write_request("regular", situation, 5)["messages"][0]["content"]
            self.assertIn("Never point at something only you can see", system, situation)
        self.assertNotIn("where to find a thing, what to do next", bank.write_request("regular", "idle_question", 5)["messages"][0]["content"])
        self.assertNotIn("Never point at", bank.write_request("regular", "reply_greeting", 5)["messages"][0]["content"])


class ReviewTests(unittest.TestCase):
    def test_the_reviewer_is_shown_numbered_lines_and_asked_for_the_ones_a_stranger_cannot_follow(self):
        request = bank.review_request(["where is the next objective?", "which class heals best?"])
        self.assertIn("1. where is the next objective?", request["messages"][1]["content"])
        self.assertIn("2. which class heals best?", request["messages"][1]["content"])
        self.assertIn("NOT make sense", request["messages"][0]["content"])

    def test_a_verdict_is_read_however_it_is_wrapped_and_nonsense_numbers_are_ignored(self):
        self.assertEqual(bank.unclear('{"confusing": [2, 9, 0, "x"]}', 3), {1})
        self.assertEqual(bank.unclear('Sure:\n```json\n{"confusing": [1]}\n```', 3), {0})
        self.assertEqual(bank.unclear('{"confusing": []}', 3), set())

    def test_a_reply_that_is_not_a_verdict_is_none_so_the_caller_can_tell_it_from_no_flags(self):
        for reply in ("sorry, I cannot", "", None, '{"other": [1]}', '{"confusing": "all"}', "{not json}"):
            self.assertIsNone(bank.unclear(reply, 3), reply)


class BankStoreTests(GatewayCase):
    def test_a_bot_does_not_repeat_itself_and_used_lines_rotate(self):
        b = self.gateway.bank
        b.add_lines("regular", "reply_greeting", ["hey", "yo", "sup"])
        seen = set()
        for _ in range(3):
            rows = b.candidates("regular", ["reply_greeting"], 5, rng=lambda: 0.0)
            self.assertTrue(rows)
            seen.add(rows[0]["text"])
            b.used(5, rows[0]["id"])
        self.assertEqual(seen, {"hey", "yo", "sup"})
        self.assertEqual(b.candidates("regular", ["reply_greeting"], 5), [])
        self.assertTrue(b.candidates("regular", ["reply_greeting"], 6))      # another bot still can

    def test_generation_fills_the_bank_and_survives_a_bad_cell(self):
        b = self.gateway.bank
        calls = []

        def dispatch(profile, request):
            calls.append(profile)
            if len(calls) <= 2:      # the first cell fails, and so does its one retry
                return "not json"
            return json.dumps(["one %d" % len(calls), "two %d" % len(calls)])
        b.start_generation(dispatch, "p", ["regular"], ["idle_general", "reply_greeting"], 5, workers=1)
        for _ in range(200):
            if not b.job["running"]:
                break
            import time
            time.sleep(0.02)
        self.assertEqual(b.job["errors"], 1)
        self.assertEqual(b.job["added"], 2)
        self.assertEqual(b.stats()["total"], 2)

    def generate(self, situation, reviewer):
        """Run one cell whose writer returns three lines and whose reviewer is `reviewer`; returns the calls made."""
        b = self.gateway.bank
        calls = []

        def dispatch(profile, request):
            is_review = request["messages"][0]["content"].startswith("You review")
            calls.append("review" if is_review else "write")
            return reviewer if is_review else json.dumps(["first line here", "the vague one", "third line here"])
        b.start_generation(dispatch, "p", ["regular"], [situation], 5, workers=1)
        for _ in range(200):
            if not b.job["running"]:
                break
            time.sleep(0.02)
        return calls

    def test_opening_lines_a_stranger_could_not_follow_are_reviewed_and_dropped(self):
        calls = self.generate("idle_question", '{"confusing": [2]}')
        self.assertEqual(calls, ["write", "review"])
        b = self.gateway.bank
        self.assertEqual(sorted(b.samples("regular", "idle_question", 10)), ["first line here", "third line here"])
        self.assertEqual((b.job["added"], b.job["dropped"], b.job["unreviewed"]), (2, 1, 0))

    def test_a_review_that_is_not_a_verdict_keeps_the_lines_and_is_counted(self):
        self.generate("idle_general", "sorry, no")
        b = self.gateway.bank
        self.assertEqual((b.job["added"], b.job["dropped"], b.job["unreviewed"], b.job["errors"]), (3, 0, 3, 0))

    def test_replies_are_not_reviewed_because_they_answer_something(self):
        self.assertEqual(self.generate("reply_greeting", '{"confusing": [1, 2, 3]}'), ["write"])
        self.assertEqual(self.gateway.bank.job["added"], 3)


class AmbientBankTests(GatewayCase):
    def setUp(self):
        super().setUp()
        self.gateway.ambient.rng = lambda: 0.0
        self.store.save_persona(20014, dict(personas.generate(20014, "Brick") if hasattr(personas, "generate") else {},
                                            name="Brick", archetype="regular", traits="plain", speech_style="short",
                                            chattiness=100), "manual")

    def test_a_banked_line_answers_without_calling_the_model(self):
        self.gateway.bank.add_lines("regular", "reply_greeting", ["hey {player}"])
        answer = self.gateway.ambient.handle(hello())
        self.assertEqual(answer["text"], "hey Ann")
        self.assertEqual(self.provider.requests, [])
        self.assertEqual(answer["cost_usd"], 0.0)

    def test_an_empty_bank_falls_through_to_the_model(self):
        self.provider.answers.append("model line")
        self.assertEqual(self.gateway.ambient.handle(hello())["text"], "model line")

    def test_the_share_setting_zero_never_uses_the_bank(self):
        self.gateway.bank.add_lines("regular", "reply_greeting", ["hey"])
        self.store.set_setting("bank_share_player", "0")
        self.provider.answers.append("model line")
        self.assertEqual(self.gateway.ambient.handle(hello())["text"], "model line")

    def test_a_link_line_is_not_banked_without_a_link(self):
        self.gateway.bank.add_lines("regular", "idle_loot", ["got {link}"])
        self.provider.answers.append("stock rewritten")
        answer = self.gateway.ambient.handle(hello(mode="rewrite", category="broadcast_looting_x", message="I looted stuff"))
        self.assertEqual(answer["text"], "stock rewritten")

    def test_a_rewrite_puts_the_real_link_in(self):
        self.gateway.bank.add_lines("regular", "idle_loot", ["finally got {link}"])
        link = "|cff0070dd|Hitem:123:0|h[Cool Axe]|h|r"
        answer = self.gateway.ambient.handle(hello(mode="rewrite", category="broadcast_looting_x", message="Got " + link))
        self.assertEqual(answer["text"], "finally got " + link)

    def test_jev_picks_the_line_that_fits_and_can_let_it_pass(self):
        self.gateway.bank.add_lines("regular", "reply_greeting", ["first", "second"])
        self.store.set_setting("bank_picker", "jev")
        def decide(state, questions):
            options = questions["pick"]["criteria"]
            wanted = [key for key, text in options.items() if text == "second"][0]
            return {"pick": {"probabilities": {wanted: 0.9}}, "join": {"noul": 0.9}}
        with mock.patch.object(jev, "available", return_value=True), mock.patch.object(jev, "decide", side_effect=decide):
            self.assertEqual(self.gateway.ambient.handle(hello())["text"], "second")
        quiet = {"pick": {"probabilities": {"1": 0.9}}, "join": {"noul": 0.02}}
        with mock.patch.object(jev, "available", return_value=True), mock.patch.object(jev, "decide", return_value=quiet):
            answer = self.gateway.ambient.handle(hello(scene="other", speaker_is_bot=True, speaker_guid=20099, speaker_name="Nym"))
        self.assertEqual(answer["text"], "")          # another bot's line: this one lets it pass

    def test_when_jev_says_nothing_fits_a_player_gets_the_model(self):
        self.gateway.bank.add_lines("regular", "reply_question", ["dunno"])
        self.store.set_setting("bank_picker", "jev")
        self.provider.answers.append("head east past the mill")
        with mock.patch.object(jev, "available", return_value=True), \
                mock.patch.object(jev, "decide", return_value={"pick": {"probabilities": {"0": 0.9, "1": 0.1}}}):
            answer = self.gateway.ambient.handle(hello(message="where is the mill?"))
        self.assertEqual(answer["text"], "head east past the mill")

    def test_a_player_is_answered_from_the_bank_when_the_model_stays_silent(self):
        self.gateway.bank.add_lines("regular", "reply_greeting", ["hey"])
        self.store.set_setting("bank_share_player", "0")
        self.provider.answers.append("(silent)")
        self.assertEqual(self.gateway.ambient.handle(hello())["text"], "hey")

    def test_a_stock_question_is_rewritten_from_the_banked_openers(self):
        self.gateway.bank.add_lines("regular", "idle_question", ["anyone about?"])
        self.provider.answers.append("model rewrite")
        answer = self.gateway.ambient.handle(hello(mode="rewrite", category="suggest_faction", message="Where to?"))
        self.assertEqual(answer["text"], "anyone about?")

    def test_a_reply_prefers_lines_about_what_is_being_discussed(self):
        self.gateway.bank.add_lines("regular", "reply_topic:mining", ["copper again, every single time"])
        self.gateway.bank.add_lines("regular", "reply_other", ["fair enough"])
        answer = self.gateway.ambient.handle(hello(speaker_is_bot=True, depth=2, message="copper prices are brutal today"))
        self.assertEqual(answer["text"], "copper again, every single time")

    def test_a_players_question_is_written_by_the_model_not_taken_from_the_bank(self):
        self.gateway.bank.add_lines("regular", "reply_question", ["no idea, sorry"])
        self.provider.answers.append("try the mine east of town")
        answer = self.gateway.ambient.handle(hello(message="anyone know where the best copper ore is?"))
        self.assertEqual(answer["text"], "try the mine east of town")
        self.assertIn("THE SUBJECT", self.provider.requests[0]["body"]["messages"][0]["content"])

    def test_a_hello_from_a_player_is_still_answered_from_the_bank(self):
        self.gateway.bank.add_lines("regular", "reply_greeting", ["hey, how is it going"])
        self.assertEqual(self.gateway.ambient.handle(hello(message="hey all"))["text"], "hey, how is it going")

    def test_a_bots_answer_is_written_while_a_player_is_in_the_talk_and_banked_once_it_is_deep_or_nobody_is(self):
        self.gateway.bank.add_lines("regular", "reply_other", ["fair enough", "yeah fair point"])
        self.provider.answers.append("copper is the worst, i keep missing nodes")
        self.gateway.ambient.handle(hello(message="i keep missing copper nodes", scene="0:1:say"))
        near = self.gateway.ambient.handle(hello(speaker_is_bot=True, speaker_name="Nia", depth=2, message="same here",
                                                 scene="0:1:say"))
        self.assertNotIn(near["text"], ("fair enough", "yeah fair point"))
        deep = self.gateway.ambient.handle(hello(speaker_is_bot=True, speaker_name="Nia", depth=4, message="same here",
                                                 scene="0:1:say"))
        self.assertIn(deep["text"], ("fair enough", "yeah fair point"))
        alone = self.gateway.ambient.handle(hello(speaker_is_bot=True, speaker_name="Nia", depth=2, message="same here",
                                                  scene="0:9:say"))
        self.assertIn(alone["text"], ("fair enough", "yeah fair point"))

    def test_the_topic_of_a_conversation_is_remembered_for_the_next_line(self):
        self.gateway.bank.add_lines("regular", "reply_topic:fishing", ["my bobber has a mind of its own"])
        self.gateway.bank.add_lines("regular", "reply_other", ["fair enough"])
        self.gateway.ambient.topics["zone:1"] = ("fishing", time.time())
        self.assertEqual(self.gateway.ambient._topic_here("zone:1", ["lol same"]), "fishing")
        self.assertEqual(self.gateway.ambient._topic_here("zone:2", ["lol same"]), "")

    def test_a_jev_failure_falls_back_to_the_local_pick(self):
        self.gateway.bank.add_lines("regular", "reply_greeting", ["only line"])
        self.store.set_setting("bank_picker", "jev")
        with mock.patch.object(jev, "available", return_value=True), \
                mock.patch.object(jev, "decide", side_effect=jev.JevError("down")):
            self.assertEqual(self.gateway.ambient.handle(hello())["text"], "only line")


class StartTests(GatewayCase):
    def setUp(self):
        super().setUp()
        self.gateway.ambient.rng = lambda: 0.0
        self.store.save_persona(20014, {"name": "Brick", "archetype": "regular", "traits": "plain", "speech_style": "short",
                                        "chattiness": 100}, "manual")

    def start(self, **extra):
        return self.gateway.ambient.handle(dict({"mode": "start", "bot_guid": 20014, "bot_name": "Brick", "channel": "zone",
                                                 "zone": "Elwynn Forest", "level": 20, "class": "Mage"}, **extra))

    def test_a_bot_opens_with_a_banked_line_and_never_calls_the_model(self):
        self.gateway.bank.add_lines("regular", "idle_general", ["{zone} again"])
        answer = self.start()
        self.assertEqual(answer["text"], "Elwynn Forest again")
        self.assertEqual(self.provider.requests, [])

    def test_an_empty_bank_means_silence_not_a_model_call(self):
        self.assertEqual(self.start()["text"], "")
        self.assertEqual(self.provider.requests, [])

    def test_a_channel_with_no_topics_is_silent(self):
        self.gateway.bank.add_lines("regular", "idle_general", ["hm"])
        self.assertEqual(self.start(channel="officer")["text"], "")

    LISTING = {"link": "|cff1eff00|Hitem:2589:0:0:0:0:0:0:0:0|h[Linen Cloth]|h|r x20", "price": "2g 50s"}

    def test_a_trade_advert_names_what_the_bot_really_has_and_its_price(self):
        self.gateway.bank.add_lines("regular", "idle_sell", ["wts {link} for {price}, pm me"])
        text = self.start(channel="trade", listing=self.LISTING)["text"]
        self.assertIn("[Linen Cloth]", text)
        self.assertIn("for 2g 50s, pm me", text)
        self.assertEqual(self.provider.requests, [])

    def test_a_bot_with_nothing_to_sell_does_not_advertise(self):
        self.gateway.bank.add_lines("regular", "idle_sell", ["wts {link} for {price}, pm me"])
        self.gateway.bank.add_lines("regular", "idle_trade", ["wts bags and mats, pm me"])
        self.assertEqual(self.start(channel="trade")["text"], "")


class CombatCalloutTests(GatewayCase):
    def setUp(self):
        super().setUp()
        self.gateway.ambient.rng = lambda: 0.0
        self.store.save_persona(20014, {"name": "Brick", "archetype": "regular", "traits": "plain", "speech_style": "short",
                                        "chattiness": 100}, "manual")

    def call(self, **extra):
        return self.gateway.ambient.handle(dict({"mode": "combat", "bot_guid": 20014, "bot_name": "Brick", "kind": "focus",
                                                 "mob": "Defias Conjurer"}, **extra))

    def test_a_bot_calls_the_target_in_its_own_words_without_a_model_call(self):
        self.gateway.bank.add_lines("regular", "combat_focus", ["get the {mob} down first"])
        answer = self.call()
        self.assertEqual(answer["text"], "get the Defias Conjurer down first")
        self.assertEqual(answer["source"], "bank")
        self.assertEqual(self.provider.requests, [])

    def test_crowd_control_lines_are_kept_apart_from_focus_lines(self):
        self.gateway.bank.add_lines("regular", "combat_focus", ["kill the {mob}"])
        self.gateway.bank.add_lines("regular", "combat_cc", ["leave the {mob} be"])
        self.assertEqual(self.call(kind="cc")["text"], "leave the Defias Conjurer be")

    def test_an_empty_bank_is_silence_so_the_game_says_its_own_line(self):
        self.assertEqual(self.call()["text"], "")
        self.assertEqual(self.provider.requests, [])

    def test_a_request_without_a_kind_or_an_enemy_is_refused(self):
        self.gateway.bank.add_lines("regular", "combat_focus", ["kill the {mob}"])
        self.assertEqual(self.call(kind="dance")["text"], "")
        self.assertEqual(self.call(mob="")["text"], "")
        self.assertEqual(self.call(bot_guid=0)["text"], "")

    def test_an_enemy_name_cannot_carry_a_placeholder_into_the_line(self):
        self.gateway.bank.add_lines("regular", "combat_focus", ["kill the {mob}"])
        self.assertEqual(self.call(mob="{player}")["text"], "")

    def test_a_muted_bot_stays_quiet_and_so_does_a_paused_service(self):
        self.gateway.bank.add_lines("regular", "combat_focus", ["kill the {mob}"])
        self.store.set_muted(20014, True)
        self.assertEqual(self.call()["text"], "")
        self.store.set_muted(20014, False)
        self.assertEqual(self.call()["text"], "kill the Defias Conjurer")
        self.store.set_setting("paused", "1")
        self.assertEqual(self.call()["text"], "")


if __name__ == "__main__":
    unittest.main()


class TopicTests(unittest.TestCase):
    def test_the_topic_is_the_subject_of_the_recent_lines(self):
        self.assertEqual(bank.topic_of(["anyone know where to find tin ore?"]), "mining")
        self.assertEqual(bank.topic_of(["lol", "so much lag today"]), "lag")
        self.assertEqual(bank.topic_of(["hello", "hi"]), "")

    def test_newer_lines_outweigh_older_ones(self):
        self.assertEqual(bank.topic_of(["fishing is so dull", "ugh the lag", "yeah the lag is brutal"]), "lag")

    def test_topic_situations_are_validated_by_their_topic(self):
        self.assertTrue(bank.valid_situation("reply_topic:mining"))
        self.assertFalse(bank.valid_situation("reply_topic:nonsense"))
        self.assertFalse(bank.valid_situation("idle_general:mining"))
        self.assertEqual(bank.base_situation("idle_topic:lag"), "idle_topic")

    def test_every_topic_writes_a_request_for_both_kinds(self):
        for topic in bank.TOPICS:
            for base in bank.TOPIC_SITUATIONS:
                text = bank.write_request("regular", "%s:%s" % (base, topic), 10)["messages"][1]["content"]
                self.assertIn(bank.TOPICS[topic][1], text)
