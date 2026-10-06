"""Read and write the curated bot settings in the server's .conf files.

The dashboard was read-only until now. This module is the only thing here that
writes, and it is deliberately narrow: it edits the value of settings it already
knows about, in place, and never adds, removes or reorders a line.

Every write takes a timestamped backup of the whole file first.

Editing a .conf while the server is stopped needs no reload at all, because the
files are read at startup. That is the intended way to use this.
"""
import collections
import datetime
import os
import re
import shutil

PLAYERBOTS = "playerbots.conf"
DYNAMICXP = "dynamicxp.conf"
BOTMINDS = "mod_bot_minds.conf"
OLLAMACHAT = "mod_ollama_chat.conf"     # the mod-ollama-chat fork that the mind service (mind/) serves

# The curated set. `when` says when a change is actually seen, in the page's terms:
#
#   "restart"   read when the server starts; a running server keeps the old value
#   "new bots"  read when a bot is first created, so existing bots keep their state
#   "reload"    read at startup and again on ".reload config"
#   "live"      used as soon as the file changes
#
# Where upstream does not document a reload path, "restart" is the promise made,
# because it is the one this panel can keep without a console.
Setting = collections.namedtuple(
    "Setting", "key file group label kind choices when help")

SETTINGS = [Setting(*row) for row in (
    ("AiPlayerbot.Enabled", PLAYERBOTS, "Population", "Bots enabled", "bool", None, "restart",
     "Master switch for the bot system. Off means no bots at all, random or otherwise."),
    ("AiPlayerbot.RandomBotAutologin", PLAYERBOTS, "Population", "Random bots log in by themselves", "bool", None, "restart",
     "Random bots log in on their own and live in the world. Off leaves only bots a player adds by hand."),
    ("AiPlayerbot.MinRandomBots", PLAYERBOTS, "Population", "Fewest random bots online", "int", None, "restart",
     "The server keeps at least this many random bots in the world."),
    ("AiPlayerbot.MaxRandomBots", PLAYERBOTS, "Population", "Most random bots online", "int", None, "restart",
     "The server never runs more random bots than this. More bots means more server load."),
    ("AiPlayerbot.BotActiveAlone", PLAYERBOTS, "Population", "Bots awake with no player near (%)", "int", None, "restart",
     "Share of bots that keep playing when no real player is around. 100 keeps them all active, at the cost of server load. 60 is what a 1000-bot realm was measured to need."),

    ("AiPlayerbot.RandomBotMinLevel", PLAYERBOTS, "Levels", "Lowest level a bot is given", "int", None, "new bots",
     "The bottom of the range new bots are rolled into."),
    ("AiPlayerbot.RandomBotMaxLevel", PLAYERBOTS, "Levels", "Highest level a bot is given", "int", None, "new bots",
     "The top of the range new bots are rolled into."),
    ("AiPlayerbot.DisableRandomLevels", PLAYERBOTS, "Levels", "Same starting level for every bot", "bool", None, "new bots",
     "On: every new bot starts at the starting level below instead of a random one. Bots still level up by playing."),
    ("AiPlayerbot.RandombotStartingLevel", PLAYERBOTS, "Levels", "Starting level", "int", None, "new bots",
     "The level every new bot starts at, when the same starting level is on."),
    ("AiPlayerbot.RandomBotMinLevelChance", PLAYERBOTS, "Levels", "Odds a new bot starts at the lowest level", "float", None, "new bots",
     "0 to 1. With random levels, this share of new bots start at the lowest level (1 means all of them). Bots that already exist are not touched."),
    ("AiPlayerbot.RandomBotMaxLevelChance", PLAYERBOTS, "Levels", "Odds a new bot starts at the highest level", "float", None, "new bots",
     "0 to 1. With random levels, this share of new bots start at the highest level. Checked before the lowest-level odds."),
    ("AiPlayerbot.RandomBotFixedLevel", PLAYERBOTS, "Levels", "Bots never level up", "bool", None, "restart",
     "On: bots stay at the level they have. Off: they gain levels by questing and killing like players."),
    ("AiPlayerbot.LevelBrackets.Enabled", PLAYERBOTS, "Levels", "Level Brackets (keep bots spread across levels)", "bool", None, "reload",
     "Every 5 minutes, moves bots between nine level ranges to keep every range populated, re-rolling a moved bot at its new level. While on, it overrides any starting level you set here."),
    ("AiPlayerbot.LevelBrackets.Dynamic.UseDynamicDistribution", PLAYERBOTS, "Levels", "Brackets follow real players", "bool", None, "reload",
     "With Level Brackets on, put more bots in the level ranges where real players are, instead of an even spread."),

    ("AiPlayerbot.RandomBotTalk", PLAYERBOTS, "Behaviour", "Canned bot chatter", "bool", None, "restart",
     "Playerbots' own built-in lines in say, yell, General and LFG. Kept off so the LLM chat below is not talked over."),
    ("AiPlayerbot.InviteChat", PLAYERBOTS, "Behaviour", "Bots announce group invites", "bool", None, "restart",
     "Bots say something in say or guild chat when they invite another bot to a group, raid or guild."),
    ("AiPlayerbot.AutoPickTalents", PLAYERBOTS, "Behaviour", "Bots spend talent points", "bool", None, "restart",
     "Bots spend their talent points themselves when they level up."),
    ("AiPlayerbot.LimitTalentsExpansion", PLAYERBOTS, "Behaviour", "Hold talents to their expansion", "bool", None, "restart",
     "Bots below 61 only use the talent rows Classic had, and below 71 the rows The Burning Crusade had."),

    # CoA Bots (mod-playerbots, branch coa). Harmless on another realm: absent keys are not shown.
    ("AiPlayerbot.CoaSpecRotations", PLAYERBOTS, "CoA Bots", "Written rotations for CoA specializations", "bool", None, "restart",
     "Bots play each Conquest of Azeroth specialization with its own written rotation. Off: they fall back to generic behaviour and none of the CoA rotation work reaches them."),
    ("AiPlayerbot.CoaClassesOnly", PLAYERBOTS, "CoA Bots", "Random bots use CoA classes only", "bool", None, "new bots",
     "New random bots are created in the Conquest of Azeroth classes only."),
    ("AiPlayerbot.CoaSmartHeal", PLAYERBOTS, "CoA Bots", "Smarter healers", "bool", None, "restart",
     "CoA healers keep their mana for healing and pick who to heal by need."),
    ("AiPlayerbot.CoaSmartTank", PLAYERBOTS, "CoA Bots", "Damage dealers let the tank open", "bool", None, "restart",
     "In a group with a tank, CoA damage dealers wait for the tank to take the target first."),
    ("AiPlayerbot.CoaTankOpenerSeconds", PLAYERBOTS, "CoA Bots", "Longest wait for the tank (seconds)", "int", None, "reload",
     "With the setting above: how long a damage dealer waits on a target no tank has touched, then goes all out. 0: no wait."),
    ("AiPlayerbot.CoaExcludedSpecializations", PLAYERBOTS, "CoA Bots", "Specializations bots never use", "ids", None, "restart",
     "Specialization numbers separated by commas. 99 (Bloodmage Eternal) is left out by default: it cannot taunt until the core grants its form."),
    ("AiPlayerbot.CoaGroupTelemetry", PLAYERBOTS, "CoA Bots", "Group fight report in CoaBots.log", "bool", None, "restart",
     "Writes a report at the end of every fight of a group with a real player in it (health, deaths, healing, mana). For measuring; off on a normal realm."),
    ("AiPlayerbot.CoaLfgBots", PLAYERBOTS, "CoA Bots", "Bots answer \"lfg bot\" in chat", "bool", None, "reload",
     "A player who says \"lfg bot heal\", \"lfg bot tank\" or \"lfg bot\" in a listened channel is whispered by free bots able to play those roles."),

    # The live view of this dashboard: mod-playerbots (branch coa) writes a snapshot of every bot.
    ("AiPlayerbot.CoaStatusFile", PLAYERBOTS, "Dashboard live view", "Live status file", "quoted", None, "reload",
     "Where the server writes each bot's health, power and current action for this dashboard's map and cards. "
     "Put it next to CoaBots.log (logs\\bot-status.json) and the dashboard finds it by itself. Empty: not written."),
    ("AiPlayerbot.CoaStatusIntervalSeconds", PLAYERBOTS, "Dashboard live view", "Refresh every (seconds)", "int", None, "reload",
     "How often the live status file is rewritten. Under a millisecond of server time per snapshot with 1000 bots."),

    # Channels and bot chat. Conquest of Azeroth numbers and names its channels differently from a
    # stock client: with the stock values bot broadcasts are dropped or land in the wrong channel.
    ("AiPlayerbot.ZoneChannelId", PLAYERBOTS, "Channels and chat", "Zone channel number", "int", None, "restart",
     "The number of the Zone channel. Conquest of Azeroth uses 3, not the stock 1."),
    ("AiPlayerbot.BroadcastWorldChannelName", PLAYERBOTS, "Channels and chat", "Realm-wide channel name", "quoted", None, "restart",
     "Conquest of Azeroth calls it Ascension. Until this matches, every broadcast meant for it is dropped."),
    ("AiPlayerbot.BroadcastToWorldGlobalChance", PLAYERBOTS, "Channels and chat", "Bot chatter in the realm-wide channel", "int", None, "restart",
     "0 to 30000; 0 keeps bots out of the realm-wide channel, which everybody reads. Their chatter belongs in Zone."),
    ("AiPlayerbot.BotTextLocale", PLAYERBOTS, "Channels and chat", "Language of the bots' chat", "choice",
     ["-1", "0", "2", "3", "6", "8"], "restart",
     "The language of everything bots say on their own: channels, say, whispers, replies (the ai_playerbot_texts lines). "
     "Auto follows the game client of the players online. Without AI."),
    ("AiPlayerbot.BotsWhisperPublic", PLAYERBOTS, "Channels and chat", "Bots whisper unasked", "bool", None, "restart",
     "On: bots whisper a player who writes in a channel, and tell their master every potion and buff. Off: a word in a channel no longer brings a wall of whispers."),
    ("AiPlayerbot.PublicReplyChance", PLAYERBOTS, "Channels and chat", "Bots answering a channel message (%)", "int", None, "restart",
     "How many of the bots that read a player's channel message may answer. High values bury the player; a bot called by name always answers."),

    ("Dynamic.XP.Preset", DYNAMICXP, "Experience", "Realm XP rate", "choice", ["0", "1", "3", "5", "7"], "reload",
     "XP multiplier for every character that has not picked its own: 1 is normal, 3, 5 or 7 times as fast, or 0 for the per-level curve."),
    ("Dynamic.XP.Preset.PlayerChoice", DYNAMICXP, "Experience", "Players may pick their own rate", "bool", None, "reload",
     "Lets any player change their own rate with .xp 1, 3, 5, 7 or dynamic. Off: game masters only."),
    ("Dynamic.XP.Rate", DYNAMICXP, "Experience", "Per-level XP curve available", "bool", None, "reload",
     "Turns on the per-level XP curve (faster at higher levels) that rate 0 and .xp dynamic use."),

    # Bot LLM chat, from mod-bot-minds. `.botminds reload` re-reads the file, but
    # "restart" is the promise this panel can keep without a console.
    ("BotMinds.Enable", BOTMINDS, "Bot chat (LLM)", "LLM chat on", "bool", None, "restart",
     "Bots write their own lines with the local language model. Off: they stay quiet (canned chatter is also off)."),
    ("BotMinds.Model", BOTMINDS, "Bot chat (LLM)", "Language model", "text", None, "restart",
     "The Ollama model that writes bot lines. It must support tool calls."),
    ("BotMinds.Url", BOTMINDS, "Bot chat (LLM)", "Ollama address", "text", None, "restart",
     "Where Ollama is listening. The default is this machine."),
    ("BotMinds.SayDistance", BOTMINDS, "Bot chat (LLM)", "Earshot in yards", "float", None, "restart",
     "How far away a bot hears say and yell, and how far it looks for something to remark on."),
    ("BotMinds.Route.HandleChannel", BOTMINDS, "Bot chat (LLM)", "Answer in General, Trade and LFG", "bool", None, "restart",
     "Bots answer in the numbered channels as well as in say and party."),
    ("BotMinds.ReplyChance.Say", BOTMINDS, "Bot chat (LLM)", "Chance to answer you nearby (%)", "int", None, "restart",
     "Out of 100: how often a bot answers something said near it."),
    ("BotMinds.ReplyChance.Channel", BOTMINDS, "Bot chat (LLM)", "Chance to answer in channels (%)", "int", None, "restart",
     "Out of 100: how often a channel message gets an answer from a bot."),
    ("BotMinds.ReplyChance.BotToBot", BOTMINDS, "Bot chat (LLM)", "Chance bots answer each other (%)", "int", None, "restart",
     "Out of 100: how often a bot picks up another bot's line. Only happens where a real player can see it."),
    ("BotMinds.Ambient.Chance", BOTMINDS, "Bot chat (LLM)", "Idle chatter (%)", "int", None, "restart",
     "Out of 100: how often a bot near a real player says something unprompted."),
    ("BotMinds.Ambient.Channel.General", BOTMINDS, "Bot chat (LLM)", "Idle chatter in General", "bool", None, "restart",
     "Unprompted bot lines may go to General."),
    ("BotMinds.Ambient.Channel.Trade", BOTMINDS, "Bot chat (LLM)", "Idle chatter in Trade", "bool", None, "restart",
     "Unprompted bot lines may go to Trade, in cities."),
    ("BotMinds.WorkerThreads", BOTMINDS, "Bot chat (LLM)", "Lines written at once", "int", None, "restart",
     "How many bot lines the model writes at the same time. Higher answers faster but loads the machine."),
    ("BotMinds.Limits.MaxCallsPerMinute", BOTMINDS, "Bot chat (LLM)", "Lines per minute, whole realm", "int", None, "restart",
     "A ceiling on model calls per minute across every bot. 0 removes the ceiling."),

    # Bot personalities and memory: the mod-ollama-chat fork, answered by the mind service (mind/, docs/minds.md).
    # The Minds page holds everything that can change while the server runs; these are the module's own switches.
    ("OllamaChat.Gateway.Enable", OLLAMACHAT, "Minds (mod-ollama-chat)", "Bots talk with a language model", "bool", None, "ollama reload",
     "Master switch for conversations. Off: bots stay ordinary playerbots."),
    ("OllamaChat.Gateway.Url", OLLAMACHAT, "Minds (mod-ollama-chat)", "Mind service address", "quoted", None, "ollama reload",
     "Where conversations are sent. The mind service on this machine listens at http://127.0.0.1:18800/v1/chat/completions."),
    ("OllamaChat.EnableWhisperReplies", OLLAMACHAT, "Minds (mod-ollama-chat)", "Bots answer whispers", "bool", None, "ollama reload",
     "Upstream ships this off, and with it off a whisper to a bot is ignored whatever else is switched on."),
    ("OllamaChat.AnswerAddressedInCombat", OLLAMACHAT, "Minds (mod-ollama-chat)", "A bot you speak to answers even in a fight", "bool", None, "ollama reload",
     "Bots that hunt are in combat most of the time. On: a bot you whisper or call by name still answers; unprompted chatter waits for the fight to end. Off: it stays silent until it is out of combat."),
    ("OllamaChat.Gateway.MinSecondsBetweenRequests", OLLAMACHAT, "Minds (mod-ollama-chat)", "Least seconds between your messages to one bot", "int", None, "ollama reload",
     "A message that arrives sooner than this after your last one to the same bot is dropped without a word. Upstream ships 5, which loses ordinary quick replies; 2 protects the budget without that. 0 removes the limit."),
    ("OllamaChat.Gateway.MaxToolIterations", OLLAMACHAT, "Minds (mod-ollama-chat)", "Most tool steps a bot takes per message", "int", None, "ollama reload",
     "Looking up gear, then bags, then acting is several steps. Upstream ships 3, and a bot that runs out says nothing at all. The mind service also withdraws the tools after its own limit, so a high number cannot loop forever."),
    ("OllamaChat.Gateway.Type", OLLAMACHAT, "Minds (mod-ollama-chat)", "Backend type", "quoted", None, "ollama reload",
     "synthiq lets a bot call the game itself (bags, gear, quests, invites). The mind service needs it. openclaw ignores tools."),
    ("OllamaChat.Gateway.EnableToolUse", OLLAMACHAT, "Minds (mod-ollama-chat)", "Bots may use game tools", "bool", None, "ollama reload",
     "Lets the model look at a bot's real bags, gear and quests and act (invite you, sell junk) instead of guessing."),
    ("OllamaChat.Mcp.AllowActionTools", OLLAMACHAT, "Minds (mod-ollama-chat)", "Bots may act when asked", "bool", None, "ollama reload",
     "Lets an awake bot do things, not just talk: invite you, follow, stay, sell junk, use an item, cast. Only players on the whitelist can ask. Off: it can look at its bags and quests but not act."),
    ("OllamaChat.Mcp.ActionRateLimitPerBotPerMinute", OLLAMACHAT, "Minds (mod-ollama-chat)", "Actions per bot per minute", "int", None, "ollama reload",
     "A ceiling on how often one bot may act, so a confused model cannot loop."),
    ("OllamaChat.Gateway.InjectIdentity", OLLAMACHAT, "Minds (mod-ollama-chat)", "Tell the model who is talking", "bool", None, "ollama reload",
     "Puts the bot's and the player's guid and name in every request. Without it the mind service cannot tell players apart and remembers nothing."),
    ("OllamaChat.Gateway.MergePersonalityPrompt", OLLAMACHAT, "Minds (mod-ollama-chat)", "Also use the module's own personality templates", "bool", None, "ollama reload",
     "Off while the mind service writes personalities: two personalities in one prompt contradict each other."),
    ("OllamaChat.Gateway.TriggerKeyword", OLLAMACHAT, "Minds (mod-ollama-chat)", "Word a message must contain", "quoted", None, "ollama reload",
     "Upstream ships \"claude\": a whisper is ignored unless it contains that word. Empty means every whisper to a bot is heard."),
    ("OllamaChat.Gateway.WhitelistAccountIds", OLLAMACHAT, "Minds (mod-ollama-chat)", "Accounts that can wake bots", "quoted", None, "ollama reload",
     "Account ids separated by commas (the id column of acore_auth.account). Only these players can start a bot talking. Empty: nobody can, which keeps a busy realm from spending your model budget."),
    ("OllamaChat.Gateway.Promote.Enable", OLLAMACHAT, "Minds (mod-ollama-chat)", "Any bot wakes when you talk to it", "bool", None, "ollama reload",
     "Whisper a bot or say its name and it answers as itself for a while; invite it and it stays awake as a companion until you remove it. Everyone else stays an ordinary bot."),
    ("OllamaChat.Gateway.Promote.ChatTtlSec", OLLAMACHAT, "Minds (mod-ollama-chat)", "A bot stays awake after your last word (seconds)", "int", None, "ollama reload",
     "How long a bot you only talked to keeps answering. Bots in your group do not time out."),
    ("OllamaChat.Gateway.Promote.MaxChatBots", OLLAMACHAT, "Minds (mod-ollama-chat)", "Most bots awake at once from chat", "int", None, "ollama reload",
     "Beyond this the bot you spoke to longest ago goes back to sleep. Group members do not count."),
    ("OllamaChat.Gateway.Promote.Channels", OLLAMACHAT, "Minds (mod-ollama-chat)", "Where naming a bot wakes it", "quoted", None, "ollama reload",
     "Comma separated: whisper, party, raid, guild, officer, say, yell, general. General is answered by whisper so a long reply does not flood the channel."),
    ("OllamaChat.Ambient.Enable", OLLAMACHAT, "Minds (mod-ollama-chat)", "Bots answer a hello nearby", "bool", None, "ollama reload",
     "Say hi in /say, /yell, the zone channel, Trade or LFG without naming anyone and the bots in earshot answer in their own voices, and sometimes each other. Only whitelisted players start it. Uses the Ambient chat model (or Quick decisions): a few tenths of a cent a line."),
    ("OllamaChat.MaxBotsToPick", OLLAMACHAT, "Minds (mod-ollama-chat)", "Most bots that answer one line", "int", None, "ollama reload",
     "A random number from 1 up to this many of the bots in earshot answer a line. 3 or 4 feels like a street; 1 like a single stranger."),
    ("OllamaChat.Ambient.ChainChance", OLLAMACHAT, "Minds (mod-ollama-chat)", "Chance a bot answers another bot's line (%)", "int", None, "ollama reload",
     "After a bot answers you, each other bot in earshot has this chance to answer that answer, so they talk among themselves."),
    ("OllamaChat.Ambient.ChainMaxDepth", OLLAMACHAT, "Minds (mod-ollama-chat)", "How many bot-to-bot replies deep", "int", None, "ollama reload",
     "2 lets a bot answer you, another answer it, and a third answer that; then it stops."),
    ("OllamaChat.Ambient.MaxLinesPerScene", OLLAMACHAT, "Minds (mod-ollama-chat)", "Most lines in one conversation", "int", None, "ollama reload",
     "A ceiling on the whole exchange after one line of yours, so a busy street does not fill your chat window."),
    ("OllamaChat.Ambient.BotCooldownSec", OLLAMACHAT, "Minds (mod-ollama-chat)", "A bot speaks at most once every (seconds)", "int", None, "ollama reload",
     "Keeps one bot from answering everything."),
    ("OllamaChat.Ambient.Channels", OLLAMACHAT, "Minds (mod-ollama-chat)", "Where bots answer a hello", "quoted", None, "ollama reload",
     "Comma separated: say, yell, zone, trade, lfg, world."),
    ("OllamaChat.Ambient.RewriteStockLines", OLLAMACHAT, "Minds (mod-ollama-chat)", "Bots say their stock chatter in their own words", "bool", None, "ollama reload",
     "The ready-made lines playerbots posts in General, Trade and /say (\"Took [quest]. Time to dive in.\", \"WTS Cloth\") are held back and said again in the bot's own personality, with item and quest links kept, whenever a whitelisted player is near. Nobody near: nothing changes."),
    ("OllamaChat.Ambient.RewriteRangeYards", OLLAMACHAT, "Minds (mod-ollama-chat)", "Rewrite stock chatter within (yards) of you", "int", None, "ollama reload",
     "Only bots this close to a whitelisted player pay for a rewrite; the rest stay stock."),
    ("OllamaChat.Ambient.RewriteScenePercent", OLLAMACHAT, "Minds (mod-ollama-chat)", "Chance a rewritten remark starts a chat (%)", "int", None, "ollama reload",
     "Bots nearby may answer the remark, and each other, for up to 45 seconds."),
    ("OllamaChat.Ambient.SceneWindowSec", OLLAMACHAT, "Minds (mod-ollama-chat)", "Bots keep talking among themselves for (seconds)", "int", None, "ollama reload",
     "After a line of yours, the bots there may go on answering each other for this long."),
    ("OllamaChat.Ambient.StaggerMs", OLLAMACHAT, "Minds (mod-ollama-chat)", "Gap between bots answering the same line (ms)", "int", None, "ollama reload",
     "Bots that heard the same line answer one after another at about this interval, plus typing time."),
    ("OllamaChat.Ambient.MaxLineChars", OLLAMACHAT, "Minds (mod-ollama-chat)", "Longest ambient chat line (characters)", "int", None, "ollama reload",
     "A chat line holds 255. Real players type short lines: 110 keeps them that way."),
    ("OllamaChat.Jev.Enable", OLLAMACHAT, "Minds (mod-ollama-chat)", "Jev: use TypeSafe's decision model", "bool", None, "restart",
     "Jev picks between options in about 0.4 s for a fraction of a cent and cannot write text. It takes routine decisions off the language model; anything it is unsure of goes to the model as before. Needs a TypeSafe key in the server's environment (AC_OLLAMA_CHAT_JEV_API_KEY): never put it in a config file. See the Jev card on the Minds page for what it saves."),
    ("OllamaChat.Jev.Tactical.Enable", OLLAMACHAT, "Minds (mod-ollama-chat)", "Jev decides awake bots' routine looks-around", "bool", None, "ollama reload",
     "The tactical loop's most common answer is 'nothing to do'. Jev makes that call; the model handles anything else."),
    ("OllamaChat.Jev.Tactical.MinConfidence", OLLAMACHAT, "Minds (mod-ollama-chat)", "How sure Jev must be to decide a look-around", "float", None, "ollama reload",
     "0 to 1. Lower lets Jev decide more (cheaper); higher hands more to the model."),
    ("OllamaChat.Jev.Classifier.Enable", OLLAMACHAT, "Minds (mod-ollama-chat)", "Jev handles short commands", "bool", None, "ollama reload",
     "A short command to a bot (invite me, follow, stay) is read by Jev instead of the model's full conversation call, and acted on when Jev is sure."),
    ("OllamaChat.Jev.Classifier.MinConfidence", OLLAMACHAT, "Minds (mod-ollama-chat)", "How sure Jev must be to act on a command", "float", None, "ollama reload",
     "0 to 1. The shipped 0.8 acts only when Jev is quite sure; a command it doubts goes to the bot's normal conversation."),
    ("OllamaChat.Jev.TimeoutMs", OLLAMACHAT, "Minds (mod-ollama-chat)", "Longest Jev may take (ms)", "int", None, "ollama reload",
     "Past this the decision goes to the language model."),
    ("OllamaChat.LocalChannelNames", OLLAMACHAT, "Minds (mod-ollama-chat)", "Zone channels (a bot must be in your zone)", "quoted", None, "ollama reload",
     "Channel names, comma separated, that only reach bots in the same zone as you. Conquest of Azeroth's per-zone channel is \"Zone - <place>\", so it needs Zone -."),
    ("OllamaChat.GlobalChannelNames", OLLAMACHAT, "Minds (mod-ollama-chat)", "Realm-wide channels", "quoted", None, "ollama reload",
     "Channel names, comma separated, that reach bots in any zone. Conquest of Azeroth's realm channel is Ascension."),
    ("OllamaChat.Tactical.Enable", OLLAMACHAT, "Minds (mod-ollama-chat)", "Awake bots react to what happens", "bool", None, "ollama reload",
     "A small, frequent model call per awake bot near you: short remarks, emotes, ready checks. Uses the quick-decision model."),
    ("OllamaChat.Tactical.AmbientEnable", OLLAMACHAT, "Minds (mod-ollama-chat)", "Awake bots make idle remarks", "bool", None, "ollama reload",
     "Contextual emotes and short lines while a real player is near. Silent when nobody is there to hear it."),
    ("OllamaChat.Tactical.Url", OLLAMACHAT, "Minds (mod-ollama-chat)", "Quick-decision address", "quoted", None, "ollama reload",
     "The mind service's fast lane: http://127.0.0.1:18800/fast/v1/chat/completions."),
    ("OllamaChat.Tactical.HeartbeatMs", OLLAMACHAT, "Minds (mod-ollama-chat)", "Awake bots look around every (ms)", "int", None, "restart",
     "How often each awake bot near you makes a quick-decision call. 10000 is about one call every 10 seconds, roughly 3,000 tokens each: the main running cost of a bot in your party. Raise it to spend less; the bot then reacts more slowly."),
    ("OllamaChat.Tactical.NearbyBotRadius", OLLAMACHAT, "Minds (mod-ollama-chat)", "Awake bots within (yards)", "float", None, "ollama reload",
     "Bots this close to a whitelisted player join the quick-decision loop."),
    ("OllamaChat.Tactical.MaxConcurrentQueries", OLLAMACHAT, "Minds (mod-ollama-chat)", "Quick-decision calls in flight at once", "int", None, "ollama reload",
     "The nearby bots' calls in one look-around share a 5 second budget. With 1 they queue behind each other and the last ones time out before they are sent (a third of the calls failed on the test realm with five bots near). Use about as many as the most nearby bots; 1 is only right for a single local GPU."),
    ("OllamaChat.Tactical.NearbyBotMax", OLLAMACHAT, "Minds (mod-ollama-chat)", "Most nearby bots in that loop", "int", None, "ollama reload",
     "A cap on the model calls the nearby bots cost."),
    ("OllamaChat.Tactical.AmbientMaxVisibleActionsPerMinute", OLLAMACHAT, "Minds (mod-ollama-chat)", "Idle remarks per bot per minute", "int", None, "ollama reload",
     "So a bot never floods the screen. 0 removes the cap."),
    # The combat director (docs/director.md in the synthiqbots fork): Jev picks the fight's targets, playerbots still fights.
    ("OllamaChat.Director.Enable", OLLAMACHAT, "Minds (mod-ollama-chat)", "Companions fight as a team", "bool", None, "ollama reload",
     "While your party fights, a quick decision model picks the enemy to kill first (a skull appears on it), whether to crowd-control one, and whether the healers should ration mana. The bots still do the fighting, and a mark you put up yourself is left alone. Needs Jev on. Off: every bot picks its own target."),
    ("OllamaChat.Jev.Director.Enable", OLLAMACHAT, "Minds (mod-ollama-chat)", "Jev picks the fight's targets", "bool", None, "ollama reload",
     "The director's decisions come from Jev: about 0.3 seconds and 0.005 cents each, one every 2.5 seconds of a real fight."),
    ("OllamaChat.Jev.Director.MinConfidence", OLLAMACHAT, "Minds (mod-ollama-chat)", "How sure Jev must be to pick a target", "float", None, "ollama reload",
     "0 to 1. The shipped 0.6 acts only on a clear call; an unsure answer leaves the bots choosing for themselves."),
    ("OllamaChat.Director.Announce", OLLAMACHAT, "Minds (mod-ollama-chat)", "A companion says the plan in party chat", "bool", None, "ollama reload",
     "\"Focus the Defias Conjurer\", in that bot's own voice, at most once every 8 seconds. Off: the skull appears and nobody says anything."),
    ("OllamaChat.Director.CrowdControl", OLLAMACHAT, "Minds (mod-ollama-chat)", "The director may crowd-control an enemy", "bool", None, "ollama reload",
     "Only for the classes whose crowd control the bots aim at the moon mark: mage, rogue, hunter, warlock and druid. Conquest of Azeroth's own classes ignore it."),
)]

