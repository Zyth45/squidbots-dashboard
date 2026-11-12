# Liaison SquidBot 3.0 → SquidBots Dashboard (proposition CoA Dashboard, 08/11)

Réponse à VISION-3.0 §4 bis. Format validé par le Pilote le 08/11. Le côté module est réparti entre trois sessions, à contacter chacune pour sa partie une fois démarrée : **CoA SquidBot** (D:\CoA-SquidBot, après L1) pour `world.json` (population, âmes, surnoms), **CoA Monde** pour `events.jsonl` et **CoA Economie** pour `economy.json`. Les runs (`groups.json`, `runs.jsonl`) viennent de **CoA Dungeon Clear**. Le Builder garde les bancs et les builds.

**Statut (08/11)** : principe accepté par le Builder, avec les modifications du §6 (elles priment sur le reste du document). Il lancera le module après le banc CPU A/B (chantier 0), sur l'ordre du Pilote. Non surveillé, le module doit rester dans le bruit de mesure. Les champs de `groups.json` et `runs.jsonl` restent à arrêter avec CoA Dungeon Clear.

## 1. Choix : des fichiers JSON écrits par le module, pas d'API HTTP

On prolonge ce qui marche déjà : `bot-status.json`, écrit par `CoaStatusFile.cpp`. Le monde construit le snapshot (moins de 1 ms pour 1000 bots), un thread à part écrit `.tmp` puis renomme, et le dashboard met la lecture en cache selon (mtime, taille).

| | Fichiers JSON | API HTTP dans le worldserver |
|---|---|---|
| Coût CPU | construction sur le thread monde, à intervalle fixe, à partir de compteurs déjà tenus ; écriture hors du thread monde | chaque requête lit les objets du monde : il faut un verrou ou une copie, avec le même coût en plus de la pile HTTP |
| Lecteurs multiples | gratuits (le cache du dashboard, le Manager, les scripts du banc, `jq`) | une requête par lecteur |
| Sécurité | aucun port, aucune popup du pare-feu ; la lecture suit les droits du dossier logs | un port à ouvrir, à lier sur 127.0.0.1 et à authentifier |
| Fraîcheur | l'intervalle de chaque sujet, de 5 à 60 s : assez pour un tableau de bord | immédiate (inutile ici) |
| Code module | on étend un écrivain qui existe déjà | un serveur HTTP à embarquer et à maintenir |

Les **actions** (commandes aux bots) ne passent pas par un fichier. Elles passent par la console RA, que le dashboard utilise déjà (`webapp/ra.py`, authentifiée, réservée aux comptes GM), avec des commandes `.squidbot …` du module. Il n'y a ni nouveau port ni boîte aux lettres écrivable.

## 2. Rien ne coûte quand personne ne regarde

- Le dashboard écrit `squidbot/watch.json` toutes les 30 s pendant qu'une page qui en a besoin est ouverte, par exemple `{"at": 1762600000, "topics": ["world", "economy"]}`.
- Le module ne lit que la date de ce fichier (un `stat`), toutes les 5 s. Il ne construit un sujet que si on l'a demandé il y a moins de 90 s. Sans lecteur, le coût se réduit à ce `stat`.
- `runs.jsonl` est la seule exception : une ligne par run DC terminé, toujours écrite, pour garder un historique complet (le coût est négligeable).
- `CoaStatusFile`, la règle existante, reste valable : `""` coupe tout. Le dossier vient de `AiPlayerbot.CoaDataDir` (par défaut, `squidbot/` à côté de `bot-status.json`).

## 3. Les fichiers

Toujours dans `<logs>/squidbot/`. Chaque fichier a la même enveloppe :

```json
{ "schema": "squidbot.world/1", "at": 1762600000, "every": 10, "build_us": 420, "data": { … } }
```

- `schema` : sujet et version majeure. Le dashboard accepte une version mineure plus récente et ignore les champs qu'il ne connaît pas. Il refuse une version majeure qu'il ne connaît pas et le dit.
- `at` : epoch du snapshot ; un fichier plus vieux que 3 × `every` est périmé.
- `build_us` : coût sur le thread monde, pour le suivi pmon.

