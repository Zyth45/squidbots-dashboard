"""pvp_build.py : données de la page « BG / Arènes » du site des joueurs (06/10). Bibliothèque standard seulement.

    python -B pvp_build.py --db nuc --out pvp_data.json        NUC (banc 24 h/24 : C:/CoA-Bench/mysql, my.ini)
    python -B pvp_build.py --db dev --out dev_pvp.json         Dev (ce PC : MySQL 8.4, root-client.ini)
    python -B pvp_build.py --mysql <mysql.exe> --defaults-extra-file <client.ini> --chars-db acore_characters
                           --auth-db acore_auth --playerbots-conf <playerbots.conf> --out <fichier.json>
                                                               autre serveur (Dashboard des serveurs des joueurs)

Lecture seule : chaque requête passe par mysql.exe en sous-processus (-N -B -e), aucune écriture en base. --db ne fait
que poser des valeurs par défaut (chemins, bases dev_*, repères de version) ; tout se règle aussi à la main.

Ce qui sort (agrégé, AUCUN nom de personnage, de compte ni d'adresse) :
  - periodes : « 24h » (les dernières 24 h) et « depuis » (--depuis ; sans --depuis : tout l'historique), bornées par
    --plancher (rien n'est compté avant : v8 du 05/10 23:12, correctifs Warsong et Arathi, pour --db nuc|dev) ;
  - bg[période] : par type (warsong, arathi, alterac, et « tous ») : parties, victoires Alliance / Horde, joueurs par
    partie, objectifs par camp (Warsong : captures, drapeaux rendus ; Arathi : bases attaquées / défendues ; Alterac :
    cimetières, tours, mines), coups fatals par camp, coups fatals par classe (avec le nombre de participations) ;
  - arenes[période] : par type (2v2, 3v3, 5v5, « tous ») : combats cotés, durée moyenne et médiane, victoires par classe,
    et « durees », l'histogramme des durées [[secondes, combats], ...] (pvp_merge.py en refait moyenne et médiane) ;
  - classement : par type, les équipes d'arène qui ont joué, par cote (instantané d'arena_team) : cote, parties,
    victoires, composition par CLASSE, bots_only (tous les membres sur un compte de bot aléatoire : préfixe
    AiPlayerbot.RandomBotAccountPrefix de playerbots.conf, défaut « rndbot »). Le nom n'est gardé que pour une équipe de
    bots dont aucun mot n'est le nom d'un personnage (base, et --groupes) : sinon nom = null (la page dit « Équipe de
    joueurs » ou « Équipe n° <numero> ») ;
  - marques : personnages marqués High Risk (aura 1004019) et War Mode (1004119) dans character_aura (instantané),
    bots / joueurs, victoires honorables du jeu (totalKills, todayKills, yesterdayKills), coffres High Risk au sol ;
    et par période, les BG et arènes joués par ces personnages (participations, victoires, coups fatals) ;
  - manque : ce que la base ne fournit pas (table absente) : laissé de côté, jamais inventé.
Les comptes bruts restent à côté des moyennes (« joueurs » des BG, « durees » des arènes, « classees » du classement) :
pvp_merge.py additionne deux serveurs et recalcule parts, moyennes et médianes à partir d'eux.
Contrôle avant d'écrire : aucun mot d'une chaîne du fichier n'est un nom de personnage (hors vocabulaire fixe : classes,
camps, types) ; au moindre doute, rien n'est écrit (code 1). Écriture atomique (fichier .tmp puis remplacement).
"""
import argparse
import csv
import json
import os
import re
import statistics
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Réglages par machine (--db) : seulement des valeurs par défaut, chaque option les remplace.
MACHINES = {
    "nuc": {"mysql": "C:/CoA-Bench/mysql/bin/mysql.exe", "defaults_file": "C:/CoA-Bench/mysql/my.ini",
            "playerbots_conf": "C:/CoA-Bench/bin/configs/modules/playerbots.conf"},
    "dev": {"mysql": "C:/Program Files/MySQL/MySQL Server 8.4/bin/mysql.exe",
            "defaults_extra_file": "C:/CoA-DevTest/mysql/root-client.ini",
            "playerbots_conf": "C:/CoA-DevTest/build/bin/RelWithDebInfo/configs/modules/playerbots.conf"},
}
# Repères de nos deux serveurs : la 1.9 PvP (arènes) depuis le 06/10 09:16, la v8 (Warsong, Arathi) depuis le 05/10 23:12.
DEPUIS_NOS_SERVEURS = "2026-10-06 09:16:00"
DEPUIS_TITRE_NOS_SERVEURS = "Since 1.9 PvP (arenas)|Depuis la 1.9 PvP (arènes)"
PLANCHER_NOS_SERVEURS = "2026-10-05 23:12:00"
PLANCHER_TITRE_NOS_SERVEURS = "BG fixes of v8 (Warsong, Arathi)|correctifs des BG de la v8 (Warsong, Arathi)"

