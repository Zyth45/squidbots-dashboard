"""Names that suit each race, for bots that were given placeholders ("Alte Bot") and for the people in a character's story.

A WoW character name is one word of 2 to 12 letters, so these are single names in the way each people names itself: Common
names for humans, harder stone-and-ale names for dwarves, quick inventive ones for gnomes, long Darnassian ones for night
elves, and so on. Hand-written lists come first; `name_for` falls back to a syllable generator when a realm has more bots than
names, so it never runs out and never repeats a name that is already taken.

Nothing here invents canon characters: the lists avoid the names of the lore's famous people (Jaina, Thrall, Tyrande...), because
a realm full of Arthas clones is its own kind of immersion break.
"""
import random
import re

NAMES = {
    "Human": {
        "male": """Aldric Bram Cedric Dorian Edmund Garrick Hadley Ivor Jorund Kellan Lorcan Merrick Norwin Osric Percival Quentin Rowan
                   Stellan Tobias Ulric Varric Wendell Alaric Baldwin Corwin Dunstan Everard Fenwick Godric Harlan Ignatius Jasper
                   Kendrick Leofric Marcus Nolan Oswin Pryce Radley Sutton Tristan Wystan Anselm Brannock Conrad Derwin Eamon Fulk""".split(),
        "female": """Adela Brenna Cassia Dorothea Elspeth Fenella Gwendolyn Helena Isolde Jocelyn Katarin Lenore Maren Nessa Odette
                     Philippa Rosalind Seraphine Thea Ursula Vivian Willa Alys Beatrix Clarice Delphine Edith Fiona Gisela Hester
                     Imogen Joanna Kerra Linnea Mabel Nerys Ottilie Petra Rhiannon Sybil Tamsin Una Verity Winifred""".split(),
        "syllables": ("Al Ber Cal Dar Ed Fal Gar Hal Ir Jor Kel Lor Mar Nor Or Pen Rod Sel Tor Wil", "ric win mund ard ley wick ton ford den mar vin rick ham"),
    },
    "Dwarf": {
        "male": """Baldrin Durgan Fargrim Gorrik Hrothi Kazdor Magnar Norgrim Orsik Rurik Thordek Ulfgar Brogan Dunmar Eitri Grimbold
                   Haldor Ingvar Jarnik Kharan Loktar Modrin Nurik Orgrim Rolgar Skarn Thrain Urgan Varnok Wulfrik Bromm Dolgan Falgrim
                   Gundar Hrolf Irongrim Jorgan Kildrin Lokmar Morgrim Nargrim Ormund Porgan Rangrim Storrik Torgrim Umrik""".split(),
        "female": """Bruna Dagna Eira Frida Gudrun Helga Ingrid Jorunn Kolga Lofna Magda Nissa Orla Runa Sigrun Thora Ulla Valka Brunhild
                     Dorrin Ebba Fenna Gerda Hilda Irma Jarla Kyra Lilja Mina Norna Olga Petra Ragna Sif Tilda Una Vigdis Yrsa Zelda""".split(),
        "syllables": ("Bor Dur Far Gor Hrot Kaz Mag Nor Ors Rur Thor Ulf Bal Dun Grim Hal", "grim dek ik rin dar gan mar nok bold drik rok gar"),
    },
    "Gnome": {
        "male": """Bixby Cogsworth Dabble Fizzle Gizmo Hobbin Ignis Jinx Klink Lumo Mekko Nibbs Oddo Pip Quill Rivet Sprocket Tinks Uzzo
                   Vixel Whirr Zibb Bolt Clank Dongle Eddo Fumble Gadd Hex Inko Jaxx Kettle Lugg Mizzle Nutt Orbo Pivot Rattle Spiff Twizzle""".split(),
        "female": """Bibble Cinda Dizzy Elixa Fizzy Gwinn Hettie Izzi Jinxie Kippa Lizzie Mabbs Nixie Ozzie Pixel Quibble Rizzo Sparkle Tilly
                     Uppa Vinka Wibble Yippi Zinnia Boltsy Clara Dottie Ember Fennel Giddy Hazel Ivy Juniper Kit Lotti Mimsy Nettle Poppet""".split(),
        "syllables": ("Biz Cog Diz Fiz Giz Hob Ink Jiz Kli Lum Mek Nib Odd Pip Riv Spr Tin Viz Whi Zib", "wick worth le zle bin bolt sy ko ty ra mo fa"),
    },
    "Night Elf": {
        "male": """Alendir Belaris Caladrel Daelon Elorin Faelar Galadris Haldrien Ilvarin Jelathor Kaelen Lorathis Maelor Naerith Orianthal
                   Pelendor Quelathar Rhaelin Shalendar Thariel Uvaris Valendis Wyndril Aelindor Belthanis Cerelion Dathrien Ethanil Fenarion
                   Galenor Hyrathil Ilthalar Jorendil Kalithar Lyrandor Mythrandir Nelendor Ormaris Phaelon Rilothar Sylvanor Taelor Vaeran""".split(),
        "female": """Alaenia Belenara Caelyra Daelia Elunara Faelira Galaela Haelenia Ilyanna Jelara Kaelira Lyssandra Maelithra Naeris Oriana
                     Phaelara Quelara Rhiannel Shaelira Thessaly Uriela Valenya Wylara Aethelia Belisara Cyrenna Delara Elenwe Faeriel Gwenara
                     Hallara Ilsandra Jenara Kyrelia Liriel Mithara Nylarra Ondara Pelena Ryssa Saelara Tiriel Vaelyra Yllara""".split(),
        "syllables": ("Ael Bel Cael Dael Elor Fael Gal Hal Ilv Jel Kael Lor Mael Nael Ori Pel Rhael Shal Thar Val", "indir aris adrel ion ithor anthal endor ariel ynna ara ena ira ael"),
    },
    "Draenei": {
        "male": """Aelorn Zeraphis Exarion Kelthian Taleris Orelis Maladin Vorrel Auradon Belanor Cyrion Dalthis Elaran Fenorus Garrion
                   Halarion Iridan Jorelan Kaldorian Lunarion Marandil Naladin Orvalis Perrian Quelrion Restalan Sarenor Teradon Uvarion
                   Velanor Xerion Zandrel Aloren Berion Calthan Doranis Elakar Fandoral Gorithan Haldaran Ishalan Keldorin Lothrian""".split(),
        "female": """Zuraka Aurelia Belara Cyrena Delira Elyssa Faria Gelani Halira Ilanya Jaretha Kaelara Lyrena Mariel Nalira Orlena
                     Perenna Quenara Ruvena Selara Taleena Uriah Valeria Xandra Yvaine Zerena Alinara Belinda Caldera Dariel Eluna Fenara
                     Galena Hylara Iselda Jeralda Kyrene Laranya Meralda Nerissa Olanya Pelara Rhilana Sylara Taranya""".split(),
        "syllables": ("Ael Zer Ex Kel Tal Or Mal Vor Aur Bel Cyr Dal Ela Fen Gar Hal Iri Jor", "orn aphis arion thian eris elis adin rel adon anor ion this aran"),
    },
    "Orc": {
        "male": """Durak Gorgrim Thokk Ruzgar Mogor Brakka Dargul Grakk Harrok Jorgrak Krusk Lokgar Morrak Nazgrim Orgak Ragnuk Skarr
                   Thrakk Ugrash Vorgul Zugrak Aggar Bolgrim Crushk Drogath Eggorn Fenrak Gashnak Hrokk Ironfang Jukk Kharg Lugdush
                   Mukkar Nargul Ozruk Prokk Ruukk Shagrak Tarkul Urzul Vrokk Warguk Yazgal""".split(),
        "female": """Draka Grelka Zurka Yorga Brakka Kagra Lurga Mogra Nazra Ogrisha Rukka Shazra Thurka Ulgra Vurka Wazra Yazka Zogra
                     Agra Bolka Dazra Ekka Fugra Gorka Hazra Irka Jazra Kazra Lagra Mazra Norga Orka Puzra Qazra Rogra Sazra Tazra Urka""".split(),
        "syllables": ("Dur Gor Thok Ruz Mog Brak Dar Gra Har Jor Kru Lok Mor Naz Org Rag Ska Thr Ugr Vor", "ak grim kk gar gul ush nak rok zak dush rak mar"),
    },
    "Undead": {
        "male": """Aldous Bartholomew Cornelius Desmond Ephraim Fitzgerald Gideon Horace Ignatius Jedediah Lazarus Mortimer Nathaniel
                   Obadiah Percival Quincy Reginald Silas Thaddeus Ulysses Vincent Winston Alistair Barnaby Crispin Dunstan Edmund
                   Finnian Grimsby Hobart Isidore Jerome Kendrick Lucian Mordecai Neville Octavian Peregrine Roderick Sebastian Tobias""".split(),
        "female": """Agatha Beatrice Cordelia Drusilla Eleanor Florence Genevieve Hortense Isadora Josephine Lucretia Mathilde Nerissa
                     Ophelia Penelope Rosalind Seraphina Theodora Ursula Vesper Winifred Adelaide Bernadette Constance Dorcas Eulalia
                     Felicity Gwendolen Henrietta Imelda Judith Lavinia Millicent Nadine Odalys Prudence Rowena Sabine Temperance Verity""".split(),
        "syllables": ("Mor Gra Cor Des Eph Fit Gid Hor Laz Mor Nat Obe Per Qui Reg Sil Tha Vin Win", "ton ley mund wick ius ard ald ent wyn ric ish ow ane"),
    },
    "Tauren": {
        "male": """Ahnuk Bahrak Cahlen Dahnu Eghak Gruhnak Hahnu Kahlek Mahnu Nuhkak Ohrnu Pahlek Rahnak Sahnu Tahrek Uhnak Wahnu Zahnek
                   Bloodshadow Brightmane Dawnstrider Earthwalker Highmesa Longhorn Plainswind Redcloud Skyseer Stonehoof Thunderhorn Windtotem
                   Ahnek Baruk Cheyak Dohnu Ehnuk Grahlak Hokan Imak Kohnu Lahnek""".split(),
        "female": """Ahnaya Bahnu Cahnaya Dahnaya Ehlani Hahnaya Kahlani Lahnaya Mahnaya Nahlani Ohnaya Pahlani Rahnaya Sahnaya Tahlani Uhnaya
                     Wahnaya Yahnaya Zahlani Brightdawn Cloudsong Dawnfeather Earthsinger Greymane Hornsong Moonhoof Rainwalker Sunbloom Windsinger
                     Ahlani Bahlani Chahna Dahlani Ehnaya Fahlani Gahnaya""".split(),
        "syllables": ("Ah Bah Cah Dah Egh Gruh Hah Kah Mah Nuh Ohr Pah Rah Sah Tah Uh Wah Zah", "nu nak lek rek ak nek lani naya hak mak kon uk"),
    },
    "Troll": {
        "male": """Jinzo Mojar Rokhan Shazu Tazjin Vazzik Zandak Bazrul Dojan Gorza Hexuk Jankor Kozu Lazzik Mazzor Nezzik Ozrak Razzor
                   Shokar Tuzzik Uzzik Voljak Zalmo Zinjar Zulkir Bwonjin Dakazi Hakka Jomba Kojo Lukor Mazuri Nazjin Sazzi Taztor Vorjin Wazzo""".split(),
        "female": """Jazzra Mazra Nazra Zuri Zandra Bazra Dazrel Hexra Jinra Kazra Lazra Mojra Nazjra Ozra Razra Shazra Tazra Uzra Vazra Zazra
                     Zinjra Akzi Bazzi Chazzi Dazzi Eezi Fazzi Gazzi Hazzi Izzi Jazzi Kazzi Lazzi Mazzi Nazzi Ozzi Pazzi Sazzi Tazzi Vazzi Zazzi""".split(),
        "syllables": ("Jin Moj Rok Sha Taz Vaz Zan Baz Doj Gor Hex Jan Koz Laz Maz Nez Ozr Raz Sho Tuz", "zo jar han zu jin zik dak rul za uk kor mo lo"),
    },
    "Blood Elf": {
        "male": """Aldanis Belorin Caelith Dorelan Elvarith Faeldor Galadrin Halvarin Ilithar Jaelion Kaelthas Lorathil Melandor Nalorin
                   Orelion Perithan Quelthis Rilvorin Sunthal Thalorin Ulvarion Valorin Wynthal Aerendil Belthandris Caldrin Dathorin
                   Eledan Farenor Gilthalan Halanil Ilvaran Jerithal Kelendor Lathorin Melthis Naldrin Orithan Pelathor Rhalnis Sylvaran""".split(),
        "female": """Aelissa Belindra Caelwyn Dalira Elathra Faelwyn Galindra Halira Ilsara Jaelira Kaelara Lorelei Melwyn Nalissa Orelle
                     Perinna Quelissa Rhaella Sunwyn Thalira Ulwen Valessa Wynlara Aeriel Belisse Caldris Delwyn Eluna Fenlara Gilra
                     Halissa Ilwyn Jaelle Keldra Lissara Maelwyn Naelle Orissa Pelara Raelle Salindra Taelyn Valdris""".split(),
        "syllables": ("Ael Bel Cael Dor Elv Fael Gal Hal Ili Jael Kael Lor Mel Nal Ore Per Que Ril Sun Tha", "anis orin ith elan arith dor drin varin thar ion thil andor wyn"),
    },
}