| Fichier | `every` | Contenu de `data` |
|---|---|---|
| `bot-status.json` | 5 s | existant, inchangé (un bot par entrée) |
| `world.json` | 10 s | population et santé |
| `economy.json` | 60 s | marché, crafts, commandes |
| `groups.json` | 15 s | runs en cours et cumul du jour |
| `runs.jsonl` | à chaque fin de run | une ligne par run terminé |
| `events.jsonl` | au fil de l'eau | journal en direct : erreurs, bots coincés, boss, wipes. Rotation à 5 Mo, en gardant le `.1` |

### world.json
```json
{ "online": 487, "players": 2,
  "zones":  [{"map": 0, "zone": 1519, "bots": 61, "capital": true}],
  "activities": {"quest": 212, "grind": 64, "city": 88, "travel": 41, "fish": 9, "pvp": 23, "dungeon": 35, "idle": 15},
  "souls": {"lazy": 85, "quester": 160, "wanderer": 94, "trader": 76, "pvp": 57},
  "surname": {"mode": 2, "list_size": 64, "top": [{"name": "Stormhand", "bots": 12}]},
  "health": { "tick_ms": {"avg": 38, "p95": 61, "max": 140},
              "bots_us_per_tick": {"avg": 9200, "p95": 15800},
              "by_strategy_us": [{"name": "rpg", "us": 3100}, {"name": "travel", "us": 1900}],
              "stuck": [{"guid": 1234, "name": "Arwen", "map": 1, "x": 0, "y": 0, "z": 0, "since": 1762599700, "why": "no path"}],
              "errors_10m": 3 } }
```
Les activités viennent de la stratégie active (même table que `ActionTasks`). `souls` donne le nombre de bots par archétype `CoaArchetype` (Lazy, Quester, Wanderer, Trader, PvP ; voir D:\CoA-IALLM\docs\ACCROCHES-LLM-3.0.md). `surname` reprend `AiPlayerbot.CoaBotSurname` (0 = aucun, 1 = « Bot », 2 = liste), la taille de la liste et, en mode 2, les noms les plus portés. Les deux arrivent avec L1 et valent `null` d'ici là.

### economy.json
```json
{ "auctions": 3120, "gold_circulating": 18450000, "gold_bots": 16200000,
  "categories": [{"class": 7, "sub": 5, "auctions": 410, "avg": 2350, "low": 900, "usual": 2100, "high": 4800, "volume_24h": 380}],
  "top_sales_24h": [{"item": 14047, "count": 212, "gold": 640000}],
  "crafts_24h": [{"skill": 197, "item": 14048, "count": 31, "profit": 52000}],
  "orders": [{"id": 77, "buyer": "Squid", "bot": "Thorgal", "item": 14154, "price": 1250000, "state": "crafting", "at": 1762599000}] }
```
Les montants sont en cuivre. `low/usual/high` sont les bandes de prix du §2 de la vision.

### groups.json et runs.jsonl (champs de Dungeon Clear, arrêtés le 08/11)
Les noms suivent le JSONL du banc DC (`bin/dc_testruns.jsonl`, schéma 19) : camelCase, dates en ms. `dungeon` est la clé courte de DC (`sfk`, `rfc`, `dm-east`…), et `difficulty` vaut 0 (normal), 1 (héroïque) ou 2 (mythique).
```json
{ "running": [{"runId": 9812, "dungeon": "sfk", "dungeonName": "Shadowfang Keep", "difficulty": 0, "bots": 5, "players": 0,
               "startedAtMs": 1762599100000, "bossesKilled": 2, "bossesTotal": 5, "wipes": 0}],
  "today": {"runs": 42, "cleared": 37, "wipes": 11, "bossKills": 168},
  "byDungeon": [{"dungeon": "sfk", "dungeonName": "Shadowfang Keep", "runs": 9, "cleared": 9, "medianS": 1420, "bestS": 1180, "wipes": 1}] }
```
- `running` : l'état live par groupe que DC exposera ; le module le lit toutes les 15 s.
- `today` et `byDungeon` : agrégats que le module calcule à partir de `runs.jsonl`.

