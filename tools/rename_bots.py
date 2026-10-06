"""Give the bots names that suit their race: "Alte Bot" becomes "Elorin Moonwhisper".

Playerbots names a Conquest of Azeroth bot "First Bot": the surname tells a bot from a player on its nameplate, but it also tells
anyone roleplaying with it that nothing is there. This renames the random bots to a first name and a family name in the way of their
people (lore_names.py): Dun Morogh dwarves get Baldrin Ironbeard, night elves Elorin Moonwhisper, orcs Gorgrim Skullcleaver. The
names are two words, which Conquest of Azeroth allows and which playerbots leaves alone with its default `AiPlayerbot.CoaBotSurname`.

It is a DRY RUN unless you pass --apply: it prints what each bot would be called and writes nothing. To apply:

  1. Stop the worldserver (the tool refuses while the world port answers; names are cached in memory and a rename under a running
     realm leaves the cache and the database disagreeing).
  2. Run it with --apply. A rollback script (every old name) is written next to the report before anything is changed, and the rename
     is one transaction.
  3. Give it the mind's database too (--mind-db) so the bots' stories, memories and friendships follow the new names.
  4. Start the realm.

    python3 tools/rename_bots.py --defaults-file ~/.config/coa-dev/client.cnf --characters-db coa_test_minds_characters \\
        --auth-db coa_test_minds_auth [--mind-db ~/src/coa-minds/mind.sqlite] [--apply]

Names are chosen from the bot's race and gender, seeded by its guid, so a second run changes nothing it already changed. Only bots on
the random-bot accounts whose name still ends in " Bot" are touched (--all renames every random bot). Standard library only; it talks
to MySQL through the `mysql` command line client.
"""
import argparse
import datetime
import os
import random
import socket
import sqlite3
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from mind import lore, lore_names  # noqa: E402

GENDERS = {0: "male", 1: "female"}


def mysql(args, sql, write=False):
    """The rows (tab separated, one list per row) the statement returns."""
    # The statement goes in on stdin: a rename of a thousand bots is far past the length of one command-line argument.
    command = ["mysql", "--defaults-file=" + args.defaults_file, "--batch", "--skip-column-names"]
    done = subprocess.run(command, input=sql, capture_output=True, text=True, timeout=300)
    if done.returncode != 0:
        raise RuntimeError("mysql failed: %s" % done.stderr.strip())
    return [line.split("\t") for line in done.stdout.splitlines() if line]


def quote(name):
    return "'" + name.replace("\\", "\\\\").replace("'", "''") + "'"


def bots(args):
    """[(guid, name, race, gender, class, level)] for the random bots."""
    prefix = args.account_prefix.replace("'", "")
    accounts = {row[0] for row in mysql(args, "SELECT id FROM `%s`.account WHERE username LIKE '%s%%'" % (args.auth_db, prefix))}
    rows = mysql(args, "SELECT guid, name, race, gender, class, level, account FROM `%s`.characters" % args.characters_db)
    return [(int(guid), name, int(race), int(gender), int(klass), int(level))
            for guid, name, race, gender, klass, level, account in rows if account in accounts]


def everyone(args):
    return [row[0] for row in mysql(args, "SELECT name FROM `%s`.characters" % args.characters_db)]


def plan(args, found, taken):
    """[(guid, old, new, race)]: the renames, deterministic per guid, none colliding with a name already in use."""
    taken = {name.lower() for name in taken}
    renames, skipped = [], []
    for guid, name, race_id, gender_id, klass, level in sorted(found):
        race = lore.RACE_IDS.get(race_id)
        if not race:
            skipped.append((guid, name, "unknown race %d" % race_id))
            continue
        if not args.all and not name.endswith(" Bot"):
            continue
        new = lore_names.full_name(race, GENDERS.get(gender_id, "male"), taken, random.Random("rename:%d" % guid))
        taken.add(new.lower())
        renames.append((guid, name, new, race))
    return renames, skipped


def world_is_running(args):
    try:
        with socket.create_connection((args.world_host, args.world_port), timeout=1.5):
            return True
    except OSError:
        return False


