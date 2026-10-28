/* SquidBots armory: find a character, bot or player, and open its sheet.
 *
 * "#armory" is the search, "#armory/Name" a character's sheet. The server side is webapp/armory.py
 * (under /api/armory). Item icons: icons/<name>.png when a game client is on this PC (webapp/icons.py), else
 * wow.zamimg.com (unless "webIcons" is false in dashboard.json), else the quality frame.
 * Without the server's DBC files or a client the sheet still opens: numbers instead of some names,
 * quality-coloured frames instead of icons. Only on the dashboard itself: the public copy leaves it out.
 */

const ARMORY_WORDS = {
  en: {
    fullPage: "Full page",
    hint: "Type the start of a character name (two letters at least).", none: "No character by that name.",
    bot: "bot", hoursPlayed: h => h + " h played", seeOnMap: "See on the map", guildNone: "no guild",
    loading: "Loading…", failed: "The dashboard did not answer.", level: "Level",
    backToSearch: "← Search the armory", copyLink: "Copy link", linkCopied: "Link copied",
    avgItemLevel: "Average item level", empty: "Empty", itemLevel: n => "Item level " + n,
    requires: n => "Requires level " + n, armorValue: n => n + " Armor", damageRange: (a, b) => a + " - " + b + " Damage",
    speed: n => "Speed " + n, dps: n => "(" + n + " damage per second)",
    statsTitle: "Stats", statsSaved: "Saved by the server at the character's last save.",
    statsGear: "Added up from the gear: the server does not save this character's stats (see How it works).",
    professions: "Professions", noProfessions: "No profession yet.",
    achievements: "Achievements", earned: n => n + " earned", points: n => n + " points", noAchievements: "None yet.",
    noNames: "The server's DBC files were not found (dbcDir in dashboard.json): some names show as numbers.",
    noIcons: "No game client found (gameClient in dashboard.json) and web icons are off: items show their quality frame instead of an icon.",
    howTitle: "How it works",
    how: {
      search: "<p>A search on <code>characters.name</code> starting with what you type: letters (one space at most, as in a bot's surname), sent to the "
        + "database as a hex literal, so nothing typed here can change the query. Bots are the characters of the "
        + "<code>RNDBOT…</code> accounts (mod-playerbots); a bot shows its zone, a player does not.</p>",
      sheet: "<p>Gear: <code>character_inventory</code> (bag 0, slots 0-18) → <code>item_instance</code> (enchantments, "
        + "random suffix) → <code>world.item_template</code>. Enchantments and gems are named from "
        + "<code>SpellItemEnchantment.dbc</code>, suffixes from <code>ItemRandomProperties.dbc</code> / "
        + "<code>ItemRandomSuffix.dbc</code>.</p><p>Stats come from <code>character_stats</code>, which the server "
        + "fills only with <code>PlayerSave.Stats.MinLevel</code> above 0 in worldserver.conf; otherwise the sheet "
        + "adds up the gear. Professions: <code>character_skills</code> with <code>SkillLine.dbc</code>. "
        + "Achievements: <code>character_achievement</code> with <code>Achievement.dbc</code> (names and points).</p>"
        + "<p>Icons: <code>item_template.displayid</code> → <code>world.itemdisplayinfo_dbc</code> (CoA's own looks), "
        + "else <code>ItemDisplayInfo.dbc</code> → the icon's name. The picture comes from a game client on this PC "
        + "(extracted once into <code>icons/</code>, never published), else from <code>wow.zamimg.com</code> "
        + "(<code>\"webIcons\": false</code> in dashboard.json turns that off), else the quality frame.</p>",
    },
    slots: ["Head", "Neck", "Shoulder", "Shirt", "Chest", "Waist", "Legs", "Feet", "Wrist", "Hands", "Finger", "Finger",
            "Trinket", "Trinket", "Back", "Main hand", "Off hand", "Ranged", "Tabard"],
  },
  fr: {
    fullPage: "Page complète",
    hint: "Tapez le début d'un nom de personnage (deux lettres au moins).", none: "Aucun personnage de ce nom.",
    bot: "bot", hoursPlayed: h => h + " h jouées", seeOnMap: "Voir sur la carte", guildNone: "sans guilde",
    loading: "Chargement…", failed: "Le dashboard n'a pas répondu.", level: "Niveau",
    backToSearch: "← Chercher dans l'armurerie", copyLink: "Copier le lien", linkCopied: "Lien copié",
    avgItemLevel: "Niveau d'objet moyen", empty: "Vide", itemLevel: n => "Niveau d'objet " + n,
    requires: n => "Niveau " + n + " requis", armorValue: n => "Armure : " + n,
    damageRange: (a, b) => "Dégâts : " + a + " - " + b, speed: n => "Vitesse " + n, dps: n => "(" + n + " dégâts par seconde)",
    statsTitle: "Caractéristiques", statsSaved: "Enregistrées par le serveur à la dernière sauvegarde du personnage.",
    statsGear: "Additionnées depuis l'équipement : le serveur n'enregistre pas les caractéristiques de ce personnage (voir Comment ça marche).",
    professions: "Métiers", noProfessions: "Aucun métier pour l'instant.",
    achievements: "Hauts faits", earned: n => n + " obtenus", points: n => n + " points", noAchievements: "Aucun pour l'instant.",
    noNames: "Les fichiers DBC du serveur sont introuvables (dbcDir dans dashboard.json) : certains noms s'affichent en nombres.",
    noIcons: "Aucun client de jeu trouvé (gameClient dans dashboard.json) et icônes web désactivées : les objets gardent leur cadre de qualité au lieu d'une icône.",
    howTitle: "Comment ça marche",
    how: null,           // the English text: table and file names read the same
    slots: ["Tête", "Cou", "Épaules", "Chemise", "Torse", "Taille", "Jambes", "Pieds", "Poignets", "Mains", "Doigt", "Doigt",
            "Bijou", "Bijou", "Dos", "Main droite", "Main gauche", "À distance", "Tabard"],
  },
};
const AW = () => ARMORY_WORDS[lang] || ARMORY_WORDS.en;
const armoryHow = key => '<details class="how"><summary>' + esc(AW().howTitle) + "</summary>"
  + (AW().how || ARMORY_WORDS.en.how)[key] + "</details>";