CLASS_NAMES = {1: "Warrior", 2: "Paladin", 3: "Hunter", 4: "Rogue", 5: "Priest", 6: "Death Knight", 7: "Shaman",
               8: "Mage", 9: "Warlock", 11: "Druid",
               12: "Barbarian", 13: "Witch Doctor", 14: "Felsworn", 15: "Witch Hunter", 16: "Stormbringer",
               17: "Knight of Xoroth", 18: "Guardian", 19: "Templar", 20: "Bloodmage", 21: "Ranger",
               22: "Chronomancer", 23: "Necromancer", 24: "Pyromancer", 25: "Cultist", 26: "Starcaller",
               27: "Sun Cleric", 28: "Tinker", 29: "Venomancer", 30: "Reaper", 31: "Primalist", 32: "Runemaster"}
RACES_ALLIANCE = {1, 3, 4, 7, 11}
AURA_HIGH_RISK = 1004019
AURA_WAR_MODE = 1004119
# pvpstats_battlegrounds.type -> clé ; attr_1..attr_5 de pvpstats_players selon le type (score du champ de bataille).
BG_TYPES = {2: "warsong", 3: "arathi", 1: "alterac"}
BG_OBJECTIFS = {
    "warsong": [("captures", 1), ("drapeaux_rendus", 2)],
    "arathi": [("bases_attaquees", 1), ("bases_defendues", 2)],
    "alterac": [("tours_prises", 3), ("tours_defendues", 4), ("cimetieres_pris", 1), ("cimetieres_defendus", 2),
                ("mines", 5)],
}
ARENE_TYPES = {2: "2v2", 3: "3v3", 5: "5v5"}
CAMPS = ("alliance", "horde")
FMT = "%Y-%m-%d %H:%M:%S"
MOT = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")
NOM_BASE = re.compile(r"[A-Za-z0-9_$]{1,64}")
# Mêmes motifs que le contrôle anti-fuite de generer.py / publier_seedbox.py (un nom d'équipe ne doit jamais y ressembler).
FUITES = re.compile(
    r"\b[A-Za-z]:[\\/]{1,2}(?:Users|CoA|COA|Program|Windows|temp)"
    r"|\\\\[A-Za-z0-9][\w.-]{2,}\\"
    r"|\b192\.168\.\d|\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|\b127\.0\.0\.1\b|:3310\b"
    r"|rduni|CoA-Build|coa-diag|CoA-DevTest|CoA-Bench|wordpress|pclab\.(?:lan|local|home)|\bNAS\b"
    r"|mysql://|acore_\w+|password|passwd|SQUID-NUC",
    re.I)


class Base:
    """mysql.exe en sous-processus, une requête par appel (-N -B -e) ; None = requête refusée (table absente...)."""
    def __init__(self, a):
        self.cmd = [a.mysql]
        # --defaults-file / --defaults-extra-file doivent venir en premier sur la ligne de commande de mysql.
        if a.defaults_file:
            self.cmd.append("--defaults-file=" + a.defaults_file)
        elif a.defaults_extra_file:
            self.cmd.append("--defaults-extra-file=" + a.defaults_extra_file)
        self.cmd += list(a.mysql_opt or []) + ["-N", "-B", "--default-character-set=utf8mb4"]
        self.erreurs = []

    def lignes(self, requete):
        try:
            r = subprocess.run(self.cmd + ["-e", requete], capture_output=True, timeout=180, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError) as e:
            raise SystemExit("mysql : %s %s" % (type(e).__name__, str(e)[:200]))
        if r.returncode:
            self.erreurs.append(r.stderr.decode("utf-8", "replace").strip()[:200])
            return None
        return [l.split("\t") for l in r.stdout.decode("utf-8", "replace").splitlines() if l]


