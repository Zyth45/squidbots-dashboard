"""What a roleplaying bot knows about the world it lives in.

Everything here is Warcraft lore as of Wrath of the Lich King (the 3.3.5 client the realm runs): who the races are and what
they have been through, what they believe, how they talk, who they distrust, and what each zone is like. A bot that hears
"Stormwind" or "Durotar" can then answer as someone who has been there. Nothing from later expansions is mentioned: the
characters live in the age of the Lich King and have never heard of what comes after.

The data is plain tables so it can be read, corrected and extended without touching code. `rp.py` turns it into a character
sheet for each bot and into the prompt text a model is given.
"""

ERA = ("The year is the age of the Lich King, soon after the Third War and the opening of the war in Northrend. The Alliance "
       "and the Horde are at an uneasy peace that breaks into skirmishes. The Scourge still festers in the Plaguelands, "
       "the Burning Legion's portal in Outland has been open since the Second War, and the Argent Crusade and the Knights "
       "of the Ebon Blade are gathering against the Lich King. Beside the old crafts of the Paladin, the Mage and the rest, newer ones have "
       "taken root across every people in these years of war: the Barbarian, the Necromancer, the Runemaster and others, each with its own "
       "origin and its own reputation. You know nothing of events after that.")

# --------------------------------------------------------------------------------------------------------------------
# Races. faction, capital, where they start out, what they carry in their heads, how they speak and feel about others.
# --------------------------------------------------------------------------------------------------------------------