const armoryHost = () => document.getElementById("armory");
const armoryName = () => hashParts().slice(1).join("/");
const ZAMIMG = name => "https://wow.zamimg.com/images/wow/icons/large/" + encodeURIComponent(name) + ".jpg";
const noIconSource = icons => !icons || (!icons.local && !icons.web);
const characterLine = c => esc(c.race) + " " + esc(c.class) + (c.spec ? " · " + esc(c.spec) : "");

async function armoryApi(path) {
  try {
    const answer = await fetch("/api/armory" + path, { cache: "no-store" });
    const data = await answer.json();
    if (!answer.ok && !data.error) data.error = AW().failed;
    return data;
  } catch (error) {
    return { error: AW().failed };
  }
}

function sessionGet(key) {
  try { return sessionStorage.getItem(key); } catch (error) { return null; }
}

let armoryTimer = null;
function renderArmory() {
  const name = armoryName();
  document.getElementById("pageTitle").textContent = name || W.pageTitles.armory;
  if (name) { renderCharacter(name); return; }
  const host = armoryHost();
  host.innerHTML = '<section class="card"><h2>' + esc(W.pageTitles.armory) + "</h2>"
    + '<div id="armoryNotes"></div>'
    + '<input id="armorySearch" type="search" autocomplete="off" class="wide-input">'
    + '<div id="armoryResults"><p class="empty"></p></div></section>' + armoryHow("search");
  const input = document.getElementById("armorySearch");
  input.placeholder = AW().hint;
  input.value = sessionGet("squidbots-armory") || "";
  input.addEventListener("input", () => {
    clearTimeout(armoryTimer);
    armoryTimer = setTimeout(searchArmory, 300);
  });
  searchArmory();
  armoryApi("/status").then(status => {
    const notes = document.getElementById("armoryNotes");
    if (!notes) return;
    if (status.error) { notes.innerHTML = '<p class="armory-note bad-text">' + esc(status.error) + "</p>"; return; }
    notes.innerHTML = (status.names ? "" : '<p class="armory-note">' + esc(AW().noNames) + "</p>")
      + (noIconSource(status.icons) ? '<p class="armory-note">' + esc(AW().noIcons) + "</p>" : "");
  });
}

