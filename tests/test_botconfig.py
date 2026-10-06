import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import botconfig  # noqa: E402

# The real module config, from the synthiqbots fork checked out beside this repo (or MOD_OLLAMA_CHAT_CONF).
DIST = os.environ.get("MOD_OLLAMA_CHAT_CONF") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "synthiqbots", "conf",
    "mod_ollama_chat.conf.dist")


@unittest.skipUnless(os.path.exists(DIST), "the synthiqbots fork is not beside this repo")
class ModuleConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        shutil.copy(DIST, os.path.join(self.tmp.name, botconfig.OLLAMACHAT))
        self.backups = os.path.join(self.tmp.name, "backups")

    def rows(self):
        return {row["key"]: row for row in botconfig.read_settings(self.tmp.name)}

    def test_every_curated_key_exists_in_the_real_config(self):
        missing = [key for key, row in self.rows().items() if row["file"] == botconfig.OLLAMACHAT and not row["present"]]
        self.assertEqual(missing, [], "curated settings the module's conf.dist does not have")

    def test_the_minds_on_recipe_applies_to_the_real_config_and_reads_back(self):
        recipe = next(r for r in botconfig.RECIPES if r["id"] == "minds-on")
        changes = {key: value for key, value in recipe["changes"].items() if key in botconfig.BY_KEY
                   and botconfig.BY_KEY[key].file == botconfig.OLLAMACHAT}
        written, backups, errors = botconfig.apply_settings(self.tmp.name, changes, self.backups)
        self.assertEqual(errors, {})
        rows = self.rows()
        for key, value in changes.items():
            self.assertEqual(rows[key]["value"], value, key)
        self.assertEqual(len(backups), 1)

    def test_the_recipe_leaves_the_rest_of_the_file_alone(self):
        recipe = next(r for r in botconfig.RECIPES if r["id"] == "minds-on")
        changes = {k: v for k, v in recipe["changes"].items() if botconfig.BY_KEY[k].file == botconfig.OLLAMACHAT}
        path = os.path.join(self.tmp.name, botconfig.OLLAMACHAT)
        before = open(path, encoding="utf-8", newline="").read().splitlines()
        botconfig.apply_settings(self.tmp.name, changes, self.backups)
        after = open(path, encoding="utf-8", newline="").read().splitlines()
        self.assertEqual(len(before), len(after))
        self.assertEqual(len([1 for a, b in zip(before, after) if a != b]), len(
            [k for k, v in changes.items() if self.rows_before(before, k) != v]))

    @staticmethod
    def rows_before(lines, key):
        for line in lines:
            if line.strip().startswith(key + " ") or line.strip().startswith(key + "="):
                value = line.split("=", 1)[1].strip()
                return value[1:-1] if len(value) > 1 and value[0] == value[-1] == '"' else value
        return None

    def test_warnings_fire_for_an_empty_whitelist_and_a_disabled_gateway(self):
        warnings = botconfig.override_warnings(botconfig.read_settings(self.tmp.name))
        self.assertIn("OllamaChat.Gateway.Promote.Enable", warnings)          # whitelist is empty in conf.dist
        self.assertIn("OllamaChat.Tactical.Url", warnings)                    # gateway is off in conf.dist

    def test_tool_use_with_the_wrong_backend_is_flagged(self):
        settings = botconfig.read_settings(self.tmp.name)
        for row in settings:
            if row["key"] == "OllamaChat.Gateway.EnableToolUse":
                row["value"] = "1"
        self.assertIn("OllamaChat.Gateway.EnableToolUse", botconfig.override_warnings(settings))

    def test_the_director_is_curated_and_warns_when_jev_is_off(self):
        rows = self.rows()
        for key in ("OllamaChat.Director.Enable", "OllamaChat.Jev.Director.Enable", "OllamaChat.Jev.Director.MinConfidence",
                    "OllamaChat.Director.Announce", "OllamaChat.Director.CrowdControl"):
            self.assertIn(key, rows)
            self.assertTrue(rows[key]["present"], key)
        settings = botconfig.read_settings(self.tmp.name)
        for row in settings:
            if row["key"] in ("OllamaChat.Director.Enable", "OllamaChat.Jev.Enable"):
                row["value"] = {"OllamaChat.Director.Enable": "1", "OllamaChat.Jev.Enable": "0"}[row["key"]]
        warned = botconfig.override_warnings(settings)
        self.assertIn("OllamaChat.Director.Enable", warned)
        self.assertTrue(any("Jev is off" in text for text in warned["OllamaChat.Director.Enable"]))

    def test_the_director_is_not_told_the_gateway_is_off(self):
        # conf.dist ships with the gateway off; the director never needed it, so it must not carry that warning.
        warned = botconfig.override_warnings(botconfig.read_settings(self.tmp.name))
        self.assertNotIn("OllamaChat.Director.Announce", warned)
        self.assertNotIn("OllamaChat.Jev.Director.MinConfidence", warned)

    def test_the_director_recipe_changes_only_its_own_switches_and_reads_back(self):
        recipe = next(r for r in botconfig.RECIPES if r["id"] == "director-on")
        written, backups, errors = botconfig.apply_settings(self.tmp.name, recipe["changes"], self.backups)
        self.assertEqual(errors, {})
        rows = self.rows()
        for key, value in recipe["changes"].items():
            self.assertEqual(rows[key]["value"], value, key)


if __name__ == "__main__":
    unittest.main()
