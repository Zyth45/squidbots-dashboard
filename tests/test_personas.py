import os
import sqlite3
import tempfile
import unittest
from collections import Counter

from mind import personas, prompt, store as store_module
from tests.support import GatewayCase


class GeneratorTests(unittest.TestCase):
    def test_the_same_bot_always_rolls_the_same_persona_and_a_new_salt_rolls_another(self):
        self.assertEqual(personas.generate(20014, "Brick"), personas.generate(20014, "Brick"))
        rolls = {personas.generate(20014, "Brick", salt=n)["archetype"] + personas.generate(20014, "Brick", salt=n)["traits"] for n in range(30)}
        self.assertGreater(len(rolls), 5)

    def test_a_persona_has_everything_the_prompt_uses(self):
        for guid in range(1, 60):
            persona = personas.generate(guid, "Bot")
            for key in ("archetype", "traits", "speech_style", "interests", "opinions"):
                self.assertTrue(persona[key], (guid, key))
            self.assertTrue(0 <= persona["chattiness"] <= 100)
            self.assertEqual(persona["archetype"], persona["archetype"].strip())

    def test_a_realm_of_bots_has_trolls_and_banter_and_quiet_ones_not_a_cast_of_heroes(self):
        kinds = Counter(personas.generate(guid)["archetype"] for guid in range(1, 400))
        self.assertGreater(kinds["troll"], 5)
        self.assertGreater(kinds["banter merchant"], 5)
        self.assertGreater(kinds["salty veteran"], 10)
        # most people in a realm are ordinary: plain talkers outnumber the jokers by a wide margin
        plain = kinds["regular"] + kinds["chill"] + kinds["impatient"] + kinds["cynic"] + kinds["returning player"]
        jokers = kinds["troll"] + kinds["banter merchant"] + kinds["meme lord"]
        self.assertGreater(plain, jokers * 3)
        self.assertLess(kinds["old-school roleplayer"], 30)
        loud = [personas.generate(guid)["chattiness"] for guid in range(1, 400)]
        self.assertTrue(any(c <= 30 for c in loud) and any(c >= 75 for c in loud))

    def test_trolls_are_chatty_and_lurkers_are_not(self):
        chat = {kind: [] for kind in ("troll", "lurker")}
        for guid in range(1, 800):
            persona = personas.generate(guid)
            if persona["archetype"] in chat:
                chat[persona["archetype"]].append(persona["chattiness"])
        self.assertGreater(min(chat["troll"]), 65)
        self.assertLess(max(chat["lurker"]), 30)

    def test_no_archetype_asks_for_hate_or_anything_the_reply_filter_would_need_to_catch(self):
        text = " ".join(str(value) for kind in personas.ARCHETYPES.values() for value in kind).lower()
        for word in ("nazi", "slur", "rape", "kill yourself"):
            self.assertNotIn(word, text)


class PromptTests(unittest.TestCase):
    def test_opinions_and_chattiness_reach_the_persona_block(self):
        block = prompt.persona_block({"name": "Brick", "opinions": "gnomes are best", "chattiness": 90}, "", "")
        self.assertIn("Your strong opinions and running jokes: gnomes are best", block)
        self.assertIn("You are chatty", block)
        self.assertIn("You are the quiet type", prompt.persona_block({"name": "Brick", "chattiness": 10}, "", ""))
        middling = prompt.persona_block({"name": "Brick", "chattiness": 50}, "", "")
        self.assertNotIn("chatty", middling)
        self.assertNotIn("quiet type", middling)


class StorageTests(GatewayCase):
    def test_opinions_and_chattiness_are_stored_and_bounded(self):
        self.store.save_persona(1, {"name": "A", "opinions": "x", "chattiness": 80}, "manual")
        self.assertEqual((self.store.persona(1)["opinions"], self.store.persona(1)["chattiness"]), ("x", 80))
        self.store.save_persona(2, {"name": "B", "chattiness": 900}, "manual")
        self.assertEqual(self.store.persona(2)["chattiness"], 100)
        self.store.save_persona(3, {"name": "C", "chattiness": "loud"}, "manual")
        self.assertEqual(self.store.persona(3)["chattiness"], 50)

    def test_a_database_made_before_these_fields_gains_them_and_keeps_its_personas(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "old.sqlite")
            db = sqlite3.connect(path)
            db.execute("CREATE TABLE persona (bot_guid INTEGER PRIMARY KEY, name TEXT NOT NULL DEFAULT '', archetype TEXT NOT NULL DEFAULT '',"
                       " traits TEXT NOT NULL DEFAULT '', speech_style TEXT NOT NULL DEFAULT '', interests TEXT NOT NULL DEFAULT '',"
                       " backstory TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT 'generated', enabled INTEGER NOT NULL DEFAULT 1,"
                       " muted INTEGER NOT NULL DEFAULT 0, updated_at REAL NOT NULL)")
            db.execute("INSERT INTO persona (bot_guid, name, archetype, updated_at) VALUES (7, 'Old', 'worrier', 1)")
            db.execute("PRAGMA user_version = 3")
            db.commit()
            db.close()
            migrated = store_module.Store(path)
            persona = migrated.persona(7)
            self.assertEqual((persona["name"], persona["archetype"], persona["opinions"], persona["chattiness"]), ("Old", "worrier", "", 50))


class MixTests(unittest.TestCase):
    def test_the_default_mix_round_trips_through_its_text(self):
        self.assertEqual(personas.parse_mix(personas.mix_text()), personas.default_mix())
        self.assertEqual(personas.parse_mix(""), personas.default_mix())

    def test_a_kind_left_out_is_never_rolled_and_a_weight_of_zero_removes_it(self):
        mix = personas.parse_mix("troll: 1")
        kinds = {personas.generate(guid, mix=mix)["archetype"] for guid in range(1, 200)}
        self.assertEqual(kinds, {"troll"})
        mix = personas.parse_mix(personas.mix_text().replace("troll: 1", "troll: 0"))
        self.assertNotIn("troll", {personas.generate(guid, mix=mix)["archetype"] for guid in range(1, 400)})

    def test_a_heavier_weight_makes_a_kind_more_common(self):
        heavy = personas.parse_mix("troll: 20, lurker: 1")
        kinds = Counter(personas.generate(guid, mix=heavy)["archetype"] for guid in range(1, 400))
        self.assertGreater(kinds["troll"], kinds["lurker"] * 8)

    def test_a_bad_mix_is_refused_with_a_reason(self):
        for text, reason in (("trol: 1", "not a kind"), ("troll: x", "must be a number"), ("troll: -2", "between 0 and 1000"),
                             ("troll: 0", "at least one")):
            with self.assertRaises(ValueError) as raised:
                personas.parse_mix(text)
            self.assertIn(reason, str(raised.exception))

    def test_a_kind_can_be_forced(self):
        for guid in (1, 2, 3):
            self.assertEqual(personas.generate(guid, archetype="lurker")["archetype"], "lurker")
        with self.assertRaises(ValueError):
            personas.generate(1, archetype="knight")


if __name__ == "__main__":
    unittest.main()