def write_rollback(path, renames):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("-- Undo rename_bots.py: puts every bot back under its old name.\nSTART TRANSACTION;\n")
        for guid, old, new, _ in renames:
            handle.write("UPDATE characters SET name = %s WHERE guid = %d AND name = %s;\n" % (quote(old), guid, quote(new)))
        handle.write("COMMIT;\n")


def apply_game(args, renames):
    statements = ["START TRANSACTION"]
    for guid, old, new, _ in renames:
        statements.append("UPDATE `%s`.characters SET name = %s WHERE guid = %d AND name = %s" % (args.characters_db, quote(new), guid, quote(old)))
    statements.append("COMMIT")
    mysql(args, "; ".join(statements))


def apply_mind(path, renames):
    """The mind service keys everything on the guid but keeps the name it last saw; without this a bot would look like someone else at
    its next conversation (and a player-style persona would be rolled again, with its memories cleared)."""
    database = sqlite3.connect(path)
    try:
        with database:
            for guid, old, new, _ in renames:
                for table in ("persona", "rp_character", "cast"):
                    try:
                        database.execute("UPDATE %s SET name = ? WHERE bot_guid = ?" % table, (new, guid))
                    except sqlite3.OperationalError:
                        pass      # a database from before roleplay has no rp_character
    finally:
        database.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--defaults-file", required=True, help="a mysql client config (user, password, host, port)")
    parser.add_argument("--characters-db", required=True)
    parser.add_argument("--auth-db", required=True)
    parser.add_argument("--account-prefix", default="RNDBOT", help="AiPlayerbot.RandomBotAccountPrefix (default RNDBOT)")
    parser.add_argument("--mind-db", help="the mind service's mind.sqlite, to rename the bots there too")
    parser.add_argument("--all", action="store_true", help="rename every random bot, not only the ones still called 'Something Bot'")
    parser.add_argument("--apply", action="store_true", help="write the new names (the default is a dry run)")
    parser.add_argument("--force", action="store_true", help="apply even though the world port answers (the realm's name cache goes stale)")
    parser.add_argument("--world-host", default="127.0.0.1")
    parser.add_argument("--world-port", type=int, default=8085)
    parser.add_argument("--out", default=".", help="where the report and the rollback script are written")
    args = parser.parse_args(argv)

    found = bots(args)
    renames, skipped = plan(args, found, everyone(args))
    print("%d random bots, %d to rename%s." % (len(found), len(renames), ", %d left alone" % len(skipped) if skipped else ""))
    by_race = {}
    for _, _, _, race in renames:
        by_race[race] = by_race.get(race, 0) + 1
    print("  by people: " + ", ".join("%s %d" % item for item in sorted(by_race.items())))
    for guid, old, new, race in renames[:40]:
        print("  %6d  %-18s -> %-24s %s" % (guid, old, new, race))
    if len(renames) > 40:
        print("  ... and %d more" % (len(renames) - 40))
    for guid, name, why in skipped[:10]:
        print("  left alone: %d %s (%s)" % (guid, name, why))
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    report = os.path.join(args.out, "rename-plan-%s.tsv" % stamp)
    with open(report, "w", encoding="utf-8") as handle:
        handle.write("guid\told\tnew\trace\n" + "".join("%d\t%s\t%s\t%s\n" % row for row in renames))
    print("The full list is in %s." % report)
    if not renames:
        return 0
    if not args.apply:
        print("DRY RUN: nothing was changed. Stop the worldserver and run again with --apply to rename.")
        return 0
    if world_is_running(args) and not args.force:
        print("ERROR The world port %s:%d answers: stop the worldserver first (or --force, and restart it right after)." % (args.world_host, args.world_port))
        return 1
    rollback = os.path.join(args.out, "rename-rollback-%s.sql" % stamp)
    write_rollback(rollback, renames)
    print("Rollback script written: %s (run it against the characters database to undo)." % rollback)
    apply_game(args, renames)
    print("Renamed %d bots in %s." % (len(renames), args.characters_db))
    if args.mind_db:
        apply_mind(os.path.expanduser(args.mind_db), renames)
        print("Updated the names in %s." % args.mind_db)
    else:
        print("The mind's database was not given (--mind-db): bots keep their stories, but the dashboard shows the old names until each speaks.")
    print("Start the realm. New bots made later are still named from playerbots' own list; run this again to rename them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