# Family names and epithets, in the way each people has them. Conquest of Azeroth characters may have two words, a first name and a
# surname, which is how a bot can be "Elorin Moonwhisper" with playerbots' own " Bot" surname left alone.
SURNAMES = {
    "Human": """Ashford Blackwood Fairwind Thornfield Hartwell Whitmore Stonebridge Greymoor Harrowgate Oakheart Redfern Silverbrook Brightwater
                Coldwell Dunmore Eastwood Goldacre Highgate Ironwood Kingsley Lockwood Moorcroft Northcott Pennywell Ravenscar Stormwood
                Tanner Cooper Fletcher Miller Thatcher Wainwright Carter Mason Fairbanks Grimsby Hollis Kestrel Larkspur Merriweather""".split(),
    "Dwarf": """Ironbeard Stonefist Deepdelver Hammerfall Forgeborn Anvilhand Coalbeard Goldvein Rockbreaker Thunderaxe Frostbeard Steelmantle
                Stoutshield Bronzebrow Axebreaker Brewbelly Granitehelm Oreseeker Runecarver Cragfist Deepforge Flintbeard Gruffaxe Ironbrow
                Mountainhelm Pickaxe Quarryman Redbeard Slatehand Stonehelm Tunnelwise Underhill""".split(),
    "Gnome": """Cogspinner Gearwhirl Fizzlebang Wrenchturn Boltwhistle Tinkerspark Springcoil Clinkbottom Whizzlebolt Rustygear Copperpot
                Pinwheel Gizzlecrank Oilwick Zapwhistle Clockwise Cranktwist Dabblewick Fuseblast Gadgetwhirl Hexnut Ratchet Sparkgear
                Tickletock Widgetwork Zigzagwick""".split(),
    "Night Elf": """Moonwhisper Starweaver Dawnstrider Bladesong Nightbreeze Silverleaf Moonshadow Dawnbringer Starsinger Moonbrook Thornwood
                    Leafsong Duskwalker Brightmoon Everbough Swiftarrow Greenmantle Lightfoot Mistwalker Nightglaive Oakenshield Riverglade
                    Shadowleaf Sunshadow Wildbranch Wyndsong""".split(),
    "Draenei": """Dawnseeker Starborn Lightwarden Crystalmind Soulweaver Farwalker Sunbringer Mistwalker Azurewing Dawnwatcher Lightbearer
                  Stargazer Prismheart Shardwalker Hopebringer Vigilant Crystalsong Brightforge Everlight Farseer Gladeheart""".split(),
    "Orc": """Bonecrusher Wolfsbane Ironjaw Redtusk Stormfist Axebiter Blacktooth Skullcleaver Warbringer Thunderfist Rageborn Gorefang Ashtusk
              Steelclaw Hellhowl Bloodmaw Deathgrip Fangbreaker Grimscar Ironhide Stonefang Shadowmane Spearbreaker Wargrip Wrathblade""".split(),
    "Tauren": """Skyhorn Windtotem Highmountain Thunderhorn Stonehoof Redcloud Plainstrider Dawnstrider Wildmane Earthsong Rainrunner Skychaser
                 Bloodmane Brightmane Cloudsong Dustwalker Farhoof Graymane Highrock Moonhorn Sunhoof Thundermane Whitemane Windseeker""".split(),
    "Troll": """Darkspear Echoshade Voodoofang Spiritwalker Stormcaller Drumbeat Seaspear Tidebreaker Hexbinder Jungleclaw Sunfang Bonespear
                Venomtongue Shadowhex Skullgrin Mojohand Rootwalker Swampstalker Fireeye Loabound Tuskbreaker Witherstep""".split(),
    "Blood Elf": """Silversun Dawnblade Sunsworn Brightspear Starfall Suncaller Evensong Duskbloom Goldenleaf Sunblade Brightwing Dawnsinger
                    Fairwind Lightsworn Moonglade Sunhawk Spellbinder Sunwhisper Starbright Sunshield Thalassar Dawnguard""".split(),
}
SURNAMES["Undead"] = SURNAMES["Human"]      # the Forsaken keep the names they had in life

