import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import rename_guilds  # noqa: E402


class GuildNameTests(unittest.TestCase):
    def test_every_name_fits_a_guild_name_and_belongs_to_one_side(self):
        for side, names in rename_guilds.NAMES.items():
            self.assertGreaterEqual(len(names), 20)
            self.assertEqual(len(names), len(set(names)))
            for name in names:
                self.assertLessEqual(len(name), 24, name)
        for side, lines in rename_guilds.MOTD.items():
            self.assertTrue(all(len(line) <= 128 for line in lines))
        self.assertTrue(all(len(text) <= 500 for text in rename_guilds.INFO.values()))

    def test_the_side_comes_from_the_leaders_race_and_names_are_unique_and_stable(self):
        found = [(guild, "Old %d" % guild, 2 if guild % 2 else 1) for guild in range(1, 21)]      # orcs and humans
        one = rename_guilds.plan(found, ["Old %d" % g for g in range(1, 21)])
        two = rename_guilds.plan(found, ["Old %d" % g for g in range(1, 21)])
        self.assertEqual(one, two)
        self.assertEqual(len({row[2].lower() for row in one}), len(one))
        for guild, old, new, side, motd, info in one:
            self.assertEqual(side, "Horde" if guild % 2 else "Alliance")
            self.assertIn(new, rename_guilds.NAMES[side])

    def test_a_guild_that_already_has_a_lore_name_is_left_alone_and_a_taken_name_is_not_reused(self):
        found = [(1, rename_guilds.NAMES["Alliance"][0], 1), (2, "Plain", 1)]
        renames = rename_guilds.plan(found, [rename_guilds.NAMES["Alliance"][0], "Plain"])
        self.assertEqual([r[0] for r in renames], [2])
        self.assertNotEqual(renames[0][2], rename_guilds.NAMES["Alliance"][0])


if __name__ == "__main__":
    unittest.main()