def entier(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


def prefixe_bots(conf, defaut="rndbot"):
    """AiPlayerbot.RandomBotAccountPrefix de playerbots.conf (défaut rndbot), et la plage de cote de départ des équipes."""
    pre, cotes = defaut, {}
    if conf and Path(conf).is_file():
        for l in Path(conf).read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\s*AiPlayerbot\.(RandomBotAccountPrefix|RandomBotArenaTeamMinRating|RandomBotArenaTeamMaxRating)"
                         r"\s*=\s*\"?([^\"#]*?)\"?\s*$", l)
            if m and m.group(2).strip():
                if m.group(1) == "RandomBotAccountPrefix":
                    pre = m.group(2).strip()
                else:
                    cotes[m.group(1)[-9:-6].lower()] = entier(m.group(2).strip())
    if not re.fullmatch(r"[A-Za-z0-9_]{1,32}", pre):
        raise SystemExit("préfixe des comptes de bots illisible : %r" % pre)
    cote = [cotes["min"], cotes["max"]] if cotes.get("min") and cotes.get("max") else None
    return pre, cote


def noms_groupes(chemin):
    """Noms de groupes.csv (colonne name), avec et sans « Bot » : bots du banc, qui ne doivent jamais sortir."""
    noms = set()
    if chemin and Path(chemin).is_file():
        with open(chemin, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                n = (r.get("name") or "").strip()
                if n:
                    noms.add(n.casefold())
                    if n.endswith(" Bot"):
                        noms.add(n[:-4].casefold())
    return noms


def mots(texte):
    """Mots d'un texte, en minuscules, avec et sans les apostrophes et traits d'union qui les relient."""
    out = set()
    for m in MOT.findall(texte or ""):
        out.add(m.casefold())
        out.update(p.casefold() for p in re.split(r"['’-]", m) if p)
    return out


def periodes(maintenant, depuis, titre_depuis, plancher):
    """[(clé, titres, début, fin, coupée)] en heure du serveur (celle des colonnes date / time des tables) ; coupée = début
    ramené au plancher."""
    fin = maintenant.strftime(FMT)
    pl = plancher or ""
    d24 = (maintenant - timedelta(hours=24)).strftime(FMT)
    out = [("24h", ["Last 24 h", "Dernières 24 h"], max(d24, pl), fin, pl > d24)]
    if depuis:
        t = (titre_depuis or "").split("|")
        en = t[0].strip() or "Since " + depuis[:16]
        fr = (t[1].strip() if len(t) > 1 else "") or "Depuis le " + depuis[:16]
        out.append(("depuis", [en, fr], max(depuis, pl), fin, pl > depuis))
    else:
        out.append(("depuis", ["All recorded games", "Tout l'historique"], pl, fin, bool(pl)))
    return out


def stats_camp():
    return {"n": 0, "kb": 0, "morts": 0, "attr": [0, 0, 0, 0, 0]}


def bilan_bg(parties, joueurs_par_bg, cle_type):
    """Agrège une liste de parties [(id, gagnant, type, date)] et leurs joueurs."""
    v = {"alliance": 0, "horde": 0, "autre": 0}
    camps = {c: stats_camp() for c in CAMPS}
    classes = {}
    n_joueurs = 0
    for bid, gagnant, _, _ in parties:
        v["alliance" if gagnant == 1 else "horde" if gagnant == 0 else "autre"] += 1
        for j in joueurs_par_bg.get(bid, ()):
            n_joueurs += 1
            if gagnant in (0, 1):
                camp = "alliance" if (gagnant == 1) == j["gagne"] else "horde"
            else:
                camp = "alliance" if j["race"] in RACES_ALLIANCE else "horde"
            c = camps[camp]
            c["n"] += 1
            c["kb"] += j["kb"]
            c["morts"] += j["morts"]
            for i in range(5):
                c["attr"][i] += j["attr"][i]
            if j["classe"]:
                k = classes.setdefault(j["classe"], {"classe": j["classe"], "n": 0, "kb": 0, "v": 0})
                k["n"] += 1
                k["kb"] += j["kb"]
                k["v"] += 1 if j["gagne"] else 0
    n = len(parties)
    out = {"parties": n, "victoires": v, "joueurs": n_joueurs,
           "joueurs_par_partie": round(n_joueurs / n, 1) if n else None,
           "coups_fatals": {c: camps[c]["kb"] for c in CAMPS},
           "morts": {c: camps[c]["morts"] for c in CAMPS},
           "objectifs": [],
           "classes": sorted(classes.values(), key=lambda k: (-k["kb"] / k["n"], k["classe"]))}
    for nom, i in BG_OBJECTIFS.get(cle_type, []):
        tot = {c: camps[c]["attr"][i - 1] for c in CAMPS}
        out["objectifs"].append({"cle": nom, "total": tot["alliance"] + tot["horde"], **tot})
    return out


def histo(durees):
    """[12, 9, 12] -> [[9, 1], [12, 2]] : durées exactes, taille bornée quel que soit le nombre de combats."""
    h = {}
    for d in durees:
        h[d] = h.get(d, 0) + 1
    return [[d, h[d]] for d in sorted(h)]


def moyenne_histo(h):
    n = sum(c for _, c in h)
    return round(sum(d * c for d, c in h) / n) if n else None


def mediane_histo(h):
    """Médiane exacte d'un histogramme [[valeur, nombre], ...] trié (comme statistics.median sur la liste dépliée)."""
    n = sum(c for _, c in h)
    if not n:
        return None
    rangs, vus, vals = ((n - 1) // 2, n // 2), 0, []
    for d, c in h:
        for r in rangs:
            if vus <= r < vus + c:
                vals.append(d)
        vus += c
    return round(sum(vals) / 2)


def bilan_arenes(combats, membres_par_combat):
    durees = [c["duree"] for c in combats if c["duree"] > 0]
    classes, equipes = {}, set()
    for c in combats:
        equipes.update((c["gagnant"], c["perdant"]))
        for m in membres_par_combat.get(c["id"], ()):
            if not m["classe"]:
                continue
            k = classes.setdefault(m["classe"], {"classe": m["classe"], "n": 0, "v": 0})
            k["n"] += 1
            k["v"] += 1 if m["equipe"] == c["gagnant"] else 0
    equipes.discard(0)
    return {"combats": len(combats),
            "duree_moyenne": round(sum(durees) / len(durees)) if durees else None,
            "duree_mediane": round(statistics.median(durees)) if durees else None,
            "durees": histo(durees),
            "equipes_actives": len(equipes),
            "classes": sorted(classes.values(), key=lambda k: (-k["v"] / k["n"], -k["n"], k["classe"]))}


def desamorcer(x):
    """Comme generer.desamorcer : une valeur 3310 écrite après « : » ressemble au port MySQL du contrôle anti-fuite ;
    décalée d'une unité (sans effet visible sur des totaux). Rend le nombre de valeurs décalées."""
    n = 0
    if isinstance(x, dict):
        for k, v in x.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool) and int(abs(v)) == 3310:
                x[k] = v + (1 if v > 0 else -1)
                n += 1
            else:
                n += desamorcer(v)
    elif isinstance(x, list):
        for v in x:
            n += desamorcer(v)
    return n


def chaines(x, out):
    if isinstance(x, str):
        out.add(x)
    elif isinstance(x, dict):
        for k, v in x.items():
            out.add(k)
            chaines(v, out)
    elif isinstance(x, list):
        for v in x:
            chaines(v, out)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", choices=sorted(MACHINES), help="réglages de nos serveurs (chemins, bases dev_*, repères)")
    ap.add_argument("--out", required=True, help="fichier JSON écrit")
    ap.add_argument("--mysql", help="chemin de mysql.exe (défaut : celui de --db, sinon « mysql »)")
    ap.add_argument("--defaults-file", help="option --defaults-file de mysql (fichier de réglages complet)")
    ap.add_argument("--defaults-extra-file", help="option --defaults-extra-file de mysql (ex. section [client])")
    ap.add_argument("--mysql-opt", action="append", help="option de plus pour mysql, répétable (ex. --mysql-opt=-P3306)")
    ap.add_argument("--chars-db", default="dev_characters", help="base des personnages (repack : acore_characters)")
    ap.add_argument("--auth-db", default="dev_auth", help="base des comptes (repack : acore_auth)")
    ap.add_argument("--realm-id", type=int, default=1, help="royaume lu dans realmlist (nom affiché)")
    ap.add_argument("--royaume", help="nom affiché du royaume (défaut : realmlist)")
    ap.add_argument("--machine", help="étiquette de la source dans la page (défaut : --db)")
    ap.add_argument("--playerbots-conf", help="playerbots.conf (préfixe des comptes de bots aléatoires)")
    ap.add_argument("--bot-prefix", help="préfixe des comptes de bots, s'il n'est pas lu dans playerbots.conf")
    ap.add_argument("--depuis", help="début de la 2e période, heure du serveur (« AAAA-MM-JJ HH:MM:SS » ; vide = tout)")
    ap.add_argument("--depuis-titre", help="titres de la 2e période « anglais|français »")
    ap.add_argument("--plancher", help="rien n'est compté avant cette date (heure du serveur ; vide = aucun)")
    ap.add_argument("--plancher-titre", help="raison du plancher, « anglais|français » (affichée sous une période coupée)")
    ap.add_argument("--equipes", type=int, default=10, help="équipes gardées par type dans le classement")
    ap.add_argument("--groupes", help="groupes.csv : noms de bots de plus, refusés dans un nom d'équipe")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    pre = MACHINES.get(a.db, {})
    a.mysql = a.mysql or pre.get("mysql") or "mysql"
    if not a.defaults_file and not a.defaults_extra_file:
        a.defaults_file = pre.get("defaults_file")
        a.defaults_extra_file = pre.get("defaults_extra_file")
    a.playerbots_conf = a.playerbots_conf or pre.get("playerbots_conf")
    if a.depuis is None:
        a.depuis = DEPUIS_NOS_SERVEURS if a.db else ""
        a.depuis_titre = a.depuis_titre or (DEPUIS_TITRE_NOS_SERVEURS if a.db else None)
    if a.plancher is None:
        a.plancher = PLANCHER_NOS_SERVEURS if a.db else ""
        a.plancher_titre = a.plancher_titre or (PLANCHER_TITRE_NOS_SERVEURS if a.db else None)
    for d in (a.depuis, a.plancher):
        if d:
            datetime.strptime(d, FMT)
    for b in (a.chars_db, a.auth_db):
        if not NOM_BASE.fullmatch(b):
            raise SystemExit("nom de base refusé : %r" % b)
    C, A = "`%s`" % a.chars_db, "`%s`" % a.auth_db
    prefixe, cote_depart = prefixe_bots(a.playerbots_conf)
    if a.bot_prefix:
        prefixe, _ = prefixe_bots(None, a.bot_prefix)
    db = Base(a)
    manque = []

    r = db.lignes("SELECT NOW(), UTC_TIMESTAMP()")
    if not r:
        raise SystemExit("mysql : connexion impossible (%s)" % (db.erreurs[-1] if db.erreurs else "?"))
    maintenant = datetime.strptime(r[0][0], FMT)
    decalage = maintenant - datetime.strptime(r[0][1], FMT)

    def utc(t):
        return (datetime.strptime(t, FMT) - decalage).strftime("%Y-%m-%dT%H:%M:%SZ") if t else None

    royaume = a.royaume
    if royaume is None:
        r = db.lignes("SELECT name FROM %s.realmlist WHERE id = %d" % (A, a.realm_id))
        royaume = r[0][0] if r else ""
    pers = periodes(maintenant, a.depuis, a.depuis_titre, a.plancher)
    t = (a.plancher_titre or "").split("|")
    titre_plancher = [t[0].strip(), (t[1] if len(t) > 1 else t[0]).strip()] if t[0].strip() else None
    debut_min = min(p[2] for p in pers)
    condition = ("'%s'" % debut_min) if debut_min else "'1970-01-01 00:00:00'"

    # Comptes de bots aléatoires : nom du compte commençant par le préfixe (sans LIKE : « _ » y serait un joker).
    est_bot = "(LEFT(UPPER(ac.username), %d) = UPPER('%s'))" % (len(prefixe), prefixe)
    # Noms de tous les personnages : seulement pour refuser un nom d'équipe qui en contient un ; jamais écrits.
    noms = {l[0].casefold() for l in (db.lignes("SELECT name FROM %s.characters" % C) or []) if l and l[0]}
    if not noms:
        raise SystemExit("characters illisible : impossible de contrôler les noms (%s)" % (db.erreurs[-1:] or "?"))
    noms |= noms_groupes(a.groupes)

    # ---------------------------------------------------------------------------------------------- marques
    marques = {}
    for l in db.lignes("SELECT a.spell, a.guid, %s FROM (SELECT DISTINCT spell, guid FROM %s.character_aura WHERE spell IN (%d, %d)) a "
                       "LEFT JOIN %s.characters c ON c.guid = a.guid LEFT JOIN %s.account ac ON ac.id = c.account"
                       % (est_bot, C, AURA_HIGH_RISK, AURA_WAR_MODE, C, A)) or []:
        marques.setdefault(entier(l[0]), {})[entier(l[1])] = l[2] == "1"
    hr = marques.get(AURA_HIGH_RISK, {})
    wm = marques.get(AURA_WAR_MODE, {})

    def resume_marque(guids):
        out = {"total": len(guids), "bots": sum(1 for b in guids.values() if b), "joueurs": sum(1 for b in guids.values() if not b)}
        return out

    hk = {}
    for l in db.lignes("SELECT CASE WHEN EXISTS (SELECT 1 FROM %s.character_aura x WHERE x.guid = c.guid AND x.spell = %d) THEN 'high_risk' "
                       "WHEN EXISTS (SELECT 1 FROM %s.character_aura x WHERE x.guid = c.guid AND x.spell = %d) THEN 'war_mode' "
                       "ELSE 'autres' END AS g, COUNT(*), SUM(c.totalKills), SUM(c.todayKills), SUM(c.yesterdayKills) "
                       "FROM %s.characters c GROUP BY g" % (C, AURA_HIGH_RISK, C, AURA_WAR_MODE, C)) or []:
        hk[l[0]] = {"personnages": entier(l[1]), "total": entier(l[2]), "aujourdhui": entier(l[3]), "hier": entier(l[4])}
    m_out = {"high_risk": resume_marque(hr), "war_mode": resume_marque(wm),
             "victoires_honorables": hk or None}
    r = db.lignes("SELECT COUNT(*), SUM(created >= NOW() - INTERVAL 1 DAY) FROM %s.highrisk_chest" % C)
    if r is None:
        manque.append("highrisk_chest")
    else:
        m_out["coffres_hr"] = {"au_sol": entier(r[0][0]), "poses_24h": entier(r[0][1])}

    def groupe_marque(guid):
        return "high_risk" if guid in hr else "war_mode" if guid in wm else "autres"

    # ---------------------------------------------------------------------------------------------- champs de bataille
    bgs = db.lignes("SELECT id, winner_faction, type, date FROM %s.pvpstats_battlegrounds WHERE date >= %s" % (C, condition))
    joueurs_par_bg = {}
    if bgs is None:
        manque.append("pvpstats_battlegrounds")
        bgs = []
    else:
        bgs = [(entier(l[0]), entier(l[1]), entier(l[2]), l[3]) for l in bgs]
        jr = db.lignes("SELECT p.battleground_id, p.winner+0, IFNULL(c.race, 0), IFNULL(c.class, 0), IFNULL(p.score_killing_blows, 0), "
                       "IFNULL(p.score_deaths, 0), IFNULL(p.attr_1, 0), IFNULL(p.attr_2, 0), IFNULL(p.attr_3, 0), IFNULL(p.attr_4, 0), "
                       "IFNULL(p.attr_5, 0), p.character_guid FROM %s.pvpstats_players p "
                       "JOIN %s.pvpstats_battlegrounds b ON b.id = p.battleground_id "
                       "LEFT JOIN %s.characters c ON c.guid = p.character_guid WHERE b.date >= %s" % (C, C, C, condition))
        if jr is None:
            manque.append("pvpstats_players")
        for l in jr or []:
            cl = entier(l[3])
            joueurs_par_bg.setdefault(entier(l[0]), []).append(
                {"gagne": l[1] == "1", "race": entier(l[2]), "classe": CLASS_NAMES.get(cl, "#%d" % cl) if cl else None,
                 "kb": entier(l[4]), "morts": entier(l[5]), "attr": [entier(x) for x in l[6:11]], "guid": entier(l[11])})

    # ---------------------------------------------------------------------------------------------- arènes
    combats = db.lignes("SELECT fight_id, time, type, duration, winner, loser FROM %s.log_arena_fights WHERE time >= %s" % (C, condition))
    membres_par_combat = {}
    if combats is None:
        manque.append("log_arena_fights")
        combats = []
    else:
        combats = [{"id": entier(l[0]), "t": l[1], "type": entier(l[2]), "duree": entier(l[3]), "gagnant": entier(l[4]),
                    "perdant": entier(l[5])} for l in combats]
        mr = db.lignes("SELECT m.fight_id, m.guid, m.team, IFNULL(c.class, 0) FROM %s.log_arena_memberstats m "
                       "JOIN %s.log_arena_fights f ON f.fight_id = m.fight_id LEFT JOIN %s.characters c ON c.guid = m.guid "
                       "WHERE f.time >= %s" % (C, C, C, condition))
        if mr is None:
            manque.append("log_arena_memberstats")
        for l in mr or []:
            cl = entier(l[3])
            membres_par_combat.setdefault(entier(l[0]), []).append(
                {"guid": entier(l[1]), "equipe": entier(l[2]), "classe": CLASS_NAMES.get(cl, "#%d" % cl) if cl else None})

    # ---------------------------------------------------------------------------------------------- périodes
    sortie_periodes, bg_out, arenes_out, hr_out = [], {}, {}, {}
    for cle, titres, debut, fin, coupee in pers:
        sortie_periodes.append({"cle": cle, "titre": titres, "debut": debut or None, "fin": fin,
                                "debut_utc": utc(debut), "fin_utc": utc(fin), "coupee": coupee})
        dans = [g for g in bgs if (not debut or g[3] >= debut) and g[3] <= fin]
        bg_out[cle] = {t: bilan_bg([g for g in dans if g[2] == n], joueurs_par_bg, t) for n, t in BG_TYPES.items()}
        bg_out[cle]["tous"] = bilan_bg(dans, joueurs_par_bg, "tous")
        cb = [c for c in combats if (not debut or c["t"] >= debut) and c["t"] <= fin]
        arenes_out[cle] = {t: bilan_arenes([c for c in cb if c["type"] == n], membres_par_combat) for n, t in ARENE_TYPES.items()}
        arenes_out[cle]["tous"] = bilan_arenes(cb, membres_par_combat)
        # High Risk / War Mode : BG et arènes joués par les personnages marqués AUJOURD'HUI (l'aura est un instantané).
        g = {k: {"bg": {"n": 0, "v": 0, "kb": 0}, "arenes": {"n": 0, "v": 0}} for k in ("high_risk", "war_mode", "autres")}
        for bid, _, _, _ in dans:
            for j in joueurs_par_bg.get(bid, ()):
                x = g[groupe_marque(j["guid"])]["bg"]
                x["n"] += 1
                x["v"] += 1 if j["gagne"] else 0
                x["kb"] += j["kb"]
        for c in cb:
            for m in membres_par_combat.get(c["id"], ()):
                x = g[groupe_marque(m["guid"])]["arenes"]
                x["n"] += 1
                x["v"] += 1 if m["equipe"] == c["gagnant"] else 0
        hr_out[cle] = g

    # ---------------------------------------------------------------------------------------------- classement
    classement = {}
    equipes = db.lignes("SELECT arenaTeamId, name, type, rating, seasonGames, seasonWins FROM %s.arena_team" % C)
    if equipes is None:
        manque.append("arena_team")
        equipes = []
    membres = {}
    for l in db.lignes("SELECT tm.arenaTeamId, IFNULL(c.class, 0), IFNULL(%s, 0) FROM %s.arena_team_member tm "
                       "LEFT JOIN %s.characters c ON c.guid = tm.guid LEFT JOIN %s.account ac ON ac.id = c.account"
                       % (est_bot, C, C, A)) or []:
        cl = entier(l[1])
        membres.setdefault(entier(l[0]), []).append((CLASS_NAMES.get(cl, "#%d" % cl) if cl else "?", l[2] == "1"))
    noms_remplaces = 0
    for n, t in ARENE_TYPES.items():
        liste = []
        for l in equipes:
            if entier(l[2]) != n:
                continue
            eid, nom = entier(l[0]), l[1]
            ms = membres.get(eid, [])
            bots_only = bool(ms) and all(b for _, b in ms)
            # Nom gardé seulement pour une équipe de bots dont aucun mot n'est le nom d'un personnage.
            if bots_only and nom and not (mots(nom) & noms) and nom.casefold() not in noms and not FUITES.search(nom):
                nom_public = nom
            else:
                nom_public = None
                noms_remplaces += 1 if bots_only else 0
            liste.append({"numero": eid, "nom": nom_public, "bots_only": bots_only, "cote": entier(l[3]),
                          "parties": entier(l[4]), "victoires": entier(l[5]), "composition": sorted(c for c, _ in ms)})
        jouees = sorted((e for e in liste if e["parties"] > 0), key=lambda e: (-e["cote"], -e["victoires"], e["numero"]))
        for i, e in enumerate(jouees, 1):
            e["rang"] = i
        classement[t] = {"equipes": len(liste), "classees": len(jouees), "sans_partie": sum(1 for e in liste if e["parties"] == 0),
                         "de_joueurs": sum(1 for e in liste if not e["bots_only"]), "tete": jouees[:max(0, a.equipes)]}

    data = {
        "format": 1,
        "fait_le": maintenant.strftime(FMT),
        "fait_le_utc": utc(maintenant.strftime(FMT)),
        "royaume": royaume,
        "machine": a.machine if a.machine is not None else (a.db or ""),
        "periodes": sortie_periodes,
        "plancher": {"debut": a.plancher, "debut_utc": utc(a.plancher), "titre": titre_plancher} if a.plancher else None,
        "bg": bg_out,
        "arenes": arenes_out,
        "classement": classement,
        "cote_depart": cote_depart,
        "marques": m_out,
        "marques_periodes": hr_out,
        "manque": manque,
    }

    # Contrôle : aucun mot d'une chaîne n'est un nom de personnage, hors vocabulaire fixe (classes, clés, titres).
    fixe = set()
    for s in list(CLASS_NAMES.values()) + [p[1][0] for p in pers] + [p[1][1] for p in pers] + (titre_plancher or []):
        fixe |= mots(s)
    roy = set()
    if royaume and ((mots(royaume) & noms) - fixe or FUITES.search(royaume)):
        data["royaume"] = ""
        roy = {royaume}
    suspects = set()
    for s in chaines(data, set()) - roy:
        if FUITES.search(s):
            suspects.add(s)
        for m in mots(s) - fixe:
            if m in noms and not re.fullmatch(r"[a-z0-9_]+", s):   # les clés (warsong, high_risk...) sont du vocabulaire
                suspects.add(s)
    if suspects:
        raise SystemExit("contrôle : %d chaîne(s) suspecte(s), rien n'est écrit (%s)" % (len(suspects), sorted(suspects)[0][:60]))
    n = desamorcer(data)
    sortie = Path(a.out)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    tmp = sortie.with_name(sortie.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="")
    os.replace(tmp, sortie)
    b, ar = bg_out[pers[-1][0]]["tous"]["parties"], arenes_out[pers[-1][0]]["tous"]["combats"]
    print("pvp_build : %s, %d BG et %d combats d'arène (%s), %d équipe(s) classée(s), High Risk %d, War Mode %d%s%s%s" % (
        sortie.name, b, ar, pers[-1][1][1].lower(), sum(len(c["tete"]) for c in classement.values()), len(hr), len(wm),
        ", %d nom(s) d'équipe remplacé(s)" % noms_remplaces if noms_remplaces else "",
        ", manque : " + " ".join(manque) if manque else "", ", %d valeur(s) 3310 décalée(s)" % n if n else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