Une ligne de `runs.jsonl` par run `dc on` réel. C'est un sous-ensemble de la ligne du banc, plus `wipes` et `players` :
`{"runId":…, "dungeon":"sfk", "dungeonName":…, "difficulty":0, "startedAtMs":…, "endedAtMs":…, "durationS":…, "result":"clear|wipe|aborted|setup_failed", "bossesKilled":…, "bossesTotal":…, "bossTimeline":[{"t":312,"entry":3914,"name":"…","via":"…"}], "wipes":1, "comp":[{"name","class","spec","role"}], "players":["…"]}`
- Le dashboard lit lui-même les 8 dernières lignes, depuis la fin du fichier, pour la liste « Derniers runs ».
- Aujourd'hui, DC n'écrit ces lignes que pour les runs de banc (`dc test`). La ligne en jeu réel et l'état live sont au plan DC 3.0.

### events.jsonl
`{"at":…,"kind":"error|stuck|unstuck|boss|wipe|order","bot":"…","text":"…"}`. Le dashboard le lit en `tail` (comme Chat.log aujourd'hui) et l'affiche en direct.

## 4. Actions (3.0, deuxième temps)
Les commandes RA du module sont `.squidbot bot <nom> stop|resume|summon|unstuck`, `.squidbot order cancel <id>` et `.squidbot reload`. Le dashboard n'envoie que des commandes d'une liste blanche, et seulement depuis ses pages privées. Le module vérifie le niveau GM du compte RA.

## 5. Côté dashboard
- `webapp/vivant.py` lit les fichiers, met chacun en cache selon (mtime, taille) et écrit `watch.json`. Quand un fichier manque, il sert des **données factices** marquées `"demo": true`, et la page affiche alors un bandeau.
- Une page privée « Monde vivant » (`#vivant`) a quatre onglets : Population, Économie, Groupes, Santé. Elle n'est jamais publiée dans la copie publique.

## 6. Décisions du Builder (08/11), qui priment sur ce qui précède
- L'enveloppe gagne `server_start` (epoch) et `module` (sha court), pour repérer un redémarrage ou un changement de version.
- L'écriture passe par `.tmp` puis `MoveFileEx(REPLACE_EXISTING)`. Si le dashboard tombe sur une violation de partage, il réessaie une fois après 100 ms (c'est fait dans `webapp/vivant.py`).
- `world.json` sort de la même passe que `bot-status.json`, sans scan en plus. `tick_ms` vient des statistiques du cœur.
  - `bots_us_per_tick` et `by_strategy_us` valent `null` sans PerfMon.
  - `stuck` vaut `null` jusqu'au détecteur 3.0 ; `souls` et `surname` valent `null` jusqu'à L1.
  - `errors_10m` est **retiré** : les entrées `error` de `events.jsonl` le remplacent.