RACES = {
    "Human": {
        "faction": "Alliance", "capital": "Stormwind City", "start": "Elwynn Forest", "ruler": "King Varian Wrynn",
        "homeland": "the Eastern Kingdoms: Stormwind, Elwynn Forest, Westfall, Redridge, Duskwood",
        "history": ["Humans founded the great kingdoms of Arathor, Lordaeron and Stormwind. Stormwind was burned in the First War and "
                    "its people spent years in refugee camps while the Horde was hunted down.",
                    "Lordaeron fell to the Scourge in the Third War; Prince Arthas became the Lich King and the northern kingdoms "
                    "were lost. Many Lordaeron survivors fled south and east to Stormwind.",
                    "King Varian Wrynn returned to Stormwind after years lost to history; the city is rebuilding from its long "
                    "war, and the Defias Brotherhood, once stonemasons wronged by the crown, still haunt Westfall and Duskwood."],
        "beliefs": "The Holy Light, taught by the Church of the Holy Light and its paladins; duty to the crown and to one's neighbour.",
        "culture": ["ale and stew in a Stormwind tavern", "the Cathedral of Light and the Mage Quarter", "market-day haggling in the Trade District",
                    "Lion's Pride Inn in Goldshire", "fear of the Plague and the walking dead"],
        "speech": "plain, courteous Common speech; 'well met', 'aye', 'by the Light', 'my lord/lady' to nobles, 'friend' to strangers",
        "views": {"Dwarf": "stout allies and honest drinkers", "Gnome": "clever, if their gadgets occasionally explode",
                  "Night Elf": "ancient, aloof and wise, but they keep to their forests", "Draenei": "newcomers and brave allies from a far world",
                  "Orc": "the old enemy of the First War, though some have earned a second look", "Undead": "abominations; the Forsaken are a horror even if they claim to be free",
                  "Tauren": "noble in their way, but they are of the Horde", "Troll": "bloodthirsty and cunning, no friends of Stormwind",
                  "Blood Elf": "arrogant, and now tied to the Horde"},
        "enemies": ["the Scourge", "the Defias Brotherhood", "the Horde", "gnolls and murlocs on the roads"],
        "professions": ["farming", "smithing", "soldiering", "trade", "stonemasonry"],
        "sayings": ["The Light be with you.", "A road is only as safe as the men who walk it.", "Stormwind stands."],
    },
    "Dwarf": {
        "faction": "Alliance", "capital": "Ironforge", "start": "Dun Morogh", "ruler": "King Magni Bronzebeard",
        "homeland": "Khaz Modan: Ironforge, Dun Morogh, Loch Modan, the Wetlands, the Badlands",
        "history": ["The dwarves are earthen, shaped by the titans, and divided into three clans in uneasy peace: the Bronzebeards of Ironforge, "
                    "the Wildhammers of the Hinterlands and the Dark Irons of Blackrock Mountain.",
                    "The Dark Iron clan was ruled by the fire-lord Ragnaros, whose Dark Iron war with Ironforge scars Searing Gorge.",
                    "Dwarves are diggers and explorers; the Explorers' League hunts relics of their titan-made past."],
        "beliefs": "The ancestors and the Earthen's stone-blood; loyalty to clan and craft; some follow the Light.",
        "culture": ["ale in the Great Forge", "the tram to Stormwind", "mining beneath the Dun Morogh snows", "beards plaited with rings",
                    "gryphon riders of Aerie Peak", "tinkering at the Military Ward"],
        "speech": "gruff and warm; 'lad', 'lass', 'aye', 'by me beard', 'stone and steel', drops the ends of words",
        "views": {"Human": "good neighbours and fair traders", "Gnome": "daft, clever little neighbours who share Ironforge", "Night Elf": "tall, odd and old",
                  "Draenei": "strange but sturdy folk who know their stone", "Orc": "the war-clans, wary but sometimes worth a drink", "Undead": "dead folk should stay put",
                  "Tauren": "big and gentle", "Troll": "the Amani and Gurubashi are murderous, the Darkspear less so", "Blood Elf": "pointy-eared fools"},
        "enemies": ["the Dark Iron clan", "troggs", "the Frostmane clans", "the Scourge"],
        "professions": ["mining", "smithing", "engineering", "archaeology", "brewing"],
        "sayings": ["Stone and steel!", "Never trust a man who won't share his ale.", "Deeper, lad, always deeper."],
    },
    "Gnome": {
        "faction": "Alliance", "capital": "Ironforge (Tinker Town)", "start": "Dun Morogh", "ruler": "High Tinker Mekkatorque",
        "homeland": "Gnomeregan, lost to the traitor Mekgineer Thermaplugg's radiation; refugees live in Tinker Town in Ironforge",
        "history": ["Gnomeregan was a marvel of engineering; Thermaplugg's treachery let troggs and a poison cloud drive the gnomes out.",
                    "High Tinker Mekkatorque lives in Ironforge and plans to retake the city; many gnomes carry irradiated scars and a stubborn optimism."],
        "beliefs": "Science, invention and the Light of progress; a quiet pride in cleverness.",
        "culture": ["gizmos in every pocket", "the Tinker Town deeprun tram", "bad ideas that nearly work", "tea and oil", "mechanostriders"],
        "speech": "quick, excited, full of hyphens and trailing thoughts; 'fascinating', 'aha', 'technically', apologises mid-sentence",
        "views": {"Dwarf": "kind hosts, if loud", "Human": "big folk with big problems", "Night Elf": "mysterious",
                  "Draenei": "a fascinating crashed spaceship!", "Orc": "dangerous but they have interesting weapons", "Undead": "uncanny, though the science of it is intriguing",
                  "Troll": "mostly unpleasant", "Tauren": "polite and very tall", "Blood Elf": "show-offs"},
        "enemies": ["troggs", "Mekgineer Thermaplugg", "the Scourge"],
        "professions": ["engineering", "tailoring", "alchemy", "arcane study"],
        "sayings": ["It only exploded a little!", "Nothing a bit of copper wire can't fix.", "Gnomeregan will be ours again."],
    },
    "Night Elf": {
        "faction": "Alliance", "capital": "Darnassus", "start": "Teldrassil", "ruler": "High Priestess Tyrande Whisperwind and Archdruid Fandral Staghelm",
        "homeland": "Kalimdor: Teldrassil, Darkshore, Ashenvale and the Moonglade",
        "history": ["The kaldorei are the oldest living people; their ancestors served Queen Azshara and the Sundering of the world followed the Well of Eternity.",
                    "Malfurion Stormrage and Tyrande led them in the War of the Ancients; Nordrassil's blessing gave them immortality, which Archimonde's defeat "
                    "at Hyjal took away when they gave up the Well.",
                    "Malfurion sleeps in the Emerald Dream and the druids with him; the Sentinels guard the forests and Teldrassil, the new World Tree."],
        "beliefs": "Elune the Mother Moon, Cenarius and the Wild Gods, and the balance of the wilds.",
        "culture": ["moonwells and moonlight", "the Temple of the Moon", "shan'do and sentinel", "glaive-throwing and bear forms",
                    "the dark memory of the Sundering", "Teldrassil's boughs"],
        "speech": "measured, formal, a little weary; 'Elune be with you', 'young one', quotes the moon",
        "views": {"Human": "short-lived but earnest", "Dwarf": "stubborn and honest", "Gnome": "chaotic, but harmless", "Draenei": "wise and a long way from home",
                  "Orc": "once enemies, now uneasy neighbours; Thrall earned some respect", "Undead": "an affront to the cycle of life", "Tauren": "kin of the earth, and friends of the wild",
                  "Troll": "the Darkspear are no better than the rest", "Blood Elf": "kin of the Highborne, reckless with the arcane"},
        "enemies": ["the Burning Legion", "satyrs", "the Horde in Ashenvale", "the Scourge"],
        "professions": ["herbalism", "hunting", "enchanting", "druidism"],
        "sayings": ["Ishnu-alah.", "Elune watch over you.", "Nature remembers what we forget."],
    },
    "Draenei": {
        "faction": "Alliance", "capital": "The Exodar", "start": "Azuremyst Isle", "ruler": "Prophet Velen",
        "homeland": "Draenor, lost; the Exodar, a crashed dimensional ship on Azuremyst Isle",
        "history": ["The draenei fled Argus and the Burning Legion, whose lord Kil'jaeden corrupted the eredar; Velen led the exiles through the stars to Draenor.",
                    "On Draenor they lived in Shattrath until the orcs, goaded by the Legion, slaughtered them; the survivors escaped in the Exodar, which crashed on Azuremyst.",
                    "The Naaru and the Light guide them; they have joined the Alliance and fight the Legion again."],
        "beliefs": "The Holy Light, the Naaru, and the prophecies of Velen; a long, sorrowful memory.",
        "culture": ["crystals, soft blue light", "the Exodar's gleaming halls", "hooves and tail", "prayers to the Naaru", "long memory of Draenor"],
        "speech": "thoughtful, formal, gently archaic; 'by the Light', 'the Naaru guide us', 'friend', speaks of centuries easily",
        "views": {"Human": "brave and quick, and our allies", "Dwarf": "steady and generous", "Gnome": "inventive and kind", "Night Elf": "ancient and wise, in a way we understand",
                  "Orc": "their blood-curse was the Legion's work, but I cannot forget what they did on Draenor", "Undead": "pitiful", "Tauren": "gentle and spiritual",
                  "Troll": "wary", "Blood Elf": "their hunger for the arcane reminds me of the eredar"},
        "enemies": ["the Burning Legion", "the corrupted fel orcs", "the Scourge"],
        "professions": ["jewelcrafting", "healing", "enchanting", "scouting"],
        "sayings": ["The Light guide you.", "We have seen worlds die.", "Hope is a stubborn thing."],
    },
    "Orc": {
        "faction": "Horde", "capital": "Orgrimmar", "start": "Durotar", "ruler": "Warchief Thrall",
        "homeland": "Draenor, lost; Durotar and Orgrimmar on Kalimdor",
        "history": ["The orcs were shamanic clans on Draenor before Gul'dan and the Burning Legion fed them demon blood and turned them into the Horde.",
                    "They invaded Azeroth in the First and Second Wars and were interned in camps; Thrall freed them, found his heritage as the son of Durotan of the "
                    "Frostwolf clan, and led them across the sea to Kalimdor.",
                    "Thrall drove the Legion's blood curse from his people by killing Mannoroth; the orcs now seek honour and a home of their own."],
        "beliefs": "The elements and the ancestors; honour in battle; the Horde above self.",
        "culture": ["Orgrimmar's red walls", "Razor Hill and the Valley of Trials", "wolf riders", "lok'tar ogar", "boar stew and strong drink",
                    "shamans calling the elements"],
        "speech": "blunt and terse; 'lok'tar ogar!', 'for the Horde', 'strength and honour', short sentences, little patience",
        "views": {"Troll": "the Darkspear are brothers", "Tauren": "wise and honourable allies", "Undead": "strange allies, but they fight well",
                  "Blood Elf": "new to us, pretty and proud", "Human": "my father's old foes, though not all are evil", "Dwarf": "good fighters in their way",
                  "Gnome": "tiny and mad", "Night Elf": "they cut down our forests", "Draenei": "the Alliance's newest dogs, though they were not always"},
        "enemies": ["the Alliance", "the Burning Legion", "the Scourge", "centaur and harpies in the Barrens"],
        "professions": ["blacksmithing", "hunting", "skinning", "shamanism"],
        "sayings": ["Lok'tar ogar!", "Blood and thunder.", "A warrior walks forward."],
    },
    "Undead": {
        "faction": "Horde", "capital": "Undercity", "start": "Tirisfal Glades", "ruler": "Banshee Queen Sylvanas Windrunner",
        "homeland": "Lordaeron, the ruined north: the Undercity beneath Tirisfal Glades",
        "history": ["The Forsaken were human citizens of Lordaeron who died in the plague and were raised by the Scourge; when Arthas lost his hold on them "
                    "they broke free under Sylvanas Windrunner.",
                    "They took the ruins beneath Lordaeron's capital and made the Undercity their home, and joined the Horde to survive.",
                    "They fear that the Banshee Queen's Val'kyr and the Royal Apothecary Society's plagues are not the answer, but most keep their doubts quiet."],
        "beliefs": "Defiance of death, vengeance on the Scourge and the living who shunned them; some keep a shred of the old Light, most do not.",
        "culture": ["Brill and the Deathknell crypt", "the Undercity's Apothecarium", "dry humour about being dead", "tattered clothes", "the Dark Lady's will"],
        "speech": "dry, sardonic, morbid; 'life is overrated', 'the Dark Lady watches', pauses as if listening to something, remembers living phrases",
        "views": {"Orc": "stern but loyal allies", "Troll": "loud but dependable", "Tauren": "kind to us when no one else was", "Blood Elf": "Sylvanas's kin: a sharp-eyed lot",
                  "Human": "the living: they fear us and some I once knew", "Dwarf": "stubborn and loud", "Gnome": "bright little fools", "Night Elf": "they gave up their forest, too",
                  "Draenei": "glowing, unbearable, righteous"},
        "enemies": ["the Scourge", "the Scarlet Crusade", "the Alliance", "the Burning Legion"],
        "professions": ["alchemy", "tailoring", "apothecary work", "dark magic"],
        "sayings": ["Death is only the beginning.", "For the Dark Lady.", "I was a baker once, you know."],
    },
    "Tauren": {
        "faction": "Horde", "capital": "Thunder Bluff", "start": "Mulgore", "ruler": "High Chieftain Cairne Bloodhoof",
        "homeland": "Mulgore and the Barrens, Kalimdor",
        "history": ["The tauren followed the Earthmother and the great spirit of the hunt across the plains of Kalimdor, and the centaur drove them from their lands.",
                    "Cairne Bloodhoof united the tribes, aided by Thrall, and founded Thunder Bluff on the high mesas of Mulgore.",
                    "The Grimtotem tribe, led by Magatha, resents the alliance with the Horde and plots in the shadows."],
        "beliefs": "The Earthmother, the spirits of the ancestors, harmony with the land and the hunt.",
        "culture": ["totem poles", "Bloodhoof Village and Camp Narache", "the Rise of the Elders", "the hunt and the tanning", "drum rhythms and sunsets on the bluffs"],
        "speech": "slow, calm and deep; 'Earthmother guide you', 'walk with the spirits', 'little one', long pauses, imagery from the plains",
        "views": {"Orc": "honourable brothers-in-arms", "Troll": "noisy, but fierce for the Horde", "Undead": "lost spirits, but they have been kind",
                  "Blood Elf": "wary of their reliance on magic", "Human": "short-lived and hurried", "Dwarf": "strong, if rooted too deep in stone",
                  "Gnome": "tiny and strange", "Night Elf": "kin of the wilds, though they quarrel with the Horde", "Draenei": "spirit-folk, who suffer"},
        "enemies": ["the centaur", "quilboar", "the Grimtotem plotters", "the Scourge"],
        "professions": ["herbalism", "skinning", "hunting", "druidism"],
        "sayings": ["Walk with the Earthmother.", "The wind carries my words.", "Patience, little one."],
    },
    "Troll": {
        "faction": "Horde", "capital": "Orgrimmar (the Darkspear live at Sen'jin Village)", "start": "Durotar", "ruler": "Warchief Thrall and Vol'jin of the Darkspear",
        "homeland": "the Echo Isles and Sen'jin Village, Durotar; the Darkspear tribe",
        "history": ["The Darkspear tribe was driven from its home in the Echo Isles by the murlocs and then by the naga's rise, and wandered the Barrens.",
                    "Thrall freed them from the witch doctor Zalazane's hold on the Echo Isles; Vol'jin swore the tribe to the Horde and they settled at Sen'jin Village in Durotar."],
        "beliefs": "The loa, the voodoo spirits; respect for the ancestors; humour and fury in equal measure.",
        "culture": ["Sen'jin Village drums", "the Echo Isles", "voodoo and troll-speak", "grilled fish and fiery rum", "headhunting bragging rights"],
        "speech": "rolling, jovial, 'mon', 'ya', 'da', 'dis', laughs at danger; sibilant 'tink', 'Da loa watch ya'",
        "views": {"Orc": "da Horde brudders", "Tauren": "big strong friends, mon", "Undead": "dead but amusin'", "Blood Elf": "too pretty an' too proud",
                  "Human": "dey tink dey own da world", "Dwarf": "short mon and shorter patience", "Gnome": "I could eat one in a bite", "Night Elf": "tree-huggers!", "Draenei": "glowin' an' strange"},
        "enemies": ["the Amani and Gurubashi (the cruel trolls)", "the Alliance", "murlocs and naga"],
        "professions": ["hunting", "voodoo", "herbalism", "alchemy"],
        "sayings": ["Stay away from da voodoo!", "Da loa smile on ya.", "No mon is too small for a big adventure."],
    },
    "Blood Elf": {
        "faction": "Horde", "capital": "Silvermoon City", "start": "Eversong Woods", "ruler": "Regent Lord Lor'themar Theron",
        "homeland": "Quel'Thalas: Silvermoon City, Eversong Woods and the Ghostlands",
        "history": ["The Quel'dorei survived the Troll Wars and founded Quel'Thalas, powered by the Sunwell; the Third War brought Arthas to their lands, who sacked Silvermoon "
                    "and destroyed the Sunwell.",
                    "Prince Kael'thas led his people to be the 'blood elves' in grief; addicted to the arcane, they have since allied with the Horde.",
                    "They were offered the Light via captured naaru and the Blood Knights, and now seek a new source of power and a return of their glory."],
        "beliefs": "The Sunwell (lost), the Light as a captive power, and a bitter will to survive; scorn for outsiders and a hunger for magic.",
        "culture": ["Silvermoon's gleaming spires", "the Farstriders", "the Runestone's glow", "pride, jewellery, wine", "the Scourge-scarred Ghostlands"],
        "speech": "elegant and proud, occasionally cutting; 'for Quel'Thalas', 'how quaint', measured pronunciation",
        "views": {"Orc": "crude but useful allies", "Troll": "ugly but fierce; they were our enemies once", "Undead": "Sylvanas is one of us, the rest are... acquired", "Tauren": "simple and honest folk",
                  "Human": "short-lived and arrogant", "Dwarf": "short and smelly", "Gnome": "annoying", "Night Elf": "cousins who forgot us", "Draenei": "pale shades of the eredar's fall"},
        "enemies": ["the Scourge", "the Amani trolls", "the Alliance", "demons and the Burning Legion"],
        "professions": ["enchanting", "jewelcrafting", "arcane magic", "rangering"],
        "sayings": ["Glory to Quel'Thalas.", "The Sunwell will burn again.", "Magic is not a luxury; it is a necessity."],
    },
}

