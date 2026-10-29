"""The realms of this server: the CoA realm, and the Wildcard and Reborn realms the launcher adds beside it.

The launcher (src/realms.cjs) keeps each extra realm in <repack>\\Royaumes\\<key>: realm.json (id, name, ports,
disabled), configs\\ (the settings it builds again before every start), Logs\\ (its journals and bot-status.json),
.state.json (the pid of its worldserver), and the databases acore_characters_<key> / acore_playerbots_<key>. MySQL,
acore_auth and acore_world are shared. The dashboard only reads that folder: it never creates, changes or starts a realm.

Without a Royaumes folder there is one realm, the CoA one, exactly as before: same files, same settings.
"""
import json
import os
import re

# What the launcher's modes are (realms.cjs MODES): the id it gives a new realm, the prefix of its bot accounts.
MODES = {
    "coa": {"id": 1, "name": "Conquest of Azeroth", "prefix": "rndbot", "step": 0},
    "wildcard": {"id": 2, "name": "Darkmoon (Wildcard)", "prefix": "rndwc", "step": 1},
    "reborn": {"id": 3, "name": "Bronzebeard (Reborn)", "prefix": "rndwr", "step": 2},
    "dawnrise": {"id": 4, "name": "Dawnrise (Free Pick)", "prefix": "rndfp", "step": 3},
}
# Files the dashboard wrote beside itself before it knew of realms: the CoA realm keeps them there.
LEGACY = {"kills.json", "levels.json", "history.json", "xp-history.json", "baseline.json", "pvp.json"}
KEY = re.compile(r"^[a-z]{3,12}$")
NAME = re.compile(r"^[A-Za-z0-9_]+$")
# Settings the launcher imposes on a realm (realms.cjs imposed()): a value written for them in settings.json would be
# overwritten at the next start, so the Settings page shows them without letting them be changed there.
IMPOSED = {
    "AiPlayerbot.RandomBotAccountPrefix", "AiPlayerbot.CoaStatusFile", "AiPlayerbot.CommandServerPort",
    "AiPlayerbot.CoaClassesOnly", "CoA.RandomBotAccountPrefix", "CoA.RotationAssist.Enable", "CoA.GameModeMask",
    "CoA.ClassModel", "CoA.RealmType", "CoA.MapClass10ToWarrior", "CoA.ClientBooleanConfigs",
    "CoAChallenges.GameModes.Realm", "CoACustomRaces.Enable", "CoACustomRaces.BotsEnable", "Ascension.Manastorm.Enable",
    "Manastorm.Enable", "RealmID", "WorldServerPort", "Ra.Port", "SOAP.Enabled", "PlayerStart.CustomSpells",
    "AlwaysMaxSkillForLevel", "CharacterCreating.Disabled.ClassMask",
}


def read_json(path):
    try:
        with open(path, encoding="utf-8-sig") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def conf_value(path, key):
    """The value of `key` in a .conf file (the last line that sets it), without quotes; None if absent."""
    pattern = re.compile(r"^\s*%s\s*=\s*(.*?)\s*$" % re.escape(key))
    found = None
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                match = pattern.match(line)
                if match:
                    found = match.group(1).strip().strip('"')
    except OSError:
        return None
    return found


class Realm:
    """One realm: its databases, folders, ports and bot accounts. `files` is where the dashboard keeps what it writes
    for this realm (history, kills, levels...): the dashboard's own folder for the CoA realm, as before, and
    data\\<key>\\ for the others."""

    def __init__(self, key, rid, name, databases, logs, config_dir, crashes, files, prefix, world_port=0, ra_port=0,
                 pid_file=None, disabled=False, mode=None, here=None):
        self.key, self.id, self.name = key, int(rid), name
        self.mode = mode or key
        self.db = databases
        self.logs = logs
        self.config_dir = config_dir
        self.crashes = crashes
        self.files = files
        self.data = os.path.join(here or files, "data", key)
        self.prefix = (prefix or "rndbot").upper()
        self.world_port, self.ra_port = int(world_port or 0), int(ra_port or 0)
        self.pid_file = pid_file
        self.disabled = disabled
        for value in databases.values():
            if not NAME.match(value):
                raise ValueError("%r is not a database name" % value)

    # Bot accounts are named <prefix><n> (mod-playerbots): a LIKE pattern, from a checked prefix only.
    @property
    def bot_like(self):
        return re.sub(r"[^A-Z0-9]", "", self.prefix) + "%"

    def file(self, name):
        folder = self.files if name in LEGACY else self.data
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, name)

    def pid(self):
        """The pid the launcher (or the repack's manage.py) recorded for this realm's worldserver, or 0."""
        record = read_json(self.pid_file) if self.pid_file else None
        try:
            return int((record or {}).get("pid") or 0)
        except (TypeError, ValueError):
            return 0

    def public(self):
        return {"key": self.key, "id": self.id, "name": self.name, "mode": self.mode, "disabled": self.disabled}


