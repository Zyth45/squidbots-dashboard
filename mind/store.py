"""The mind's database: one SQLite file, opened per call.

SQLite rather than the game database: the dashboard promises never to write to the game DB, the standard
library has no MySQL driver, and persona text typed in a form must never be pasted into a SQL string.
Every statement here is parameterised.

A bot is identified by its character guid. `name` is stored beside it so that a guid reused by a
different character (bots deleted and re-created) is noticed rather than inheriting someone else's past.
"""
import contextlib
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS persona (
    bot_guid     INTEGER PRIMARY KEY,
    name         TEXT NOT NULL DEFAULT '',
    archetype    TEXT NOT NULL DEFAULT '',
    traits       TEXT NOT NULL DEFAULT '',
    speech_style TEXT NOT NULL DEFAULT '',
    interests    TEXT NOT NULL DEFAULT '',
    backstory    TEXT NOT NULL DEFAULT '',
    source       TEXT NOT NULL DEFAULT 'generated',
    enabled      INTEGER NOT NULL DEFAULT 1,
    muted        INTEGER NOT NULL DEFAULT 0,
    updated_at   REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS rp_character (
    bot_guid    INTEGER PRIMARY KEY,
    name        TEXT NOT NULL DEFAULT '',
    race        TEXT NOT NULL DEFAULT '',
    klass       TEXT NOT NULL DEFAULT '',
    gender      TEXT NOT NULL DEFAULT '',
    calling     TEXT NOT NULL DEFAULT '',
    traits      TEXT NOT NULL DEFAULT '',
    speech      TEXT NOT NULL DEFAULT '',
    convictions TEXT NOT NULL DEFAULT '',
    goal        TEXT NOT NULL DEFAULT '',
    quirk       TEXT NOT NULL DEFAULT '',
    fear        TEXT NOT NULL DEFAULT '',
    keepsake    TEXT NOT NULL DEFAULT '',
    home        TEXT NOT NULL DEFAULT '',
    facts       TEXT NOT NULL DEFAULT '',
    story       TEXT NOT NULL DEFAULT '',
    chattiness  INTEGER NOT NULL DEFAULT 50,
    level       INTEGER NOT NULL DEFAULT 0,
    zone        TEXT NOT NULL DEFAULT '',
    chapters_to INTEGER NOT NULL DEFAULT -1,
    source      TEXT NOT NULL DEFAULT 'generated',
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS rp_chapter (
    bot_guid   INTEGER NOT NULL,
    bracket    INTEGER NOT NULL,
    level      INTEGER NOT NULL DEFAULT 0,
    text       TEXT NOT NULL,
    source     TEXT NOT NULL DEFAULT 'template',
    created_at REAL NOT NULL,
    PRIMARY KEY (bot_guid, bracket)
);
CREATE TABLE IF NOT EXISTS memory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_guid        INTEGER NOT NULL,
    subject_guid    INTEGER,
    subject_name    TEXT NOT NULL DEFAULT '',
    kind            TEXT NOT NULL,
    text            TEXT NOT NULL,
    salience        REAL NOT NULL DEFAULT 0.3,
    created_at      REAL NOT NULL,
    last_referenced REAL
);
CREATE INDEX IF NOT EXISTS memory_bot ON memory (bot_guid, subject_guid);
CREATE TABLE IF NOT EXISTS relationship (
    bot_guid     INTEGER NOT NULL,
    other_guid   INTEGER NOT NULL,
    other_name   TEXT NOT NULL DEFAULT '',
    other_is_bot INTEGER NOT NULL DEFAULT 0,
    affinity     REAL NOT NULL DEFAULT 0,
    reason       TEXT NOT NULL DEFAULT '',
    interactions INTEGER NOT NULL DEFAULT 0,
    first_seen   REAL NOT NULL,
    last_seen    REAL NOT NULL,
    PRIMARY KEY (bot_guid, other_guid)
);
CREATE TABLE IF NOT EXISTS profile (
    name              TEXT PRIMARY KEY,
    base_url          TEXT NOT NULL,
    model             TEXT NOT NULL,
    api_key_env       TEXT NOT NULL DEFAULT '',
    timeout_s         INTEGER NOT NULL DEFAULT 60,
    max_tokens        INTEGER NOT NULL DEFAULT 0,
    price_in          REAL NOT NULL DEFAULT 0,
    price_out         REAL NOT NULL DEFAULT 0,
    price_cached      REAL NOT NULL DEFAULT 0,
    max_calls_per_min INTEGER NOT NULL DEFAULT 0,
    daily_budget_usd  REAL NOT NULL DEFAULT 0,
    fallback          TEXT NOT NULL DEFAULT '',
    enabled           INTEGER NOT NULL DEFAULT 1,
    extra             TEXT NOT NULL DEFAULT '',
    updated_at        REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS lane (
    lane    TEXT PRIMARY KEY,
    profile TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bot_route (
    bot_guid INTEGER NOT NULL,
    lane     TEXT NOT NULL,
    profile  TEXT NOT NULL,
    PRIMARY KEY (bot_guid, lane)
);
CREATE TABLE IF NOT EXISTS call_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                REAL NOT NULL,
    lane              TEXT NOT NULL,
    bot_guid          INTEGER NOT NULL DEFAULT 0,
    profile           TEXT NOT NULL DEFAULT '',
    model             TEXT NOT NULL DEFAULT '',
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    cached_tokens     INTEGER NOT NULL DEFAULT 0,
    cost_usd          REAL NOT NULL DEFAULT 0,
    latency_ms        INTEGER NOT NULL DEFAULT 0,
    ok                INTEGER NOT NULL DEFAULT 1,
    error             TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS call_ts ON call_log (ts);
CREATE TABLE IF NOT EXISTS setting (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cast (
    bot_guid  INTEGER PRIMARY KEY,
    name      TEXT NOT NULL DEFAULT '',
    team      INTEGER NOT NULL DEFAULT 0,
    guild_id  INTEGER NOT NULL DEFAULT 0,
    klass     TEXT NOT NULL DEFAULT '',
    level     INTEGER NOT NULL DEFAULT 0,
    since     REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS bond (
    a    INTEGER NOT NULL,
    b    INTEGER NOT NULL,
    kind TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (a, b)
);
CREATE TABLE IF NOT EXISTS turn_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                REAL NOT NULL,
    lane              TEXT NOT NULL,
    bot_guid          INTEGER NOT NULL DEFAULT 0,
    bot_name          TEXT NOT NULL DEFAULT '',
    player_guid       INTEGER NOT NULL DEFAULT 0,
    player_name       TEXT NOT NULL DEFAULT '',
    profile           TEXT NOT NULL DEFAULT '',
    model             TEXT NOT NULL DEFAULT '',
    said              TEXT NOT NULL DEFAULT '',
    reply             TEXT NOT NULL DEFAULT '',
    tool_calls        TEXT NOT NULL DEFAULT '',
    tools_offered     TEXT NOT NULL DEFAULT '',
    mind              TEXT NOT NULL DEFAULT '',
    system_prompt     TEXT NOT NULL DEFAULT '',
    latency_ms        INTEGER NOT NULL DEFAULT 0,
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd          REAL NOT NULL DEFAULT 0,
    ok                INTEGER NOT NULL DEFAULT 1,
    error             TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS turn_bot ON turn_log (bot_guid, ts);
CREATE INDEX IF NOT EXISTS turn_ts ON turn_log (ts);
"""

# A database made before these existed gets them added, in order. user_version says how far it got.
MIGRATIONS = [
    (1, ["ALTER TABLE persona ADD COLUMN muted INTEGER NOT NULL DEFAULT 0",
         "ALTER TABLE profile ADD COLUMN extra TEXT NOT NULL DEFAULT ''"]),
    (2, ["ALTER TABLE turn_log ADD COLUMN tools_offered TEXT NOT NULL DEFAULT ''"]),
    (3, ["ALTER TABLE profile ADD COLUMN price_cached REAL NOT NULL DEFAULT 0",
         "ALTER TABLE call_log ADD COLUMN cached_tokens INTEGER NOT NULL DEFAULT 0"]),
    (4, ["ALTER TABLE persona ADD COLUMN opinions TEXT NOT NULL DEFAULT ''",
         "ALTER TABLE persona ADD COLUMN chattiness INTEGER NOT NULL DEFAULT 50"]),
]

PERSONA_FIELDS = ("name", "archetype", "traits", "speech_style", "interests", "backstory", "opinions")
PROFILE_FIELDS = ("base_url", "model", "api_key_env", "timeout_s", "max_tokens", "price_in", "price_out", "price_cached",
                  "max_calls_per_min", "daily_budget_usd", "fallback", "enabled", "extra")

# Short of a reason to change them, these are what a fresh install runs with.
SETTING_DEFAULTS = {
    "auto_persona": "1",        # give a bot a generated persona the first time it speaks
    "recall_count": "8",        # memories put in front of the model
    "memory_per_subject": "150",  # events kept per bot and player before the dullest are dropped
    "reflect_every": "6",       # exchanges between memory reflections (needs a "memory" lane profile)
    "awake_window_s": "600",    # a bot counts as awake this long after it last answered
    "paused": "0",              # 1 = answer nothing: the module logs an error and bots stay ordinary playerbots
    "daily_cap_usd": "0",       # all profiles together; 0 = no cap. Reached: every call is refused until midnight
    "max_reply_chars": "250",   # a WoW chat line holds 255; longer replies are cut at a sentence
    "blocked_words": "",        # comma separated; each is starred out of every reply
    "bank_share_player": "60",  # percent of unnamed lines answering a player that come from the line bank (free) not the LLM
    "bank_share_bots": "100",   # ... answering another bot, or a stock line said in the bot's own voice
    "bank_picker": "local",     # who picks the bank line: "local" (free, keyword rules) or "jev" (a typed decision, ~$0.00002)
    "bank_join_min": "25",      # Jev only: least percent chance that this person would say anything, or the bot stays quiet
    "bank_llm_depth": "3",      # while a player is in the talk, the bots' first answers this deep are written, not banked (0: all banked)
    "cast_size": "24",          # how many bots are the realm's regulars: the ones who start and carry the chat
    "max_tool_rounds": "40",    # tool rounds in one turn before tools are withdrawn and the bot must answer in words
    "guard": "1",               # tell the model that players' words are conversation, never instructions
    "log_turns": "1",           # keep what was said and what the model was shown, for the Conversations view
    "turn_log_keep": "1500",    # newest conversation turns kept
    "personality_mix": "",      # "troll: 3, lurker: 1, ...": how common each kind of generated personality is; empty = the defaults
    "ambient_vibe": "",         # how bots behave in public chat (banter, hot takes); empty = the built-in text
    "chat_mode": "roleplay",    # "roleplay": bots are characters in the world's lore; "players": bots chat like players at a keyboard
    "rp_channels": "say,yell,guild",   # roleplay: where bots talk by themselves (whispers, party and direct questions are always answered)
    "rp_rules": ("You are a real person living in the world of Warcraft, not a player at a keyboard. Stay in character at all times: "
                 "speak as this person would, in the voice described above, with the knowledge and prejudices of their people. "
                 "Never mention levels, experience, objectives, gear scores, dungeon finders, servers, bots, addons or the game itself; "
                 "say errand, task, commission, bounty or duty where a player would say quest. Know only what someone of your age and "
                 "place would know; for anything you cannot know (the future, other worlds), say so in character or change the "
                 "subject. Use lore names and places correctly, and if you are not sure of a fact be vague rather than invent. "
                 "Speak aloud in one to three short sentences. The odd *action* in asterisks is fine, but not on every line. Stay "
                 "consistent with your story and what you remember: you are the same person every time, and people you meet can "
                 "become friends or rivals. Only when the other person writes (( )) or says 'ooc' do you answer out of character, "
                 "briefly, in (( )), and go back to the scene when they do. Any other question, however odd, is put to the person "
                 "you are playing: 'are you an AI?' or 'are you a bot?' is answered as they would, puzzled, amused or offended, "
                 "never by confirming or denying anything outside the world."),
    "rp_bank_share_player": "25",   # roleplay: percent of unnamed lines answering a player that come from the line bank (the rest are written)
    "rp_start_llm": "40",       # roleplay: percent of a bot's own remarks that are written from its quests and surroundings, not the bank
    "rp_ai_story": "1",         # roleplay: a model writes each bot's backstory and new chapters as it levels (off: plain templates)
    "style_rules": ("Talk like a player in a game chat: one or two short sentences, casual, no speeches. "
                    "Stay in character in how you sound, but never let it change what is true: report gear, "
                    "gold, quests and position only from your tools or the state you were given."),
}


class Store:
    def __init__(self, path):
        self.path = path
        with self.conn() as db:
            db.executescript(SCHEMA)
            self._migrate(db)
        # WAL lets the dashboard read while the service writes. It is stored in the file, once.
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            db.execute("PRAGMA journal_mode=WAL")

    @staticmethod
    def _migrate(db):
        """Bring a database made by an older version up to date. A fresh one already has every column."""
        version = db.execute("PRAGMA user_version").fetchone()[0]
        for target, statements in MIGRATIONS:
            if version >= target:
                continue
            for statement in statements:
                table, column = statement.split()[2], statement.split()[5]
                have = {row["name"] for row in db.execute("PRAGMA table_info(%s)" % table)}
                if column not in have:
                    db.execute(statement)
            db.execute("PRAGMA user_version = %d" % target)

    @contextlib.contextmanager
    def conn(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # ---- settings --------------------------------------------------------------------------------------

    # Text that must never be empty: clearing the box on the dashboard means "go back to the built-in text".
    BLANK_IS_DEFAULT = ("rp_rules",)

    def setting(self, key):
        with self.conn() as db:
            row = db.execute("SELECT value FROM setting WHERE key = ?", (key,)).fetchone()
        if row and not (key in self.BLANK_IS_DEFAULT and not row["value"].strip()):
            return row["value"]
        return SETTING_DEFAULTS[key]

    def settings(self):
        with self.conn() as db:
            stored = {row["key"]: row["value"] for row in db.execute("SELECT key, value FROM setting")}
        return {key: (stored[key] if key in stored and not (key in self.BLANK_IS_DEFAULT and not stored[key].strip()) else default)
                for key, default in SETTING_DEFAULTS.items()}

    def set_setting(self, key, value):
        if key not in SETTING_DEFAULTS:
            raise KeyError(key)
        with self.conn() as db:
            db.execute("INSERT INTO setting (key, value) VALUES (?, ?) "
                       "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, str(value)))

    # ---- persona ---------------------------------------------------------------------------------------

    def persona(self, bot_guid):
        with self.conn() as db:
            row = db.execute("SELECT * FROM persona WHERE bot_guid = ?", (bot_guid,)).fetchone()
        return dict(row) if row else None

    def save_persona(self, bot_guid, fields, source):
        row = {key: str(fields.get(key, "")).strip() for key in PERSONA_FIELDS}
        enabled = 1 if fields.get("enabled", 1) in (1, True, "1") else 0
        try:
            chattiness = max(0, min(100, int(fields.get("chattiness", 50))))
        except (TypeError, ValueError):
            chattiness = 50
        with self.conn() as db:
            db.execute(
                "INSERT INTO persona (bot_guid, name, archetype, traits, speech_style, interests, backstory, opinions,"
                " chattiness, source, enabled, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(bot_guid) DO UPDATE SET name = excluded.name, archetype = excluded.archetype,"
                " traits = excluded.traits, speech_style = excluded.speech_style,"
                " interests = excluded.interests, backstory = excluded.backstory, opinions = excluded.opinions,"
                " chattiness = excluded.chattiness, source = excluded.source,"
                " enabled = excluded.enabled, updated_at = excluded.updated_at",
                (bot_guid, row["name"], row["archetype"], row["traits"], row["speech_style"],
                 row["interests"], row["backstory"], row["opinions"], chattiness, source, enabled, time.time()))

    def set_muted(self, bot_guid, muted, name=""):
        """Mute or unmute a bot, making a persona row first if it has none (the flag lives there)."""
        with self.conn() as db:
            db.execute("INSERT INTO persona (bot_guid, name, source, muted, updated_at) VALUES (?, ?, 'generated', ?, ?) "
                       "ON CONFLICT(bot_guid) DO UPDATE SET muted = excluded.muted", (bot_guid, name, 1 if muted else 0, time.time()))

    def is_muted(self, bot_guid):
        with self.conn() as db:
            row = db.execute("SELECT muted FROM persona WHERE bot_guid = ?", (bot_guid,)).fetchone()
        return bool(row and row["muted"])

    def delete_persona(self, bot_guid):
        with self.conn() as db:
            db.execute("DELETE FROM persona WHERE bot_guid = ?", (bot_guid,))

    def persona_cards(self):
        """{name: [archetype, source, muted, enabled]} for every persona with a name: what a bot card shows."""
        with self.conn() as db:
            rows = db.execute("SELECT name, archetype, source, muted, enabled FROM persona WHERE name != ''").fetchall()
        return {row["name"]: [row["archetype"], row["source"], row["muted"], row["enabled"]] for row in rows}

    def personas(self, query="", limit=200):
        pattern = "%" + query.replace("%", "").replace("_", "") + "%"
        with self.conn() as db:
            rows = db.execute(
                "SELECT bot_guid, name, archetype, source, enabled, muted, updated_at FROM persona "
                "WHERE name LIKE ? OR archetype LIKE ? ORDER BY name LIMIT ?",
                (pattern, pattern, limit)).fetchall()
        return [dict(row) for row in rows]

    # ---- roleplay characters ---------------------------------------------------------------------------

    RP_FIELDS = ("name", "race", "klass", "gender", "calling", "traits", "speech", "convictions", "goal", "quirk", "fear", "keepsake",
                 "home", "facts", "story")

    def rp_character(self, bot_guid):
        with self.conn() as db:
            row = db.execute("SELECT * FROM rp_character WHERE bot_guid = ?", (bot_guid,)).fetchone()
        return dict(row) if row else None

    def save_rp_character(self, bot_guid, fields, source="generated", chattiness=50, level=0, zone=""):
        row = {key: str(fields.get(key, "")).strip() for key in self.RP_FIELDS}
        now = time.time()
        with self.conn() as db:
            db.execute(
                "INSERT INTO rp_character (bot_guid, name, race, klass, gender, calling, traits, speech, convictions, goal, quirk, fear,"
                " keepsake, home, facts, story, chattiness, level, zone, source, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(bot_guid) DO UPDATE SET name = excluded.name, race = excluded.race, klass = excluded.klass,"
                " gender = excluded.gender, calling = excluded.calling, traits = excluded.traits, speech = excluded.speech,"
                " convictions = excluded.convictions, goal = excluded.goal, quirk = excluded.quirk, fear = excluded.fear,"
                " keepsake = excluded.keepsake, home = excluded.home, facts = excluded.facts, story = excluded.story,"
                " chattiness = excluded.chattiness, source = excluded.source, updated_at = excluded.updated_at",
                (bot_guid, row["name"], row["race"], row["klass"], row["gender"], row["calling"], row["traits"], row["speech"],
                 row["convictions"], row["goal"], row["quirk"], row["fear"], row["keepsake"], row["home"], row["facts"], row["story"],
                 max(0, min(100, int(chattiness))), int(level), zone, source, now, now))

    def set_rp_field(self, bot_guid, field, value):
        if field not in self.RP_FIELDS:
            raise KeyError(field)
        with self.conn() as db:
            db.execute("UPDATE rp_character SET %s = ?, updated_at = ? WHERE bot_guid = ?" % field, (value, time.time(), bot_guid))

    def set_rp_state(self, bot_guid, level, zone):
        with self.conn() as db:
            db.execute("UPDATE rp_character SET level = ?, zone = ? WHERE bot_guid = ?", (int(level), zone, bot_guid))

    def set_rp_chapters_to(self, bot_guid, bracket):
        with self.conn() as db:
            db.execute("UPDATE rp_character SET chapters_to = MAX(chapters_to, ?) WHERE bot_guid = ?", (int(bracket), bot_guid))

    def mark_rp_manual(self, bot_guid):
        with self.conn() as db:
            db.execute("UPDATE rp_character SET source = 'manual' WHERE bot_guid = ?", (bot_guid,))

    def rp_chapters(self, bot_guid):
        with self.conn() as db:
            return [dict(row) for row in db.execute("SELECT * FROM rp_chapter WHERE bot_guid = ? ORDER BY bracket", (bot_guid,))]

    def save_rp_chapter(self, bot_guid, bracket, level, text, source):
        with self.conn() as db:
            db.execute("INSERT INTO rp_chapter (bot_guid, bracket, level, text, source, created_at) VALUES (?, ?, ?, ?, ?, ?) "
                       "ON CONFLICT(bot_guid, bracket) DO UPDATE SET text = excluded.text, source = excluded.source, level = excluded.level",
                       (bot_guid, int(bracket), int(level), text, source, time.time()))

    def reset_rp_story(self, bot_guid):
        """Forget the written story and the chapters: they are written again (from the facts, which stay) the next time the bot speaks."""
        with self.conn() as db:
            db.execute("UPDATE rp_character SET story = '', chapters_to = -1 WHERE bot_guid = ?", (bot_guid,))
            db.execute("DELETE FROM rp_chapter WHERE bot_guid = ?", (bot_guid,))

    def reset_all_rp_stories(self):
        with self.conn() as db:
            count = db.execute("UPDATE rp_character SET story = '', chapters_to = -1 WHERE source = 'generated'").rowcount
            db.execute("DELETE FROM rp_chapter WHERE bot_guid IN (SELECT bot_guid FROM rp_character WHERE source = 'generated')")
        return count

    def delete_rp_character(self, bot_guid):
        with self.conn() as db:
            db.execute("DELETE FROM rp_character WHERE bot_guid = ?", (bot_guid,))
            db.execute("DELETE FROM rp_chapter WHERE bot_guid = ?", (bot_guid,))

    def rp_characters(self, query="", limit=200):
        pattern = "%" + query.replace("%", "").replace("_", "") + "%"
        with self.conn() as db:
            rows = db.execute("SELECT bot_guid, name, race, klass, calling, level, zone, source, updated_at FROM rp_character "
                              "WHERE name LIKE ? OR race LIKE ? OR calling LIKE ? OR klass LIKE ? ORDER BY name LIMIT ?",
                              (pattern, pattern, pattern, pattern, limit)).fetchall()
        return [dict(row) for row in rows]

    def rp_stats(self):
        with self.conn() as db:
            characters = db.execute("SELECT COUNT(*) FROM rp_character").fetchone()[0]
            storied = db.execute("SELECT COUNT(*) FROM rp_character WHERE story != ''").fetchone()[0]
            chapters = db.execute("SELECT COUNT(*) FROM rp_chapter").fetchone()[0]
            ai_chapters = db.execute("SELECT COUNT(*) FROM rp_chapter WHERE source = 'ai'").fetchone()[0]
            races = {row["race"]: row["n"] for row in db.execute("SELECT race, COUNT(*) n FROM rp_character GROUP BY race")}
        return {"characters": characters, "with_story": storied, "chapters": chapters, "ai_chapters": ai_chapters, "races": races}

    # ---- memory ----------------------------------------------------------------------------------------

    def add_memory(self, bot_guid, subject_guid, subject_name, kind, text, salience):
        with self.conn() as db:
            db.execute(
                "INSERT INTO memory (bot_guid, subject_guid, subject_name, kind, text, salience, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (bot_guid, subject_guid, subject_name, kind, text, salience, time.time()))

    def memories(self, bot_guid, subject_guid=None, kinds=None, limit=500):
        """Newest first. subject_guid None = everything the bot holds."""
        sql, args = "SELECT * FROM memory WHERE bot_guid = ?", [bot_guid]
        if subject_guid is not None:
            sql += " AND subject_guid = ?"
            args.append(subject_guid)
        if kinds:
            sql += " AND kind IN (%s)" % ",".join("?" * len(kinds))
            args.extend(kinds)
        sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
        args.append(limit)
        with self.conn() as db:
            return [dict(row) for row in db.execute(sql, args)]

    def touch_memories(self, ids):
        if not ids:
            return
        with self.conn() as db:
            db.execute("UPDATE memory SET last_referenced = ? WHERE id IN (%s)" % ",".join("?" * len(ids)),
                       [time.time()] + list(ids))

    def update_memory(self, memory_id, bot_guid, text, salience):
        with self.conn() as db:
            db.execute("UPDATE memory SET text = ?, salience = ?, last_referenced = ? "
                       "WHERE id = ? AND bot_guid = ?", (text, salience, time.time(), memory_id, bot_guid))

    def delete_memory(self, memory_id, bot_guid):
        with self.conn() as db:
            db.execute("DELETE FROM memory WHERE id = ? AND bot_guid = ?", (memory_id, bot_guid))

    def clear_memories(self, bot_guid, subject_guid=None):
        with self.conn() as db:
            if subject_guid is None:
                db.execute("DELETE FROM memory WHERE bot_guid = ?", (bot_guid,))
                db.execute("DELETE FROM relationship WHERE bot_guid = ?", (bot_guid,))
            else:
                db.execute("DELETE FROM memory WHERE bot_guid = ? AND subject_guid = ?",
                           (bot_guid, subject_guid))
                db.execute("DELETE FROM relationship WHERE bot_guid = ? AND other_guid = ?",
                           (bot_guid, subject_guid))

    def prune_events(self, bot_guid, subject_guid, keep):
        """Drop the oldest low-salience events beyond `keep`. Facts and summaries are never pruned here."""
        with self.conn() as db:
            db.execute(
                "DELETE FROM memory WHERE id IN (SELECT id FROM memory WHERE bot_guid = ? AND subject_guid = ?"
                " AND kind = 'event' AND salience < 0.6 ORDER BY created_at DESC LIMIT -1 OFFSET ?)",
                (bot_guid, subject_guid, keep))

    # ---- relationships ---------------------------------------------------------------------------------

    def relationship(self, bot_guid, other_guid):
        with self.conn() as db:
            row = db.execute("SELECT * FROM relationship WHERE bot_guid = ? AND other_guid = ?",
                             (bot_guid, other_guid)).fetchone()
        return dict(row) if row else None

    def relationships(self, bot_guid):
        with self.conn() as db:
            rows = db.execute("SELECT * FROM relationship WHERE bot_guid = ? ORDER BY last_seen DESC",
                              (bot_guid,)).fetchall()
        return [dict(row) for row in rows]

    def note_seen(self, bot_guid, other_guid, other_name, other_is_bot=False):
        now = time.time()
        with self.conn() as db:
            db.execute(
                "INSERT INTO relationship (bot_guid, other_guid, other_name, other_is_bot, first_seen, last_seen,"
                " interactions) VALUES (?, ?, ?, ?, ?, ?, 1) "
                "ON CONFLICT(bot_guid, other_guid) DO UPDATE SET interactions = interactions + 1,"
                " last_seen = excluded.last_seen,"
                " other_name = CASE WHEN excluded.other_name != '' THEN excluded.other_name ELSE other_name END",
                (bot_guid, other_guid, other_name, 1 if other_is_bot else 0, now, now))

    def set_affinity(self, bot_guid, other_guid, affinity, reason):
        with self.conn() as db:
            db.execute("UPDATE relationship SET affinity = ?, reason = ? WHERE bot_guid = ? AND other_guid = ?",
                       (max(-1.0, min(1.0, affinity)), reason[:200], bot_guid, other_guid))

    # ---- the cast: the regulars of the realm -----------------------------------------------------------

    def cast(self):
        """The regulars, oldest first."""
        with self.conn() as db:
            return [dict(row) for row in db.execute("SELECT * FROM cast ORDER BY since, bot_guid")]

    def set_cast(self, members):
        """Replace the cast with `members` (dicts with bot_guid, name, team, guild_id, klass, level). Someone who stays
        keeps the date they joined."""
        now = time.time()
        with self.conn() as db:
            since = {row["bot_guid"]: row["since"] for row in db.execute("SELECT bot_guid, since FROM cast")}
            db.execute("DELETE FROM cast")
            for index, member in enumerate(members):
                db.execute("INSERT INTO cast (bot_guid, name, team, guild_id, klass, level, since) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (member["bot_guid"], member.get("name", ""), member.get("team", 0), member.get("guild_id", 0),
                            member.get("klass", ""), member.get("level", 0), since.get(member["bot_guid"], now + index * 1e-6)))

    def bonds(self):
        with self.conn() as db:
            return [dict(row) for row in db.execute("SELECT * FROM bond")]

    def bond(self, a, b):
        with self.conn() as db:
            row = db.execute("SELECT kind, note FROM bond WHERE a = ? AND b = ?", (a, b)).fetchone()
        return dict(row) if row else None

    def bonds_of(self, guid):
        with self.conn() as db:
            return [dict(row) for row in db.execute("SELECT b, kind, note FROM bond WHERE a = ?", (guid,))]

    def add_bond(self, a, b, kind, note):
        """A bond goes both ways."""
        with self.conn() as db:
            for left, right in ((a, b), (b, a)):
                db.execute("INSERT INTO bond (a, b, kind, note) VALUES (?, ?, ?, ?) "
                           "ON CONFLICT(a, b) DO UPDATE SET kind = excluded.kind, note = excluded.note",
                           (left, right, kind[:40], note[:200]))

    # ---- LLM profiles and routing ----------------------------------------------------------------------

    def profiles(self):
        with self.conn() as db:
            return [dict(row) for row in db.execute("SELECT * FROM profile ORDER BY name")]

    def profile(self, name):
        with self.conn() as db:
            row = db.execute("SELECT * FROM profile WHERE name = ?", (name,)).fetchone()
        return dict(row) if row else None

    def save_profile(self, name, fields):
        values = [fields[key] for key in PROFILE_FIELDS]
        with self.conn() as db:
            db.execute(
                "INSERT INTO profile (name, %s, updated_at) VALUES (?, %s, ?) ON CONFLICT(name) DO UPDATE SET %s,"
                " updated_at = excluded.updated_at" % (
                    ", ".join(PROFILE_FIELDS), ", ".join("?" * len(PROFILE_FIELDS)),
                    ", ".join("%s = excluded.%s" % (key, key) for key in PROFILE_FIELDS)),
                [name] + values + [time.time()])

    def delete_profile(self, name):
        """Removes the profile and every route to it; a profile naming it as fallback loses that fallback."""
        with self.conn() as db:
            db.execute("DELETE FROM profile WHERE name = ?", (name,))
            db.execute("DELETE FROM lane WHERE profile = ?", (name,))
            db.execute("DELETE FROM bot_route WHERE profile = ?", (name,))
            db.execute("UPDATE profile SET fallback = '' WHERE fallback = ?", (name,))

    def lanes(self):
        with self.conn() as db:
            return {row["lane"]: row["profile"] for row in db.execute("SELECT lane, profile FROM lane")}

    def set_lane(self, lane, profile):
        with self.conn() as db:
            if profile:
                db.execute("INSERT INTO lane (lane, profile) VALUES (?, ?) "
                           "ON CONFLICT(lane) DO UPDATE SET profile = excluded.profile", (lane, profile))
            else:
                db.execute("DELETE FROM lane WHERE lane = ?", (lane,))

    def routes(self, bot_guid):
        with self.conn() as db:
            return {row["lane"]: row["profile"] for row in
                    db.execute("SELECT lane, profile FROM bot_route WHERE bot_guid = ?", (bot_guid,))}

    def set_route(self, bot_guid, lane, profile):
        with self.conn() as db:
            if profile:
                db.execute("INSERT INTO bot_route (bot_guid, lane, profile) VALUES (?, ?, ?) "
                           "ON CONFLICT(bot_guid, lane) DO UPDATE SET profile = excluded.profile",
                           (bot_guid, lane, profile))
            else:
                db.execute("DELETE FROM bot_route WHERE bot_guid = ? AND lane = ?", (bot_guid, lane))

    def profile_for(self, lane, bot_guid):
        """The profile name a request should use: the bot's own route, else the lane's default."""
        with self.conn() as db:
            row = db.execute("SELECT profile FROM bot_route WHERE bot_guid = ? AND lane = ?",
                             (bot_guid, lane)).fetchone()
            if row:
                return row["profile"]
            row = db.execute("SELECT profile FROM lane WHERE lane = ?", (lane,)).fetchone()
        return row["profile"] if row else None

    # ---- call log --------------------------------------------------------------------------------------

    def log_call(self, lane, bot_guid, profile, model, prompt_tokens, completion_tokens, cost_usd,
                 latency_ms, ok, error="", cached_tokens=0):
        with self.conn() as db:
            db.execute(
                "INSERT INTO call_log (ts, lane, bot_guid, profile, model, prompt_tokens, completion_tokens,"
                " cached_tokens, cost_usd, latency_ms, ok, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (time.time(), lane, bot_guid, profile, model, prompt_tokens, completion_tokens, cached_tokens,
                 cost_usd, latency_ms, 1 if ok else 0, error[:300]))

    # ---- conversation turns ----------------------------------------------------------------------------

    def log_turn(self, turn, keep):
        columns = ("ts", "lane", "bot_guid", "bot_name", "player_guid", "player_name", "profile", "model", "said",
                   "reply", "tool_calls", "tools_offered", "mind", "system_prompt", "latency_ms", "prompt_tokens",
                   "completion_tokens", "cost_usd", "ok", "error")
        row = dict({"ts": time.time(), "bot_guid": 0, "bot_name": "", "player_guid": 0, "player_name": "",
                    "profile": "", "model": "", "said": "", "reply": "", "tool_calls": "", "tools_offered": "", "mind": "",
                    "system_prompt": "", "latency_ms": 0, "prompt_tokens": 0, "completion_tokens": 0,
                    "cost_usd": 0.0, "ok": 1, "error": ""}, **turn)
        with self.conn() as db:
            db.execute("INSERT INTO turn_log (%s) VALUES (%s)" % (",".join(columns), ",".join("?" * len(columns))),
                       [row[column] for column in columns])
            db.execute("DELETE FROM turn_log WHERE id <= (SELECT MAX(id) FROM turn_log) - ?", (keep,))

    def turns(self, bot_guid=None, player_guid=None, before=None, limit=50, only_problems=False):
        """Newest first, without the bulky prompt text (see turn())."""
        sql = ("SELECT id, ts, lane, bot_guid, bot_name, player_guid, player_name, profile, model, said, reply, "
               "tool_calls, latency_ms, prompt_tokens, completion_tokens, cost_usd, ok, error FROM turn_log WHERE 1=1")
        args = []
        if bot_guid:
            sql += " AND bot_guid = ?"
            args.append(bot_guid)
        if player_guid:
            sql += " AND player_guid = ?"
            args.append(player_guid)
        if before:
            sql += " AND id < ?"
            args.append(before)
        if only_problems:
            sql += " AND ok = 0"
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self.conn() as db:
            return [dict(row) for row in db.execute(sql, args)]

    def turn(self, turn_id):
        with self.conn() as db:
            row = db.execute("SELECT * FROM turn_log WHERE id = ?", (turn_id,)).fetchone()
        return dict(row) if row else None

    def daily_usage(self, since):
        """One row per local day: calls, errors, tokens and cost."""
        with self.conn() as db:
            rows = db.execute(
                "SELECT date(ts, 'unixepoch', 'localtime') AS day, COUNT(*) AS calls, SUM(1 - ok) AS errors,"
                " SUM(prompt_tokens) AS prompt_tokens, SUM(completion_tokens) AS completion_tokens,"
                " SUM(cost_usd) AS cost_usd FROM call_log WHERE ts >= ? GROUP BY day ORDER BY day", (since,)).fetchall()
        return [dict(row) for row in rows]

    def usage_by_bot(self, since, limit=10):
        with self.conn() as db:
            rows = db.execute(
                "SELECT c.bot_guid, COALESCE(p.name, '') AS name, COUNT(*) AS calls, SUM(c.cost_usd) AS cost_usd,"
                " SUM(c.prompt_tokens + c.completion_tokens) AS tokens FROM call_log c"
                " LEFT JOIN persona p ON p.bot_guid = c.bot_guid WHERE c.ts >= ? AND c.bot_guid != 0"
                " GROUP BY c.bot_guid ORDER BY cost_usd DESC, calls DESC LIMIT ?", (since, limit)).fetchall()
        return [dict(row) for row in rows]

    def latencies(self, since, limit=800):
        with self.conn() as db:
            return [row[0] for row in db.execute(
                "SELECT latency_ms FROM call_log WHERE ts >= ? AND ok = 1 AND latency_ms > 0 "
                "ORDER BY ts DESC LIMIT ?", (since, limit))]

    def calls_since(self, since, profile=None):
        sql, args = "SELECT COUNT(*) FROM call_log WHERE ts >= ? AND ok = 1", [since]
        if profile:
            sql += " AND profile = ?"
            args.append(profile)
        with self.conn() as db:
            return db.execute(sql, args).fetchone()[0]

    def spend_since(self, since, profile=None):
        sql, args = "SELECT COALESCE(SUM(cost_usd), 0) FROM call_log WHERE ts >= ?", [since]
        if profile:
            sql += " AND profile = ?"
            args.append(profile)
        with self.conn() as db:
            return db.execute(sql, args).fetchone()[0]

    def usage_summary(self, since):
        """Per profile and lane: calls, errors, tokens, cost, average latency."""
        with self.conn() as db:
            rows = db.execute(
                "SELECT profile, lane, COUNT(*) AS calls, SUM(1 - ok) AS errors,"
                " SUM(prompt_tokens) AS prompt_tokens, SUM(completion_tokens) AS completion_tokens,"
                " SUM(cached_tokens) AS cached_tokens,"
                " SUM(cost_usd) AS cost_usd, AVG(latency_ms) AS latency_ms FROM call_log WHERE ts >= ?"
                " GROUP BY profile, lane ORDER BY cost_usd DESC, calls DESC", (since,)).fetchall()
        return [dict(row) for row in rows]

    def recent_errors(self, since, limit=8):
        with self.conn() as db:
            rows = db.execute("SELECT ts, lane, profile, error FROM call_log WHERE ts >= ? AND ok = 0 "
                              "ORDER BY ts DESC LIMIT ?", (since, limit)).fetchall()
        return [dict(row) for row in rows]

    def awake(self, window_s):
        """Bots that answered on the smart lane recently, newest first, with who they were talking to."""
        with self.conn() as db:
            rows = db.execute(
                "SELECT c.bot_guid, MAX(c.ts) AS last_ts, COUNT(*) AS calls,"
                " (SELECT profile FROM call_log WHERE bot_guid = c.bot_guid AND lane = 'smart' AND ok = 1"
                "  ORDER BY ts DESC LIMIT 1) AS profile,"
                " COALESCE(p.name, '') AS name FROM call_log c LEFT JOIN persona p ON p.bot_guid = c.bot_guid"
                " WHERE c.lane = 'smart' AND c.ok = 1 AND c.bot_guid != 0 AND c.ts >= ?"
                " GROUP BY c.bot_guid ORDER BY last_ts DESC", (time.time() - window_s,)).fetchall()
        return [dict(row) for row in rows]

    def counts(self):
        with self.conn() as db:
            counts = {table: db.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
                      for table in ("persona", "memory", "relationship")}
            counts["muted"] = db.execute("SELECT COUNT(*) FROM persona WHERE muted = 1").fetchone()[0]
        return counts

    def prune_call_log(self, older_than_s=30 * 86400):
        with self.conn() as db:
            db.execute("DELETE FROM call_log WHERE ts < ?", (time.time() - older_than_s,))
