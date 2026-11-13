/* The living world (CoA Bots 3.0): what the bots do, from the files SquidBot writes.
   Private page, on this PC only. Reads /api/vivant (webapp/vivant.py), which answers with made-up figures,
   marked "demo", for each topic the module does not write yet. Uses server.js (SW, coins, ago, getJson). */

const VIVANT_WORDS = {
  en: {
    tabs: { population: "Population", monde: "World life", economy: "Economy", groups: "Groups & dungeons", health: "Health", events: "Journal" },
    allKinds: "All", noEvent: "Nothing in the journal yet.", eventsHelp: "The newest 200 lines of events.jsonl, written by the server as things happen.",
    kind: { invasion: "Invasion", rush: "Rush", server_first: "Server first", guild: "Guild", stuck: "Stuck", unstuck: "Unstuck", boss: "Boss", wipe: "Wipe", order: "Order", error: "Error" },
    demo: t => "Made-up figures for " + t + ": the server does not write these files yet (CoA Bots 3.0).",
    stale: t => "Not updated for a while: " + t + ". The module has stopped writing, or the realm is down.",
    online: "Bots online", players: "Players", inCapitals: "In capitals", busy: "In a dungeon", stuck: "Stuck", zonesUsed: "Zones with bots", inBg: "In battlegrounds and arenas", pvpAll: n => n + " in PvP in all",
    demoTab: "Made-up figures: nothing on this tab comes from the server yet.",
    leveling: "XP catch-up", catchOn: "Catch-up on", catchOff: "Catch-up off (AiPlayerbot.CoaFreshStart.CatchUp.Enable = 0): the bots level at the normal pace.",
    frontIs: (lv, n) => "Players' front: level " + lv + " (median of " + n + " active players)", noFront: n => "No players' front: " + n + " active players, too few to set one.",
    surveyed: t => "counted " + t + " ago, every 10 minutes", byLevel: "Random bots by level (online or not)", pcts: (a, b, c) => "p10 " + a + " · p50 " + b + " · p90 " + c,
    hourlyTitle: "Bots' levels and players' front, hour by hour", front: "Players' front", hourlyWait: "One point an hour: the curve starts after the second hour.",
    raid: "Capital raid", raidPhase: { gathering: "gathering", assault: "assault" }, raidLine: (a, d) => a + " attackers · " + d + " defenders",
    king: n => "leader at " + n + " % health", stepOf: (a, b) => "step " + a + "/" + b, assaultAt: "assault",
    realNow: "Real groups in instances", simNow: "Simulated dungeons", bgNow: "Battlegrounds and arenas", bgSimOff: "Simulated battlegrounds: off.", bgSimTitle: "Simulated",
    noRealBg: "Nobody in a battleground or an arena right now.", lastReal: "Last real runs", lastSim: "Last simulated runs",
    dcRuns: "Dungeon Clear runs (detail)", parts: n => n + " dc on in a row", leader: "led by", noRealRun: "No real run since the server start.", noSim: "No simulated dungeon right now.", noBg: "No simulated battleground right now.",
    simOff: "Simulated dungeons are off: AiPlayerbot.CoaWorld.DungeonSim.Enable = 1 in playerbots.conf.",
    phase: { gathering: "gathering", inside: "inside", back: "coming back", playing: "playing" }, faction: { alliance: "Alliance", horde: "Horde" },
    realSim: (a, b) => a + " real · " + b + " simulated", realOnly: "real groups", sinceAt: t => "since " + t, simItems: n => n + " items looted by simulated runs today",
    bgToday: (m, a, h, hon) => "Today: " + m + " matches, Alliance " + a + " · Horde " + h + " wins, " + hon + " honor", won: side => side + " won", honor: "honor",
    everyone: "Everyone online", allChars: "Characters online", whoCols: ["Players", "Alts", "Bots", "All"], split: (p, a, b) => p + " players · " + a + " alts · " + b + " bots",
    place: { arena: "Arena", battleground: "Battleground", raid: "Raid", dungeon: "Dungeon", capital: "Capital", world: "Out in the world" },
    raidPart: n => "of which " + n + " in a raid", everyoneHelp: "Players, their alts and party bots, and the random bots; each one counted once, in the first place that fits: arena, battleground, raid, dungeon, capital, world.", soon: "comes with CoA Bots 3.0", perfOff: "PerfMon is off on this realm: no cost by strategy. Turn it on with .playerbots pmon toggle (game master, in game or at the world console), or AiPlayerbot.PerfMonEnabled = 1 in playerbots.conf.",
    missing: (what, key) => "No " + what + " from this realm: turn on " + key + " = 1 in playerbots.conf (with AiPlayerbot.CoaDataFiles = 1), then restart the realm.",
    noDataYet: "No data yet: real and simulated dungeon groups come with CoA Bots 3.0 (CoA SquidBot, CoA World, Dungeon Clear).",
    files: { world: "population and health file (world.json)", economy: "economy file (economy.json)", monde: "world life file (monde.json)", events: "journal (events.jsonl)" },
    zones: "Where they are", capital: "capital", activities: "What they do", souls: "Souls", surnames: "Surnames", soonL1: "comes with CoA Bots 3.0 (L1)", soulsOff: "Souls are off on this realm (AiPlayerbot.CoaSoul.Enable = 0).",
    surnameMode: ["None", "“Bot”", "From the list"], surnameHelp: ["Bots show their first name only.", "Every bot is named “First Bot” (as in 2.x).", n => "A family name per bot, drawn once from a list of " + n + "."],
    mostWorn: "Most worn",
    act: { quest: "Questing", grind: "Grinding", camp: "Camping", city: "In town", travel: "Travelling", flight: "Flying", wander_random: "Wandering", wander_npc: "Visiting NPCs",
      rest: "Resting", fish: "Fishing", gather: "Gathering", pvp: "PvP", dungeon: "Dungeon (simulated)", idle: "Idle" },
    capitals: "Capitals", alliance: "Alliance", horde: "Horde", noCapital: "No bot in a capital right now.",
    invasionsNow: "Invasions", rushesNow: "Rushes", guilds: "Guilds", guildOrders: "Guild orders", stuck24: "Stuck, 24 h", unstuck24: "Freed, 24 h",
    happening: "Happening now", nothingNow: "No invasion or rush right now.", ends: "ends", members: "Members", onlineCol: "All online", bank: "Bank", openOrders: "Open orders",
    noGuild: "No guild yet.", noGuildOrder: "No guild order.", firsts: "Server firsts", noFirst: "No server first yet.", highlights: "Latest highlights",
    noHighlight: "Nothing yet in the journal.", fromEvents: "counted in events.jsonl", guildOrderState: { shared: "shared from the bank", crafted: "crafted", bought: "bought", none: "not served", open: "open", done: "done" },
    botsOnline: "Bots online", announced: "announced", starts: "starts", wave: "wave", nodes: "nodes", level: "level", servedBy: "by", sinceStart: "since the server start",
    smelt: "Smelting, 24 h", disenchant: "Disenchanting and prospecting, 24 h", fromItems: n => "from " + n + " items", fromOre: n => "prospected from " + n + " ore", resumed: "Auctions shifted at start-up", clock: "Auction clock",
    clockOn: "Auctions run on game time: the hours the server is off are added to every auction.", clockOff: "Auctions run on real time (clock off).",
    offlineAdded: "Added at the last start", expired: "Expired, 24 h", soldClock: "Sold, 24 h", relisted: "Relisted, 24 h",
    ahbot: "Auction house bot, 24 h", listed: "Listed", bought: "Bought", goldIn: "Gold in", goldOut: "Gold out",
    ramping: "Ramping up", rampFoot: (o, t) => o + " / " + t + " bots in, tick counted 5 min after 95 %", rampLeft: m => "tick counted in " + m + " min",
    maxSinceStart: "max since the server start", stuckSince: t => "Stuck bots since " + t, unstuckSince: t => "Freed since " + t, detections: n => n + " detections",
    stuckEvents: "From the journal (stuck and freed)", liveLog: "Live log", logHelp: "The newest lines of CoaBots.log, read again every 15 s.", logFilter: "Filter",
    noLog: "No CoaBots.log for this realm.", noMatch: "No line matches.",
    soul: { lazy: "Lazy", quester: "Quester", wanderer: "Wanderer", trader: "Trader", pvp: "PvP" },
    auctions: "Auctions", goldAll: "Gold in circulation", goldBots: "Held by bots", sold24: "Sold, 24 h", crafted24: "Crafted, 24 h", ordersTile: "Orders (last 50)", refusedN: n => n + " refused", goldWait: "first count within 10 min", needs: what => "Nothing yet: needs " + what + " in the module settings.", nothing24: "Nothing yet in the last 24 h.", noAuction: "No auction right now.",
    categories: "Prices by category", cat: "Category", avg: "Average", band: "Low · usual · high", volume: "Sold 24 h",
    topSales: "Best sellers, 24 h", crafts: "Crafts, 24 h", orders: "Orders to crafting bots", item: "Item", qty: "Qty", gold: "Gold",
    orderState: { mailed: "mailed", refused: "refused", busy: "busy" },
    by: "by", forWhom: "for", profit: "profit", auctionsWeek: "Auctions, 48 h",
    runsToday: "Runs today", cleared: "Cleared", wipes: "Wipes", bossKills: "Bosses killed", running: "Running now",
    noRun: "No group in a dungeon right now.", dungeon: "Dungeon", runs: "Runs", median: "Median", best: "Best", started: "started",
    bosses: "bosses", lastRuns: "Last runs", result: { clear: "cleared", wipe: "wiped", aborted: "aborted", setup_failed: "failed to start", left: "left" }, difficulty: ["", "heroic", "mythic"], perDungeon: "By dungeon",
    tick: "World tick", tickFoot: (p, m) => (p === null ? "" : "p95 " + p + " ms · ") + (m === null ? "" : "max " + m + " ms"), botsCpu: "Bots per tick", botsCpuFoot: p => "p95 " + p + " ms",
    build: "Snapshot cost", buildFoot: "on the world thread, all files", strategies: "Cost by strategy, microseconds per tick",
    stuckList: "Stuck bots", noStuck: "No bot is stuck.", since: "since", tickChart: "Tick (ms), 6 h", botsChart: "Bots online, 6 h", curveWait: "The curve draws itself as readings come in: a point every 5 minutes while this page is open.",
    actionsSoon: "Commands to the bots (stop, resume, summon, unstuck) arrive with the module, through the world console.",
  },
  fr: {
    tabs: { population: "Population", monde: "Vie du monde", economy: "Économie", groups: "Groupes et donjons", health: "Santé", events: "Journal" },
    allKinds: "Tout", noEvent: "Rien dans le journal pour l’instant.", eventsHelp: "Les 200 dernières lignes d’events.jsonl, écrites par le serveur au fil de l’eau.",
    kind: { invasion: "Invasion", rush: "Ruée", server_first: "Premier du serveur", guild: "Guilde", stuck: "Coincé", unstuck: "Décoincé", boss: "Boss", wipe: "Wipe", order: "Commande", error: "Erreur" },
    demo: t => "Données factices pour " + t + " : le serveur n'écrit pas encore ces fichiers (CoA Bots 3.0).",
    stale: t => "Pas de mise à jour depuis un moment : " + t + ". Le module n'écrit plus, ou le royaume est arrêté.",
    online: "Bots en ligne", players: "Joueurs", inCapitals: "En capitale", busy: "En donjon", stuck: "Coincés", zonesUsed: "Zones occupées", inBg: "En champ de bataille ou arène", pvpAll: n => n + " en JcJ au total",
    demoTab: "Chiffres factices : rien dans cet onglet ne vient encore du serveur.",
    leveling: "Rattrapage d’XP", catchOn: "Rattrapage actif", catchOff: "Rattrapage coupé (AiPlayerbot.CoaFreshStart.CatchUp.Enable = 0) : les bots montent au rythme normal.",
    frontIs: (lv, n) => "Front des joueurs : niveau " + lv + " (médiane de " + n + " joueurs actifs)", noFront: n => "Pas de front des joueurs : " + n + " joueurs actifs, trop peu pour en fixer un.",
    surveyed: t => "compté il y a " + t + ", toutes les 10 minutes", byLevel: "Bots aléatoires par niveau (en ligne ou non)", pcts: (a, b, c) => "p10 " + a + " · p50 " + b + " · p90 " + c,
    hourlyTitle: "Niveaux des bots et front des joueurs, heure par heure", front: "Front des joueurs", hourlyWait: "Un point par heure : la courbe commence après la deuxième heure.",
    raid: "Raid de capitale", raidPhase: { gathering: "rassemblement", assault: "assaut" }, raidLine: (a, d) => a + " attaquants · " + d + " défenseurs",
    king: n => "chef à " + n + " % de vie", stepOf: (a, b) => "étape " + a + "/" + b, assaultAt: "assaut",
    realNow: "Groupes réels en instance", simNow: "Donjons simulés", bgNow: "Champs de bataille et arènes", bgSimOff: "BG simulés : coupés.", bgSimTitle: "Simulés",
    noRealBg: "Personne en champ de bataille ou en arène en ce moment.", lastReal: "Derniers runs réels", lastSim: "Derniers runs simulés",
    dcRuns: "Runs Dungeon Clear (détail)", parts: n => n + " dc on à la suite", leader: "mené par", noRealRun: "Aucun run réel depuis le démarrage du serveur.", noSim: "Aucun donjon simulé en ce moment.", noBg: "Aucun champ de bataille simulé en ce moment.",
    simOff: "Les donjons simulés sont coupés : AiPlayerbot.CoaWorld.DungeonSim.Enable = 1 dans playerbots.conf.",
    phase: { gathering: "rassemblement", inside: "à l’intérieur", back: "retour", playing: "en cours" }, faction: { alliance: "Alliance", horde: "Horde" },
    realSim: (a, b) => a + " réels · " + b + " simulés", realOnly: "groupes réels", sinceAt: t => "depuis " + t, simItems: n => n + " objets ramassés par les runs simulés aujourd’hui",
    bgToday: (m, a, h, hon) => "Aujourd’hui : " + m + " matchs, victoires Alliance " + a + " · Horde " + h + ", " + hon + " points d’honneur", won: side => "victoire " + side, honor: "honneur",
    everyone: "Tout le monde en ligne", allChars: "Personnages en ligne", whoCols: ["Joueurs", "Alts", "Bots", "Total"], split: (p, a, b) => p + " joueurs · " + a + " alts · " + b + " bots",
    place: { arena: "Arène", battleground: "Champ de bataille", raid: "Raid", dungeon: "Donjon", capital: "Capitale", world: "Dans le monde" },
    raidPart: n => "dont " + n + " en raid", everyoneHelp: "Les joueurs, leurs alts et bots de groupe, et les bots aléatoires ; chacun compté une fois, au premier lieu qui convient : arène, champ de bataille, raid, donjon, capitale, monde.", soon: "arrive avec CoA Bots 3.0", perfOff: "PerfMon est coupé sur ce royaume : pas de coût par stratégie. Active-le avec .playerbots pmon toggle (maître de jeu, en jeu ou à la console du monde), ou AiPlayerbot.PerfMonEnabled = 1 dans playerbots.conf.",
    missing: (what, key) => "Pas de " + what + " sur ce royaume : active " + key + " = 1 dans playerbots.conf (avec AiPlayerbot.CoaDataFiles = 1), puis redémarre le royaume.",
    noDataYet: "Pas encore de données : les groupes réels et simulés arrivent avec CoA Bots 3.0 (CoA SquidBot, CoA Monde, Dungeon Clear).",
    files: { world: "fichier de population et de santé (world.json)", economy: "fichier d’économie (economy.json)", monde: "fichier de vie du monde (monde.json)", events: "journal (events.jsonl)" },
    zones: "Où ils sont", capital: "capitale", activities: "Ce qu'ils font", souls: "Âmes", surnames: "Surnoms", soonL1: "arrive avec CoA Bots 3.0 (L1)", soulsOff: "Les âmes sont coupées sur ce royaume (AiPlayerbot.CoaSoul.Enable = 0).",
    surnameMode: ["Aucun", "« Bot »", "Liste"], surnameHelp: ["Les bots ne montrent que leur prénom.", "Chaque bot s'appelle « Prénom Bot » (comme en 2.x).", n => "Un nom de famille par bot, tiré une fois pour toutes d'une liste de " + n + "."],
    mostWorn: "Les plus portés",
    act: { quest: "En quête", grind: "Farm", camp: "Campent", city: "En ville", travel: "En voyage", flight: "En vol", wander_random: "Se promènent", wander_npc: "Chez les PNJ",
      rest: "Se reposent", fish: "Pêche", gather: "Récolte", pvp: "JcJ", dungeon: "Donjon (simulé)", idle: "Inactifs" },
    capitals: "Capitales", alliance: "Alliance", horde: "Horde", noCapital: "Aucun bot en capitale pour l’instant.",
    invasionsNow: "Invasions", rushesNow: "Ruées", guilds: "Guildes", guildOrders: "Commandes de guilde", stuck24: "Coincés, 24 h", unstuck24: "Décoincés, 24 h",
    happening: "En ce moment", nothingNow: "Aucune invasion ni ruée en ce moment.", ends: "fin", members: "Membres", onlineCol: "Tous en ligne", bank: "Banque", openOrders: "Commandes ouvertes",
    noGuild: "Aucune guilde pour l’instant.", noGuildOrder: "Aucune commande de guilde.", firsts: "Premiers du serveur", noFirst: "Aucun premier du serveur pour l’instant.", highlights: "Derniers faits marquants",
    noHighlight: "Rien dans le journal pour l’instant.", fromEvents: "comptés dans events.jsonl", guildOrderState: { shared: "donnée par la banque", crafted: "fabriquée", bought: "achetée", none: "non servie", open: "ouverte", done: "livrée" },
    botsOnline: "Bots en ligne", announced: "annoncée", starts: "début", wave: "vague", nodes: "filons", level: "niveau", servedBy: "par", sinceStart: "depuis le démarrage du serveur",
    smelt: "Fonte, 24 h", disenchant: "Désenchantement et prospection, 24 h", fromItems: n => "de " + n + " objets", fromOre: n => "prospecté dans " + n + " minerais", resumed: "Enchères décalées au démarrage", clock: "Horloge des enchères",
    clockOn: "Les enchères tournent sur le temps de jeu : les heures où le serveur est arrêté sont ajoutées à chaque enchère.", clockOff: "Les enchères tournent sur le temps réel (horloge coupée).",
    offlineAdded: "Ajouté au dernier démarrage", expired: "Expirées, 24 h", soldClock: "Vendues, 24 h", relisted: "Remises en vente, 24 h",
    ahbot: "Bot de l’hôtel des ventes, 24 h", listed: "Mises en vente", bought: "Achats", goldIn: "Or reçu", goldOut: "Or dépensé",
    ramping: "Montée en charge", rampFoot: (o, t) => o + " / " + t + " bots connectés, tick compté 5 min après 95 %", rampLeft: m => "tick compté dans " + m + " min",
    maxSinceStart: "max depuis le démarrage", stuckSince: t => "Bots coincés depuis " + t, unstuckSince: t => "Décoincés depuis " + t, detections: n => n + " détections",
    stuckEvents: "D’après le journal (coincés et décoincés)", liveLog: "Logs en direct", logHelp: "Les dernières lignes de CoaBots.log, relues toutes les 15 s.", logFilter: "Filtrer",
    noLog: "Pas de CoaBots.log pour ce royaume.", noMatch: "Aucune ligne ne correspond.",
    soul: { lazy: "Paresseux", quester: "Quêteur", wanderer: "Flâneur", trader: "Commerçant", pvp: "JcJ" },
    auctions: "Enchères", goldAll: "Or en circulation", goldBots: "Détenu par les bots", sold24: "Vendus, 24 h", crafted24: "Fabriqués, 24 h", ordersTile: "Commandes (50 dernières)", refusedN: n => n + " refusée(s)", goldWait: "premier compte sous 10 min", needs: what => "Rien pour l’instant : il faut " + what + " dans les réglages du module.", nothing24: "Rien pour l’instant sur les dernières 24 h.", noAuction: "Aucune enchère pour l’instant.",
    categories: "Prix par catégorie", cat: "Catégorie", avg: "Moyen", band: "Bas · usuel · haut", volume: "Vendus 24 h",
    topSales: "Meilleures ventes, 24 h", crafts: "Artisanat, 24 h", orders: "Commandes aux bots artisans", item: "Objet", qty: "Qté", gold: "Or",
    orderState: { mailed: "envoyée", refused: "refusée", busy: "artisan occupé" },
    by: "par", forWhom: "pour", profit: "bénéfice", auctionsWeek: "Enchères, 48 h",
    runsToday: "Runs du jour", cleared: "Terminés", wipes: "Wipes", bossKills: "Boss tués", running: "En cours",
    noRun: "Aucun groupe en donjon pour l'instant.", dungeon: "Donjon", runs: "Runs", median: "Médiane", best: "Record", started: "commencé",
    bosses: "boss", lastRuns: "Derniers runs", result: { clear: "terminé", wipe: "wipe", aborted: "abandonné", setup_failed: "échec au départ", left: "quitté" }, difficulty: ["", "héroïque", "mythique"], perDungeon: "Par donjon",
    tick: "Tick du monde", tickFoot: (p, m) => (p === null ? "" : "p95 " + p + " ms · ") + (m === null ? "" : "max " + m + " ms"), botsCpu: "Bots par tick", botsCpuFoot: p => "p95 " + p + " ms",
    build: "Coût des snapshots", buildFoot: "sur le thread monde, tous fichiers", strategies: "Coût par stratégie, microsecondes par tick",
    stuckList: "Bots coincés", noStuck: "Aucun bot coincé.", since: "depuis", tickChart: "Tick (ms), 6 h", botsChart: "Bots en ligne, 6 h", curveWait: "La courbe se dessine au fil des relevés : un point toutes les 5 minutes tant que cette page est ouverte.",
    actionsSoon: "Les commandes aux bots (arrêt, reprise, invocation, décoincer) arriveront avec le module, par la console du monde.",
  },
};
const VW = () => VIVANT_WORDS[lang] || VIVANT_WORDS.en;
let VIVANT = null, VIVANT_TAB = "population", vivantTimer = null;
const SOUL_COLORS = { lazy: "var(--text-muted)", quester: "var(--gold)", wanderer: "#7d9cc4", trader: "var(--accent)", pvp: "var(--horde)" };
const ACT_COLORS = { quest: "var(--gold)", grind: "#c96b3a", camp: "#a0522d", city: "var(--accent)", travel: "#7d9cc4", flight: "#9fb8d8",
  wander_random: "#6b8f71", wander_npc: "#8fbf8f", rest: "#8a8070", fish: "#3fa7d6", gather: "#5aa05a", pvp: "var(--horde)", dungeon: "#b36df2", idle: "var(--text-muted)" };