BY_KEY = {entry.key: entry for entry in SETTINGS}

# What a choice means, for the page. The value is what the .conf holds.
CHOICE_LABELS = {
    "AiPlayerbot.BotTextLocale": {"-1": "Auto (the players' game client)", "0": "English", "2": "Français",
                                  "3": "Deutsch", "6": "Español", "8": "Русский"},
}

# Settings a .conf may not have yet (mod-playerbots reads them, its .conf.dist did not list them):
# shown with their default, and added at the end of the file the first time they are changed.
# Every other setting is only ever edited in place.
ADDABLE = {
    "AiPlayerbot.BotTextLocale": ("-1", [
        "AiPlayerbot.BotTextLocale",
        "    Description: Language of the bots' own lines (ai_playerbot_texts).",
        "                 -1 follows the game client of the players online; 0 enUS, 1 koKR, 2 frFR,",
        "                 3 deDE, 4 zhCN, 5 zhTW, 6 esES, 7 esMX, 8 ruRU forces one.",
        "    Default:     -1 (added by the SquidBots dashboard)"]),
}

_CHANCES = ["AiPlayerbot.RandomBotMinLevelChance", "AiPlayerbot.RandomBotMaxLevelChance"]
_LLM = [s.key for s in SETTINGS if s.file == BOTMINDS and s.key != "BotMinds.Enable"]
# The director needs Jev, not the language-model gateway, so the "bots are not talking" warning does not apply to it.
_MINDS = [s.key for s in SETTINGS if s.file == OLLAMACHAT and s.key != "OllamaChat.Gateway.Enable"
          and not s.key.startswith(("OllamaChat.Director.", "OllamaChat.Jev.Director."))]
