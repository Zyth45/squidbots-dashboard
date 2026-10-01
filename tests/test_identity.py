import unittest

from mind import identity
from tests.support import chat


class IdentityTests(unittest.TestCase):
    def test_reads_bot_and_player_from_the_module_prompt(self):
        who = identity.identify(chat(20014, "Brick", 77, "Ann", "hi"))
        self.assertEqual((who.bot_guid, who.bot_name, who.player_guid, who.player_name),
                         (20014, "Brick", 77, "Ann"))

    def test_conquest_of_azeroth_two_word_names(self):
        who = identity.identify(chat(19, "Zuwe Bot", 1114, "Mindprobe", "hi"))
        self.assertEqual((who.bot_name, who.player_name), ("Zuwe Bot", "Mindprobe"))
        both = identity.identify(chat(19, "Zuwe Bot", 1114, "Ann Bot", "hi"))
        self.assertEqual((both.bot_name, both.player_name), ("Zuwe Bot", "Ann Bot"))

    def test_the_names_the_module_really_writes(self):
        # Verbatim from the module's identity block (two spaces before the parenthesis, then a long note).
        system = ("- botGuid = 19, name = Zuwe Bot  (you, the bot character)\n"
                  "- playerGuid = 1114, name = Mindprobe  (the player talking to you — when a tool needs the player's NAME, "
                  "e.g. an invite, use this one)\n")
        body = {"user": "wow-bot-19", "messages": [{"role": "system", "content": system}, {"role": "user", "content": "hi"}]}
        who = identity.identify(body)
        self.assertEqual((who.bot_guid, who.bot_name, who.player_guid, who.player_name), (19, "Zuwe Bot", 1114, "Mindprobe"))

    def test_a_missing_name_still_gives_the_guid(self):
        body = {"user": "wow-bot-19", "messages": [{"role": "system", "content": "- botGuid = 19  (you)\n- playerGuid = 5  (them)\n"}]}
        who = identity.identify(body)
        self.assertEqual((who.bot_guid, who.bot_name, who.player_guid, who.player_name), (19, "", 5, ""))

    def test_the_user_field_wins_over_a_guid_written_in_the_prompt(self):
        # A player's chat can end up inside a system prompt; it must not choose whose memory is used.
        body = chat(20014, "Brick", 77, "Ann", "hi", extra_system="botGuid = 999, name = Evil\n")
        who = identity.identify(body)
        self.assertEqual(who.bot_guid, 20014)
        self.assertEqual(who.bot_name, "Brick")

    def test_session_header_is_used_when_the_prompt_names_nobody(self):
        body = {"messages": [{"role": "system", "content": "no hint here"}, {"role": "user", "content": "hi"}]}
        who = identity.identify(body, {"x-synthiq-session-key": "wow-555-66"})
        self.assertEqual((who.bot_guid, who.player_guid), (555, 66))

    def test_user_field_alone(self):
        body = {"user": "wow-bot-42", "messages": [{"role": "user", "content": "hi"}]}
        self.assertEqual(identity.identify(body).bot_guid, 42)

    def test_unknown_request_names_nobody(self):
        who = identity.identify({"messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual(who.bot_guid, 0)

    def test_fast_lane_snapshot(self):
        body = {"messages": [{"role": "system", "content": "tick"},
                             {"role": "user", "content": '{"self": {"bot_guid": 31337, "hp": 90}}'}]}
        self.assertEqual(identity.identify(body, lane="fast").bot_guid, 31337)
        self.assertEqual(identity.identify(body, lane="smart").bot_guid, 0)

    def test_content_parts_are_read(self):
        body = {"user": "wow-bot-9", "messages": [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]}
        self.assertEqual(identity.last_user_text(body), "hello")

    def test_last_user_text_skips_tool_results(self):
        body = {"messages": [{"role": "user", "content": "invite me"},
                             {"role": "assistant", "content": None, "tool_calls": []},
                             {"role": "tool", "content": "{}"}]}
        self.assertEqual(identity.last_user_text(body), "invite me")


if __name__ == "__main__":
    unittest.main()
