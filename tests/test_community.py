import json
import time
import unittest

from mind import community
from tests.support import GatewayCase
from tests.test_ambient import hello


def realm(count=40, guild=5):
    """Bots 1000.. around: even ones are team 0, odd team 1; the first dozen even ones are in one guild."""
    return [{"guid": 1000 + index, "name": "Nia%d Bot" % index, "team": index % 2,
             "guild_id": guild if index < 24 and index % 2 == 0 else 0, "level": 20, "class": "Mage"} for index in range(count)]


def sheets_for(guids):
    return json.dumps([{"guid": guid, "traits": "easygoing, nosy, loyal", "speech_style": "lowercase, short lines",
                        "interests": "fishing, alts", "backstory": "Plays every night. Always late.",
                        "opinions": "fishing is underrated"} for guid in guids])


class CastTests(GatewayCase):
    def wait(self):
        for _ in range(200):
            if not self.gateway.community.job["running"]:
                return
            time.sleep(0.02)
        self.fail("the cast job never finished")

    def sync(self, **extra):
        return self.gateway.community.command(dict({"op": "sync", "candidates": realm(), "homes": [5], "size": 12}, **extra))

    def test_the_cast_is_the_guildmates_first_and_has_both_factions(self):
        answer = self.sync()
        self.wait()
        guids = {member["guid"] for member in answer["cast"]}
        self.assertEqual(len(guids), 12)
        self.assertGreaterEqual(len([m for m in answer["cast"] if m["guild_id"] == 5]), 8)      # 65% of 12, rounded up
        self.assertEqual({member["team"] for member in answer["cast"]}, {0, 1})

    def test_a_regular_stays_a_regular(self):
        first = {member["guid"] for member in self.sync()["cast"]}
        self.wait()
        second = {member["guid"] for member in self.sync()["cast"]}
        self.wait()
        self.assertEqual(first, second)

    def test_newcomers_get_character_sheets_and_friends(self):
        self.provider.answers.append(sheets_for(range(1000, 1012)))      # the cast is written ten at a time
        self.provider.answers.append(sheets_for(range(1000, 1012)))
        self.provider.answers.append(json.dumps([{"a": 1000, "b": 1002, "kind": "old guildmates", "note": "lost a raid together"},
                                                 {"a": 1000, "b": 9999, "kind": "friends", "note": "not in the cast"}]))
        self.store.set_lane("ambient", "main")
        answer = self.sync()
        self.wait()
        self.assertEqual(answer["added"], 12)
        persona = self.store.persona(answer["cast"][0]["guid"])
        self.assertEqual(persona["source"], "cast")
        self.assertIn("lowercase", persona["speech_style"])
        bonds = self.store.bonds()
        self.assertEqual({(b["a"], b["b"]) for b in bonds}, {(1000, 1002), (1002, 1000)})
        self.assertEqual(self.gateway.community.bond(1002, 1000)["note"], "lost a raid together")

    def test_someone_who_knows_the_player_ranks_first(self):
        self.store.note_seen(1004, 1468, "John")
        self.store.note_seen(1004, 1468, "John")
        self.store.set_affinity(1004, 1468, 0.6, "helped with a quest")
        ranked = self.gateway.community.command({"op": "rank", "player_guid": 1468, "candidates": [1000, 1002, 1004]})
        self.assertEqual(ranked["order"][0], 1004)
        self.assertEqual(ranked["known"], [1004])