async function searchArmory() {
  const input = document.getElementById("armorySearch");
  if (!input) return;
  const text = input.value.trim();
  try { sessionStorage.setItem("squidbots-armory", text); } catch (error) { /* ignore */ }
  const results = document.getElementById("armoryResults");
  if (text.length < 2) { results.innerHTML = '<p class="empty">' + esc(AW().hint) + "</p>"; return; }
  const data = await armoryApi("?name=" + encodeURIComponent(text));
  if (input.value.trim() !== text) return;              // typed on meanwhile
  if (data.error) { results.innerHTML = '<p class="empty bad-text">' + esc(data.error) + "</p>"; return; }
  if (!data.characters.length) { results.innerHTML = '<p class="empty">' + esc(AW().none) + "</p>"; return; }
  results.innerHTML = '<div class="char-grid">' + data.characters.map(c =>
    '<a class="char-card link" href="#armory/' + encodeURIComponent(c.name) + '"><div class="char-head">'
    + factionDot(c.faction) + "<b>" + esc(c.name) + "</b>"
    + (c.bot ? '<span class="badge">' + esc(AW().bot) + "</span>" : "") + '<span class="bc-lvl">' + c.level + "</span></div>"
    + '<div class="meta">' + characterLine(c) + "</div>"
    + '<div class="meta">' + esc(c.guild || AW().guildNone) + " · " + esc(AW().hoursPlayed(num(c.hours))) + "</div>"
    + (c.bot ? '<div class="meta">' + esc(c.zone || "") + "</div>" : "")
    + "</a>").join("") + "</div>";
}

// The paper doll, in the game's own order: left column, right column, then the weapons.
const DOLL_LEFT = [0, 1, 2, 14, 4, 3, 18, 8];
const DOLL_RIGHT = [9, 5, 6, 7, 10, 11, 12, 13];
const DOLL_BOTTOM = [15, 16, 17];
let SHEET = null;

function sheetDate(ts) {
  if (!ts) return "";
  return new Date(ts * 1000).toLocaleString(lang === "fr" ? "fr-FR" : "en-GB", { dateStyle: "medium", timeStyle: "short" });
}