# Unpronounceable or unfortunate once glued together by the generator: dropped rather than rerolled.
BLOCKED = re.compile(r"(?:fuck|shit|cunt|nigg|fagg|rape|nazi|hitler|cock|dick|piss|slut|whor|^tits?$)", re.I)
WOW_NAME = re.compile(r"^[A-Za-z]{2,12}$")


def clean_name(name):
    """The name as WoW writes it: letters only, first letter capital, the rest lower case, at most 12 letters."""
    letters = re.sub(r"[^A-Za-z]", "", name or "")[:12]
    return letters[:1].upper() + letters[1:].lower()


def valid(name):
    return bool(WOW_NAME.match(name or "")) and not BLOCKED.search(name)


def _generated(race, gender, rng, parts=2):
    """A name built from the race's syllables: two parts first, three when the two-part names are all taken."""
    low, high = NAMES[race]["syllables"]
    for _ in range(40):
        name = clean_name(rng.choice(low.split()) + "".join(rng.choice(high.split()) for _ in range(parts - 1)))
        if gender == "female" and not name.endswith("a"):
            name = clean_name(name[:11] + rng.choice(["a", "ia", "ya", "ea"]))
        # A long name is a mouthful in chat: nine letters at most, except for gnomes (whose names are meant to be silly) and three-part names.
        if valid(name) and 4 <= len(name) <= (12 if race == "Gnome" or parts == 3 else 9):
            return name
    return clean_name(low.split()[0] + high.split()[0])