let VIVANT_LOGQ = "";

async function loadVivant() {
  VIVANT = await getJson("/api/vivant").catch(error => ({ error: String(error) }));
  renderVivant();
}

function vivantFigures(tiles) {
  return '<div class="figures">' + tiles.map(f => '<div class="figure"><div class="label">' + esc(f[0]) + '</div><div class="value num">' +
    f[1] + '</div><div class="foot">' + esc(f[2] || "") + "</div></div>").join("") + "</div>";
}

const qualityName = (name, quality) => '<span style="color:' + (QUALITY_COLORS[quality] || "#eee") + '">[' + esc(name) + "]</span>";
const duration = s => Math.floor(s / 60) + ":" + String(Math.round(s % 60)).padStart(2, "0");

function renderVivant() {
  const host = document.getElementById("vivantPage");
  if (!host || !VIVANT) return;
  const w = VW();
  if (VIVANT.error && !VIVANT.world) { host.innerHTML = '<div class="banner">' + esc(VIVANT.error) + "</div>"; return; }
  const tabs = Object.keys(w.tabs).map(k => '<button type="button" role="tab" data-vivant="' + k + '" aria-selected="' + (k === VIVANT_TAB) + '">' +
    esc(w.tabs[k]) + "</button>").join("");
  const banners = (VIVANT.demo && VIVANT.demo.length ? '<div class="banner">' + esc(w.demo(VIVANT.demo.join(", "))) + "</div>" : "") +
    (VIVANT.stale && VIVANT.stale.length ? '<div class="banner">' + esc(w.stale(VIVANT.stale.join(", "))) + "</div>" : "");
  const typing = document.activeElement && document.activeElement.id === "vvLogQ";
  host.innerHTML = banners + '<div class="tabs" role="tablist">' + tabs + '</div><div id="vivantBody"></div>';
  const vbody = document.getElementById("vivantBody");
  // A file the realm does not write: say which option makes it, never made-up or zero figures (the Pilot, 09/11).
  const topic = { population: "world", monde: "monde", economy: "economy", groups: "groups", health: "world", events: "events" }[VIVANT_TAB];
  if ((VIVANT.missing || []).includes(topic)) {
    const say = topic === "groups" ? w.noDataYet : w.missing(w.files[topic], OPTION_KEYS[topic]);
    vbody.innerHTML = '<section class="card"><p class="empty">' + esc(say) + "</p></section>" + (VIVANT_TAB === "health" ? liveLogCard(w) : "");
    if (VIVANT_TAB === "health") showLiveLog(w);
  } else ({ population: vivantPopulation, monde: vivantMonde, economy: vivantEconomy, groups: vivantGroups, health: vivantHealth, events: vivantEvents })[VIVANT_TAB](vbody, w);
  const q = document.getElementById("vvLogQ");
  if (q && typing) { q.focus(); q.setSelectionRange(q.value.length, q.value.length); }
}