- `economy.json` (60 s, seulement s'il est surveillé) fait une passe sur l'hôtel des ventes. `gold_*` vient d'une requête asynchrone mise en cache. Les bandes de prix, `crafts_24h` et `orders` restent des tableaux vides jusqu'à l'économie 3.0.
- `groups.json` et `runs.jsonl` : l'état des runs appartient à Dungeon Clear. Le module n'écrit que ce que DC expose ; les champs, arrêtés avec DC, sont au §3.
- Réglages : `AiPlayerbot.CoaDataDir` (`""` = `<Logs>/squidbot`) et `AiPlayerbot.CoaDataFiles = 1` (`0` coupe tout, y compris `runs.jsonl`).

## 7. Maquette (branche `feature/vivant-3.0` du dépôt dashboard)
- `webapp/vivant.py` lit les fichiers et met en cache selon (mtime, taille). Il vérifie la version du schéma, signale un fichier périmé au-delà de 3 × `every`, et réécrit `watch.json` toutes les 30 s, mais seulement si le dossier `squidbot/` existe.
- Pour chaque sujet absent, il sert des données factices, signalées par un bandeau.
- `static/vivant.js` : la page privée `#vivant` (Population, Économie, Groupes et donjons, Santé). Les `null` du §6 s'affichent « – » ou « arrive avec CoA Bots 3.0 », jamais en faux chiffres.
- Elle est absente de la copie publique, car `public_files()` la refuse.

## 8. Branchement réel (08/11 soir)
- **economy.json** est écrit par CoA Economie (commit 14068cc4, `AiPlayerbot.CoaEconomy.DataFile.Enable = 1`, coupé par défaut). La page Économie le lit tel quel.
  - Les valeurs `null` (or, prix, bandes) s'affichent « – ».
  - Les catégories (classe et sous-classe) sont regroupées par classe d'objet. Les prix sont pondérés par le nombre d'enchères.
  - Les noms et qualités des objets viennent de `item_template`, en une requête par nouvel objet.
  - Les métiers sont affichés par leur nom, à partir de l'id de compétence.
  - Les états de commande sont mailed, refused et busy.
  - La courbe des enchères sur 48 h est tenue par le dashboard (un point toutes les 15 min), car le module n'envoie que la valeur du moment.
- **Correctif d'amorçage** : le module ne crée `squidbot/` qu'en écrivant, et il n'écrit que si `watch.json` existe. Le dashboard crée donc le dossier, mais seulement dans un dossier de logs existant.
- **Dossier** : `squidbotDir` dans dashboard.json (même rôle que `AiPlayerbot.CoaDataDir`). Vide, c'est `squidbot/` à côté de CoaBots.log, c'est-à-dire `LogsDir`.
- **events.jsonl** : écrit par CoA Monde (coa-3.0-monde c881e5c4, pas encore dans un build), activé par `AiPlayerbot.CoaWorld.Events.Enable = 1`.
  - Le module l'écrit toujours quand l'option est active, sans tenir compte de watch.json, puisque c'est un journal.
  - Valeurs de `kind` chez Monde : invasion, rush, server_first, guild, stuck, unstuck. Les valeurs error, boss, wipe et order sont réservées à DC et à Economie.
  - Le dashboard lit les 200 dernières lignes, en complétant par `events.jsonl.1` juste après une rotation, et les affiche dans l'onglet **Journal**, filtrable par `kind`.
- **world.json** : écrit par CoA SquidBot (coa-3.0-live 0c3eb7c1, pas encore dans un build), activé par `AiPlayerbot.CoaLive.DataFile.Enable = 1`.
  - Il donne les 40 zones les plus peuplées. Les noms de zones viennent d'AreaTable.dbc, même quand MySQL est arrêté.
  - `souls` est écrit depuis a5dcd8c0 (bots en ligne par archétype). Il vaut `null` tant que `AiPlayerbot.CoaSoul.Enable = 0`, et la page le dit.
  - Valent `null` : `tick_ms.p95`, `bots_us_per_tick`, `by_strategy_us` et stuck. La page les montre comme tels.
  - Les courbes de tick et de bots en ligne sur 6 h sont tenues par le dashboard, en mémoire : un point toutes les 5 min tant que la page est ouverte.
  - Le coût des snapshots n'additionne que les fichiers réels.
- Correctif au passage : quand MySQL ne répond pas, les noms de zones (DBC) se chargent avant les classes (base).
- **groups.json** et **runs.jsonl** attendent le plan DC 3.0.

## 9. Économie complète et vie du serveur (09/11, demande de l'user via le Pilote)
- **Population** : toutes les activités de SquidBot (rest, grind, camp, wander_random, wander_npc, quest, flight, pvp, city, fish, gather, dungeon simulé, idle), triées par nombre. Répartition Alliance/Horde par zone (`zones[].faction`, SquidBot 0926f235). Bloc « Capitales ».
- **Vie du monde** (nouvel onglet) : lit `monde.json`, proposé à CoA Monde (schema `squidbot.monde/1`, every 30 s, seulement si watch.json contient `monde`) :
  `{"invasions":[{zone,map,kind,since,ends,bots}], "rushes":[{what,zone,since,bots}], "guilds":[{id,name,members,bots,online,bank_gold,orders_open}], "guild_orders":[{id,guild,item,count,state,at}], "server_firsts":[{what,by,at}], "recovery_24h":{stuck,unstuck}}`.
  Sans ce fichier, les premiers du serveur, les faits marquants et les coincés sur 24 h viennent d'`events.jsonl`. Les noms de zones viennent d'AreaTable.dbc, les objets d'item_template.
- **Économie** : fonte (`smelt_24h`), désenchantement (`disenchant_24h`, avec `from`), horloge des enchères (`clock` : enabled, offline_added_s, sold/expired/relisted_24h) et AHBot (`ahbot_24h` : listed, bought, gold_in, gold_out). Noms proposés à CoA Economie ; absents ou `null`, la carte dit « arrive avec CoA Bots 3.0 ».
- **Santé** : `tick_ms.p95` (SquidBot 0926f235). `stuck` reste `null` chez SquidBot : la carte et le compteur prennent les events stuck/unstuck de Monde sur 24 h. **Logs en direct** : les 120 dernières lignes de CoaBots.log (64 Ko lus depuis la fin), filtrables, erreurs en rouge, relues toutes les 15 s. Page privée seulement.
- Commandes aux bots : toujours en lecture seule. Elles viendront par la liste blanche RA du §4.

## 10. Formats livrés par les modules (09/11)
- **CoA Economie** (coa-3.0-eco ed530e06), toujours `squidbot.economy/1` :
  - `smelt_24h` [{item, count}], `disenchant_24h` et `prospect_24h` [{item, count, from}] (pour la prospection, `from` = minerais, 5 par prospection). Le dashboard les montre dans une carte « Désenchantement et prospection ».
  - `clock` {enabled, offline_added_s, resumed (enchères décalées au démarrage), expired_24h, sold_24h (joueurs et bots), relisted_24h: null (pas de remise en vente)}.
  - `ahbot_24h` {listed, bought, gold_in (net de la taxe), gold_out}, en cuivre. `orders[]` gagne `skill` (0 si refusée) et `kind` ("player").
  - Un compteur vaut 0 ou [] quand sa brique est coupée.
- **CoA Monde** (coa-3.0-monde 20b305f5), `monde.json`, `squidbot.monde/1`, every 30, activé par `AiPlayerbot.CoaWorld.StateFile.Enable = 1` (coupé par défaut) :
  - `invasions[]` : zone, map, kind, site, state ("announced" | "running"), level, wave, since (null si annoncée), starts (null si en cours), ends, bots.
  - `rushes[]` (au plus une) : what, zone, map, area (sous-zone), level, nodes, since, ends, bots.
  - `guilds[]` : guildes avec quelqu'un en ligne, 50 au plus ; `bots` = bots en ligne, `online` = tous ; `bank_gold` en cuivre ; `orders_open` toujours null (une commande est servie tout de suite), la colonne est donc masquée.
  - `guild_orders[]` : les 20 dernières depuis le démarrage ; state shared | crafted | bought | none, `by` = bot qui l'a servie.
  - `server_firsts[]` : les 20 derniers {what, by, guild, at} ; `recovery_24h` {stuck, unstuck}.
  - Pas encore passé au banc côté Monde : testé ici avec des fichiers à ce format sur le royaume d'essai.

## 11. Tout le monde en ligne : `world.json` → `everyone` (CoA SquidBot d2ce3948, 09/11)
Ajout seulement, même version de schéma. Les autres champs de `world.json` continuent de ne compter que les bots aléatoires.
```json
"everyone": {
  "total":    {"players": n, "alts": n, "bots": n},
  "places":   {"battleground": M, "arena": M, "raid": M, "dungeon": M, "capital": M, "world": M},
  "factions": {"alliance": M, "horde": M},
  "zones":    [{"map": n, "zone": n, "capital": bool, "players": n, "alts": n, "bots": n}]
}
```
- `M` = `{"players", "alts", "bots"}`. `players` = vrais joueurs ; `alts` = bots tenus par un joueur (alts, addbots) ; `bots` = bots aléatoires.
- Chaque personnage est compté dans un seul lieu, le premier qui convient : arène > champ de bataille > raid > donjon > capitale > monde.
- `zones` : les 40 zones les plus peuplées, triées par total.
- Même passe et même écriture que le reste du fichier, rien par tick.
- Côté dashboard (Population) : quand `everyone` est là, les tuiles (personnages en ligne, joueurs, capitale, donjon + raid, champ de bataille + arène), le tableau « Tout le monde en ligne » (lieux × joueurs/alts/bots, puis factions) et la liste des zones en viennent. Sans lui, la page reste sur les bots aléatoires ; les bots en champ de bataille sont alors comptés d'après la carte de leur zone.

## 12. Montée en charge et coincés distincts (09/11)
- **Montée en charge** (demande de l'user) : tant que les bots en ligne n'ont pas atteint 95 % du nombre visé, et pendant 5 min de plus, Santé affiche « Montée en charge » à la place du tick, et la courbe du tick ne garde pas ces points. Le nombre visé et la fin de la montée viennent de `health.ramp` = `{target, done_at, after_s}` (CoA SquidBot, coa-3.0-live : `target` = GetMaxAllowedBotCount avec CoaPlayersReplaceBots ; `tick_ms` vaut null jusqu'à `done_at + after_s`, puis avg et p95 sur les 3 000 derniers ticks et max depuis ce moment ; avec `target` 0 (pas de bots aléatoires), `done_at` est posé au premier passage, puis les mêmes 300 s ; commit 3cd8ac28). En attendant, le dashboard prend `AiPlayerbot.MinRandomBots` dans playerbots.conf et calcule lui-même la fin de la montée ; le max du cœur contient alors encore les pics du démarrage et s'affiche « max depuis le démarrage ».
- **monde.json `recovery_24h`** (Monde, prochain exe) : `stuck` et `unstuck` comptent des bots distincts ; `stuck_events` et `unstuck_events` comptent les détections ; `since` = début de la fenêtre (max(démarrage, maintenant − 24 h)). Le libellé devient « Bots coincés depuis HH:MM » tant que la fenêtre fait moins de 24 h, les détections en pied de tuile.

## 13. Groupes et donjons réels (proposition du 09/11)
Chaque module écrit dans son propre fichier : deux modules qui écrivent le même fichier se marcheraient dessus. Le dashboard assemble les trois sources dans l'onglet Groupes et donjons.

**CoA SquidBot → `world.json`, bloc `groups`** : tous les groupes réels en instance (joueurs, alts et bots mêlés), avec Dungeon Clear ou sans.
```json
"groups": {
  "running": [{"instance": n, "map": n, "dungeon": "sfk", "dungeonName": "Shadowfang Keep", "kind": "dungeon|raid", "difficulty": 0,
               "players": n, "alts": n, "bots": n, "leader": "…", "startedAt": epoch, "bossesKilled": n, "bossesTotal": n|null, "wipes": n, "dc": bool}],
  "today": {"since": epoch, "runs": n, "cleared": n, "wipes": n, "bossKills": n},
  "byDungeon": [{"dungeon": "sfk", "dungeonName": "…", "runs": n, "cleared": n, "wipes": n, "medianS": n, "bestS": n}],
  "last": [{"instance": n, "dungeon": "…", "dungeonName": "…", "difficulty": 0, "startedAt": epoch, "endedAt": epoch, "result": "clear|wipe|left",
            "bossesKilled": n, "bossesTotal": n, "wipes": n, "players": n, "alts": n, "bots": n, "dc": bool}]
}
```
- Un run commence à la première entrée du groupe dans l'instance. Il finit quand la sortie dure plus de 5 min, ou quand l'instance est réinitialisée. Il est `clear` quand le dernier boss est tué.
- Un wipe = tout le groupe mort dans l'instance. `bossesTotal` vient des données CoA (comme DC).
- `today` court depuis 00:00, heure du serveur, ou depuis le démarrage s'il est plus récent. `last` garde les 8 derniers runs.

**CoA Monde → `monde.json`, bloc `dungeon_sim`** : les donjons simulés. Les bots se déconnectent pendant le run, donc ni `world.json` ni `everyone` ne les voient.
```json
"dungeon_sim": {
  "running": [{"dungeon": "…", "dungeonName": "…", "faction": "alliance|horde", "level": n, "bots": n, "startedAt": epoch, "endsAt": epoch, "bosses": n}],
  "today": {"since": epoch, "runs": n, "bossKills": n, "items": n},
  "last": [{"dungeon": "…", "dungeonName": "…", "bots": n, "durationS": n, "bossesKilled": n, "at": epoch}]
}
```

**Dungeon Clear → `runs.jsonl`** (§3, inchangé) : une ligne par run `dc on` réel, avec `bossTimeline` et `comp`. Il ajoute `instance` pour que le dashboard rattache la ligne au run de SquidBot.

**Dashboard** : tuiles (runs du jour, terminés, wipes, boss tués, groupes en cours, bots en donjon = `everyone.places.dungeon + raid` + bots des donjons simulés). En dessous : « En cours » (réels, avec DC marqué, puis simulés), « Par donjon » et « Derniers runs » (détail DC quand il existe). Plus aucune donnée factice dès qu'un des trois blocs existe.

## 14. Plus de chiffres factices pour les joueurs (09/11, décision du Pilote)
- Quand le royaume n'écrit pas un fichier, la page dit quelle option l'active : « active <clé> = 1 dans playerbots.conf (avec AiPlayerbot.CoaDataFiles = 1) ». Les clés : CoaLive.DataFile.Enable (world), CoaEconomy.DataFile.Enable (economy), CoaWorld.StateFile.Enable (monde), CoaWorld.Events.Enable (events).
- Pour les groupes, elle affiche « pas encore de données », puis les derniers runs de DC dès qu'il y en a. Jamais de zéro inventé.
- Les données factices ne servent plus que sur un royaume d'essai : `"vivantDemo": true` dans dashboard.json.
- PerfMon coupé : la page donne la commande (`.playerbots pmon toggle`, MJ) et la clé `AiPlayerbot.PerfMonEnabled = 1`.
- Les courbes sur 6 h (tick, bots en ligne) sont gardées dans `data/<royaume>/vivant-world.json` et reprises au redémarrage du dashboard.
- runs.jsonl (DC) : rotation à 5 Mo en gardant le `.1`, comme events.jsonl.

## 15. Groupes et donjons branchés (09/11)
Le dashboard ne lit plus de `groups.json`. L'onglet assemble trois sources :
- **CoA SquidBot** (coa-3.0-live 24174435) : `world.json` → `groups`, selon le §13, avec ces différences :
  - `dungeon` et `dc` valent toujours null ; `map` est ajouté ; `byDungeon` est rangé par carte.
  - `bossesTotal` = nombre de rencontres du script d'instance (null sans script). `clear` = toutes les rencontres faites.
  - Un run commence au passage de 10 s qui suit l'entrée. `result` vaut `left` s'il n'est ni terminé ni fini sur un wipe.
  - `groups` vaut null tant qu'aucun run n'a eu lieu.
- **CoA Monde** (coa-3.0-monde a9d79274) : `monde.json` → `dungeon_sim` et `bg_sim` (null quand la brique est coupée).
  - `dungeon_sim.running[]` : dungeon (id de carte), dungeonName, faction, level, bots, phase (gathering | inside | back), startedAt, endsAt, bosses.
  - `bg_sim` : `running[]` {bg, bgName, levelMin, levelMax, alliance, horde, phase, startedAt, endsAt} ; `today` {since, matches, allianceWins, hordeWins, honor, purchases} ; `last[]` {bg, bgName, levelMin, levelMax, bots, winner, durationS, honor, at}.
  - Un run simulé compte quand son butin est tiré, au retour du premier bot.
- **Dungeon Clear** : `runs.jsonl` (§3 + `instance`, dc-3.0 ff66c98), rotation à 5 Mo vers `.1`.
  - `runId` = `rr-<aaaammjj-hhmmss>-<instance>`. `result` : clear, wipe ou aborted (`setup_failed` jamais en jeu réel).
  - Après un wipe, un nouveau `dc on` dans la même instance ouvre une nouvelle ligne, dont `bossesKilled` repart de là. Le dashboard regroupe les lignes d'une même `instance` en un seul run : boss, wipes et durées additionnés, premier départ, dernier résultat, « n dc on à la suite ».

Ce que montre la page :
- Tuiles : runs du jour, réels + simulés ; terminés et wipes, réels seulement ; boss tués, réels + simulés ; groupes en cours ; personnages en donjon, `everyone` + bots des runs simulés.
- Cartes : groupes réels en cours, donjons simulés en cours, par donjon, derniers runs réels, derniers runs simulés, champs de bataille simulés (en cours, bilan du jour, derniers), détail Dungeon Clear.
- Chaque source absente ou coupée dit quoi activer : `AiPlayerbot.CoaWorld.DungeonSim.Enable`, ou les fichiers du §14.
- Champs de bataille : BgSim reste coupé dans le pack (décision de l'user, 09/11). La carte montre les BG et arènes réels (zones de `everyone`, sinon zones des bots aléatoires) et une simple mention « BG simulés : coupés » ; le bloc simulé n'apparaît que si `bg_sim` existe.

## 16. Rattrapage d’XP et raid de capitale (12/11)
- **world.json `leveling`** (CoA SquidBot, CoaCatchUp) : `{catchUp, front, humans, surveyedAt, bots: [bots aléatoires par niveau, index 0 = niveau 1], hourly: [{at, front, humans, bots, p10, p50, p90}] (72 h au plus)}`. Le front est la médiane des joueurs actifs ; il vaut 0 quand le rattrapage est coupé ou qu’il y a trop peu de joueurs. Population affiche une carte « Rattrapage d’XP » : état et front, histogramme des bots par niveau (échelle racine, niveau au survol), p10/p50/p90 du moment, et une courbe horaire p10/p50/p90 avec le front en pointillé.
- **monde.json `capital_raid`** (CoA Monde) : null quand la brique est coupée, `{running: null}` sans raid en cours, sinon `{city, attackers, phase: gathering|assault, step, steps, bots, defenders, kingHealthPct, startedAt, assaultAt, endsAt}`. Vie du monde le montre dans « En ce moment » et sous la tuile Invasions. Ruées, invasions et raids sont lancés par un MJ par défaut : la page n’annonce jamais de « prochain ».

## 17. Royaumes secondaires (Squid World, clé living, 12/11)

- Le dashboard montre tout dossier `Royaumes\<clé>` du launcher, même d'un mode qu'il ne connaît pas : id et nom pris dans `realm.json`, ports dans `configs\worldserver.conf`, préfixe dans `configs\modules\playerbots.conf`, pid dans `.state.json`, bases `acore_characters_<clé>` et `acore_playerbots_<clé>`. Conventions confirmées par le Launcher sur un vrai Malfurion (id 5).
- `watch.json` et les fichiers du module sont lus dans `Royaumes\<clé>\Logs\squidbot\` : le launcher impose `AiPlayerbot.CoaDataDir` vide sur chaque royaume secondaire (launcher a794655).
- Royaume CoA arrêté et un seul autre en marche : la page ouvre celui-là, sauf si l'adresse donne `?realm=`.
- La clé `"realms"` de `dashboard.json` ne masque les royaumes secondaires que si elle vaut `false`. Absente ou `true`, ils sont montrés. Le launcher ne l'écrit jamais.

## 18. Fusion 3.0.0 (12/11)

- `feature/vivant-3.0` fusionnée dans `main` en local, `VERSION` 3.0.0, changelog 3.0.0. Ni tag ni push : ils attendent le go de l'user.
- Dans le paquet, le dépôt va dans `CoA-Bots\Tools\Dashboard`. Seuls les fichiers suivis par git sont livrés (`git archive`). Ce qui est propre au joueur n'est pas dans le dépôt et ne doit jamais être écrasé ni effacé : `dashboard.json`, `data\`, `history.json`, `xp-history.json`, `levels.json`, `kills.json`, `baseline.json`, `pvp.json`, `maps\`, `icons\`, `config-backups\`, `alerte-discord.txt`.
- Un `dashboard.json` existant (2.9.x) marche tel quel : les nouvelles clés (`squidbotDir`, `vivantDemo`) ont des défauts sûrs.

## 19. Économie : fonctions actives (3.0.1, 13/11)

- CoA Economy 6d432392 ajoute à `economy.json`, dans l'enveloppe à côté de `server_start`, `"features": {"market", "bot_auctions", "artisans", "craft_orders"}` (booléens).
- Le dashboard (f79704c, puis la lecture de l'enveloppe) n'affiche « il faut … » que pour une fonction à false. Pour une fonction à true dont la liste est vide, il affiche « rien sur les dernières 24 h ». Sans `features` (fichiers 3.0), le texte d'avant reste. `bot_auctions` n'est pas affiché.
