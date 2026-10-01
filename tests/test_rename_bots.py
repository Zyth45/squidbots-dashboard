import argparse
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import rename_bots  # noqa: E402

from mind import lore_names, store as store_module  # noqa: E402

# guid, name, race id, gender id, class id, level, account
ROWS = [["1", "Walenno Bot", "1", "0", "1", "20", "10"], ["2", "Edimin Bot", "11", "1", "2", "20", "10"],
        ["3", "Alte Bot", "2", "0", "1", "20", "10"], ["4", "Neleth Bot", "4", "1", "3", "20", "10"],
        ["5", "Ann", "1", "1", "8", "70", "99"],                  # a player's character: never touched
        ["6", "Already Named", "3", "0", "1", "20", "10"]]         # a bot that no longer ends in " Bot"


def fake_mysql(statements):
    def run(args, sql, write=False):
        statements.append(sql)
        if "FROM `auth`.account" in sql:
            return [["10"]]
        if "SELECT guid, name, race" in sql:
            return [list(row) for row in ROWS]
        if sql.startswith("SELECT name FROM"):
            return [[row[1]] for row in ROWS]
        return []
    return run


def arguments(**overrides):
    values = dict(defaults_file="x.cnf", characters_db="chars", auth_db="auth", account_prefix="RNDBOT", mind_db=None, all=False,
                  apply=False, force=False, world_host="127.0.0.1", world_port=1, out=tempfile.mkdtemp())
    values.update(overrides)
    return argparse.Namespace(**values)


class RenameTests(unittest.TestCase):
    def run_tool(self, **overrides):
        statements = []
        args = arguments(**overrides)
        argv = ["--defaults-file", "x.cnf", "--characters-db", "chars", "--auth-db", "auth", "--out", args.out, "--world-port", "1"]
        argv += ["--apply"] if args.apply else []
        argv += ["--force"] if args.force else []
        argv += ["--all"] if args.all else []
        if args.mind_db:
            argv += ["--mind-db", args.mind_db]
        with mock.patch.object(rename_bots, "mysql", fake_mysql(statements)):
            code = rename_bots.main(argv)
        return code, statements, args.out

    def test_a_dry_run_changes_nothing_and_says_so(self):
        code, statements, out = self.run_tool()
        self.assertEqual(code, 0)
        self.assertFalse([s for s in statements if "UPDATE" in s])
        self.assertTrue([name for name in os.listdir(out) if name.startswith("rename-plan-")])
        self.assertFalse([name for name in os.listdir(out) if name.startswith("rename-rollback-")])

    def test_only_bots_still_called_bot_are_renamed_and_the_names_suit_the_race(self):
        found = rename_bots.plan(arguments(), [(1, "Walenno Bot", 1, 0, 1, 20), (3, "Alte Bot", 2, 0, 1, 20), (6, "Already Named", 3, 0, 1, 20)],
                                 ["Walenno Bot", "Alte Bot", "Already Named"])[0]
        self.assertEqual([guid for guid, *_ in found], [1, 3])
        for guid, old, new, race in found:
            self.assertTrue(lore_names.valid_full_name(new), new)
            self.assertEqual(new.split(" ")[1] in lore_names.SURNAMES[race], True)

    def test_the_same_guid_always_gets_the_same_name(self):
        one = rename_bots.plan(arguments(), [(1, "Walenno Bot", 1, 0, 1, 20)], [])[0]
        two = rename_bots.plan(arguments(), [(1, "Walenno Bot", 1, 0, 1, 20)], [])[0]
        self.assertEqual(one, two)

    def test_no_two_bots_get_the_same_name_and_none_takes_a_players(self):
        found = [(guid, "Bot%d Bot" % guid, 1, 0, 1, 20) for guid in range(1, 400)]
        renames = rename_bots.plan(arguments(), found, ["Aldric Ashford"])[0]
        names = [new.lower() for _, _, new, _ in renames]
        self.assertEqual(len(names), len(set(names)))
        self.assertNotIn("aldric ashford", names)

    def test_applying_writes_a_rollback_first_and_renames_in_one_transaction(self):
        code, statements, out = self.run_tool(apply=True, force=True)
        self.assertEqual(code, 0)
        rollback = [name for name in os.listdir(out) if name.startswith("rename-rollback-")]
        self.assertEqual(len(rollback), 1)
        text = open(os.path.join(out, rollback[0]), encoding="utf-8").read()
        self.assertIn("'Walenno Bot'", text)
        self.assertEqual(text.count("UPDATE characters"), 4)
        update = [s for s in statements if "UPDATE `chars`.characters" in s][0]
        self.assertTrue(update.startswith("START TRANSACTION") and update.endswith("COMMIT"))
        self.assertNotIn("guid = 5", update)

    def test_it_refuses_while_the_world_port_answers(self):
        with mock.patch.object(rename_bots, "world_is_running", return_value=True):
            code, statements, _ = self.run_tool(apply=True)
        self.assertEqual(code, 1)
        self.assertFalse([s for s in statements if "UPDATE" in s])

    def test_the_minds_database_follows_the_new_names(self):
        directory = tempfile.mkdtemp()
        path = os.path.join(directory, "mind.sqlite")
        store = store_module.Store(path)
        store.save_persona(1, {"name": "Walenno Bot"}, "generated")
        store.save_rp_character(1, {"name": "Walenno Bot", "race": "Human", "klass": "Warrior"}, "generated")
        code, _, _ = self.run_tool(apply=True, force=True, mind_db=path)
        self.assertEqual(code, 0)
        with sqlite3.connect(path) as db:
            persona = db.execute("SELECT name FROM persona WHERE bot_guid = 1").fetchone()[0]
            character = db.execute("SELECT name FROM rp_character WHERE bot_guid = 1").fetchone()[0]
        self.assertEqual(persona, character)
        self.assertNotIn("Bot", persona)
        self.assertEqual(len(persona.split(" ")), 2)


if __name__ == "__main__":
    unittest.main()