function topicError(data) { return data && data.error ? '<div class="banner">' + esc(data.error) + "</div>" : ""; }

function vivantPopulation(body, w) {
  const d = VIVANT.world || {};
  const zones = d.zones || [], acts = d.activities || {}, h = d.health || {};
  const capitals = zones.filter(z => z.capital).reduce((s, z) => s + z.bots, 0);
  // world.json "everyone" (SquidBot d2ce3948): players, alts and random bots together; the other fields count random bots only.
  const ev = d.everyone && d.everyone.total ? d.everyone : null;
  const all = m => (m ? (m.players || 0) + (m.alts || 0) + (m.bots || 0) : 0);
  const at = k => all(ev && ev.places && ev.places[k]);
  const total = ev ? all(ev.total) : 0;
  const head = ev ? [[w.allChars, num(total), w.split(num(ev.total.players || 0), num(ev.total.alts || 0), num(ev.total.bots || 0))],
      [w.players, num(ev.total.players || 0), num(ev.total.alts || 0) + " alts"],
      [w.inCapitals, num(at("capital")), Math.round(at("capital") / Math.max(1, total) * 100) + " %"],
      [w.busy, num(at("dungeon") + at("raid")), at("raid") ? w.raidPart(num(at("raid"))) : ""]]
    : [[w.online, num(d.online), ""], [w.players, num(d.players), ""],
      [w.inCapitals, num(capitals), Math.round(capitals / Math.max(1, d.online) * 100) + " %"], [w.busy, num(acts.dungeon), ""]];
  const bgCount = ev ? at("battleground") + at("arena") : zones.filter(z => BG_MAPS.has(z.map)).reduce((s, z) => s + z.bots, 0);
  const whoRow = (label, m) => "<tr><td>" + esc(label) + '</td><td class="r">' + num((m || {}).players || 0) + '</td><td class="r">' + num((m || {}).alts || 0) +
    '</td><td class="r">' + num((m || {}).bots || 0) + '</td><td class="r"><strong>' + num(all(m)) + "</strong></td></tr>";
  const everyoneCard = !ev ? "" : '<section class="card"><h2>' + esc(w.everyone) + '</h2><p class="meta">' + esc(w.everyoneHelp) +
    '</p><div class="scroll"><table><thead><tr><th></th>' + w.whoCols.map(c => '<th class="r">' + esc(c) + "</th>").join("") + "</tr></thead><tbody>" +
    ["arena", "battleground", "raid", "dungeon", "capital", "world"].filter(k => at(k)).map(k => whoRow(w.place[k], ev.places[k])).join("") +
    (ev.factions ? whoRow(w.alliance, ev.factions.alliance) + whoRow(w.horde, ev.factions.horde) : "") + whoRow(w.whoCols[3], ev.total) + "</tbody></table></div></section>";
  body.innerHTML = topicError(d) + vivantFigures(head.concat([
    h.stuck ? [w.stuck, num(h.stuck.length), ""] : [stuckLabel(w, (stuckDay() || {}).since), (stuckDay() || {}).count || "–", stuckDay() ? (stuckDay().journal ? w.fromEvents : "") : w.soon],
    [w.inBg, num(bgCount), acts.pvp == null || ev ? "" : w.pvpAll(num(acts.pvp))]])) + everyoneCard + levelingCard(w, d.leveling) +
    '<div class="grid two"><section class="card"><h2>' + esc(w.zones) + '</h2><div id="vvZones"></div></section>' +
    '<section class="card"><h2>' + esc(w.activities) + '</h2><div class="splits" id="vvActs"></div>' +
    '<h2 class="later">' + esc(w.capitals) + '</h2><div class="splits" id="vvCaps"></div>' +
    '<h2 class="later">' + esc(w.souls) + '</h2><div class="splits" id="vvSouls"></div>' +
    '<h2 class="later">' + esc(w.surnames) + '</h2><div id="vvSurname"></div></section></div>';
  const sides = z => { const f = z.faction || {}; return f.alliance == null && f.horde == null ? "" : w.alliance + " " + num(f.alliance || 0) + " · " + w.horde + " " + num(f.horde || 0); };
  if (d.leveling && document.getElementById("vvHourly")) levelCharts(w, d.leveling);
  if (ev && ev.zones && ev.zones.length)
    rankedList(document.getElementById("vvZones"), ev.zones.map(z => ({ name: z.name || "#" + z.zone, n: all(z), capital: z.capital,
      who: w.split(num(z.players || 0), num(z.alts || 0), num(z.bots || 0)) })).sort((a, b) => b.n - a.n),
      { value: r => r.n, unit: "", line2: r => [r.capital ? w.capital : "", r.who].filter(Boolean).join(" · ") });
  else rankedList(document.getElementById("vvZones"), zones.map(z => ({ name: z.name || "#" + z.zone, bots: z.bots, capital: z.capital, sides: sides(z) })),
    { value: r => r.bots, unit: "bots", line2: r => [r.capital ? w.capital : "", r.sides].filter(Boolean).join(" · ") });
  const caps = zones.filter(z => z.capital), capHost = document.getElementById("vvCaps");
  if (!caps.length) capHost.innerHTML = '<p class="empty">' + esc(w.noCapital) + "</p>";
  else splitBar(capHost, caps.map((z, i) => ({ label: z.name || "#" + z.zone, count: z.bots,
    color: ["var(--gold)", "var(--horde)", "#7d9cc4", "#c96b3a", "var(--accent)", "#b36df2"][i % 6] })));
  splitBar(document.getElementById("vvActs"), Object.keys(acts).filter(k => acts[k]).sort((a, b) => acts[b] - acts[a]).map(k => ({ label: w.act[k] || k, count: acts[k], color: ACT_COLORS[k] || "var(--gold)" })));
  const souls = d.souls, soulHost = document.getElementById("vvSouls");
  if (!souls) soulHost.innerHTML = '<p class="empty">' + esc((VIVANT.demo || []).includes("world") ? w.soonL1 : w.soulsOff) + "</p>";
  else splitBar(soulHost, Object.keys(SOUL_COLORS).map(k => ({ label: w.soul[k], count: souls[k] || 0, color: SOUL_COLORS[k] })));
  const sn = d.surname, snHost = document.getElementById("vvSurname");
  if (!sn) { snHost.innerHTML = '<p class="empty">' + esc(w.soonL1) + "</p>"; return; }
  const help = w.surnameHelp[sn.mode];
  snHost.innerHTML = '<div class="tabs" aria-label="' + esc(w.surnames) + '">' + w.surnameMode.map((label, mode) =>
    '<button type="button" disabled aria-selected="' + (mode === sn.mode) + '">' + esc(label) + "</button>").join("") + "</div>" +
    '<p class="meta">' + esc(typeof help === "function" ? help(sn.list_size || 0) : help) + "</p>" +
    (sn.mode === 2 && sn.top && sn.top.length ? '<p class="meta"><strong>' + esc(w.mostWorn) + '</strong></p><div id="vvSurnameTop"></div>' : "");
  if (sn.mode === 2 && sn.top && sn.top.length) rankedList(document.getElementById("vvSurnameTop"), sn.top.slice().sort((a, b) => b.bots - a.bots),
    { value: r => r.bots, unit: "bots", line2: () => "" });
}