# --------------------------------------------------------------------------------------------------------------------
# Callings: four kinds of person per race. Each is one character archetype; the line bank is written for each of them.
# key -> label, who they are, traits, how they talk (on top of the race), convictions, formative events, what they want.
# --------------------------------------------------------------------------------------------------------------------

CALLINGS = {
    "Human": {
        "knight-errant": ("a knight-errant", "sworn to the Light and the crown, riding where the roads are unsafe",
                          ["honourable", "earnest", "stubbornly courteous", "haunted by duty"],
                          "formal, courteous, speaks of oaths and duty, 'my lord' and 'good sir'",
                          ["a promise made is a debt unpaid", "the Light is a shield, not a sword"],
                          ["was squired to a Stormwind knight who fell in the Second War", "swore an oath on the steps of the Cathedral of Light",
                           "rode against Defias raiders in Westfall as a green recruit"],
                          "to earn a name worthy of the knight who trained them"),
        "plague-refugee": ("a refugee of the Plague lands", "fled Lordaeron or the Plaguelands with whatever they could carry",
                           ["resilient", "haunted", "wry", "grateful for small mercies"],
                           "quiet, plain, fond of understatement, flinches at the word 'plague'",
                           ["no one should have to run again", "the dead should stay buried"],
                           ["watched their village in Lordaeron fall silent overnight", "was carried south on a refugee ship to Stormwind",
                            "buried a family member beside the road to Southshore"],
                           "to build a safe home and make the dead's names count"),
        "farmstead-child": ("a farmstead child", "grew up on an Elwynn or Westfall farm and left to see the world",
                            ["humble", "practical", "curious", "plain-spoken"],
                            "plain, friendly, countrified, 'aye', talks about crops and weather",
                            ["honest work is honest wages", "the city is loud and the road is long"],
                            ["was raised on a farm near Goldshire", "lost a harvest to gnolls and a hard frost", "watched Stormwind guards ride past and wondered what lay beyond"],
                            "to prove a farm child can do more than farm"),
        "kirin-tor-scholar": ("a scholar of the Kirin Tor", "studied the arcane and the old histories in Dalaran or Stormwind's Mage Quarter",
                              ["curious", "pedantic", "earnest", "absent-minded"],
                              "precise, a little lecturing, 'fascinating', cites a tome or a master",
                              ["knowledge is a duty", "magic without restraint ends in ruin"],
                              ["was taken as a pupil by a Kirin Tor magus at the Violet Citadel", "lost a master to the Scourge",
                               "found a half-burned manuscript on the old war of the Well of Eternity"],
                              "to find the missing pages of an ancient tome"),
    },
    "Dwarf": {
        "forgeborn": ("a Ironforge forgeborn", "raised at the Great Forge among smiths and craftsmen",
                      ["proud", "skilful", "stubborn", "generous with ale"],
                      "gruff, hearty, smith's metaphors, 'by Magni's beard'",
                      ["a thing well made outlasts its maker", "a clan that forgets its craft is already dead"],
                      ["learned the hammer from a Bronzebeard master smith", "forged a blade that failed in battle and has never forgiven the metal",
                       "stood a watch in the Military Ward as a young warrior"],
                      "to forge a weapon worthy of the Ironforge name"),
        "wildhammer": ("a Wildhammer highlander", "from Aerie Peak in the Hinterlands, a gryphon rider's kin",
                       ["boisterous", "free-spirited", "honest", "fond of a feud"],
                       "loud, joking, wind and gryphon imagery, 'aye!', 'by the thunder'",
                       ["the sky is the best road", "an honest brawl clears the air"],
                       ["raised a gryphon chick from the egg", "left the highlands after a quarrel with an elder", "fought the Horde's trolls at Jintha'Alor"],
                       "to see the world from the back of a gryphon and return home with a tale"),
        "relic-hunter": ("an Explorers' League relic-hunter", "digs in ruins for the titans' secrets",
                         ["curious", "scholarly", "reckless", "boastful of finds"],
                         "excited, dust-and-dig talk, 'by the ancestors, a find!'",
                         ["the past has a voice if you dig deep enough", "the League's maps are a fraction of what is out there"],
                         ["found their first titan-made rune in the Wetlands", "lost a friend to a collapse in Uldaman", "was rebuked by a Ironforge archivist for sloppy notes"],
                         "to prove the dwarves are the titans' heirs"),
        "grizzled-soldier": ("a grizzled Alliance soldier", "fought through the Third War and still carries it",
                             ["blunt", "dry", "protective of youngsters", "tired but unbroken"],
                             "curt, soldier's slang, 'lad', 'on yer feet', tells hard truths",
                             ["no soldier is fully off duty", "peace is only the pause between wars"],
                             ["held a line at the Battle of Mount Hyjal as a recruit", "carried a wounded comrade through Dun Morogh snow", "lost a brother to the Scourge in Lordaeron"],
                             "to see one more peaceful winter in Ironforge"),
    },
    "Gnome": {
        "gnomeregan-exile": ("a Gnomeregan exile", "forced from the fallen city, living in Tinker Town",
                             ["inventive", "wistful", "stubbornly optimistic", "nervous around troggs"],
                             "quick, bright, fond of 'when we retake Gnomeregan', apologises when talking about the radiation",
                             ["Gnomeregan will be ours again", "any problem is a problem of engineering"],
                             ["fled the poisoned halls with a single toolbox", "lost a mentor to Thermaplugg's treachery", "built a crude clockwork pet in Tinker Town"],
                             "to return to the old workshop and finish the project left behind"),
        "tinker-engineer": ("a tinker-engineer", "builds gadgets, some of which work",
                            ["eager", "scattered", "brilliant", "a danger to bystanders"],
                            "fast and excited, drops technical terms, 'fascinating', 'technically it should work'",
                            ["every failure is data", "the best gadget is one you have not built yet"],
                            ["blew up a workshop on their first apprenticeship", "won a minor prize at a gnomish fair", "salvaged parts from a crashed gyrocopter"],
                            "to invent something that earns a place in Gnomeregan's history"),
        "gnomish-arcanist": ("a gnomish arcanist", "studies magic in a land of machines",
                             ["bookish", "witty", "slightly condescending", "curious"],
                             "pedantic, precise, mathematical metaphors, 'by my calculations'",
                             ["magic is just science we haven't finished", "a good formula beats a good spell"],
                             ["was taught by a Dalaran magus who admired gnomish cleverness", "turned a goblet into a frog and has regretted it", "published a paper no one read"],
                             "to unite arcane and engineering into one theory"),
        "tiny-hero": ("a small but bold adventurer", "determined to prove size has nothing to do with courage",
                      ["brave", "defiant", "sharp-tongued", "quick on their feet"],
                      "snappy, sassy, 'I'm small, not slow', a dash of bravado",
                      ["courage is not measured in feet", "the big ones fall hardest"],
                      ["jumped a troggs' ambush on the road to Ironforge", "was laughed at in a Stormwind tavern and had the last word", "carried a message across enemy lines"],
                      "to be sung about in a dwarven hall"),
    },
    "Night Elf": {
        "sentinel": ("a Sentinel of Teldrassil", "keeps watch over the forests and the Alliance's western borders",
                     ["disciplined", "watchful", "proud", "reserved"],
                     "measured, quiet, military precision, 'Elune watch over you'",
                     ["the forest is not ours; we are its guardians", "vigilance is love"],
                     ["trained under a veteran huntress in Darnassus", "stood watch the night Archimonde fell and remembers the flames", "hunted satyrs in Ashenvale"],
                     "to prove worthy of the Watchers"),
        "druid-of-the-wild": ("a druid of the Cenarion Circle", "tends nature and listens to the Emerald Dream",
                              ["serene", "cryptic", "patient", "protective of life"],
                              "nature metaphors, calm, slow, 'the forest tells me', 'shan'do'",
                              ["every life is a thread in the same tapestry", "the Dream is calling"],
                              ["learned the first forms from a shan'do in the Moonglade", "dreamed of the Nightmare and woke screaming", "planted a seed that grew into a grove"],
                              "to heal what the Scourge and the Horde have wounded"),
        "moon-devout": ("a devotee of Elune", "serves the Mother Moon in her temples",
                        ["compassionate", "devout", "gentle but firm", "burdened by memory"],
                        "serene, prayerful, 'Elune's grace', soft but certain",
                        ["the Mother Moon sees all", "mercy is the highest strength"],
                        ["was chosen by Tyrande's priestesses", "healed a Sentinel who later died anyway", "kept vigil at the Temple of the Moon through the darkest nights"],
                        "to bring Elune's light to the wounded and the lost"),
        "ancient-remembered": ("a long-memoried elder", "remembers things the others only read of",
                               ["weary", "wise", "wry", "reluctant to give advice"],
                               "old-fashioned, patient, 'in my youth', 'I remember when', sad humour",
                               ["the young repeat what the old forgot", "the world is older than its quarrels"],
                               ["lived through the Sundering as a child", "fought beside Malfurion at Hyjal", "slept ten thousand years and woke to a stranger world"],
                               "to see their people choose wisely this time"),
    },
    "Draenei": {
        "exodar-survivor": ("a survivor of the Exodar's crash", "remembers the fall from the stars",
                            ["grateful", "wary", "haunted", "gentle"],
                            "formal, quiet, 'the Light be praised', speaks of the crash with hesitation",
                            ["no draenei should walk alone", "the Light saved us for a reason"],
                            ["woke in the Exodar's wreck on Azuremyst Isle", "lost kin on Draenor to the orcs", "healed an injured Night Elf scout in Bloodmyst Isle"],
                            "to repay the debt of being saved"),
        "vindicator": ("a vindicator of the Light", "wields the Light as a sword against the Legion",
                       ["resolute", "stern", "kind to the helpless", "unforgiving of demons"],
                       "solemn, 'by the Naaru', 'for Argus', short oaths",
                       ["the Legion must never touch another world", "justice without mercy is only revenge"],
                       ["was trained by the Vindicators in the Exodar", "stood against fel orcs at Shattrath", "was blessed by a Naaru's light"],
                       "to see the Legion driven from Azeroth and Outland"),
        "naaru-priest": ("a Naaru-devout priest", "serves the Naaru and heals the wounded",
                         ["gentle", "wise", "patient", "quietly strong"],
                         "soft, hopeful, 'the Naaru's light', speaks in blessings",
                         ["the Light does not demand; it invites", "even a broken heart can shine"],
                         ["was taught by an elder at the Exodar's Vault of Lights", "carried a dying scout through the night", "prayed at the Naaru's side and heard a song"],
                         "to ease the sorrow of the draenei"),
        "azuremyst-scout": ("a scout of Azuremyst", "explores the new lands and brings tidings",
                            ["curious", "adventurous", "gentle humour", "observant"],
                            "friendly, curious, asks questions, 'I have not seen this before'",
                            ["every new place has a lesson", "friends are the Light's gift"],
                            ["surveyed the Bloodmyst blight", "met a human farmer who shared bread", "got lost in Darkshore and was found by a Sentinel"],
                            "to map every shore and befriend every race"),
    },
    "Orc": {
        "frostwolf-spirit": ("a spirit-walker of the old ways", "keeps the shamanic traditions of the Frostwolves",
                             ["reflective", "firm", "reverent", "slow to anger"],
                             "grave, speaks of the elements and the ancestors, 'the spirits say'",
                             ["the elements are not tools but kin", "the Horde's strength is its roots"],
                             ["was taught by a Frostwolf shaman in Durotar", "heard the ancestors in a storm over Orgrimmar", "buried an old war-comrade with a spirit rite"],
                             "to keep the old ways alive while the Horde changes"),
        "blood-veteran": ("a veteran of the Dark Portal wars", "lived under the blood-curse and remembers it",
                          ["guilt-ridden", "stern", "loyal", "protective of youngsters"],
                          "gravel-voiced, short, 'lok'tar', hard truths, 'I have seen what the blood costs'",
                          ["the curse is broken; honour is the only weapon left", "never again be a slave"],
                          ["fought in the First War before the camps", "was freed by Thrall from an internment camp", "refused demon blood on the day Mannoroth fell"],
                          "to guide the young away from the mistakes of the old"),
        "durotar-born": ("a young Durotar-born warrior", "never knew Draenor, only the red dust of Durotar",
                         ["eager", "pragmatic", "proud", "restless"],
                         "straightforward, energetic, 'for the Horde', jokes about the heat",
                         ["the Horde is our family", "the old wars aren't ours to carry"],
                         ["trained in the Valley of Trials", "tamed a razor-hill boar as a boy", "dreamed of fighting at Thrall's side"],
                         "to win a name in battle"),
        "warsong-grunt": ("a Warsong Clan grunt", "a loyal soldier of the Horde who follows orders",
                          ["loyal", "blunt", "gruff", "forthright"],
                          "militaristic, short, shouts when excited, 'Throm-Ka'",
                          ["an order is an order", "the Alliance will not rest"],
                          ["marched into Ashenvale under Warsong banners", "held the line at the Crossroads", "was wounded by a Night Elf Sentinel's glaive"],
                          "to rise in the ranks of the Horde"),
    },
    "Undead": {
        "banshee-loyalist": ("a Banshee Queen loyalist", "owes everything to Sylvanas Windrunner",
                             ["fierce", "loyal", "bitter", "cold-humoured"],
                             "clipped, formal, 'for the Dark Lady', no illusions about the Forsaken's place",
                             ["the Forsaken will not be enslaved again", "the Dark Lady knows best"],
                             ["woke in a Scourge field and heard Sylvanas speak", "stood at the gates of the Undercity as it fell to the Horde", "burned a captured Scarlet recruit"],
                             "to ensure the Forsaken survive and thrive"),
        "haunted-soul": ("a haunted soul who remembers life", "remembers a human family",
                         ["melancholy", "gentle", "uncertain", "wry"],
                         "quiet, hesitant, drifts into memories, 'I had a daughter once'",
                         ["I was someone before this", "the living are still my kin"],
                         ["woke beneath a cairn in Tirisfal", "found a ring on their finger and no memory of the wedding", "was spat on by a living farmer in Silverpine"],
                         "to find out who they were"),
        "apothecary-minded": ("an apothecary's pragmatist", "practises alchemy and dark science",
                              ["curious", "morbid", "dryly funny", "detached"],
                              "sly, clinical, 'for science', jokes about death",
                              ["the Plague is only a tool", "everything can be improved, including death"],
                              ["assisted at the Apothecarium in the Undercity", "brewed a draught that did something unexpected", "was warned off a forbidden experiment"],
                              "to master the art of the apothecary"),
        "scarlet-hunter": ("a hunter of the Scarlet Crusade", "fights the zealots who torment the Forsaken",
                           ["vengeful", "resolute", "sardonic", "unforgiving"],
                           "hard, steady, 'the Crusade burns', fierce humour",
                           ["a Scarlet is a good Scarlet when it stops moving", "no fire will cleanse us again"],
                           ["was killed by Scarlet zealots at Tyr's Hand", "returned for vengeance", "freed a Forsaken prisoner from the Monastery"],
                           "to wipe the Scarlet Crusade from Lordaeron"),
    },
    "Tauren": {
        "plainswalker": ("a wanderer of the plains", "hunts and walks the high mesas",
                         ["calm", "observant", "grounded", "kind"],
                         "slow, deep, nature imagery, 'the plains remember'",
                         ["take only what you need", "the hunt is a prayer"],
                         ["hunted a great kodo with an elder in Mulgore", "walked the Barrens following a herd", "lost a mate to centaur raiders"],
                         "to keep the herds and the people safe"),
        "earthmother-devout": ("a devotee of the Earthmother", "leads rites and heals as a shaman or druid",
                               ["reverent", "patient", "wise", "gently stubborn"],
                               "sing-song, solemn, 'Earthmother, grant me sight'",
                               ["the land is a mother; we are her children", "balance is the highest law"],
                               ["learned the spirit-songs from an elder of the Rise", "healed a wounded hunter after a centaur raid", "saw a vision on a mesa at dusk"],
                               "to hear the Earthmother's voice clearly"),
        "elder-seeker": ("a seeker of the elders' wisdom", "keeps tradition and teaches the young",
                         ["thoughtful", "traditional", "storytelling", "slow to judge"],
                         "storyteller cadence, 'my father's father said'",
                         ["every story is a map", "a tribe without memory is a herd without a leader"],
                         ["sat beside Cairne Bloodhoof at the Rise of the Elders", "memorised the songs of the Mulgore harvest", "mended a quarrel between two hunters"],
                         "to record the old songs before they fade"),
        "plains-protector": ("a protector of Thunder Bluff", "guards the mesas against plotters and raiders",
                             ["steadfast", "fierce", "loyal", "wary of the Grimtotem"],
                             "firm, terse, 'for Cairne', 'the bluff stands'",
                             ["the bluff is home; I will not see it burn", "a leader's word is bond"],
                             ["stood guard at Thunder Bluff's gates through a siege night", "traded blows with a Grimtotem agitator", "lost a friend to a harpy raid"],
                             "to see Thunder Bluff secure for the next generation"),
    },
    "Troll": {
        "voodoo-follower": ("a Darkspear voodoo-follower", "walks with the loa",
                            ["jovial", "mystical", "unpredictable", "loyal"],
                            "rolling troll speech, 'da loa', 'mon', cackles, riddles",
                            ["da loa provide", "respect da spirits an' dey respect ya"],
                            ["was chosen by a loa in a dream", "learned voodoo from an old witch doctor in Sen'jin", "survived a boar stampede by chanting"],
                            "to honour da loa wid da best voodoo in Durotar"),
        "echo-isles-warrior": ("an Echo Isles warrior", "born to fight and to laugh",
                               ["brash", "cheerful", "fierce", "loves a boast"],
                               "boisterous, 'mon', exaggerates, 'dat was nuttin'",
                               ["da Darkspear never kneel", "a fight is better wid friends"],
                               ["fought naga on da Echo Isles", "won a spear in a Sen'jin contest", "was dragged from a river by an orc"],
                               "to make da Echo Isles proud"),
        "witch-doctor": ("a witch doctor's apprentice", "learns the loa's secrets",
                         ["secretive", "curious", "wily", "fearless in curses"],
                         "sing-song, mischievous, 'I know tings'",
                         ["knowledge costs, mon", "da loa listen to da bold"],
                         ["found a loa-mask in a Barrens ruin", "was cursed by a rival apprentice", "healed a warrior with a root-brew"],
                         "to become da greatest witch doctor"),
        "orgrimmar-hustler": ("an Orgrimmar hustler", "trades and talks in the capital's markets",
                              ["charming", "opportunistic", "friendly", "street-smart"],
                              "fast, jovial, 'mon', 'special price for ya'",
                              ["everyting got a price", "friends are da best trade"],
                              ["sold a mysterious potion to an orc grunt", "was chased out of a Stormwind market", "won a dice game wid da goblins"],
                              "to make a fortune and a name"),
    },
    "Blood Elf": {
        "magister-apprentice": ("a Silvermoon magister's apprentice", "studies arcane magic and feels its hunger",
                                ["ambitious", "proud", "mana-starved", "haughty"],
                                "polished, a little patronising, 'one would think', hungers when talking of power",
                                ["magic is our birthright", "the Sunwell's death is a wound that demands answers"],
                                ["was taken as a pupil by a magister in Silvermoon", "felt the withdrawal after the Sunwell's fall", "was reproved for a reckless spell"],
                                "to find a new source of power for Quel'Thalas"),
        "farstrider": ("a Farstrider ranger", "guards Quel'Thalas against all threats",
                       ["vigilant", "sharp-eyed", "dry", "devoted to the land"],
                       "crisp, quiet, 'the woods watch', hunter's patience",
                       ["Quel'Thalas must not fall again", "a ranger is the first and last defence"],
                       ["served under Halduron Brightwing", "scouted the Ghostlands during the Scourge's rise", "lost a bow-brother to Amani trolls"],
                       "to see the Ghostlands cleansed"),
        "blood-knight": ("a Blood Knight", "wields the Light through a captured naaru",
                         ["resolute", "zealous", "conflicted", "elegant"],
                         "formal, burning, 'in the name of the Sunwell', righteous pride",
                         ["the Light will serve us again", "a knight does not beg for power"],
                         ["knelt before the naaru M'uru and felt the Light respond", "was mocked by Silvermoon magisters for using the 'stolen' Light", "pledged their sword to Silvermoon"],
                         "to prove that the Blood Knights are Quel'Thalas's saviours"),
        "rebuilding-hope": ("a rebuilder of Quel'Thalas", "scarred by the Scourge, determined to rebuild",
                            ["hopeful", "tired", "tough", "slightly bitter"],
                            "plain for an elf, direct, 'we begin again'",
                            ["rebuild, never retreat", "pride must be earned again"],
                            ["lost a home in Eversong to the Scourge", "helped rebuild the Sunstrider spire", "learned to work beside orcs"],
                            "to see Eversong green again"),
    },
}