// `popup`: the sheet goes in the window opened from the Bots page (openArmoryPopup) instead of the Armory page.
async function renderCharacter(name, popup) {
  const host = popup || armoryHost();
  const words = AW();
  if (popup || !SHEET || SHEET.name !== name) host.innerHTML = '<p class="empty">' + esc(words.loading) + "</p>";
  const data = await armoryApi("/character?name=" + encodeURIComponent(name));
  if (popup ? popup.dataset.sheet !== name : PAGE !== "armory" || armoryName() !== name) return;   // gone elsewhere meanwhile
  const back = popup ? "" : '<p class="back-link"><a href="#armory">' + esc(words.backToSearch) + "</a></p>";
  if (data.error) {
    host.innerHTML = back + '<p class="empty bad-text">' + esc(data.error) + "</p>";
    return;
  }
  if (!popup) SHEET = data;
  const bySlot = {};
  for (const piece of data.gear) bySlot[piece.slot] = piece;
  const tile = (slot, side) => {
    const piece = bySlot[slot];
    const label = words.slots[slot];
    if (!piece) {
      return '<div class="gear-slot empty ' + side + '"><span class="gear-icon"></span><span class="gear-text">'
        + '<span class="gear-name">' + esc(label) + '</span><span class="meta">' + esc(words.empty) + "</span></span></div>";
    }
    // The item's own icon: from the game client on this PC, else from the web, else the slot's initials.
    const icons = data.icons || {};
    const source = !piece.icon ? "" : icons.local ? "icons/" + encodeURIComponent(piece.icon) + ".png" : icons.web ? ZAMIMG(piece.icon) : "";
    const face = source ? '<img src="' + esc(source) + '" alt="" data-icon-name="' + esc(piece.icon) + '" data-initials="'
      + esc(label.slice(0, 2)) + '">' : esc(label.slice(0, 2));
    return '<div class="gear-slot ' + side + '" tabindex="0" data-slot="' + slot + '"><span class="gear-icon q' + piece.quality
      + (source ? " has-icon" : "") + '">' + face + '</span><span class="gear-text"><span class="gear-name q' + piece.quality + '">'
      + esc(piece.name) + '</span><span class="meta">' + esc(label) + " · " + piece.itemLevel + "</span></span></div>";
  };
  const stats = data.stats.values.length
    ? '<table class="details">' + data.stats.values.map(v => "<tr><th>" + esc(v.name) + "</th><td>"
      + esc(Number.isInteger(v.value) ? num(v.value) : one(v.value)) + "</td></tr>").join("") + "</table>"
    : '<p class="empty">—</p>';
  const skills = data.skills.length ? data.skills.map(k => '<div class="skill"><div class="skill-head"><b>' + esc(k.name)
    + '</b><span class="meta">' + k.value + " / " + k.max + '</span></div><div class="skill-bar"><i style="width:'
    + Math.round(100 * k.value / Math.max(1, k.max)) + '%"></i></div></div>').join("")
    : '<p class="empty">' + esc(words.noProfessions) + "</p>";
  const earned = data.achievements;
  const achievements = earned.latest.length ? '<ul class="events">' + earned.latest.map(a =>
    '<li><span class="dot live"></span><span><b>' + esc(a.name) + '</b><br><span class="meta">' + esc(sheetDate(a.at))
    + "</span></span></li>").join("") + "</ul>" : '<p class="empty">' + esc(words.noAchievements) + "</p>";
  const notes = (data.names ? "" : '<p class="armory-note">' + esc(words.noNames) + "</p>")
    + (noIconSource(data.icons) ? '<p class="armory-note">' + esc(words.noIcons) + "</p>" : "");

  host.innerHTML = back + notes
    + '<div class="sheet-head"><span class="sheet-crest">' + esc(data.name.slice(0, 1)) + '</span><div class="sheet-who">'
      + '<h2 class="sheet-name">' + esc(data.name) + (data.bot ? ' <span class="badge">' + esc(words.bot) + "</span>" : "") + "</h2>"
      + '<div class="meta">' + factionDot(data.faction) + esc(words.level) + " " + data.level + " · " + characterLine(data)
      + (data.guild ? " · &lt;" + esc(data.guild) + "&gt;" : "") + " · " + esc(words.hoursPlayed(num(data.hours)))
      + (data.bot && data.zone ? " · " + esc(data.zone) : "") + "</div></div>"
      + '<div class="sheet-ilvl"><b>' + data.itemLevel + "</b><span>" + esc(words.avgItemLevel) + "</span></div>"
      + (popup ? '<a class="btn small" href="#armory/' + esc(encodeURIComponent(data.name)) + '" data-sheet-page>'
        + esc(words.fullPage) + "</a>"
        : '<button class="btn small" type="button" data-sheet-copy>' + esc(words.copyLink) + "</button>")
      + (data.bot && data.online ? '<button class="btn small" type="button" data-sheet-see>' + esc(words.seeOnMap) + "</button>" : "")
    + "</div>"
    + '<section class="card doll"><div class="doll-side">' + DOLL_LEFT.map(s => tile(s, "left")).join("") + "</div>"
      + '<div class="doll-middle"><h3>' + esc(words.statsTitle) + "</h3>" + stats + '<p class="meta">'
      + esc(data.stats.source === "saved" ? words.statsSaved : words.statsGear) + "</p></div>"
      + '<div class="doll-side right">' + DOLL_RIGHT.map(s => tile(s, "right")).join("") + "</div>"
      + '<div class="doll-bottom">' + DOLL_BOTTOM.map(s => tile(s, "left")).join("") + "</div></section>"
    + '<div class="grid two"><section class="card"><h2>' + esc(words.professions) + "</h2>" + skills + "</section>"
      + '<section class="card"><h2>' + esc(words.achievements) + ' <span class="sub">' + esc(words.earned(num(earned.count)))
      + (earned.points === null ? "" : " · " + esc(words.points(num(earned.points)))) + "</span></h2>" + achievements
      + "</section></div>"
    + (popup ? "" : armoryHow("sheet")) + '<div class="item-tip" hidden></div>';

  const copy = host.querySelector("[data-sheet-copy]");
  if (copy) copy.addEventListener("click", event => {
    const link = location.origin + location.pathname + "#armory/" + encodeURIComponent(data.name);
    if (navigator.clipboard) navigator.clipboard.writeText(link).then(() => { event.target.textContent = words.linkCopied; }, () => {});
  });
  const page = host.querySelector("[data-sheet-page]");
  if (page) page.addEventListener("click", closeArmoryPopup);
  const see = host.querySelector("[data-sheet-see]");
  if (see) see.addEventListener("click", () => { closeArmoryPopup(); location.hash = "#world"; setFocus(data.name); });
  for (const img of host.querySelectorAll(".gear-icon img")) {
    img.addEventListener("error", () => {
      // Not in the local client: try the web once (if allowed); not there either (a custom CoA icon): the frame.
      const web = ZAMIMG(img.dataset.iconName);
      if ((data.icons || {}).web && img.getAttribute("src") !== web) { img.src = web; return; }
      img.parentNode.classList.remove("has-icon");
      img.replaceWith(document.createTextNode(img.dataset.initials));
    });
  }
  const tip = host.querySelector(".item-tip");
  const show = node => {
    const piece = bySlot[node.dataset.slot];
    if (!piece) return;
    tip.innerHTML = itemTipHtml(piece, words.slots[piece.slot]);
    tip.hidden = false;
    const box = node.getBoundingClientRect(), holder = host.getBoundingClientRect();
    const left = node.classList.contains("right") ? box.left - holder.left - tip.offsetWidth - 8 : box.right - holder.left + 8;
    tip.style.left = Math.max(0, Math.min(left, holder.width - tip.offsetWidth)) + "px";
    tip.style.top = (box.top - holder.top) + "px";
  };
  for (const node of host.querySelectorAll(".gear-slot[data-slot]")) {
    node.addEventListener("mouseenter", () => show(node));
    node.addEventListener("focus", () => show(node));
    node.addEventListener("mouseleave", () => { tip.hidden = true; });
    node.addEventListener("blur", () => { tip.hidden = true; });
  }
}