const DAY = 86400;
const OPTION_KEYS = { world: "AiPlayerbot.CoaLive.DataFile.Enable", economy: "AiPlayerbot.CoaEconomy.DataFile.Enable",
  monde: "AiPlayerbot.CoaWorld.StateFile.Enable", events: "AiPlayerbot.CoaWorld.Events.Enable" };
// Battlegrounds and arenas (map ids): world.json counts their bots under "pvp", never under "dungeon".
const BG_MAPS = new Set([30, 489, 529, 566, 607, 628, 559, 562, 572, 617, 618]);
const recentEvents = (kinds, span) => (VIVANT.events || []).filter(e => kinds.includes(e.kind) && (!span || Date.now() / 1000 - e.at < span));
// Stuck bots over 24 h: CoA World's own count (monde.json) when it writes one; the 200 journal lines cover only minutes on a big realm.
function stuckDay() {
  const rec = !(VIVANT.demo || []).includes("monde") && VIVANT.monde && VIVANT.monde.recovery_24h;
  if (rec) return { count: num(rec.stuck), journal: false, since: rec.since, events: rec.stuck_events };
  return VIVANT.events ? { count: num(recentEvents(["stuck"], DAY).length), journal: true } : null;
}

// "Stuck, 24 h", or "since 16:32" while the server has run less than a day (monde.json recovery_24h.since).
const stuckLabel = (w, since, other) => since && since > Date.now() / 1000 - DAY + 60 ?
  (other ? w.unstuckSince : w.stuckSince)(new Date(since * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })) : (other ? w.unstuck24 : w.stuck24);

const cityName = key => String(key || "").replace(/(^|[_-])(\w)/g, (m, sep, c) => (sep ? " " : "") + c.toUpperCase());

// XP catch-up (CoA SquidBot, world.json "leveling"): the players' front, the random bots by level, the hourly percentiles.
function levelingCard(w, lv) {
  if (!lv) return "";
  const bots = lv.bots || [];
  const pct = q => { const total = bots.reduce((a, b) => a + b, 0); let run = 0; for (let i = 0; i < bots.length; i++) { run += bots[i]; if (run >= total * q) return i + 1; } return 0; };
  const top = Math.max(1, ...bots);
  const bars = bots.map((n, i) => '<i title="' + esc((lang === "fr" ? "niveau " : "level ") + (i + 1) + " : " + num(n) + " bots") + '" style="height:' +
    (n ? Math.max(4, Math.sqrt(n / top) * 100) : 0) + '%"></i>').join("");
  return '<section class="card"><h2>' + esc(w.leveling) + '</h2><p class="meta"><strong>' + esc(lv.catchUp ? w.catchOn : w.catchOff) + "</strong>" +
    (lv.catchUp ? " · " + esc(lv.front ? w.frontIs(lv.front, num(lv.humans || 0)) : w.noFront(num(lv.humans || 0))) : "") +
    (lv.surveyedAt ? " · " + esc(w.surveyed(ago(lv.surveyedAt))) : "") + "</p>" +
    '<p class="meta">' + esc(w.byLevel) + " · " + esc(w.pcts(pct(.1), pct(.5), pct(.9))) + '</p><div class="lvbars">' + bars + "</div>" +
    '<div class="lvaxis"><span>1</span><span>' + bots.length + "</span></div>" +
    '<h2 class="later">' + esc(w.hourlyTitle) + '</h2><div class="chart" id="vvHourly"></div></section>';
}

