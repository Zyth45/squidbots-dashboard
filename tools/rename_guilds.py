"""Give the bots' guilds names, a message of the day and an info text that belong to the world of Warcraft.

A realm of playerbots ends up with guilds called "Elite Guard" and "Family of Misfits". This renames every guild that a random bot leads to a
name of its side's own (Stormwind, Ironforge, Darnassus and the Exodar for the Alliance; Orgrimmar, Thunder Bluff, Undercity and Silvermoon for
the Horde), and gives it a message of the day and an info text in the same voice. The side comes from the race of the guild's leader.

A DRY RUN unless you pass --apply. Applying needs the worldserver stopped (guild names are cached in memory), writes a rollback script first and
changes everything in one transaction. Guilds a real player leads are never touched.

    python3 tools/rename_guilds.py --defaults-file ~/.config/coa-dev/client.cnf --characters-db coa_test_minds_characters \\
        --auth-db coa_test_minds_auth [--apply]

Names are chosen by guild id, so a second run changes nothing it already changed. Standard library only (MySQL through the `mysql` client).
"""
import argparse
import datetime
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import rename_bots  # noqa: E402
from mind import lore  # noqa: E402

NAMES = {
    "Alliance": """The Lion's Pride Company|Order of the Silver Dawn|Stormwind Vanguard|Goldshire Wayfarers|The Hammer Brotherhood|Ironforge Delvers|
        Keepers of the Forge|Tinker Town Cogwrights|Darnassus Sentinels|Moonwell Wardens|Teldrassil Boughwatch|The Exodar Lightbearers|
        Crystal Hall Vigil|Westfall Plowmen|Redridge Rangers|Duskwood Watchers|Loch Modan Pickmen|Wildhammer Riders|Kirin Tor Scholars|
        The Cathedral Guard|Brotherhood of the Light|Thelsamar Stoutmen|Southshore Militia|Menethil Harbor Guild|Auberdine Seafarers|
        Dun Morogh Frostwalkers|The Argent Dawn Lodge|Stonewrought Sappers|Lakeshire Watch|Northshire Brethren""".replace("\n", "").split("|"),
    "Horde": """Orgrimmar Wolfriders|The Razor Hill Blades|Darkspear Kin|Sen'jin Spearmen|Thunder Bluff Hunters|Bloodhoof Clan|Earthmother's Children|
        Undercity Apothecaries|The Forsaken Vigil|Brill Gravediggers|Silvermoon Farstriders|Sunstrider Court|Eversong Wardens|Crossroads Marauders|
        The Barrens Caravan|Camp Taurajo Watch|Warsong Remnant|Frostwolf Clan|Hammerfall Raiders|Tarren Mill Militia|Ratchet Dockhands|
        Grommash Honour Guard|Echo Isles Fishers|Thrallmar Vanguard|Horde Wayfarers|Skull Rock Vigil|Valley of Honor Blades|
        The Stonetalon Climbers|Shadowglen Exiles|Spirit Rise Shamans""".replace("\n", "").split("|"),
}
MOTD = {
    "Alliance": ["The hearth is warm and the road is long. Come in.", "For the Alliance, and for whoever is buying the next round.",
                 "Stand together, travel together, come home together.", "Keep your blade clean and your word cleaner.",
                 "Light keep you on the road; the ale is on the table."],
    "Horde": ["Blood and thunder. The fire is lit, come and sit.", "For the Horde, and for whoever fills the cups.",
              "Strength and honour. Bring a story for the fire.", "Lok'tar ogar: a warrior walks forward.",
              "The spirits watch the road; so do we."],
}
INFO = {
    "Alliance": "A fellowship of the Alliance: travellers, tradesfolk and sellswords who look after one another on the roads. New faces are welcome at the fire.",
    "Horde": "A clan of the Horde: warriors, hunters and wanderers who keep faith with one another on the long roads. Bring your stories to the fire.",
}
NAMES = {side: [name.strip() for name in names] for side, names in NAMES.items()}
SIDE_OF = {name: info["faction"] for name, info in lore.RACES.items()}