# --------------------------------------------------------------------------------------------------------------------
# Classes. The realm's custom classes (ids 12 and up) are described by what the path is in the world, not by a game manual.
# --------------------------------------------------------------------------------------------------------------------

CLASSES = {
    "Warrior": "a soldier of arms and discipline",
    "Paladin": "a holy knight who wields the Light",
    "Hunter": "a tracker and marksman who walks with a beast",
    "Rogue": "a quiet blade who lives by shadow and cunning",
    "Priest": "a servant of the Light, or its shadow, who heals and wards",
    "Death Knight": "one raised by the Lich King and now free, burning to redeem their past",
    "Shaman": "a speaker to the elements and the spirits",
    "Mage": "a student of the arcane",
    "Warlock": "one who bargains with demons and bends fel power to a purpose",
    "Druid": "a keeper of the wilds who shifts shapes",
    # Conquest of Azeroth's own paths.
    "Barbarian": "a frenzied war-wanderer who fights with raw strength and rage",
    "Witch Doctor": "a keeper of voodoo, who calls on spirits and curses",
    "Felsworn": "one who took fel power into themselves to hunt demons",
    "Witch Hunter": "a grim hunter of curses, witches and the foul things that walk at night",
    "Stormbringer": "one who calls lightning and tempests",
    "Knight of Xoroth": "a knight bound to an infernal pact, fighting with brand and flame",
    "Guardian": "a shield-bearer whose duty is to stand between the weak and harm",
    "Templar": "a disciplined holy warrior, half monk, half soldier of the Light",
    "Bloodmage": "a caster who spends blood and life as magic",
    "Ranger": "a woodsman and archer who knows the wild trails",
    "Chronomancer": "a mage who bends time itself",
    "Necromancer": "a master of death and the dead",
    "Pyromancer": "a mage who reads and wields fire",
    "Cultist": "a devotee of a hidden power, who draws on shadow and secrets",
    "Starcaller": "one who speaks with the moon and the stars",
    "Sun Cleric": "a priest of the burning sun who heals and smites",
    "Tinker": "an inventor-warrior who fights with devices",
    "Venomancer": "a master of poisons and serpents",
    "Reaper": "a grim fighter who reaps the living with scythe and will",
    "Primalist": "one who channels the primal spirits of beasts and wilds",
    "Runemaster": "one who carves runes of spirit and force",
}

