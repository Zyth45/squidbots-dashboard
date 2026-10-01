import json
import unittest

from tests.support import GatewayCase, chat


def tool_round(request, call_id, name, arguments, result):
    """The request the module sends for the next round of a tool loop: the model's call and the tool's answer."""
    request["messages"] += [
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}]},
        {"role": "tool", "tool_call_id": call_id, "content": json.dumps(result)},
    ]
    return request


class ActionMemoryTests(GatewayCase):
    def test_a_follow_up_knows_which_item_the_bot_just_put_in_the_trade(self):
        first = tool_round(chat(20014, "Brick", 77, "Ann", "Sure"), "call_1", "economy",
                           {"action": "bot_trade_give", "params": {"botGuid": 20014, "playerGuid": 77, "item_id": 484325}},
                           {"ok": True, "item_id": 484325, "player_name": "Ann", "item_count": 1})
        self.gateway.handle("smart", first)
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "I dont see the sword?"))
        system = self.system_text()
        self.assertIn("WHAT YOU JUST DID IN THE GAME", system)
        self.assertIn("bot_trade_give(item_id=484325)", system)
        self.assertIn('"ok":true', system.replace(" ", ""))
        self.assertNotIn("playerGuid=", system.split("WHAT YOU JUST DID")[1])   # ids the model is told anyway are left out

    def test_a_refusal_is_remembered_too(self):
        request = tool_round(chat(20014, "Brick", 77, "Ann", "trade me it"), "call_9", "economy",
                             {"action": "bot_trade_give", "params": {"item_id": 5}}, {"error": "not_in_party"})
        self.gateway.handle("smart", request)
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "why not"))
        self.assertIn("not_in_party", self.system_text())

    def test_looking_things_up_or_asking_how_a_tool_works_is_not_remembered(self):
        request = tool_round(chat(20014, "Brick", 77, "Ann", "what do you carry"), "call_2", "core",
                             {"action": "get_inventory", "params": {}}, {"items": ["a", "b"]})
        request = tool_round(request, "call_3", "economy", {"describe": "bot_trade_give"}, {"description": "long"})
        self.gateway.handle("smart", request)
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "and now?"))
        self.assertNotIn("WHAT YOU JUST DID", self.system_text())

    def test_each_call_is_kept_once_however_many_rounds_repeat_it(self):
        request = tool_round(chat(20014, "Brick", 77, "Ann", "go"), "call_4", "core",
                             {"action": "bot_follow", "params": {}}, {"ok": True})
        self.gateway.handle("smart", request)
        self.gateway.handle("smart", request)
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "still there?"))
        self.assertEqual(self.system_text().count("bot_follow"), 1)

    def test_actions_belong_to_one_bot_and_one_player(self):
        request = tool_round(chat(20014, "Brick", 77, "Ann", "go"), "call_5", "core",
                             {"action": "bot_follow", "params": {}}, {"ok": True})
        self.gateway.handle("smart", request)
        self.gateway.handle("smart", chat(20014, "Brick", 88, "Bob", "hello"))
        self.assertNotIn("bot_follow", self.system_text())
        self.gateway.handle("smart", chat(20015, "Nym", 77, "Ann", "hello"))
        self.assertNotIn("bot_follow", self.system_text())

    def test_they_are_forgotten_after_half_an_hour(self):
        import time
        request = tool_round(chat(20014, "Brick", 77, "Ann", "go"), "call_6", "core",
                             {"action": "bot_follow", "params": {}}, {"ok": True})
        self.gateway.handle("smart", request)
        with self.gateway.lock:
            at, line, call_id = self.gateway.actions[(20014, 77)][0]
            self.gateway.actions[(20014, 77)][0] = (at - 31 * 60, line, call_id)
        self.gateway.handle("smart", chat(20014, "Brick", 77, "Ann", "hello"))
        self.assertNotIn("bot_follow", self.system_text())


if __name__ == "__main__":
    unittest.main()