def _port(*values):
    for value in values:
        try:
            if int(value or 0) > 0:
                return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def discover(root, settings, here, coa):
    """[Realm] of this server, the CoA realm first. `coa` is the CoA realm as dashboard.json describes it."""
    realms = [coa]
    if settings.get("realms") is False:
        return realms
    folder = os.path.join(root or "", "Royaumes")
    try:
        keys = sorted(os.listdir(folder))
    except OSError:
        return realms
    for key in keys:
        place = os.path.join(folder, key)
        saved = read_json(os.path.join(place, "realm.json"))
        if not KEY.match(key) or not isinstance(saved, dict) or key not in MODES or key == "coa":
            continue
        configs = os.path.join(place, "configs")
        if not os.path.exists(os.path.join(configs, "worldserver.conf")):
            continue                     # created by an older launcher and never started: nothing to read yet
        modules = os.path.join(configs, "modules")
        mode = MODES[key]
        prefix = conf_value(os.path.join(modules, "playerbots.conf"), "AiPlayerbot.RandomBotAccountPrefix") or mode["prefix"]
        # The ports the realm's worldserver really uses: those of the configs the launcher wrote for it, then realm.json,
        # then the launcher's own rule for a realm that never saved them (the CoA realm's + 100 per step).
        conf = os.path.join(configs, "worldserver.conf")
        repack = read_json(os.path.join(root, "Settings", "repack.json")) or {}
        world_port = _port(conf_value(conf, "WorldServerPort"), saved.get("worldPort"),
                           _port(repack.get("worldPort"), 8085) + 100 * mode["step"])
        ra_port = _port(conf_value(conf, "Ra.Port"), saved.get("raPort"), _port(repack.get("raPort"), 3443) + 100 * mode["step"])
        databases = {"auth": coa.db["auth"], "world": coa.db["world"], "characters": "acore_characters_" + key,
                     "playerbots": "acore_playerbots_" + key}
        try:
            realms.append(Realm(
                key, saved.get("id") or mode["id"], saved.get("name") or mode["name"], databases,
                logs=os.path.join(place, "Logs"), config_dir=modules, crashes=[os.path.join(place, "Crashes")],
                files=os.path.join(here, "data", key), prefix=prefix, world_port=world_port,
                ra_port=ra_port, pid_file=os.path.join(place, ".state.json"),
                disabled=bool(saved.get("disabled")), here=here))
        except ValueError:
            continue
    realms[1:] = sorted(realms[1:], key=lambda r: r.id)
    return realms


def own_settings(root, key):
    """Royaumes\\<key>\\settings.json: the keys the player changed for this realm, by settings file (the launcher's
    layer 2). {} when there is none."""
    saved = read_json(os.path.join(root, "Royaumes", key, "settings.json"))
    return saved if isinstance(saved, dict) else {}


def write_own_settings(root, key, changes):
    """Put `changes` ({file: {key: value}}) into Royaumes\\<key>\\settings.json, the way the launcher writes it: the
    launcher builds the realm's .conf files from it at the next start. Returns the keys written."""
    path = os.path.join(root, "Royaumes", key, "settings.json")
    own = own_settings(root, key)
    written = []
    for name, keys in changes.items():
        for setting, value in keys.items():
            if setting in IMPOSED:
                continue
            own.setdefault(name, {})[setting] = str(value)
            written.append(setting)
    own = {name: keys for name, keys in own.items() if keys}
    temporary = path + ".tmp"
    # As the launcher writes it (JSON.stringify(own, null, 2)): LF line ends, no BOM.
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(own, handle, indent=2, ensure_ascii=False)
    os.replace(temporary, path)
    return written