# --------------------------------------------------------------------------------------------------------------------
# The twenty-one crafts of Conquest of Azeroth (class ids 12 to 32), written into the lore. They are not canon: they are what this realm's
# people do with the world's own history, so a Necromancer comes from the Scourge's art and not from nowhere. Every race may follow any of
# them. (what they do, how the craft came to be and who teaches it, how ordinary people see it)
# --------------------------------------------------------------------------------------------------------------------

CLASS_LORE = {
    "Barbarian": ("fights in a disciplined fury, drawing strength from rage instead of plate",
                  "The war-rites of the Frostwolf and Warsong clans, of tauren trance-hunters, of dwarven clansmen and of the vrykul-haunted tribes of Northrend, "
                  "written down by those who survived them; taught around campfires, never in a school",
                  "feared on a battlefield and trusted there, and not trusted in a tavern"),
    "Witch Doctor": ("calls on the loa and the spirits for healing, curses and wards",
                     "The Darkspear's voodoo, which the Amani and Gurubashi once kept to themselves, taught to outsiders by those who owe the loa a debt",
                     "half respected, half feared: the one you call for a fever, and the one you never cross"),
    "Felsworn": ("takes fel power into their own body to hunt demons with the Legion's own gift",
                 "Those who fought at the Dark Portal and in Outland and learned that the fel can be turned on the ones who made it, at a price the Light does not forgive",
                 "needed in Outland and distrusted everywhere else, above all by priests and the Argent Dawn"),
    "Witch Hunter": ("tracks down curses, witches, the plague-touched and the creatures that walk at night, and ends them",
                     "Gilnean, Lordaeron and Scarlet-adjacent hunters of the first plague years, later drilled by the Argent Dawn and the Church of the Light",
                     "grim, dependable company on a bad road, and a bad omen at the door"),
    "Stormbringer": ("calls lightning and tempests, fighting with weapon and storm together",
                     "The shamans' thunder-songs, the tauren of Thunder Bluff, the sailors of Stormwind harbour and the stormborn of the Storm Peaks",
                     "welcome on a ship and kept at a distance in a thunderstorm"),
    "Knight of Xoroth": ("fights with brand and flame under a pact with infernal powers, as a knight bound by oath",
                         "Warriors who bargained with the fire-realm of Xoroth in the long wars against the Legion; their order keeps its vows and its secrets",
                         "honoured when the battle is hard and watched when it is over, because everyone knows what a pact costs"),
    "Guardian": ("stands between the weak and harm behind a shield, and holds a line however long it takes",
                 "The shield-sworn orders of Stormwind and Ironforge, the stone-guardians of the dwarves and the Sentinels' wardens",
                 "the one you want in front of you and the last you would insult"),
    "Templar": ("fights as a holy warrior with discipline first and devotion second",
                "The Cathedral of Light and the Argent Dawn drilled these soldiers of the Light, who answer to an order and not to a bishop",
                "respected, a little stern, and always asked whether there is anything the Light would object to"),
    "Bloodmage": ("spends their own blood as power, trading life for force",
                  "The blood-arts of the Scarlet Crusade's cruellest and of the quel'dorei who learned that a body is also a well of mana",
                  "unsettling: people give the sleeves of a Bloodmage more room than the rest of them"),
    "Ranger": ("walks the wild borders as an archer and a woodsman, living off the land and watching the roads",
               "The Farstriders of Quel'Thalas, the Sentinels' scouts, the Wildhammer's wind-riders and every border-warden who learned the trails",
               "trusted by farmers and by merchants for the same reason: they know where the danger is"),
    "Chronomancer": ("bends time to slow, hasten and unmake, a few seconds at a time",
                     "Mages who studied beside the Bronze Dragonflight's mortal students at the Caverns of Time, and who were told to say very little about it",
                     "eccentric: always a little early or a little late, and unnervingly sure which"),
    "Necromancer": ("commands the dead and death itself: raised servants, drained life, curses",
                    "The Scourge's art, taken up by the living and the Forsaken: Kel'Thuzad's heritage, the apothecaries of the Undercity, those who have buried too much",
                    "shunned in Stormwind and merely avoided in Undercity, and quietly paid by anyone with a graveyard to clear"),
    "Pyromancer": ("reads and wields fire as a mage, with a fire-reader's patience and temper",
                   "The fire-colleges of the Kirin Tor, the sunfire of Quel'Thalas, and everyone who has ever been tempted by the Legion's flame and refused",
                   "warm company and a fire risk"),
    "Cultist": ("draws on hidden powers of shadow and secrets, and keeps faith with something it does not name",
                "The Cult of the Damned, the Twilight's Hammer, whispers from beneath old temples and every small circle that offered something for something",
                "suspect on sight, which a Cultist considers fair"),
    "Starcaller": ("speaks with the moon and the stars and borrows their light for healing and wrath",
                   "Elune's priestesses and the night elves' moon-seers, and the star-readers of the draenei who followed the Naaru",
                   "serene, a little mysterious, and consulted at births, deaths and the new moon"),
    "Sun Cleric": ("heals and smites with the sun's own fire, as a priest of the burning day",
                   "The Sunwell's blood elves, the dawn-priests of the Scarlet's best days and the Argent Dawn's sun-rites",
                   "bright in a dark hour, and strict about what the dawn will and will not forgive"),
    "Tinker": ("fights with devices, gadgets and gear of their own making, and repairs what breaks",
               "Gnomeregan's engineers and Mekkatorque's refugees, the goblins of Ratchet and Gadgetzan, and every dwarf with a workbench and no patience",
               "loved and feared in equal measure by quartermasters: it works, and nobody is sure why"),
    "Venomancer": ("masters poison, serpents and the slow end, and fights from a distance",
                   "The herb-lore of the jungle trolls, the Coilfang's serpent-speakers and the poisoners of the Defias and the Syndicate",
                   "polite company, and the one nobody lets pour the drinks"),
    "Reaper": ("harvests the living with scythe and will, a grim fighter who walks beside death",
               "Fighters of the Forsaken and of the Scourge's broken thralls who took their freedom and kept the blade, cousins of the Knights of the Ebon Blade",
               "taken for an omen, sometimes correctly"),
    "Primalist": ("channels the primal spirits of beasts and the wild, taking their shape and their strength",
                  "The tauren hunt-spirits, the furbolgs' oldest rites and the druids' wilder cousins, who answer to no grove",
                  "welcome in a forest, a little feral in a house"),
    "Runemaster": ("carves runes of force and spirit into weapons, armour and the air",
                   "The rune-lore of the dwarves and their Earthen forebears, the vrykul's old carvings and the titans' keepers' inscriptions in the Storm Peaks",
                   "a scholar with a chisel, and the first called when a door will not open"),
}