// The Armory sheet in a window over the Bots page, opened by the Armory button of a row: the same sheet as
// #armory/Name, without leaving the list. Escape, the close button or a click outside closes it.
function openArmoryPopup(name) {
  let dialog = document.getElementById("armoryPopup");
  if (!dialog) {
    dialog = document.createElement("dialog");
    dialog.id = "armoryPopup";
    dialog.className = "armory-popup";
    dialog.innerHTML = '<button class="btn small armory-popup-close" type="button" aria-label="Close">✕</button>'
      + '<div class="armory-popup-body"></div>';
    dialog.querySelector(".armory-popup-close").addEventListener("click", closeArmoryPopup);
    dialog.addEventListener("click", event => { if (event.target === dialog) closeArmoryPopup(); });
    document.body.appendChild(dialog);
  }
  const body = dialog.querySelector(".armory-popup-body");
  body.dataset.sheet = name;
  renderCharacter(name, body);
  if (!dialog.open) dialog.showModal();
}

function closeArmoryPopup() {
  const dialog = document.getElementById("armoryPopup");
  if (dialog && dialog.open) dialog.close();
}

// The item's tooltip, laid out like the game's: name in its quality's colour, then what it gives.
function itemTipHtml(piece, slotWord) {
  const words = AW();
  const lines = ['<div class="tip-name q' + piece.quality + '">' + esc(piece.name) + "</div>",
                 '<div class="tip-ilvl">' + esc(words.itemLevel(piece.itemLevel)) + "</div>",
                 "<div>" + esc(slotWord) + "</div>"];
  if (piece.damage) {
    const dps = (piece.damage[0] + piece.damage[1]) / 2 / (piece.speed || 1);
    lines.push('<div class="tip-row"><span>' + esc(words.damageRange(piece.damage[0], piece.damage[1])) + "</span><span>"
      + esc(words.speed(piece.speed.toFixed(2))) + "</span></div>", "<div>" + esc(words.dps(one(dps))) + "</div>");
  }
  if (piece.armor) lines.push("<div>" + esc(words.armorValue(piece.armor)) + "</div>");
  for (const stat of piece.stats) lines.push('<div class="tip-stat">+' + stat.value + " " + esc(stat.name) + "</div>");
  if (piece.enchant) lines.push('<div class="tip-green">' + esc(piece.enchant) + "</div>");
  for (const gem of piece.gems) lines.push('<div class="tip-gem">◆ ' + esc(gem) + "</div>");
  if (piece.requiredLevel > 1) lines.push("<div>" + esc(words.requires(piece.requiredLevel)) + "</div>");
  return lines.join("");
}

// dashboard.js drew its first page before this file was loaded.
if (PAGE === "armory") renderArmory();