_WAKING = [s.key for s in SETTINGS if s.key.startswith("OllamaChat.Gateway.Promote.")]

# When every "if" setting has the given value, each "warn" setting shows the text.
# The page evaluates this same table as values are edited, so the rules live once.
OVERRIDES = [
    {"if": {"AiPlayerbot.LevelBrackets.Enabled": "1"},
     "warn": _CHANCES + ["AiPlayerbot.DisableRandomLevels", "AiPlayerbot.RandombotStartingLevel"],
     "text": "Level Brackets is on: every 5 minutes it moves bots between level ranges, so "
             "starting levels do not last. Turn Level Brackets off for this to stick."},
    {"if": {"AiPlayerbot.DisableRandomLevels": "0"},
     "warn": ["AiPlayerbot.RandombotStartingLevel"],
     "text": "Only used while \"Same starting level for every bot\" is on."},
    {"if": {"AiPlayerbot.DisableRandomLevels": "1"},
     "warn": _CHANCES,
     "text": "Ignored while \"Same starting level for every bot\" is on."},
    {"if": {"AiPlayerbot.LevelBrackets.Enabled": "0"},
     "warn": ["AiPlayerbot.LevelBrackets.Dynamic.UseDynamicDistribution"],
     "text": "Only used while Level Brackets is on."},
    {"if": {"Dynamic.XP.Preset": "0", "Dynamic.XP.Rate": "0"},
     "warn": ["Dynamic.XP.Preset"],
     "text": "Rate 0 means the per-level curve, which is switched off below, so this gives normal XP."},
    {"if": {"BotMinds.Route.HandleChannel": "0"},
     "warn": ["BotMinds.ReplyChance.Channel"],
     "text": "Bots do not answer in channels at all while \"Answer in General, Trade and LFG\" is off."},
    {"if": {"BotMinds.Enable": "0"},
     "warn": _LLM,
     "text": "LLM chat is off, so this has no effect."},
    {"if": {"OllamaChat.Gateway.Enable": "0"},
     "warn": _MINDS,
     "text": "Bots are not talking with a language model (the first setting in this group is off), so this has no effect."},
    {"if": {"OllamaChat.Gateway.WhitelistAccountIds": ""},
     "warn": _WAKING,
     "text": "Nobody is listed under \"Accounts that can wake bots\", and with an empty list waking is switched off: no bot will answer anyone."},
    {"if": {"OllamaChat.EnableWhisperReplies": "0", "OllamaChat.Gateway.Enable": "1"},
     "warn": ["OllamaChat.EnableWhisperReplies"],
     "text": "Off: a whisper to a bot is ignored, so the most direct way to talk to one does nothing."},
    {"if": {"OllamaChat.Gateway.EnableToolUse": "1", "OllamaChat.Gateway.Type": "openclaw"},
     "warn": ["OllamaChat.Gateway.EnableToolUse"],
     "text": "Tools are only sent to backend type synthiq. With openclaw they are ignored."},
    {"if": {"OllamaChat.Director.Enable": "1", "OllamaChat.Jev.Enable": "0"},
     "warn": ["OllamaChat.Director.Enable"],
     "text": "Jev is off, and the director's decisions come from Jev, so it does nothing."},
    {"if": {"OllamaChat.Director.Enable": "1", "OllamaChat.Jev.Director.Enable": "0"},
     "warn": ["OllamaChat.Director.Enable"],
     "text": "\"Jev picks the fight's targets\" is off, so the director has nobody to ask and does nothing."},
    {"if": {"OllamaChat.Gateway.InjectIdentity": "0", "OllamaChat.Gateway.Enable": "1"},
     "warn": ["OllamaChat.Gateway.InjectIdentity"],
     "text": "Off: the mind service cannot tell players apart, so bots remember nothing between conversations."},
]

