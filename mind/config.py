"""Where the mind service listens and keeps its files, from the "mind" object of dashboard.json.

    "mind": {"port": 18800, "host": "127.0.0.1", "db": "mind.sqlite", "token": ""}

Every key is optional. Paths are relative to the dashboard folder.
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULTS = {
    "port": 18800,
    "host": "127.0.0.1",
    "db": "mind.sqlite",
    "statusFile": "mind-status.json",
    # API keys are never stored in the database or shown by the dashboard. A profile names an
    # environment variable; when the variable is not set, this file ({"<profile>": "<key>"}) is read.
    "secretsFile": "mind-secrets.json",
    # Bearer token the worldserver must send. Empty = accept any caller on the bound address, which
    # is only reasonable while the host is 127.0.0.1.
    "token": "",
}


def load(dashboard_json=None):
    """The effective settings, with absolute paths.

    The file is `dashboard_json`, else the path in SQUIDBOTS_DASHBOARD_JSON (so a test or a second realm can keep its
    own), else dashboard.json beside the code. Relative paths are relative to the folder the file is in.
    """
    path = dashboard_json or os.environ.get("SQUIDBOTS_DASHBOARD_JSON") or os.path.join(HERE, "dashboard.json")
    base = os.path.dirname(os.path.abspath(path))
    given = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig") as handle:
            given = (json.load(handle) or {}).get("mind") or {}
    settings = dict(DEFAULTS)
    settings.update({key: given[key] for key in DEFAULTS if key in given})
    for key in ("db", "statusFile", "secretsFile"):
        settings[key] = os.path.join(base, settings[key])
    settings["port"] = int(settings["port"])
    return settings
