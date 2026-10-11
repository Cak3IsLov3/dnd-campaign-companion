"""Default NPC generator tables, loaded by a data migration."""

NAMES = {
    "Human": [
        "Aldric Thorne",
        "Mira Castellan",
        "Joren Blackwood",
        "Elsbeth Marrow",
        "Tomas Reed",
        "Sabine Holloway",
        "Garrick Vance",
        "Ilse Fairweather",
    ],
    "Elf": [
        "Aelar Moonwhisper",
        "Sylvara Nightbreeze",
        "Thamior Galanodel",
        "Lia Amastacia",
        "Erevan Ilphelkiir",
        "Naivara Siannodel",
    ],
    "Dwarf": [
        "Borin Ironfist",
        "Helga Stonebrew",
        "Durgan Rumnaheim",
        "Vistra Balderk",
        "Thorek Fireforge",
        "Gunnloda Gorunn",
    ],
    "Halfling": [
        "Milo Tealeaf",
        "Rosie Underbough",
        "Perrin Goodbarrel",
        "Verna Highhill",
        "Corrin Tosscobble",
        "Seraphina Brushgather",
    ],
    "Gnome": [
        "Fizwick Nackle",
        "Nyx Timbers",
        "Boddynock Folkor",
        "Ellywick Raulnor",
        "Dimble Scheppen",
        "Zanna Garrick",
    ],
    "Half-Orc": [
        "Grusk Bonecrusher",
        "Shava Redtusk",
        "Dench Ironhide",
        "Kansif Stormcaller",
        "Thokk Ashfang",
        "Volen the Quiet",
    ],
    "Tiefling": [
        "Zariel Ashgrave",
        "Kallista Vex",
        "Mordai Embershade",
        "Nemeia Duskwalker",
        "Skamos Thorn",
        "Orianna Hope",
    ],
    "Dragonborn": [
        "Arjhan Clethtinthiallor",
        "Sora Kerrhylon",
        "Balasar Myastan",
        "Kava Daardendrian",
        "Rhogar Shestendeliath",
        "Thava Turnuroth",
    ],
}

# (value, weight): common entries get a higher weight.
OCCUPATIONS = [
    ("Innkeeper", 5),
    ("Blacksmith", 5),
    ("Farmer", 6),
    ("Merchant", 5),
    ("City guard", 5),
    ("Fisher", 3),
    ("Herbalist", 3),
    ("Scribe", 3),
    ("Stable hand", 3),
    ("Carpenter", 3),
    ("Priest", 2),
    ("Sailor", 3),
    ("Hunter", 3),
    ("Tax collector", 2),
    ("Minstrel", 2),
    ("Gravedigger", 1),
    ("Alchemist", 1),
    ("Smuggler", 1),
    ("Retired adventurer", 1),
    ("Court wizard", 1),
]

TRAITS = [
    ("Speaks in a whisper, even when excited", 2),
    ("Laughs at their own jokes", 3),
    ("Never makes eye contact", 2),
    ("Compulsively generous", 2),
    ("Suspicious of strangers", 4),
    ("Collects odd trinkets", 2),
    ("Hums old war songs", 2),
    ("Quotes proverbs nobody knows", 2),
    ("Blunt to the point of rudeness", 3),
    ("Endlessly curious", 3),
    ("Always eating something", 2),
    ("Deeply superstitious", 3),
    ("Fiercely proud of their home town", 2),
    ("Forgets names constantly", 2),
    ("Unfailingly polite", 3),
]

SECRETS = [
    ("Owes a dangerous amount of money to a crime boss", 3),
    ("Is secretly of noble birth", 1),
    ("Witnessed a murder and never told anyone", 2),
    ("Spies for a rival faction", 2),
    ("Is hiding a cursed heirloom", 1),
    ("Deserted from the army years ago", 2),
    ("Has been stealing from their employer", 3),
    ("Is hiding a relative wanted by the law", 2),
    ("Made a pact they deeply regret", 1),
    ("Is not who they claim to be", 1),
    ("Knows where an old treasure is buried", 1),
    ("Poisoned a rival and got away with it", 1),
]

MOTIVATIONS = [
    ("Wants to provide for their family", 5),
    ("Seeks revenge for an old wrong", 2),
    ("Craves recognition and status", 3),
    ("Wants to leave this town forever", 3),
    ("Is searching for a lost sibling", 2),
    ("Wants to pay off a debt", 3),
    ("Hopes to earn a place in a guild", 2),
    ("Is devoted to their faith", 2),
    ("Wants to be left alone", 2),
    ("Dreams of adventure", 2),
    ("Protects a secret at any cost", 1),
    ("Wants to restore the family name", 1),
]


def default_rows():
    """Yield (category, race, value, weight) for every default row."""
    for race, names in NAMES.items():
        for name in names:
            yield "name", race, name, 1
    for category, rows in [
        ("occupation", OCCUPATIONS),
        ("trait", TRAITS),
        ("secret", SECRETS),
        ("motivation", MOTIVATIONS),
    ]:
        for value, weight in rows:
            yield category, "", value, weight