# A recipe is a named set of changes, shown as a before and after list first.
RECIPES = [
    {"id": "fresh-level-1",
     "title": "Fresh world: every bot starts at level 1",
     "summary": "New bots start at level 1 in their starting zones and level up by playing. "
                "Level Brackets is turned off so nothing moves them afterwards.",
     "changes": {"AiPlayerbot.DisableRandomLevels": "1",
                 "AiPlayerbot.RandombotStartingLevel": "1",
                 "AiPlayerbot.LevelBrackets.Enabled": "0"},
     "after": "Takes effect for new bots after a restart. Bots that already exist keep their "
              "level until they are re-created."},
    {"id": "spread-levels",
     "title": "Mixed levels: bots spread from 1 to max",
     "summary": "The repack's own setup: random starting levels, and Level Brackets keeping "
                "every level range populated, weighted towards where real players are.",
     "changes": {"AiPlayerbot.DisableRandomLevels": "0",
                 "AiPlayerbot.LevelBrackets.Enabled": "1",
                 "AiPlayerbot.LevelBrackets.Dynamic.UseDynamicDistribution": "1"},
     "after": "Level Brackets starts moving bots within 5 minutes of a restart."},
]
RECIPES.insert(0, {
    "id": "coa-v14",
    "title": "CoA Bots v1.4: the recommended settings",
    "summary": "What the v1.4 release ships: 200 bots, 60% awake, Conquest of Azeroth's channel number "
               "and name, no whisper flood, the written rotations on and Bloodmage Eternal left out.",
    "changes": {"AiPlayerbot.MinRandomBots": "200", "AiPlayerbot.MaxRandomBots": "200",
                "AiPlayerbot.BotActiveAlone": "60",
                "AiPlayerbot.ZoneChannelId": "3", "AiPlayerbot.BroadcastWorldChannelName": "Ascension",
                "AiPlayerbot.BroadcastToWorldGlobalChance": "0",
                "AiPlayerbot.BotsWhisperPublic": "0", "AiPlayerbot.PublicReplyChance": "5",
                "AiPlayerbot.CoaSpecRotations": "1", "AiPlayerbot.CoaExcludedSpecializations": "99",
                "AiPlayerbot.CoaGroupTelemetry": "0", "AiPlayerbot.CoaLfgBots": "1"},
    "after": "Takes effect at the next server start."})