def name_for(race, gender, taken, rng=None):
    """A name that suits this race and gender and is not in `taken` (compared without case). Raises KeyError for an unknown race."""
    rng = rng or random.Random()
    gender = "female" if str(gender).lower() in ("female", "1", "f") else "male"
    pool = [name for name in NAMES[race][gender] if valid(clean_name(name))]
    wanted = {name.lower() for name in taken}
    rng.shuffle(pool)
    for name in pool:
        name = clean_name(name)
        if name.lower() not in wanted:
            return name
    for parts in (2, 3):
        for _ in range(600):
            name = _generated(race, gender, rng, parts)
            if name.lower() not in wanted:
                return name
    raise RuntimeError("could not find a free %s name" % race)


def person_name(race, gender, rng):
    """A first name for someone in a character's story (a mentor, a sibling, a rival): the hand-written lists only."""
    gender = "female" if gender == "female" else "male"
    return clean_name(rng.choice(NAMES[race][gender]))


def full_name(race, gender, taken, rng=None):
    """"First Surname" for a character that may have two words: a first name for the race, and a surname for the people. Not in `taken`
    (compared without case) as a whole, and the first name is not one that is already taken as a first name either, so a realm has
    no two Aldrics unless it must."""
    rng = rng or random.Random()
    wanted = {name.lower() for name in taken}
    firsts = {name.split(" ")[0].lower() for name in taken}
    pool = [clean_name(n) for n in NAMES[race]["female" if str(gender).lower() in ("female", "1", "f") else "male"] if valid(clean_name(n))]
    surnames = [n for n in SURNAMES[race] if valid(clean_name(n))]
    rng.shuffle(pool)
    for first in pool + [name_for(race, gender, firsts, rng)]:
        if first.lower() in firsts:
            continue
        for _ in range(30):
            candidate = "%s %s" % (first, clean_name(rng.choice(surnames)))
            if candidate.lower() not in wanted:
                return candidate
    # Every first name is taken: share one, but never a whole name.
    for _ in range(600):
        candidate = "%s %s" % (clean_name(rng.choice(pool)), clean_name(rng.choice(surnames)))
        if candidate.lower() not in wanted:
            return candidate
    raise RuntimeError("could not find a free %s name" % race)


def valid_full_name(name):
    """One or two words, each 2 to 12 letters."""
    parts = (name or "").split(" ")
    return 1 <= len(parts) <= 2 and all(valid(part) for part in parts)