class ChatTests(GatewayCase):
    def setUp(self):
        super().setUp()
        self.store.set_lane("ambient", "main")
        self.gateway.ambient.rng = lambda: 0.0
        self.store.save_persona(20014, {"name": "Brick", "archetype": "regular", "traits": "plain", "speech_style": "short",
                                        "chattiness": 100}, "manual")

    def test_a_line_spoken_to_a_bot_by_name_is_written_not_banked(self):
        self.gateway.bank.add_lines("regular", "reply_greeting", ["hey all"])
        self.provider.answers.append("pretty good, you?")
        answer = self.gateway.ambient.handle(hello(message="hey", addressed=True))
        self.assertEqual(answer["text"], "pretty good, you?")
        self.assertIn("talking to you directly", self.provider.requests[0]["body"]["messages"][1]["content"])

    def test_a_friend_is_answered_by_name_with_a_friend_line(self):
        self.store.add_bond(20014, 20015, "friends", "fish together")
        self.gateway.bank.add_lines("regular", "reply_friend", ["{friend}, you never change"])
        answer = self.gateway.ambient.handle(hello(speaker_is_bot=True, speaker_guid=20015, speaker_name="Kell Bot",
                                                   message="again with the fishing", depth=5, scene="0:1:say"))
        self.assertEqual(answer["text"], "Kell, you never change")

    def test_the_prompt_says_how_the_two_know_each_other(self):
        self.store.add_bond(20014, 20015, "rivals", "argue over tin")
        self.provider.answers.append("not this again")
        self.gateway.ambient.player_at["0:1:say"] = time.time()      # someone is in the talk, so this one is written
        self.gateway.ambient.handle(hello(speaker_is_bot=True, speaker_guid=20015, speaker_name="Kell Bot",
                                          message="tin again", depth=2, scene="0:1:say"))
        system = self.provider.requests[0]["body"]["messages"][0]["content"]
        self.assertIn("Kell and you are rivals: argue over tin", system)

    def test_a_regular_opens_to_a_friend_by_name_and_the_friend_is_asked_to_answer(self):
        self.gateway.bank.add_lines("regular", "idle_friend", ["{friend}, you alive?"])
        answer = self.gateway.ambient.handle({"mode": "start", "bot_guid": 20014, "bot_name": "Brick", "channel": "world",
                                              "friends": [{"guid": 20015, "name": "Kell Bot"}]})
        self.assertEqual(answer["text"], "Kell, you alive?")
        self.assertEqual(answer["addressed_guid"], 20015)

    def test_a_guild_channel_has_openers_too(self):
        self.gateway.bank.add_lines("regular", "idle_general", ["quiet night in here"])
        answer = self.gateway.ambient.handle({"mode": "start", "bot_guid": 20014, "bot_name": "Brick", "channel": "guild"})
        self.assertEqual(answer["text"], "quiet night in here")

    def test_a_regular_welcomes_a_player_back_by_name_remembering_them(self):
        self.store.add_memory(20014, 1468, "John", "fact", "John is hunting for a staff", 0.8)
        self.store.note_seen(20014, 1468, "John")
        self.provider.answers.append("John! found that staff yet?")
        answer = self.gateway.ambient.handle({"mode": "welcome", "bot_guid": 20014, "bot_name": "Brick", "player_guid": 1468,
                                              "player_name": "John", "channel": "guild"})
        self.assertEqual(answer["text"], "John! found that staff yet?")
        system = self.provider.requests[0]["body"]["messages"][0]["content"]
        self.assertIn("John has just logged in", system)
        self.assertIn("hunting for a staff", system)
        self.assertIn("guild chat", system)

    def test_a_welcome_that_runs_on_is_cut_to_a_whole_sentence_not_left_hanging(self):
        self.provider.answers.append("Welcome, John! Glad you're here. Every group needs a tank and a questionable plan, so you're "
                                     "already among the best and the most entertaining people we have had in this guild for a while.")
        answer = self.gateway.ambient.handle({"mode": "welcome", "bot_guid": 20014, "bot_name": "Brick", "player_guid": 1468,
                                              "player_name": "John", "channel": "guild", "joined": True})
        self.assertTrue(answer["text"].endswith((".", "!", "?")), answer["text"])
        self.assertNotIn("...", answer["text"])


if __name__ == "__main__":
    unittest.main()