RECIPES.insert(1, {
    "id": "minds-on",
    "title": "Minds on: bots with personalities and memory",
    "summary": "Points the module at the mind service on this machine (python run-mind.py) and switches on tools, waking a bot "
               "by talking to it, and the player identity the memory needs. It leaves the whitelist alone: add your account id "
               "under Minds afterwards, or no bot will wake.",
    "changes": {"OllamaChat.Gateway.Enable": "1", "OllamaChat.EnableWhisperReplies": "1", "OllamaChat.AnswerAddressedInCombat": "1",
                "OllamaChat.Gateway.MinSecondsBetweenRequests": "2",
                "OllamaChat.Gateway.MaxToolIterations": "50",
                "OllamaChat.Gateway.Type": "synthiq",
                "OllamaChat.Gateway.Url": "http://127.0.0.1:18800/v1/chat/completions",
                "OllamaChat.Gateway.EnableToolUse": "1", "OllamaChat.Mcp.AllowActionTools": "1",
                "OllamaChat.Gateway.InjectIdentity": "1", "OllamaChat.Gateway.TriggerKeyword": "",
                "OllamaChat.Gateway.MergePersonalityPrompt": "0", "OllamaChat.Gateway.Promote.Enable": "1",
                "OllamaChat.Ambient.Enable": "1", "OllamaChat.Ambient.RewriteStockLines": "1", "OllamaChat.MaxBotsToPick": "3",
                "OllamaChat.LocalChannelNames": "General -,Trade -,LocalDefense -,Zone -",
                "OllamaChat.GlobalChannelNames": "World,LookingForGroup,Ascension",
                "OllamaChat.Tactical.Enable": "1",
                "OllamaChat.Tactical.Url": "http://127.0.0.1:18800/fast/v1/chat/completions",
                "OllamaChat.Tactical.MaxConcurrentQueries": "4",
                "AiPlayerbot.RandomBotTalk": "0"},
    "after": "Type .ollama reload in game or restart the server. Then choose a model on the Minds page and press Test."})