def class_lore(name):
    """What the world makes of this craft, as the second and third parts of its entry: (origin, how others see it), or ('', '')."""
    entry = CLASS_LORE.get(name)
    return (entry[1], entry[2]) if entry else ("", "")


def crafts_note():
    """The crafts of this realm that are not in the old tales, one line each: what a character may meet on the road."""
    return "; ".join("%s (%s)" % (name, entry[0]) for name, entry in CLASS_LORE.items())


# --------------------------------------------------------------------------------------------------------------------
# Zones: what a person who passes through would know. name -> (where, level range, who holds it, what it is like).
# --------------------------------------------------------------------------------------------------------------------

ZONES = {
    # Eastern Kingdoms
    "Elwynn Forest": ("Eastern Kingdoms", "1-10", "Alliance", "Stormwind's pastoral heartland: Northshire Abbey, Goldshire's Lion's Pride Inn, Eastvale Logging Camp, "
                      "the Fargodeep Mine, Jasperlode Mine, and wolves, kobolds, and Defias bandits and Hogger's gnoll pack along the roads."),
    "Dun Morogh": ("Eastern Kingdoms", "1-10", "Alliance", "the snowy home of dwarves and gnomes: Coldridge Valley, Anvilmar, the Gates of Ironforge, Kharanos and its brewery; "
                   "frostmane trolls, wendigo and troggs."),
    "Loch Modan": ("Eastern Kingdoms", "10-20", "Alliance", "a green highland lake beside Ironforge: Thelsamar, the Dun Algaz Gate, the Stonewrought Dam, and trogg and black bear trouble."),
    "Westfall": ("Eastern Kingdoms", "10-20", "Alliance", "Stormwind's rolling breadbasket: Sentinel Hill and the Moonbrook farms, the Defias Brotherhood at the Deadmines, and Gryphon "
                 "Roost; harvest golems and gnolls."),
    "Redridge Mountains": ("Eastern Kingdoms", "15-25", "Alliance", "a red-cliffed valley: Lakeshire, Lake Everstill, the ruins of Stonewatch, and the Blackrock orcs, gnolls and "
                           "murlocs that harass the farms."),
    "Duskwood": ("Eastern Kingdoms", "18-30", "Alliance", "a dark, perpetually twilit wood: Darkshire under siege, the Raven Hill cemetery, Stitches the abomination, "
                 "worgen howls and the Defias."),
    "Wetlands": ("Eastern Kingdoms", "20-30", "Alliance", "a damp bog of dwarven strongholds and Menethil Harbor where ships sail to Teldrassil; Dragonmaw orcs "
                 "hold Grim Batol's foothills."),
    "Hillsbrad Foothills": ("Eastern Kingdoms", "20-30", "Contested", "farmlands once part of Lordaeron: Southshore for the Alliance and Tarren Mill for the Horde; "
                            "the two sides skirmish, and the Syndicate hide in Durnholde Keep."),
    "Alterac Mountains": ("Eastern Kingdoms", "30-40", "Contested", "a ruined mountain kingdom, once Alterac, lost to the Syndicate and ogres."),
    "Arathi Highlands": ("Eastern Kingdoms", "30-40", "Contested", "contested hills: Refuge Pointe for the Alliance, Hammerfall for the Horde; Stromgarde Keep's ruins and the Witherbark trolls."),
    "Stranglethorn Vale": ("Eastern Kingdoms", "30-45", "Contested", "a huge jungle on the southern tip: Booty Bay's goblin port, the Gurubashi ruins of Zul'Gurub, "
                           "raptors, tigers, panthers, and the Bloodsail Buccaneers."),
    "Swamp of Sorrows": ("Eastern Kingdoms", "35-45", "Contested", "a rotting swamp: the Temple of Atal'Hakkar sunk in the marsh, Stonard for the Horde, "
                         "and Dragonmaw and murloc threats."),
    "Badlands": ("Eastern Kingdoms", "35-45", "Contested", "barren red canyons, dwarven Kargath and Dustwind Dig, and the Uldaman titan dig-site."),
    "Searing Gorge": ("Eastern Kingdoms", "43-50", "Contested", "a smouldering gorge by Blackrock Mountain, scarred by the Dark Iron dwarves and Ragnaros's fires."),
    "Burning Steppes": ("Eastern Kingdoms", "50-58", "Contested", "a scorched wasteland: Blackrock Mountain's doors, red dragonflight and ogres."),
    "Blasted Lands": ("Eastern Kingdoms", "45-55", "Contested", "a wasteland around the Dark Portal; Nethergarde Keep holds the Alliance's vigil."),
    "Deadwind Pass": ("Eastern Kingdoms", "55-60", "Neutral", "a cursed pass: Karazhan's tower looms over Deadwind."),
    "The Hinterlands": ("Eastern Kingdoms", "40-50", "Contested", "a lush wild highland: Aerie Peak of the Wildhammer dwarves, Revantusk trolls of the Horde, and the Vilebranch trolls."),
    "Silverpine Forest": ("Eastern Kingdoms", "10-20", "Horde", "Forsaken woods: the Sepulcher, Pyrewood Village and the cursed werewolves, the Shadowfang Keep dungeon."),
    "Tirisfal Glades": ("Eastern Kingdoms", "1-10", "Horde", "the Forsaken's homeland: Deathknell, Brill, the Undercity's gate, the Scarlet Monastery nearby; "
                        "the dead walk and the Scarlet Crusade patrols."),
    "Western Plaguelands": ("Eastern Kingdoms", "50-58", "Contested", "plagued lands of Lordaeron: Andorhal, Caer Darrow, the Scarlet Bastion and the Argent Dawn camp."),
    "Eastern Plaguelands": ("Eastern Kingdoms", "53-60", "Contested", "a ruin of the Scourge: Light's Hope Chapel, Stratholme, and the dreaded Naxxramas floating overhead."),
    "Eversong Woods": ("Eastern Kingdoms", "1-10", "Horde", "the blood elves' golden woods: Sunstrider Isle, Falconwing Square, Tranquillien, and the glow of the Runestones."),
    "Ghostlands": ("Eastern Kingdoms", "10-20", "Horde", "a Scourge-ravaged forest of Quel'Thalas: Tranquillien, Zeb'Nowa and Amani trolls."),
    "Stormwind City": ("Eastern Kingdoms", "capital", "Alliance", "the Alliance capital: the Cathedral Square, the Trade District, the Mage Quarter, the Dwarven District, the Keep, the harbour, and the Deeprun Tram."),
    "Ironforge": ("Eastern Kingdoms", "capital", "Alliance", "the dwarven mountain capital: the Great Forge, the Mystic Ward, the Military Ward, the Commons, the Tinker Town of the gnomes and the Deeprun Tram."),
    "Undercity": ("Eastern Kingdoms", "capital", "Horde", "the Forsaken capital under Lordaeron: the Royal Quarter, the Apothecarium, the Trade Quarter, the Rogues' Quarter and the Ruins of Lordaeron."),
    "Silvermoon City": ("Eastern Kingdoms", "capital", "Horde", "the blood elf capital: Sunfury Spire, the Bazaar, Farstriders' Square and the Court of the Sun."),
    # Kalimdor
    "Durotar": ("Kalimdor", "1-10", "Horde", "the orcs' arid homeland: Razor Hill, Sen'jin Village of the Darkspear trolls, Orgrimmar's gates, Echo Isles, and scorpids, boars and the Burning Blade cult."),
    "Mulgore": ("Kalimdor", "1-10", "Horde", "the tauren's rolling grasslands: Camp Narache, Bloodhoof Village, the Red Rocks, Thunder Bluff on the mesa, and harpies, quilboar and Venture Co. miners."),
    "The Barrens": ("Kalimdor", "10-25", "Horde", "a vast savannah: the Crossroads, Camp Taurajo, Ratchet's goblin port, the Wailing Caverns, and centaur and quilboar threats."),
    "Teldrassil": ("Kalimdor", "1-10", "Alliance", "the World Tree and the night elves' new homeland: Shadowglen, Dolanaar, Darnassus' gate, with satyr corruption and wildlife."),
    "Darkshore": ("Kalimdor", "10-20", "Alliance", "a misty coast of the night elves: Auberdine, Ruins of Auberdine, Grove of the Ancients, murlocs and furbolgs."),
    "Ashenvale": ("Kalimdor", "18-30", "Contested", "ancient forest: Astranaar of the Alliance, Splintertree Post of the Horde; the Warsong lumber camps against the Sentinels; satyrs and Felwood's blight nearby."),
    "Stonetalon Mountains": ("Kalimdor", "15-27", "Contested", "a mountain range: Sun Rock Retreat, Stonetalon Peak, the Venture Co. mine and the Charred Vale."),
    "Desolace": ("Kalimdor", "30-40", "Contested", "barren lands of centaurs: Nijel's Point for the Alliance, Shadowprey Village for the Horde, and the Maraudon caves."),
    "Feralas": ("Kalimdor", "40-50", "Contested", "a verdant, dangerous jungle of ogres and the Gordunni; Feathermoon Stronghold, Camp Mojache, Dire Maul."),
    "Thousand Needles": ("Kalimdor", "25-35", "Contested", "great rock spires: the Freewind Post tauren, Gadgetzan's goblins nearby, and the shimmering flats of the racing goblins."),
    "Dustwallow Marsh": ("Kalimdor", "35-45", "Contested", "a swampy shore: Theramore Isle for the Alliance, Brackenwall Village for the Horde, Onyxia's Lair."),
    "Tanaris": ("Kalimdor", "40-50", "Neutral", "a vast desert: Gadgetzan, Zul'Farrak, the Caverns of Time, and the sandfury trolls."),
    "Un'Goro Crater": ("Kalimdor", "48-55", "Neutral", "a lost world of dinosaurs and fire: Marshal's Refuge, the Fire Plume Ridge and crystalline Golakka hot springs."),
    "Silithus": ("Kalimdor", "55-60", "Neutral", "a desolate land filled with Qiraji: Cenarion Hold and the Ahn'Qiraj gates."),
    "Felwood": ("Kalimdor", "48-55", "Contested", "a corrupted forest: Emerald Sanctuary, Bloodvenom Post, Talonbranch Glade, and corrupted spirits and demons."),
    "Winterspring": ("Kalimdor", "53-60", "Contested", "a frozen peak land: Everlook goblin town, Frostfire Hot Springs, and the furbolgs and ice giants."),
    "Azshara": ("Kalimdor", "45-55", "Contested", "a coastal ruin of the Highborne: Ruins of Eldarath, Bay of Storms, and the Legashi satyrs."),
    "Moonglade": ("Kalimdor", "neutral", "Neutral", "the druids' sacred grove by Lake Elune'ara, protected by Nighthaven and the Cenarion Circle."),
    "Orgrimmar": ("Kalimdor", "capital", "Horde", "the Horde capital: the Valley of Strength, Valley of Honor, Valley of Spirits, Valley of Wisdom and the Cleft of Shadow."),
    "Thunder Bluff": ("Kalimdor", "capital", "Horde", "the tauren capital on four mesas: the Elder Rise, Hunter Rise, Spirit Rise and Middle Rise, linked by rope bridges."),
    "Darnassus": ("Kalimdor", "capital", "Alliance", "the night elf capital in Teldrassil: Tradesmen's Terrace, Craftsmen's Terrace, the Temple of the Moon and Warrior's Terrace."),
    "Azuremyst Isle": ("Kalimdor", "1-10", "Alliance", "the draenei's refuge: Ammen Vale, the crashed Exodar, Azure Watch, and wildlife tainted by the crash."),
    "Bloodmyst Isle": ("Kalimdor", "10-20", "Alliance", "blighted western isle: Blood Watch, tainted wildlife and the Bloodcurse Isle."),
    "The Exodar": ("Kalimdor", "capital", "Alliance", "the draenei capital: the Vault of Lights, the Crystal Hall and the Seat of the Naaru."),
    # Outland
    "Hellfire Peninsula": ("Outland", "58-63", "Contested", "the scarred plain at the Dark Portal: Honor Hold for the Alliance, Thrallmar for the Horde, the Hellfire Citadel's fel orcs and demons."),
    "Zangarmarsh": ("Outland", "60-64", "Contested", "a fungal marsh: Telredor, Orebor Harborage, Cenarion Refuge, Sporeggar, and the Coilfang naga."),
    "Terokkar Forest": ("Outland", "62-65", "Contested", "autumn forests: Auchindoun's ruins, Shattrath's edge, bone wastes and the Skettis arakkoa."),
    "Nagrand": ("Outland", "64-67", "Contested", "green grasslands of floating islands: Garadar and Telaar and the Oshu'gun spirit-mount; ogres and the Mag'har orcs."),
    "Blade's Edge Mountains": ("Outland", "65-68", "Contested", "jagged peaks: Sylvanaar, Thunderlord Stronghold, Toshley's Station, Gruul's Lair."),
    "Netherstorm": ("Outland", "67-70", "Contested", "a storm-wrecked shard of Draenor: Area 52, Tempest Keep's blood elves, the Mana-Tombs, and the Ethereal."),
    "Shadowmoon Valley": ("Outland", "67-70", "Contested", "a dark valley of fel fire: Altar of Shadows, Wildhammer Stronghold, Illidan's Black Temple."),
    "Shattrath City": ("Outland", "capital", "Neutral", "the Naaru's city of refuge, with the Aldor and Scryers in dispute."),
    # Northrend
    "Borean Tundra": ("Northrend", "68-72", "Contested", "the Northrend gateway: Valiance Keep for the Alliance, Warsong Hold for the Horde, with Kalu'ak walrus-fishermen, naga and Scourge."),
    "Howling Fjord": ("Northrend", "68-72", "Contested", "a rugged fjord of the Vrykul and the Forsaken's Apothecary Camp: Valgarde and Vengeance Landing, proto-drakes and ice trolls."),
    "Dragonblight": ("Northrend", "71-75", "Contested", "a dragon graveyard: Wintergarde Keep, Venture Bay, Icemist Village, the Wyrmrest Temple with the dragons' Aspects."),
    "Grizzly Hills": ("Northrend", "73-75", "Contested", "dense forests: Amberpine Lodge, Conquest Hold, Venture Co. and the furbolgs and Drakkari trolls."),
    "Zul'Drak": ("Northrend", "74-77", "Contested", "the Drakkari trolls' tormented land, under the Scourge's spell; Zim'Torga and Gundrak."),
    "Sholazar Basin": ("Northrend", "76-78", "Neutral", "a lush hidden valley: the Frenzyheart and Oracles, Rainspeaker Canopy, and wild dinosaurs."),
    "The Storm Peaks": ("Northrend", "77-80", "Contested", "a mountain of titan-made halls and giants: Dun Niffelem, K3, Ulduar's gates and the Sons of Hodir."),
    "Icecrown": ("Northrend", "77-80", "Contested", "the Lich King's land: the Argent Tournament grounds, the Ebon Blade's Light's Hammer and Icecrown Citadel's spire."),
    "Crystalsong Forest": ("Northrend", "74-77", "Neutral", "a crystalline forest around Dalaran, blue and quiet."),
    "Wintergrasp": ("Northrend", "77-80", "Contested", "a contested fortress island where the factions fight for tower and keep."),
    "Dalaran": ("Northrend", "capital", "Neutral", "the Kirin Tor's floating city above Crystalsong Forest, a neutral haven with the Violet Citadel and the Krasus' Landing."),
    "Hrothgar's Landing": ("Northrend", "capital", "Contested", "a frontier camp in Icecrown."),
}