function levelCharts(w, lv) {
  const host = document.getElementById("vvHourly"), pts = (lv.hourly || []).slice().sort((a, b) => a.at - b.at);
  if (pts.length < 2) { host.innerHTML = '<p class="empty">' + esc(w.hourlyWait) + "</p>"; return; }
  const W0 = 640, H0 = 180, L = 30, R = 8, T = 8, B = 22;
  const lines = [["p90", "var(--gold-bright)"], ["p50", "var(--gold)"], ["p10", "#c96b3a"], ["front", "var(--accent)"]];
  const vals = pts.flatMap(p => lines.map(l => p[l[0]]).filter(v => v));
  const lo = Math.max(1, Math.min(...vals) - 2), hi = Math.max(...vals) + 1;
  const x = i => L + (W0 - L - R) * i / (pts.length - 1), y = v => T + (H0 - T - B) * (1 - (v - lo) / Math.max(1, hi - lo));
  const path = key => pts.map((p, i) => p[key] ? (i && pts[i - 1][key] ? "L" : "M") + x(i).toFixed(1) + " " + y(p[key]).toFixed(1) : "").join(" ");
  const hh = t => new Date(t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  host.innerHTML = '<svg viewBox="0 0 ' + W0 + " " + H0 + '" role="img" aria-label="' + esc(w.hourlyTitle) + '" style="width:100%;height:auto">' +
    [lo, Math.round((lo + hi) / 2), hi].map(v => '<line x1="' + L + '" x2="' + (W0 - R) + '" y1="' + y(v) + '" y2="' + y(v) + '" stroke="var(--hairline)"/><text x="' + (L - 4) +
      '" y="' + (y(v) + 4) + '" text-anchor="end" font-size="10" fill="var(--text-muted)">' + v + "</text>").join("") +
    lines.map(l => '<path d="' + path(l[0]) + '" fill="none" stroke="' + l[1] + '" stroke-width="2"' + (l[0] === "front" ? ' stroke-dasharray="5 4"' : "") + "/>").join("") +
    '<text x="' + L + '" y="' + (H0 - 6) + '" font-size="10" fill="var(--text-muted)">' + hh(pts[0].at) + '</text><text x="' + (W0 - R) + '" y="' + (H0 - 6) +
    '" text-anchor="end" font-size="10" fill="var(--text-muted)">' + hh(pts[pts.length - 1].at) + "</text></svg>" +
    '<p class="meta">' + lines.map(l => '<span style="color:' + l[1] + '">■</span> ' + esc(l[0] === "front" ? w.front : l[0])).join(" &nbsp; ") + "</p>";
}

function vivantMonde(body, w) {
  const d = VIVANT.monde || {};
  const inv = d.invasions || [], rush = d.rushes || [], guilds = d.guilds || [], gorders = d.guild_orders || (VIVANT.world || {}).guild_orders || [];
  const rec = d.recovery_24h || { stuck: recentEvents(["stuck"], DAY).length, unstuck: recentEvents(["unstuck"], DAY).length, events: true };
  const firsts = d.server_firsts && d.server_firsts.length ? d.server_firsts.map(f => ({ at: f.at, text: f.what + (f.guild ? " <" + f.guild + ">" : ""), bot: f.by }))
    : recentEvents(["server_first"]).map(e => ({ at: e.at, text: e.text, bot: e.bot }));
  const clock = t => new Date(t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const when = x => x.state === "announced" ? w.announced + (x.starts ? " · " + w.starts + " " + clock(x.starts) : "")
    : (x.since ? w.since + " " + ago(x.since) : "") + (x.ends ? " · " + w.ends + " " + clock(x.ends) : "");
  const bits = list => list.filter(Boolean).map(esc).join(" · ");
  const now = inv.map(i => '<div class="zone-row"><div><strong>' + esc(w.kind.invasion) + " · " + esc(i.name || "#" + i.zone) + (i.site ? " (" + esc(i.site) + ")" : "") +
      '</strong><div class="meta">' + bits([i.kind, i.level ? w.level + " " + i.level : "", i.wave ? w.wave + " " + i.wave : "", when(i)]) +
      '</div></div><div class="meta">' + count(i.bots) + " bots</div></div>")
    .concat(rush.map(r => '<div class="zone-row"><div><strong>' + esc(w.kind.rush) + " · " + esc(r.what || "") + " · " + esc(r.area || r.name || "#" + r.zone) +
      '</strong><div class="meta">' + bits([r.area && r.name ? r.name : "", r.level ? w.level + " " + r.level : "", r.nodes != null ? r.nodes + " " + w.nodes : "", when(r)]) +
      '</div></div><div class="meta">' + count(r.bots) + " bots</div></div>")).join("");
  const queue = guilds.some(g => g.orders_open != null);   // CoA World serves an order at once: no queue, orders_open null
  const guildRows = guilds.slice().sort((a, b) => (b.online || 0) - (a.online || 0)).map(g => "<tr><td>&lt;" + esc(g.name) + '&gt;</td><td class="r">' + count(g.members) +
    '</td><td class="r">' + count(g.bots) + '</td><td class="r">' + count(g.online) + '</td><td class="r">' + money(g.bank_gold) +
    (queue ? '</td><td class="r">' + count(g.orders_open) : "") + "</td></tr>").join("");
  const orderRows = gorders.slice().sort((a, b) => b.at - a.at).map(o => "<tr><td>" + qualityName(o.name || "#" + o.item, o.quality) + " × " + count(o.count) +
    '<div class="meta">&lt;' + esc(o.guild) + "&gt;" + (o.by ? " · " + esc(w.servedBy) + " " + esc(o.by) : "") + "</div></td><td>" + esc(w.guildOrderState[o.state] || o.state) +
    '</td><td class="r meta">' + esc(ago(o.at)) + "</td></tr>").join("");
  const line = e => '<tr><td class="meta">' + esc(ago(e.at)) + "</td><td>" + (e.bot ? "<strong>" + esc(e.bot) + "</strong> " : "") + esc(e.text) + "</td></tr>";
  const raid = d.capital_raid && d.capital_raid.running;
  const raidRow = !raid ? "" : '<div class="zone-row"><div><strong>' + esc(w.raid) + " · " + esc(cityName(raid.city)) + " · " +
    esc(raid.attackers === "horde" ? w.horde : w.alliance) + '</strong><div class="meta">' +
    bits([w.raidPhase[raid.phase] || raid.phase, raid.steps ? w.stepOf(raid.step, raid.steps) : "", w.raidLine(num(raid.bots || 0), num(raid.defenders || 0)),
      raid.phase === "assault" && raid.kingHealthPct != null ? w.king(raid.kingHealthPct) : "",
      raid.phase === "gathering" && raid.assaultAt ? w.assaultAt + " " + clock(raid.assaultAt) : "", raid.endsAt ? w.ends + " " + clock(raid.endsAt) : ""]) +
    "</div></div></div>";
  const lastFew = recentEvents(["invasion", "rush", "guild", "server_first"]).slice(0, 15).map(e => '<tr><td class="meta">' + esc(ago(e.at)) +
    '</td><td><span style="color:' + (KIND_COLORS[e.kind] || "var(--text-muted)") + '">' + esc(w.kind[e.kind] || e.kind) + "</span></td><td>" +
    (e.bot ? "<strong>" + esc(e.bot) + "</strong> " : "") + esc(e.text) + "</td></tr>").join("");
  const table = (head, rows, why) => rows ? '<div class="scroll"><table>' + (head ? "<thead><tr>" + head + "</tr></thead>" : "") + "<tbody>" + rows + "</tbody></table></div>"
    : '<p class="empty">' + esc(why) + "</p>";
  body.innerHTML = topicError(d) + vivantFigures([[w.invasionsNow, num(inv.length), raid ? w.raid + " · " + (w.raidPhase[raid.phase] || raid.phase) : ""], [w.rushesNow, num(rush.length), ""], [w.guilds, num(guilds.length), ""],
    [w.guildOrders, num(gorders.length), w.sinceStart],
    [stuckLabel(w, rec.since), count(rec.stuck), rec.events ? w.fromEvents : rec.stuck_events != null ? w.detections(num(rec.stuck_events)) : ""],
    [stuckLabel(w, rec.since, true), count(rec.unstuck), rec.events ? w.fromEvents : rec.unstuck_events != null ? w.detections(num(rec.unstuck_events)) : ""]]) +
    '<div class="grid two"><section class="card"><h2>' + esc(w.happening) + "</h2>" + (raidRow + now || '<p class="empty">' + esc(w.nothingNow) + "</p>") + "</section>" +
    '<section class="card"><h2>' + esc(w.firsts) + "</h2>" + table("", firsts.slice(0, 12).map(line).join(""), w.noFirst) + "</section></div>" +
    '<div class="grid two"><section class="card"><h2>' + esc(w.guilds) + "</h2>" + table("<th></th><th class=\"r\">" + esc(w.members) + '</th><th class="r">' + esc(w.botsOnline) + '</th><th class="r">' +
      esc(w.onlineCol) + '</th><th class="r">' + esc(w.bank) + "</th>" + (queue ? '<th class="r">' + esc(w.openOrders) + "</th>" : ""), guildRows, w.noGuild) + "</section>" +
    '<section class="card"><h2>' + esc(w.guildOrders) + "</h2>" + table("", orderRows, w.noGuildOrder) + "</section></div>" +
    '<section class="card"><h2>' + esc(w.highlights) + "</h2>" + table("", lastFew, w.noHighlight) + "</section>";
}

const PROFESSIONS = { 164: "Blacksmithing", 165: "Leatherworking", 171: "Alchemy", 182: "Herbalism", 185: "Cooking", 186: "Mining",
  197: "Tailoring", 202: "Engineering", 333: "Enchanting", 356: "Fishing", 393: "Skinning", 755: "Jewelcrafting", 773: "Inscription", 129: "First Aid" };
const money = v => (v === null || v === undefined ? "–" : coins(v));
const count = v => (v === null || v === undefined ? "–" : num(v));

function vivantEconomy(body, w) {
  // Nulls are real: gold before the first query, prices without buyouts, bands without Market.Enable.
  const d = VIVANT.economy || {};
  const cats = d.categories || [], orders = d.orders || [], crafts = d.crafts_24h || [], sales = d.top_sales_24h || [];
  const known = cats.filter(c => c.volume_24h !== null && c.volume_24h !== undefined);
  const sold = known.length ? known.reduce((s, c) => s + c.volume_24h, 0) : null, crafted = crafts.reduce((s, c) => s + (c.count || 0), 0);
  const className = c => c.name || (SW().mkClass[c.class] || "#" + c.class);
  const band = c => (c.low === null && c.usual === null && c.high === null) || c.low === undefined ? "–" : money(c.low) + " · " + money(c.usual) + " · " + money(c.high);
  const catRows = cats.map(c => "<tr><td>" + esc(className(c)) + '</td><td class="r">' + count(c.auctions) + '</td><td class="r">' + money(c.avg) +
    '</td><td class="r meta">' + band(c) + '</td><td class="r">' + count(c.volume_24h) + "</td></tr>").join("");
  const salesRows = sales.map(s => "<tr><td>" + qualityName(s.name || "#" + s.item, s.quality) + '</td><td class="r">' + num(s.count) +
    '</td><td class="r">' + money(s.gold) + "</td></tr>").join("");
  const craftRows = crafts.map(c => "<tr><td>" + qualityName(c.name || "#" + c.item, c.quality) + '<div class="meta">' + esc(PROFESSIONS[c.skill] || c.skill) +
    '</div></td><td class="r">' + num(c.count) + '</td><td class="r">' + money(c.profit) + "</td></tr>").join("");
  const orderRows = orders.map(o => "<tr><td>" + qualityName(o.name || "#" + o.item, o.quality) + '<div class="meta">' + esc(w.by) + " " + esc(o.bot) + " · " +
    esc(w.forWhom) + " " + esc(o.buyer) + '</div></td><td class="r">' + (o.state === "refused" && !o.price ? "–" : money(o.price)) + '</td><td class="order-' + esc(o.state) + '">' + esc(w.orderState[o.state] || o.state) +
    '</td><td class="r meta">' + esc(ago(o.at)) + "</td></tr>").join("");
  const refused = orders.filter(o => o.state === "refused").length;
  const smeltRows = (d.smelt_24h || []).map(r => "<tr><td>" + qualityName(r.name || "#" + r.item, r.quality) + '</td><td class="r">' + count(r.count) + "</td></tr>").join("");
  const deRow = (r, from) => "<tr><td>" + qualityName(r.name || "#" + r.item, r.quality) + (r.from ? '<div class="meta">' + esc(from(num(r.from))) + "</div>" : "") +
    '</td><td class="r">' + count(r.count) + "</td></tr>";
  const deRows = (d.disenchant_24h || []).map(r => deRow(r, w.fromItems)).concat((d.prospect_24h || []).map(r => deRow(r, w.fromOre))).join("");
  const pairs = rows => '<div class="scroll"><table><tbody>' + rows.map(p => "<tr><td>" + esc(p[0]) + '</td><td class="r">' + p[1] + "</td></tr>").join("") + "</tbody></table></div>";
  const c = d.clock, a = d.ahbot_24h;
  const clockHtml = !c ? '<p class="empty">' + esc(w.soon) + "</p>" : '<p class="meta">' + esc(c.enabled ? w.clockOn : w.clockOff) + "</p>" +
    pairs([[w.offlineAdded, c.offline_added_s == null ? "–" : duration(c.offline_added_s / 60) + " h"], [w.resumed, count(c.resumed)], [w.soldClock, count(c.sold_24h)],
      [w.expired, count(c.expired_24h)], [w.relisted, count(c.relisted_24h)]]);
  const ahHtml = !a ? '<p class="empty">' + esc(w.soon) + "</p>" :
    pairs([[w.listed, count(a.listed)], [w.bought, count(a.bought)], [w.goldIn, money(a.gold_in)], [w.goldOut, money(a.gold_out)]]);
  const table = (head, rows, why) => rows ? '<div class="scroll"><table><thead><tr>' + head + "</tr></thead><tbody>" + rows + "</tbody></table></div>"
    : '<p class="empty">' + esc(why) + "</p>";
  // CoA Economy 3.0.1 says which features are on ("features"): "needs …" only for one that is off; a 3.0 file keeps the old text.
  const f = d.features, why = (key, option) => f && typeof f[key] === "boolean" && f[key] ? w.nothing24 : w.needs(option);
  const share = d.gold_bots !== null && d.gold_bots !== undefined && d.gold_circulating ? Math.round(d.gold_bots / d.gold_circulating * 100) + " %" : "";
  body.innerHTML = topicError(d) + vivantFigures([[w.auctions, count(d.auctions), ""],
    [w.goldAll, money(d.gold_circulating), d.gold_circulating === null ? w.goldWait : ""], [w.goldBots, money(d.gold_bots), share],
    [w.sold24, count(sold), sold === null ? why("market", "Market.Enable") : ""], [w.crafted24, num(crafted), ""],
    [w.ordersTile, num(orders.length), refused ? w.refusedN(refused) : ""]]) +
    '<section class="card"><h2>' + esc(w.categories) + "</h2>" + table("<th>" + esc(w.cat) + '</th><th class="r">' + esc(w.auctions) + '</th><th class="r">' +
      esc(w.avg) + '</th><th class="r">' + esc(w.band) + '</th><th class="r">' + esc(w.volume) + "</th>", catRows, w.noAuction) + "</section>" +
    '<div class="grid two"><section class="card"><h2>' + esc(w.topSales) + "</h2>" + table("<th>" + esc(w.item) + '</th><th class="r">' + esc(w.qty) +
      '</th><th class="r">' + esc(w.gold) + "</th>", salesRows, why("market", "Market.Enable")) + "</section>" +
    '<section class="card"><h2>' + esc(w.crafts) + "</h2>" + table("<th>" + esc(w.item) + '</th><th class="r">' + esc(w.qty) + '</th><th class="r">' +
      esc(w.profit) + "</th>", craftRows, why("artisans", "Artisans")) + "</section></div>" +
    '<div class="grid two"><section class="card"><h2>' + esc(w.orders) + "</h2>" + table("<th>" + esc(w.item) + '</th><th class="r">' + esc(w.gold) +
      "</th><th></th><th></th>", orderRows, why("craft_orders", "CraftOrders")) + "</section>" +
    '<section class="card"><h2>' + esc(w.auctionsWeek) + '</h2><div class="chart" id="vvAh"></div></section></div>' +
    '<div class="grid two"><section class="card"><h2>' + esc(w.smelt) + "</h2>" + (d.smelt_24h == null ? '<p class="empty">' + esc(w.soon) + "</p>" :
      table("<th>" + esc(w.item) + '</th><th class="r">' + esc(w.qty) + "</th>", smeltRows, w.needs("Materials"))) + "</section>" +
    '<section class="card"><h2>' + esc(w.disenchant) + "</h2>" + (d.disenchant_24h == null ? '<p class="empty">' + esc(w.soon) + "</p>" :
      table("<th>" + esc(w.item) + '</th><th class="r">' + esc(w.qty) + "</th>", deRows, w.needs("Materials"))) + "</section></div>" +
    '<div class="grid two"><section class="card"><h2>' + esc(w.clock) + "</h2>" + clockHtml + "</section>" +
    '<section class="card"><h2>' + esc(w.ahbot) + "</h2>" + ahHtml + "</section></div>";
  lineChart(document.getElementById("vvAh"), d.history || [], { value: p => p.auctions, label: w.auctionsWeek, unit: "" });
}

// Dungeon Clear's finished runs (runs.jsonl lines: camelCase, times in ms), newest first.
function lastRunsCard(w, runs) {
  const label = r => esc(r.dungeonName || r.dungeon) + (r.difficulty ? ' <span class="meta">' + esc(w.difficulty[r.difficulty] || "") + "</span>" : "");
  const rows = runs.map(r => "<tr><td>" + label(r) + '<div class="meta">' + esc((r.comp || []).map(c => c.name).concat(r.players || []).join(", ")) +
    (r.parts > 1 ? " · " + esc(w.parts(r.parts)) : "") + "</div></td><td>" + esc(w.result[r.result] || r.result) + ' <span class="meta">' + r.bossesKilled + "/" + r.bossesTotal +
    '</span></td><td class="r">' + duration(r.durationS) + '</td><td class="r">' + (r.wipes || 0) + '</td><td class="r meta">' + esc(ago(r.endedAtMs / 1000)) + "</td></tr>").join("");
  return '<section class="card"><h2>' + esc(w.lastRuns) + '</h2><div class="scroll"><table><tbody>' + rows + "</tbody></table></div></section>";
}

function vivantGroups(body, w) {
  // Three writers: CoA SquidBot's real instance runs (world.json "groups", null before the first run),
  // CoA World's simulated dungeons and battlegrounds (monde.json, null when off), Dungeon Clear's finished runs (runs.jsonl).
  const d = VIVANT.groups || {};
  const real = d.real, sim = d.sim, bg = d.bg, dc = d.dc || [];
  const rt = (real && real.today) || {}, st = (sim && sim.today) || {}, bt = (bg && bg.today) || {};
  const fake = (VIVANT.demo || []).includes("groups") ? '<div class="banner">' + esc(w.demoTab) + "</div>" : "";
  const hhmm = t => new Date(t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const note = text => '<p class="empty">' + esc(text) + "</p>";
  const table = (head, rows) => '<div class="scroll"><table>' + (head ? "<thead><tr>" + head + "</tr></thead>" : "") + "<tbody>" + rows + "</tbody></table></div>";
  const name = r => esc(r.dungeonName || r.bgName || "#" + (r.map || r.dungeon || r.bg)) +
    (r.difficulty ? ' <span class="meta">' + esc(w.difficulty[r.difficulty] || "") + "</span>" : "") + (r.kind === "raid" ? ' <span class="meta">raid</span>' : "");
  const who = r => w.split(num(r.players || 0), num(r.alts || 0), num(r.bots || 0));
  const progress = (k, t) => t ? '<div class="bar" title="' + k + "/" + t + '"><i style="width:' + (k / Math.max(1, t) * 100) + '%"></i></div><div class="meta">' +
    k + "/" + t + " " + esc(w.bosses) + "</div>" : '<div class="meta">' + num(k) + " " + esc(w.bosses) + "</div>";
  const realRunning = real ? (real.running || []).map(r => '<div class="zone-row"><div><strong>' + name(r) + '</strong><div class="meta">' + esc(who(r)) +
    (r.leader ? " · " + esc(w.leader) + " " + esc(r.leader) : "") + " · " + esc(w.started) + " " + esc(ago(r.startedAt)) +
    (r.wipes ? " · " + r.wipes + " " + esc(w.wipes.toLowerCase()) : "") + "</div></div>" + progress(r.bossesKilled || 0, r.bossesTotal) + "</div>").join("") : "";
  const simRunning = sim ? (sim.running || []).map(r => '<div class="zone-row"><div><strong>' + name(r) + '</strong><div class="meta">' +
    esc([w.faction[r.faction] || r.faction, r.level ? w.level + " " + r.level : "", r.bots + " bots", w.phase[r.phase] || r.phase,
      r.endsAt ? w.ends + " " + hhmm(r.endsAt) : ""].filter(Boolean).join(" · ")) + '</div></div><div class="meta">' + (r.bosses ? num(r.bosses) + " " + esc(w.bosses) : "") +
    "</div></div>").join("") : "";
  const bgRunning = bg ? (bg.running || []).map(r => '<div class="zone-row"><div><strong>' + name(r) + '</strong><div class="meta">' +
    esc([r.levelMin ? w.level + " " + r.levelMin + "-" + r.levelMax : "", w.alliance + " " + num(r.alliance || 0) + " · " + w.horde + " " + num(r.horde || 0),
      w.phase[r.phase] || r.phase, r.endsAt ? w.ends + " " + hhmm(r.endsAt) : ""].filter(Boolean).join(" · ")) + "</div></div></div>").join("") : "";
  const byRows = real ? (real.byDungeon || []).map(b => "<tr><td>" + name(b) + '</td><td class="r">' + num(b.runs) + '</td><td class="r">' + num(b.cleared) +
    '</td><td class="r">' + num(b.wipes) + '</td><td class="r">' + (b.medianS ? duration(b.medianS) : "–") + '</td><td class="r">' + (b.bestS ? duration(b.bestS) : "–") + "</td></tr>").join("") : "";
  const realLast = real ? (real.last || []).map(r => "<tr><td>" + name(r) + '<div class="meta">' + esc(who(r)) + "</div></td><td>" + esc(w.result[r.result] || r.result) +
    ' <span class="meta">' + num(r.bossesKilled || 0) + (r.bossesTotal ? "/" + r.bossesTotal : "") + '</span></td><td class="r">' +
    (r.endedAt && r.startedAt ? duration(r.endedAt - r.startedAt) : "–") + '</td><td class="r">' + num(r.wipes || 0) + '</td><td class="r meta">' + esc(ago(r.endedAt)) + "</td></tr>").join("") : "";
  const simLast = sim ? (sim.last || []).map(r => "<tr><td>" + name(r) + '<div class="meta">' + num(r.bots) + ' bots</div></td><td class="r">' + num(r.bossesKilled || 0) + " " +
    esc(w.bosses) + '</td><td class="r">' + duration(r.durationS || 0) + '</td><td class="r meta">' + esc(ago(r.at)) + "</td></tr>").join("") : "";
  const bgLast = bg ? (bg.last || []).map(r => "<tr><td>" + name(r) + '<div class="meta">' + num(r.bots) + " bots" + (r.levelMin ? " · " + w.level + " " + r.levelMin + "-" + r.levelMax : "") +
    "</div></td><td>" + esc(r.winner ? w.won(r.winner === "alliance" ? w.alliance : w.horde) : "–") + '</td><td class="r">' + duration(r.durationS || 0) + '</td><td class="r">' +
    num(r.honor || 0) + " " + esc(w.honor) + '</td><td class="r meta">' + esc(ago(r.at)) + "</td></tr>").join("") : "";
  const ev = VIVANT.world && VIVANT.world.everyone && VIVANT.world.everyone.places;
  const all = m => (m ? (m.players || 0) + (m.alts || 0) + (m.bots || 0) : 0);
  const inReal = ev ? all(ev.dungeon) + all(ev.raid) : real ? (real.running || []).reduce((n, r) => n + (r.players || 0) + (r.alts || 0) + (r.bots || 0), 0) : null;
  const inSim = sim ? (sim.running || []).reduce((n, r) => n + (r.bots || 0), 0) : 0;
  const realOff = !d.worldOn ? w.missing(w.files.world, OPTION_KEYS.world) : !real ? w.noRealRun : "";
  const simOff = !d.mondeOn ? w.missing(w.files.monde, OPTION_KEYS.monde) : !sim ? w.simOff : "";
  // Real battlegrounds (BgSim stays off in the pack, the user 09/11): everyone's zones, else the random bots' zones.
  const evZones = VIVANT.world && VIVANT.world.everyone && VIVANT.world.everyone.zones;
  const bgZones = (evZones || (VIVANT.world || {}).zones || []).filter(z => BG_MAPS.has(z.map));
  const realBg = bgZones.map(z => '<div class="zone-row"><div><strong>' + esc(z.name || "#" + z.zone) + '</strong><div class="meta">' +
    esc(evZones ? who(z) : num(z.bots) + " bots") + '</div></div><div class="meta">' + num(evZones ? all(z) : z.bots) + "</div></div>").join("");
  const sinceFoot = t => t ? w.sinceAt(hhmm(t)) : "";
  body.innerHTML = fake + vivantFigures([
    [w.runsToday, real || sim ? num((rt.runs || 0) + (st.runs || 0)) : "–", sim ? w.realSim(num(rt.runs || 0), num(st.runs || 0)) : sinceFoot(rt.since)],
    [w.cleared, real ? num(rt.cleared || 0) : "–", real && rt.runs ? Math.round((rt.cleared || 0) / rt.runs * 100) + " %" : ""],
    [w.wipes, real ? num(rt.wipes || 0) : "–", w.realOnly],
    [w.bossKills, real || sim ? num((rt.bossKills || 0) + (st.bossKills || 0)) : "–", sim ? w.realSim(num(rt.bossKills || 0), num(st.bossKills || 0)) : ""],
    [w.running, num((real ? (real.running || []).length : 0) + (sim ? (sim.running || []).length : 0)), ""],
    [w.busy, inReal === null && !sim ? "–" : num((inReal || 0) + inSim), sim ? w.realSim(num(inReal || 0), num(inSim)) : ""]]) +
    '<div class="grid two"><section class="card"><h2>' + esc(w.realNow) + "</h2>" + (realOff ? note(realOff) : realRunning || note(w.noRun)) + "</section>" +
    '<section class="card"><h2>' + esc(w.simNow) + "</h2>" + (simOff ? note(simOff) : simRunning || note(w.noSim)) +
      (sim && st.items ? '<p class="meta">' + esc(w.simItems(num(st.items))) + "</p>" : "") + "</section></div>" +
    (byRows ? '<section class="card"><h2>' + esc(w.perDungeon) + "</h2>" + table("<th>" + esc(w.dungeon) + '</th><th class="r">' + esc(w.runs) + '</th><th class="r">' +
      esc(w.cleared) + '</th><th class="r">' + esc(w.wipes) + '</th><th class="r">' + esc(w.median) + '</th><th class="r">' + esc(w.best) + "</th>", byRows) + "</section>" : "") +
    '<div class="grid two"><section class="card"><h2>' + esc(w.lastReal) + "</h2>" + (realLast ? table("", realLast) : note(realOff || w.noRealRun)) + "</section>" +
    '<section class="card"><h2>' + esc(w.lastSim) + "</h2>" + (simLast ? table("", simLast) : note(simOff || w.noSim)) + "</section></div>" +
    '<section class="card"><h2>' + esc(w.bgNow) + "</h2>" + (realBg || note(w.noRealBg)) +
      (!bg ? '<p class="meta">' + esc(w.bgSimOff) + "</p>" : '<h2 class="later">' + esc(w.bgSimTitle) + "</h2>" + (bgRunning || note(w.noBg)) +
        '<p class="meta">' + esc(w.bgToday(num(bt.matches || 0), num(bt.allianceWins || 0), num(bt.hordeWins || 0), num(bt.honor || 0))) + "</p>" +
        (bgLast ? table("", bgLast) : "")) + "</section>" +
    (dc.length ? lastRunsCard(w, dc).replace(esc(w.lastRuns), esc(w.dcRuns)) : "");
}

const KIND_COLORS = { invasion: "var(--horde)", rush: "#c96b3a", server_first: "var(--gold-bright)", guild: "var(--accent)", stuck: "#d6a03f",
  unstuck: "#7d9cc4", boss: "#b36df2", wipe: "var(--horde)", order: "var(--gold)", error: "#ff5a5a" };
let VIVANT_KIND = "";

function vivantEvents(body, w) {
  const rows = VIVANT.events || [];
  const kinds = Array.from(new Set(rows.map(e => e.kind))).sort();
  const shown = VIVANT_KIND ? rows.filter(e => e.kind === VIVANT_KIND) : rows;
  const pills = '<div class="tabs" role="tablist">' + ["", ...kinds].map(k => '<button type="button" data-vkind="' + esc(k) + '" aria-selected="' +
    (k === VIVANT_KIND) + '">' + esc(k ? (w.kind[k] || k) : w.allKinds) + (k ? " · " + rows.filter(e => e.kind === k).length : "") + "</button>").join("") + "</div>";
  const lines = shown.map(e => '<tr><td class="meta">' + esc(ago(e.at)) + '</td><td><span style="color:' + (KIND_COLORS[e.kind] || "var(--text-muted)") + '">' +
    esc(w.kind[e.kind] || e.kind) + "</span></td><td>" + (e.bot ? "<strong>" + esc(e.bot) + "</strong> " : "") + esc(e.text) + "</td></tr>").join("");
  body.innerHTML = '<section class="card"><h2>' + esc(w.tabs.events) + '</h2><p class="meta">' + esc(w.eventsHelp) + "</p>" + pills +
    (lines ? '<div class="scroll"><table><tbody>' + lines + "</tbody></table></div>" : '<p class="empty">' + esc(w.noEvent) + "</p>") + "</section>";
}

document.addEventListener("click", event => {
  const pill = event.target.closest("[data-vkind]");
  if (!pill) return;
  VIVANT_KIND = pill.dataset.vkind;
  renderVivant();
});

function vivantHealth(body, w) {
  const d = VIVANT.world || {};
  const h = d.health || {}, tick = h.tick_ms || {}, cpu = h.bots_us_per_tick || {};
  const real = ["world", "economy", "monde"].filter(k => !(VIVANT.demo || []).concat(VIVANT.missing || []).includes(k));
  const builds = real.reduce((s, k) => s + ((VIVANT[k] || {}).buildUs || 0), 0);
  const stuck = (h.stuck || []).map(s => "<tr><td>" + esc(s.name) + '</td><td class="meta">' + esc(s.zone || "") + "</td><td>" + esc(s.why) +
    '</td><td class="r meta">' + esc(w.since) + " " + esc(ago(s.since)) + "</td></tr>").join("");
  const journal = recentEvents(["stuck", "unstuck"], DAY);
  const stuckJournal = journal.length ? '<p class="meta">' + esc(w.stuckEvents) + '</p><div class="scroll"><table><tbody>' + journal.slice(0, 20).map(e =>
    '<tr><td class="meta">' + esc(ago(e.at)) + '</td><td><span style="color:' + KIND_COLORS[e.kind] + '">' + esc(w.kind[e.kind]) + "</span></td><td><strong>" + esc(e.bot) +
    "</strong> " + esc(e.text) + "</td></tr>").join("") + "</tbody></table></div>" : '<p class="empty">' + esc(w.noStuck) + "</p>";
  const day = stuckDay();
  const stuckCount = h.stuck ? num(h.stuck.length) : day ? day.count : "–";
  const ramp = d.ramp || {};
  const left = ramp.until ? Math.max(1, Math.ceil((ramp.until - Date.now() / 1000) / 60)) : null;
  // After the ramp the module's max still holds the start-up's spikes unless it measures from the ramp's end itself.
  const maxText = tick.max == null ? null : ramp.source === "conf" ? null : num(tick.max);
  const tickTile = ramp.ramping ? [w.tick, w.ramping, ramp.doneAt ? w.rampLeft(left) : w.rampFoot(num(ramp.online || 0), num(ramp.target || 0))]
    : [w.tick, tick.avg === null || tick.avg === undefined ? "–" : num(tick.avg) + " ms", maxText !== null || tick.max == null ? w.tickFoot(tick.p95 == null ? null : num(tick.p95), maxText)
      : (tick.p95 == null ? "" : "p95 " + num(tick.p95) + " ms · ") + w.maxSinceStart + " " + num(tick.max) + " ms"];
  body.innerHTML = topicError(d) + vivantFigures([tickTile,
    [w.botsCpu, h.bots_us_per_tick ? (cpu.avg / 1000).toFixed(1) + " ms" : "–", h.bots_us_per_tick ? w.botsCpuFoot((cpu.p95 / 1000).toFixed(1)) : "PerfMon off"], [w.build, num(builds) + " µs", w.buildFoot],
    [h.stuck ? w.stuck : stuckLabel(w, (day || {}).since), stuckCount, h.stuck ? "" : day ? (day.journal ? w.fromEvents : "") : w.soon], [w.players, num(d.players), ""], [w.online, num(d.online), ""]]) +
    '<div class="grid two"><section class="card"><h2>' + esc(w.tickChart) + '</h2><div class="chart" id="vvTick"></div></section>' +
    '<section class="card"><h2>' + esc(w.botsChart) + '</h2><div class="chart" id="vvBots"></div></section></div>' +
    '<div class="grid two"><section class="card"><h2>' + esc(w.strategies) + '</h2><div id="vvStrat"></div></section>' +
    '<section class="card"><h2>' + esc(w.stuckList) + "</h2>" + (!h.stuck ? stuckJournal : stuck ? '<div class="scroll"><table><tbody>' + stuck + "</tbody></table></div>"
      : '<p class="empty">' + esc(w.noStuck) + "</p>") + '<p class="meta">' + esc(w.actionsSoon) + "</p></section></div>" +
    liveLogCard(w);
  showLiveLog(w);
  const points = h.history || [];
  lineChart(document.getElementById("vvTick"), points.filter(p => p.tick != null), { value: p => p.tick, label: w.tickChart, unit: " ms", waiting: w.curveWait });
  lineChart(document.getElementById("vvBots"), points.filter(p => p.online != null), { value: p => p.online, label: w.botsChart, unit: "", color: "var(--accent)", waiting: w.curveWait });
  if (!h.by_strategy_us) { document.getElementById("vvStrat").innerHTML = '<p class="empty">' + esc(w.perfOff) + "</p>"; return; }
  rankedList(document.getElementById("vvStrat"), h.by_strategy_us.map(s => ({ name: s.name, us: s.us })),
    { value: r => r.us, unit: "µs", line2: () => "" });
}

function liveLogCard(w) {
  return '<section class="card"><h2>' + esc(w.liveLog) + '</h2><p class="meta">' + esc(w.logHelp) + '</p><input id="vvLogQ" type="search" placeholder="' + esc(w.logFilter) +
    '" value="' + esc(VIVANT_LOGQ) + '"><pre class="livelog" id="vvLog"></pre></section>';
}

function showLiveLog(w) {
  const pre = document.getElementById("vvLog");
  if (!pre) return;
  const lines = VIVANT.log, q = VIVANT_LOGQ.toLowerCase();
  if (!lines) { pre.textContent = w.noLog; return; }
  const shown = q ? lines.filter(l => l.toLowerCase().includes(q)) : lines;
  pre.innerHTML = shown.length ? shown.map(l => /error|fail|crash|assert/i.test(l) ? '<span class="log-bad">' + esc(l) + "</span>" : esc(l)).join("\n") : esc(w.noMatch);
  pre.scrollTop = pre.scrollHeight;
}

document.addEventListener("input", event => {
  if (event.target.id !== "vvLogQ") return;
  VIVANT_LOGQ = event.target.value;
  showLiveLog(VW());
});

document.addEventListener("click", event => {
  const tab = event.target.closest("[data-vivant]");
  if (!tab) return;
  VIVANT_TAB = tab.dataset.vivant;
  renderVivant();
});

function showVivantPage(page) {
  clearInterval(vivantTimer);
  if (page !== "vivant") return;
  loadVivant();
  vivantTimer = setInterval(() => { if (!document.hidden) loadVivant(); }, 15000);
}

document.getElementById("langButton").addEventListener("click", () => { if (PAGE === "vivant") renderVivant(); });
showVivantPage(PAGE);