RECIPES.insert(2, {
    "id": "director-on",
    "title": "Combat director: the party fights as a team",
    "summary": "Switches on Jev and the director. While you fight with companions, Jev picks the enemy to kill first (a skull appears on "
               "it), and a companion says so in party chat. Playerbots still does the fighting.",
    "changes": {"OllamaChat.Jev.Enable": "1", "OllamaChat.Jev.Director.Enable": "1", "OllamaChat.Director.Enable": "1"},
    "after": "Jev needs a TypeSafe key (see the module's docs/jev.md). Restart the server, or type .ollama reload if Jev was already on."})
_RECIPES = {recipe["id"]: recipe for recipe in RECIPES}


def override_warnings(settings):
    """{key: [warning, ...]} for the given settings (read_settings rows)."""
    current = {row["key"]: row["value"] for row in settings}
    out = {}
    for rule in OVERRIDES:
        if all(current.get(key) == value for key, value in rule["if"].items()):
            for key in rule["warn"]:
                out.setdefault(key, []).append(rule["text"])
    return out


def recipe_diff(settings, recipe_id):
    """The rows a recipe would change: [{key, label, from, to}]. KeyError if unknown."""
    recipe = _RECIPES[recipe_id]
    current = {row["key"]: row["value"] for row in settings}
    return [{"key": key, "label": BY_KEY[key].label, "from": current.get(key), "to": value}
            for key, value in recipe["changes"].items() if current.get(key) != value]

