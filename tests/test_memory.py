import os
import tempfile
import time
import unittest

from mind import memory, store as store_module


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = store_module.Store(os.path.join(self.tmp.name, "m.sqlite"))

    def test_a_matching_old_fact_beats_recent_small_talk(self):
        now = time.time()
        self.store.add_memory(1, 9, "Ann", "fact", "Ann is farming Ulduar for her tier gear", 0.7)
        for index in range(12):
            self.store.add_memory(1, 9, "Ann", "event", 'Ann said: "lol %d" - you replied: "ha"' % index, 0.25)
        recalled = memory.recall(self.store, 1, 9, "how is the Ulduar farming going?", now)
        self.assertIn("Ulduar", " ".join(m["text"] for m in recalled))
        self.assertLessEqual(len(recalled), int(self.store.setting("recall_count")))

    def test_recall_is_about_this_player_only(self):
        self.store.add_memory(1, 9, "Ann", "fact", "Ann likes fishing", 0.8)
        self.store.add_memory(1, 10, "Bob", "fact", "Bob hates fishing", 0.8)
        texts = [m["text"] for m in memory.recall(self.store, 1, 9, "fishing")]
        self.assertEqual(texts, ["Ann likes fishing"])

    def test_no_player_no_recall(self):
        self.store.add_memory(1, 9, "Ann", "fact", "x", 0.9)
        self.assertEqual(memory.recall(self.store, 1, 0, "x"), [])

    def test_exchange_is_stored_once_and_important_ones_weigh_more(self):
        self.assertTrue(memory.record_exchange(self.store, 1, 9, "Ann", "remember my name is Ann", "Will do"))
        self.assertFalse(memory.record_exchange(self.store, 1, 9, "Ann", "remember my name is Ann", "Will do"))
        self.assertTrue(memory.record_exchange(self.store, 1, 9, "Ann", "nice weather", "Sure is"))
        by_text = {m["text"]: m["salience"] for m in self.store.memories(1, 9)}
        important = next(v for k, v in by_text.items() if "remember" in k)
        plain = next(v for k, v in by_text.items() if "weather" in k)
        self.assertGreater(important, plain)
        self.assertEqual(self.store.relationship(1, 9)["interactions"], 2)

    def test_nothing_is_stored_without_both_sides_or_a_player(self):
        self.assertFalse(memory.record_exchange(self.store, 1, 0, "", "hi", "hello"))
        self.assertFalse(memory.record_exchange(self.store, 1, 9, "Ann", "hi", ""))

    def test_events_are_capped_but_facts_are_not(self):
        self.store.set_setting("memory_per_subject", 5)
        self.store.add_memory(1, 9, "Ann", "fact", "Ann main is a healer", 0.9)
        for index in range(20):
            memory.record_exchange(self.store, 1, 9, "Ann", "line %d" % index, "reply %d" % index)
        self.assertEqual(len(self.store.memories(1, 9, kinds=["event"])), 5)
        self.assertEqual(len(self.store.memories(1, 9, kinds=["fact"])), 1)

    def test_parse_reflection_survives_chatter_and_bad_numbers(self):
        reply = 'Sure! ```json\n{"facts": [{"text": "Ann plays a healer", "salience": "high"}, "Ann owes 5 gold"],' \
                ' "affinity_change": 9, "reason": "she was kind"}\n``` hope that helps'
        parsed = memory.parse_reflection(reply)
        self.assertEqual([f["text"] for f in parsed["facts"]], ["Ann plays a healer", "Ann owes 5 gold"])
        self.assertEqual(parsed["affinity_change"], 0.25)
        self.assertTrue(all(0.1 <= f["salience"] <= 1.0 for f in parsed["facts"]))

    def test_parse_reflection_rejects_nonsense(self):
        self.assertIsNone(memory.parse_reflection("I cannot do that"))
        self.assertIsNone(memory.parse_reflection("{not json}"))
        self.assertIsNone(memory.parse_reflection("[1, 2]"))

    def test_reflection_dedupes_facts_and_moves_affinity_within_bounds(self):
        self.store.note_seen(1, 9, "Ann")
        reflection = {"facts": [{"text": "Ann plays a healer", "salience": 0.6}], "affinity_change": 0.25, "reason": "kind"}
        memory.apply_reflection(self.store, 1, 9, "Ann", reflection)
        memory.apply_reflection(self.store, 1, 9, "Ann", {"facts": [{"text": "Ann plays a healer.", "salience": 0.9}],
                                                         "affinity_change": 0.25, "reason": "kind again"})
        facts = self.store.memories(1, 9, kinds=["fact"])
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["salience"], 0.9)
        self.assertAlmostEqual(self.store.relationship(1, 9)["affinity"], 0.5)
        for _ in range(10):
            memory.apply_reflection(self.store, 1, 9, "Ann", {"facts": [], "affinity_change": 0.25, "reason": "x"})
        self.assertEqual(self.store.relationship(1, 9)["affinity"], 1.0)


if __name__ == "__main__":
    unittest.main()