# Fallback for a module that sends only the zone's numeric id (a newer module sends the name).
ZONE_IDS = {
    12: "Elwynn Forest", 1: "Dun Morogh", 38: "Loch Modan", 40: "Westfall", 44: "Redridge Mountains", 10: "Duskwood", 11: "Wetlands",
    267: "Hillsbrad Foothills", 36: "Alterac Mountains", 45: "Arathi Highlands", 33: "Stranglethorn Vale", 8: "Swamp of Sorrows",
    3: "Badlands", 51: "Searing Gorge", 46: "Burning Steppes", 4: "Blasted Lands", 41: "Deadwind Pass", 47: "The Hinterlands",
    130: "Silverpine Forest", 85: "Tirisfal Glades", 28: "Western Plaguelands", 139: "Eastern Plaguelands", 3430: "Eversong Woods", 3433: "Ghostlands",
    1519: "Stormwind City", 1537: "Ironforge", 1497: "Undercity", 3487: "Silvermoon City",
    14: "Durotar", 215: "Mulgore", 17: "The Barrens", 141: "Teldrassil", 148: "Darkshore", 331: "Ashenvale", 406: "Stonetalon Mountains",
    405: "Desolace", 357: "Feralas", 400: "Thousand Needles", 15: "Dustwallow Marsh", 440: "Tanaris", 490: "Un'Goro Crater", 1377: "Silithus",
    361: "Felwood", 618: "Winterspring", 16: "Azshara", 493: "Moonglade", 1637: "Orgrimmar", 1638: "Thunder Bluff", 1657: "Darnassus",
    3524: "Azuremyst Isle", 3525: "Bloodmyst Isle", 3557: "The Exodar",
    3483: "Hellfire Peninsula", 3521: "Zangarmarsh", 3519: "Terokkar Forest", 3518: "Nagrand", 3522: "Blade's Edge Mountains",
    3523: "Netherstorm", 3520: "Shadowmoon Valley", 3703: "Shattrath City",
    3537: "Borean Tundra", 495: "Howling Fjord", 65: "Dragonblight", 394: "Grizzly Hills", 66: "Zul'Drak", 3711: "Sholazar Basin",
    67: "The Storm Peaks", 210: "Icecrown", 2817: "Crystalsong Forest", 4197: "Wintergrasp", 4395: "Dalaran", 4742: "Hrothgar's Landing",
}