# A setting line looks like "Key.Name = value", optionally indented.
def _line_re(key):
    # Spaces and tabs only: \s would reach across the line end and eat the blank line after it.
    return re.compile(r"^([ \t]*%s[ \t]*=[ \t]*)([^\r\n]*?)([ \t]*)(?=\r?$)" % re.escape(key), re.M)


def config_dir(repack_root, bots=True):
    """Where the module .conf files live. The bots server has its own set."""
    if bots:
        return os.path.join(repack_root, "CoA-Bots", "Core", "configs", "modules")
    return os.path.join(repack_root, "Core", "configs", "modules")


def read_settings(conf_dir):
    """Current value of every curated setting. Missing files and keys are reported,
    not raised: the dashboard has to work on a half-configured install too."""
    cache = {}
    out = []
    for key, filename, group, label, kind, choices, when, help_text in SETTINGS:
        if filename not in cache:
            path = os.path.join(conf_dir, filename)
            try:
                cache[filename] = open(path, encoding="utf-8-sig", errors="replace").read()
            except OSError:
                cache[filename] = None
        text = cache[filename]
        value, present = None, False
        if text is not None:
            match = _line_re(key).search(text)
            if match:
                value, present = match.group(2).strip(), True
                if kind == "quoted" and len(value) >= 2 and value[0] == value[-1] == '"':
                    value = value[1:-1]
            elif key in ADDABLE:
                value, present = ADDABLE[key][0], True       # the module's default until it is written
        out.append({"key": key, "file": filename, "group": group, "label": label,
                    "kind": kind, "choices": choices, "when": when, "help": help_text,
                    "value": value, "present": present, "labels": CHOICE_LABELS.get(key)})
    return out


