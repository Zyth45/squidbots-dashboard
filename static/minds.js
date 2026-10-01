/* The Minds page: language-model profiles, usage, conversations, a bot's persona and memory, and the mind
 * service's status. It also tells the bot cards, the roster and the bot sheet of dashboard.js who has a
 * personality and who is awake.
 *
 * Private: loaded only by the local dashboard, never part of the public copy. Uses esc/num/one/LAST/PAGE/lineChart
 * from dashboard.js, which is loaded first.
 */
(() => {
  const $ = id => document.getElementById(id);
  const LANES = [
    ["smart", "Conversation", "A player talks to a bot: whispers, party, and asking it to do things. Wants a capable model."],
    ["fast", "Quick decisions", "Frequent, cheap calls: ambient remarks and short orders. A small or local model is fine."],
    ["ambient", "Ambient chat", "Bots answering a hello in /say, the zone channel or Trade, and each other: one short line at a time. Uses Quick decisions until you pick a model here."],
    ["memory", "Memory", "Turns conversations into lasting memories and feelings. Optional; without it bots only keep a log."],
  ];
  // [label, endpoint, key variable, suggested model, suggested extra parameters]. OpenAI's cheapest model that used tools
  // reliably in testing (see docs/minds.md) is gpt-6-luna; "reasoning_effort none" keeps it quick and cheap.
  const PRESETS = [
    ["Ollama (local)", "http://127.0.0.1:11434/v1", "", "", ""],
    ["OpenAI", "https://api.openai.com/v1", "OPENAI_API_KEY", "gpt-6-luna", '{"reasoning_effort":"none"}'],
    ["DeepSeek", "https://api.deepseek.com/v1", "DEEPSEEK_API_KEY", "", ""],
    ["OpenRouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "", ""],
    ["Anthropic", "https://api.anthropic.com/v1", "ANTHROPIC_API_KEY", "", ""],
  ];
  const KEY_TEXT = {
    env: ["key found (environment)", "ok"], file: ["key found (secrets file)", "ok"],
    missing: ["key NOT found", "bad"], none: ["no key", ""], unknown: ["-", ""],
  };
  // [key, label, help, kind]; kinds: bool, int, number, text
  const SETTING_GROUPS = [
    ["Personality and memory", [
      ["auto_persona", "Give every bot a personality", "A bot with none gets a random one the first time it speaks. You can rewrite it below.", "bool"],
      ["recall_count", "Memories shown to the model", "How many remembered lines go in front of the model each time a player talks to a bot.", "int"],
      ["memory_per_subject", "Conversation lines kept per player", "Per bot and player; the dullest old lines are dropped beyond this. Lasting facts are never dropped.", "int"],
      ["reflect_every", "Reflect on memory every N exchanges", "0 turns it off. Needs a model on the Memory lane; that is one extra model call per N exchanges.", "int"],
      ["awake_window_s", "A bot counts as awake for (seconds)", "After it last answered a player.", "int"],
      ["style_rules", "How bots should sound", "Added to every personality.", "text"],
    ]],
    ["Chat and personalities", [
      ["personality_mix", "How common each kind of personality is", "For personalities made automatically, like troll: 3, lurker: 1. A bigger number is more common, 0 removes a kind, a kind left out is never made. Empty uses the built-in mix. Apply it with Re-roll all generated personalities below.", "text"],
      ["max_tool_rounds", "Most tool steps per message", "Stops a bot that keeps calling tools without ever answering. The game module has its own, higher limit.", "int"],
      ["ambient_vibe", "The vibe of public chat", "Told to every bot that answers a hello or says its stock chatter in its own words. Make it politer, ruder, sillier or more roleplay. Empty uses the built-in text (shown in grey).", "text"],
    ]],
    ["Line bank", [
      ["bank_share_player", "Answers to players taken from the bank (%)", "When a player talks in public chat and a fitting line is banked. The rest go to the model. 0 uses the model always.", "int"],
      ["bank_share_bots", "Bot-to-bot chatter and stock lines from the bank (%)", "Bots talking to each other, and stock playerbots lines said in their own words. 100 costs nothing.", "int"],
      ["bank_picker", "Who picks the line", "Local picks at random among lines that fit. Jev also reads the recent chat, so the line answers what was just said, and can decide a bot stays quiet. Costs a fraction of a cent per hundred picks.", "choice"],
      ["bank_join_min", "Jev: chance to speak needed (%)", "With Jev picking, a bot only answers when Jev thinks it would have spoken at least this often.", "int"],
    ]],
    ["Safety", [
      ["paused", "Pause all AI", "Bots answer nothing and stay ordinary playerbots until you resume. The dashboard's own try-outs still work.", "bool"],
      ["guard", "Protect against instructions in chat", "Tells the model that players' words are conversation, never orders, and that it must not reveal its instructions.", "bool"],
      ["max_reply_chars", "Longest reply (characters)", "A chat line holds 255. Longer replies are cut at a sentence.", "int"],
      ["blocked_words", "Words to star out", "Comma separated. Each one is replaced by asterisks wherever a bot would say it.", "text"],
      ["daily_cap_usd", "Daily spending cap, all models ($)", "Every call is refused for the rest of the day once this is reached. 0 means no cap.", "number"],
    ]],
    ["Conversation log", [
      ["log_turns", "Keep what was said", "Feeds the Conversations view: what a player said, what the model was shown, what it answered.", "bool"],
      ["turn_log_keep", "Turns kept", "The newest this many are kept.", "int"],
    ]],
  ];

  // [key, title, what it means]: the switch at the top of the page. Roleplay is what a fresh install runs.
  const CHAT_MODES = [
    ["roleplay", "Roleplay", "Every bot is a person of its race and calling, with a backstory that grows as it levels. They know the lore, the zone they stand in and what they are doing there, and talk in character. They stay out of the realm channel, General, Trade and LFG."],
    ["players", "Fake players", "Bots chat like players at a keyboard: banter, hot takes, LFG and Trade adverts, in every channel."],
  ];
  const RP_CHANNELS = [["say", "/say"], ["yell", "/yell"], ["guild", "Guild"], ["zone", "Zone (General)"], ["world", "Realm channel"], ["trade", "Trade"], ["lfg", "Looking for group"]];
  const LEVEL_STRETCHES = [[1, 9], [10, 19], [20, 29], [30, 39], [40, 49], [50, 59], [60, 69], [70, 80]];

  let overview = null;
  let analyticsDays = 14;
  let openBot = null;
  let turnsBefore = null;
  let timer = null;
  let usageTimer = 0;
  let cards = { personas: {}, awake: {}, paused: false, running: false };
  const talk = {};       // bot guid -> [{role, content}] the playground has said so far

  const money = value => "$" + (value < 1 ? value.toFixed(3) : value.toFixed(2));
  const ago = ts => {
    const seconds = Math.max(0, Date.now() / 1000 - ts);
    if (seconds < 90) return "just now";
    if (seconds < 5400) return Math.round(seconds / 60) + " min ago";
    if (seconds < 172800) return Math.round(seconds / 3600) + " h ago";
    return Math.round(seconds / 86400) + " days ago";
  };
  const clip = (text, size) => { text = String(text || ""); return text.length > size ? text.slice(0, size - 1) + "…" : text; };
  // Each card has its own message line, so a result appears next to the button that caused it.
  const say = (text, kind, at) => {
    const node = $(at || "mindMsg");
    if (!node) return;
    node.textContent = text || "";
    node.className = "meta" + (kind ? " " + kind + "-msg" : "");
  };
  const messageAt = node => (node.closest("[data-msg]") || { dataset: {} }).dataset.msg || "mindMsg";
  const botFacts = name => ((typeof LAST !== "undefined" && LAST && LAST.bots) || []).find(bot => bot.n === name);

  async function request(path, body) {
    const answer = await fetch(path, body === undefined ? { cache: "no-store" } : {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await answer.json().catch(() => ({ error: "unreadable answer" }));
    if (!answer.ok) throw new Error(data.error || "HTTP " + answer.status);
    return data;
  }

  // One write. Errors are shown next to the card that asked; the page reloads its own state afterwards.
  async function act(body, done, at) {
    try {
      const result = await request("/api/mind", body);
      if (done) done(result);
      return result;
    } catch (error) {
      say(String(error.message || error), "bad", at);
      return null;
    }
  }

  /* ---------------- status ---------------- */

  function renderStatus(o) {
    const s = o.service, paused = o.settings.paused === "1";
    const cap = Number(o.settings.daily_cap_usd) || 0;
    $("mindSub").textContent = paused ? "paused" : s.running ? "running" : "not running";
    const figure = (label, value, foot) => '<div class="figure"><div class="label">' + esc(label)
      + '</div><div class="value num">' + esc(value) + '</div><div class="foot">' + esc(foot || "") + "</div></div>";
    $("mindStatus").innerHTML =
      '<div class="mind-state"><span class="pill"><span class="dot' + (s.running && !paused ? "" : " off") + '"></span>'
      + (s.running ? "Running on port " + esc(s.port) + " · " + esc(s.inflight) + " in flight" : "Not running") + "</span>"
      + '<button class="btn small" type="button" id="mindPause">' + (paused ? "Resume all AI" : "Pause all AI") + "</button>"
      + (s.running ? "" : "<code>python run-mind.py</code><span class=\"meta\">in the dashboard folder. Until it runs, "
        + "bots fall back to the module's own behaviour.</span>") + "</div>"
      + (paused ? '<p class="mind-notice">All AI is paused: every bot answers nothing and stays an ordinary playerbot. '
        + "Resume when you are ready.</p>" : "")
      + '<div class="mind-figures">'
      + figure("Awake now", num(o.awake.length), "bots that answered lately")
      + figure("Calls today", num(o.today.calls), "all models")
      + figure("Spend today", money(o.today.cost), cap ? "of a " + money(cap) + " cap"
        : o.today.cost || !o.today.calls ? "estimated from your prices" : "set prices on a model to see this")
      + figure("Personalities", num(o.counts.persona), o.counts.muted ? num(o.counts.muted) + " muted" : "")
      + figure("Memories", num(o.counts.memory), num(o.counts.relationship) + " relationships")
      + "</div>"
      + (o.awake.length ? '<div class="mind-awake"><span class="meta">Awake:</span>'
        + o.awake.map(bot => '<button class="chip" type="button" data-bot="' + esc(bot.name || "") + '">'
          + esc(bot.name || "bot " + bot.bot_guid) + "</button>").join("") + "</div>" : "")
      + (s.noPlayer > 0 && o.counts.memory === 0
        ? '<p class="mind-notice">' + num(s.noPlayer) + " conversation request(s) arrived without a player's identity, so nothing can be "
          + "remembered. Automatic ticks always look like that; if players are talking to bots, set OllamaChat.Gateway.InjectIdentity = 1 "
          + "in mod_ollama_chat.conf (the Minds on recipe does).</p>" : "")
      + '<details class="mind-connect"><summary>Connect the worldserver</summary>'
      + "<p>Settings &rarr; the <b>Minds on</b> recipe writes these for you. By hand, in mod_ollama_chat.conf:</p><pre>"
      + esc('OllamaChat.Gateway.Enable = 1\nOllamaChat.Gateway.Type = "synthiq"\nOllamaChat.Gateway.InjectIdentity = 1\n'
        + 'OllamaChat.Gateway.Url = "http://127.0.0.1:' + (s.port || 18800) + '/v1/chat/completions"\n'
        + 'OllamaChat.Tactical.Url = "http://127.0.0.1:' + (s.port || 18800) + '/fast/v1/chat/completions"')
      + "</pre></details>";
    const names = new Set(((typeof LAST !== "undefined" && LAST && LAST.bots) || []).map(bot => bot.n));
    o.awake.forEach(bot => bot.name && names.add(bot.name));
    Object.keys(cards.personas).forEach(name => names.add(name));
    $("mindBotNames").innerHTML = [...names].sort().map(name => '<option value="' + esc(name) + '">').join("");
  }

  /* ---------------- profiles ---------------- */

  function profileOptions(selected, blank) {
    return '<option value="">' + esc(blank) + "</option>" + overview.profiles.map(p =>
      '<option value="' + esc(p.name) + '"' + (p.name === selected ? " selected" : "") + ">" + esc(p.name) + "</option>").join("");
  }

  function renderProfiles(o) {
    const lanes = '<div class="mind-lanes">' + LANES.map(([lane, title, help]) =>
      '<div class="mind-lane"><label for="lane_' + lane + '">' + esc(title) + '</label><span class="meta">' + esc(help)
      + '</span><select id="lane_' + lane + '" data-lane="' + lane + '">' + profileOptions(o.lanes[lane], "(none)")
      + "</select></div>").join("") + "</div>";
    const rows = o.profiles.map(p => {
      const [keyText, keyClass] = KEY_TEXT[p.key] || KEY_TEXT.unknown;
      return "<tr><td><span class=\"pname\">" + esc(p.name) + "</span>" + (p.enabled ? "" : ' <span class="meta">(off)</span>')
        + '<br><span class="meta">' + esc(p.model) + "</span></td>"
        + '<td class="meta">' + esc(p.base_url) + '<br><span class="' + keyClass + '">' + esc(keyText) + "</span></td>"
        + '<td class="r">' + num(p.calls_24h) + '</td><td class="r">' + money(p.cost_24h) + "</td>"
        + '<td class="meta">' + esc(p.fallback ? "then " + p.fallback : "") + esc(p.max_calls_per_min ? " · " + p.max_calls_per_min + "/min" : "")
        + esc(p.daily_budget_usd ? " · " + money(p.daily_budget_usd) + "/day" : "") + esc(p.extra ? " · extra params" : "") + "</td>"
        + '<td class="actions"><button class="btn small" type="button" data-test="' + esc(p.name) + '">Test</button>'
        + '<button class="btn small" type="button" data-edit="' + esc(p.name) + '">Edit</button>'
        + '<button class="btn small" type="button" data-del="' + esc(p.name) + '">Delete</button></td></tr>';
    }).join("");
    const errors = o.errors.length
      ? '<p class="meta bad">Recent errors: ' + o.errors.slice(0, 3).map(e => esc(e.profile + ": " + e.error)).join(" · ") + "</p>" : "";
    $("mindProfiles").innerHTML = lanes
      + (o.profiles.length
        ? '<div class="scroll"><table><thead><tr><th>Profile</th><th>Endpoint</th><th class="r">Calls 24 h</th><th class="r">Cost 24 h</th><th>Limits</th><th></th></tr></thead><tbody>'
          + rows + "</tbody></table></div>"
        : '<p class="empty">No language model yet. Add one to bring the bots to life.</p>')
      + errors
      + '<p><button class="btn" type="button" id="mindAdd">Add a model</button></p>';
  }

  function profileForm(p) {
    const editing = Boolean(p);
    p = p || { name: "", base_url: "", model: "", api_key_env: "", timeout_s: 60, max_tokens: 0, price_in: 0, price_out: 0, price_cached: 0,
      max_calls_per_min: 0, daily_budget_usd: 0, fallback: "", enabled: 1, extra: "" };
    const field = (name, label, value, hint, type) => '<label>' + esc(label) + '<input name="' + name + '" type="' + (type || "text")
      + '" value="' + esc(value) + '"' + (name === "name" && editing ? " readonly" : "") + (type === "number" ? ' step="any" min="0"' : "") + ">"
      + (hint ? '<span class="hint">' + esc(hint) + "</span>" : "") + "</label>";
    $("mindProfileForm").innerHTML = '<form class="mind-form" id="profileForm">'
      + '<div class="wide row"><h3>' + (editing ? "Edit " + esc(p.name) : "New model") + "</h3>"
      + PRESETS.map(([label, url, env, model, extra]) => '<button class="btn small" type="button" data-preset="' + esc([url, env, model, extra].join("|")) + '">' + esc(label) + "</button>").join("") + "</div>"
      + field("name", "Name", p.name, "Anything you like, e.g. fast-local")
      + field("base_url", "Endpoint", p.base_url, "An OpenAI-compatible base URL")
      + field("model", "Model", p.model, "The model name your provider uses")
      + field("api_key_env", "Key variable", p.api_key_env, "The NAME of an environment variable, not the key. Or put the key in mind-secrets.json")
      + field("price_in", "Input price, $ per million tokens", p.price_in, "Only used for the spend estimate", "number")
      + field("price_out", "Output price, $ per million tokens", p.price_out, "", "number")
      + field("price_cached", "Cached input price, $ per million", p.price_cached, "Providers bill repeated prompt starts at a fraction; 0 = the input price", "number")
      + field("max_calls_per_min", "Calls per minute (0 = no limit)", p.max_calls_per_min, "", "number")
      + field("daily_budget_usd", "Daily budget, $ (0 = no limit)", p.daily_budget_usd, "Calls to this model stop for the day when reached", "number")
      + field("timeout_s", "Timeout, seconds", p.timeout_s, "", "number")
      + field("max_tokens", "Longest reply, tokens (0 = default)", p.max_tokens, "Reasoning models spend these thinking too: leave room", "number")
      + '<label>If it fails, try<select name="fallback">' + profileOptions(p.fallback, "(nothing)") + "</select></label>"
      + '<label>Enabled<select name="enabled"><option value="1"' + (p.enabled ? " selected" : "") + '>Yes</option><option value="0"'
      + (p.enabled ? "" : " selected") + ">No</option></select></label>"
      + '<label class="wide">Extra parameters (JSON, optional)<input name="extra" value="' + esc(p.extra || "") + '" placeholder=\'{"reasoning_effort": "low"}\'>'
      + '<span class="hint">Added to every request to this model. OpenAI reasoning models answer faster with reasoning_effort low; the service sets it to none for tool rounds, which they require.</span></label>'
      + '<div class="wide row"><button class="btn primary" type="submit">Save</button>'
      + '<button class="btn" type="button" id="profileCancel">Cancel</button></div></form>';
    $("profileForm").elements.name.focus();
  }

  /* ---------------- usage ---------------- */

  async function loadUsage() {
    let report;
    try {
      report = await request("/api/mind/analytics?days=" + analyticsDays);
    } catch (error) {
      $("mindUsage").innerHTML = '<p class="empty">Usage is unavailable: ' + esc(String(error.message || error)) + "</p>";
      return;
    }
    $("mindUsageSub").textContent = "last " + report.days + " days";
    const figure = (label, value, foot) => '<div class="figure"><div class="label">' + esc(label)
      + '</div><div class="value num">' + esc(value) + '</div><div class="foot">' + esc(foot || "") + "</div></div>";
    $("mindUsage").innerHTML = '<div class="mind-figures">'
      + figure("Calls", num(report.total_calls), report.total_errors ? num(report.total_errors) + " failed" : "none failed")
      + figure("Spend", money(report.total_cost), report.total_cost || !report.total_calls ? "estimated from your prices" : "set prices on a model to see this")
      + figure("Tokens", num(report.daily.reduce((sum, d) => sum + d.tokens, 0)), "read and written")
      + figure("Typical answer", report.latency.n ? (report.latency.p50 / 1000).toFixed(1) + " s" : "-", "median")
      + figure("Slowest 5%", report.latency.n ? (report.latency.p95 / 1000).toFixed(1) + " s" : "-", num(report.latency.n) + " answers timed")
      + "</div>"
      + '<div class="grid two"><div><h4 class="mini">Calls per day</h4><div id="mindCallsChart" class="chart"></div></div>'
      + '<div><h4 class="mini">Spend per day</h4><div id="mindSpendChart" class="chart"></div></div></div>'
      + '<div class="grid two"><div><h4 class="mini">By model</h4>' + usageByProfile(report) + "</div>"
      + '<div><h4 class="mini">Busiest bots</h4>' + usageByBot(report) + "</div></div>";
    dayBars($("mindCallsChart"), report.daily, d => d.calls, n => num(n) + " calls", "var(--accent)");
    dayBars($("mindSpendChart"), report.daily, d => d.cost_usd, money, "var(--gold)");
  }

  // One bar per day. (The dashboard's line chart labels its axis with the time of day, which means nothing here.)
  function dayBars(host, days, value, format, color) {
    const width = 720, height = 190, left = 44, right = 8, top = 10, bottom = 24;
    const most = Math.max(...days.map(value), 0);
    if (!most) { host.innerHTML = '<p class="empty">Nothing in this period.</p>'; return; }
    const rough = most * 1.1 / 3, power = Math.pow(10, Math.floor(Math.log10(rough)));
    const step = power * [1, 2, 2.5, 5, 10].find(m => power * m >= rough), ceiling = step * 3;
    const slot = (width - left - right) / days.length;
    const y = v => height - bottom - (height - top - bottom) * (v / ceiling);
    let svg = '<svg viewBox="0 0 ' + width + " " + height + '" role="img">';
    for (let i = 0; i <= 3; i++) {
      svg += '<line x1="' + left + '" x2="' + (width - right) + '" y1="' + y(step * i) + '" y2="' + y(step * i) + '" stroke="var(--grid)"/>'
        + '<text x="' + (left - 6) + '" y="' + (y(step * i) + 4) + '" text-anchor="end" fill="var(--text-muted)" font-size="11">'
        + esc(format(step * i).replace(" calls", "")) + "</text>";
    }
    days.forEach((day, index) => {
      const v = value(day), x = left + slot * index + slot * 0.15;
      svg += '<rect x="' + x.toFixed(1) + '" y="' + y(v).toFixed(1) + '" width="' + (slot * 0.7).toFixed(1) + '" height="' + Math.max(0, height - bottom - y(v)).toFixed(1)
        + '" fill="' + color + '" opacity=".85" rx="1"><title>' + esc(day.day + ": " + format(v)) + "</title></rect>";
      if (index === 0 || index === days.length - 1 || index % Math.ceil(days.length / 7) === 0) {
        svg += '<text x="' + (x + slot * 0.35).toFixed(1) + '" y="' + (height - 8) + '" text-anchor="middle" fill="var(--text-muted)" font-size="11">'
          + esc(day.day.slice(5)) + "</text>";
      }
    });
    host.innerHTML = svg + "</svg>";
  }

  const usageByProfile = report => report.by_profile.length
    ? '<table><thead><tr><th>Model</th><th>Lane</th><th class="r">Calls</th><th class="r">Tokens</th><th class="r">Cached</th><th class="r">Cost</th></tr></thead><tbody>'
      + report.by_profile.map(row => "<tr><td>" + esc(row.profile) + '</td><td class="meta">' + esc(row.lane) + '</td><td class="r">' + num(row.calls)
        + (row.errors ? ' <span class="bad">(' + num(row.errors) + " failed)</span>" : "") + '</td><td class="r">'
        + num((row.prompt_tokens || 0) + (row.completion_tokens || 0)) + '</td><td class="r meta">'
        + (row.prompt_tokens ? Math.round(100 * (row.cached_tokens || 0) / row.prompt_tokens) + "%" : "-")
        + '</td><td class="r">' + money(row.cost_usd || 0) + "</td></tr>").join("")
      + "</tbody></table>"
    : '<p class="empty">No calls in this period.</p>';

  const usageByBot = report => report.by_bot.length
    ? '<table><thead><tr><th>Bot</th><th class="r">Calls</th><th class="r">Tokens</th><th class="r">Cost</th></tr></thead><tbody>'
      + report.by_bot.map(row => "<tr><td>" + (row.name ? '<button class="linklike" type="button" data-bot="' + esc(row.name) + '">' + esc(row.name) + "</button>" : "bot " + row.bot_guid)
        + '</td><td class="r">' + num(row.calls) + '</td><td class="r">' + num(row.tokens || 0) + '</td><td class="r">' + money(row.cost_usd || 0) + "</td></tr>").join("")
      + "</tbody></table>"
    : '<p class="empty">No bot has spoken in this period.</p>';

  /* ---------------- conversations ---------------- */

  function turnRow(t) {
    return '<tr class="turn' + (t.ok ? "" : " failed") + '" data-turn="' + t.id + '">'
      + '<td class="meta">' + esc(ago(t.ts)) + '</td><td><span class="lane ' + esc(t.lane) + '">' + esc(t.lane) + "</span></td>"
      + "<td><b>" + esc(t.bot_name || (t.bot_guid ? "bot " + t.bot_guid : "dashboard")) + "</b>" + (t.player_name ? '<span class="meta"> ← ' + esc(t.player_name) + "</span>" : "") + "</td>"
      + "<td>" + (t.said ? '<span class="said">' + esc(clip(t.said, 90)) + "</span><br>" : "")
      + (t.ok ? '<span class="reply">' + (t.reply ? esc(clip(t.reply, 130)) : '<span class="meta">' + esc(t.tool_calls ? "asked for: " + t.tool_calls : "(no text)") + "</span>") + "</span>"
        : '<span class="bad">' + esc(clip(t.error, 140)) + "</span>") + "</td>"
      + '<td class="meta">' + esc(t.model || t.profile) + (t.latency_ms ? "<br>" + (t.latency_ms / 1000).toFixed(1) + " s" : "") + "</td>"
      + '<td class="r meta">' + (t.cost_usd ? money(t.cost_usd) : "") + "</td></tr>";
  }

  async function loadTurns(append) {
    const params = new URLSearchParams({ limit: "40" });
    if ($("turnBot").value.trim()) params.set("bot", $("turnBot").value.trim());
    if ($("turnPlayer").value.trim()) params.set("player", $("turnPlayer").value.trim());
    const problems = document.querySelector("#turnKind [aria-selected=true]");
    if (problems && problems.dataset.problems) params.set("problems", "1");
    if (append && turnsBefore) params.set("before", turnsBefore);
    let list;
    try {
      list = (await request("/api/mind/turns?" + params.toString())).turns;
    } catch (error) {
      say(String(error.message || error), "bad", "mindTurnsMsg");
      return;
    }
    say("", "", "mindTurnsMsg");
    turnsBefore = list.length ? list[list.length - 1].id : turnsBefore;
    const rows = list.map(turnRow).join("");
    if (append) {
      const body = $("mindTurns").querySelector("tbody");
      if (body) body.insertAdjacentHTML("beforeend", rows);
    } else if (!list.length) {
      $("mindTurns").innerHTML = '<p class="empty">Nothing yet. Turns appear here as players talk to bots, or when you try one below.</p>';
    } else {
      $("mindTurns").innerHTML = '<div class="scroll"><table class="turns"><thead><tr><th>When</th><th>Lane</th><th>Who</th><th>Said and answered</th><th>Model</th><th class="r">Cost</th></tr></thead><tbody>'
        + rows + "</tbody></table></div>"
        + (list.length >= 40 ? '<p><button class="btn small" type="button" id="turnMore">Older</button></p>' : "");
    }
    $("mindTurnsSub").textContent = list.length ? "click a line to see what the model was shown" : "";
  }

  async function openTurn(id) {
    let t;
    try {
      t = await request("/api/mind/turn?id=" + encodeURIComponent(id));
    } catch (error) {
      say(String(error.message || error), "bad", "mindTurnsMsg");
      return;
    }
    const block = (title, text) => text ? "<h4>" + esc(title) + '</h4><pre class="turn-text">' + esc(text) + "</pre>" : "";
    $("mindSheetBody").innerHTML = "<h3>" + esc(t.bot_name || "bot " + t.bot_guid) + (t.player_name ? " ← " + esc(t.player_name) : "") + "</h3>"
      + '<p class="who">' + esc(t.lane) + " · " + esc(new Date(t.ts * 1000).toLocaleString()) + " · " + esc(t.profile) + " / " + esc(t.model)
      + " · " + (t.latency_ms / 1000).toFixed(1) + " s · " + num(t.prompt_tokens) + " in, " + num(t.completion_tokens) + " out"
      + (t.cost_usd ? " · " + money(t.cost_usd) : "") + "</p>"
      + (t.ok ? "" : '<p class="mind-notice">Failed: ' + esc(t.error) + "</p>")
      + block("Player said", t.said) + block("Bot answered", t.reply) + block("Tools it asked for", t.tool_calls)
      + block("Tools it was offered (" + (t.tools_offered ? t.tools_offered.split(",").length : 0) + ")", t.tools_offered)
      + block("What the mind added (personality, memory, safety)", t.mind)
      + (t.system_prompt ? '<details><summary>The whole system prompt the model saw</summary><pre class="turn-text">' + esc(t.system_prompt) + "</pre></details>" : "")
      + '<button class="ghost close" type="button" id="mindSheetClose">Close</button>';
    $("mindSheet").showModal();
  }

  /* ---------------- settings ---------------- */

  function renderChatStyle(o) {
    const mode = o.settings.chat_mode === "players" ? "players" : "roleplay";
    const rp = o.roleplay || {};
    const channels = (o.settings.rp_channels || "").split(",").filter(Boolean);
    $("mindChatSub").textContent = mode === "roleplay" ? "roleplay: the bots are characters in the lore" : "fake players: the bots chat like players at a keyboard";
    const setting = (key, label, hint, control) => '<label class="' + (key === "rp_rules" ? "wide" : "") + '">' + esc(label) + control + '<span class="hint">' + esc(hint) + "</span></label>";
    const number = key => '<input data-setting="' + key + '" type="number" min="0" max="100" step="5" value="' + esc(o.settings[key]) + '">';
    const stats = rp.characters
      ? " " + num(rp.characters) + " characters so far, " + num(rp.with_story) + " with a written story, " + num(rp.chapters) + " chapters of their lives"
        + (rp.ai_chapters ? " (" + num(rp.ai_chapters) + " written by a model)" : "") + "."
      : mode === "roleplay" ? " No characters yet: each is made the first time the game tells the service a bot's race and class, which needs the updated game module." : "";
    $("mindChatStyle").innerHTML = '<div class="mind-modes">' + CHAT_MODES.map(([key, title, help]) =>
        '<button type="button" class="mind-mode' + (key === mode ? " active" : "") + '" data-chatmode="' + key + '" aria-pressed="' + (key === mode) + '">'
        + "<strong>" + esc(title) + (key === "roleplay" ? ' <span class="meta">(default)</span>' : "") + "</strong><span>" + esc(help) + "</span></button>").join("") + "</div>"
      + '<p class="meta">The game follows this within a few seconds, with no restart.' + esc(stats) + "</p>"
      + '<div class="mind-form rp-settings' + (mode === "roleplay" ? "" : " dim") + '">'
      + '<div class="wide"><strong>Where characters speak up on their own</strong> <span class="hint">Whispers, party chat and anyone talking to a bot nearby are always answered, in every channel.</span>'
      + '<div class="rp-channels">' + RP_CHANNELS.map(([key, label]) => '<label class="check"><input type="checkbox" data-rpchannel="' + key + '"'
        + (channels.includes(key) ? " checked" : "") + "> " + esc(label) + "</label>").join("") + "</div></div>"
      + setting("rp_bank_share_player", "Answers to players taken from the bank (%)", "Unnamed lines said near a character. The rest are written by the model. Questions are always written.", number("rp_bank_share_player"))
      + setting("rp_start_llm", "Remarks written from what the bot is doing (%)", "A character that speaks up on its own mentions its zone and errands. The rest come from the bank, free.", number("rp_start_llm"))
      + setting("rp_ai_story", "Models write backstories and chapters", "Off keeps plain templates. A model is used on the Memory lane, else Ambient, else Quick decisions.",
        '<select data-setting="rp_ai_story"><option value="1"' + (o.settings.rp_ai_story === "1" ? " selected" : "") + ">On</option><option value=\"0\""
        + (o.settings.rp_ai_story === "0" ? " selected" : "") + ">Off</option></select>")
      + setting("rp_rules", "How characters behave", "Told to every character after its sheet. Empty restores the built-in rules.",
        '<textarea data-setting="rp_rules" rows="6"' + (o.defaults && o.defaults.rp_rules ? ' placeholder="' + esc(o.defaults.rp_rules) + '"' : "") + ">"
        + esc(o.settings.rp_rules === (o.defaults || {}).rp_rules ? "" : o.settings.rp_rules) + "</textarea>")
      + '<div class="wide row"><button class="btn" type="button" id="rpResetAll" title="Throw away every written backstory and chapter. They are written again, from the same facts, the next time each bot speaks. Characters you edited are kept.">Write all the stories again</button></div></div>';
  }

  function rpSheet(view) {
    const rp = view.rp;
    if (!rp) {
      return overview && overview.settings.chat_mode === "roleplay"
        ? '<p class="meta">No roleplay character yet. It is made the first time the game tells the service this bot\'s race and class: when it first speaks, or at the next sync of the regulars.</p>' : "";
    }
    const c = rp.character;
    const field = (name, label, value) => '<label>' + esc(label) + '<input name="' + name + '" value="' + esc(value || "") + '"></label>';
    const chapters = rp.chapters.length ? '<ul class="mind-mem">' + rp.chapters.map(ch => {
      const stretch = LEVEL_STRETCHES[ch.bracket] || [ch.level, ch.level];
      return '<li><span class="kind">' + stretch[0] + "–" + stretch[1] + "</span><span>" + esc(ch.text) + '<span class="ago">'
        + (ch.source === "ai" ? "written by a model" : ch.source === "manual" ? "written by you" : "from a template") + "</span></span><span></span></li>";
    }).join("") + "</ul>" : '<p class="empty">No chapters yet: the first is written when the game says what level this bot is.</p>';
    return "<h4>Character</h4>"
      + '<div class="mind-chips"><span class="state">' + esc(c.race + " · " + rp.calling + " · " + c.klass) + "</span>"
      + '<span class="state">' + (c.source === "manual" ? "written by you" : "generated") + "</span>"
      + (c.level ? '<span class="state">level ' + esc(c.level) + (c.zone ? " in " + esc(c.zone) : "") + "</span>" : "") + "</div>"
      + '<form class="mind-form" id="rpForm">'
      + field("traits", "Temperament", c.traits) + field("speech", "How they talk", c.speech) + field("goal", "What they want most", c.goal)
      + '<label class="wide">Convictions<input name="convictions" value="' + esc(c.convictions) + '"></label>'
      + '<label class="wide">Facts of their life<textarea name="facts" rows="4">' + esc(c.facts) + '</textarea><span class="hint">The people and events the story and every chapter must agree with.</span></label>'
      + '<label class="wide">Story<textarea name="story" rows="5" placeholder="Written by a model from the facts the first time this bot speaks, once a model is assigned to the Memory, Ambient or Quick decisions lane.">'
      + esc(c.story) + "</textarea></label>"
      + '<div class="wide row"><button class="btn primary" type="submit">Save character</button>'
      + '<button class="btn" type="button" id="rpResetStory">Write the story again</button>'
      + '<span class="hint">Saving marks the character as written by you: it is never rewritten behind your back.</span></div></form>'
      + "<h4>Chapters of their life</h4>" + chapters;
  }

  function renderSettings(o) {
    $("mindSettings").innerHTML = SETTING_GROUPS.map(([title, rows]) => '<div class="settings-group"><h3>' + esc(title) + "</h3>"
      + rows.map(([key, label, help, kind]) => {
        const value = o.settings[key];
        const control = kind === "bool"
          ? '<select data-setting="' + key + '"><option value="1"' + (value === "1" ? " selected" : "") + ">On</option><option value=\"0\""
            + (value === "0" ? " selected" : "") + ">Off</option></select>"
          : kind === "choice"
            ? '<select data-setting="' + key + '">' + ["local", "jev"].map(v => '<option value="' + v + '"' + (value === v ? " selected" : "") + ">"
              + (v === "jev" ? "Jev (reads the chat)" : "Local (random fit)") + "</option>").join("") + "</select>"
          : kind === "text"
            ? '<textarea data-setting="' + key + '" rows="' + (key === "ambient_vibe" || key === "personality_mix" ? 5 : 3) + '" style="width:360px"'
              + (o.defaults && o.defaults[key] ? ' placeholder="' + esc(o.defaults[key]) + '"' : "") + ">" + esc(value) + "</textarea>"
            : '<input data-setting="' + key + '" type="number" min="0"' + (kind === "number" ? ' step="0.01"' : "") + ' value="' + esc(value) + '">';
        const kinds = key === "personality_mix" && o.archetypes ? " Kinds: " + o.archetypes.join(", ") + "." : "";
        return '<div class="settings-row"><div class="set-text"><label>' + esc(label) + '</label><p class="set-help">' + esc(help + kinds)
          + '</p></div><div class="set-control">' + control + "</div></div>";
      }).join("") + "</div>").join("");
  }

  /* ---------------- a bot ---------------- */

  function renderBot(view) {
    openBot = view;
    const persona = view.persona || {};
    const facts = botFacts(view.name);
    const awake = overview && overview.awake.find(b => b.bot_guid === view.guid);
    const source = view.persona ? (persona.source === "manual" ? "written by you" : "generated") : "none yet";
    const field = (name, label, value) => '<label>' + esc(label) + '<input name="' + name + '" value="' + esc(value || "") + '"></label>';
    const routeSelect = lane => '<label>' + esc(lane === "smart" ? "Conversation model" : lane === "ambient" ? "Ambient chat model" : "Quick-decision model")
      + '<select data-route="' + lane + '">' + profileOptions((view.routes || {})[lane], "(same as everyone)") + "</select></label>";
    const zone = facts && typeof zoneNameOf === "function" ? zoneNameOf(facts) : "";
    const who = facts ? [facts.c, facts.s, "level " + facts.l, zone, facts.o ? "online" : "offline"].filter(Boolean).join(" · ") : "";
    $("mindBot").innerHTML = '<div class="mind-bot"><h3>' + esc(view.name || "Bot " + view.guid)
      + ' <span class="meta">guid ' + esc(view.guid) + "</span></h3>"
      + (who ? '<p class="who">' + esc(who) + "</p>" : "")
      + '<div class="mind-chips">'
      + '<span class="state ' + (awake ? "on" : "") + '">' + (awake ? "awake · last spoke " + esc(ago(awake.last_ts)) : "asleep: an ordinary playerbot") + "</span>"
      + '<span class="state">personality: ' + esc(source) + "</span>"
      + (view.muted ? '<span class="state bad">muted</span>' : "")
      + (view.usage ? '<span class="state">' + num(view.usage.calls) + " calls, " + money(view.usage.cost_usd || 0) + " today</span>" : "") + "</div>"
      + rpSheet(view)
      + (view.rp && overview && overview.settings.chat_mode === "roleplay"
        ? '<details class="mind-connect"><summary>Fake-player personality (used when Chat style is Fake players)</summary>' : "")
      + '<form class="mind-form" id="personaForm">'
      + field("archetype", "Type", persona.archetype) + field("traits", "Personality", persona.traits)
      + field("speech_style", "How they talk", persona.speech_style) + field("interests", "Interests", persona.interests)
      + '<label class="wide">Opinions and running jokes<textarea name="opinions" rows="2" placeholder="Hot takes they bring up and defend, separated by semicolons">' + esc(persona.opinions || "") + "</textarea></label>"
      + '<label>Chattiness (0 to 100)<input name="chattiness" type="number" min="0" max="100" step="5" value="' + esc(persona.chattiness === undefined ? 50 : persona.chattiness) + '">'
      + '<span class="hint">How often they join in when someone says hello nearby. 10 is a lurker, 90 never stops.</span></label>'
      + '<label class="wide">Backstory<textarea name="backstory" rows="3">' + esc(persona.backstory || "") + "</textarea></label>"
      + '<label>Personality on<select name="enabled"><option value="1"' + (persona.enabled === 0 ? "" : " selected") + ">Yes</option><option value=\"0\""
      + (persona.enabled === 0 ? " selected" : "") + ">No</option></select></label>"
      + routeSelect("smart") + routeSelect("fast") + routeSelect("ambient")
      + '<div class="wide row"><button class="btn primary" type="submit">Save personality</button>'
      + '<button class="btn" type="button" id="personaRoll">Roll a random one</button>'
      + '<select id="personaRollKind" title="Roll one of a chosen kind of person"><option value="">of any kind (by the mix)</option>'
      + ((overview && overview.archetypes) || []).map(kind => '<option value="' + esc(kind) + '">' + esc(kind) + "</option>").join("") + "</select>"
      + '<button class="btn" type="button" id="personaDelete">Remove</button>'
      + '<button class="btn" type="button" id="botMute">' + (view.muted ? "Unmute" : "Mute this bot") + "</button></div>"
      + '<div class="wide row"><input id="personaHint" placeholder="Guidance for the AI, e.g. a grumpy dwarf who loves fishing" size="52">'
      + '<button class="btn" type="button" id="personaWrite">Write one with AI</button>'
      + '<span class="hint">Fills the fields above for you to review. Nothing is saved until you press Save.</span></div></form>'
      + (view.rp && overview && overview.settings.chat_mode === "roleplay" ? "</details>" : "")
      + "<h4>Talk to " + esc(view.name || "this bot") + '</h4><p class="meta">Try the personality without logging in to the game. The bot sees this as an ordinary chat.</p>'
      + '<div class="playground"><div class="talk" id="talkLog">' + talkHtml(view.guid) + "</div>"
      + '<form class="talk-form" id="talkForm"><input name="player" id="talkAs" placeholder="Speak as (character name, optional)" size="22" value="'
      + esc(localStorage.getItem("mindTalkAs") || "") + '"><input name="text" placeholder="Say something..." autocomplete="off" maxlength="400">'
      + '<select name="profile" title="Model">' + profileOptions("", "lane's model") + "</select>"
      + '<label class="check"><input type="checkbox" name="remember"> remember it</label><button class="btn small" type="submit">Send</button>'
      + '<button class="btn small" type="button" id="talkClear">Clear</button></form>'
      + '<details class="mind-connect" id="talkMind" hidden><summary>What the model was shown</summary><pre id="talkMindText"></pre></details></div>'
      + "<h4>Recent conversations</h4>" + botTurns(view)
      + "<h4>Memories (" + view.memories.length + ')</h4>' + memoryList(view)
      + '<form class="mind-memory-add" id="memoryAdd"><input name="player" placeholder="About which player?" size="16">'
      + '<input name="text" placeholder="Something this bot should remember, e.g. Ann is my sworn friend" maxlength="200">'
      + '<button class="btn small" type="submit">Remember</button>'
      + (view.memories.length ? '<button class="btn small" type="button" id="memoryClear">Forget everything</button>' : "") + "</form>"
      + "<h4>Relationships</h4>" + relationshipTable(view) + "</div>";
  }

  const talkHtml = guid => (talk[guid] || []).map(line => '<p class="' + line.role + '"><b>' + esc(line.who) + "</b> " + esc(line.content) + "</p>").join("")
    || '<p class="empty">Nothing said yet.</p>';

  function botTurns(view) {
    if (!view.turns.length) return '<p class="empty">No conversations logged for this bot yet.</p>';
    return '<div class="scroll"><table class="turns"><tbody>' + view.turns.slice(0, 8).map(turnRow).join("") + "</tbody></table></div>";
  }

  function memoryList(view) {
    if (!view.memories.length) return '<p class="empty">Nothing yet. It remembers what players say to it once they talk.</p>';
    return '<ul class="mind-mem">' + view.memories.slice(0, 60).map(m => '<li><span class="kind ' + esc(m.kind) + '">' + esc(m.kind) + "</span>"
      + "<span>" + esc(m.text) + '<span class="ago">' + esc(m.subject_name ? "about " + m.subject_name + " · " : "") + ago(m.created_at)
      + " · importance " + Math.round(m.salience * 100) + "%</span></span>"
      + '<button class="btn small" type="button" data-forget="' + esc(m.id) + '">Delete</button></li>').join("") + "</ul>"
      + (view.memories.length > 60 ? '<p class="meta">Showing the newest 60 of ' + view.memories.length + ".</p>" : "");
  }

  function relationshipTable(view) {
    if (!view.relationships.length) return '<p class="empty">Nobody yet.</p>';
    const feeling = a => a >= 0.6 ? "close friend" : a >= 0.25 ? "friend" : a > -0.25 ? "acquaintance" : a > -0.6 ? "dislikes" : "dislikes strongly";
    return '<table><thead><tr><th>Who</th><th>Feels</th><th class="r">Talks</th><th>Last</th><th>Why</th></tr></thead><tbody>'
      + view.relationships.map(r => "<tr><td class=\"name\">" + esc(r.other_name || "guid " + r.other_guid) + "</td><td>" + esc(feeling(r.affinity))
        + ' <span class="meta">' + (r.affinity >= 0 ? "+" : "") + r.affinity.toFixed(2) + "</span></td><td class=\"r\">" + num(r.interactions)
        + "</td><td class=\"meta\">" + ago(r.last_seen) + '</td><td class="meta">' + esc(r.reason) + "</td></tr>").join("") + "</tbody></table>";
  }

  async function loadBot(name) {
    name = (name || "").trim();
    if (!name) return;
    $("mindBotName").value = name;
    say("", "", "mindBotMsg");
    try {
      renderBot(await request("/api/mind/bot?name=" + encodeURIComponent(name)));
    } catch (error) {
      say(String(error.message || error), "bad", "mindBotMsg");
    }
  }

  const reloadBot = () => openBot ? loadBot(openBot.name) : Promise.resolve();

  /* ---------------- what the rest of the dashboard shows ---------------- */

  async function refreshCards() {
    try {
      const next = await request("/api/mind/cards");
      const changed = JSON.stringify(next) !== JSON.stringify(cards);
      cards = next;
      if (changed && typeof renderRoster === "function" && typeof LAST !== "undefined" && LAST) renderRoster();
    } catch (error) { /* the mind is optional: the cards simply show nothing */ }
  }

  window.mindDot = name => {
    const persona = cards.personas[name];
    if (cards.awake[name]) return ' <span class="mind-dot awake" title="awake: ' + esc(persona ? persona[0] : "talking") + '"></span>';
    if (persona && persona[2]) return ' <span class="mind-dot muted" title="muted"></span>';
    return persona ? ' <span class="mind-dot" title="' + esc(persona[0]) + '"></span>' : "";
  };

  window.botMindHtml = name => {
    const persona = cards.personas[name];
    if (!persona && !cards.awake[name]) return "";
    const state = cards.awake[name] ? "awake" : persona && persona[2] ? "muted" : "asleep";
    return '<div class="bc-mind"><span class="mind-dot ' + (state === "awake" ? "awake" : state === "muted" ? "muted" : "") + '"></span> '
      + esc(persona ? persona[0] : "no personality yet") + ' <span class="meta">· ' + state + "</span></div>";
  };

  window.botMindSheet = name => {
    const persona = cards.personas[name];
    if (!persona && !cards.awake[name]) return "";
    return '<p class="who">Personality: ' + esc(persona ? persona[0] : "none yet") + (cards.awake[name] ? " · awake now" : "")
      + '</p><p><button class="btn small" type="button" data-open-mind="' + esc(name) + '">Open its mind</button></p>';
  };

  /* ---------------- loading ---------------- */

  async function load() {
    try {
      overview = await request("/api/mind");
    } catch (error) {
      $("mindSub").textContent = "unavailable";
      $("mindStatus").innerHTML = '<p class="empty">The Minds page could not load: ' + esc(String(error.message || error)) + "</p>";
      return;
    }
    renderStatus(overview);
    if (!$("mindChatStyle").contains(document.activeElement)) renderChatStyle(overview);
    // A dropdown that is open (or a field being typed in) must not be redrawn under the user's hand.
    if (!$("mindProfiles").contains(document.activeElement)) renderProfiles(overview);
    if (!$("mindSettings").contains(document.activeElement)) renderSettings(overview);
    if (!$("mindAssign").contains(document.activeElement)) renderAssign(overview);
    loadJev();
    loadBank();
    loadCast();
  }

  /* ---------------- the regulars ---------------- */

  let castTimer = null;
  async function loadCast() {
    const result = await act({ op: "cast.status" }, null, "mindCastMsg");
    if (!result) return;
    renderCast(result);
    clearTimeout(castTimer);
    if (result.job && result.job.running) castTimer = setTimeout(loadCast, 4000);
  }

  function renderCast(cast) {
    if (!cast.cast || !cast.cast.length) {
      $("mindCast").innerHTML = '<p class="meta">Nobody yet. The game picks the regulars a little after the realm starts (it needs about thirty bots online).</p>';
      return;
    }
    const job = cast.job || {};
    $("mindCast").innerHTML = "<p>" + cast.size + " regulars"
      + (job.running ? ", writing their characters and friendships now (" + job.sheets + " sheets, " + job.bonds + " friendships so far)" : "")
      + (job.errors ? '. <span class="meta">' + job.errors + " failed: " + esc(job.last_error) + "</span>" : "") + ".</p>"
      + '<div class="cast-list">' + cast.cast.map(m => "<details><summary><strong>" + esc(m.name.replace(/ Bot$/, "")) + "</strong> "
        + '<span class="meta">' + esc(m.archetype || "") + (m.level ? ", level " + m.level : "") + (m.class ? " " + esc(m.class) : "")
        + (m.guild_id ? ", guild " + m.guild_id : "") + "</span></summary>"
        + (m.backstory ? "<p>" + esc(m.backstory) + "</p>" : "")
        + (m.friends && m.friends.length ? '<p class="meta">Knows: ' + m.friends.map(f => esc(f.name.replace(/ Bot$/, "")) + " (" + esc(f.kind) + (f.note ? ": " + esc(f.note) : "") + ")").join("; ") + "</p>" : "")
        + "</details>").join("") + "</div>";
  }

  /* ---------------- the line bank ---------------- */

  let bankTimer = null;
  async function loadBank() {
    const result = await act({ op: "bank.stats" }, null, "mindBankMsg");
    if (!result) return;
    renderBank(result.bank);
    clearTimeout(bankTimer);
    if (result.bank.job && result.bank.job.running) bankTimer = setTimeout(loadBank, 3000);
  }

  function renderBank(bank) {
    if ($("mindBank").contains(document.activeElement)) return;
    const job = bank.job || {}, jev = bank.jev || {};
    const kinds = Object.keys(bank.by_kind).sort();
    const jevText = !jev.key ? "no Jev key, so the local picker is used"
      : jev.paused ? "paused after repeated failures, local picker in use"
        : jev.calls + " picks so far, about $" + (jev.spentUsd || 0).toFixed(4);
    const rpBank = bank.roleplay || { total: 0, by_race: {}, by_situation: {}, by_zone: {} };
    $("mindBank").innerHTML = '<p><strong>Roleplay:</strong> ' + num(rpBank.total) + " in-character lines across " + Object.keys(rpBank.by_race).length + " peoples, "
      + Object.keys(rpBank.by_situation).length + " situations and " + Object.keys(rpBank.by_zone).length + " zones. "
      + '<span class="meta">Written once, for every race and calling of the lore, and used without a model call.</span></p>'
      + '<p>' + esc(String(bank.total)) + " fake-player lines banked"
      + (kinds.length ? " across " + kinds.length + " kinds of person, " + Object.keys(bank.by_situation).length + " situations and " + Object.keys(bank.by_topic || {}).length + " topics" : "")
      + ". Picker: " + esc(bank.picker) + ". Jev: " + esc(jevText) + ".</p>"
      + (job.running ? '<p class="meta">Writing: ' + job.done + " of " + job.total + " done, " + job.added + " lines added"
        + (job.errors ? ", " + job.errors + " failed (" + esc(job.last_error) + ")" : "") + ".</p>"
        : job.total ? '<p class="meta">Last run: ' + job.added + " lines added" + (job.errors ? ", " + job.errors + " failed" : "") + ".</p>" : "")
      + '<div class="settings-actions">'
      + '<select id="bankProfile" title="The model that writes the lines">' + profileOptions(overview.lanes.ambient || overview.lanes.fast, "(the ambient model)") + "</select>"
      + '<select id="bankPerCell" title="Lines per kind of person and situation"><option value="15">15 each</option><option value="30" selected>30 each</option><option value="50">50 each</option></select>'
      + '<button class="btn" type="button" id="bankGenerate"' + (job.running ? " disabled" : "") + ">Write more fake-player lines</button>"
      + '<select id="bankPerCellRp" title="Lines per kind of character and situation"><option value="12">12 each</option><option value="24" selected>24 each</option><option value="36">36 each</option></select>'
      + '<button class="btn primary" type="button" id="bankGenerateRp"' + (job.running ? " disabled" : "") + ">Write roleplay lines</button>"
      + '<button class="btn" type="button" id="bankClear">Empty the bank</button></div>';
  }

  /* ---------------- give bots a personality ---------------- */

  function renderAssign(o) {
    const kept = $("mindAssign").querySelector("textarea");
    const names = kept ? kept.value : "";
    const kind = $("mindAssignKind") ? $("mindAssignKind").value : "";
    $("mindAssign").innerHTML = '<div class="mind-form"><label class="wide">Bot names, separated by commas<textarea id="mindAssignNames" rows="2" placeholder="Bralli Bot, Alte Bot, Serdukurn Bot">' + esc(names) + "</textarea></label>"
      + '<label>Kind of person<select id="mindAssignKind"><option value="">any (by the personality mix)</option>'
      + (o.archetypes || []).map(k => '<option value="' + esc(k) + '"' + (k === kind ? " selected" : "") + ">" + esc(k) + "</option>").join("") + "</select></label>"
      + '<div class="wide row"><button class="btn primary" type="button" id="mindAssignGo">Give them a personality</button></div></div>'
      + '<p class="set-help">Each named bot gets a fresh personality of that kind and keeps it: it counts as written by you, so it is never regenerated. To write one by hand, or change one, open the bot above.</p>';
  }

  /* ---------------- Jev ---------------- */

  async function loadJev() {
    const host = $("mindJev");
    if (!host) return;
    let report;
    try {
      report = await request("/api/mind/jev?hours=24");
    } catch (error) {
      host.innerHTML = '<p class="empty">Jev figures are unavailable: ' + esc(String(error.message || error)) + "</p>";
      return;
    }
    const on = report.enabled.jev;
    const figure = (label, value, foot) => '<div class="figure"><div class="label">' + esc(label)
      + '</div><div class="value num">' + esc(value) + '</div><div class="foot">' + esc(foot || "") + "</div></div>";
    const tactical = report.sites.tactical || {};
    const classifier = report.sites.classifier || {};
    const share = site => {
      if (!site.jev) return "-";
      const total = site.jev.calls + site.llm.calls;
      return total ? Math.round(100 * site.jev.calls / total) + "%" : "-";
    };
    const secs = ms => ms ? (ms / 1000).toFixed(1) + " s" : "-";
    const both = tactical.jev || { calls: 0 };
    $("mindJevSub").textContent = on ? "on" : "off";
    host.innerHTML = '<div class="mind-chips"><span class="state ' + (on ? "on" : "") + '">' + (on ? "Jev is on" : "Jev is off") + "</span>"
      + '<span class="state ' + (report.enabled.tactical ? "on" : "") + '">looking around: ' + (report.enabled.tactical ? "on" : "off") + "</span>"
      + '<span class="state ' + (report.enabled.classifier ? "on" : "") + '">short commands: ' + (report.enabled.classifier ? "on" : "off") + "</span></div>"
      + '<div class="mind-figures">'
      + figure("Decisions by Jev", num(report.jev_calls), "last " + report.hours + " hours")
      + figure("Looking around", share(tactical), tactical.jev ? "decided by Jev, " + secs(tactical.jev.ms) + " each vs " + secs(tactical.llm.ms) + " on the model" : "no data")
      + figure("Short commands", share(classifier), classifier.jev ? "decided by Jev, " + secs(classifier.jev.ms) + " each vs " + secs(classifier.llm.ms) + " on the model" : "no data")
      + figure("Jev cost", money(report.jev_cost), "at $" + report.price_per_m + " per million tokens")
      + figure("The model would have cost", money(report.displaced_cost), "the same decisions at " + money(report.llm_cost_per_call || 0) + " each")
      + figure("Saved", (report.saved < 0 ? "-" : "") + money(Math.abs(report.saved)), report.saved < 0 ? "Jev is costing more here" : "over the same hours")
      + "</div>"
      + '<p class="set-help">A decision Jev was not sure about is made by the language model and counted there, so Jev\'s spend on those is not in this figure. Turn Jev\'s parts on and off under Settings, Minds (Jev). The TypeSafe key is read from the server\'s environment, never typed here.</p>';
  }

  /* ---------------- events ---------------- */

  document.addEventListener("click", async event => {
    const target = event.target.closest("button, tr[data-turn]");
    if (!target || !$("mindStatus")) return;
    const data = target.dataset;
    const at = messageAt(target);

    if (data.turn) { openTurn(data.turn); return; }
    if (data.openMind) { $("sheet").close(); location.hash = "#minds"; loadBot(data.openMind); return; }
    if (target.id === "mindSheetClose") { $("mindSheet").close(); return; }
    if (data.bot !== undefined) { if (data.bot) loadBot(data.bot); return; }
    if (target.id === "mindFind") { loadBot($("mindBotName").value); return; }
    if (target.id === "mindAdd") { profileForm(null); return; }
    if (target.id === "profileCancel") { $("mindProfileForm").innerHTML = ""; return; }
    if (target.id === "mindPause") {
      const paused = overview.settings.paused === "1";
      await act({ op: "setting.set", key: "paused", value: !paused }, () => { say(paused ? "Resumed." : "Paused: every bot now answers nothing.", "good", at); load(); }, at);
      return;
    }
    if (target.id === "turnRefresh") { turnsBefore = null; loadTurns(false); return; }
    if (target.id === "turnMore") { loadTurns(true); return; }
    if (data.days) {
      analyticsDays = Number(data.days);
      for (const tab of document.querySelectorAll("#mindDays button")) tab.setAttribute("aria-selected", String(tab === target));
      loadUsage();
      return;
    }
    if (data.problems !== undefined && target.closest("#turnKind")) {
      for (const tab of document.querySelectorAll("#turnKind button")) tab.setAttribute("aria-selected", String(tab === target));
      turnsBefore = null;
      loadTurns(false);
      return;
    }
    if (data.preset) {
      const [url, env, model, extra] = data.preset.split("|");
      const form = $("profileForm").elements;
      form.base_url.value = url;
      form.api_key_env.value = env;
      if (model && !form.model.value) form.model.value = model;
      if (extra && !form.extra.value) form.extra.value = extra;
      if (!form.name.readOnly && !form.name.value) form.name.value = target.textContent.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
      form.model.focus();
      return;
    }
    if (data.edit) { profileForm(overview.profiles.find(p => p.name === data.edit)); return; }
    if (data.del) {
      if (window.confirm("Delete the model \"" + data.del + "\"? Bots and lanes using it will have none until you pick another.")) {
        await act({ op: "profile.delete", name: data.del }, () => { say("Deleted " + data.del, "good", at); load(); }, at);
      }
      return;
    }
    if (data.test) {
      say("Testing " + data.test + "...", "", at);
      target.disabled = true;
      const result = await act({ op: "profile.test", name: data.test }, null, at);
      target.disabled = false;
      if (result) say(result.ok ? data.test + " answered \"" + result.reply + "\" in " + result.ms + " ms" : data.test + " failed: " + result.error, result.ok ? "good" : "bad", at);
      load();
      return;
    }
    if (target.id === "personaRoll") {
      await act({ op: "persona.roll", guid: openBot.guid, archetype: $("personaRollKind").value }, () => { reloadBot(); say("New personality rolled.", "good", at); }, at);
      return;
    }
    if (target.id === "personaWrite") {
      const form = $("personaForm").elements;
      const facts = botFacts(openBot.name) || {};
      say("Asking the model...", "", at);
      target.disabled = true;
      const result = await act({ op: "persona.write", guid: openBot.guid, hint: $("personaHint").value, facts: {
        name: openBot.name, class: facts.c, spec: facts.s, level: facts.l, faction: facts.f,
        zone: typeof zoneNameOf === "function" && facts.n ? zoneNameOf(facts) : "" } }, null, at);
      target.disabled = false;
      if (result) {
        for (const key of ["archetype", "traits", "speech_style", "interests", "opinions", "chattiness"]) form[key].value = result.persona[key];
        form.backstory.value = result.persona.backstory;
        say("Written. Read it, change what you like, then press Save personality.", "good", at);
      }
      return;
    }
    if (target.id === "botMute") {
      await act({ op: "bot.mute", guid: openBot.guid, name: openBot.name, muted: !openBot.muted },
        () => { reloadBot(); say(openBot.muted ? "Unmuted." : "Muted: this bot makes no more model calls.", "good", at); }, at);
      return;
    }
    if (target.id === "personaDelete") {
      if (window.confirm("Remove this bot's personality? It gets a fresh generated one the next time it speaks (if that is on).")) {
        await act({ op: "persona.delete", guid: openBot.guid }, () => { reloadBot(); say("Removed.", "good", at); }, at);
      }
      return;
    }
    if (target.id === "talkClear") { talk[openBot.guid] = []; $("talkLog").innerHTML = talkHtml(openBot.guid); $("talkMind").hidden = true; return; }
    if (data.forget) {
      await act({ op: "memory.delete", guid: openBot.guid, id: Number(data.forget) }, reloadBot, at);
      return;
    }
    if (target.id === "memoryClear") {
      if (window.confirm("Make " + openBot.name + " forget everything, and every relationship? This cannot be undone.")) {
        await act({ op: "memory.clear", guid: openBot.guid }, () => { reloadBot(); say("Forgotten.", "good", at); }, at);
      }
      return;
    }
    if (target.id === "mindAssignGo") {
      const names = $("mindAssignNames").value;
      const result = await act({ op: "persona.assign", names, archetype: $("mindAssignKind").value }, null, at);
      if (result) {
        const done = result.assigned.map(a => a.name + " (" + a.archetype + ")").join(", ");
        say((done ? "Done: " + done + "." : "Nobody was changed.") + (result.unknown.length ? " Not found: " + result.unknown.join(", ") + "." : ""),
          result.unknown.length && !done ? "bad" : "good", at);
        refreshCards();
      }
      return;
    }
    if (data.chatmode) {
      await act({ op: "setting.set", key: "chat_mode", value: data.chatmode }, () => {
        say(data.chatmode === "roleplay" ? "Roleplay: the bots are characters in the lore from now on." : "Fake players: the bots chat like players again.", "good", at);
        load();
      }, at);
      return;
    }
    if (target.id === "rpResetAll") {
      if (window.confirm("Throw away every written backstory and chapter? They are written again, from the same facts, the next time each bot speaks. Characters you edited are kept.")) {
        await act({ op: "rp.reset_all" }, result => { say("Cleared " + (result && result.cleared || 0) + " stories.", "good", at); load(); }, at);
      }
      return;
    }
    if (target.id === "rpResetStory") {
      await act({ op: "rp.reset_story", guid: openBot.guid }, () => { reloadBot(); say("Cleared: the story is written again the next time this bot speaks.", "good", at); }, at);
      return;
    }
    if (target.id === "bankGenerateRp") {
      const profile = $("bankProfile").value;
      await act({ op: "bank.generate", mode: "roleplay", profile: profile || undefined, per_cell: Number($("bankPerCellRp").value) },
        () => { say("Writing roleplay lines in the background.", "good", "mindBankMsg"); loadBank(); }, "mindBankMsg");
      return;
    }
    if (target.id === "bankGenerate") {
      const profile = $("bankProfile").value;
      await act({ op: "bank.generate", profile: profile || undefined, per_cell: Number($("bankPerCell").value) },
        () => { say("Writing lines in the background.", "good", "mindBankMsg"); loadBank(); }, "mindBankMsg");
      return;
    }
    if (target.id === "bankClear") {
      if (window.confirm("Delete every banked line? Bots go back to asking the model until you write more.")) {
        await act({ op: "bank.clear" }, () => { say("Bank emptied.", "good", "mindBankMsg"); loadBank(); }, "mindBankMsg");
      }
      return;
    }
    if (target.id === "mindRerollAll") {
      if (window.confirm("Throw away every automatically made personality? Each bot gets a new one the next time it speaks. Personalities you wrote or edited are kept.")) {
        await act({ op: "persona.reroll_all" }, result => say("Cleared " + (result && result.cleared || 0) + " generated personalities. They roll again as the bots speak.", "good", at), at);
      }
      return;
    }
    if (target.id === "mindExport" || target.id === "mindExportFull") {
      try {
        const full = target.id === "mindExportFull";
        const document_ = await request("/api/mind/export" + (full ? "?full=1" : ""));
        const link = document.createElement("a");
        link.href = URL.createObjectURL(new Blob([JSON.stringify(document_, null, 1)], { type: "application/json" }));
        link.download = "squidbots-minds" + (full ? "-full" : "") + "-" + new Date().toISOString().slice(0, 10) + ".json";
        link.click();
        URL.revokeObjectURL(link.href);
        say("Exported " + document_.personas.length + " personalities" + (full ? ", " + (document_.memories || []).length + " memories" : "") + ".", "good", at);
      } catch (error) { say(String(error.message || error), "bad", at); }
      return;
    }
    if (target.id === "mindImport") { $("mindImportFile").click(); }
  });

  document.addEventListener("submit", async event => {
    const form = event.target;
    const at = messageAt(form);
    const values = () => Object.fromEntries(new FormData(form).entries());
    if (form.id === "profileForm") {
      event.preventDefault();
      const fields = values();
      await act(Object.assign({ op: "profile.save" }, fields), () => {
        $("mindProfileForm").innerHTML = "";
        say("Saved " + fields.name + ". Use Test to check it answers.", "good", at);
        load();
      }, at);
    } else if (form.id === "personaForm") {
      event.preventDefault();
      await act(Object.assign({ op: "persona.save", guid: openBot.guid, name: openBot.name }, values()),
        () => { reloadBot(); say("Saved.", "good", at); refreshCards(); }, at);
    } else if (form.id === "rpForm") {
      event.preventDefault();
      await act(Object.assign({ op: "rp.save", guid: openBot.guid }, values()), () => { reloadBot(); say("Saved.", "good", at); }, at);
    } else if (form.id === "memoryAdd") {
      event.preventDefault();
      const fields = values();
      await act({ op: "memory.add", guid: openBot.guid, subject_name: fields.player, text: fields.text }, reloadBot, at);
    } else if (form.id === "talkForm") {
      event.preventDefault();
      const fields = values();
      if (!fields.text.trim()) return;
      try { localStorage.setItem("mindTalkAs", fields.player || ""); } catch (error) { /* private window */ }
      const lines = talk[openBot.guid] = talk[openBot.guid] || [];
      const history = lines.map(line => ({ role: line.role, content: line.content }));
      lines.push({ role: "user", who: fields.player || "You:", content: fields.text });
      $("talkLog").innerHTML = talkHtml(openBot.guid) + '<p class="thinking">…</p>';
      form.elements.text.value = "";
      const result = await act({ op: "chat.try", guid: openBot.guid, name: openBot.name, player: fields.player, text: fields.text,
        history, remember: fields.remember === "on", profile: fields.profile }, null, at);
      if (result) {
        lines.push({ role: "assistant", who: openBot.name + ":", content: result.reply || "(no text)" });
        const m = result.mind || {};
        $("talkMind").hidden = false;
        $("talkMindText").textContent = "Model: " + (m.profile || "?") + " / " + (m.model || "?") + " · " + ((m.latency_ms || 0) / 1000).toFixed(1) + " s"
          + (m.cost_usd ? " · " + money(m.cost_usd) : "") + " · " + (m.recalled || 0) + " memories recalled\n\n" + (m.mind_block || "(no personality added)");
      } else {
        lines.pop();
      }
      $("talkLog").innerHTML = talkHtml(openBot.guid);
      $("talkLog").scrollTop = $("talkLog").scrollHeight;
      if (result) {
        // Memories, conversations and relationships moved: reload them, and put the explanation back afterwards.
        const shown = { hidden: $("talkMind").hidden, text: $("talkMindText").textContent, open: $("talkMind").open };
        await reloadBot();
        $("talkMind").hidden = shown.hidden;
        $("talkMind").open = shown.open;
        $("talkMindText").textContent = shown.text;
        $("talkLog").scrollTop = $("talkLog").scrollHeight;
        load();
      }
    }
  });

  document.addEventListener("change", async event => {
    const target = event.target;
    const at = messageAt(target);
    const saved = () => say("Saved.", "good", at);
    if (target.dataset.lane) {
      await act({ op: "lane.set", lane: target.dataset.lane, profile: target.value }, saved, at);
    } else if (target.dataset.route && openBot) {
      await act({ op: "route.set", guid: openBot.guid, lane: target.dataset.route, profile: target.value }, saved, at);
    } else if (target.dataset.rpchannel) {
      const kinds = [...document.querySelectorAll("[data-rpchannel]")].filter(box => box.checked).map(box => box.dataset.rpchannel).join(",");
      await act({ op: "setting.set", key: "rp_channels", value: kinds }, () => { saved(); load(); }, at);
    } else if (target.dataset.setting) {
      await act({ op: "setting.set", key: target.dataset.setting, value: target.value }, () => { saved(); load(); }, at);
    } else if (target.id === "mindImportFile" && target.files.length) {
      let file;
      try { file = JSON.parse(await target.files[0].text()); } catch (error) { say("That file is not JSON.", "bad", at); return; }
      target.value = "";
      const overwrite = window.confirm("Replace personalities that already exist?\n\nOK replaces them, Cancel keeps the ones you have and only adds new ones.");
      await act(Object.assign({}, file, { op: "persona.import", overwrite }), result => {
        say("Imported " + result.added + ", kept " + result.skipped + " you already had"
          + (result.unknown ? ", " + result.unknown + " names not found in the game" : "") + (result.memories ? ", " + result.memories + " memories restored" : "") + ".", "good", at);
        load();
        refreshCards();
      }, at);
    }
  });

  document.addEventListener("keydown", event => {
    if (event.key !== "Enter") return;
    if (event.target.id === "mindBotName") loadBot(event.target.value);
    if (event.target.id === "turnBot" || event.target.id === "turnPlayer") { turnsBefore = null; loadTurns(false); }
  });

  /* ---------------- lifecycle ---------------- */

  // Refresh only while the page is showing: the service status and spend move; the forms below do not.
  function sync() {
    if (PAGE === "minds") {
      if (!timer) {
        load();
        loadUsage();
        loadTurns(false);
        timer = setInterval(() => {
          if (document.hidden) return;
          load();
          usageTimer = (usageTimer + 1) % 6;
          if (!usageTimer) loadUsage();
          const active = document.activeElement;
          if (turnsBefore === null || !$("mindTurns").contains(active)) loadTurns(false);
        }, 10000);
      }
    } else if (timer) {
      clearInterval(timer);
      timer = null;
    }
  }
  window.addEventListener("hashchange", sync);
  sync();
  refreshCards();
  setInterval(() => { if (!document.hidden) refreshCards(); }, 30000);
})();