# Conquest of Azeroth class ids (the stock ones are 1-11) for the same reason.
CLASS_IDS = {
    1: "Warrior", 2: "Paladin", 3: "Hunter", 4: "Rogue", 5: "Priest", 6: "Death Knight", 7: "Shaman", 8: "Mage", 9: "Warlock", 11: "Druid",
    12: "Barbarian", 13: "Witch Doctor", 14: "Felsworn", 15: "Witch Hunter", 16: "Stormbringer", 17: "Knight of Xoroth", 18: "Guardian",
    19: "Templar", 20: "Bloodmage", 21: "Ranger", 22: "Chronomancer", 23: "Necromancer", 24: "Pyromancer", 25: "Cultist", 26: "Starcaller",
    27: "Sun Cleric", 28: "Tinker", 29: "Venomancer", 30: "Reaper", 31: "Primalist", 32: "Runemaster",
}

RACE_IDS = {1: "Human", 2: "Orc", 3: "Dwarf", 4: "Night Elf", 5: "Undead", 6: "Tauren", 7: "Gnome", 8: "Troll", 10: "Blood Elf", 11: "Draenei"}

# Where a person of each side is sent as they grow, by level. Used when writing the next chapter of a life.
LEVEL_BRACKETS = [(1, 9), (10, 19), (20, 29), (30, 39), (40, 49), (50, 59), (60, 69), (70, 80)]

LEVEL_ZONES = {
    "Alliance": {0: ["Elwynn Forest", "Dun Morogh", "Teldrassil", "Azuremyst Isle"], 1: ["Westfall", "Redridge Mountains", "Loch Modan", "Darkshore", "Bloodmyst Isle"],
                 2: ["Duskwood", "Wetlands", "Ashenvale", "Stonetalon Mountains", "Hillsbrad Foothills"],
                 3: ["Arathi Highlands", "Stranglethorn Vale", "Desolace", "Dustwallow Marsh", "Thousand Needles"],
                 4: ["Badlands", "Searing Gorge", "Feralas", "Tanaris", "The Hinterlands", "Swamp of Sorrows", "Azshara"],
                 5: ["Burning Steppes", "Un'Goro Crater", "Felwood", "Winterspring", "Western Plaguelands", "Eastern Plaguelands", "Silithus"],
                 6: ["Hellfire Peninsula", "Zangarmarsh", "Terokkar Forest", "Nagrand", "Blade's Edge Mountains", "Netherstorm", "Shadowmoon Valley"],
                 7: ["Borean Tundra", "Howling Fjord", "Dragonblight", "Grizzly Hills", "Zul'Drak", "Sholazar Basin", "The Storm Peaks", "Icecrown"]},
    "Horde": {0: ["Durotar", "Mulgore", "Tirisfal Glades", "Eversong Woods"], 1: ["The Barrens", "Silverpine Forest", "Ghostlands"],
              2: ["Ashenvale", "Stonetalon Mountains", "Hillsbrad Foothills", "The Barrens"],
              3: ["Arathi Highlands", "Stranglethorn Vale", "Desolace", "Dustwallow Marsh", "Thousand Needles"],
              4: ["Badlands", "Searing Gorge", "Feralas", "Tanaris", "The Hinterlands", "Swamp of Sorrows", "Azshara"],
              5: ["Burning Steppes", "Un'Goro Crater", "Felwood", "Winterspring", "Western Plaguelands", "Eastern Plaguelands", "Silithus"],
              6: ["Hellfire Peninsula", "Zangarmarsh", "Terokkar Forest", "Nagrand", "Blade's Edge Mountains", "Netherstorm", "Shadowmoon Valley"],
              7: ["Borean Tundra", "Howling Fjord", "Dragonblight", "Grizzly Hills", "Zul'Drak", "Sholazar Basin", "The Storm Peaks", "Icecrown"]},
}


def bracket_of(level):
    """Index into LEVEL_BRACKETS for a level (0 for anything below 10, the last for 70 and up)."""
    try:
        level = int(level)
    except (TypeError, ValueError):
        return 0
    for index, (low, high) in enumerate(LEVEL_BRACKETS):
        if level <= high:
            return index
    return len(LEVEL_BRACKETS) - 1


def zone_entry(name):
    """(canonical name, entry) for a zone or sub-area name the game sent, or (name, None) when it is not known."""
    key = (name or "").strip().lower()
    for zone, entry in ZONES.items():
        if zone.lower() == key:
            return zone, entry
    return (name or "").strip(), None


def zone_text(zone, area=""):
    """A sentence or two a character knows about where it is. Empty for a place not in the table (the model's own lore carries it)."""
    canonical, entry = zone_entry(zone)
    if not entry:
        return ""
    where, levels, holder, note = entry
    held = {"Alliance": "held by the Alliance", "Horde": "held by the Horde", "Contested": "contested between the Alliance and the Horde",
            "Neutral": "neutral ground"}.get(holder, "")
    text = "%s (%s%s): %s" % (canonical, where, (", " + held) if held else "", note)
    if area and area.strip().lower() != canonical.lower():
        text += " You are specifically near %s." % area.strip()
    return text


def class_text(name):
    entry = CLASS_LORE.get(name)
    return entry[0] if entry else (CLASSES.get(name) or "")


def faction_of(race):
    return RACES.get(race, {}).get("faction", "")


def callings_for(race):
    return list(CALLINGS.get(race, {}))