def validate(key, value):
    """Return an error string, or None when the value is acceptable."""
    entry = BY_KEY.get(key)
    if not entry:
        return "unknown setting"
    kind, choices = entry[4], entry[5]
    text = str(value).strip()
    if text == "" and kind != "quoted":
        return "value is empty"
    if kind == "bool":
        if text not in ("0", "1"):
            return "expected 0 or 1"
    elif kind == "int":
        if not re.match(r"^-?\d+$", text):
            return "expected a whole number"
    elif kind == "float":
        if not re.match(r"^-?\d+(\.\d+)?$", text):
            return "expected a number"
    elif kind == "ids":
        if not re.match(r"^\d+(\s*,\s*\d+)*$", text):
            return "expected numbers separated by commas"
    elif kind == "quoted":
        if '"' in text or len(text) > 100:
            return "a name without quotes, at most 100 characters"
    elif kind == "text":
        if len(text) > 200:
            return "value is too long"
    elif kind == "choice":
        if text not in (choices or []):
            return "expected one of %s" % ", ".join(choices or [])
    if "\n" in text or "\r" in text:
        return "value may not span lines"
    return None


def apply_settings(conf_dir, changes, backup_dir):
    """Write `changes` ({key: value}) into the .conf files.

    Backs up each file it touches first. Returns (written, backups, errors).
    Nothing is written if any value fails validation, so a bad field cannot leave
    the configuration half applied.
    """
    errors = {}
    for key, value in changes.items():
        problem = validate(key, value)
        if problem:
            errors[key] = problem
    if errors:
        return {}, [], errors

    by_file = {}
    for key, value in changes.items():
        text = str(value).strip()
        if BY_KEY[key].kind == "quoted":
            text = '"%s"' % text
        by_file.setdefault(BY_KEY[key].file, {})[key] = text

    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    written, backups = {}, []

    for filename, pairs in by_file.items():
        path = os.path.join(conf_dir, filename)
        if not os.path.exists(path):
            errors[filename] = "file not found: %s" % path
            continue
        # newline="" keeps CRLF as it is, and plain utf-8 keeps a BOM as a character: the file
        # comes back byte for byte apart from the values changed.
        with open(path, encoding="utf-8", errors="replace", newline="") as handle:
            text = handle.read()

        updated = text
        missing = []
        for key, value in pairs.items():
            pattern = _line_re(key)
            if not pattern.search(updated):
                if key in ADDABLE:
                    # A documented block at the end of the file, in the file's own line endings.
                    newline = "\r\n" if "\r\n" in updated else "\n"
                    block = ["", "#"] + ["#    " + line for line in ADDABLE[key][1]] + ["#", "", "%s = %s" % (key, value), ""]
                    updated = updated.rstrip("\r\n") + newline + newline.join(block)
                    continue
                missing.append(key)
                continue
            updated = pattern.sub(lambda m: m.group(1) + value + m.group(3), updated, count=1)
        for key in missing:
            errors[key] = "setting not found in %s" % filename
        if missing or updated == text:
            if not missing:
                written[filename] = 0
            continue

        os.makedirs(backup_dir, exist_ok=True)
        backup = os.path.join(backup_dir, "%s.%s.bak" % (filename, stamp))
        shutil.copy2(path, backup)
        backups.append(backup)

        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(updated)
        written[filename] = len(pairs)

    return written, backups, errors