class ToolRoundLimitTests(GatewayCase):
    def setUp(self):
        super().setUp()
        self.store.set_setting("plain_chat_no_tools", "0")      # these are about the round limit, not about plain chat

    def rounds(self, count):
        request = chat(20014, "Brick", 77, "Ann", "trade me your staff")
        request["tools"] = [{"type": "function", "function": {"name": "core", "parameters": {"type": "object"}}}]
        for number in range(count):
            request = tool_round(request, "call_%d" % number, "core", {"action": "get_inventory"}, {"items": []})
        return request

    def test_tools_are_withdrawn_after_the_limit_so_the_bot_must_answer(self):
        self.gateway.store.set_setting("max_tool_rounds", "4")
        self.gateway.handle("smart", self.rounds(4))
        self.assertNotIn("tools", self.provider.requests[-1]["body"])

    def test_tools_stay_until_the_limit_is_reached(self):
        self.gateway.store.set_setting("max_tool_rounds", "4")
        self.gateway.handle("smart", self.rounds(3))
        self.assertIn("tools", self.provider.requests[-1]["body"])

    def test_only_rounds_since_the_players_last_message_count(self):
        self.gateway.store.set_setting("max_tool_rounds", "2")
        request = self.rounds(3)
        request["messages"].append({"role": "assistant", "content": "done"})
        request["messages"].append({"role": "user", "content": "thanks, one more thing"})
        self.gateway.handle("smart", request)
        self.assertIn("tools", self.provider.requests[-1]["body"])


class PlainChatTests(GatewayCase):
    """A message that asks nothing of the bot is answered without the tools' schemas (most of the prompt)."""

    def ask(self, text, **more):
        request = chat(20014, "Brick", 77, "Ann", text)
        request["tools"] = [{"type": "function", "function": {"name": "core", "parameters": {"type": "object"}}}]
        request["tool_choice"] = "auto"
        request.update(more)
        self.provider.answers.append("ok")
        self.gateway.handle("smart", request)
        return self.provider.requests[-1]["body"]

    def test_conversation_is_answered_without_tools(self):
        sent = self.ask("tell me who you are, and how was the road?")
        self.assertNotIn("tools", sent)
        self.assertNotIn("tool_choice", sent)
        self.assertEqual(self.gateway.plain_chats, 1)

    def test_anything_that_could_be_a_request_keeps_the_tools(self):
        for text in ("invite me please", "can you follow me?", "what gear are you wearing", "go ahead of us", "how much gold do you have"):
            self.assertIn("tools", self.ask(text), text)

    def test_a_follow_up_to_something_the_bot_just_did_keeps_them(self):
        self.gateway._note_actions(tool_round(chat(20014, "Brick", 77, "Ann", "invite me"), "c1", "core", {"action": "invite"}, {"ok": True}),
                                   self.gateway_ident())
        self.assertIn("tools", self.ask("yes, that one"))

    def test_a_tick_with_no_player_and_the_middle_of_a_tool_round_keep_them(self):
        request = chat(20014, "Brick", 0, "", "x")
        request["messages"][0]["content"] = request["messages"][0]["content"].replace("- playerGuid = 0, name =   (the player talking to you)\n", "")
        request["tools"] = [{"type": "function", "function": {"name": "core"}}]
        self.provider.answers.append("ok")
        self.gateway.handle("smart", request)
        self.assertIn("tools", self.provider.requests[-1]["body"])
        round_one = tool_round(chat(20014, "Brick", 77, "Ann", "tell me about yourself"), "c1", "core", {"action": "get_state"}, {"hp": 100})
        round_one["tools"] = [{"type": "function", "function": {"name": "core"}}]
        self.provider.answers.append("ok")
        self.gateway.handle("smart", round_one)
        self.assertIn("tools", self.provider.requests[-1]["body"])

    def test_the_switch_turns_it_off(self):
        self.store.set_setting("plain_chat_no_tools", "0")
        self.assertIn("tools", self.ask("who are you?"))

    def gateway_ident(self):
        from mind import identity
        return identity.Identity(20014, "Brick", 77, "Ann")