def guilds(args):
    """[(guildid, name, leader_race_id)] for guilds a random bot leads."""
    prefix = args.account_prefix.replace("'", "")
    accounts = {row[0] for row in rename_bots.mysql(args, "SELECT id FROM `%s`.account WHERE username LIKE '%s%%'" % (args.auth_db, prefix))}
    rows = rename_bots.mysql(args, "SELECT g.guildid, g.name, c.race, c.account FROM `%s`.guild g JOIN `%s`.characters c ON c.guid = g.leaderguid" % (
        args.characters_db, args.characters_db))
    return [(int(guild), name, int(race)) for guild, name, race, account in rows if account in accounts]


def plan(found, taken):
    """[(guildid, old, new, side, motd, info)]: deterministic per guild id, no two the same and none that another guild already has."""
    used = {name.lower() for name in taken}
    out = []
    for guild_id, old, race_id in sorted(found):
        side = SIDE_OF.get(lore.RACE_IDS.get(race_id, ""), "Alliance")
        rng = random.Random("guild:%d" % guild_id)
        pool = [n for n in NAMES[side] if len(n) <= 24 and n.lower() not in used]
        if not pool or old in NAMES[side]:
            continue
        new = rng.choice(pool)
        used.add(new.lower())
        out.append((guild_id, old, new, side, rng.choice(MOTD[side]), INFO[side]))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--defaults-file", required=True)
    parser.add_argument("--characters-db", required=True)
    parser.add_argument("--auth-db", required=True)
    parser.add_argument("--account-prefix", default="RNDBOT")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--world-host", default="127.0.0.1")
    parser.add_argument("--world-port", type=int, default=8085)
    parser.add_argument("--out", default=".")
    args = parser.parse_args(argv)

    found = guilds(args)
    taken = [row[0] for row in rename_bots.mysql(args, "SELECT name FROM `%s`.guild" % args.characters_db)]
    renames = plan(found, taken)
    print("%d guilds led by bots, %d to rename." % (len(found), len(renames)))
    for guild_id, old, new, side, motd, _ in renames:
        print("  %3d  %-24s -> %-26s %-9s %s" % (guild_id, old, new, side, motd))
    if not renames:
        return 0
    if not args.apply:
        print("DRY RUN: nothing was changed. Stop the worldserver and run again with --apply.")
        return 0
    if rename_bots.world_is_running(args) and not args.force:
        print("ERROR The world port %s:%d answers: stop the worldserver first (or --force, and restart it right after)." % (args.world_host, args.world_port))
        return 1
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    rollback = os.path.join(args.out, "guild-rollback-%s.sql" % stamp)
    olds = {row[0]: row[1:] for row in rename_bots.mysql(args, "SELECT guildid, name, motd, info FROM `%s`.guild" % args.characters_db)}
    with open(rollback, "w", encoding="utf-8") as handle:
        handle.write("START TRANSACTION;\n")
        for guild_id, old, new, *_ in renames:
            name, motd, info = (olds.get(str(guild_id)) or (old, "", ""))
            handle.write("UPDATE guild SET name = %s, motd = %s, info = %s WHERE guildid = %d;\n" % (
                rename_bots.quote(old), rename_bots.quote(motd), rename_bots.quote(info), guild_id))
        handle.write("COMMIT;\n")
    statements = ["START TRANSACTION"] + [
        "UPDATE `%s`.guild SET name = %s, motd = %s, info = %s WHERE guildid = %d AND name = %s" % (
            args.characters_db, rename_bots.quote(new), rename_bots.quote(motd), rename_bots.quote(info), guild_id, rename_bots.quote(old))
        for guild_id, old, new, side, motd, info in renames] + ["COMMIT"]
    rename_bots.mysql(args, "; ".join(statements))
    print("Renamed %d guilds. Rollback script: %s. Start the realm." % (len(renames), rollback))
    return 0


if __name__ == "__main__":
    sys.exit(main())
